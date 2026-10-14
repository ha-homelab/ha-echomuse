"""Security and numeric invariants without a Home Assistant installation."""
from datetime import datetime
import importlib.util
from pathlib import Path
import unittest
from zoneinfo import ZoneInfo

path = Path(__file__).resolve().parents[1] / "custom_components/echomuse_home/policy.py"
spec = importlib.util.spec_from_file_location("home_policy", path)
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class PolicyTest(unittest.TestCase):
    def test_russian_resolution(self):
        self.assertGreater(p.score("первый обогреватель", ["switch.heater_one", "Heater One"]), 0)
        self.assertEqual(p.score("второй обогреватель", ["switch.heater_one", "Heater One"]), 0)
        self.assertGreater(p.score("лампа на кухне", ["light.kitchen_lamp"]), 0)
        self.assertGreater(p.score("обогреватель 1", ["switch.heater_one"]), 0)
        self.assertEqual(p.score("10", ["switch.heater_one"]), 0)

    def test_allowed_actions(self):
        self.assertEqual(p.control_request("light.room", "set_brightness", 12, {}),
                         ("light", "turn_on", {"entity_id": "light.room", "brightness_pct": 12}))
        self.assertEqual(p.control_request("climate.room", "set_temperature", 22, {"min_temp": 10, "max_temp": 30})[2]["temperature"], 22)
        self.assertEqual(p.control_request("media_player.room", "set_volume", 20, {})[2]["volume_level"], 0.2)

    def test_no_arbitrary_or_security_service(self):
        for entity, action in [("switch.x", "restart"), ("button.reset", "activate"),
                               ("lock.door", "open"), ("light.room", "unlock"),
                               ("automation.x", "activate")]:
            with self.subTest(entity=entity), self.assertRaises(ValueError):
                p.control_request(entity, action, None, {})

    def test_invalid_numbers_and_missing_bounds(self):
        for value in [True, False, float("nan"), float("inf"), -1, 101, "50"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                p.control_request("light.room", "set_brightness", value, {})
        with self.assertRaises(ValueError):
            p.control_request("climate.room", "set_temperature", 22, {})
        with self.assertRaises(ValueError):
            p.control_request("climate.room", "set_temperature", 35, {"min_temp": 10, "max_temp": 30})

    def test_modes_and_generic_controls_still_validate_device_capabilities(self):
        self.assertEqual(p.control_request("climate.room", "set_hvac_mode", "heat", {"hvac_modes": ["off", "heat"]})[2]["hvac_mode"], "heat")
        with self.assertRaises(ValueError):
            p.control_request("climate.room", "set_hvac_mode", "cool", {"hvac_modes": ["off", "heat"]})
        self.assertEqual(p.control_request("select.room", "select_option", "eco", {"options": ["eco", "normal"]})[1], "select_option")
        with self.assertRaises(ValueError):
            p.control_request("number.room", "set_value", -5, {"min": 0, "max": 10})

    def test_calendar_days_and_elapsed_hours_differ_at_dst(self):
        now = datetime(2026, 3, 9, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        a, b = p.period_bounds("yesterday", now)
        self.assertEqual(b.timestamp() - a.timestamp(), 23 * 3600)
        a, b = p.period_bounds("last_24_hours", now)
        self.assertEqual(b.timestamp() - a.timestamp(), 24 * 3600)

    def test_bad_periods(self):
        now = datetime(2026, 10, 14, tzinfo=ZoneInfo("America/Los_Angeles"))
        for a, b in [("2026-10-13", "2026-10-15"), ("2026-10-14", "2026-10-13"), ("2020-01-01", "2026-01-01")]:
            with self.assertRaises(ValueError):
                p.period_bounds("custom", now, a, b)


if __name__ == "__main__":
    unittest.main()
