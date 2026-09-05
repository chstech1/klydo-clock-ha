> Published planning reference. The example address is sanitized. See docs/IMPLEMENTATION_STATUS.md for actual completion status.

# Klydo Clock Home Assistant ADB Integration Plan

Status: Draft 0.2
Last updated: 2026-09-04
Proposed integration domain: `klydo_clock`

## 1. Purpose

Create a Home Assistant custom integration, installable through HACS, that controls and monitors the existing Klydo Clock application over the local network using Android Debug Bridge (ADB).

This plan covers only the stock Klydo application and ADB control.

## 2. Scope

### In scope

- Local ADB connection from Home Assistant to the clock.
- UI-based configuration through a Home Assistant config flow.
- Automatic reconnect after network interruptions and clock reboots.
- Next and previous animation controls.
- Display power and brightness controls after validation.
- Klydo night-mode control after its state and setter are identified.
- Klydo application start, stop, and restart controls.
- Current animation, application, display, connection, and storage status.
- Selection of a specific animation or playback mode if a reliable ADB-accessible mechanism is found.
- Home Assistant entities, diagnostics, tests, HACS packaging, and documentation.

### Out of scope

- Klydo cloud API or Firebase access.
- Cloud-content downloading or archival.
- Uploading or registering custom animations.
- Editing the Klydo SQLite database.
- MQTT.
- A replacement clock application.
- Home Assistant overlays on the clock.
- Disabling or modifying the installed Klydo APK.
- A generic user-accessible ADB shell action.

These topics can receive separate plans later without expanding this integration's initial scope.

## 3. Confirmed test-device facts

The following has been observed on the current test clock:

| Item | Observed value |
|---|---|
| Device address | `192.0.2.10` |
| ADB TCP port | `1379` |
| Android version | 8.1 |
| Hardware | Rockchip PX30 |
| Klydo package | `com.klydoclock` |
| Display resolution | 1080 x 1920 |
| Klydo APK version | 623.3 |
| Next animation | Android key event `22` |
| Previous animation | Android key event `21` |

Key events 22 and 21 were tested against the physical clock. The current animation ID changed and then returned as expected.

The current ADB endpoint provides unauthenticated root access. That makes integration development straightforward but creates a significant network-security requirement.

## 4. Design principles

- All normal operation must remain local; internet access is not required by the integration.
- Use the least invasive ADB command that accomplishes each operation.
- Prefer Android intents, key events, and read-only state queries over database access.
- Expose only allowlisted commands, never arbitrary shell text.
- Do not represent a command as a stateful Home Assistant control until its actual state can be read reliably.
- Unknown values remain unknown; the integration must not guess state.
- Keep the ADB transport separate from Home Assistant entity classes so it can be tested independently.
- Treat the physical clock as the authority for state.

## 5. Architecture

```text
Home Assistant
  custom_components/klydo_clock
      |
      +-- Config flow and options
      +-- DataUpdateCoordinator
      +-- Home Assistant entities
      +-- Klydo ADB client
                |
                +---- ADB/TCP port 1379 ---- Klydo Clock
```

### 5.1 ADB client

Use a pure-Python ADB implementation by default so users do not need to operate a separate ADB server. The known device does not currently require an ADB key, but the client design should not prevent adding authenticated ADB support later.

The client is responsible for:

- Connecting and disconnecting.
- Reusing a healthy connection.
- Serializing commands with one asynchronous lock.
- Applying command and connection timeouts.
- Reconnecting after socket failure.
- Running allowlisted shell commands and key events.
- Parsing command output into typed state.
- Translating transport failures into integration-specific exceptions.

Home Assistant's official Android Debug Bridge integration also uses a pure-Python implementation and recommends it before using a separate ADB server. We should follow the same general deployment model while implementing Klydo-specific state and controls.

### 5.2 Coordinator

Use one `DataUpdateCoordinator` per configured clock. It should collect all inexpensive state in one update operation and distribute the result to every entity.

