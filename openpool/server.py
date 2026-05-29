#!/usr/bin/env python3
"""OpenPool Home Assistant add-on server.

The server owns OpenPool runtime state, serves the tablet UI and proxies Home
Assistant API calls. Keeping controller state here means every browser sees the
same state and pump runtimes/jobs survive frontend reloads and add-on restarts.
"""

from __future__ import annotations

import json
import mimetypes
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlparse
from urllib.request import Request, urlopen


PORT = int(os.environ.get("OPENPOOL_PORT", "8099"))
WWW_ROOT = Path(os.environ.get("OPENPOOL_WWW", "/app/www")).resolve()
OPTIONS_PATH = Path(os.environ.get("OPENPOOL_OPTIONS", "/data/options.json"))
STATE_PATH = Path(os.environ.get("OPENPOOL_STATE", "/data/openpool_state.json"))
SUPERVISOR_HA_API_BASE = "http://supervisor/core/api"
DEFAULT_HA_URL = "http://homeassistant:8123"
DEFAULT_POLL_INTERVAL_SECONDS = 1
DEFAULT_LOG_LEVEL = "info"
PULSE_TRIGGER_WINDOW_SECONDS = 90
PULSE_RESTORE_GRACE_SECONDS = 20
RUN_ON_SECONDS = 5 * 60
RESTART_PULSE_SECONDS = 5
CONTINUOUS_RESTART_INTERVAL_SECONDS = 12 * 60 * 60
COMMAND_LOG_LIMIT = 6
WEATHER_FORECAST_REFRESH_SECONDS = 12 * 60 * 60
HEATER_ACTIVE_POWER_W = 100
DEFAULT_WEATHER_ENTITY = "weather.home"
DEFAULT_HEATER_START_MODE = "Auto"
FALLBACK_HEATER_START_MODES = ("Heat", "Cool", "Auto", "Boost Heat", "Silent Heat")
BAD_WEATHER_CONDITIONS = {
    "cloudy",
    "fog",
    "hail",
    "lightning",
    "lightning-rainy",
    "pouring",
    "rainy",
    "snowy",
    "snowy-rainy",
    "windy",
    "windy-variant",
    "exceptional",
}
BATHING_WEATHER_CONDITIONS = {"sunny", "clear-night", "partlycloudy"}
WEATHER_MODE_OPTIONS = {"Empfehlung", "Automatik"}
WEATHER_MANAGED_PUMP_MODES = {"Badebetrieb", "Schlechtwetter"}

DEFAULT_ENTITIES = {
    "pump_switch": "switch.poolpumpe",
    "heater_climate": "climate.poolheizung",
    "heater_operation_mode": "select.poolheizung_betriebsmodus",
    "pv_generation": "sensor.pv_erzeugungsleistung",
    "pv_export": "sensor.stromzahler_active_power_minus",
    "grid_import": "sensor.stromzahler_active_power_plus",
    "pump_power": "sensor.poolpumpe_leistung",
    "pump_current": "sensor.poolpumpe_current",
    "pump_voltage": "sensor.poolpumpe_spannung",
    "pump_signal": "sensor.poolpumpe_signal",
    "heater_power": "sensor.poolheizung_leistung",
    "heater_current": "sensor.poolheizung_netzstrom",
    "heater_voltage": "sensor.poolheizung_netzspannung",
    "heater_fan": "sensor.poolheizung_lufter",
    "heater_ambient": "sensor.poolheizung_umgebungsluft_temperatur",
    "heater_water_in": "sensor.poolheizung_wassertemperatur_eingang",
    "heater_water_out": "sensor.poolheizung_wassertemperatur_ausgang",
}

UI_ENTITY_KEYS = {
    "entity-pump-switch": "pump_switch",
    "entity-heater-climate": "heater_climate",
    "entity-heater-operation-mode": "heater_operation_mode",
    "entity-pv-generation": "pv_generation",
    "entity-pv-export": "pv_export",
    "entity-grid-import": "grid_import",
    "entity-pump-power": "pump_power",
    "entity-pump-current": "pump_current",
    "entity-pump-voltage": "pump_voltage",
    "entity-pump-signal": "pump_signal",
    "entity-heater-power": "heater_power",
    "entity-heater-current": "heater_current",
    "entity-heater-voltage": "heater_voltage",
    "entity-heater-fan": "heater_fan",
    "entity-heater-ambient": "heater_ambient",
    "entity-heater-water-in": "heater_water_in",
    "entity-heater-water-out": "heater_water_out",
}

HEATER_ENTITY_KEYS = {
    "heater_climate",
    "heater_operation_mode",
    "heater_power",
    "heater_current",
    "heater_voltage",
    "heater_fan",
    "heater_ambient",
    "heater_water_in",
    "heater_water_out",
}

LOG_LEVELS = {
    "trace": 10,
    "debug": 20,
    "info": 30,
    "notice": 35,
    "warning": 40,
    "error": 50,
    "fatal": 60,
}


