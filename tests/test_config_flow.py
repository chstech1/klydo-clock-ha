from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
from homeassistant.data_entry_flow import FlowResultType

from custom_components.klydo_clock.config_flow import valid_host
from custom_components.klydo_clock.exceptions import (
    KlydoAuthenticationError,
    KlydoConnectionError,
    KlydoResponseError,
    KlydoUnsupportedError,
)
from custom_components.klydo_clock.models import KlydoIdentity


@pytest.fixture
def flow_client():
    with patch("custom_components.klydo_clock.config_flow.KlydoClient") as factory:
        client = factory.return_value
        client.identify = AsyncMock(return_value=KlydoIdentity("stable-test-id"))
        client.close = AsyncMock()
        yield client


async def test_user_flow(hass, flow_client):
    result = await hass.config_entries.flow.async_init("klydo_clock", context={"source": "user"})
    assert result["type"] is FlowResultType.FORM
    with patch("custom_components.klydo_clock.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "Clock.Example", "port": 1379}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["host"] == "clock.example"
    assert result["result"].unique_id == "stable-test-id"
    flow_client.close.assert_awaited_once()


async def test_duplicate(hass, entry, flow_client):
    result = await hass.config_entries.flow.async_init(
        "klydo_clock", context={"source": "user"}, data={"host": "other.example", "port": 1379}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("error", "key"),
    [
        (KlydoConnectionError, "cannot_connect"),
        (KlydoAuthenticationError, "invalid_auth"),
        (KlydoUnsupportedError, "not_klydo"),
        (KlydoResponseError, "missing_identity"),
    ],
)
async def test_errors(hass, flow_client, error, key):
    flow_client.identify.side_effect = error("private-data")
    result = await hass.config_entries.flow.async_init(
        "klydo_clock", context={"source": "user"}, data={"host": "clock.example", "port": 1379}
    )
    assert result["errors"] == {"base": key}
    flow_client.close.assert_awaited_once()


async def test_reconfigure_preserves_identity(hass, entry, flow_client):
    with patch.object(hass.config_entries, "async_reload", return_value=True):
        result = await hass.config_entries.flow.async_init(
            "klydo_clock",
            context={"source": "reconfigure", "entry_id": entry.entry_id},
            data={"host": "new.example", "port": 1379},
        )
        await hass.async_block_till_done()
    assert result["reason"] == "reconfigure_successful"
    assert entry.data["host"] == "new.example"
    assert entry.unique_id == "stable-test-id"


async def test_reconfigure_wrong_device(hass, entry, flow_client):
    flow_client.identify.return_value = KlydoIdentity("different-device")
    result = await hass.config_entries.flow.async_init(
        "klydo_clock",
        context={"source": "reconfigure", "entry_id": entry.entry_id},
        data={"host": "new.example", "port": 1379},
    )
    assert result["reason"] == "unique_id_mismatch"
    assert entry.data["host"] == "clock.example"


async def test_options(hass, entry):
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"poll_interval": 30, "command_timeout": 5, "diagnostic_sensors": False}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["poll_interval"] == 30


@pytest.mark.parametrize(
    "value", ["https://clock.example", "host;reboot", "host:1379", "a b", "-bad", ""]
)
def test_bad_host(value):
    with pytest.raises(vol.Invalid):
        valid_host(value)


@pytest.mark.parametrize("value", ["clock.example", "192.0.2.1", "2001:db8::1"])
def test_good_host(value):
    assert valid_host(value) == value
