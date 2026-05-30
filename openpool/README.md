# OpenPool

[English version](README.en.md)

OpenPool ist ein Home-Assistant-Add-on fuer eine kompakte Poolsteuerung rund um
Pumpe, Chlorsystem, Waermepumpe, Wetterprofil und PV-Ueberschuss. Das System ist
aktuell fuer Setups mit dem Intex 26680 Sandfilter-/Salzwasserelektrolyse-System
ausgelegt.

## Funktionen

- Pumpenprofile: Aus, Dauerbetrieb, Badebetrieb, Schlechtwetter und Nachtbaden.
- Restart-Pulse fuer das Chlorsystem mit einstellbarer Pulse-Dauer.
- Waermepumpensteuerung mit Zieltemperatur, Start-Betriebsmodus aus einem
  Home-Assistant-Selector, Nachlauf und optionaler PV-Automatik.
- Wettersteuerung als Empfehlung oder Automatik.
- Live-Sync zwischen mehreren Browsern und persistenter Zustand unter
  `/data/openpool_state.json`.

## Vor dem ersten Start

Passe in der Add-on-Konfiguration alle Entitaeten an deine Home-Assistant-Anlage
an. Besonders wichtig sind:

- `entities.pump_switch`
- `entities.heater_climate`
- `entities.heater_operation_mode`
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

Technische Details stehen in [DOCS.md](DOCS.md).
