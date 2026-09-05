from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.klydo_clock.diagnostics import async_get_config_entry_diagnostics
from custom_components.klydo_clock.exceptions import KlydoConnectionError
from custom_components.klydo_clock.models import KlydoIdentity


async def setup(hass, entry):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_setup_entities_commands_unload(hass, entry, client):
    await setup(hass, entry)
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("binary_sensor.klydo_clock_klydo_running").state == "on"
    assert hass.states.get("binary_sensor.klydo_clock_adb_connected").state == "on"
    assert hass.states.get("sensor.klydo_clock_app_version").state == "623.3"
    before = client.poll.await_count
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.klydo_clock_next_animation"}, blocking=True
    )
    client.next_animation.assert_awaited_once()
    assert client.poll.await_count == before + 1
    assert await hass.config_entries.async_unload(entry.entry_id)
    client.close.assert_awaited_once()


async def test_failure_recovery_and_diagnostics(hass, entry, client):
    await setup(hass, entry)
    client.poll.side_effect = KlydoConnectionError("private output")
    await entry.runtime_data.async_refresh()
    assert hass.states.get("binary_sensor.klydo_clock_klydo_running").state == "unavailable"
    assert hass.states.get("binary_sensor.klydo_clock_adb_connected").state == "off"
    client.poll.side_effect = None
    await entry.runtime_data.async_refresh()
    assert hass.states.get("binary_sensor.klydo_clock_klydo_running").state == "on"
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert "clock.example" not in str(diag)
    assert "stable-test-id" not in str(diag)
    assert "623.3" not in str(diag)
    assert diag["state"]["app_running"] is True


async def test_first_refresh_failure_closes(hass, entry, client):
    client.poll.side_effect = KlydoConnectionError("private")
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    client.close.assert_awaited_once()


async def test_wrong_device_rejected(hass, entry, client):
    client.identify.return_value = KlydoIdentity("different-device")
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    client.poll.assert_not_awaited()
    client.close.assert_awaited_once()


async def test_command_failure_marks_unavailable(hass, entry, client):
    await setup(hass, entry)
    client.next_animation.side_effect = KlydoConnectionError("private")
    with pytest.raises(HomeAssistantError, match="Unable to communicate"):
        await entry.runtime_data.async_command("next_animation")
    assert not entry.runtime_data.last_update_success


async def test_options_reload_and_diagnostic_disable(hass, entry, client):
    await setup(hass, entry)
    with patch.object(hass.config_entries, "async_reload", return_value=True) as reload:
        hass.config_entries.async_update_entry(entry, options={"poll_interval": 30})
        await hass.async_block_till_done()
        reload.assert_awaited_once_with(entry.entry_id)
    await hass.config_entries.async_unload(entry.entry_id)
    hass.config_entries.async_update_entry(entry, options={"diagnostic_sensors": False})
    await setup(hass, entry)
    assert hass.states.get("sensor.klydo_clock_app_version").state == "unavailable"


async def test_coordinator_comparable_data(hass, entry, client):
    await setup(hass, entry)
    coordinator = entry.runtime_data
    assert not coordinator.always_update
    assert await coordinator._async_update_data() == coordinator.data
    client.poll.side_effect = KlydoConnectionError()
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_shutdown_closes_socket(hass, entry, client):
    from homeassistant.const import EVENT_HOMEASSISTANT_STOP

    await setup(hass, entry)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    client.close.assert_awaited_once()


async def test_refresh_button(hass, entry, client):
    await setup(hass, entry)
    before = client.poll.await_count
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.klydo_clock_refresh_state"}, blocking=True
    )
    assert client.poll.await_count == before + 1
