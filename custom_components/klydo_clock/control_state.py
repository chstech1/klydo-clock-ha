"""Strict parsers for selected stock-app settings and accessibility state."""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from .exceptions import KlydoResponseError


@dataclass(frozen=True)
class ControlState:
    screen: str | None = None
    automatic: str | None = None
    brightness: int | None = None
    mode: str | None = None

    @property
    def night_mode(self) -> bool | None:
        if self.screen is None:
            return None
        return self.screen in {"NIGHTMODE", "OFF"}


def parse_control_state(output: str) -> ControlState:
    """Read only exact key / protobuf-string marker / scalar triples.

    Android strings separates the non-printable protobuf lengths; the command
    filters four known scalar entries on-device. Missing/malformed fields stay
    unknown; old SharedPreferences and Android brightness are not substitutes.
    """
    lines = [line.strip() for line in output.splitlines()]
    values = {}
    for key in ("screenState_value", "nightMode_value", "brightness_value", "mode_value"):
        indexes = [i for i, line in enumerate(lines) if line == key]
        if len(indexes) != 1:
            continue
        i = indexes[0]
        if i + 1 < len(lines):
            marker = lines[i + 1]
            if marker == "*" and i + 2 < len(lines):
                values[key] = lines[i + 2]
            elif marker.startswith("*\t"):
                values[key] = marker[2:]
    screen = values.get("screenState_value")
    automatic = values.get("nightMode_value")
    brightness = values.get("brightness_value", "")
    mode = values.get("mode_value")
    return ControlState(
        screen=screen if screen in {"DEFAULT", "NIGHTMODE", "OFF"} else None,
        automatic=automatic if automatic in {"OFF", "SCHEDULE", "AUTO"} else None,
        brightness=int(brightness) if re.fullmatch(r"(?:[0-9]|10)", brightness) else None,
        mode=mode if mode in {"FEED", "FAVORITES", "COLLECTIONS", "EXPLORE", "RATING"} else None,
    )


@dataclass(frozen=True)
class ClockUI:
    texts: tuple[str, ...]
    descriptions: tuple[str, ...]

    @property
    def clear(self) -> bool:
        return not self.texts and not self.descriptions

    @property
    def ring_label(self) -> str | None:
        if (
            len(self.texts) == 1
            and "Menu ring indicator" in self.descriptions
            and "Back icon" not in self.descriptions
        ):
            return self.texts[0]
        return None

    @property
    def night_settings(self) -> bool:
        return self.night_menu and "Left" in self.descriptions and "Right" in self.descriptions

    @property
    def night_menu(self) -> bool:
        """The leaf remains visible after Back hides its editing arrows."""
        return (
            "NIGHT MODE" in self.texts
            and "Back icon" in self.descriptions
            and any(value in self.texts for value in ("OFF", "SCHEDULE", "DIM ROOM"))
        )


def parse_clock_ui(output: str) -> ClockUI:
    """Never accept a failed/truncated UI dump as an empty clock screen."""
    start = output.find("<?xml")
    end = output.rfind("</hierarchy>")
    if start < 0 or end < start or len(output) > 131072:
        raise KlydoResponseError("Unable to verify the clock screen")
    document = output[start : end + len("</hierarchy>")]
    if "<!DOCTYPE" in document or "<!ENTITY" in document:
        raise KlydoResponseError("Unable to verify the clock screen")
    try:
        root = ET.fromstring(document)
    except ET.ParseError:
        raise KlydoResponseError("Unable to verify the clock screen") from None
    nodes = list(root.iter("node"))
    if not nodes or not any(node.get("package") == "com.klydoclock" for node in nodes):
        raise KlydoResponseError("Open the Klydo application first")
    return ClockUI(
        texts=tuple(" ".join(node.get("text", "").split()) for node in nodes if node.get("text")),
        descriptions=tuple(node.get("content-desc") for node in nodes if node.get("content-desc")),
    )
