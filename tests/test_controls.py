import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.klydo_clock.adb_client import Command, KlydoClient
from custom_components.klydo_clock.control_state import (
    ClockUI,
    ControlState,
    parse_clock_ui,
    parse_control_state,
)
from custom_components.klydo_clock.exceptions import KlydoResponseError


def test_scalar_state_and_inline_tab():
    state = parse_control_state(
        "screenState_value\r\n*\tNIGHTMODE\r\nscreenState_time\r\n"
        "nightMode_value\n*\nAUTO\nbrightness_value\n*\n4\nmode_value\n*\tFAVORITES\n"
    )
    assert state == ControlState("NIGHTMODE", "AUTO", 4, "FAVORITES")
    assert state.night_mode is True
    assert parse_control_state("screenState_value\n*\nDEFAULT").night_mode is False
    assert parse_control_state("screenState_value\n*\nOFF").night_mode is True


@pytest.mark.parametrize(
    "output",
    [
        "",
        "Permission denied",
        "screenState_value\n*\nNEW",
        "screenState_value\n*\nOFF\nscreenState_value\n*\nDEFAULT",
    ],
)
def test_unknown_state_is_not_off(output):
    assert parse_control_state(output).night_mode is None


def test_ui_parser_rejects_failures():
    for value in [
        "",
        "ERROR: could not get idle state",
        '<?xml version="1.0"?><hierarchy></hierarchy>',
    ]:
        with pytest.raises(KlydoResponseError):
            parse_clock_ui(value)
    clear = parse_clock_ui(
        '<?xml version="1.0"?><hierarchy><node package="com.klydoclock" text="" /></hierarchy>'
    )
    assert clear.clear
    assert ClockUI(("NIGHT MODE",), ("Menu ring indicator",)).ring_label == "NIGHT MODE"
    assert ClockUI(("NIGHT MODE", "DIM ROOM"), ("Back icon", "Left", "Right")).night_settings


@pytest.fixture
def control_client():
    with (
        patch("custom_components.klydo_clock.adb_client.AdbDeviceTcpAsync"),
        patch("custom_components.klydo_clock.adb_client.asyncio.sleep", new_callable=AsyncMock),
    ):
        client = KlydoClient("clock.example")
        client._require_main_screen = AsyncMock(
            return_value=ControlState("DEFAULT", "OFF", 10, "FEED")
        )
        client._key = AsyncMock()
        client._settings = AsyncMock()
        yield client


async def test_night_on_off_confirmed(control_client):
    c = control_client
    c._settings.side_effect = [
        ControlState("DEFAULT", "OFF", 7),
        ControlState("DEFAULT", "OFF", 4),
        ControlState("NIGHTMODE", "OFF", 4),
    ]
    await c.set_night_mode(True)
    assert c._key.await_count == 3
    assert all(call.args == (Command.NIGHT_CYCLE,) for call in c._key.await_args_list)
    c._require_main_screen.return_value = ControlState("NIGHTMODE", "OFF", 4)
    c._settings.side_effect = [ControlState("OFF", "OFF", 4), ControlState("DEFAULT", "OFF", 10)]
    await c.set_night_mode(False)
    assert c._key.await_count == 5


async def test_night_idempotent_and_stalled(control_client):
    c = control_client
    await c.set_night_mode(False)
    c._key.assert_not_awaited()
    c._settings.return_value = c._require_main_screen.return_value
    with pytest.raises(KlydoResponseError, match="did not confirm"):
        await c.set_night_mode(True)
    c._key.assert_awaited_once_with(Command.NIGHT_CYCLE)


async def test_favorite_verification_and_no_replay(control_client):
    c = control_client
    c._fingerprint = AsyncMock(side_effect=["a", "a", "b"])
    await c.toggle_favorite()
    c._key.assert_awaited_once_with(Command.CONFIRM)
    c._key.reset_mock()
    c._fingerprint.side_effect = None
    c._fingerprint.return_value = "a"
    with pytest.raises(KlydoResponseError, match="Favorite did not change"):
        await c.toggle_favorite()
    c._key.assert_awaited_once_with(Command.CONFIRM)


async def test_favorite_rejects_sleep_and_rating(control_client):
    for state in [
        ControlState("OFF", "OFF", 4, "FEED"),
        ControlState("DEFAULT", "OFF", 10, "RATING"),
    ]:
        control_client._require_main_screen.return_value = state
        with pytest.raises(KlydoResponseError, match="normal animation"):
            await control_client.toggle_favorite()
    control_client._key.assert_not_awaited()


