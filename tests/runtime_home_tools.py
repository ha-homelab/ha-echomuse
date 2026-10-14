"""Exercise actual HA service/schema behavior in a separate, isolated runtime."""
import asyncio
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace

from homeassistant import loader
from homeassistant.bootstrap import async_load_base_functionality
from homeassistant.config_entries import ConfigEntries
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm
from homeassistant.components.ollama.entity import _parse_tool_args
from hassil import Intents, recognize
import probatio
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from custom_components.echomuse_home import HomeAPI, ControlEntity


class HomeToolsRuntimeTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="home-tools-test-")
        self.hass = HomeAssistant(self.temp.name)
        loader.async_setup(self.hass)
        self.hass.config_entries = ConfigEntries(self.hass, {})
        self.hass.config.skip_pip = True
        self.assertTrue(await async_load_base_functionality(self.hass))
        self.calls = []
        self.hass.services.async_register("light", "turn_on", self.turn_on)
        self.hass.states.async_set("light.test_room", "off", {"friendly_name": "Kitchen Lamp"})
        self.hass.states.async_set("switch.server", "on", {"friendly_name": "Server"})
        self.hass.states.async_set("sensor.test_energy", "12", {
            "friendly_name": "Test Energy", "unit_of_measurement": "kWh", "state_class": "total_increasing"})
        self.hass.states.async_set("sensor.hidden_secret", "123", {"access_token": "dummy-secret"})
        self.api = HomeAPI(self.hass, {"control_entities": ["light.test_room"], "aliases": {}})
        self.context = llm.LLMContext(platform="ollama", context=None, language="ru", assistant="conversation", device_id=None)
        self.instance = await self.api.async_get_api_instance(self.context)
        await self.hass.async_start()

    async def asyncTearDown(self):
        await self.hass.async_stop(force=True)
        self.temp.cleanup()

    async def turn_on(self, call):
        self.calls.append(call.data)
        self.hass.states.async_set(call.data["entity_id"], "on", {"friendly_name": "Kitchen Lamp"})

    async def tool(self, name, **args):
        # The internal dispatcher retains an additional discovery guard.
        tool = (ControlEntity(self.instance.tools[0].session) if name == "ControlEntity"
                else next(t for t in self.instance.tools if t.name == name))
        return await tool.async_call(self.hass, llm.ToolInput(tool_name=name, tool_args=args), self.context)

    async def test_schemas_serialize_for_real_ollama_adapter(self):
        for tool in self.instance.tools:
            schema = probatio.to_openapi(tool.parameters, custom_serializer=self.instance.custom_serializer)
            self.assertEqual(schema["type"], "object")

    async def test_empty_lookup_survives_native_ollama_argument_filter(self):
        # The native adapter removes empty strings from model arguments.
        result = await self.tool("FindEntities", **_parse_tool_args({"query": "", "domain": "light"}))
        self.assertFalse(result.error)
        self.assertEqual(result.data["total"], 1)
        self.assertNotIn("aliases", result.data["entities"][0])

    async def test_russian_state_sentences_do_not_match_control_commands(self):
        path = Path(__file__).resolve().parents[1] / "examples/custom_sentences/ru/echomuse_home.yaml"
        data = yaml.safe_load(path.read_text())
        data["lists"]["name"] = {"values": [{"in": "первый обогреватель", "out": "first heater", "context": {"domain": "switch"}}]}
        grammar = Intents.from_dict(data)
        for text in ["Включён ли первый обогреватель", "Первый обогреватель сейчас включен"]:
            result = recognize(text, grammar)
            self.assertIsNotNone(result, text)
            self.assertEqual(result.intent.name, "HassGetState")
            self.assertEqual(result.entities["state"].value, "on")
        self.assertIsNone(recognize("Выключи первый обогреватель", grammar))

    async def test_lookup_and_control_actual_isolated_service(self):
        found = await self.tool("FindEntities", query="лампа на кухне", domain="light")
        self.assertFalse(found.error)
        self.assertEqual(found.data["total"], 1)
        self.assertEqual(found.data["entities"][0]["state"], "off")
        result = await self.tool("ControlEntity", entity_id="light.test_room", operation="turn_on")
        self.assertFalse(result.error)
        self.assertEqual(result.data["observed"]["state"], "on")
        self.assertEqual(len(self.calls), 1)

    async def test_undiscovered_readonly_unavailable_and_invalid_calls_never_execute(self):
        self.assertTrue((await self.tool("ControlEntity", entity_id="light.test_room", operation="turn_on")).error)
        await self.tool("FindEntities", query="")
        self.assertTrue((await self.tool("ControlEntity", entity_id="switch.server", operation="turn_off")).error)
        self.assertTrue((await self.tool("ControlEntity", entity_id="light.test_room", operation="set_brightness", value=999)).error)
        self.assertTrue((await self.tool("ControlEntity", entity_id="light.test_room", operation="turn_on", extra="bad")).error)
        self.hass.states.async_set("light.test_room", "unavailable")
        self.assertTrue((await self.tool("ControlEntity", entity_id="light.test_room", operation="turn_on")).error)
        self.assertEqual(self.calls, [])

    async def test_sensor_discovery_cannot_be_mistaken_for_period_consumption(self):
        result = await self.tool("FindEntities", query="test energy")
        row = result.data["entities"][0]
        self.assertNotIn("state", row)
        self.assertTrue(row["available"])
        self.assertEqual(row["read_with"]["history"], "GetStatistics")
        current = await self.tool("GetEntityState", entity_id=row["entity_id"])
        self.assertEqual(current.data["state"], "12")

    async def test_named_control_resolves_authorizes_and_executes_once(self):
        result = await self.tool("ControlDevice", query="лампа на кухне", domain="light", operation="turn_on")
        self.assertFalse(result.error)
        self.assertEqual(result.data["observed"]["state"], "on")
        self.assertEqual(len(self.calls), 1)
        self.assertTrue((await self.tool("ControlDevice", query="server", operation="turn_off")).error)
        self.hass.states.async_set("light.second_room", "off", {"friendly_name": "Kitchen Lamp Two"})
        self.api.controls.add("light.second_room")
        self.assertTrue((await self.tool("ControlDevice", query="kitchen lamp", operation="turn_on")).error)
        self.assertTrue((await self.tool("ControlDevice", query="в", operation="turn_on")).error)
        self.assertEqual(len(self.calls), 1)

    async def test_current_time_uses_home_assistant_timezone(self):
        result = await self.tool("GetDateTime")
        self.assertFalse(result.error)
        self.assertEqual(result.data["timezone"], self.hass.config.time_zone)
        self.assertIn("T", result.data["datetime"])
        self.assertEqual(self.calls, [])

    async def test_private_attributes_and_other_providers(self):
        result = await self.tool("FindEntities", query="secret")
        self.assertNotIn("access_token", result.data["entities"][0]["attributes"])
        self.context.platform = "openai_conversation"
        with self.assertRaises(HomeAssistantError):
            await self.api.async_get_api_instance(self.context)

    async def test_entity_permissions_are_enforced(self):
        self.context.context = SimpleNamespace(user_id="test-user")
        user = SimpleNamespace(permissions=SimpleNamespace(check_entity=lambda *_: False))
        auth = SimpleNamespace(async_get_user=AsyncMock(return_value=user))
        with patch.object(self.hass, "auth", new=auth, create=True):
            result = await self.tool("FindEntities", query="")
            denied = await self.tool("ControlDevice", query="kitchen lamp", operation="turn_on")
        self.assertTrue(denied.error)
        self.assertEqual(self.calls, [])
        self.assertEqual(result.data["total"], 0)

    async def test_limited_pagination_and_fresh_state(self):
        for i in range(20):
            self.hass.states.async_set(f"sensor.thermo_{i}", str(i), {"friendly_name": f"Thermo {i}"})
        result = await self.tool("FindEntities", query="thermo")
        self.assertEqual(len(result.data["entities"]), 12)
        self.assertEqual(result.data["total"], 20)
        second = await self.tool("FindEntities", query="thermo", offset=12)
        self.assertEqual(len(second.data["entities"]), 8)
        entity = result.data["entities"][0]["entity_id"]
        self.hass.states.async_set(entity, "99")
        self.assertEqual((await self.tool("GetEntityState", entity_id=entity)).data["state"], "99")

    async def test_statistics_preserve_missing_and_numeric_values(self):
        await self.tool("FindEntities", query="test energy")
        recorder = AsyncMock()
        recorder.async_add_executor_job.return_value = {"change": 2.5, "mean": None, "min": float("nan")}
        with patch("homeassistant.components.recorder.get_instance", return_value=recorder):
            result = await self.tool("GetStatistics", entity_id="sensor.test_energy", period="yesterday")
        self.assertEqual(result.data["statistics"], {"change": 2.5})
        self.assertEqual(result.data["unit"], "kWh")
        recorder.async_add_executor_job.return_value = {}
        with patch("homeassistant.components.recorder.get_instance", return_value=recorder):
            result = await self.tool("GetStatistics", entity_id="sensor.test_energy", period="yesterday")
        self.assertFalse(result.data["available"])
        self.assertEqual(result.data["statistics"], {})


if __name__ == "__main__":
    unittest.main()
