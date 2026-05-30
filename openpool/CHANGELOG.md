# Changelog

## 1.1.11

- Preserve the selected heat-pump start mode across add-on restarts even before
  Home Assistant has reported the selector options.
- Re-apply the stored heat-pump operating mode after an add-on restart when the
  heat pump is already running.
- Shorten OpenPool README files and clean up add-on documentation wording.

## 1.1.10

- Switch OpenPool add-on backups from hot to cold mode so Home Assistant
  Supervisor stops the add-on briefly while backing up the frequently updated
  runtime state file.
- Exclude transient `*.tmp` state-write files from add-on backups.

## 1.1.9

- Remove the hard 3-second restart-pulse limit again. The add-on option
  `restart_pulses.pulse_duration_s` now defines the actual pump-off duration.
- Keep `3` seconds as the default and validate only that pulse duration is at
  least 1 second.

## 1.1.8

- Add one central add-on option `restart_pulses.pulse_duration_s` (`Pulse-Dauer`)
  for manual, scheduled and 12-hour restart pulses.
- Reduce the default pulse duration to 3 seconds and clamp every restart pulse
  to a maximum pump-off time of 3 seconds.
- Keep legacy per-pulse `duration_s` values as migration fallback, but clamp
  them to the same safety limit.
- Keep legacy per-pulse duration options schema-compatible during upgrades.

## 1.1.7

- Keep heat-pump control untouched during short restart pulses and add a short
  pump-restore confirmation window after each pulse.
- Avoid the false `Heizung AUS` command-log entry that could happen while Home
  Assistant had not yet reported the pump as on again after a pulse.

## 1.1.6

- Read the available heat-pump start operating modes from the configured Home
  Assistant `select` entity instead of relying on a fixed UI list.
- Keep the previous Heat/Cool/Auto/Boost Heat/Silent Heat values as a fallback
  while Home Assistant has not yet provided selector options.
- Add translated add-on option labels and documentation for the heat-pump
  operating mode selector.

## 1.1.5

- Add `entities.heater_operation_mode` for a Home Assistant `select` entity that
  controls the heat pump operating mode.
- Add a persisted heat-pump start mode selector to the heating controls with
  `Auto` as default and options for Heat, Cool, Auto, Boost Heat and Silent Heat.
- Apply the selected operating mode when OpenPool starts the heat pump.

## 1.1.4

- Change Dauerbetrieb restart handling from fixed daily restart pulses to a
  dedicated 12-hour runtime restart.
- Show the next Dauerbetrieb restart as `12h-Restart` in the activity card
  instead of showing the configured `Pulse 1` schedule.

## 1.1.3

- Add a large-desktop layout profile that uses more available screen width and
  scales dashboard spacing, cards, buttons and sensor typography on wide desktop
  screens only.

## 1.1.2

- Remove the internal sensor-card scroll area and let the dashboard grid size the
  task history and sensor cards together.
- Enlarge the task history card and its text so the tablet layout has enough
  natural height for the full sensor list.

## 1.1.1

- Fix the iPad/tablet sensor card layout so the pump, heater and energy sensor
  groups no longer overlap when the sensor card is locked to the activity card
  height.

## 1.1.0

- Mark the current UI and automation state as the first golden-image release.
- Refresh repository screenshots for desktop, tablet and iPhone layouts.
- Shorten the GitHub and Home Assistant README files and move detailed
  technical information into the add-on documentation.
- Remove local Python cache artifacts from the workspace.
- Bump add-on and server metadata to `1.1.0`.

## 1.0.10

- Center the three heater mode buttons as a fixed button group instead of using
  auto-filled grid columns.

## 1.0.9

- Center the heater mode buttons inside the card body below the heading.

## 1.0.8

- Re-center the heater mode button row on desktop and iPad-width layouts.

## 1.0.7

- Keep the sensor card locked to the same height as the activity card on
  desktop and tablet-wide layouts, with internal sensor scrolling when needed.

