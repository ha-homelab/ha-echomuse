"""Exercise the rendered HA template with malformed and concurrent-session data."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

from jinja2 import Environment, StrictUndefined
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from render_energy_assist import FALLBACK, REPORTS, SPEECH_TEMPLATE, configuration, render


def snapshot():
    return {"status": 200, "content": {
        "schema_version": 1, "locale": "ru", "generated_at": 1000,
        "mqtt_connected": True,
        "metrics": {"battery_soc": {}, "solar_power": {}, "solar_today": {}},
        "reports": {key: {"status": "fresh", "text": "Достоверная сводка."} for key in REPORTS},
    }}


class TestEnergyAssist(unittest.TestCase):
    def setUp(self):
        self.env = Environment(undefined=StrictUndefined)
        self.env.globals.update(now=lambda: 1005, as_timestamp=lambda value: value)
        self.template = self.env.from_string(SPEECH_TEMPLATE)

    def speech(self, response, report="status"):
        return self.template.render(igw_response=response, report_key=report,
                                    maximum_age=30, fallback=FALLBACK)

    def test_valid_report_and_preferred_status_brief(self):
        body = snapshot()
        self.assertEqual(self.speech(body), "Достоверная сводка.")
        body["content"]["reports"]["status"]["brief_text"] = "Данные свежие. Заряд семьдесят процентов."
        self.assertEqual(self.speech(body), "Данные свежие. Заряд семьдесят процентов.")

    def test_warning_states_are_not_converted_to_zero(self):
        for status in ("stale", "unavailable", "unconfigured"):
            body = snapshot()
            body["content"]["mqtt_connected"] = False
            body["content"]["reports"]["battery"] = {"status": status, "text": "Данные устарели. Заряд неизвестен."}
            self.assertEqual(self.speech(body, "battery"), "Данные устарели. Заряд неизвестен.")

    def test_malformed_envelopes_fail_closed(self):
        for response in (None, [], "text", {}, {"status": 200}, {"status": 200, "content": []}):
            with self.subTest(response=response):
                self.assertEqual(self.speech(response), FALLBACK)
        for field, value in [("locale", "en"), ("locale", None), ("schema_version", True),
                             ("schema_version", 2), ("generated_at", True),
                             ("generated_at", "1000"), ("generated_at", 900),
                             ("generated_at", 1011), ("generated_at", float("nan")),
                             ("generated_at", float("inf")), ("mqtt_connected", "true"),
                             ("mqtt_connected", False), ("metrics", []), ("reports", [])]:
            body = snapshot()
            body["content"][field] = value
            with self.subTest(field=field, value=value):
                self.assertEqual(self.speech(body), FALLBACK)

    def test_invalid_or_overlong_report_not_truncated(self):
        for value in (None, 42, [], "", "  ", "а" * 901, "Ответ\x00", "Ответ\x1b"):
            body = snapshot()
            body["content"]["reports"]["status"]["text"] = value
            self.assertEqual(self.speech(body), FALLBACK)
        body = snapshot()
        body["content"]["reports"]["status"]["brief_text"] = "а" * 901
        self.assertEqual(self.speech(body), FALLBACK)
        body = snapshot()
        del body["content"]["reports"]["flow"]
        self.assertEqual(self.speech(body, "flow"), FALLBACK)
        self.assertEqual(self.speech(snapshot(), "shell_command"), FALLBACK)
        self.assertEqual(self.template.render(igw_response=snapshot(), maximum_age=30, fallback=FALLBACK), FALLBACK)

    def test_report_text_is_not_evaluated_as_template(self):
        body = snapshot()
        body["content"]["reports"]["status"]["text"] = "{{ 123 * 456 }}"
        self.assertEqual(self.speech(body), "{{ 123 * 456 }}")

    def test_response_state_is_session_local(self):
        first, second = snapshot(), snapshot()
        first["content"]["reports"]["battery"]["text"] = "Первый ответ."
        second["content"]["reports"]["battery"]["text"] = "Второй ответ."
        self.assertEqual(self.speech(first, "battery"), "Первый ответ.")
        self.assertEqual(self.speech(second, "battery"), "Второй ответ.")
        self.assertEqual(self.speech(first, "battery"), "Первый ответ.")

    def test_rendered_package_yaml_and_exact_response_routing(self):
        class Loader(yaml.SafeLoader):
            pass
        Loader.add_constructor("!secret", lambda loader, node: {"tag": loader.construct_scalar(node)})
        with TemporaryDirectory() as directory:
            target = Path(directory) / "rendered"
            render(target)
            package = yaml.load((target / "packages/igw_energy_assist.yaml").read_text(), Loader=Loader)
            sentences = json.loads((target / "custom_sentences/ru/igw_energy.yaml").read_text())
            rest = package["rest_command"]["igw_assist_energy_snapshot"]
            self.assertEqual(rest["url"], {"tag": "igw_assist_energy_url"})
            self.assertEqual(rest["headers"]["Authorization"], {"tag": "igw_assist_energy_authorization"})
            self.assertTrue(rest["verify_ssl"])
            self.assertEqual(rest["method"], "GET")
            self.assertEqual(sentences["language"], "ru")
            self.assertEqual(set(sentences["intents"]), set(package["intent_script"]))
            for key, (intent, _) in REPORTS.items():
                handler = package["intent_script"][intent]
                self.assertEqual(handler["action"][0]["data"], {"report_key": key})
                self.assertEqual(handler["action"][1]["response_variable"], "report")
                self.assertEqual(handler["speech"]["text"], "{{ action_response.speech }}")
                self.assertEqual(handler["mode"], "parallel")
            self.assertNotIn("media_player", json.dumps(package))
            self.assertNotIn("tts.speak", json.dumps(package))
            before = (target / "packages/igw_energy_assist.yaml").read_bytes()
            with self.assertRaises(FileExistsError):
                render(target)
            self.assertEqual(before, (target / "packages/igw_energy_assist.yaml").read_bytes())

    def test_age_configuration_bounds(self):
        for age in (False, 1, 121, "30"):
            with self.assertRaises(ValueError):
                configuration(age)


if __name__ == "__main__":
    unittest.main()
