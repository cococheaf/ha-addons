# OpenPool

[Deutsche Version](README.md)

OpenPool is a Home Assistant add-on for compact pool control. It controls the
pump, chlorinator, heat pump, weather profiles and PV surplus heating from a
tablet-friendly interface.

OpenPool is currently designed for setups based on the Intex 26680 sand filter
and saltwater chlorinator system.

![OpenPool Tablet Dashboard](https://raw.githubusercontent.com/cococheaf/ha-openpool/main/docs/screenshots/openpool-tablet.png)

## In Short

- Pump profiles: off, continuous operation, swim mode, bad weather mode, night
  swimming.
- Restart pulses for the chlorinator.
- Chlorinator status from pump power.
- Heat pump with target temperature, start operating mode from a Home Assistant
  selector, run-on and optional PV automation.
- Weather control as recommendation or automation.
- Live sync between multiple open interfaces.
- Persistent state in `/data/openpool_state.json`.

## Before First Start

Adapt the entities in the add-on configuration to your Home Assistant
installation. The bundled entity IDs are only examples.

Most important:

- `entities.pump_switch`
- `entities.heater_climate`
- `entities.heater_operation_mode` for the optional Home Assistant heat pump
  selector
- `entities.weather`
- `entities.pv_generation`
- `entities.pv_export`
- `entities.grid_import`
- Pump and heat pump sensors

Wrong entities can make OpenPool take bad decisions or send commands to the
wrong device.

## Installation

1. Install the add-on.
2. Check the add-on configuration and adapt the entities.
3. Start the add-on.
4. Enable **Show in sidebar**.

## Home Assistant Logbook Note

By default, OpenPool uses the `SUPERVISOR_TOKEN`. If the logbook should show
actions as triggered by `OpenPool`, create a Home Assistant user named
`OpenPool`, create a long-lived access token for that user and set:

```yaml
connection:
  auth_mode: openpool_user_token
  access_token: "TOKEN_OF_THE_OPENPOOL_USER"
```

More technical details are in [DOCS.md](DOCS.md).
