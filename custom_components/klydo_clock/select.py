"""Automatic night mode is independent of the immediate switch."""

from homeassistant.components.select import SelectEntity, SelectEntityDescription

from .entity import KlydoEntity

OPTIONS = {"off": "OFF", "scheduled": "SCHEDULE", "dim_room": "AUTO"}


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        [
            KlydoNightSelect(
                entry.runtime_data,
                entry,
                SelectEntityDescription(
                    key="automatic_night_mode", translation_key="automatic_night_mode"
                ),
            )
        ]
    )


class KlydoNightSelect(KlydoEntity, SelectEntity):
    _attr_options = list(OPTIONS)

    @property
    def available(self):
        return super().available and self.coordinator.data.night_mode_setting in OPTIONS.values()

    @property
    def current_option(self):
        return next(
            (
                key
                for key, value in OPTIONS.items()
                if value == self.coordinator.data.night_mode_setting
            ),
            None,
        )

    async def async_select_option(self, option):
        await self.coordinator.async_command("automatic_night_mode", OPTIONS[option])
