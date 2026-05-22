#!/usr/bin/with-contenv bashio
set -e

export HA_URL="$(bashio::config 'ha_url')"

CONFIG_TOKEN=""
if bashio::config.has_value 'ha_token'; then
  CONFIG_TOKEN="$(bashio::config 'ha_token')"
fi

if [ -n "$CONFIG_TOKEN" ]; then
  export HA_TOKEN="$CONFIG_TOKEN"
else
  export HA_TOKEN="${SUPERVISOR_TOKEN:-}"
fi

export ENTITY_POWER="$(bashio::config 'entity_power')"
export POWER_SIGN="$(bashio::config 'power_sign')"
export POWER_MULTIPLIER="$(bashio::config 'power_multiplier')"
export POWER_OFFSET="$(bashio::config 'power_offset')"

export CACHE_TTL_SECONDS="$(bashio::config 'cache_ttl_seconds')"
export STALE_AFTER_SECONDS="$(bashio::config 'stale_after_seconds')"
export ROUND_DIGITS="$(bashio::config 'round_digits')"
export REQUEST_TIMEOUT_SECONDS="$(bashio::config 'request_timeout_seconds')"
export LOG_LEVEL="$(bashio::config 'log_level')"

bashio::log.info "Starting EcoTracker Meter Bridge on port 80"
exec gunicorn --bind 0.0.0.0:80 --workers 1 --threads 4 --timeout 15 app:app
