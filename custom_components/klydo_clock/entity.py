"""Common stable identity and device information."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import KlydoCoordinator


class KlydoEntity(CoordinatorEntity[KlydoCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, description):
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)},
            manufacturer="Klydo",
            model="Klydo Clock",
            name=entry.title,
            sw_version=coordinator.data.app_version,
        )
