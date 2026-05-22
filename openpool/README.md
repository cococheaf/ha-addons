# OpenPool

[English version](README.en.md)

OpenPool ist ein Home Assistant Add-on fuer eine kompakte Poolsteuerung. Es
steuert Pumpe, Chlorsystem, Waermepumpe, Wetterprofile und PV-Ueberschussheizung
ueber eine tabletfreundliche Oberflaeche.

Aktuell ist OpenPool fuer Setups rund um das Intex 26680
Sandfilter-/Salzwasserelektrolyse-System ausgelegt.

![OpenPool Tablet Dashboard](https://raw.githubusercontent.com/cococheaf/ha-openpool/main/docs/screenshots/openpool-tablet.png)

## Kurz gesagt

- Pumpenprofile: Aus, Dauerbetrieb, Badebetrieb, Schlechtwetter, Nachtbaden.
- Restart-Pulse fuer das Chlorsystem.
- Chlorinator-Status aus der Pumpenleistung.
- Waermepumpe mit Zieltemperatur, Start-Betriebsmodus aus dem
  Home-Assistant-Selector, Nachlauf und optionaler PV-Automatik.
- Wettersteuerung als Empfehlung oder Automatik.
- Live-Sync zwischen mehreren offenen Oberflaechen.
- Persistenter Zustand in `/data/openpool_state.json`.

## Vor dem ersten Start

Passe die Entitaeten in der Add-on-Konfiguration an deine Home-Assistant-Anlage
an. Die mitgelieferten Entity-IDs sind nur Beispiele.

Wichtig sind vor allem:

- `entities.pump_switch`
- `entities.heater_climate`
- `entities.heater_operation_mode` fuer den optionalen Home-Assistant-Selector
  der Waermepumpe
- `entities.weather`
- `entities.pv_generation`
- `entities.pv_export`
- `entities.grid_import`
- Pumpen- und Heizungssensoren

Falsche Entitaeten koennen dazu fuehren, dass OpenPool keine sauberen
Entscheidungen trifft oder Befehle an das falsche Geraet sendet.

## Installation

1. Add-on installieren.
2. Add-on-Konfiguration pruefen und Entitaeten anpassen.
3. Add-on starten.
4. **In Seitenleiste anzeigen** aktivieren.

## Hinweis zum Home-Assistant-Verlauf

Standardmaessig nutzt OpenPool den `SUPERVISOR_TOKEN`. Soll der Verlauf
`wurde ausgelöst durch OpenPool` anzeigen, lege einen Home-Assistant-Benutzer
`OpenPool` an, erstelle fuer ihn einen Long-Lived Access Token und setze:

```yaml
connection:
  auth_mode: openpool_user_token
  access_token: "TOKEN_DES_OPENPOOL_BENUTZERS"
```

Ausfuehrliche technische Details stehen in [DOCS.md](DOCS.md).
