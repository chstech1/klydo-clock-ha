"""One comparable snapshot shared by all entities."""

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .adb_client import KlydoClient
from .const import CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL, DOMAIN
from .exceptions import KlydoError
from .models import KlydoState

LOGGER = logging.getLogger(__name__)


class KlydoCoordinator(DataUpdateCoordinator[KlydoState]):
    """Poll state; the standard HA coordinator manages unavailable/recovery."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: KlydoClient):
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
            ),
            always_update=False,
        )
        self.client = client

    async def _async_update_data(self) -> KlydoState:
        try:
            return await self.client.poll()
        except KlydoError:
            raise UpdateFailed("Unable to communicate with the clock") from None

    async def async_command(self, key: str) -> None:
        actions = {
            "next_animation": self.client.next_animation,
            "previous_animation": self.client.previous_animation,
        }
        try:
            await actions[key]()
        except KlydoError:
            self.async_set_update_error(UpdateFailed("Clock command failed"))
            raise HomeAssistantError("Unable to communicate with the clock") from None
        await self.async_refresh()
