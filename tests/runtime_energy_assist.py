"""Run in the pinned HA image, isolated from the real HA instance and network."""
import asyncio
from pathlib import Path
import sys
import tempfile
import time
import unittest

from homeassistant import loader
from homeassistant.bootstrap import async_load_base_functionality
from homeassistant.config_entries import ConfigEntries
from homeassistant.core import Context, HomeAssistant, SupportsResponse
from homeassistant.helpers import intent
from homeassistant.setup import async_setup_component
from hassil import Intents, recognize

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from render_energy_assist import FALLBACK, REPORTS, configuration


class EnergyRuntimeTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="energy-intent-test-")
        self.hass = HomeAssistant(self.temp.name)
        loader.async_setup(self.hass)
        self.hass.config_entries = ConfigEntries(self.hass, {})
        self.hass.config.skip_pip = True
        self.assertTrue(await async_load_base_functionality(self.hass))
        self.failure = False
        self.locale = "ru"
        self.status = "fresh"
        self.text = None
        self.calls = []
        self.hass.services.async_register("rest_command", "igw_assist_energy_snapshot",
                                          self.snapshot, supports_response=SupportsResponse.ONLY)
        self.package, self.sentences = configuration()
        self.assertTrue(await async_setup_component(self.hass, "script", {"script": self.package["script"]}))
        self.assertTrue(await async_setup_component(self.hass, "intent_script", {"intent_script": self.package["intent_script"]}))
        await self.hass.async_start()

    async def asyncTearDown(self):
        await self.hass.async_stop(force=True)
        self.temp.cleanup()

    async def snapshot(self, call):
        self.calls.append(call.context.id)
        await asyncio.sleep(0.01)
        if self.failure:
            from homeassistant.exceptions import HomeAssistantError
            raise HomeAssistantError("Synthetic unavailable gateway")
        return {"status": 200, "content": {
            "schema_version": 1, "locale": self.locale, "generated_at": time.time(),
            "mqtt_connected": self.status == "fresh",
            "metrics": {"battery_soc": {}, "solar_power": {}, "solar_today": {}},
            "reports": {key: {"status": self.status, "text": self.text or "Отчёт " + key} for key in REPORTS},
        }}

    async def request(self, name):
        return await intent.async_handle(self.hass, "conversation", name, {},
                                          text_input="synthetic", context=Context(), language="ru")

    async def test_all_intents_execute_and_return_speech(self):
        for key, (name, _) in REPORTS.items():
            response = await self.request(name)
            self.assertEqual(response.speech["plain"]["speech"], "Отчёт " + key)

    async def test_same_intent_runs_concurrently_without_lost_response(self):
        replies = await asyncio.gather(*(self.request("EchoEnergyStatus") for _ in range(2)))
        self.assertEqual([reply.speech["plain"]["speech"] for reply in replies], ["Отчёт status"] * 2)
        self.assertEqual(len(set(self.calls)), 2)

    async def test_failure_wrong_locale_and_stale_warning(self):
        self.failure = True
        self.assertEqual((await self.request("EchoEnergyBattery")).speech["plain"]["speech"], FALLBACK)
        self.failure = False
        self.locale = "en"
        self.assertEqual((await self.request("EchoEnergyBattery")).speech["plain"]["speech"], FALLBACK)
        self.locale = "ru"
        self.status = "stale"
        self.assertEqual((await self.request("EchoEnergyBattery")).speech["plain"]["speech"], "Отчёт battery")

    async def test_real_sentence_recognizer(self):
        grammar = Intents.from_dict(self.sentences)
        examples = {
            "Какая сейчас энергетическая сводка": "EchoEnergyStatus",
            "Сколько заряда в аккумуляторе": "EchoEnergyBattery",
            "Сколько сейчас дают солнечные панели": "EchoEnergySolar",
            "Сколько солнце выработало сегодня": "EchoEnergySolarToday",
            "Есть ли аварии": "EchoEnergyAlarms",
            "Что с сетью": "EchoEnergyFlow",
        }
        for phrase, expected in examples.items():
            result = recognize(phrase, grammar)
            self.assertIsNotNone(result, phrase)
            self.assertEqual(result.intent.name, expected)
        self.assertIsNone(recognize("выключи сеть", grammar))

    async def test_upstream_text_is_data_and_control_characters_are_rejected(self):
        self.text = "{{ 123 * 456 }}"
        self.assertEqual((await self.request("EchoEnergyBattery")).speech["plain"]["speech"], self.text)
        self.text = "Ответ\x00"
        self.assertEqual((await self.request("EchoEnergyBattery")).speech["plain"]["speech"], FALLBACK)


if __name__ == "__main__":
    unittest.main()
