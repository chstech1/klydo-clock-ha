"""Discovery must verify the device, avoid duplicate connections and retain identity."""

from ipaddress import ip_address
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from custom_components.klydo_clock.exceptions import KlydoConnectionError, KlydoUnsupportedError
from custom_components.klydo_clock.models import KlydoIdentity


@pytest.fixture
def discovery():
    return ZeroconfServiceInfo(
        ip_address=ip_address("192.0.2.10"),
        ip_addresses=[ip_address("192.0.2.10")],
        port=1379,
        hostname="Android.local.",
        type="_adb._tcp.local.",
        name="adb-synthetic._adb._tcp.local.",
        properties={},
    )


@pytest.fixture
def probe():
    with patch("custom_components.klydo_clock.config_flow.KlydoClient") as factory:
        client = factory.return_value
        client.identify = AsyncMock(return_value=KlydoIdentity("stable-test-id"))
        client.close = AsyncMock()
        yield client


async def discover(hass, discovery):
    return await hass.config_entries.flow.async_init(
        "klydo_clock",
        context={"source": "zeroconf"},
        data=discovery,
    )


async def test_confirm_verified_discovery(hass, discovery, probe):
    result = await discover(hass, discovery)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    assert not hass.config_entries.async_entries("klydo_clock")
    probe.close.assert_awaited_once()
    with patch("custom_components.klydo_clock.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "stable-test-id"
    assert result["data"] == {"host": "192.0.2.10", "port": 1379}
    assert probe.identify.await_count == 2


@pytest.mark.parametrize("port", [5555, 5556, None])
async def test_other_adb_ports_not_probed(hass, discovery, probe, port):
    discovery.port = port
    assert (await discover(hass, discovery))["reason"] == "not_klydo"
    probe.identify.assert_not_awaited()


@pytest.mark.parametrize("address", ["127.0.0.1", "0.0.0.0", "224.0.0.251", "fe80::1"])
async def test_unusable_address_not_probed(hass, discovery, probe, address):
    discovery.ip_address = ip_address(address)
    assert (await discover(hass, discovery))["reason"] == "invalid_host"
    probe.identify.assert_not_awaited()


@pytest.mark.parametrize("error", [KlydoConnectionError, KlydoUnsupportedError])
async def test_unverified_device_not_offered(hass, discovery, probe, error):
    probe.identify.side_effect = error("private-data")
    result = await discover(hass, discovery)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_verify"
    probe.close.assert_awaited_once()


async def test_existing_address_not_probed(hass, entry, discovery, probe):
    hass.config_entries.async_update_entry(entry, data={"host": "192.0.2.10", "port": 1379})
    assert (await discover(hass, discovery))["reason"] == "already_configured"
    probe.identify.assert_not_awaited()


async def test_verified_address_change_reloads_once(hass, entry, client, discovery, probe):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    with patch.object(hass.config_entries, "async_reload", return_value=True) as reload:
        result = await discover(hass, discovery)
        await hass.async_block_till_done()
        reload.assert_awaited_once_with(entry.entry_id)
    assert result["reason"] == "already_configured"
    assert entry.data["host"] == "192.0.2.10"
    assert entry.unique_id == "stable-test-id"


async def test_different_identity_never_overwrites_existing(hass, entry, discovery, probe):
    probe.identify.return_value = KlydoIdentity("other-clock")
    result = await discover(hass, discovery)
    assert result["step_id"] == "discovery_confirm"
    assert entry.data["host"] == "clock.example"


async def test_repeated_advertisement_no_second_probe(hass, discovery, probe):
    first = await discover(hass, discovery)
    assert first["step_id"] == "discovery_confirm"
    result = await discover(hass, discovery)
    assert result["reason"] == "already_in_progress"
    probe.identify.assert_awaited_once()


async def test_identity_changes_before_confirmation(hass, discovery, probe):
    result = await discover(hass, discovery)
    probe.identify.return_value = KlydoIdentity("changed-clock")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["reason"] == "unique_id_mismatch"
    assert not hass.config_entries.async_entries("klydo_clock")


async def test_unreachable_at_confirmation(hass, discovery, probe):
    result = await discover(hass, discovery)
    probe.identify.side_effect = KlydoConnectionError()
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["reason"] == "cannot_verify"
