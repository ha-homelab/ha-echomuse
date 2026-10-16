"""Constrained prosody values."""
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.exceptions import HomeAssistantError
from .entity import SettingEntity

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    async_add_entities([SpeechNumber(coordinator, entry, key)
                        for key in ('rate', 'pitch', 'sentence_pause_ms', 'emphasis_intensity')])

class SpeechNumber(SettingEntity, NumberEntity):
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, entry, key):
        super().__init__(coordinator, entry, key)
        schema = coordinator.data['schema'][key]
        self._attr_native_min_value = schema['min']
        self._attr_native_max_value = schema['max']
        self._attr_native_step = schema['step']
        self._attr_native_unit_of_measurement = schema.get('unit')

    @property
    def native_value(self):
        return self.value

    async def async_set_native_value(self, value):
        if not float(value).is_integer():
            raise HomeAssistantError('Use a whole number')
        await self.coordinator.async_change({self.key: int(value)})
