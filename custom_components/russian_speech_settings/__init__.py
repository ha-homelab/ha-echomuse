"""Controls for the existing local Russian TTS service, alongside Wyoming."""
from datetime import timedelta
import asyncio
import logging

from homeassistant.const import Platform
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import Client, SettingsError, AuthenticationError, connection_options

DOMAIN = 'russian_speech_settings'
PLATFORMS = [Platform.SELECT, Platform.NUMBER, Platform.SWITCH, Platform.TEXT, Platform.BUTTON]


class SettingsCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry, client):
        super().__init__(hass, logging.getLogger(__name__), name=DOMAIN,
                         config_entry=entry, update_interval=timedelta(seconds=30))
        self.client = client
        self.change_lock = asyncio.Lock()

    async def clear_changed_cache(self, data):
        if (self.data and data['settings'] != self.data['settings']
                and self.hass.services.has_service('tts', 'clear_cache')):
            # HA keys cached audio by voice name, which stays "service default".
            await self.hass.services.async_call('tts', 'clear_cache', {}, blocking=True)

    async def _async_update_data(self):
        try:
            async with self.change_lock:
                data = await self.client.request()
                await self.clear_changed_cache(data)
                return data
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed('Speech credential rejected') from err
        except SettingsError as err:
            raise UpdateFailed('Speech settings unavailable') from err

    async def async_change(self, patch):
        try:
            # Only changed keys are sent; two controls cannot overwrite each other.
            async with self.change_lock:
                data = await self.client.request(patch)
                await self.clear_changed_cache(data)
                self.async_set_updated_data(data)
        except SettingsError as err:
            raise HomeAssistantError('Speech setting was not saved') from err


async def async_setup_entry(hass, entry):
    try:
        options = await hass.async_add_executor_job(connection_options, entry.data)
    except (ValueError, OSError):
        from homeassistant.exceptions import ConfigEntryNotReady
        raise ConfigEntryNotReady('Speech TLS configuration unavailable') from None
    coordinator = SettingsCoordinator(hass, entry, Client(async_get_clientsession(hass), options))
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
