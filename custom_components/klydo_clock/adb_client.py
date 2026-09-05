"""Direct asynchronous ADB transport with a fixed command inventory."""

import asyncio
import hashlib
import re
import time
from enum import Enum
from functools import wraps

from adb_shell import exceptions as adb_errors
from adb_shell.adb_device_async import AdbDeviceTcpAsync

from .control_state import parse_clock_ui, parse_control_state
from .exceptions import (
    KlydoAuthenticationError,
    KlydoConnectionError,
    KlydoResponseError,
    KlydoTimeoutError,
    KlydoUnsupportedError,
)
from .models import KlydoIdentity, KlydoState


class Command(Enum):
    """No caller-provided text is ever interpolated into a shell command."""

    IDENTITY = "getprop ro.serialno; getprop ro.boot.serialno; settings get secure android_id"
    PACKAGE = "pm path com.klydoclock"
    VERSION = "dumpsys package com.klydoclock | grep versionName"
    PROCESS = "pidof com.klydoclock"
    FOREGROUND = "dumpsys window windows | grep mCurrentFocus"
    STORAGE = "df -k /data"
    SCREEN = "dumpsys power | grep 'Display Power'"
    BRIGHTNESS = "settings get system screen_brightness"
    NEXT = "input keyevent 22"
    PREVIOUS = "input keyevent 21"
    NIGHT_CYCLE = "input keyevent 42"
    CONFIRM = "input keyevent 66"
    MENU_BACK = "input keyevent 20"
    UI = "uiautomator dump /dev/tty"
    APP_SETTINGS = (
        "su -c 'strings -n 1 /data/data/com.klydoclock/files/datastore/"
        "synced_settings.preferences_pb | grep -A2 -E "
        '"^screenState_value$|^nightMode_value$|^brightness_value$|^mode_value$"' + "'"
    )
    FAVORITES_FINGERPRINT = (
        "su -c 'strings -n 1 /data/data/com.klydoclock/files/datastore/"
        'synced_settings.preferences_pb | grep -A2 "^favorites_value$" | sha256sum' + "'"
    )


def parse_version(output: str) -> str | None:
    match = re.search(r"versionName=([\w.+-]{1,80})(?:\s|$)", output)
    return match[1] if match else None


def parse_process(output: str) -> bool | None:
    if not output.strip():
        return False
    return True if re.fullmatch(r"\d+(?:\s+\d+)*", output.strip()) else None


def parse_foreground(output: str) -> bool | None:
    match = re.search(r"mCurrentFocus=.*?\bu\d+\s+([\w.]+)/", output)
    return match[1] == "com.klydoclock" if match else None


def parse_storage(output: str) -> int | None:
    for line in output.splitlines():
        fields = line.split()
        if len(fields) >= 6 and fields[-1] == "/data":
            try:
                value = int(fields[-3])
            except ValueError:
                return None
            return value * 1024 if value >= 0 else None
    return None


def parse_screen(output: str) -> bool | None:
    match = re.search(r"Display Power: state=(ON|OFF)\b", output)
    return match[1] == "ON" if match else None


def parse_brightness(output: str) -> int | None:
    try:
        value = int(output.strip())
    except ValueError:
        return None
    return value if 0 <= value <= 255 else None


def serialized(method):
    """Keep a whole UI/control operation atomic against other client calls."""

    @wraps(method)
    async def wrapper(self, *args, **kwargs):
        async with self._operation_lock:
            return await method(self, *args, **kwargs)

    return wrapper


