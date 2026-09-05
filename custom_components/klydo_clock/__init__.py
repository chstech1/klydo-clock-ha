"""Local Klydo Clock integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from .adb_client import KlydoClient
from .const import CONF_COMMAND_TIMEOUT, DEFAULT_TIMEOUT, PLATFORMS
from .coordinator import KlydoCoordinator
from .exceptions import (
    KlydoAuthenticationError,
    KlydoError,
    KlydoResponseError,
    KlydoUnsupportedError,
)

type KlydoConfigEntry = ConfigEntry[KlydoCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: KlydoConfigEntry) -> bool:
    """Validate identity on each setup so changed addresses cannot control another clock."""
    client = KlydoClient(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.options.get(CONF_COMMAND_TIMEOUT, DEFAULT_TIMEOUT),
    )
    try:
        identity = await client.identify()
        if identity.unique_id != entry.unique_id:
            raise ConfigEntryError(
                "A different device is using this address; reconfigure the clock"
            )
        coordinator = KlydoCoordinator(hass, entry, client)
        await coordinator.async_config_entry_first_refresh()
    except KlydoAuthenticationError, KlydoUnsupportedError, KlydoResponseError:
        await client.close()
        raise ConfigEntryError(
            "Clock identity or ADB authorization could not be verified"
        ) from None
    except KlydoError:
        await client.close()
        raise ConfigEntryNotReady("Unable to connect to the clock") from None
    except BaseException:
        await client.close()
        raise
    entry.runtime_data = coordinator
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await client.close()
        raise
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    async def async_stop(event):
        await client.close()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: KlydoConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: KlydoConfigEntry) -> bool:
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.client.close()
    return unloaded