async def test_main_screen_guard(control_client):
    c = control_client
    del c._require_main_screen
    c._run = AsyncMock(return_value=["mCurrentFocus=Window{abc u0 com.android.settings/.Main}"])
    with pytest.raises(KlydoResponseError, match="Open the Klydo"):
        await c.set_night_mode(True)
    c._run.return_value = ["mCurrentFocus=Window{abc u0 com.klydoclock/.MainActivity}"]
    c._settings.return_value = ControlState("DEFAULT", "OFF", 10, "FEED")
    c._ui = AsyncMock(return_value=ClockUI(("SETTINGS",), ("Menu ring indicator",)))
    with pytest.raises(KlydoResponseError, match="Close the clock menu"):
        await c.toggle_favorite()
    c._key.assert_not_awaited()


async def test_auto_checked_route(control_client):
    c = control_client

    def ring(label):
        return ClockUI((label,), ("Menu ring indicator",))

    leaf = ClockUI(("NIGHT MODE", "OFF"), ("Back icon", "Left", "Right"))
    c._ui = AsyncMock(
        side_effect=[
            ring("FEED"),
            ring("SETTINGS"),
            ring("CYCLE"),
            ring("DISPLAY"),
            ring("BRIGHTNESS"),
            ring("NIGHT MODE"),
            leaf,
            leaf,
            leaf,
            leaf,
            ring("NIGHT MODE"),
            ring("DISPLAY"),
            ring("SETTINGS"),
            ring("FEED"),
            ClockUI((), ()),
        ]
    )
    c._settings.side_effect = [
        ControlState("DEFAULT", "OFF"),
        ControlState("DEFAULT", "SCHEDULE"),
        ControlState("DEFAULT", "SCHEDULE"),
        ControlState("DEFAULT", "AUTO"),
        ControlState("DEFAULT", "AUTO"),
        ControlState("DEFAULT", "AUTO"),
    ]
    await c.set_automatic_night_mode("AUTO")
    c._require_main_screen.assert_awaited_once_with(feed_only=True)
    assert c._key.await_args_list[0].args == (Command.MENU_BACK,)
    assert c._key.await_args_list[-1].args == (Command.MENU_BACK,)


async def test_auto_unexpected_menu_stops(control_client):
    c = control_client
    c._ui = AsyncMock(return_value=ClockUI(("FACTORY RESET",), ("Menu ring indicator",)))
    with pytest.raises(KlydoResponseError, match="Unexpected clock menu"):
        await c.set_automatic_night_mode("AUTO")
    c._key.assert_awaited_once_with(Command.MENU_BACK)


async def test_multi_step_operation_blocks_poll():
    with patch("custom_components.klydo_clock.adb_client.AdbDeviceTcpAsync"):
        c = KlydoClient("clock.example")
        started, release = asyncio.Event(), asyncio.Event()

        async def main():
            started.set()
            await release.wait()
            return ControlState("DEFAULT", "OFF", 10, "FEED")

        c._require_main_screen = main
        c._run = AsyncMock(return_value=[""] * 7)
        operation = asyncio.create_task(c.set_night_mode(False))
        await started.wait()
        polling = asyncio.create_task(c.poll())
        await asyncio.sleep(0)
        c._run.assert_not_awaited()
        release.set()
        await asyncio.gather(operation, polling)
        c._run.assert_awaited_once()


async def test_fingerprint_rejects_empty_or_failed_read(control_client):
    import hashlib

    c = control_client
    c._run = AsyncMock()
    for output in ["permission denied", hashlib.sha256(b"").hexdigest() + "  -\n"]:
        c._run.return_value = [output]
        with pytest.raises(KlydoResponseError):
            await c._fingerprint()
    c._run.return_value = ["a" * 64 + "  -\r\n"]
    assert await c._fingerprint() == "a" * 64


async def test_menu_cleanup_accepts_inactive_night_leaf(control_client):
    c = control_client
    c._ui = AsyncMock(
        side_effect=[
            ClockUI(
                ("NIGHT MODE", "DIM ROOM"),
                ("Menu indicator icon", "Menu ring indicator", "Back icon"),
            ),
            ClockUI((), ()),
        ]
    )
    await c._close_control_menu()
    c._key.assert_awaited_once_with(Command.MENU_BACK)
