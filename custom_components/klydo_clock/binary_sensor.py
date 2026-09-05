"""Connection and stock application state."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.helpers.entity import EntityCategory

from .entity import KlydoEntity

DESCRIPTIONS = (
    BinarySensorEntityDescription(
        key="connected",
        translation_key="connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BinarySensorEntityDescription(key="app_running", translation_key="app_running"),
    BinarySensorEntityDescription(key="app_foreground", translation_key="app_foreground"),
)


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(KlydoBinarySensor(entry.runtime_data, entry, item) for item in DESCRIPTIONS)


class KlydoBinarySensor(KlydoEntity, BinarySensorEntity):
    @property
    def available(self) -> bool:
        # Keep the connection indicator readable when the other entities go unavailable.
        return self.entity_description.key == "connected" or super().available

    @property
    def is_on(self) -> bool | None:
        if self.entity_description.key == "connected":
            return self.coordinator.last_update_success
        return getattr(self.coordinator.data, self.entity_description.key)