def read_options() -> dict:
    if not OPTIONS_PATH.exists():
        return {}

    try:
        return json.loads(OPTIONS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def configured_log_level() -> str:
    level = str(read_options().get("log_level") or DEFAULT_LOG_LEVEL).lower()
    return level if level in LOG_LEVELS else DEFAULT_LOG_LEVEL


def should_log(level: str) -> bool:
    configured = LOG_LEVELS.get(configured_log_level(), LOG_LEVELS[DEFAULT_LOG_LEVEL])
    requested = LOG_LEVELS.get(level, LOG_LEVELS[DEFAULT_LOG_LEVEL])
    return requested >= configured


def log(level: str, message: str) -> None:
    if should_log(level):
        print(f"[openpool] {message}", flush=True)


def public_options(options: dict) -> dict:
    public = json.loads(json.dumps(options))
    connection = public.get("connection")

    if isinstance(connection, dict):
        access_token = str(connection.get("access_token") or "").strip()
        connection["access_token"] = ""
        connection["access_token_configured"] = bool(access_token)

    return public


def read_s6_environment(name: str) -> str:
    for folder in ("/run/s6/container_environment", "/var/run/s6/container_environment"):
        path = Path(folder) / name
        if path.exists():
            try:
                return path.read_text(encoding="utf-8").strip().strip("\x00")
            except OSError:
                pass
    return ""


def supervisor_token() -> str:
    return (
        os.environ.get("SUPERVISOR_TOKEN")
        or os.environ.get("HASSIO_TOKEN")
        or read_s6_environment("SUPERVISOR_TOKEN")
        or read_s6_environment("HASSIO_TOKEN")
        or ""
    )


def entity_domain(entity_id: str) -> str:
    return entity_id.split(".", 1)[0] if "." in entity_id else "homeassistant"


def now_ts() -> float:
    return time.time()


def today_key() -> str:
    return time.strftime("%Y-%m-%d", time.localtime())


def day_key_for_ts(value: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(value))


def normalize_heater_start_mode(value: object, options: list[str] | tuple[str, ...] | None = None) -> str:
    available = [str(option).strip() for option in (options or FALLBACK_HEATER_START_MODES) if str(option).strip()]
    requested = str(value or "").strip().lower()
    for mode in available:
        if requested == mode.lower():
            return mode
    for mode in available:
        if DEFAULT_HEATER_START_MODE.lower() == mode.lower():
            return mode
    return available[0] if available else DEFAULT_HEATER_START_MODE


def seconds_to_clock(value: float | None) -> str:
    if not value:
        return "--:--"
    return time.strftime("%H:%M", time.localtime(value))


def clock_to_day_ts(value: object, reference_ts: float) -> float | None:
    try:
        parsed = time.strptime(str(value), "%H:%M")
    except ValueError:
        return None

    current = time.localtime(reference_ts)
    return time.mktime(
        (
            current.tm_year,
            current.tm_mon,
            current.tm_mday,
            parsed.tm_hour,
            parsed.tm_min,
            0,
            current.tm_wday,
            current.tm_yday,
            current.tm_isdst,
        )
    )


class HomeAssistantClient:
    def __init__(self) -> None:
        self._last_auth_source = "missing"

    def credentials(self) -> tuple[str, str, str] | None:
        connection = read_options().get("connection") or {}
        auth_mode = str(connection.get("auth_mode") or "supervisor").strip()
        access_token = str(connection.get("access_token") or "").strip()
        homeassistant_url = str(connection.get("homeassistant_url") or DEFAULT_HA_URL).rstrip("/")

        if auth_mode == "openpool_user_token":
            if access_token:
                return f"{homeassistant_url}/api", access_token, "openpool_user_token"
            return None

        token = supervisor_token()
        if token:
            return SUPERVISOR_HA_API_BASE, token, "supervisor"

        if access_token:
            return f"{homeassistant_url}/api", access_token, "configured_token"

        return None

    def auth_status(self) -> str:
        credentials = self.credentials()
        if not credentials:
            return "missing token"
        labels = {
            "supervisor": "Supervisor token available",
            "openpool_user_token": "using configured OpenPool user token",
            "configured_token": "using configured fallback token",
        }
        return labels.get(credentials[2], "using configured token")

    def auth_error_detail(self) -> str:
        connection = read_options().get("connection") or {}
        auth_mode = str(connection.get("auth_mode") or "supervisor").strip()
        if auth_mode == "openpool_user_token":
            return "connection.auth_mode is openpool_user_token but connection.access_token is empty."
        return "SUPERVISOR_TOKEN is missing and no fallback access token is configured."

    def request(self, method: str, path: str, data: dict | None = None, raw_body: bytes | None = None) -> tuple[int, str, bytes]:
        credentials = self.credentials()
        if not credentials:
            payload = {
                "error": "Home Assistant authentication is not configured",
                "detail": self.auth_error_detail(),
            }
            return 503, "application/json", json.dumps(payload).encode("utf-8")

        api_base, token, auth_source = credentials
        self._last_auth_source = auth_source
        body = json.dumps(data).encode("utf-8") if data is not None else raw_body
        target_url = f"{api_base}{path}"
        request_log_level = "debug" if method == "GET" else "info"
        log(request_log_level, f"HA {method} {path} via {auth_source}")

        request = Request(
            target_url,
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )

        try:
            with urlopen(request, timeout=10) as response:
                payload = response.read()
                log(request_log_level, f"HA {method} {path} -> {response.status}")
                return response.status, response.headers.get("Content-Type", "application/json"), payload
        except HTTPError as err:
            payload = err.read()
            detail = payload.decode("utf-8", "replace")[:220] if payload else err.reason
            log("warning", f"HA {method} {path} -> {err.code}: {detail}")
            if not payload:
                payload = json.dumps({"error": err.reason}).encode("utf-8")
            return err.code, err.headers.get("Content-Type", "application/json"), payload
        except URLError as err:
            log("warning", f"HA {method} {path} -> 502: {err.reason}")
            return 502, "application/json", json.dumps({"error": str(err.reason)}).encode("utf-8")

    def json_request(self, method: str, path: str, data: dict | None = None) -> dict | list | None:
        status, _content_type, payload = self.request(method, path, data=data)
        if status < 200 or status >= 300:
            message = payload.decode("utf-8", "replace")[:240]
            raise RuntimeError(f"HA {method} {path} failed with {status}: {message}")
        if not payload:
            return None
        return json.loads(payload.decode("utf-8"))

    def service(
        self,
        domain: str,
        service: str,
        entity_id: str | None = None,
        data: dict | None = None,
        return_response: bool = False,
    ) -> dict | list | None:
        payload = dict(data or {})
        if entity_id:
            payload["entity_id"] = entity_id

        path = f"/services/{domain}/{service}"
        if return_response:
            path += "?return_response"

        try:
            return self.json_request("POST", path, payload)
        except RuntimeError:
            if entity_id and domain != "homeassistant" and service in {"turn_on", "turn_off"}:
                return self.json_request("POST", f"/services/homeassistant/{service}", {"entity_id": entity_id})
            raise


class OpenPoolController:
    def __init__(self, ha: HomeAssistantClient) -> None:
        self.ha = ha
        self.lock = threading.RLock()
        self.state = self._load_state()
        self.ha_states: dict[str, dict] = {}
        forecast = self.state.get("weather_forecast")
        self.weather_forecast: list[dict] = forecast if isinstance(forecast, list) else []
        try:
            self.weather_forecast_updated_at = float(self.state.get("weather_forecast_updated_at") or 0)
        except (TypeError, ValueError):
            self.weather_forecast_updated_at = 0.0
        self.weather_forecast_error = str(self.state.get("weather_forecast_error") or "")
        self.connected = False
        self.last_error = ""
        self._stop = threading.Event()
        self.thread = threading.Thread(target=self._run, name="openpool-controller", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def _default_state(self) -> dict:
        current_ts = now_ts()
        return {
            "version": 1,
            "master_enabled": True,
            "pump_mode": "Badebetrieb",
            "pump_mode_started_at": current_ts,
            "heater_mode": "PV-Automatik",
            "weather_mode": "Empfehlung",
            "heater_target_temp": 28,
            "heater_start_mode": DEFAULT_HEATER_START_MODE,
            "pump_running_since": None,
            "pump_runtime_total_s": 0,
            "pump_runtime_today_s": 0,
            "runtime_day": today_key(),
            "heater_off_since": current_ts - RUN_ON_SECONDS - 1,
            "pv_above_since": None,
            "pv_below_since": None,
            "pv_last_available_w": None,
            "pending_job": None,
            "restart_pulses_done": {},
            "continuous_restart_last_at": None,
            "weather_forecast": [],
            "weather_forecast_updated_at": 0,
            "weather_forecast_error": "",
            "command_log": [
                {
                    "time": time.strftime("%H:%M", time.localtime(current_ts)),
                    "date": day_key_for_ts(current_ts),
                    "ts": current_ts,
                    "title": "OpenPool gestartet",
                    "detail": "Controller wartet auf Home Assistant.",
                }
            ],
            "updated_at": current_ts,
        }

    def _load_state(self) -> dict:
        if not STATE_PATH.exists():
            return self._default_state()
        try:
            loaded = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self._default_state()

        state = self._default_state()
        state.update(loaded)
        if not state.get("pump_mode_started_at"):
            state["pump_mode_started_at"] = now_ts()
        if state.get("pump_mode") == "Dauerbetrieb":
            state["continuous_restart_last_at"] = (
                state.get("continuous_restart_last_at")
                or state.get("pump_mode_started_at")
                or now_ts()
            )
        else:
            state["continuous_restart_last_at"] = None
        if state.get("heater_mode") == "Wetterautomatik":
            state["heater_mode"] = "PV-Automatik"
        state["heater_start_mode"] = normalize_heater_start_mode(state.get("heater_start_mode"))
        if state.get("weather_mode") not in WEATHER_MODE_OPTIONS:
            state["weather_mode"] = "Empfehlung"
        state["command_log"] = list(state.get("command_log") or [])[:COMMAND_LOG_LIMIT]
        return state

    def _save_state(self) -> None:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, ensure_ascii=True, indent=2), encoding="utf-8")
        tmp.replace(STATE_PATH)

    def options(self) -> dict:
        return read_options()

    def features(self) -> dict:
        values = {
            "heat_pump_control": True,
            "weather_control": True,
        }
        values.update((self.options().get("features") or {}))
        return {key: bool(values.get(key)) for key in values}

    def heat_pump_enabled(self) -> bool:
        return bool(self.features().get("heat_pump_control", True))

    def weather_control_enabled(self) -> bool:
        return bool(self.features().get("weather_control", True))

    def weather_mode(self) -> str:
        mode = str(self.state.get("weather_mode") or "Empfehlung")
        if not self.weather_control_enabled() or mode not in WEATHER_MODE_OPTIONS:
            return "Empfehlung"
        return mode

    def weather_entity(self) -> str:
        configured = (self.options().get("entities") or {}).get("weather")
        entity_id = str(configured or DEFAULT_WEATHER_ENTITY).strip()
        return entity_id or DEFAULT_WEATHER_ENTITY

    def heater_start_modes(self) -> list[str]:
        selector = self.ha_states.get("heater_operation_mode") or {}
        options = (selector.get("attributes") or {}).get("options")
        if isinstance(options, list):
            modes = [str(option).strip() for option in options if str(option).strip()]
            if modes:
                return modes
        return list(FALLBACK_HEATER_START_MODES)

    def entities(self) -> dict:
        entities = dict(DEFAULT_ENTITIES)
        configured = self.options().get("entities") or {}
        for key in entities:
            if configured.get(key) is not None:
                entities[key] = configured[key]
        if not self.heat_pump_enabled():
            for key in HEATER_ENTITY_KEYS:
                entities.pop(key, None)
        return entities

    def thresholds(self) -> dict:
        values = {
            "pv_start_export_w": 1500,
            "pv_stop_export_w": 1500,
            "pv_start_stable_minutes": 5,
            "pv_stop_stable_minutes": 1,
            "heater_temp_min": 18,
            "heater_temp_max": 32,
            "pump_power_without_chlorinator_w": 450,
            "pump_power_with_chlorinator_w": 500,
        }
        values.update((self.options().get("thresholds") or {}))
        return values

    def poll_interval_seconds(self) -> float:
        try:
            configured = float(self.options().get("poll_interval_s") or DEFAULT_POLL_INTERVAL_SECONDS)
        except (TypeError, ValueError):
            configured = DEFAULT_POLL_INTERVAL_SECONDS
        return max(1.0, min(60.0, configured))

    def profile(self) -> dict:
        values = {
            "pump_start": "07:30",
            "pump_end": "22:00",
            "bad_weather_start": "13:00",
            "bad_weather_end": "16:15",
            "night_swim_duration_hours": 10,
        }
        configured = dict(self.options().get("profiles") or {})
        if "night_swim_duration_hours" not in configured:
            legacy_minutes = configured.get("night_swim_duration_minutes", configured.get("night_swim_max_minutes"))
            if legacy_minutes is not None:
                try:
                    configured["night_swim_duration_hours"] = float(legacy_minutes) / 60
                except (TypeError, ValueError):
                    pass
        values.update(configured)
        try:
            hours = float(values.get("night_swim_duration_hours") or 10)
        except (TypeError, ValueError):
            hours = 10
        hours = max(0.1, hours)
        values["night_swim_duration_hours"] = hours
        values["night_swim_duration_minutes"] = int(round(hours * 60))
        values["night_swim_max_minutes"] = values["night_swim_duration_minutes"]
        return values

    def restart_pulses(self) -> list[dict]:
        configured = self.options().get("restart_pulses") or {}
        defaults = [
            {"key": "pulse_1", "enabled": True, "time": "11:59", "duration_s": 5},
            {"key": "pulse_2", "enabled": True, "time": "16:59", "duration_s": 5},
            {"key": "pulse_3", "enabled": True, "time": "23:59", "duration_s": 5},
            {"key": "pulse_4", "enabled": False, "time": "00:00", "duration_s": 5},
        ]
        for pulse in defaults:
            options = configured.get(pulse["key"]) or {}
            pulse.update({key: options[key] for key in pulse.keys() & options.keys()})
        return defaults

    def weather_recommendation(self) -> dict:
        if not self.weather_control_enabled():
            return {
                "category": "disabled",
                "label": "Deaktiviert",
                "pump_mode": "Badebetrieb",
                "icon": "☀️",
                "reason": "Wettersteuerung ist deaktiviert.",
            }

        day = self.weather_forecast[0] if self.weather_forecast else {}
        condition = str((day or {}).get("condition") or "").lower()
        if condition in BATHING_WEATHER_CONDITIONS:
            return {
                "category": "bathing",
                "label": "Badewetter",
                "pump_mode": "Badebetrieb",
                "icon": "☀️",
                "reason": "Überwiegend sonnig oder wolkenlos.",
            }

        if condition in BAD_WEATHER_CONDITIONS:
            return {
                "category": "bad",
                "label": "Schlechtwetter",
                "pump_mode": "Schlechtwetter",
                "icon": "🌧️",
                "reason": "Stark bewölkt oder Regen erwartet.",
            }

        return {
            "category": "unknown",
            "label": "Wetter offen",
            "pump_mode": "Schlechtwetter",
            "icon": "☁️",
            "reason": "Tagesvorhersage noch nicht bewertet.",
        }

    def _recommended_pump_mode(self) -> str:
        mode = str(self.weather_recommendation().get("pump_mode") or "Schlechtwetter")
        return mode if mode in WEATHER_MANAGED_PUMP_MODES else "Schlechtwetter"

    def _apply_weather_pump_mode(self, force: bool = False) -> None:
        if self.weather_mode() != "Automatik":
            return

        current_mode = str(self.state.get("pump_mode") or "Aus")
        if not force and current_mode not in WEATHER_MANAGED_PUMP_MODES:
            return

        target_mode = self._recommended_pump_mode()
        if current_mode == target_mode:
            return

        self.state["pump_mode"] = target_mode
        self.state["pump_mode_started_at"] = now_ts()
        self.state["continuous_restart_last_at"] = None
        self.command("Wetterautomatik Pumpenprofil", target_mode)

    def snapshot(self) -> dict:
        with self.lock:
            runtime = self._runtime_snapshot(now_ts())
            heater_start_modes = self.heater_start_modes()
            self.state["heater_start_mode"] = normalize_heater_start_mode(
                self.state.get("heater_start_mode"),
                heater_start_modes,
            )
            return {
                "controller": dict(self.state),
                "runtime": runtime,
                "connected": self.connected,
                "last_error": self.last_error,
                "auth_status": self.ha.auth_status(),
                "ha_states": self._ui_ha_states(),
                "weather_forecast": list(self.weather_forecast),
                "weather_forecast_updated_at": self.weather_forecast_updated_at,
                "weather_forecast_error": self.weather_forecast_error,
                "weather_recommendation": self.weather_recommendation(),
                "features": self.features(),
                "options": public_options(self.options()),
                "entities": self.entities(),
                "thresholds": self.thresholds(),
                "profiles": self.profile(),
                "restart_pulses": self.restart_pulses(),
                "continuous_restart_interval_s": CONTINUOUS_RESTART_INTERVAL_SECONDS,
                "heater_start_modes": heater_start_modes,
                "now": now_ts(),
            }

    def _ui_ha_states(self) -> dict:
        entities = self.entities()
        return {ui_key: self.ha_states.get(option_key) for ui_key, option_key in UI_ENTITY_KEYS.items()}

    def _runtime_snapshot(self, current_ts: float) -> dict:
        runtime_today = float(self.state.get("pump_runtime_today_s") or 0)
        runtime_total = float(self.state.get("pump_runtime_total_s") or 0)
        running_since = self.state.get("pump_running_since")
        if running_since:
            delta = max(0, current_ts - float(running_since))
            runtime_today += delta
            runtime_total += delta
        return {
            "pump_running_since": running_since,
            "pump_runtime_today_s": int(runtime_today),
            "pump_runtime_total_s": int(runtime_total),
        }

    def command(self, title: str, detail: str) -> None:
        signature = f"{title}|{detail}"
        log = self.state.setdefault("command_log", [])
        if log and f"{log[0].get('title')}|{log[0].get('detail')}" == signature:
            return
        current_ts = now_ts()
        log.insert(
            0,
            {
                "time": time.strftime("%H:%M", time.localtime(current_ts)),
                "date": day_key_for_ts(current_ts),
                "ts": current_ts,
                "title": title,
                "detail": detail,
            },
        )
        del log[COMMAND_LOG_LIMIT:]

    def handle_action(self, action: dict) -> dict:
        action_type = action.get("type")
        with self.lock:
            if action_type == "master":
                current_ts = now_ts()
                self.state["master_enabled"] = bool(action.get("enabled"))
                if self.state.get("pump_mode") == "Dauerbetrieb":
                    self.state["continuous_restart_last_at"] = current_ts if self.state["master_enabled"] else None
                self.command(
                    "Hauptfreigabe EIN" if self.state["master_enabled"] else "Hauptfreigabe AUS",
                    "Von der OpenPool UI gesetzt.",
                )
                self._save_state()
            elif action_type == "pump_mode":
                mode = str(action.get("mode") or "Aus")
                if mode != self.state.get("pump_mode"):
                    current_ts = now_ts()
                    self.state["pump_mode_started_at"] = current_ts
                    self.state["continuous_restart_last_at"] = current_ts if mode == "Dauerbetrieb" else None
                if self.weather_mode() == "Automatik":
                    self.state["weather_mode"] = "Empfehlung"
                    self.command("Wetterautomatik pausiert", "Pumpenmodus wurde manuell gesetzt.")
                self.state["pump_mode"] = mode
                self.command("Pumpenmodus", self.state["pump_mode"])
                self._save_state()
            elif action_type == "weather_mode":
                mode = str(action.get("mode") or "Empfehlung")
                if mode not in WEATHER_MODE_OPTIONS or not self.weather_control_enabled():
                    mode = "Empfehlung"
                self.state["weather_mode"] = mode
                self.command("Wettersteuerung", mode)
                if mode == "Automatik":
                    self._apply_weather_pump_mode(force=True)
                self._save_state()
            elif action_type == "heater_mode":
                if not self.heat_pump_enabled():
                    return self.snapshot()
                mode = str(action.get("mode") or "Aus")
                if mode == "Wetterautomatik":
                    mode = "PV-Automatik"
                if mode != self.state.get("heater_mode"):
                    self._reset_pv_tracking()
                self.state["heater_mode"] = mode
                self.command("Heizungsmodus", self.state["heater_mode"])
                self._save_state()
            elif action_type == "heater_start_mode":
                if not self.heat_pump_enabled():
                    return self.snapshot()
                mode = normalize_heater_start_mode(action.get("mode"), self.heater_start_modes())
                self.state["heater_start_mode"] = mode
                self.command("WP-Startmodus", mode)
                self._save_state()
                if self._heater_is_active():
                    self._set_heater_operation_mode()
            elif action_type == "target_temp":
                if not self.heat_pump_enabled():
                    return self.snapshot()
                self.state["heater_target_temp"] = float(action.get("value") or self.state.get("heater_target_temp") or 28)
                self.command("Zieltemperatur gesetzt", f"{self.state['heater_target_temp']:.1f} Grad")
                self._save_state()
                self._set_heater_temperature()
            elif action_type == "restart_pulse":
                self._start_restart_pulse(RESTART_PULSE_SECONDS, "Manueller Restart-Pulse")
            else:
                raise ValueError(f"Unknown action type: {action_type}")

        self._apply_control_rules()
        return self.snapshot()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.poll_home_assistant()
                if self.connected:
                    self._apply_jobs()
                    self._apply_control_rules()
            except Exception as err:  # noqa: BLE001 - controller must keep running
                self.last_error = str(err)
                log("error", f"controller error: {err}")
            self._stop.wait(self.poll_interval_seconds())

    def poll_home_assistant(self) -> None:
        entities = self.entities()
        states: dict[str, dict] = {}
        success = 0

        for key, entity_id in entities.items():
            try:
                states[key] = self.ha.json_request("GET", f"/states/{quote(entity_id, safe='')}")  # type: ignore[assignment]
                success += 1
            except Exception as err:  # noqa: BLE001
                self.last_error = str(err)

        self._refresh_weather_forecast_if_needed()

        with self.lock:
            self.connected = success >= 2
            self.ha_states = states
            self._track_runtime(states)
            self.state["updated_at"] = now_ts()
            self._save_state()

    def _store_weather_forecast(self, forecast: list[dict], updated_at: float, error: str = "") -> None:
        self.weather_forecast = forecast
        self.weather_forecast_updated_at = updated_at
        self.weather_forecast_error = error
        self.state["weather_forecast"] = forecast
        self.state["weather_forecast_updated_at"] = updated_at
        self.state["weather_forecast_error"] = error

    def _refresh_weather_forecast_if_needed(self) -> None:
        if not self.weather_control_enabled():
            if self.weather_forecast or self.weather_forecast_error:
                self._store_weather_forecast([], 0, "")
            return

        entity_id = self.weather_entity()
        if not entity_id:
            return

        current_ts = now_ts()
        if self.weather_forecast and current_ts - self.weather_forecast_updated_at < WEATHER_FORECAST_REFRESH_SECONDS:
            return

        try:
            response = self.ha.service(
                "weather",
                "get_forecasts",
                entity_id=entity_id,
                data={"type": "daily"},
                return_response=True,
            )
            service_response = response.get("service_response") if isinstance(response, dict) else None
            if service_response is None and isinstance(response, dict):
                service_response = response
            entity_response = (service_response or {}).get(entity_id) if isinstance(service_response, dict) else None
            if entity_response is None and isinstance(service_response, dict) and service_response:
                entity_response = next(iter(service_response.values()))
            forecast = entity_response.get("forecast") if isinstance(entity_response, dict) else None
            if isinstance(forecast, list):
                self._store_weather_forecast(forecast[:5], current_ts, "")
            else:
                self._store_weather_forecast(self.weather_forecast, current_ts, "Keine Tagesvorhersage erhalten.")
        except Exception as err:  # noqa: BLE001 - forecast is optional UI context
            self._store_weather_forecast(self.weather_forecast, current_ts, str(err))

    def _track_runtime(self, states: dict[str, dict]) -> None:
        current_day = today_key()
        current_ts = now_ts()
        if self.state.get("runtime_day") != current_day:
            self.state["runtime_day"] = current_day
            self.state["pump_runtime_today_s"] = 0
            self.state["restart_pulses_done"] = {}

        pump_on = str((states.get("pump_switch") or {}).get("state", "")).lower() == "on"
        heater_state = str((states.get("heater_climate") or {}).get("state", "")).lower()
        heater_on = (
            heater_state not in {"", "off", "idle", "unavailable", "unknown"}
            or self._heater_power_is_active(states)
        )

        running_since = self.state.get("pump_running_since")
        if pump_on and not running_since:
            self.state["pump_running_since"] = current_ts
        elif not pump_on and running_since:
            elapsed = max(0, current_ts - float(running_since))
            self.state["pump_runtime_today_s"] = int(float(self.state.get("pump_runtime_today_s") or 0) + elapsed)
            self.state["pump_runtime_total_s"] = int(float(self.state.get("pump_runtime_total_s") or 0) + elapsed)
            self.state["pump_running_since"] = None

        if heater_on:
            self.state["heater_off_since"] = None
        elif self.state.get("heater_off_since") is None:
            self.state["heater_off_since"] = current_ts

    def _apply_jobs(self) -> None:
        job = self.state.get("pending_job")
        if not job:
            self._apply_scheduled_pulses()
            return

        current_ts = now_ts()
        if job.get("type") == "restart_pulse_run_on":
            # Migration path for states written by 0.2.9: restart pulses no
            # longer wait for heat-pump run-on because the pulse is only a few
            # seconds long.
            duration_s = int(job.get("duration_s") or RESTART_PULSE_SECONDS)
            title = str(job.get("title") or "Restart-Pulse")
            self.state["pending_job"] = None
            self._start_restart_pulse(duration_s, title)
            return
        if job.get("type") == "restart_pulse_restore":
            if self._pump_is_active():
                self.state["pending_job"] = None
                self._save_state()
                self._apply_control_rules()
                return
            if current_ts < float(job.get("until") or 0):
                return
            self.state["pending_job"] = None
            self.command("Restart-Pulse Restore offen", "Pumpe wurde nicht bestaetigt, Sicherheitslogik wird angewendet.")
            self._save_state()
            self._apply_control_rules()
            return

        if current_ts < float(job.get("until") or 0):
            return

        if job.get("type") == "restart_pulse":
            # Restart pulses are short enough that the heat pump may stay on;
            # wait for Home Assistant to confirm pump flow again before normal rules resume.
            pump_mode = str(self.state.get("pump_mode") or "Aus")
            restore_pump = (
                bool(job.get("restore_pump", True))
                and bool(self.state.get("master_enabled"))
                and self._pump_should_run(pump_mode)
            )
            if restore_pump:
                self._turn_pump(True)
                self.state["pending_job"] = {
                    "type": "restart_pulse_restore",
                    "until": current_ts + PULSE_RESTORE_GRACE_SECONDS,
                }
                self.command("Restart-Pulse fertig", "Pumpe wird wieder eingeschaltet.")
            else:
                self.state["pending_job"] = None
                self.command("Restart-Pulse fertig", "Pumpenprofil wird wieder angewendet.")
                self._apply_control_rules()
            self._save_state()
            return
        elif job.get("type") == "pump_run_on":
            if not self.heat_pump_enabled():
                self._turn_pump(False)
                self.state["pending_job"] = None
                self._save_state()
                return
            if self._heater_needs_run_on():
                job["until"] = self._heater_run_on_until(current_ts)
                self._turn_heater(False)
                self._turn_pump(True)
                self._save_state()
                return
            self._turn_pump(False)
            self.command("Pumpennachlauf fertig", "Pumpe nach Heizungs-Nachlauf ausgeschaltet.")

        self.state["pending_job"] = None
        self._save_state()

    def _apply_scheduled_pulses(self) -> None:
        self._apply_weather_pump_mode()
        pump_mode = str(self.state.get("pump_mode") or "Aus")
        if not self.state.get("master_enabled") or pump_mode == "Aus" or not self._pump_should_run(pump_mode):
            return

        current_ts = now_ts()
        done = self.state.setdefault("restart_pulses_done", {})

        if pump_mode == "Dauerbetrieb":
            self._apply_continuous_restart_pulse(current_ts)
            return

        for pulse in self.restart_pulses():
            scheduled_ts = clock_to_day_ts(pulse.get("time"), current_ts)
            if (
                not pulse.get("enabled")
                or scheduled_ts is None
                or current_ts < scheduled_ts
                or current_ts > scheduled_ts + PULSE_TRIGGER_WINDOW_SECONDS
                or not self._pump_should_run_at(pump_mode, scheduled_ts)
            ):
                continue
            key = f"{day_key_for_ts(scheduled_ts)}:{pulse['key']}"
            if done.get(key):
                continue
            done[key] = True
            self._start_restart_pulse(int(pulse.get("duration_s") or 5), f"Automatischer {pulse['key']}")
            break

    def _continuous_restart_due_ts(self, current_ts: float) -> float:
        baseline = self.state.get("continuous_restart_last_at") or self.state.get("pump_mode_started_at")
        try:
            baseline_ts = float(baseline)
        except (TypeError, ValueError):
            baseline_ts = current_ts
            self.state["continuous_restart_last_at"] = baseline_ts
        return baseline_ts + CONTINUOUS_RESTART_INTERVAL_SECONDS

    def _apply_continuous_restart_pulse(self, current_ts: float) -> None:
        if current_ts < self._continuous_restart_due_ts(current_ts):
            return
        self.state["continuous_restart_last_at"] = current_ts
        self._start_restart_pulse(RESTART_PULSE_SECONDS, "12h-Restart Dauerbetrieb")

    def _apply_control_rules(self) -> None:
        if self.state.get("pending_job"):
            return

        master_enabled = bool(self.state.get("master_enabled"))
        pump_mode = str(self.state.get("pump_mode") or "Aus")
        heater_mode = str(self.state.get("heater_mode") or "Aus")
        heat_pump_enabled = self.heat_pump_enabled()
        if heater_mode == "Wetterautomatik":
            heater_mode = "PV-Automatik"
            self.state["heater_mode"] = heater_mode

        if not master_enabled:
            self._reset_pv_tracking()
            self._turn_heater(False)
            self._turn_pump(False)
            return

        if pump_mode == "Nachtbaden" and self._night_swim_expired():
            self.state["pump_mode"] = "Aus"
            self.state["pump_mode_started_at"] = now_ts()
            pump_mode = "Aus"
            self.command(
                "Nachtbaden beendet",
                "Maximale Laufzeit erreicht, Heizung wird mit Nachlauf ausgeschaltet."
                if heat_pump_enabled
                else "Maximale Laufzeit erreicht, Pumpe wird ausgeschaltet.",
            )

        self._apply_weather_pump_mode()
        pump_mode = str(self.state.get("pump_mode") or "Aus")

        if pump_mode == "Aus":
            self._reset_pv_tracking()
            self._turn_heater(False)
            if heat_pump_enabled and self._heater_needs_run_on():
                self._start_pump_run_on("Pumpennachlauf gestartet", "Heizung war kuerzlich aktiv.")
            else:
                self._turn_pump(False)
            self._save_state()
            return

        pump_should_run = self._pump_should_run(pump_mode)

        if not pump_should_run:
            self._reset_pv_tracking()
            self._turn_heater(False)
            if heat_pump_enabled and self._heater_needs_run_on():
                self._start_pump_run_on("Pumpennachlauf gestartet", "Profilende erreicht, Heizung war kuerzlich aktiv.")
            else:
                self._turn_pump(False)
            self._save_state()
            return

        self._turn_pump(True)

        if not self._pump_is_active():
            self._turn_heater(False)
            self._save_state()
            return

        if heat_pump_enabled and self._pump_stop_run_on_active(pump_mode):
            self._reset_pv_tracking()
            if self._heater_is_active():
                self._turn_heater(False)
                self.command("Heizung vor Pumpenstopp AUS", "Pumpe bleibt fuer den Schutz-Nachlauf aktiv.")
            self._save_state()
            return

        if not heat_pump_enabled:
            self._reset_pv_tracking()
        elif pump_mode == "Nachtbaden":
            self._reset_pv_tracking()
            self._turn_heater(True)
        elif heater_mode == "Aus":
            self._reset_pv_tracking()
            self._turn_heater(False)
        elif heater_mode == "Ein":
            self._reset_pv_tracking()
            self._turn_heater(True)
        elif heater_mode == "PV-Automatik":
            self._apply_pv_heating(pump_should_run)

        self._save_state()

    def _pump_should_run(self, pump_mode: str) -> bool:
        return self._pump_should_run_at(pump_mode, now_ts())

    def _pump_should_run_at(self, pump_mode: str, reference_ts: float) -> bool:
        profile = self.profile()
        current_time = time.strftime("%H:%M", time.localtime(reference_ts))
        if pump_mode in {"Dauerbetrieb", "Nachtbaden"}:
            return True
        if pump_mode == "Badebetrieb":
            return str(profile["pump_start"]) <= current_time < str(profile["pump_end"])
        if pump_mode == "Schlechtwetter":
            return str(profile["bad_weather_start"]) <= current_time < str(profile["bad_weather_end"])
        return False

    def _night_swim_expired(self) -> bool:
        max_minutes = float(self.profile().get("night_swim_duration_minutes") or 600)
        started_at = float(self.state.get("pump_mode_started_at") or now_ts())
        return now_ts() - started_at >= max(1, max_minutes) * 60

    def _heater_needs_run_on(self) -> bool:
        if not self.heat_pump_enabled():
            return False
        return self._heater_is_active() or self._heater_run_on_until() > now_ts()

    def _heater_run_on_until(self, current_ts: float | None = None) -> float:
        current_ts = current_ts or now_ts()
        heater_off_since = self.state.get("heater_off_since")
        if heater_off_since is None or self._heater_is_active():
            return current_ts + RUN_ON_SECONDS
        return max(current_ts, float(heater_off_since) + RUN_ON_SECONDS)

    def _start_pump_run_on(self, title: str, detail: str) -> None:
        self.state["pending_job"] = {"type": "pump_run_on", "until": self._heater_run_on_until()}
        self._turn_pump(True)
        self.command(title, detail)

    def _pump_stop_run_on_active(self, pump_mode: str) -> bool:
        if not self.heat_pump_enabled():
            return False
        current_ts = now_ts()
        planned_stop_ts = self._next_planned_pump_stop_ts(pump_mode, current_ts)
        return planned_stop_ts is not None and current_ts >= planned_stop_ts - RUN_ON_SECONDS

    def _next_planned_pump_stop_ts(self, pump_mode: str, current_ts: float) -> float | None:
        candidates = [
            self._profile_end_ts(pump_mode, current_ts),
        ]
        candidates = [value for value in candidates if value is not None]
        return min(candidates) if candidates else None

    def _profile_end_ts(self, pump_mode: str, current_ts: float) -> float | None:
        profile = self.profile()
        if pump_mode == "Badebetrieb" and self._pump_should_run_at(pump_mode, current_ts):
            return clock_to_day_ts(profile.get("pump_end"), current_ts)
        if pump_mode == "Schlechtwetter" and self._pump_should_run_at(pump_mode, current_ts):
            return clock_to_day_ts(profile.get("bad_weather_end"), current_ts)
        if pump_mode == "Nachtbaden":
            max_minutes = float(profile.get("night_swim_duration_minutes") or 600)
            started_at = float(self.state.get("pump_mode_started_at") or current_ts)
            end_ts = started_at + max(1, max_minutes) * 60
            return end_ts if end_ts > current_ts else None
        return None

    def _apply_pv_heating(self, pump_should_run: bool) -> None:
        if not self.heat_pump_enabled():
            self._reset_pv_tracking()
            return
        if not pump_should_run:
            self._reset_pv_tracking()
            self._turn_heater(False)
            return
        available = self._pv_available_watts()
        if available is None:
            self._reset_pv_tracking()
            self._turn_heater(False)
            return

        current_ts = now_ts()
        config = self._pv_release_settings()
        self.state["pv_last_available_w"] = round(available, 1)

        if self._heater_is_active():
            self.state["pv_above_since"] = None
            if available < config["stop_w"]:
                if not self.state.get("pv_below_since"):
                    self.state["pv_below_since"] = current_ts
                if current_ts - float(self.state["pv_below_since"]) >= config["stop_stable_s"]:
                    self._turn_heater(False)
                    self.state["pv_below_since"] = None
                    self.state["pv_above_since"] = None
            else:
                self.state["pv_below_since"] = None
            return

        self.state["pv_below_since"] = None
        if available >= config["start_w"]:
            if not self.state.get("pv_above_since"):
                self.state["pv_above_since"] = current_ts
            if current_ts - float(self.state["pv_above_since"]) >= config["start_stable_s"]:
                self._turn_heater(True)
                self.state["pv_above_since"] = None
            return

        self.state["pv_above_since"] = None
        self._turn_heater(False)

    def _pv_release_settings(self) -> dict[str, float]:
        thresholds = self.thresholds()
        start_w = self._threshold_float(thresholds, "pv_start_export_w", 1500)
        stop_w = self._threshold_float(thresholds, "pv_stop_export_w", start_w)
        start_stable_s = max(0.0, self._threshold_float(thresholds, "pv_start_stable_minutes", 5) * 60)
        stop_stable_s = max(0.0, self._threshold_float(thresholds, "pv_stop_stable_minutes", 1) * 60)

        # Keep the stop threshold at or below the start threshold so a configured
        # hysteresis cannot make the heat pump flap at one boundary.
        return {
            "start_w": max(0.0, start_w),
            "stop_w": max(0.0, min(stop_w, start_w)),
            "start_stable_s": start_stable_s,
            "stop_stable_s": stop_stable_s,
        }

    def _threshold_float(self, thresholds: dict, key: str, fallback: float) -> float:
        try:
            value = thresholds.get(key)
            return float(value if value is not None else fallback)
        except (TypeError, ValueError):
            return fallback

    def _reset_pv_tracking(self) -> None:
        self.state["pv_above_since"] = None
        self.state["pv_below_since"] = None
        self.state["pv_last_available_w"] = None

    def _pv_available_watts(self) -> float | None:
        pv_generation = self._entity_power_watts("pv_generation")
        house_consumption = self._calculated_house_consumption_watts()
        if pv_generation is None or house_consumption is None:
            return None

        # House consumption includes PV self-consumption and any grid import.
        # Subtracting it from PV production yields the current export/import
        # balance that can be used for the heat pump.
        available = pv_generation - house_consumption
        if self._heater_is_active():
            available += abs(self._entity_power_watts("heater_power") or 0)
        return available

    def _calculated_house_consumption_watts(self) -> float | None:
        pv_generation = self._entity_power_watts("pv_generation")
        pv_export = self._entity_power_watts("pv_export")
        grid_import = self._entity_power_watts("grid_import")
        if pv_generation is None or pv_export is None or grid_import is None:
            return None
        return pv_generation - pv_export + grid_import

    def _state_power_watts(self, state: dict | None) -> float | None:
        if not state:
            return None
        try:
            value = float(str(state.get("state")).replace(",", "."))
        except (TypeError, ValueError):
            return None
        unit = str((state.get("attributes") or {}).get("unit_of_measurement") or "").lower()
        return value * 1000 if "kw" in unit else value

    def _entity_power_watts(self, key: str) -> float | None:
        return self._state_power_watts(self.ha_states.get(key))

    def _heater_power_is_active(self, states: dict[str, dict] | None = None) -> bool:
        source = states if states is not None else self.ha_states
        power = self._state_power_watts((source or {}).get("heater_power"))
        return power is not None and abs(power) >= HEATER_ACTIVE_POWER_W

    def _heater_is_active(self) -> bool:
        if not self.heat_pump_enabled():
            return False
        heater_state = str((self.ha_states.get("heater_climate") or {}).get("state", "")).lower()
        return (
            heater_state not in {"", "off", "idle", "unavailable", "unknown"}
            or self._heater_power_is_active()
        )

    def _pump_is_active(self) -> bool:
        return str((self.ha_states.get("pump_switch") or {}).get("state", "")).lower() == "on"

    def _turn_pump(self, enabled: bool) -> None:
        entity_id = self.entities().get("pump_switch")
        if not entity_id:
            return
        current_state = str((self.ha_states.get("pump_switch") or {}).get("state", "")).lower()
        if current_state in {"on", "off"} and (current_state == "on") == enabled:
            return
        service = "turn_on" if enabled else "turn_off"
        self.ha.service(entity_domain(entity_id), service, entity_id=entity_id)
        self.command("Pumpe EIN" if enabled else "Pumpe AUS", "Schaltbefehl an Home Assistant gesendet.")

    def _turn_heater(self, enabled: bool) -> None:
        if not self.heat_pump_enabled():
            return
        entity_id = self.entities().get("heater_climate")
        if not entity_id:
            return
        domain = entity_domain(entity_id)
        current_state = str((self.ha_states.get("heater_climate") or {}).get("state", "")).lower()
        if current_state not in {"", "unknown", "unavailable"}:
            heater_on = current_state not in {"off", "idle"} or self._heater_power_is_active()
            if heater_on == enabled:
                return
        if domain == "climate":
            if enabled:
                try:
                    self.ha.service("climate", "set_hvac_mode", entity_id=entity_id, data={"hvac_mode": "heat"})
                except RuntimeError:
                    self.ha.service("climate", "turn_on", entity_id=entity_id)
                try:
                    self._set_heater_temperature()
                except RuntimeError:
                    pass
                try:
                    self._set_heater_operation_mode()
                except RuntimeError as err:
                    log("warning", f"could not set heat pump operation mode: {err}")
            else:
                self.ha.service("climate", "turn_off", entity_id=entity_id)
        else:
            self.ha.service(domain, "turn_on" if enabled else "turn_off", entity_id=entity_id)
            if enabled:
                try:
                    self._set_heater_operation_mode()
                except RuntimeError as err:
                    log("warning", f"could not set heat pump operation mode: {err}")
        self.command("Heizung EIN" if enabled else "Heizung AUS", "Schaltbefehl an Home Assistant gesendet.")

    def _set_heater_temperature(self) -> None:
        if not self.heat_pump_enabled():
            return
        entity_id = self.entities().get("heater_climate")
        if entity_id and entity_domain(entity_id) == "climate":
            self.ha.service("climate", "set_temperature", entity_id=entity_id, data={"temperature": self.state["heater_target_temp"]})

    def _set_heater_operation_mode(self) -> None:
        if not self.heat_pump_enabled():
            return
        entity_id = self.entities().get("heater_operation_mode")
        if not entity_id:
            return
        self.ha.service(
            "select",
            "select_option",
            entity_id=entity_id,
            data={"option": normalize_heater_start_mode(self.state.get("heater_start_mode"), self.heater_start_modes())},
        )

    def _start_restart_pulse(self, duration_s: int, title: str) -> None:
        current_ts = now_ts()
        pump_mode = str(self.state.get("pump_mode") or "Aus")
        restore_pump = bool(self.state.get("master_enabled")) and self._pump_should_run(pump_mode)
        self._turn_pump(False)
        self.state["pending_job"] = {
            "type": "restart_pulse",
            "until": current_ts + max(1, duration_s),
            "restore_pump": restore_pump,
        }
        if self.state.get("pump_mode") == "Dauerbetrieb":
            self.state["continuous_restart_last_at"] = current_ts
        self.command(title, f"Pumpe fuer {duration_s} Sekunden ausgeschaltet.")
        self._save_state()