Initial polling interval: 15 seconds. Make this configurable within safe bounds, such as 5–300 seconds.

Use `always_update=False` with an immutable, comparable state object to avoid unnecessary Home Assistant state writes.

### 5.3 State model

```python
@dataclass(frozen=True)
class KlydoState:
    available: bool
    screen_on: bool | None
    app_running: bool | None
    app_foreground: bool | None
    current_animation_id: str | None
    current_animation_name: str | None
    current_artist: str | None
    night_mode: bool | None
    brightness: int | None
    free_storage_bytes: int | None
    app_version: str | None
```

State polling must not perform complete filesystem scans or retrieve video files.

## 6. Proposed entities

Only implement an entity when its underlying state or command has been validated.

### 6.1 Initial entities

| Platform | Entity | Behavior |
|---|---|---|
| `button` | Next animation | Send tested key event 22 |
| `button` | Previous animation | Send tested key event 21 |
| `button` | Restart Klydo | Force-stop and relaunch `com.klydoclock` |
| `binary_sensor` | ADB connected | Report control-channel availability |
| `binary_sensor` | Klydo running | Report whether the package process is running |
| `binary_sensor` | Klydo foreground | Report whether Klydo owns the foreground window |
| `sensor` | Current animation | Report ID, with name and artist as attributes when available |
| `sensor` | App version | Report the installed Klydo version |
| `sensor` | Free storage | Report available clock storage |

### 6.2 Entities requiring further validation

| Platform | Entity | Required discovery |
|---|---|---|
| `media_player` | Klydo Clock | Reliable display state, next/previous, turn-on, and turn-off behavior |
| `switch` | Night mode | Reliable getter and reversible setter |
| `light` | Display | Panel power and brightness behavior, including scale and persistence |
| `select` | Playback mode | Safe method for changing Klydo mode |
| `select` | Animation | Safe targeted-selection mechanism and catalog query |

Buttons can be command-only. Switches, lights, and selects require reliable state feedback and must not be optimistic unless explicitly documented.

## 7. Proposed actions

Prefer standard entity actions such as `button.press`, `media_player.media_next_track`, `light.turn_on`, and `switch.turn_on` whenever possible.

Klydo-specific actions may include:

- `klydo_clock.restart_app`
- `klydo_clock.refresh_state`
- `klydo_clock.select_animation` — deferred pending validation.
- `klydo_clock.set_playback_mode` — deferred pending validation.

No action may accept arbitrary shell text. Animation IDs and other parameters must be validated against strict character and length rules before use.

## 8. ADB command inventory

### 8.1 Confirmed commands

| Operation | Command behavior | Status |
|---|---|---|
| Next animation | `input keyevent 22` | Confirmed |
| Previous animation | `input keyevent 21` | Confirmed |

### 8.2 Read-only queries to validate

- Android build and serial properties.
- Installed version of `com.klydoclock`.
- Klydo process ID.
- Foreground application/window.
- Display power and interactive state.
- System brightness value.
- Available storage.
- Current animation ID and metadata.
- Current Klydo night-mode value.
- Current Klydo playback mode.

Every parser should be developed from sanitized fixtures and handle missing or unexpected output without raising uncaught exceptions.

### 8.3 Reversible commands to validate

- Launch `com.klydoclock` using its launcher activity or a package-level monkey command.
- Force-stop `com.klydoclock`.
- Restart `com.klydoclock`.
- Wake the display.
- Turn off or suspend the display.
- Set display brightness.
- Enable and disable night mode.
- Change playback mode.
- Select a specific animation.

Application restart should be disabled by default or presented as a diagnostic entity if routine use would be disruptive.

## 9. Configuration flow

### 9.1 User configuration

Request:

- Hostname or IP address.
- ADB port, default `1379`.

During validation:

