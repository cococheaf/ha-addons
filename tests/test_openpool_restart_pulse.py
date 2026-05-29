import importlib.util
import tempfile
import unittest
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


def load_openpool_server(tmp_path: Path):
    spec = importlib.util.spec_from_file_location("openpool_server_test", ROOT_DIR / "openpool" / "server.py")
    server = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server)
    server.OPTIONS_PATH = tmp_path / "options.json"
    server.STATE_PATH = tmp_path / "state.json"
    server.OPTIONS_PATH.write_text(
        """{
          "features": {"heat_pump_control": true},
          "entities": {
            "pump_switch": "switch.poolpumpe",
            "heater_climate": "climate.poolheizung",
            "heater_operation_mode": "select.poolheizung_betriebsmodus"
          }
        }""",
        encoding="utf-8",
    )
    return server


class RestartPulseTest(unittest.TestCase):
    def test_restart_pulse_does_not_turn_heater_off_while_pump_state_restores(self):
        with tempfile.TemporaryDirectory() as tmp:
            server = load_openpool_server(Path(tmp))
            ha = FakeHomeAssistant()
            controller = server.OpenPoolController(ha)
            controller.state["pump_mode"] = "Dauerbetrieb"
            controller.state["heater_mode"] = "Ein"
            controller.state["master_enabled"] = True
            controller.ha_states = {
                "pump_switch": {"state": "on", "attributes": {}},
                "heater_climate": {"state": "heat", "attributes": {}},
                "heater_operation_mode": {"state": "Auto", "attributes": {"options": ["Auto"]}},
                "heater_power": {"state": "900", "attributes": {"unit_of_measurement": "W"}},
            }

            controller._start_restart_pulse(1, "Test Restart-Pulse")
            controller.state["pending_job"]["until"] = server.now_ts() - 1
            controller.ha_states["pump_switch"]["state"] = "off"

            controller._apply_jobs()

            self.assertEqual(controller.state["pending_job"]["type"], "restart_pulse_restore")
            self.assertIn(
                {"domain": "switch", "service": "turn_on", "entity_id": "switch.poolpumpe", "data": {}},
                ha.calls,
            )
            self.assertNotIn(
                {"domain": "climate", "service": "turn_off", "entity_id": "climate.poolheizung", "data": {}},
                ha.calls,
            )

            controller._apply_jobs()
            self.assertEqual(controller.state["pending_job"]["type"], "restart_pulse_restore")
            self.assertNotIn(
                {"domain": "climate", "service": "turn_off", "entity_id": "climate.poolheizung", "data": {}},
                ha.calls,
            )

            controller.ha_states["pump_switch"]["state"] = "on"
            controller._apply_jobs()

            self.assertIsNone(controller.state["pending_job"])
            self.assertNotIn(
                {"domain": "climate", "service": "turn_off", "entity_id": "climate.poolheizung", "data": {}},
                ha.calls,
            )
            self.assertNotIn("Heizung AUS", [entry.get("title") for entry in controller.state["command_log"]])


if __name__ == "__main__":
    unittest.main()
