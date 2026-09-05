# Implementation and acceptance status

Release scope: **0.1.2 — ADB controls, night mode, favorites and verified mDNS discovery**. This is the first installment of the supplied plan, not completion of every phase. The repository is separate from the private reverse-engineering workspace and backup.

## Implemented

- Pure-Python asynchronous ADB transport pinned to `adb-shell[async]==0.4.4`, with serialized transactions, timeouts, cancellation cleanup, bounded reconnect backoff and no automatic command replay.
- Verified package presence and hashed stable identity; no IP-based permanent IDs.
- User/config/options/reconfigure flows, duplicate rejection and device-mismatch protection during setup.
- Coordinator with immutable comparable state, unavailable/recovery behavior, immediate refresh after commands, unload and shutdown cleanup.
- Next/previous/refresh buttons, connectivity/running/foreground sensors, app-version and free-storage sensors.
- Explicitly allowlisted diagnostics, translated entity names, local icon artwork.
- HACS layout and metadata, Hassfest/HACS/test/lint workflows, installation/recovery/update/rollback documentation.
- Synthetic/sanitized parser fixtures and Home Assistant integration tests with network sockets disabled.

## Device evidence

Read-only ADB queries succeeded on the available stock Android 8.1/PX30 clock running Klydo `623.3`: package version, process, focused window, `/data` storage, Android display-power state and system brightness. Next/previous key events were already physically verified in the source plan. No new display, app-stop, night-mode, playback, database or cloud changes were performed for the 0.1.0/0.1.1 releases.

Local validation for 0.1.1: 70 automated tests passed with 96% coverage; Ruff passed; the 0.1.0 baseline passed Hassfest, and GitHub Actions validates each update. The physical clock completed 100 consecutive read-only polls at five-second intervals and an explicit close/reconnect/identify/poll check. A separate final-client check verified the corrected storage parser against the device. Explicit disconnect/reconnect tests do not substitute for testing an actual device reboot or Wi-Fi outage.

## Acceptance work still required

| Plan phase | Remaining acceptance or discovery |
| --- | --- |
| 0 | Owner verification of VLAN/firewall isolation from untrusted networks; manufacturer/full-stock restoration has not been rehearsed |
| 1 | Real clock reboot and Wi-Fi interruption recovery; physical next/previous retest on the installation target |
| 2 | Install via HACS on the owner's actual Home Assistant instance; exercise disable/delete/re-add there |
| 3 | Establish a reliable bounded current-animation getter and metadata source; validate launch/stop/restart and media-player semantics |
| 4 | Verify independent panel power/brightness controls; extended night scheduling and ambient-light behavior acceptance |
| 5 | Identify safe playback/targeted-selection methods without SQLite edits; validate invalid/deleted IDs and bounded catalog retrieval |
| 6 | Actual HACS update/rollback on the owner installation |

No placeholder `media_player` or `light` platform is shipped. Switch and select platforms expose the validated stock night controls. Restart is not exposed until its recovery/validation gate is satisfied. No generic shell action or speculative setter is included. The independent backup stays private and untouched.

## Environment

Automated tests use Python 3.14 and Home Assistant 2026.9.0 with `pytest-homeassistant-custom-component==0.13.363`. The initial HACS minimum is the tested HA version. Supporting older HA releases requires a compatibility test run before lowering it.

## Publishing status

The public HACS package uses versioned GitHub releases. GitHub authorization includes the required `workflow` scope, and `.github/workflows/validate.yaml` is uploaded. Tests, Ruff, Hassfest, and HACS validation run on pushes and pull requests. Check the repository Actions tab for the latest results.

## Discovery update (0.1.1)

Live unicast DNS-SD and multicast browsing both confirmed the stock `_adb._tcp.local.` service on port 1379. ADB service identity is verified before discovery confirmation or existing-entry address updates. The clock has a generic Android hostname and no distinctive `net.hostname`, so no DHCP hostname/vendor matcher was added. See `DISCOVERY.md` for sanitized evidence and network limitations.


## Controls update (0.1.2)

Night mode uses a bounded stock moon-button sequence with state confirmation after each step. Automatic night settings use verified English menu labels. Favorite toggles are checked against an on-device hash, with no automatic key replay. Tests cover parser failures, inline protobuf length markers, state availability, guarded menu navigation, no-op/idempotent requests, serialized multi-step operations and Home Assistant services.

Only selected app state is read; there are no direct clock file/database edits, APK replacements or installed helpers. Manual exit restores the stock maximum brightness. Automatic scheduling/dim-room behavior remains independent of manual state. Full ambient-light and scheduled-boundary acceptance remains to be observed on the installation target.
