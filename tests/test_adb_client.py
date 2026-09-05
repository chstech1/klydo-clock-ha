import asyncio
import hashlib
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from adb_shell.exceptions import DeviceAuthError

from custom_components.klydo_clock.adb_client import (
    KlydoClient,
    parse_brightness,
    parse_foreground,
    parse_process,
    parse_screen,
    parse_storage,
    parse_version,
)
from custom_components.klydo_clock.exceptions import (
    KlydoAuthenticationError,
    KlydoConnectionError,
    KlydoResponseError,
    KlydoTimeoutError,
    KlydoUnsupportedError,
)


def test_sanitized_fixture():
    fixture = json.loads((Path(__file__).parent / "fixtures/state.json").read_text())
    assert parse_version(fixture["version"]) == "623.3"
    assert parse_process(fixture["process"]) is True
    assert parse_foreground(fixture["foreground"]) is True
    assert parse_storage(fixture["storage"]) == 21520360 * 1024
    assert parse_screen(fixture["screen"]) is True
    assert parse_brightness(fixture["brightness"]) == 255


@pytest.mark.parametrize(
    "parser", [parse_brightness, parse_foreground, parse_screen, parse_storage, parse_version]
)
@pytest.mark.parametrize("output", ["", "unexpected response", "null"])
def test_unknown_output(parser, output):
    assert parser(output) is None


def test_process_and_foreground():
    assert parse_process("") is False
    assert parse_process("permission denied") is None
    assert parse_foreground("mCurrentFocus=Window{abc u0 com.android.settings/.Main}") is False
    assert parse_foreground("mCurrentFocus=null") is None
    assert parse_brightness("-1") is None
    assert parse_brightness("256") is None
    assert parse_storage("/dev/example 100 10 -1 10% /data") is None


@pytest.fixture
def transport():
    with patch("custom_components.klydo_clock.adb_client.AdbDeviceTcpAsync") as factory:
        instance = factory.return_value
        instance.connect = AsyncMock(return_value=True)
        instance.close = AsyncMock()
        instance.shell = AsyncMock(return_value="")
        yield instance


async def test_identity_hashed_and_missing(transport):
    client = KlydoClient("clock.example")
    transport.shell.side_effect = ["package:/data/app/example/base.apk", "SERIALTEST123\n"]
    assert (await client.identify()).unique_id == hashlib.sha256(b"SERIALTEST123").hexdigest()
    transport.shell.side_effect = ["package:/example", "unknown\nnull\n000000\n"]
    with pytest.raises(KlydoResponseError):
        await client.identify()
    transport.shell.side_effect = ["", "SERIALTEST123"]
    with pytest.raises(KlydoUnsupportedError):
        await client.identify()


async def test_connection_reused_and_commands_allowlisted(transport):
    client = KlydoClient("clock.example")
    await client.next_animation()
    await client.previous_animation()
    transport.connect.assert_awaited_once()
    assert [call.args[0] for call in transport.shell.await_args_list] == [
        "input keyevent 22",
        "input keyevent 21",
    ]
    with pytest.raises(ValueError):
        await client._run(("reboot",))
    await client.close()
    transport.close.assert_awaited_once()


async def test_failure_backoff_reconnect_no_command_replay(transport):
    client = KlydoClient("clock.example")
    transport.shell.side_effect = OSError("sensitive address")
    with patch("custom_components.klydo_clock.adb_client.time.monotonic", return_value=100):
        with pytest.raises(KlydoConnectionError, match="^ADB request failed$"):
            await client.next_animation()
        with pytest.raises(KlydoConnectionError, match="Waiting"):
            await client.next_animation()
    transport.shell.assert_awaited_once()
    transport.shell.side_effect = None
    with patch("custom_components.klydo_clock.adb_client.time.monotonic", return_value=200):
        await client.previous_animation()
    assert transport.connect.await_count == 2


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (TimeoutError(), KlydoTimeoutError),
        (DeviceAuthError("authorization required"), KlydoAuthenticationError),
    ],
)
async def test_errors_sanitized_and_closed(transport, failure, expected):
    transport.connect.side_effect = failure
    with pytest.raises(expected):
        await KlydoClient("clock.example").poll()
    transport.close.assert_awaited_once()


async def test_serializes_transactions(transport):
    active = 0
    maximum = 0

    async def shell(*args, **kwargs):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0)
        active -= 1
        return ""

    transport.shell.side_effect = shell
    client = KlydoClient("clock.example")
    await asyncio.gather(client.poll(), client.next_animation(), client.previous_animation())
    assert maximum == 1
    assert len(transport.shell.await_args_list) == 8


async def test_cancel_closes_transport(transport):
    transport.shell.side_effect = asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        await KlydoClient("clock.example").poll()
    transport.close.assert_awaited_once()


async def test_command_output_error_is_not_success(transport):
    transport.shell.return_value = "Error: permission denied"
    with pytest.raises(KlydoResponseError):
        await KlydoClient("clock.example").next_animation()
    transport.shell.assert_awaited_once()


async def test_real_async_deadline_cancels_stalled_shell(transport):
    async def stalled(*args, **kwargs):
        await asyncio.Event().wait()

    transport.shell.side_effect = stalled
    with pytest.raises(KlydoTimeoutError):
        await KlydoClient("clock.example", timeout=0.01).poll()
    transport.close.assert_awaited_once()


async def test_false_handshake_is_failure(transport):
    transport.connect.return_value = False
    with pytest.raises(KlydoConnectionError):
        await KlydoClient("clock.example").poll()
    transport.shell.assert_not_awaited()
    transport.close.assert_awaited_once()
