# Security and stock recovery

## Assessment: critical exposure on the tested firmware

**Any client that can reach the tested clock's TCP port 1379 can obtain an unauthenticated ADB shell and become root. This is an unacceptable security posture for a consumer device on a trusted home network.** There is no host-key approval prompt protecting this endpoint. Root access permits credential/data theft, software replacement, deletion and disruption of the clock. A compromised clock can also attempt to attack other systems it can reach; root on the clock does not automatically bypass those systems' defenses.

The inspected unit runs Android 8.1 with a reported security patch date of 2020-07-05, a development build and permissive SELinux. These are observations of the tested firmware, not a claim that every unit or later release is identical. There is no evidence here that the clock has already been compromised.

The stock application also contains a separate cloud-triggered support shell. Client-code analysis and a local privilege check establish root-equivalent capability; vendor backend authorization and actual historical use were not audited. **Restricting inbound ADB does not disable an outbound cloud support connection.** Generic HTTPS-only egress does not exclude encrypted WebSockets on port 443.

HACS validation and passing integration tests do not fix these device weaknesses. A safe command inventory constrains this integration's intended behavior; it does not reduce the authority available to another ADB client or a compromised controller.

See the [full sanitized assessment](../SECURITY.md) for finding severity, evidence limits and vendor remediation priorities.

## Required deployment precautions

- **Never expose port 1379 to the internet or untrusted VPN/guest peers.** Remove any forwarding or tunnel that does so.
- Isolate the clock from trusted computers, storage and other appliances. Permit ADB only from Home Assistant and specifically chosen administration hosts. Deny other inbound access and unnecessary clock-initiated lateral connections.
- Apply isolation to IPv4 and IPv6, including globally addressed internal IPv6 networks. Same-subnet traffic can bypass router rules; a VLAN label or DHCP reservation is not a security boundary by itself.
- Verify the policy from both approved and unapproved clients and inspect gateway rule counters. This project has not verified the owner's firewall configuration.
- Forward mDNS only where needed for discovery. Advertisements contain a device identifier; do not publish raw records. Manual setup works without multicast forwarding.
- Decide whether to retain vendor internet access. Blocking it prevents the cloud route but can stop or degrade synchronization, new content and updates. Long-term offline and cold-boot behavior remain unverified. A vendor firmware remedy is needed to remove the underlying privileged support capability while retaining supported cloud operation.

If effective isolation cannot be established, disconnect the clock from the trusted network. Do not assume an unusual port number makes an unauthenticated root service safe.

## What the integration does—and the authority it still holds

Release 0.1.2 executes fixed ADB commands. Ordinary controls send stock remote key events. It directly edits no device files, databases, APKs or firmware, and installs no helper on the clock. The stock app saves its own settings and may synchronize those changes using its existing cloud connection.

Status polling includes four narrowly filtered app-settings reads using stock root access. Favorite confirmation uses a hash calculated on the clock; the favorites list is not downloaded. No Firebase credentials, database contents or media are read by the integration, and no generic shell service or cloud API is exposed. Diagnostic exports use an allowlist and omit addresses, serials, identity hashes, entry IDs, raw responses and favorite hashes. This does not promise that all third-party debug logs are free of sensitive information.

One connection serializes entire control operations against polling. Per-command timeouts, bounded navigation and state confirmation prevent blind command replay. UI output is size-checked, but there is no general transport-output cap or explicit action rate limiter. Physical remote use, a second ADB client and vendor cloud changes can still interfere. Avoid concurrent controllers during menu operations.

Discovery checks reported package presence and a stable identity hash. **Those checks are not cryptographic authentication.** A malicious endpoint can lie about its identity. Trust the network boundary, not the word “verified” in discovery documentation.

The Python dependency is pinned and minimal. Nevertheless, a malicious integration/dependency update or compromised Home Assistant host would inherit access to the clock's root-capable endpoint. Review updates and install only repositories you trust. GitHub/HACS downloads happen during installation and updates; normal device control is local.

## Recovery for 0.1.2 controls

1. Disable the integration and stop other ADB controllers if commands interfere with the clock. No reboot is performed automatically.
2. If automatic-mode navigation stopped, close the settings menu with the physical remote. Start a retry only with the clock awake in Feed and menus closed. A timeout may occur after a setting changed; inspect actual state before retrying.
3. Restore Automatic night mode to the desired Off, Scheduled or Dim room option on the clock. The manual Night mode switch does not disable an automatic rule. Scheduled hours remain configured on the clock.
4. Manual night exit follows the stock sequence and restores maximum brightness. Set a preferred brightness using the remote afterward. This integration does not save and restore the previous brightness level.
5. Favorite is a toggle. If the result is uncertain, inspect the current animation/favorite state before pressing again; an indiscriminate retry can undo a successful first press or affect a different animation. Use the remote to reverse unwanted navigation/favorite changes.
6. For an unresponsive stock app, use the manufacturer's normal restart/power-cycle procedure. Re-enable the integration after the app and network recover; use Reconfigure if the address changed.

Uninstalling the integration closes its connection. It does not restore previous app settings, harden Android, disable ADB or remove the vendor cloud channel. For a software rollback, select a previous HACS release and restart Home Assistant.

## Validation, backups and remaining work

Release 0.1.2 passed 88 automated tests plus Ruff, Hassfest and HACS validation. Live checks confirmed night on/off, automatic-setting changes and favorite toggling, with the initial automatic setting and favorite state restored. Schedule boundaries, ambient-light behavior, real reboot/Wi-Fi recovery and owner-side HACS lifecycle acceptance remain outstanding. None of these checks constitutes a penetration test of the vendor backend or the owner's network.

A private file-level backup of the test clock existed before development. It is **not a bootable disk image**, and full-stock restoration has not been rehearsed. It may contain live credentials, personal data, identifiers and copyrighted media. Keep it private with restrictive access; none of its data or decompiled artifacts belongs in this public repository.

Do not copy app-data files over a running app and call that a safe restore. Firmware changes, ADB authentication changes and SELinux hardening require a separately tested recovery plan. This project has not performed those changes.
