# Klydo Clock for Home Assistant

Local control of the stock Klydo Clock over ADB, installable as a HACS custom integration. No separate ADB server, cloud account, MQTT broker, or clock firmware changes are required.

**Critical security exposure:** Any client that can reach the tested stock clock's TCP port **1379** can obtain unauthenticated ADB access and become root. This is an unacceptable production security posture. Isolate the clock from trusted devices, allow ADB only from Home Assistant and designated administrators, and never expose it to the internet. The stock app also has a separate cloud-triggered support shell; blocking inbound ADB does not disable that outbound path. This integration does not fix the clock's security. Read [security and recovery](docs/SECURITY_AND_RECOVERY.md) before deploying it.

For the detailed findings, see the [security assessment](SECURITY.md) and [application architecture and behavior](docs/APP.md). These describe the tested firmware and distinguish observed capabilities from unverified backend behavior.

## Requirements

- Home Assistant **2026.9.0 or newer** (the first tested baseline).
- HACS installed and configured, or use manual installation below.
- A stock Klydo Clock reachable from Home Assistant on its ADB TCP port (normally `1379`).
- The tested device runs Android 8.1 on PX30 hardware with Klydo app `623.3`. Other firmware versions need validation. Authenticated ADB pairing is not supported in this release.

## Install with HACS

