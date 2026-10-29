"""Offline adapter contract against installed HA imports; no real device I/O.

Run with a compatible Home Assistant Python environment. All transports,
registries and storage are fakes. Importing this file does not run tests.
"""
import asyncio
from ipaddress import IPv4Address
import json
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from homeassistant.core import Context, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
import probatio as vol

from custom_components.echomuse_home import announcements as a

RID = "announce-" + "b" * 32 + "-223"
ENTITY = "assist_satellite.test"
# Synthetic RFC1918 address, not a discovered endpoint or an actual connection.
FOREIGN_PRIVATE_ORIGIN = f"http://{IPv4Address(0x0A000007)}"


class RuntimeAnnouncementsTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.runtime = SimpleNamespace(available=True, device_info=SimpleNamespace(name="test-dot"),
                                       services={}, client=SimpleNamespace(execute_service=AsyncMock()))
        self.entry = SimpleNamespace(domain="assist_satellite", platform="esphome", device_id="device-1",
                                     disabled_by=None, config_entry_id="config-1")
        self.config = SimpleNamespace(domain="esphome", data={"noise_psk": "test"}, runtime_data=self.runtime)
        self.auth = SimpleNamespace(async_get_user=AsyncMock(return_value=SimpleNamespace(
            permissions=SimpleNamespace(check_entity=lambda *_: True))))
        self.hass = SimpleNamespace(auth=self.auth, config_entries=SimpleNamespace(async_get_entry=lambda _: self.config),
                                    config=SimpleNamespace(internal_url="http://ha.internal:8123", external_url="https://ha.example"))
        self.transport = a.NativeTransport(self.hass)
        self.call = SimpleNamespace(data={"entity_id": ENTITY}, context=Context(user_id="user-1"))
        self.registry = SimpleNamespace(async_get=lambda _: self.entry)

    async def bind(self):
        with patch.object(a.er, "async_get", return_value=self.registry):
            return await self.transport.bind(self.call, control=True)

    async def test_registry_binding_not_user_supplied_service_name(self):
        endpoint = await self.bind()
        self.assertEqual(endpoint.device_id, "device-1")
        self.assertEqual(endpoint.name, "test-dot")
        self.assertIs(endpoint.runtime, self.runtime)

    async def test_permission_denial_happens_before_transport(self):
        self.auth.async_get_user.return_value.permissions.check_entity = lambda *_: False
        with self.assertRaises(HomeAssistantError): await self.bind()
        self.runtime.client.execute_service.assert_not_called()

    async def test_no_unencrypted_or_non_esphome_target(self):
        self.config.data = {}
        with self.assertRaises(HomeAssistantError): await self.bind()
        self.config.data = {"noise_psk": "test"}
        self.entry.platform = "other"
        with self.assertRaises(HomeAssistantError): await self.bind()
        self.runtime.client.execute_service.assert_not_called()

    async def test_disconnected_endpoint_is_explicit(self):
        self.runtime.available = False
        with self.assertRaises(a.EndpointUnavailable): await self.bind()

    async def test_relative_tts_proxy_uses_standard_ha_resolution(self):
        path = "/api/tts_proxy/example.wav"
        final = "http://ha.internal:8123" + path + "?authSig=example"
        with patch.object(a, "get_url", return_value="http://ha.internal:8123"), \
             patch.object(a, "async_process_play_media_url", return_value=final) as resolve:
            self.assertEqual(await self.transport.resolve(path), final)
            resolve.assert_called_once_with(self.hass, path)
        self.runtime.client.execute_service.assert_not_called()

    async def test_configured_and_current_ha_origins_are_allowed(self):
        with patch.object(a, "get_url", return_value="http://selected-ha.example:8123"), \
             patch.object(a, "async_process_play_media_url", side_effect=lambda _, url: url):
            for url in ("https://ha.example:443/api/tts_proxy/a.wav", "http://ha.internal:8123/api/tts_proxy/a.wav",
                        "http://selected-ha.example:8123/api/tts_proxy/a.wav"):
                self.assertEqual(await self.transport.resolve(url), url)

    async def test_foreign_private_or_lookalike_origin_is_rejected_before_resolution(self):
        with patch.object(a, "get_url", return_value="http://ha.internal:8123"), \
             patch.object(a, "async_process_play_media_url") as resolve:
            for url in ("http://192.0.2.20:8181/audio.wav", FOREIGN_PRIVATE_ORIGIN + "/audio.wav", "https://ha.example.evil.test/a.wav",
                        "http://ha.example/a.wav", "https://ha.example:8443/a.wav"):
                with self.subTest(url=url), self.assertRaises(ValueError):
                    await self.transport.resolve(url)
            resolve.assert_not_called()

    async def test_foreign_origin_after_media_source_resolution_is_rejected(self):
        with patch.object(a, "get_url", return_value="http://ha.internal:8123"), \
             patch.object(a.media_source, "async_resolve_media", new=AsyncMock(return_value=SimpleNamespace(url=FOREIGN_PRIVATE_ORIGIN + "/audio.wav"))), \
             patch.object(a, "async_process_play_media_url") as resolve:
            with self.assertRaises(ValueError):
                await self.transport.resolve("media-source://media_source/local/example.wav")
            resolve.assert_not_called()

    async def test_final_origin_is_checked_again(self):
        with patch.object(a, "get_url", return_value="http://ha.internal:8123"), \
             patch.object(a, "async_process_play_media_url", return_value=FOREIGN_PRIVATE_ORIGIN + "/audio.wav"):
            with self.assertRaises(ValueError):
                await self.transport.resolve("/api/tts_proxy/example.wav")

    async def test_tts_source_never_reaches_resolver(self):
        with patch.object(a.media_source, "async_resolve_media", new=AsyncMock()) as resolve:
            with self.assertRaises(ValueError):
                await self.transport.resolve("media-source://tts/provider?message=example")
            resolve.assert_not_called()

    async def test_native_response_is_correlated(self):
        endpoint = await self.bind()
        service = SimpleNamespace(name="guarded_announcement_status", supports_response=2)
        self.runtime.services[1] = service
        self.runtime.client.execute_service.return_value = SimpleNamespace(success=True, response_data=json.dumps(
            {"request_id": RID, "status": "completed", "protocol": a.PROTOCOL, "boot_id": "boot-1"}))
        result = await self.transport.send(endpoint, "status", {"request_id": RID})
        self.assertEqual(result["status"], "completed")
        self.runtime.client.execute_service.assert_awaited_once_with(service, {"request_id": RID}, return_response=True)

    async def test_response_from_other_request_is_rejected(self):
        endpoint = await self.bind()
        self.runtime.services[1] = SimpleNamespace(name="guarded_announcement_status", supports_response=2)
        self.runtime.client.execute_service.return_value = SimpleNamespace(success=True, response_data='{"request_id":"other"}')
        with self.assertRaises(HomeAssistantError):
            await self.transport.send(endpoint, "status", {"request_id": RID})

    async def test_missing_guard_never_falls_back(self):
        endpoint = await self.bind()
        self.runtime.services[1] = SimpleNamespace(name="announce", supports_response=0)
        with self.assertRaises(HomeAssistantError):
            await self.transport.send(endpoint, "submit", {"request_id": RID})
        self.runtime.client.execute_service.assert_not_called()

    async def test_duck_capability_requires_responding_dedicated_action(self):
        endpoint = await self.bind()
        self.runtime.services[1] = SimpleNamespace(name="guarded_announcement_capabilities", supports_response=2)
        async def reply(service, values, **kwargs):
            return SimpleNamespace(success=True, response_data=json.dumps({"request_id": values["request_id"],
                "protocol": a.PROTOCOL, "boot_id": "boot-1", "duck_music": True}))
        self.runtime.client.execute_service.side_effect = reply
        self.assertFalse((await self.transport.send(endpoint, "capabilities", {}))["duck_music"])
        self.runtime.services[2] = SimpleNamespace(name="guarded_announcement_submit_duck", supports_response=0)
        self.assertFalse((await self.transport.send(endpoint, "capabilities", {}))["duck_music"])
        self.runtime.services[2].supports_response = 1
        self.assertTrue((await self.transport.send(endpoint, "capabilities", {}))["duck_music"])
        self.runtime.services[3] = SimpleNamespace(name="guarded_announcement_submit_duck", supports_response=1)
        self.assertFalse((await self.transport.send(endpoint, "capabilities", {}))["duck_music"])

    async def test_missing_duck_action_does_not_use_legacy_submit(self):
        endpoint = await self.bind()
        self.runtime.services[1] = SimpleNamespace(name="guarded_announcement_submit", supports_response=2)
        with self.assertRaises(HomeAssistantError):
            await self.transport.send(endpoint, "submit_duck", {"request_id": RID, "media_id": "http://ha.example/a.wav", "expires_at": "1000"})
        self.runtime.client.execute_service.assert_not_called()

    async def test_event_only_service_is_not_playback_evidence(self):
        endpoint = await self.bind()
        self.runtime.services[1] = SimpleNamespace(name="guarded_announcement_status", supports_response=0)
        with self.assertRaises(HomeAssistantError):
            await self.transport.send(endpoint, "status", {"request_id": RID})
        self.runtime.client.execute_service.assert_not_called()

    async def test_native_response_timeout_is_bounded(self):
        endpoint = await self.bind()
        self.runtime.services[1] = SimpleNamespace(name="guarded_announcement_status", supports_response=1)
        async def never_returns(*args, **kwargs):
            await asyncio.Future()
        self.runtime.client.execute_service.side_effect = never_returns
        with patch.object(a, "TIMEOUT", .005):
            with self.assertRaises(TimeoutError):
                await self.transport.send(endpoint, "status", {"request_id": RID})

    def test_schema_requires_one_target_and_no_audio_overrides(self):
        good = {"entity_id": ENTITY, "request_id": RID, "media_id": "/local/rendered.wav", "expires_at": 1234}
        self.assertIs(a.SUBMIT(good)["preannounce"], False)
        self.assertEqual(a.SUBMIT(good)["busy_policy"], "skip")
        self.assertEqual(a.SUBMIT({**good, "busy_policy": "duck_music"})["busy_policy"], "duck_music")
        for override in ({"preannounce": True}, {"preannounce": 0}, {"busy_policy": "interrupt"},
                         {"expires_at": True}, {"entity_id": [ENTITY]}, {"start_conversation": True}, {"duck_db": -18}):
            with self.subTest(override=override), self.assertRaises(vol.Invalid): a.SUBMIT({**good, **override})

    async def setup_services(self, saved=None):
        self.registered = {}
        self.hass.services = SimpleNamespace(async_register=lambda domain, name, handler, **options:
                                             self.registered.update({name: (handler, options)}))
        store = SimpleNamespace(async_load=AsyncMock(return_value=saved), async_save=AsyncMock())
        with patch.object(a, "Store", return_value=store):
            broker = await a.async_setup_announcements(self.hass)
        return broker, store

    async def test_services_are_response_only_without_new_setup_dependency(self):
        await self.setup_services()
        self.assertEqual(set(self.registered), {"announcement_" + name for name in ("submit", "status", "stop", "capabilities")})
        for _, options in self.registered.values():
            self.assertIs(options["supports_response"], SupportsResponse.ONLY)

    async def test_submit_service_forwards_explicit_duck_policy(self):
        broker, _ = await self.setup_services()
        broker.submit = AsyncMock(return_value={"request_id": RID, "status": "accepted"})
        data = a.SUBMIT({"entity_id": ENTITY, "request_id": RID, "media_id": "/api/tts_proxy/a.wav", "expires_at": 1000, "busy_policy": "duck_music"})
        call = SimpleNamespace(service="announcement_submit", data=data, context=self.call.context)
        with patch.object(a.er, "async_get", return_value=self.registry):
            self.assertEqual((await self.registered[call.service][0](call))["status"], "accepted")
        self.assertEqual(broker.submit.call_args.kwargs["policy"], "duck_music")

    async def test_unavailable_device_returns_truthful_receipt(self):
        await self.setup_services()
        self.runtime.available = False
        call = SimpleNamespace(service="announcement_status", data={"entity_id": ENTITY, "request_id": RID}, context=self.call.context)
        with patch.object(a.er, "async_get", return_value=self.registry):
            response = await self.registered[call.service][0](call)
        self.assertEqual(response, {"request_id": RID, "status": "unknown", "reason": "satellite_unavailable"})

    async def test_corrupt_ledger_keeps_home_integration_loaded_but_blocks_dispatch(self):
        broker, store = await self.setup_services({"records": {"damaged": {}}})
        async def send(target, operation, data):
            self.fail("Corrupt ledger must be rejected before native dispatch")
        broker.send = send
        broker.resolve = AsyncMock(return_value="http://ha.local/file.wav")
        self.assertEqual((await broker.get_capabilities("target"))["reason"], "ledger_unavailable")
        response = await broker.submit("target", identity="device-1", rid=RID, source="/local/file.wav", expires_at=int(broker.now()) + 100)
        self.assertEqual(response["reason"], "guarded_endpoint_unavailable")
        store.async_save.assert_not_called()

    async def test_non_object_top_level_ledger_is_not_reset(self):
        broker, store = await self.setup_services(["corrupt"])
        self.assertFalse((await broker.get_capabilities("target"))["dedup"])
        store.async_save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
