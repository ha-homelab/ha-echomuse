"""HA transport for the optional, device-owned guarded announcement protocol."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

import probatio as vol

from homeassistant.auth.permissions.const import POLICY_CONTROL, POLICY_READ
from homeassistant.components import media_source
from homeassistant.components.media_player import async_process_play_media_url
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.storage import Store

from .announcement_protocol import AnnouncementBroker, PROTOCOL, capabilities, failed, request_id, media_id as validate_media_id
from .policy import DOMAIN

NATIVE_PREFIX = "guarded_announcement_"
TIMEOUT = 2


def _origin(value: str) -> tuple[str, str, int]:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("A trusted Home Assistant HTTP origin is required")
    port = parsed.port if parsed.port is not None else (443 if parsed.scheme == "https" else 80)
    return parsed.scheme, parsed.hostname.lower(), port


def _false(value):
    if value is not False:
        raise vol.Invalid("preannounce must be false")
    return value


def _integer(value):
    if type(value) is not int:
        raise vol.Invalid("expires_at must be integer Unix UTC seconds")
    return value


def _request_id(value):
    try:
        return request_id(value)
    except ValueError as exc:
        raise vol.Invalid(str(exc)) from exc


TARGET = {vol.Required("entity_id"): cv.entity_id}
REQUEST = {**TARGET, vol.Required("request_id"): _request_id}
SUBMIT = vol.Schema({
    **REQUEST,
    vol.Required("media_id"): cv.string,
    vol.Required("expires_at"): _integer,
    vol.Optional("preannounce", default=False): _false,
    vol.Optional("busy_policy", default="skip"): vol.In(["skip"]),
})


@dataclass(frozen=True)
class Endpoint:
    entity_id: str
    device_id: str
    name: str
    runtime: Any


class EndpointUnavailable(Exception):
    """The authorized target has no current transport."""


class NativeTransport:
    """Resolve the native action on the target's own encrypted ESPHome entry."""
    def __init__(self, hass):
        self.hass = hass

    async def bind(self, call, *, control: bool) -> Endpoint:
        entity_id = call.data["entity_id"]
        if call.context.user_id:
            user = await self.hass.auth.async_get_user(call.context.user_id)
            if user is None or not user.permissions.check_entity(entity_id, POLICY_CONTROL if control else POLICY_READ):
                raise HomeAssistantError("Entity permission denied")
        entry = er.async_get(self.hass).async_get(entity_id)
        if (entry is None or entry.domain != "assist_satellite" or entry.platform != "esphome"
            or not entry.device_id or entry.disabled_by is not None):
            raise HomeAssistantError("A registered ESPHome assist satellite is required")
        config = self.hass.config_entries.async_get_entry(entry.config_entry_id)
        runtime = getattr(config, "runtime_data", None)
        if config is None or config.domain != "esphome" or not config.data.get("noise_psk"):
            raise HomeAssistantError("An encrypted ESPHome connection is required")
        if runtime is None or not runtime.available or runtime.device_info is None:
            raise EndpointUnavailable()
        return Endpoint(entity_id, entry.device_id, runtime.device_info.name, runtime)

    async def resolve(self, source: str) -> str:
        async with asyncio.timeout(TIMEOUT):
            validate_media_id(source)
            configured = [self.hass.config.internal_url, self.hass.config.external_url]
            try:
                # Match the same selection used by async_process_play_media_url.
                configured.append(get_url(self.hass))
            except NoURLAvailableError:
                pass
            origins = set()
            for url in configured:
                if url:
                    origins.add(_origin(url))

            def check_absolute(url):
                if urlsplit(url).scheme in {"http", "https"} and _origin(url) not in origins:
                    raise ValueError("Audio URL must use a configured Home Assistant origin")

            check_absolute(source)
            if media_source.is_media_source_id(source):
                resolved = await media_source.async_resolve_media(self.hass, source, None)
                source = resolved.url
                validate_media_id(source)
                check_absolute(source)
            resolved = async_process_play_media_url(self.hass, source)
            validate_media_id(resolved)
            if _origin(resolved) not in origins:
                raise ValueError("Resolved audio URL must use a configured Home Assistant origin")
            return resolved

    async def send(self, endpoint: Endpoint, operation: str, values: dict) -> dict:
        if not endpoint.runtime.available:
            raise HomeAssistantError("The satellite disconnected")
        matches = [item for item in endpoint.runtime.services.values() if item.name == NATIVE_PREFIX + operation]
        if len(matches) != 1:
            raise HomeAssistantError("The guarded native action is unavailable")
        service = matches[0]
        values = dict(values)
        if operation == "capabilities":
            values["request_id"] = "announce-" + uuid4().hex + "-000"
        rid = values["request_id"]
        # Require the authenticated, wire-correlated native action response.
        # Global HA events and successful command submission are not receipts.
        if getattr(service, "supports_response", 0) not in (1, 2):
            raise HomeAssistantError("The guarded native action requires JSON responses")
        async with asyncio.timeout(TIMEOUT):
            response = await endpoint.runtime.client.execute_service(service, values, return_response=True)
        if response is None or not response.success or not response.response_data:
            raise HomeAssistantError("The native action returned no receipt")
        data = json.loads(response.response_data)
        if not isinstance(data, dict) or data.get("request_id") != rid:
            raise HomeAssistantError("The native receipt is not correlated")
        return data


async def async_setup_announcements(hass):
    """Register additive services; stock firmware always fails closed."""
    store = Store(hass, 1, DOMAIN + ".announcement_dispatches")
    store_ready = True
    try:
        saved = await store.async_load()
        if saved is None:
            records = {}
        elif isinstance(saved, dict) and "records" in saved:
            records = saved["records"]
        else:
            raise ValueError("Invalid dispatch ledger")
        if not isinstance(records, dict):
            raise ValueError("Invalid dispatch ledger")
    except Exception:
        # A damaged ledger must never become permission to replay a request.
        store_ready, records = False, {}

    async def save(records):
        if not store_ready:
            raise HomeAssistantError("The dispatch ledger is unavailable")
        await store.async_save({"records": records})

    transport = NativeTransport(hass)
    try:
        broker = AnnouncementBroker(transport.send, transport.resolve, save, records=records, ready=lambda: store_ready)
    except ValueError:
        store_ready = False
        broker = AnnouncementBroker(transport.send, transport.resolve, save, ready=lambda: store_ready)

    async def handle(call):
        operation = call.service.removeprefix("announcement_")
        data = call.data
        try:
            async with asyncio.timeout(5):
                target = await transport.bind(call, control=operation in {"submit", "stop"})
                if operation == "capabilities":
                    return await broker.get_capabilities(target)
                if operation == "status":
                    return await broker.get_status(target, data["request_id"])
                if operation == "stop":
                    return await broker.stop(target, data["request_id"])
                return await broker.submit(target, identity=target.device_id, rid=data["request_id"],
                                           source=data["media_id"], expires_at=data["expires_at"])
        except TimeoutError:
            return capabilities(None) if operation == "capabilities" else failed(data["request_id"], "service_deadline")
        except EndpointUnavailable:
            return capabilities(None) if operation == "capabilities" else failed(data["request_id"], "satellite_unavailable")
        except ValueError as exc:
            raise HomeAssistantError(str(exc)) from exc

    for name, schema in (
        ("submit", SUBMIT), ("status", vol.Schema(REQUEST)),
        ("stop", vol.Schema(REQUEST)), ("capabilities", vol.Schema(TARGET)),
    ):
        hass.services.async_register(DOMAIN, "announcement_" + name, handle, schema=schema,
                                     supports_response=SupportsResponse.ONLY)
    return broker
