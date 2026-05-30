import importlib.util
import json
import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


class FakeHomeAssistant:
    def __init__(self):
        self.calls = []

    def service(self, domain, service, entity_id=None, data=None, return_response=False):
        self.calls.append(
            {
                "domain": domain,
                "service": service,
                "entity_id": entity_id,
                "data": data or {},
            }
        )

    def auth_status(self):
        return {"mode": "test", "token_source": "test"}


def load_openpool_server(tmp_path: Path, extra_options: dict | None = None):
    options_path = tmp_path / "options.json"
    state_path = tmp_path / "state.json"
    options = {
        "features": {"heat_pump_control": True},
        "entities": {
            "pump_switch": "switch.poolpumpe",
            "heater_climate": "climate.poolheizung",
            "heater_operation_mode": "select.poolheizung_betriebsmodus",
        },
    }
    if extra_options:
        options.update(extra_options)
    options_path.write_text(json.dumps(options), encoding="utf-8")

    spec = importlib.util.spec_from_file_location("openpool_server_test", ROOT_DIR / "openpool" / "server.py")
    server = importlib.util.module_from_spec(spec)
    previous_options = os.environ.get("OPENPOOL_OPTIONS")
    previous_state = os.environ.get("OPENPOOL_STATE")
    os.environ["OPENPOOL_OPTIONS"] = str(options_path)
    os.environ["OPENPOOL_STATE"] = str(state_path)
    try:
        spec.loader.exec_module(server)
    finally:
        if previous_options is None:
            os.environ.pop("OPENPOOL_OPTIONS", None)
        else:
            os.environ["OPENPOOL_OPTIONS"] = previous_options
        if previous_state is None:
            os.environ.pop("OPENPOOL_STATE", None)
        else:
            os.environ["OPENPOOL_STATE"] = previous_state

    server.OPTIONS_PATH = options_path
    server.STATE_PATH = state_path
    return server
