"""Direct asynchronous ADB transport with a fixed command inventory."""

import asyncio
import hashlib
import re
import time
from enum import Enum

from adb_shell import exceptions as adb_errors
from adb_shell.adb_device_async import AdbDeviceTcpAsync

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


class KlydoClient:
    """Serialize entire transactions and reconnect on the next call after failure.

    Commands are never retried automatically: a timed-out key event may already
    have happened. Backoff is bounded at 60 seconds, without sleeping in a lock.
    """

    def __init__(self, host: str, port: int = 1379, timeout: int = 10) -> None:
        self._device = AdbDeviceTcpAsync(host, port, default_transport_timeout_s=timeout)
        self._timeout = timeout
        self._lock = asyncio.Lock()
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

    async def poll(self) -> KlydoState:
        """Read bounded, inexpensive state without accessing private app data."""
        version, process, foreground, storage, screen, brightness = await self._run(
            (
                Command.VERSION,
                Command.PROCESS,
                Command.FOREGROUND,
                Command.STORAGE,
                Command.SCREEN,
                Command.BRIGHTNESS,
            )
        )
        return KlydoState(
            app_version=parse_version(version),
            app_running=parse_process(process),
            app_foreground=parse_foreground(foreground),
            free_storage_bytes=parse_storage(storage),
            screen_on=parse_screen(screen),
            brightness=parse_brightness(brightness),
        )

    async def next_animation(self) -> None:
        """Advance once; never retry a possibly delivered input event."""
        (output,) = await self._run((Command.NEXT,))
        if output.strip():
            raise KlydoResponseError("Navigation command was not acknowledged cleanly")

    async def previous_animation(self) -> None:
        """Go back once."""
        (output,) = await self._run((Command.PREVIOUS,))
        if output.strip():
            raise KlydoResponseError("Navigation command was not acknowledged cleanly")
