"""Explicit allowlist prevents exporting addresses, identifiers or raw responses."""


async def async_get_config_entry_diagnostics(hass, entry):
    coordinator = entry.runtime_data
    state = coordinator.data
    return {
        "integration_version": "0.1.0",
        "connected": coordinator.last_update_success,
        "poll_interval": coordinator.update_interval.total_seconds(),
        "state": {
            "app_running": state.app_running,
            "app_foreground": state.app_foreground,
            "free_storage_bytes": state.free_storage_bytes,
            "screen_on": state.screen_on,
            "brightness": state.brightness,
        },
    }