1. Open an ADB connection with a short timeout.
2. Read basic Android properties.
3. Confirm that `com.klydoclock` is installed.
4. Obtain a stable device identifier.
5. Reject duplicate entries for the same clock.
6. Create the config entry using a friendly title.

Do not include serial numbers or command output in user-facing errors.

### 9.2 Options flow

- Poll interval.
- Command timeout.
- Enable application restart control.
- Enable diagnostic sensors.
- Power-control method after multiple methods have been tested.

Changing options should reload the config entry without requiring a Home Assistant restart.

### 9.3 Discovery

Automatic discovery is optional and should not delay the first release. Port scanning the user's network is undesirable. If a reliable Klydo-specific mDNS, SSDP, DHCP, or hostname signature is found, add targeted discovery later.

## 10. Entity and device identity

Create one Home Assistant device per physical clock.

Device information should include:

- Manufacturer: Klydo.
- Model: Klydo Clock, refined if a reliable model property exists.
- Software version: installed Klydo APK version.
- Configuration URL: omitted unless the clock exposes a legitimate local UI.
- Stable identifier: a hashed or appropriately stored device-specific identifier.

Do not use the IP address as the permanent unique identifier because it may change.

Entity unique IDs should be derived from the stable device identifier and an entity suffix, not from entity names.

## 11. Connection handling

- All blocking ADB work must run outside Home Assistant's event loop.
- Serialize ADB operations with one asynchronous lock per device.
- Use explicit connection and shell-command timeouts.
- Reconnect with bounded exponential backoff after transport failure.
- Mark entities unavailable after coordinator refresh failure.
- Request an immediate refresh after a successful command.
- Close the ADB socket when unloading the config entry or stopping Home Assistant.
- Recover automatically when the clock reboots.
- Never automatically reboot or restart the clock in response to a failed poll.
- Avoid simultaneous control by this integration and Home Assistant's general Android Debug Bridge integration unless multi-client behavior is proven reliable.

Suggested exception categories:

- `KlydoConnectionError`
- `KlydoTimeoutError`
- `KlydoAuthenticationError`
- `KlydoUnsupportedError`
- `KlydoResponseError`

## 12. Security requirements

The clock's current ADB endpoint exposes unauthenticated root control. Before regular integration use:

- Place the clock on a trusted IoT VLAN.
- Permit TCP port `1379` only from Home Assistant and designated administration hosts.
- Block access to port `1379` from ordinary client devices and guest networks.
- Never forward port `1379` through the router.
- Do not expose it through a reverse proxy, VPN port-forward, or cloud tunnel without strong access controls.
- Do not provide arbitrary ADB command execution through the integration.
- Redact the device serial and sensitive command output from logs and diagnostics.
- Do not read or export Firebase credentials.

The integration documentation must prominently explain this exposure. A Home Assistant repair warning may be added when unauthenticated ADB is detected, although the integration cannot reliably determine the clock's VLAN or firewall policy.

## 13. Repository structure

```text
HA_INT_PLAN.md
README.md
LICENSE
hacs.json
custom_components/
  klydo_clock/
    __init__.py
    manifest.json
    const.py
    config_flow.py
    coordinator.py
    entity.py
    adb_client.py
    models.py
    exceptions.py
    button.py
    binary_sensor.py
    sensor.py
    media_player.py
    switch.py
    light.py
    select.py
    diagnostics.py
    services.yaml
    strings.json
    translations/
      en.json
tests/
  components/
    klydo_clock/
      conftest.py
      fixtures/
      test_adb_client.py
      test_config_flow.py
      test_coordinator.py
      test_entities.py
      test_diagnostics.py
```

Only platform files actually implemented should be included in a release.

## 14. Manifest and HACS requirements

Planned `manifest.json` values:

- `domain`: `klydo_clock`
- `name`: `Klydo Clock`
- `config_flow`: `true`
- `integration_type`: `device`
- `iot_class`: `local_polling`
- Semantic `version`
- Documentation URL.
- Issue tracker URL.
- Code owner list.
- A pinned and reviewed Python ADB dependency.

