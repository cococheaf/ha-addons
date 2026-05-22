# Andre's HA-Addons

Dieses Repository bündelt Home-Assistant-Add-ons von Andre Gross in einer gemeinsamen Add-on-Store-Kategorie.

## Add-ons

- **OpenPool**: Poolsteuerung für Home Assistant mit Pumpenprofilen, Wärmepumpenlogik, Wettersteuerung und PV-Automatik.
- **EcoTracker Meter Bridge**: EcoTracker-kompatibler `/v1/json` Endpunkt für vorhandene Home-Assistant-Leistungssensoren.

## Installation in Home Assistant

1. In Home Assistant **Einstellungen** öffnen.
2. Zu **Add-ons** wechseln.
3. Den **Add-on Store** öffnen.
4. Oben rechts über die drei Punkte **Repositories** öffnen.
5. Diese Repository-URL einfügen und hinzufügen:

   ```text
   https://github.com/cococheaf/ha-addons
   ```

6. Store neu laden.
7. Das gewünschte Add-on aus der Kategorie **Andre's HA-Addons** installieren.

## Hinweise zur Migration

Wenn du `OpenPool` oder `EcoTracker Meter Bridge` bereits aus den bisherigen Einzel-Repositories installiert hast, entferne die alten Repository-Einträge erst, nachdem du geprüft hast, dass die Add-ons im neuen Sammel-Repository sichtbar sind.

Die Add-on-Slugs bleiben unverändert:

- `openpool`
- `ecotracker_meter_bridge`

Dadurch erkennt Home Assistant die Add-ons weiterhin über denselben technischen Namen.

## Dokumentation

- OpenPool: [openpool/DOCS.md](openpool/DOCS.md)
- EcoTracker Meter Bridge: [ecotracker_meter_bridge/DOCS.md](ecotracker_meter_bridge/DOCS.md)

## Projekt

- Sicherheitsmeldungen: siehe [SECURITY.md](SECURITY.md)
- Beiträge: siehe [CONTRIBUTING.md](CONTRIBUTING.md)
- Verhaltenskodex: siehe [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- Lizenz: GNU General Public License v3.0, siehe [LICENSE](LICENSE)