class KlydoClient:
    """Serialize entire transactions and reconnect on the next call after failure.

    Commands are never retried automatically: a timed-out key event may already
    have happened. Backoff is bounded at 60 seconds, without sleeping in a lock.
    """

    def __init__(self, host: str, port: int = 1379, timeout: int = 10) -> None:
        self._device = AdbDeviceTcpAsync(host, port, default_transport_timeout_s=timeout)
        self._timeout = timeout
        self._lock = asyncio.Lock()
        self._operation_lock = asyncio.Lock()
        self._connected = False
        self._failures = 0
        self._retry_at = 0.0

    async def _disconnect(self) -> None:
        self._connected = False
        try:
            async with asyncio.timeout(self._timeout):
                await self._device.close()
        except Exception:
            pass

    @serialized
    async def close(self) -> None:
        """Release transport after any active operation finishes."""
        async with self._lock:
            await self._disconnect()

    async def _run(self, commands: tuple[Command, ...]) -> list[str]:
        if any(not isinstance(command, Command) for command in commands):
            raise ValueError("Only fixed Klydo commands are supported")
        async with self._lock:
            if time.monotonic() < self._retry_at:
                raise KlydoConnectionError("Waiting to reconnect")
            try:
                if not self._connected:
                    async with asyncio.timeout(self._timeout):
                        connected = await self._device.connect(
                            transport_timeout_s=self._timeout,
                            auth_timeout_s=self._timeout,
                        )
                    if not connected:
                        raise KlydoConnectionError("Connection failed")
                    self._connected = True
                outputs = []
                for command in commands:
                    async with asyncio.timeout(self._timeout):
                        outputs.append(
                            await self._device.shell(
                                command.value,
                                transport_timeout_s=self._timeout,
                                read_timeout_s=self._timeout,
                                timeout_s=self._timeout,
                            )
                        )
            except asyncio.CancelledError:
                await self._disconnect()
                raise
            except Exception as err:
                await self._disconnect()
                self._failures += 1
                self._retry_at = time.monotonic() + min(2 ** min(self._failures, 6), 60)
                if isinstance(err, adb_errors.DeviceAuthError):
                    raise KlydoAuthenticationError("ADB authorization required") from None
                if isinstance(err, (TimeoutError, adb_errors.AdbTimeoutError)):
                    raise KlydoTimeoutError("ADB request timed out") from None
                raise KlydoConnectionError("ADB request failed") from None
            self._failures = 0
            self._retry_at = 0.0
            return outputs

    @serialized
    async def identify(self) -> KlydoIdentity:
        """Verify the package and hash a stable device ID; never retain raw IDs."""
        package, identity = await self._run((Command.PACKAGE, Command.IDENTITY))
        if not any(line.startswith("package:") for line in package.splitlines()):
            raise KlydoUnsupportedError("Klydo application not installed")
        for value in identity.splitlines():
            value = value.strip()
            if (
                re.fullmatch(r"[A-Za-z0-9._-]{4,128}", value)
                and value.lower() not in {"unknown", "null", "none"}
                and set(value) != {"0"}
            ):
                return KlydoIdentity(hashlib.sha256(value.encode()).hexdigest())
        raise KlydoResponseError("Stable device identifier unavailable")

    @serialized
    async def poll(self) -> KlydoState:
        """Read status and four allowlisted stock-app settings; never export raw data."""
        version, process, foreground, storage, screen, brightness, settings = await self._run(
            (
                Command.VERSION,
                Command.PROCESS,
                Command.FOREGROUND,
                Command.STORAGE,
                Command.SCREEN,
                Command.BRIGHTNESS,
                Command.APP_SETTINGS,
            )
        )
        control = parse_control_state(settings)
        return KlydoState(
            night_mode=control.night_mode,
            night_mode_setting=control.automatic,
            app_screen_state=control.screen,
            app_version=parse_version(version),
            app_running=parse_process(process),
            app_foreground=parse_foreground(foreground),
            free_storage_bytes=parse_storage(storage),
            screen_on=parse_screen(screen),
            brightness=parse_brightness(brightness),
        )

    @serialized
    async def next_animation(self) -> None:
        """Advance once; never retry a possibly delivered input event."""
        (output,) = await self._run((Command.NEXT,))
        if output.strip():
            raise KlydoResponseError("Navigation command was not acknowledged cleanly")

    @serialized
    async def previous_animation(self) -> None:
        """Go back once."""
        (output,) = await self._run((Command.PREVIOUS,))
        if output.strip():
            raise KlydoResponseError("Navigation command was not acknowledged cleanly")

    async def _settings(self):
        (output,) = await self._run((Command.APP_SETTINGS,))
        return parse_control_state(output)

    async def _ui(self):
        (output,) = await self._run((Command.UI,))
        return parse_clock_ui(output)

    async def _key(self, command):
        (output,) = await self._run((command,))
        if output.strip():
            raise KlydoResponseError("Clock key command failed")
        await asyncio.sleep(0.4)

    async def _require_main_screen(self, *, feed_only=False):
        (output,) = await self._run((Command.FOREGROUND,))
        if parse_foreground(output) is not True:
            raise KlydoResponseError("Open the Klydo application first")
        state = await self._settings()
        if state.screen is None:
            raise KlydoResponseError(
                "Stock clock state cannot be read; root read access is required"
            )
        if not (await self._ui()).clear:
            raise KlydoResponseError("Close the clock menu or overlay before using this control")
        if feed_only and (state.mode != "FEED" or state.screen != "DEFAULT"):
            raise KlydoResponseError(
                "Wake the clock and select Feed before changing automatic night mode"
            )
        return state

    @serialized
    async def set_night_mode(self, enabled: bool) -> None:
        """Reach a verified state using at most five stock remote cycle presses."""
        if type(enabled) is not bool:
            raise ValueError("Night mode must be a boolean")
        state = await self._require_main_screen()
        if state.night_mode == enabled:
            return
        for _ in range(5):
            before = state
            await self._key(Command.NIGHT_CYCLE)
            for _ in range(8):
                state = await self._settings()
                if state.screen is not None and (state.screen, state.brightness) != (
                    before.screen,
                    before.brightness,
                ):
                    break
                await asyncio.sleep(0.25)
            else:
                raise KlydoResponseError("The clock did not confirm a night-mode change")
            if state.night_mode == enabled:
                return
        raise KlydoResponseError("The clock did not reach the requested night mode")

    async def _fingerprint(self):
        (output,) = await self._run((Command.FAVORITES_FINGERPRINT,))
        if not re.fullmatch(r"[a-f0-9]{64}\s+-\s*", output.strip()):
            raise KlydoResponseError("Unable to verify favorites")
        fingerprint = output.split()[0]
        if fingerprint == hashlib.sha256(b"").hexdigest():
            raise KlydoResponseError("Unable to read favorites")
        return fingerprint

    @serialized
    async def toggle_favorite(self) -> None:
        """Like the remote heart button; never repeat a possibly delivered press."""
        state = await self._require_main_screen()
        if state.screen != "DEFAULT" or state.mode not in {
            "FEED",
            "FAVORITES",
            "COLLECTIONS",
            "EXPLORE",
        }:
            raise KlydoResponseError(
                "Wake the clock and display a normal animation before favoriting"
            )
        before = await self._fingerprint()
        await self._key(Command.CONFIRM)
        for _ in range(8):
            if await self._fingerprint() != before:
                return
            await asyncio.sleep(0.25)
        raise KlydoResponseError(
            "Favorite did not change; this animation may not support favorites"
        )

    async def _seek_ring(self, target, allowed, direction):
        for _ in range(len(allowed) + 1):
            label = (await self._ui()).ring_label
            if label == target:
                return
            if label not in allowed:
                raise KlydoResponseError("Unexpected clock menu; operation stopped")
            await self._key(direction)
        raise KlydoResponseError("Required clock menu was not found")

    async def _close_control_menu(self):
        for _ in range(7):
            ui = await self._ui()
            if ui.clear:
                return
            if not ui.ring_label and not ui.night_menu:
                raise KlydoResponseError("Unexpected clock screen; close the menu with the remote")
            await self._key(Command.MENU_BACK)
        raise KlydoResponseError("Close the clock menu with the remote")

    @serialized
    async def set_automatic_night_mode(self, mode: str) -> None:
        """Set the stock option through its checked UI, never by file/database writes."""
        if mode not in {"OFF", "SCHEDULE", "AUTO"}:
            raise ValueError("Unsupported automatic night mode")
        state = await self._require_main_screen(feed_only=True)
        if state.automatic is None:
            raise KlydoResponseError("Automatic night-mode setting is unavailable")
        if state.automatic == mode:
            return
        # Menu labels are validated before every navigation/selection. Only the
        # observed English stock UI is supported; different firmware fails closed.
        await self._key(Command.MENU_BACK)
        await self._seek_ring("SETTINGS", {"FEED", "SETTINGS"}, Command.PREVIOUS)
        await self._key(Command.CONFIRM)
        await self._seek_ring(
            "DISPLAY",
            {"CYCLE", "SOUND", "FILTERS", "SYSTEM", "Wi-Fi", "SUPPORT", "TIME", "DISPLAY"},
            Command.PREVIOUS,
        )
        await self._key(Command.CONFIRM)
        await self._seek_ring("NIGHT MODE", {"BRIGHTNESS", "NIGHT MODE"}, Command.NEXT)
        await self._key(Command.CONFIRM)
        for _ in range(3):
            if not (await self._ui()).night_settings:
                raise KlydoResponseError("Unexpected night-mode settings screen; operation stopped")
            before = await self._settings()
            if before.automatic == mode:
                break
            if before.automatic is None or before.screen != "DEFAULT":
                raise KlydoResponseError("Clock state changed; wake the clock and try again")
            await self._key(Command.NEXT)
            for _ in range(8):
                after = await self._settings()
                if after.automatic is not None and after.automatic != before.automatic:
                    break
                await asyncio.sleep(0.25)
            else:
                raise KlydoResponseError("Clock did not confirm automatic night-mode change")
        if (await self._settings()).automatic != mode:
            raise KlydoResponseError("Clock did not reach the requested automatic setting")
        await self._close_control_menu()