[Open this repository in HACS](https://my.home-assistant.io/redirect/hacs_repository/?owner=chstech1&repository=klydo-clock-ha&category=integration)

1. Open **HACS → ⋮ → Custom repositories**.
2. Add `https://github.com/chstech1/klydo-clock-ha` and choose **Integration** as the type.
3. Find **Klydo Clock**, select **Download**, and choose the latest release.
4. Restart Home Assistant.
5. Open **Settings → Devices & services** and accept the **Klydo Clock** discovered card.
6. If no card appears, use **Add integration → Klydo Clock** and enter the clock's hostname or IP address and ADB port (`1379` by default).

Adding a custom repository does not require inclusion in the default HACS catalog. See the [HACS custom repository instructions](https://www.hacs.xyz/docs/faq/custom_repositories/).

## Automatic discovery (0.1.1+)

The tested stock clock advertises `_adb._tcp.local.` through mDNS on port `1379`. The integration listens through Home Assistant's built-in Zeroconf discovery. It only probes matching advertisements on the stock port and verifies the installed Klydo app and stable device identity over ADB before offering a confirmation card. It does not scan network addresses or use the advertised service name as a trusted device ID.

For an already configured clock, an advertisement from a new address is verified over ADB before its saved address is updated. Existing entity IDs stay the same. Repeated advertisements at the configured IP do not open another ADB connection. A DHCP reservation remains useful.

Home Assistant must receive the clock's mDNS traffic and reach its ADB port. Discovery normally works on the same local network; across VLANs, your router may need mDNS forwarding configured, plus the existing restricted HA-to-clock ADB firewall rule. Keep manual setup for networks that block multicast, clocks using a different ADB port, or firmware that advertises differently. The generic Android hostname is not used for DHCP auto-discovery.

Discovery was observed live from the test clock, and the Home Assistant flow is covered by automated tests. Appearance of the card on your particular HA/network installation still needs confirmation. Full details: [discovery evidence](docs/DISCOVERY.md).

## Included controls and sensors

| Entity | Purpose |
| --- | --- |
| Night mode switch | Enter or leave night mode now, with confirmed device state |
| Automatic night mode selector | Off, Scheduled, or Dim room |
| Toggle favorite button | Add/remove the displayed animation from favorites |
| Next animation button | Send the validated next-animation key event |
| Previous animation button | Send the validated previous-animation key event |
| Refresh state button | Read the clock immediately |
| ADB connected binary sensor | Indicate whether the most recent request succeeded |
| Klydo running binary sensor | Report the stock app process |
| Klydo foreground binary sensor | Report whether the stock app owns the focused window |
| App version sensor | Installed stock app version |
| Free storage sensor | Available `/data` storage |

All entities share one device and one serialized ADB connection. Polling defaults to 15 seconds. Failed communication makes device entities unavailable; the ADB connected indicator changes to off. Reconnection uses bounded backoff, and control commands are never automatically replayed after a timeout. Missing/unrecognized state is unknown. Empty `pidof` output means the app is stopped on the validated firmware.

Navigation sends Android directional keys and should be used while the Klydo app is in the foreground. The integration does not launch the app automatically.

Use the integration's **Configure** action to change polling (5–300 seconds), command timeout (2–30 seconds), or whether software/storage diagnostic sensors are loaded. Changes reload the integration. Use **Reconfigure** to change an address without changing entity IDs. A different physical device at the same address is rejected during setup.

## Night mode and favorites (0.1.2+)

**Night mode** is an immediate action, not a schedule toggle. It follows the stock remote's moon-button sequence and confirms the app's actual screen state. Entering night mode takes up to three presses; leaving takes up to two and restores the stock maximum brightness. The dark/off stage counts as night mode on. Allow a few seconds for screen verification and button processing; this is not an instantaneous network switch.

**Automatic night mode** has three options: **Off**, **Scheduled** (the start/end times already saved on the clock), and **Dim room** (the clock's ambient-light behavior). Set scheduled hours on the clock. This option is independent of the immediate switch: an enabled automatic rule can put the clock back into night mode later. Turn automatic mode off to keep manual control. Ambient thresholds and schedule timing remain stock-app behavior.

Changing the automatic option navigates the stock English settings menus, so it can take a minute or more and temporarily shows those menus. Start with the clock awake, showing **Feed**, with all menus closed. Avoid operating the remote during the change. Unsupported menus or missing state stop the operation with an error; close any remaining menu using the remote before retrying.

**Toggle favorite** acts like the remote heart button: it adds or removes the currently displayed animation. Wake the clock and close menus first. The integration verifies that the favorites list changed using a hash calculated on the device; it does not download the list. Animations without favorite support report an error. A toggle is never automatically replayed after a timeout.

No device files, databases, APKs, or firmware are directly edited, and no helper is installed on the clock. The integration reads four selected app settings through stock root access and sends normal remote key events. The stock app saves its own settings and may synchronize them using its existing cloud connection. The integration uses no cloud credentials or cloud APIs. Missing or unrecognized app settings make the affected controls unavailable. State changes made with the remote appear on the next poll.

## Planned features

Current-animation metadata, app launch/stop/restart, media-player controls, display power/brightness, playback modes, and targeted selection are **not implemented in 0.1.2**. They require the validation gates in [the plan](HA_INT_PLAN.md). Android display state and brightness can be read in diagnostics, but their effect on the physical panel has not been established. See [implementation status](docs/IMPLEMENTATION_STATUS.md) for the exact remaining work.

## Update, rollback, remove

Before an update, create a Home Assistant backup. Download the desired release in HACS and restart Home Assistant. To roll back once multiple releases exist, use HACS **Redownload**, choose the prior version, and restart. For manual rollback, replace the integration directory with files from the chosen release and restart. Do not mix files from different versions.

To remove it, delete the Klydo Clock config entry in Devices & services, remove the download in HACS, and restart. This closes the connection and does not modify the stock clock application.

## Manual installation

Download a release's source ZIP. Copy only `custom_components/klydo_clock` into your Home Assistant `config/custom_components/` directory, then restart and add the integration as above. Home Assistant installs the pinned Python dependency automatically. The root of this repository is not the directory to copy into `custom_components`.

## Troubleshooting

- **Cannot connect:** check the address, port, Wi-Fi, and firewall from the Home Assistant host. Reserve the clock's address in DHCP. Avoid simultaneously using the general Android Debug Bridge integration or another active ADB client; multi-client behavior is unverified.
- **Authorization required:** this release supports the tested unauthenticated stock endpoint only. Do not disable authentication on another device to use it.
- **Unknown values:** the app/Android output may differ. Download integration diagnostics; do not attach raw ADB logs or private app data to public issues.
- **Buttons do nothing:** check the running/foreground sensors. ADB key events have no application-level acknowledgment. Keep the stock app open.
- **Disconnected after reboot:** leave the integration enabled; it polls again and reconnects when the clock becomes reachable. Recovery across a real reboot is still an acceptance test.
- **Not listed after installing:** restart Home Assistant, then search in Add integration. Check the minimum HA version and exact directory layout.

## Development

```sh
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -r requirements-dev.txt
.venv/bin/ruff check custom_components tests scripts
.venv/bin/pytest
```

Tests run with sockets disabled and use synthetic/sanitized fixtures. To run the read-only physical soak test from a trusted administration machine:

```sh
.venv/bin/python scripts/check_clock.py CLOCK_HOST --polls 100 --interval 5
```

The client can also run without Home Assistant; this script only needs `adb-shell[async]==0.4.4`. It prints counts, not device identifiers. It does not reboot or change the clock.

GitHub Actions runs tests, Ruff, Hassfest, and HACS validation on pushes and pull requests. Runtime files live entirely in `custom_components/klydo_clock`. Original local brand artwork is included for modern Home Assistant; the HACS legacy CDN-brand check is skipped for this custom repository. Upstream catalog submission is outside this release.

This is an independent community integration, not affiliated with or endorsed by Klydo.