## 1.0.6

- Add standard `line-clamp` CSS declarations next to the WebKit fallback.
- Refine the master enable switch size and align its status text with the
  neighboring dashboard status tiles.
- Keep dashboard history and sensor cards content-sized on desktop and make the
  sensor section more compact on wide screens.
- Disable tile hover tooltips on iPhone, iPad and other touch-sized layouts.
- Suppress expected Home Assistant Ingress client-disconnect tracebacks in the
  add-on log.
- Refresh the GitHub README dashboard screenshot.

## 1.0.5

- Change master toggle design to fit text alignment

## 1.0.4

- Remove the master tile pseudo-element conflict with hover tooltips.
- Make the master toggle itself smaller while keeping the master tile style.

## 1.0.3

- Vertically center the heater mode buttons inside the Heizungsmodus control
  card.

## 1.0.2

- Move the master enable switch to the first dashboard status tile and give it
  a stronger but still integrated master-switch style.
- Increase task-history typography on desktop and iPad while keeping the mobile
  layout compact.

## 1.0.1

- Add the visible add-on option `profiles.night_swim_duration_hours` for
  configuring the Nachtbaden duration in hours.
- Keep backward compatibility with existing
  `profiles.night_swim_duration_minutes` and `profiles.night_swim_max_minutes`
  settings.
- Bump the add-on and server version to `1.0.1`.

## 1.0.0

- Mark OpenPool as stable by removing the Home Assistant add-on experimental
  stage flag.
- Remove the old dashboard pool-state tile and center the master enable switch
  as a normal status tile.
- Keep the heat-pump tooltip consistent when the climate entity reports `off`
  but the heat-pump power sensor shows active load.
- Limit task history to six previous entries and remove the history scrollbar.
- Rename the Nachtbaden profile option to
  `profiles.night_swim_duration_minutes`, with a fallback for existing
  `profiles.night_swim_max_minutes` installations.
- Reorder the sensor section with pump and heat pump side by side and energy
  values underneath.
- Polish add-on option labels and descriptions in German and English for the
  first stable release.

## 0.5.0

- Reworked the dashboard into the final pre-stable card layout for Allgemein,
  Steuerelemente, Aufgabenverlauf and Sensoren.
- Normalized control button and tile sizing across desktop, iPad and mobile
  layouts.
- Moved explanatory tile text into hover/focus tooltips for a cleaner tablet
  interface.
- Split pump, weather, heater mode and heater temperature into consistent
  control subcards and fixed heat-pump running detection from the power sensor.

## 0.4.0

- Added provider-neutral daily weather forecast handling and weather-based
  pump profile recommendations.
- Added optional heat pump and weather feature switches in the add-on
  configuration.
- Added chlorinator detection thresholds from pump power and heat-energy source
  calculation from live power values.
- Added logbook attribution options and configurable OpenPool log levels.

## 0.3.0

- Added autonomous pump profiles, scheduled restart pulses, Nachtbaden expiry
  and heat-pump run-on protection.
- Added PV surplus calculation from PV production, grid export and grid import
  with configurable start/stop thresholds and stability timers.
- Added upcoming task display, heat-pump start countdowns and safer restart
  pulse behavior.
- Documented the Intex 26680 focus and expanded the project README in German
  and English.

## 0.2.0

- Moved OpenPool runtime state and automation jobs into the add-on server.
- Persisted controller state, pump runtimes, pending jobs and command history
  under `/data`.
- Added shared state/action endpoints, server-sent live updates and no-cache UI
  delivery so multiple browser sessions stay synchronized.
- Removed the web settings page and moved configuration fully into Home
  Assistant add-on options.

## 0.1.0

- Initial Home Assistant add-on packaging for Ingress with the first OpenPool
  web UI.
- Added Home Assistant API proxying, configurable entity wiring and service
  calls for pump, heat pump, restart pulse and target temperature actions.
- Added token fallback handling and a categorized live sensor dashboard.
