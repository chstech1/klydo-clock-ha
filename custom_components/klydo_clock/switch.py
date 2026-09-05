"""Immediate night-mode control with device-confirmed state."""

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription

from .entity import KlydoEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        [
            KlydoNightSwitch(
                entry.runtime_data,
                entry,
                SwitchEntityDescription(key="night_mode", translation_key="night_mode"),
            )
        ]
    )


class KlydoNightSwitch(KlydoEntity, SwitchEntity):
    @property
    def available(self):
        return super().available and self.coordinator.data.night_mode is not None

    @property
    def is_on(self):
        return self.coordinator.data.night_mode

    async def async_turn_on(self, **kwargs):
        await self.coordinator.async_command("night_mode", True)

    async def async_turn_off(self, **kwargs):
        await self.coordinator.async_command("night_mode", False)
