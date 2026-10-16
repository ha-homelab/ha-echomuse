"""Reset voice and prosody to the documented service defaults."""
from homeassistant.components.button import ButtonEntity
from .entity import SettingEntity

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([ResetSettings(entry.runtime_data, entry, 'reset')])

class ResetSettings(SettingEntity, ButtonEntity):
    async def async_press(self):
        await self.coordinator.async_change(self.coordinator.data['defaults'])
