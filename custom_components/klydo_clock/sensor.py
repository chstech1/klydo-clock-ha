"""Read-only software and storage diagnostics."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfInformation
from homeassistant.helpers.entity import EntityCategory

from .const import CONF_DIAGNOSTIC_SENSORS
from .entity import KlydoEntity

DESCRIPTIONS = (
    SensorEntityDescription(
        key="app_version",
        translation_key="app_version",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="free_storage_bytes",
        translation_key="free_storage",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(hass, entry, async_add_entities):
    if entry.options.get(CONF_DIAGNOSTIC_SENSORS, True):
        async_add_entities(KlydoSensor(entry.runtime_data, entry, item) for item in DESCRIPTIONS)


class KlydoSensor(KlydoEntity, SensorEntity):
    @property
    def native_value(self):
        return getattr(self.coordinator.data, self.entity_description.key)
