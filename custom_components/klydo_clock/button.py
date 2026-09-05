"""Validated next and previous controls."""

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.helpers.entity import EntityCategory

from .entity import KlydoEntity

DESCRIPTIONS = (
    ButtonEntityDescription(key="toggle_favorite", translation_key="toggle_favorite"),
    ButtonEntityDescription(key="next_animation", translation_key="next_animation"),
    ButtonEntityDescription(key="previous_animation", translation_key="previous_animation"),
    ButtonEntityDescription(
        key="refresh_state",
        translation_key="refresh_state",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(KlydoButton(entry.runtime_data, entry, item) for item in DESCRIPTIONS)


class KlydoButton(KlydoEntity, ButtonEntity):
    async def async_press(self) -> None:
        if self.entity_description.key == "refresh_state":
            await self.coordinator.async_refresh()
        else:
            await self.coordinator.async_command(self.entity_description.key)
