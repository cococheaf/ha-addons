import json
import tempfile
import unittest
from pathlib import Path

from openpool_test_utils import FakeHomeAssistant, load_openpool_server


class HeatPumpModeTest(unittest.TestCase):
    def test_saved_custom_start_mode_survives_restart_before_ha_options_arrive(self):
        with tempfile.TemporaryDirectory() as tmp:
            server = load_openpool_server(Path(tmp))
            server.STATE_PATH.write_text(json.dumps({"heater_start_mode": "Eco Heat"}), encoding="utf-8")

            controller = server.OpenPoolController(FakeHomeAssistant())

            self.assertEqual(controller.state["heater_start_mode"], "Eco Heat")
            self.assertIn("Eco Heat", controller.heater_start_modes())
            self.assertEqual(controller.snapshot()["controller"]["heater_start_mode"], "Eco Heat")

    def test_running_heat_pump_gets_stored_start_mode_after_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            server = load_openpool_server(Path(tmp))
            ha = FakeHomeAssistant()
            controller = server.OpenPoolController(ha)
            controller.state["heater_start_mode"] = "Silent Heat"
            controller.ha_states = {
                "heater_climate": {"state": "heat", "attributes": {}},
                "heater_operation_mode": {
                    "state": "Auto",
                    "attributes": {"options": ["Auto", "Silent Heat"]},
                },
                "heater_power": {"state": "900", "attributes": {"unit_of_measurement": "W"}},
            }

            controller._turn_heater(True)

            self.assertIn(
                {
                    "domain": "select",
                    "service": "select_option",
                    "entity_id": "select.poolheizung_betriebsmodus",
                    "data": {"option": "Silent Heat"},
                },
                ha.calls,
            )

    def test_running_heat_pump_does_not_resend_matching_start_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            server = load_openpool_server(Path(tmp))
            ha = FakeHomeAssistant()
            controller = server.OpenPoolController(ha)
            controller.state["heater_start_mode"] = "Silent Heat"
            controller.ha_states = {
                "heater_climate": {"state": "heat", "attributes": {}},
                "heater_operation_mode": {
                    "state": "Silent Heat",
                    "attributes": {"options": ["Auto", "Silent Heat"]},
                },
                "heater_power": {"state": "900", "attributes": {"unit_of_measurement": "W"}},
            }

            controller._turn_heater(True)

            self.assertNotIn(
                {
                    "domain": "select",
                    "service": "select_option",
                    "entity_id": "select.poolheizung_betriebsmodus",
                    "data": {"option": "Silent Heat"},
                },
                ha.calls,
            )


if __name__ == "__main__":
    unittest.main()
