# Contributing to Andre's HA-Addons

Thank you for your interest in contributing to **Andre's HA-Addons**.

This repository bundles multiple Home Assistant add-ons in one add-on repository so they appear together in the Home Assistant Add-on Store.

## Add-ons

- `openpool`: Pool system controller for Home Assistant.
- `ecotracker_meter_bridge`: EcoTracker-compatible endpoint for Home Assistant power sensors.

## Pull Requests

Please keep pull requests focused and update the affected add-on documentation when behavior or configuration changes.

Depending on the change, check:

- the affected add-on's `config.yaml`
- the affected add-on's `DOCS.md`
- the affected add-on's `README.md`
- root `repository.yaml` if repository metadata changes
- add-on translations when option names or descriptions change

## Testing

Local test dependencies can be installed with:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
```

Run repository checks with:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

For add-on-specific changes, also test the add-on in Home Assistant where possible.

## License

By contributing to this project, you agree that your contributions will be licensed under the same license as the project.

This project is licensed under the **GNU General Public License v3.0**.
