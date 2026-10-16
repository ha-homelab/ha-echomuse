"""Shared availability and configuration identity."""
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN


class SettingEntity(CoordinatorEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, entry, key):
        super().__init__(coordinator)
        self.key = key
        self._attr_unique_id = f'{entry.entry_id}_{key}'
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name='Local Russian Speech',
            manufacturer='Silero / IGW', model='v5_6_ru', sw_version='0.1.0')

    @property
    def value(self):
        return self.coordinator.data['settings'][self.key]
