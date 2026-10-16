"""Voice and intonation selectors."""
from homeassistant.components.select import SelectEntity
from .entity import SettingEntity

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    async_add_entities([SpeechSelect(coordinator, entry, key)
                        for key in ('voice', 'intonation')])

class SpeechSelect(SettingEntity, SelectEntity):
    @property
    def options(self):
        return self.coordinator.data['schema'][self.key]['options']

    @property
    def current_option(self):
        return self.value

    async def async_select_option(self, option):
        await self.coordinator.async_change({self.key: option})
