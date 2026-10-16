"""Russian pronunciation preprocessing controls."""
from homeassistant.components.switch import SwitchEntity
from .entity import SettingEntity

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    async_add_entities([SpeechSwitch(coordinator, entry, key)
                        for key in ('auto_stress', 'auto_yo')])

class SpeechSwitch(SettingEntity, SwitchEntity):
    @property
    def is_on(self):
        return self.value

    async def async_turn_on(self, **kwargs):
        await self.coordinator.async_change({self.key: True})

    async def async_turn_off(self, **kwargs):
        await self.coordinator.async_change({self.key: False})