HACS repository requirements:

- Exactly one integration below `custom_components/`.
- All runtime files inside `custom_components/klydo_clock/`.
- Root-level `hacs.json`.
- HACS validation workflow.
- Hassfest workflow.
- GitHub releases for versioned installation and rollback.

Begin as a HACS custom repository. Submission to the default HACS catalog is not required for initial testing.

## 15. Implementation phases

### Phase 0 — Safety and command inventory

- Restrict network access to ADB port `1379`.
- Preserve the current APK and application backup.
- Record confirmed read-only queries and reversible commands.
- Create sanitized output fixtures.

Exit criteria:

- A documented stock recovery procedure exists.
- No credential or serial data is present in fixtures.
- ADB is not reachable from untrusted networks.

### Phase 1 — Standalone ADB client

- Implement connect, execute, key-event, timeout, close, and reconnect operations.
- Implement typed queries for package, process, foreground app, display, and storage state.
- Add next and previous commands.
- Test outside Home Assistant against the physical clock.

Exit criteria:

- 100 consecutive state polls without hanging or leaking connections.
- Next/previous commands produce the expected animation changes.
- The client reconnects after a clock reboot.

### Phase 2 — Home Assistant MVP

- Add manifest, config flow, coordinator, translations, and device registration.
- Add next, previous, ADB connectivity, process, version, and storage entities.
- Add diagnostics with redaction.
- Add unit and mocked Home Assistant tests.

Exit criteria:

- Installation through a HACS custom repository succeeds.
- Setup, reload, disable, delete, and re-add work correctly.
- Duplicate entries are prevented.
- Temporary disconnection results in unavailable entities and later recovery.

### Phase 3 — Current animation and media player

- Establish a reliable, read-only current-animation query.
- Add animation name and artist when safely available.
- Implement a `media_player` entity with only confirmed supported features.
- Add app launch, stop, and optional restart.

Exit criteria:

- Home Assistant observes animation changes made from both HA and the physical controls.
- The media-player state is correct after app restart and clock reboot.

### Phase 4 — Night mode, display power, and brightness

- Trace the stock app's night-mode state and setter.
- Test wake, sleep, screen-off, and brightness commands.
- Confirm persistence and interaction with Klydo's own scheduling.
- Add `switch.night_mode` and `light.display` only after reliable state feedback exists.

Exit criteria:

- Every operation is reversible.
- Reported state matches the physical display.
- The controls remain correct across app and device restarts.

### Phase 5 — Playback mode and targeted animation selection

- Identify an intent, broadcast, command executor, or other safe ADB-accessible selection method.
- Add playback-mode selection.
- Add targeted animation selection only without database editing.
- Add media browsing if a stable catalog can be queried read-only.

Exit criteria:

- Invalid or deleted IDs fail safely.
- Selection does not corrupt feeds, settings, or the database.
- Catalog retrieval does not block Home Assistant's event loop.

### Phase 6 — HACS release hardening

- Complete documentation and troubleshooting guidance.
- Add GitHub Actions for HACS validation, Hassfest, linting, and tests.
- Exercise installation and upgrade from a tagged release.
- Test rollback to the previous release.

Exit criteria:

- No known secret leakage.
- No generic shell execution path.
- Reconnect and unavailable behavior are reliable.
- Release installation and rollback are documented.

## 16. Test strategy

### Unit tests

- ADB response parsing from sanitized fixtures.
- Command allowlisting and argument validation.
- Connection timeout and reconnect behavior.
- Immutable state comparison.
- Config-flow validation and duplicate handling.
- Entity availability and supported features.
- Diagnostics redaction.
- Config-entry version migration.

### Home Assistant tests

- Successful setup, unload, reload, and removal.
- First-refresh failure and later recovery.
- Concurrent entity commands are serialized.
- Successful commands request an immediate coordinator refresh.
- Options changes reload the entry correctly.
- Device and entity identifiers stay stable after IP changes.

