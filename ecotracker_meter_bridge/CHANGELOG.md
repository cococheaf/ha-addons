# Changelog

## 1.0.0

- First stable release after successful Home Assistant and SunEnergy XT 500 Pro endpoint testing.
- Adds the project icon for the Home Assistant add-on store.
- Marks the add-on as stable.
- Polishes README and add-on documentation for public installation and diagnostics.

## 0.1.4

- Fixes Home Assistant Supervisor option validation by avoiding `str(min,)` schema syntax for `ha_url`.
- Quotes complex schema expressions in the add-on metadata for safer YAML parsing.
- Adds a regression test for add-on schema compatibility.

## 0.1.3

- Removes internal versioning guidance from the public README.

## 0.1.2

- Clarifies Home Assistant installation steps with the public add-on repository URL.

## 0.1.1

- Documents the project background and SunEnergy XT 500 Pro local-control use case.

## 0.1.0

- Initial beta version for testing before the final `1.0.0` release.
- Uses the Home Assistant Supervisor API token by default.
- Reads one Home Assistant power sensor.
- Supports sign inversion, multiplier, offset, request timeout, rounding, cache TTL, stale timeout, and log level.
- Runs the HTTP endpoint via Gunicorn.
- Includes `/health` endpoint.
- Adds Home Assistant add-on configuration translations.
- Adds local unit tests and repository hygiene files.
- Uses `ha-ecotracker-emulator` as the public repository/project name.
