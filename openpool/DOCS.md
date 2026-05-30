# OpenPool Add-on Documentation

![OpenPool Desktop Dashboard](../docs/screenshots/openpool-desktop.png)

## Home Assistant API

The add-on is configured with `homeassistant_api: true`. At runtime, Home
Assistant provides `SUPERVISOR_TOKEN`, which the OpenPool server uses to proxy
selected API calls:

- `GET /api/ha/states/<entity_id>`
- `POST /api/ha/services/<domain>/<service>`

The browser UI should call the local add-on endpoints instead of storing a
long-lived access token in the frontend.

Daily weather forecasts are read server-side with
`weather.get_forecasts?return_response` for the configured `entities.weather`
entity. The forecast is cached for 12 hours and persisted in the OpenPool state
file. Normal one-second sensor polling does not read the weather entity.

If the Supervisor token is not available in the add-on container, OpenPool can
fall back to the configured `connection.homeassistant_url` and
`connection.access_token` add-on options.

`connection.auth_mode` controls which token source is preferred:

- `supervisor`: use `SUPERVISOR_TOKEN` first and only fall back to
  `connection.access_token` if the Supervisor token is unavailable.
- `openpool_user_token`: always use `connection.access_token`. Use this with a
  dedicated Home Assistant user named `OpenPool` when logbook entries should be
  attributed to OpenPool instead of Supervisor.

## Controller State

OpenPool keeps its runtime state in the add-on server, not in the browser. The
state is persisted in `/data/openpool_state.json` and contains the active modes,
pump runtime counters, pending jobs and command history.

The frontend listens to `GET /api/openpool/events` for live state updates, uses
`GET /api/openpool/state` as a fallback and sends user actions to
`POST /api/openpool/action`. This keeps multiple browser sessions in sync and
allows automation jobs to continue when the UI is closed.

## Backups

OpenPool uses `backup: cold` in its add-on metadata. Home Assistant Supervisor
therefore stops OpenPool briefly while creating an add-on backup, then starts it
again afterwards. This avoids hot-backup races with `/data/openpool_state.json`,
which is updated frequently while the controller is running. Transient
`*.tmp` files from atomic state writes are excluded from backups.

## Heat Pump Run-on

Any planned pump stop is protected by the heat pump run-on rule. Before a pump
profile ends and before Nachtbaden reaches its maximum duration, OpenPool
switches the heat pump off five minutes early and keeps the pump running for
flow. If a manual pump-off action happens while the heat pump is running or has
stopped less than five minutes ago, the pump remains on until the remaining
run-on time has completed. Restart pulses are intentionally exempt from this
rule because they only stop the pump for a few seconds.

## Heat Pump Release

OpenPool derives the current house consumption from PV production, grid export
and grid import: `pv_generation - pv_export + grid_import`. The heat-pump
release value is then calculated as `pv_generation - house_consumption`, which
is equivalent to the current grid export minus grid import balance. When the
heat pump is already running, its current power sensor is added back to estimate
the surplus that would exist without the heat pump load.
OpenPool only enables the heat pump after the pump switch is confirmed on by
Home Assistant, so the pump load is already represented at the grid meter.
The add-on options control the heat-pump release with a start threshold, stop
threshold and separate stability times. `pv_start_export_w` is the legacy option
name for the calculated available PV power needed to start the heat pump. The
heat pump starts only after that value has been reached continuously for
`pv_start_stable_minutes`. While the heat pump is running, OpenPool waits until
the available PV power stays below `pv_stop_export_w` for
`pv_stop_stable_minutes` before switching it off.

## Heat Pump Start Mode

If `entities.heater_operation_mode` points to a Home Assistant `select` entity,
OpenPool reads the available start modes directly from that entity's
`attributes.options`. The UI dropdown therefore follows the actual modes
provided by the heat pump integration. The selected value is persisted in
`/data/openpool_state.json` and is preserved during add-on restarts even before
Home Assistant has reported selector options again. If the heat pump is already
running after an add-on restart, OpenPool re-applies the stored selector value
when the control loop resumes.

## Pump Profiles

Profile times are configured in the add-on `profiles` section. Nachtbaden uses
`profiles.night_swim_duration_hours` as its maximum runtime. Older
installations that still have `profiles.night_swim_duration_minutes` or
`profiles.night_swim_max_minutes` are migrated as a fallback. The dashboard
labels, the upcoming task and the automatic Nachtbaden shutdown all use this
same add-on option.

Restart pulses use one shared duration from
`restart_pulses.pulse_duration_s` (`Pulse-Dauer`). This value defines how many
seconds the pump stays off between pulse start and pulse stop. It is used for
manual, scheduled and 12-hour restart pulses. Older per-pulse `duration_s`
values are accepted as a migration fallback when the central option is missing.

## Weather Recommendation

OpenPool uses the configured Home Assistant weather entity, for example
`weather.home`, `weather.openweathermap` or another provider-specific weather
entity, and asks Home Assistant for the daily forecast at most twice per day.
The recommendation is intentionally coarse:

- `Badewetter`: `sunny`, `clear-night` or `partlycloudy`.
- `Schlechtwetter`: strongly cloudy, rain, storms, fog, snow or exceptional
  weather states.

The dashboard shows the resulting daily class and the recommended pump profile.
The weather card has a persistent `Empfehlung`/`Automatik` switch:

- `Empfehlung`: OpenPool only displays the recommended pump profile.
- `Automatik`: OpenPool sets the pump profile to `Badebetrieb` or
  `Schlechtwetter` according to the cached daily recommendation.

Manual pump-mode changes pause weather automation and switch it back to
`Empfehlung`. Heat-pump control is intentionally independent from weather and is
handled by manual heat mode or PV automation.

## Feature Switches

`features.heat_pump_control` disables heat-pump polling, heat-pump service
calls, heat-pump UI cards, heat-pump run-on handling and PV heating logic when
set to `false`.

`features.weather_control` disables weather forecast polling, the weather
forecast card and the weather-dependent pump automation switch when set to
`false`.
The weather provider itself is selected only through `entities.weather`.

## Configuration

The add-on options contain the Home Assistant entity IDs, profile times, restart
pulses and control thresholds. The OpenPool UI is intentionally control-only;
permanent configuration changes are made in the Home Assistant add-on options.
Before the first live run, all entity IDs in the add-on configuration must be
adapted to the local Home Assistant installation. The defaults are examples from
the original OpenPool setup; wrong entities can prevent control actions or send
them to the wrong device.

The dashboard derives the chlorinator status from the configured pump power
sensor. `pump_power_without_chlorinator_w` is the expected pump-only reference
load, while `pump_power_with_chlorinator_w` is the threshold from which the
chlorinator tile shows `EIN`.

## Files

- `/app/www`: bundled frontend
- `/data/options.json`: Home Assistant add-on options
- `/config`: writable add-on configuration directory
