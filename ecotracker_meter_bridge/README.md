# EcoTracker Meter Bridge

Dieses Add-on stellt einen Home-Assistant-Leistungssensor als EcoTracker-kompatiblen HTTP-Endpunkt bereit.

Es ist dafür gedacht, den SunEnergy XT 500 Pro lokal mit vorhandenen Messdaten aus Home Assistant zu betreiben, ohne ein zusätzliches Energiemessgerät verbauen zu müssen.

## Endpoint

```text
http://<HA-IP>:<PORT>/v1/json
```

Antwort:

```json
{
  "power": 1234.0,
  "valid": true,
  "stale": false,
  "timestamp": 1779391044
}
```

SunEnergy XT liest über `dat_str.pwr` nur das Feld `power`. Die zusätzlichen Felder sind für Diagnose und Monitoring gedacht.

## Konfiguration

```yaml
ha_url: "http://supervisor/core"

entity_power: "sensor.solaredge_modbuszahler_ac_power"
power_sign: "-1"
power_multiplier: 1.0
power_offset: 0.0

cache_ttl_seconds: 1.0
stale_after_seconds: 15
round_digits: 2
request_timeout_seconds: 3.0
log_level: info
```

Bei Home Assistant OS/Supervised bleibt `ha_url` auf `http://supervisor/core`. Das Add-on verwendet dann automatisch den Supervisor-Token. `ha_token` ist nur für externe Home-Assistant-URLs nötig und kann in der Add-on-Konfiguration optional eingeblendet werden.

### Vorzeichen

Beispiel SolarEdge-Zähler:

```text
SolarEdge -1108 W = Netzbezug
```

Für SunEnergy XT/EcoTracker soll Netzbezug positiv sein. Deshalb:

```yaml
power_sign: -1
```

Wenn dein Sensor bereits positiv bei Netzbezug ist:

```yaml
power_sign: 1
```

### Umrechnung

`power_multiplier` rechnet den Sensorwert in Watt um. Wenn dein Sensor bereits Watt liefert, bleibt der Wert bei `1.0`. Wenn dein Sensor kW liefert, setze `power_multiplier` auf `1000`.

Die Formel lautet:

```text
power = raw_sensor_value * power_multiplier * power_sign + power_offset
```

## SunEnergy XT MD

Beispiel:

```json
{"mode":"direct","direct":{"dat_url":"http://172.16.20.254/v1/json"},"dat_str":{"pwr":"power"}}
```

Wenn du im Add-on einen anderen Host-Port als `80` einstellst, muss die URL den Port enthalten, z. B. `http://172.16.20.254:8080/v1/json`.

## Test

```bash
curl http://<HA-IP>/v1/json
curl http://<HA-IP>/health
```

Der Health-Endpunkt zeigt den gelesenen Rohwert aus Home Assistant, den transformierten EcoTracker-Wert, den Cache-Status und eventuelle Fehler.
