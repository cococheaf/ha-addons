from dataclasses import dataclass
from threading import Lock

from flask import Flask, jsonify
import logging
import math
import os
import time

import requests

app = Flask(__name__)

LOG_LEVELS = {
    "TRACE": logging.DEBUG,
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "NOTICE": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "FATAL": logging.FATAL,
}
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVELS.get(LOG_LEVEL, logging.INFO))
logger = logging.getLogger("ecotracker_meter_bridge")

# Avoid access log spam when SunEnergy XT polls every second.
logging.getLogger("werkzeug").setLevel(logging.ERROR)


@dataclass(frozen=True)
class Settings:
    ha_url: str
    ha_token: str
    entity_power: str
    power_sign: float
    power_multiplier: float
    power_offset: float
    cache_ttl_seconds: float
    stale_after_seconds: int
    round_digits: int
    request_timeout_seconds: float


def env_float(name, default, minimum=None):
    value = os.getenv(name, str(default))
    try:
        number = float(value)
    except (TypeError, ValueError):
        logger.warning("Invalid %s=%r, using %s", name, value, default)
        number = float(default)

    if math.isnan(number) or math.isinf(number):
        logger.warning("Invalid %s=%r, using %s", name, value, default)
        number = float(default)

    if minimum is not None and number < minimum:
        logger.warning("%s=%s is below minimum %s, using %s", name, number, minimum, minimum)
        return float(minimum)

    return number


def env_int(name, default, minimum=None, maximum=None):
    value = os.getenv(name, str(default))
    try:
        number = int(value)
    except (TypeError, ValueError):
        logger.warning("Invalid %s=%r, using %s", name, value, default)
        number = int(default)

    if minimum is not None and number < minimum:
        logger.warning("%s=%s is below minimum %s, using %s", name, number, minimum, minimum)
        number = int(minimum)

    if maximum is not None and number > maximum:
        logger.warning("%s=%s is above maximum %s, using %s", name, number, maximum, maximum)
        number = int(maximum)

    return number


def load_settings():
    ha_url = os.getenv("HA_URL", "http://supervisor/core").strip().rstrip("/")
    if not ha_url:
        ha_url = "http://supervisor/core"

    return Settings(
        ha_url=ha_url,
        ha_token=os.getenv("HA_TOKEN", "").strip(),
        entity_power=os.getenv("ENTITY_POWER", "").strip(),
        power_sign=env_float("POWER_SIGN", 1.0),
        power_multiplier=env_float("POWER_MULTIPLIER", 1.0, minimum=0.0),
        power_offset=env_float("POWER_OFFSET", 0.0),
        cache_ttl_seconds=env_float("CACHE_TTL_SECONDS", 1.0, minimum=0.0),
        stale_after_seconds=env_int("STALE_AFTER_SECONDS", 15, minimum=1),
        round_digits=env_int("ROUND_DIGITS", 2, minimum=0, maximum=6),
        request_timeout_seconds=env_float("REQUEST_TIMEOUT_SECONDS", 3.0, minimum=0.1),
    )


SETTINGS = load_settings()


def empty_cache():
    return {
        "timestamp": 0.0,
        "raw_power": 0.0,
        "power": 0.0,
        "last_success": None,
        "last_error": None,
    }


cache = empty_cache()
cache_lock = Lock()


def reset_cache():
    global cache
    with cache_lock:
        cache = empty_cache()


def ha_headers():
    headers = {"Content-Type": "application/json"}

    if SETTINGS.ha_token:
        headers["Authorization"] = f"Bearer {SETTINGS.ha_token}"

    return headers


def safe_float(value, default=0.0):
    try:
        number = float(value)
        if math.isnan(number) or math.isinf(number):
            return default
        return number
    except Exception:
        return default


def ha_api_url():
    if SETTINGS.ha_url.endswith("/api"):
        return SETTINGS.ha_url
    return f"{SETTINGS.ha_url}/api"


def transform_power(raw_power):
    return raw_power * SETTINGS.power_multiplier * SETTINGS.power_sign + SETTINGS.power_offset


def get_ha_state(entity_id, fallback=0.0):
    if not entity_id:
        return fallback, "entity_power is empty"

    url = f"{ha_api_url()}/states/{entity_id}"

    try:
        response = requests.get(
            url,
            headers=ha_headers(),
            timeout=SETTINGS.request_timeout_seconds,
        )
        response.raise_for_status()

        payload = response.json()
        state = payload.get("state")

        if state in (None, "", "unknown", "unavailable"):
            return fallback, f"{entity_id}: state is {state}"

        return safe_float(state, fallback), None

    except Exception as exc:
        return fallback, f"{entity_id}: {exc}"


def update_power_if_needed():
    now = time.time()

    with cache_lock:
        if now - cache["timestamp"] <= SETTINGS.cache_ttl_seconds:
            return cache["power"]
        fallback_raw = cache["raw_power"]

    raw_power, error = get_ha_state(SETTINGS.entity_power, fallback_raw)
    power = transform_power(raw_power)

    with cache_lock:
        cache["timestamp"] = now
        cache["raw_power"] = raw_power
        cache["power"] = power
        cache["last_error"] = error

        if error is None:
            cache["last_success"] = int(now)
        else:
            logger.warning(error)

        return cache["power"]


def is_stale():
    with cache_lock:
        last_success = cache["last_success"]

    if last_success is None:
        return True

    return int(time.time()) - int(last_success) > SETTINGS.stale_after_seconds


def cache_snapshot():
    with cache_lock:
        return dict(cache)


def rounded(value):
    return round(value, SETTINGS.round_digits)


@app.route("/")
def root():
    return jsonify({
        "name": "EcoTracker Meter Bridge",
        "status": "ok",
        "endpoint": "/v1/json",
    })


@app.route("/v1/json")
def ecotracker_json():
    power = update_power_if_needed()
    snapshot = cache_snapshot()
    stale = is_stale()

    # SunEnergy XT EcoTracker direct mode reads dat_str.pwr = "power".
    # Additional fields are harmless and useful for debugging.
    return jsonify({
        "power": rounded(power),
        "valid": snapshot["last_error"] is None and not stale,
        "stale": stale,
        "timestamp": int(time.time()),
    })


@app.route("/health")
def health():
    power = update_power_if_needed()
    snapshot = cache_snapshot()
    stale = is_stale()

    status = "ok"
    if snapshot["last_error"] is not None:
        status = "degraded"
    if stale:
        status = "stale"

    return jsonify({
        "status": status,
        "ha_url": SETTINGS.ha_url,
        "entity_power": SETTINGS.entity_power,
        "power_sign": SETTINGS.power_sign,
        "power_multiplier": SETTINGS.power_multiplier,
        "power_offset": SETTINGS.power_offset,
        "raw_power": rounded(snapshot["raw_power"]),
        "power": rounded(power),
        "cache_ttl_seconds": SETTINGS.cache_ttl_seconds,
        "stale_after_seconds": SETTINGS.stale_after_seconds,
        "request_timeout_seconds": SETTINGS.request_timeout_seconds,
        "last_success": snapshot["last_success"],
        "last_error": snapshot["last_error"],
        "has_token": bool(SETTINGS.ha_token),
        "ecotracker_endpoint": "/v1/json",
    })


if __name__ == "__main__":
    port = env_int("PORT", 8080, minimum=1, maximum=65535)
    app.run(host="0.0.0.0", port=port)
