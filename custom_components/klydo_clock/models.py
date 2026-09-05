"""Immutable device data; independent of Home Assistant."""

from dataclasses import dataclass


@dataclass(frozen=True)
class KlydoState:
    available: bool = True
    app_running: bool | None = None
    app_foreground: bool | None = None
    app_version: str | None = None
    free_storage_bytes: int | None = None
    screen_on: bool | None = None
    brightness: int | None = None


@dataclass(frozen=True)
class KlydoIdentity:
    unique_id: str
    model: str = "Klydo Clock"