### Physical clock tests

Run in increasing order of risk:

1. Read Android and package properties.
2. Read process, foreground app, screen, version, and storage state.
3. Send next and previous key events.
4. Stop and relaunch only the Klydo application.
5. Reboot the clock manually and test reconnection.
6. Test display wake and screen-off behavior.
7. Test brightness at safe middle values before minimum or maximum.
8. Test night mode and verify it physically.
9. Test playback-mode selection.
10. Test targeted animation selection.

### Failure scenarios

- Home Assistant restarts while the clock is running.
- The clock restarts while Home Assistant is running.
- Clock IP address changes.
- Wi-Fi disconnects and reconnects.
- Klydo app is stopped or crashes.
- Another ADB client owns the connection.
- A command times out after partially completing.
- Command output changes after an APK update.
- Storage is nearly full.

## 17. Safety gates

| Gate | Permitted work | Requirement to advance |
|---|---|---|
| A | Read-only ADB queries | Stable connection and sanitized output |
| B | Tested navigation key events | Observable and reversible behavior |
| C | App stop/start and display controls | Documented recovery behavior |
| D | Night mode and playback settings | Reliable getter plus reversible setter |
| E | Targeted animation selection | No database editing or feed corruption |

No milestone implicitly authorizes bypassing a safety gate.

## 18. Release outline

### `0.1.0` — ADB MVP

- UI setup.
- Connection health.
- Next and previous buttons.
- Klydo running/foreground state.
- App version and free-storage sensors.
- Automatic reconnect and redacted diagnostics.

### `0.2.0` — Media state

- Current animation information.
- Klydo `media_player` entity.
- App launch, stop, and restart controls.

### `0.3.0` — Display controls

- Night mode after validation.
- Display power and brightness after validation.

### `0.4.0` — Selection controls

- Playback-mode selection.
- Specific animation selection.
- Optional read-only media browsing.

### `1.0.0` — Stable release

- Proven reconnect and upgrade behavior.
- Complete tests, documentation, translations, and diagnostics.
- Confirmed compatibility with the supported Klydo APK/device versions.

## 19. Open questions

- Where is night-mode state stored, and what is the least invasive ADB setter?
- Does changing night mode locally cause a Klydo cloud writeback?
- Which command controls the physical panel rather than only Android's interactive state?
- Does system brightness directly control the panel, and what range is safe?
- What is the safest source for the current animation ID?
- Can a specific animation be selected through an Android intent or existing Klydo command executor?
- Can playback mode be changed without editing SQLite?
- Does ADB port `1379` accept multiple clients reliably?
- Which property provides a stable identifier across clock and APK reboots?
- Does a future Klydo APK update change the tested navigation behavior?

## 20. Immediate next steps

1. Restrict TCP port `1379` to Home Assistant and approved administration hosts.
2. Create a sanitized inventory of read-only ADB state commands.
3. Confirm reliable queries for app process, foreground state, display state, and current animation.
4. Trace night mode while observing only reversible changes.
5. Scaffold `custom_components/klydo_clock` and its tests.
6. Implement the standalone ADB client before adding entity platforms.

## 21. References

- [Home Assistant: Integration manifest](https://developers.home-assistant.io/docs/creating_integration_manifest/)
- [Home Assistant: Config flow](https://developers.home-assistant.io/docs/core/integration/config_flow/)
- [Home Assistant: Fetching data and DataUpdateCoordinator](https://developers.home-assistant.io/docs/integration_fetching_data/)
- [Home Assistant: Media player entity](https://developers.home-assistant.io/docs/core/entity/media-player/)
- [Home Assistant: Android Debug Bridge integration](https://www.home-assistant.io/integrations/androidtv/)
- [HACS: Custom integration requirements](https://hacs.xyz/docs/publish/integration/)
