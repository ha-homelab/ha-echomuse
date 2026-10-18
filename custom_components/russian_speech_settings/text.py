"""Optional whole words to emphasize."""
from homeassistant.components.text import TextEntity, TextMode
from .entity import SettingEntity

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([SpeechText(entry.runtime_data, entry, 'emphasis_words')])

class SpeechText(SettingEntity, TextEntity):
    _attr_native_min = 0
    _attr_native_max = 160
    _attr_mode = TextMode.TEXT

    @property
    def native_value(self):
        return self.value

    async def async_set_value(self, value):
        await self.coordinator.async_change({self.key: value})