HA = HomeAssistantClient()
CONTROLLER = OpenPoolController(HA)


class QuietThreadingHTTPServer(ThreadingHTTPServer):
    """Threading HTTP server that keeps expected Ingress disconnects quiet."""

    def handle_error(self, request: object, client_address: tuple[str, int]) -> None:
        _exc_type, exc, _traceback = sys.exc_info()
        if isinstance(exc, (BrokenPipeError, ConnectionResetError, TimeoutError)):
            log("debug", f"{client_address[0]} disconnected before the request completed")
            return
        super().handle_error(request, client_address)


class OpenPoolHandler(BaseHTTPRequestHandler):
    server_version = "OpenPool/1.1.7"
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/healthz":
            self._send_json({"ok": True})
            return

        if parsed.path == "/api/config":
            self._send_json(public_options(read_options()))
            return

        if parsed.path == "/api/openpool/state":
            self._send_json(CONTROLLER.snapshot())
            return

        if parsed.path == "/api/openpool/events":
            self._send_event_stream()
            return

        if parsed.path.startswith("/api/ha/states/"):
            entity_id = unquote(parsed.path.removeprefix("/api/ha/states/"))
            self._proxy_ha("GET", f"/states/{quote(entity_id, safe='')}")
            return

        self._serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/api/openpool/action":
            try:
                action = json.loads(self._read_body().decode("utf-8") or "{}")
                self._send_json(CONTROLLER.handle_action(action))
            except (ValueError, json.JSONDecodeError) as err:
                self._send_json({"error": str(err)}, status=400)
            except Exception as err:  # noqa: BLE001
                self._send_json({"error": str(err)}, status=502)
            return

        if parsed.path.startswith("/api/ha/services/"):
            service_path = parsed.path.removeprefix("/api/ha/services/")
            self._proxy_ha("POST", f"/services/{service_path}", raw_body=self._read_body())
            return

        self._send_json({"error": "Not found"}, status=404)

    def _read_body(self) -> bytes:
        if self.headers.get("Transfer-Encoding", "").lower() == "chunked":
            return self._read_chunked_body()

        length = int(self.headers.get("content-length", "0"))
        return self.rfile.read(length) if length else b"{}"

    def _read_chunked_body(self) -> bytes:
        chunks: list[bytes] = []
        while True:
            line = self.rfile.readline().strip()
            if not line:
                break
            size = int(line.split(b";", 1)[0], 16)
            if size == 0:
                self.rfile.readline()
                break
            chunks.append(self.rfile.read(size))
            self.rfile.read(2)
        return b"".join(chunks) or b"{}"

    def _proxy_ha(self, method: str, path: str, raw_body: bytes | None = None) -> None:
        status, content_type, payload = HA.request(method, path, raw_body=raw_body)
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self._send_no_cache_headers()
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _serve_static(self, request_path: str) -> None:
        relative = request_path.lstrip("/") or "index.html"
        target = (WWW_ROOT / relative).resolve()

        if not str(target).startswith(str(WWW_ROOT)) or not target.exists() or target.is_dir():
            target = WWW_ROOT / "index.html"

        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        payload = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self._send_no_cache_headers()
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_json(self, data: dict, status: int = 200) -> None:
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self._send_no_cache_headers()
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_event_stream(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self._send_no_cache_headers()
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        while True:
            payload = json.dumps(CONTROLLER.snapshot(), ensure_ascii=True)
            try:
                self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                return
            time.sleep(CONTROLLER.poll_interval_seconds())

    def _send_no_cache_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")

    def log_message(self, fmt: str, *args: object) -> None:
        log("debug", f"{self.address_string()} - {fmt % args}")


def main() -> None:
    CONTROLLER.start()
    server = QuietThreadingHTTPServer(("0.0.0.0", PORT), OpenPoolHandler)
    log("info", f"listening on 0.0.0.0:{PORT}")
    log("info", f"Home Assistant auth: {HA.auth_status()}")
    server.serve_forever()


if __name__ == "__main__":
    main()
