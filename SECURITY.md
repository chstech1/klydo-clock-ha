# Klydo Clock Security Assessment

Status: Working assessment 1.2  
Initial assessment: 2026-09-04  
Last updated: 2026-09-05 (UTC)  
Device under test: owner-authorized Klydo Clock on a private LAN  
Stock application: `com.klydoclock` version 623.3  
Stock updater: `klydo.clock.updator` version 25

## 1. Executive summary

**The tested firmware has critical security failures and should be treated as an untrusted appliance. It is not suitable for an unrestricted network shared with personal computers, storage or other trusted systems. Shipping a consumer device with unauthenticated network access to root is an unacceptable production security posture.** This judgment applies to the inspected unit and firmware; it is not a claim about every Klydo product or evidence of a past compromise.

The most serious condition is an ADB daemon listening on TCP port 1379 on all interfaces with Android host authentication disabled. Any machine that can reach that port can obtain an ADB shell without approving an RSA key on the clock. That shell can invoke the installed `su` binary and become root. The clock is also a `userdebug`/`test-keys` Android 8.1 build, is patched only through 2020-07-05, and runs SELinux in permissive mode.

The stock Klydo application has a separate vendor support command plane. After automatic Firebase authentication, it watches a Firestore command collection. Available commands include an interactive shell, interactive SQL queries, Room database export, logcat streaming, crash/log uploads, application updates, and deletion of content. The interactive shell executes unrestricted received text through `sh -c` as Android system UID 1000. A controlled test confirmed that UID 1000 can invoke the installed `su` binary and become UID 0 on this firmware. Compromise or misuse of the device account, Firebase rules, or the vendor control plane would therefore provide root-equivalent remote command execution and data-exfiltration capability on the clock.

This does not mean the clock can automatically execute commands on every other device. It does mean code running as root on the clock can probe and connect to systems the clock can reach, making the clock a potential internal-network foothold. No local log or cached Firestore evidence of an actual `streamAdbShell` session was found, but commands are deleted after processing and relevant history may not be retained locally, so absence of evidence is not proof that the feature has never been used.

The released [Home Assistant integration, v0.1.2](https://github.com/chstech1/klydo-clock-ha/releases/tag/v0.1.2), uses this existing ADB endpoint. It installs nothing on the clock and directly edits no device files. **HACS compatibility, passing tests and fixed integration commands are not security remediation for the clock.** The daemon still accepts other clients with full authority, and the stock cloud channel remains active.

If TCP 1379 is reachable from an untrusted network, close that path now. A DHCP reservation provides a stable address; it supplies no access control. A VLAN name alone supplies no isolation. Require tested firewall rules, restrict ADB to explicitly approved controllers, and block clock-initiated access to trusted systems over both IPv4 and IPv6. If adequate isolation cannot be established, disconnect the clock from that network.

Blocking inbound ADB does not disable the outbound cloud shell. Generic “HTTPS only” egress is also insufficient: a support channel can use encrypted WebSockets over port 443. Removing internet access blocks this cloud route but can break stock content and synchronization; long-term offline behavior has not been established.

## 2. Scope and confidence labels

This assessment is based on:

- Read-only live ADB inspection of the test clock.
- Android package-manager, process, property, and listener information.
- Static analysis of the installed Klydo 623.3 APK and updater 25 APK with JADX.
- Inspection of the extracted application data, Room database, external media, and manifests.
- Controlled functional testing of next/previous, night on/off, automatic night options and favorite toggling, plus a controlled test of whether UID 1000 can invoke `su`. Normal app settings may be saved by the app during key-event tests; this is distinct from directly editing device files.

The following labels are used:

- **Confirmed** — directly observed on the device or in executable code.
- **Design risk** — the capability is confirmed, but exploitation depends on another principal or trust boundary.
- **Potential** — plausible from the configuration, but not demonstrated.
- **Not assessed** — the necessary server, source, key, hardware, or policy was not available.

This was not a destructive penetration test. Firebase/Firestore security rules, Klydo server authorization, TLS server configuration, signing-key custody, bootloader state, hardware attacks, and Bluetooth protocol security were not audited. “No issue found” should not be inferred for those areas.

## 3. Severity summary

| ID | Severity | Finding | Status |
|---|---:|---|---|
| KLY-01 | Critical | Network ADB requires no host authorization and leads to root | Confirmed |
| KLY-02 | Critical | Firebase command plane includes a root-equivalent interactive shell | Confirmed capability / command-origin authorization not assessed |
| KLY-03 | High | Pre-provisioned device credentials are deterministically derived from the serial number | Confirmed client behavior and provisioning sequence |
| KLY-04 | High | Development build, permissive SELinux, old Android patch level | Confirmed |
| KLY-05 | High | Klydo and updater run as the Android system shared UID | Confirmed |
| KLY-06 | High | Cloud commands can export/query the database and stream logs | Confirmed capability / design risk |
| KLY-07 | High | App and BLE-firmware update chains have privileged installation and weak app-layer validation | Confirmed, with qualifications |
| KLY-08 | High | The local device dump contains live authentication and private application data | Confirmed |
| KLY-09 | Medium | Unprotected exported components permit reboot/relaunch/update-trigger behavior | Confirmed code path |
| KLY-10 | Medium | External media and update staging are broadly writable and cleanup is destructive | Confirmed / design risk |
| KLY-11 | Medium | Support WebSockets accept arbitrary destinations and plaintext `ws://` | Confirmed capability / design risk |
| KLY-12 | Medium | Backup is enabled without explicit exclusions for sensitive state | Confirmed configuration / potential exposure |
| KLY-13 | Medium | Extensive telemetry and diagnostic upload surface | Confirmed capability / privacy risk |
| KLY-14 | Medium | Vendor cloud can alter settings, hide/delete content, and initiate updates | Confirmed client capability / server authority not assessed |
| KLY-15 | Medium | Vendor-cloud failure or policy change is a single point of availability/control failure | Architecture risk |
| HA-01 | High | A generic Home Assistant ADB shell action would create command injection/root risk | Integration design risk |
| HA-02 | Medium | HACS and dependency supply-chain compromise would inherit ADB authority | Integration design risk |
| HA-03 | Medium | Poor diagnostics, logging, or entity permissions could leak data or enable abuse | Integration design risk |

Severity represents the tested configuration. Network isolation can reduce reachability but does not remove the underlying condition.

### 3.1 Practical risk by deployment

The cloud shell's impact is **Critical** because successful use yields root-equivalent control of the clock. Its practical likelihood depends on Klydo's unpublished Firestore rules, vendor access controls, and whether the device credentials can be obtained or guessed. Those server-side controls were not available for audit, so a reliable probability cannot be assigned.

| Deployment condition | Practical assessment |
|---|---|
| Clock has internet access and shares a flat LAN with computers, storage, cameras, or other trusted devices | **High to Critical.** Either unauthenticated ADB from the LAN or misuse of the outbound cloud shell can provide a root foothold with lateral-network reachability. |
| Clock has internet access but is isolated on an IoT VLAN; inbound ADB is allowlisted and clock-to-private-network traffic is denied | **Low to Medium risk to the rest of the network; High risk to the clock and data on it.** Cloud control still exists, but segmentation materially limits pivoting. |
| Clock has no internet access and ADB 1379 is restricted to one trusted controller/admin host | **Low external-remote risk, with residual local, physical, old-firmware, and controller-compromise risk.** Klydo cloud features will stop or degrade. |
| TCP 1379 is reachable from the public internet, untrusted VPN peers, or broadly routed guest/IoT networks | **Critical and urgent.** Unauthenticated ADB provides a direct root path without depending on the vendor cloud. |

An inbound firewall rule on TCP 1379 addresses KLY-01 but does not stop KLY-02: the cloud support channel is an outbound connection initiated by the clock. Mitigating both requires egress/lateral filtering or removal of the cloud command feature.

## 4. Detailed findings

### KLY-01 — Unauthenticated network ADB can become root

**Severity:** Critical  
**Status:** Confirmed

The device listens on `:::1379`, which makes ADB reachable over IPv4/IPv6 interfaces allowed by the network. The relevant device properties and observations were:

```text
ro.adb.secure=0
ro.debuggable=1
ro.secure=1
shell uid=2000(shell)
/system/xbin/su mode 0755, owner root
su -c id -> uid=0(root)
```

No device-side RSA authorization prompt was required. A client with LAN reachability obtained the shell immediately, and the shell successfully invoked `su` to reach root. AOSP's normal ADB authorization protocol uses a challenge signed by an approved host key; Android's user-facing documentation describes the confirmation dialog as the protection preventing unapproved ADB commands. The tested configuration disables that protection. See the [ADB protocol authentication description](https://android.googlesource.com/platform/packages/modules/adb/+/1a0fb8846d4e6b671c8aa7f137a8c21d7b248716/protocol.txt) and [Android ADB documentation](https://developer.android.com/tools/adb).

**Impact**

- Read, modify, or delete essentially all clock data.
- Extract Firebase tokens, device identifiers, Wi-Fi configuration, logs, and media.
- Install or replace software, alter system settings, stop the display app, or reboot the clock.
- Persist code or use the clock as a pivot point toward other reachable LAN systems.
- Disable or falsify behavior expected by Home Assistant.

**Mitigation**

1. Immediately firewall TCP 1379 so only the Home Assistant IP and a designated admin workstation can reach it.
2. Put the clock on an IoT VLAN with no unsolicited access to trusted clients and no lateral access to other IoT devices.
3. Never port-forward, tunnel, or publish port 1379 to the internet.
4. Give the clock a DHCP reservation and use explicit source/destination rules rather than a broad subnet allow rule.
5. Longer term, replace the firmware configuration with authenticated ADB (`ro.adb.secure=1`), a production `user` build, or a narrow local control service. Test recovery access before changing firmware.

Network filtering is the only low-risk mitigation available without altering the clock. It should be complete before deploying the HACS integration.

### KLY-02 — Vendor command plane exposes an interactive system shell

**Severity:** Critical  
**Status:** Confirmed capability; who is authorized to originate commands is not assessed

After Firebase authentication, `CommandManager` watches:

```text
machines/<firebase-user-id>/commands
```

The `streamAdbShell` executor accepts a first parameter beginning with `ws://` or `wss://`, opens that WebSocket, and passes every received text message to:

```text
sh -c <received text>
```

It returns stdout, stderr, and the exit code. The app process runs as UID 1000 (`system`) in the `system_app` SELinux domain. This is not Android's network ADB daemon despite the class name; it is a separate cloud-triggered shell built into the application.

The shell session has a 30-second per-command timeout and a two-minute inactivity timeout. Those timeouts limit accidental hangs but do not constrain command content or filesystem/network authority.

**Impact**

Compromise or misuse of any principal able to place a valid Firestore command could result in root-equivalent arbitrary command execution. A controlled test started a shell as UID 1000—the Klydo application's Linux identity—and then invoked `/system/xbin/su 0 id`; the result was UID 0. This confirms that the app identity can cross the final boundary to root on the tested permissive firmware. The test did not send a real Firestore shell command and is not evidence that the vendor has exercised the capability.

Root on the clock permits file and credential access, persistence, application replacement, traffic observation available to the device, and arbitrary outbound network connections. It creates a beachhead for scanning or attacking reachable internal systems, but does not by itself bypass authentication or vulnerabilities on those other systems.

**Mitigation**

- Vendor fix: remove the shell executor from production builds.
- If remote support is required, replace it with signed, single-purpose operations, explicit authorization, audit trails, endpoint allowlisting, and an on-device owner approval/expiry mechanism.
- Block unknown outbound WebSocket destinations and plaintext WebSockets at the network gateway where practical.
- Deny the clock access to trusted/private subnets—including IPv6 unique-local ranges—except for narrowly required controller, DHCP, DNS, and NTP flows.
- Removing internet access from the stock clock prevents this cloud path but also disables normal Klydo synchronization, settings sync, and updates.

### KLY-03 — Predictable device cloud credentials

**Severity:** High  
**Status:** Confirmed client algorithm and pre-provisioning sequence; server rate limits and Firestore rules not assessed

The user does not create a normal Klydo login. The application creates a device identity from the hardware serial:

```text
email    = lowercase(serial) + "@clocks.com"
password = lowercase hexadecimal MD5(lowercase(serial))
```

It uses those values with Firebase email/password authentication. Firebase returns an ID token and refresh token; the API client sends the ID token as a Bearer token and adds the serial in `X-Klydo-Serial`.

The password is a deterministic transform of an identifier, not an independent secret. MD5 is not the central issue here: any public, unsalted transform is reproducible once the serial is known or guessed.

No Firebase account-creation call or create-account fallback was found in the installed APK; it directly calls `signInWithEmailAndPassword`. Persisted account and package metadata on the tested unit show:

| Event | Timestamp |
|---|---|
| Firebase device identity created | Before recorded app installation |
| Main APK first installed, according to this Android installation | After device identity provisioning |
| First sign-in retained in the inspected Firebase metadata | After recorded app installation |

The Firebase identity existed about 83 days before the retained sign-in and roughly ten weeks before the recorded app installation. This strongly supports Klydo pre-provisioning the identity before customer setup, likely during manufacturing, inventory, or another batch process. The device cannot reveal which of those stages created it, and re-imaging can reset Android package timestamps. The later `registerProduct` state/UI is separate from Firebase identity creation.

**Impact**

If a device serial is exposed and the backend accepts this derivation without another control, an attacker may be able to impersonate that clock account. Factory, inventory, or backend systems involved in pre-provisioning can also reconstruct or know the account mapping. Successful impersonation could expose cloud data or, depending on Firestore rules, reach the command plane described in KLY-02 and KLY-06.

**Mitigation**

- Vendor fix: provision a unique high-entropy secret or asymmetric device key during manufacturing; support rotation and revocation.
- Enforce server-side device attestation or a second device-bound credential rather than trusting a serial-derived password.
- Rate-limit authentication and monitor duplicate/geographically implausible device sessions.
- Treat the clock serial as sensitive until the backend design is corrected.
- Do not copy the serial-derived credential into Home Assistant; the ADB-only integration does not need it.

No serial, derived password, Firebase token, or user ID is recorded in this document.

### KLY-04 — Production device uses a weak development security posture

**Severity:** High  
**Status:** Confirmed

Observed device state:

```text
Android release:       8.1.0 (API 27)
Security patch level:  2020-07-05
Build type:            userdebug
Build tags:            test-keys
ro.debuggable:         1
SELinux:               Permissive
```

The patch level is more than six years old as of this assessment and cannot include Android fixes issued after July 2020. `userdebug`, `test-keys`, debuggability, and permissive SELinux are development characteristics that greatly amplify the impact of other flaws. AOSP explicitly states that permissive mode is unsupported for production devices and that production policy should be enforcing. See [AOSP SELinux validation](https://source.android.com/docs/security/features/selinux/validate) and [AOSP system security best practices](https://source.android.com/docs/security/best-practices/system).

`test-keys` does not by itself prove that the private signing key is public. The tested Klydo, updater, and Android platform packages share the same observed signature identifier, but the private key was not available for comparison and key custody was not assessed.

**Mitigation**

- Vendor firmware should be rebuilt as a production `user` image, signed with protected release keys, with authenticated/disabled-by-default ADB and SELinux enforcing.
- Provide a supported OTA path with current Android/platform security fixes.
- Until replacement firmware exists, isolate the device and minimize both inbound reachability and outbound destinations.

### KLY-05 — Main app and updater share the Android system UID

**Severity:** High  
**Status:** Confirmed

Both manifests declare `android:sharedUserId="android.uid.system"`, both packages are platform-signed, and package/process inspection reports UID 1000. Android normally gives each application a unique Linux UID; shared UIDs combine trust and permissions between identically signed packages. Android now strongly discourages and deprecates shared user IDs. See the [`<manifest>` documentation](https://developer.android.com/guide/topics/manifest/manifest-element#uid).

The effective shared-UID permission set shown by the package manager is much broader than the permissions visibly requested by the Klydo manifest. It includes highly sensitive telephony, contacts, call log, package management, event injection, notification/status-bar, storage, location, camera, and microphone capabilities contributed by packages sharing that UID.

The stock application also uses root intentionally. `SystemShellInitializer` runs `su -c` to remount `/data` with a different filesystem mode, and the display-control path invokes `su` when writing hardware state through sysfs. This makes root execution part of normal product behavior rather than merely an accidental consequence of the exposed ADB daemon.

**Impact**

- A bug in either Klydo or the updater has system-app impact.
- The cloud shell and exported components execute with a much stronger identity than a normal app.
- Permission review based only on the Klydo manifest understates effective authority.
- Replacing the app while retaining the same package/data may require the platform signing key.

**Mitigation**

Vendor firmware should migrate functions into least-privileged components and narrow, permission-protected services. Migrating an already-installed shared-UID package is difficult, so this is a firmware/product change rather than a HACS change.

### KLY-06 — Remote database export, SQL query, and logcat streaming

**Severity:** High  
**Status:** Confirmed capability; originating authorization not assessed

The command set contains:

- `sendRoomDB`: sends the complete `klydo_database` file in WebSocket chunks.
- `streamSQLQueries`: accepts SQL text from the WebSocket, passes it to a `SimpleSQLiteQuery`, and returns rows as JSON.
- `logcat`: streams Android log buffers.
- `sendCrashBundle`, `syncLogs`, `syncAnalytics`, `syncInteractions`, and `syncMonitorReports`: upload additional diagnostics/behavior data.

The SQL path is intended as an interactive query facility. It clearly permits arbitrary query text and database reads. Whether all modifying SQL forms can execute through the readable-query API was not tested, so database-write capability is not claimed.

Because the app is the Android system UID, logcat access is broader than a normal application. Logs can contain device identifiers, command names, WebSocket URIs, filenames, failures, and behavior history. The shell manager logs the incoming command text.

**Mitigation**

- Remove production database/query/logcat streaming, or require explicit time-limited on-device owner approval.
- Limit export to a documented redacted schema.
- Redact credentials, tokens, URIs with embedded secrets, serials, Wi-Fi data, and command text from logs.
- Require `wss://`, an allowed host, and session authentication independent of the Firestore command itself.

### KLY-07 — Privileged app and BLE-firmware update chains have weak app-layer validation

**Severity:** High  
**Status:** Confirmed implementation; platform signer security not assessed

There are two update paths:

1. The current Klydo app downloads an APK through the authenticated HTTPS API and silently installs it through `PackageInstaller`. No explicit Klydo-level checksum or pinned signing-certificate comparison was found before committing the session.
2. The separate updater downloads from a Klydo Google Cloud Function and stages `/sdcard/u-main.apk`. If that file already exists, the updater uses it without downloading a replacement, runs `pm install -r`, and then deletes it. No explicit checksum/content verification was found.

There is also a BLE remote-control firmware path. The main app downloads `/sdcard/remote.bin` through the authenticated API and passes it to the Realsil HID DFU library. The DFU configuration explicitly sets IC compatibility checking and version checking to false. No application-level firmware hash or signature verification was found. The Realsil binary format/library may perform internal validation that was not visible in the Klydo calling code, so absence of all cryptographic verification is not claimed.

Android Package Manager still verifies APK structure, package/update compatibility, and signing identity. This assessment does **not** claim that an unsigned or differently signed APK can replace Klydo. A planted invalid APK can at least disrupt an update. A malicious replacement would ordinarily need the accepted signing key or another platform/package-manager vulnerability.

The updater is system-UID, requests `INSTALL_PACKAGES`, and exposes its main activity. The main app's Firebase command `updateApp` can initiate an application update.

**Risk factors**

- Shared external-storage staging creates a time-of-check/time-of-use and local tampering surface.
- No application-layer hash makes download corruption/tampering detection dependent on APK verification alone.
- No application-specific certificate pinning was found; HTTPS relies on the old Android platform trust store.
- BLE DFU deliberately disables IC and version checks in the Klydo configuration, increasing the chance of incompatible firmware being accepted by the update procedure.
- `test-keys` raises a signing-key-custody question, but public-key reuse was not established.
- A vendor backend or signing-key compromise would have system-UID consequences.

**Mitigation**

- Stage updates in private app storage with restrictive permissions.
- Publish a signed update manifest containing version, size, SHA-256, package, and expected signing-certificate digest.
- Verify all fields before installation and refuse unexpected signers/downgrades.
- For remote firmware, enable IC/version checks and verify a vendor-signed manifest plus firmware hash/signature before DFU.
- Protect release keys in hardened signing infrastructure and support key rotation.
- Permission-protect or unexport the updater activities.

### KLY-08 — Extracted device dump contains live secrets and private data

**Severity:** High  
**Status:** Confirmed

The local full-device dump contains the Klydo private data directory, Firebase Auth persistence, caches, settings, logs, analytics, database records, and media. Firebase authentication storage contains persisted session material. Other device-wide data may also include Wi-Fi or system credentials because the dump was obtained with root access.

This is now a second copy of the clock's security state. Host filesystem mode alone is not sufficient if the directory is synchronized to consumer cloud storage, indexed by another user, included in broad backups, committed to a repository, or shared with support bundles.

**Mitigation**

- Keep the dump outside source control and ordinary cloud-synced folders.
- Store it on an encrypted volume with directory mode `0700` and files readable only by the owner.
- Never paste raw auth XML, tokens, database rows, serials, Wi-Fi configuration, or logs into issues or public repositories.
- Create redacted, minimal fixtures for integration tests.
- After analysis, decide whether the original dump is still needed; use a recoverable, documented secure deletion process appropriate to the storage medium if it is retired.
- Reprovisioning or vendor-side token revocation may be warranted if the dump has ever left trusted storage.

### KLY-09 — Unprotected exported application components

**Severity:** Medium  
**Status:** Confirmed code/configuration; exploit was not exercised

The main app exports `com.klydoclock.Main` without a required permission. Its `onCreate()` immediately executes `reboot` and finishes. Another installed app can normally launch an exported activity, so this creates a local reboot/denial-of-service primitive.

`InstallReceiver` is exported for `com.klydoclock.UPDATE_INSTALL_COMPLETE` without a manifest permission. A broadcast reporting success causes the Klydo app to relaunch before any callback/session match is required. The callback map is keyed by session ID, which limits spoofing of the in-memory update callback, but does not protect the relaunch behavior.

The updater also exports its main and restart activities without a custom permission. Starting the updater main activity begins its update behavior after a short delay.

Firebase and Google library activities also appear exported where required by their SDK flows; those were not classified as Klydo-specific findings because some are library defaults or permission-protected.

**Mitigation**

- Set legacy reboot/update activities to `exported=false` unless external invocation is required.
- Protect necessary update entry points and receivers with signature permissions.
- Validate action, caller, package, session ID, and installer identity before performing privileged work.

### KLY-10 — Broadly writable external content and destructive cleanup

**Severity:** Medium  
**Status:** Confirmed

Animation, audio, art, logos, firmware, and update files are kept under shared `/sdcard` locations. The app requests legacy and all-files storage access. On this old Android version, other sufficiently privileged/storage-authorized apps and any ADB user can alter these files.

The daily midnight cleanup builds an allowlist of `mainLoop` values from database records and recursively deletes every directory under `/sdcard/gifs2` whose directory name is not in that set. It similarly cleans unused audio, logos, artist media, collection assets, and explore assets.

**Impact**

- Manually copying a custom animation directory is not durable; cleanup can remove it if no matching database record exists.
- Reusing a vendor ID can be overwritten by synchronization because Room inserts use replacement semantics.
- Corrupt or missing media causes availability failures and can trigger removal/re-download logic.
- Modifying app/database state while the stock app is running can race with playback, sync, and cleanup.

**Mitigation**

- Do not have the ADB-only integration edit the database or content directories.
- Archive stock content outside `/sdcard` before experimenting.
- For future custom content, use a separate namespace, transactional database changes, checksums, backups, and a cleanup exclusion mechanism—or use a replacement player that owns its storage.
- Treat untrusted media as hostile input and transcode/validate it before playback.

### KLY-11 — Support WebSockets accept arbitrary destinations and plaintext

**Severity:** Medium  
**Status:** Confirmed capability; command-origin reachability not assessed

The interactive shell, database transfer/query, and logcat support paths accept a caller-provided URI if it begins with either `ws://` or `wss://`. No Klydo host allowlist or separate WebSocket authentication was found in those managers.

**Impact**

- `ws://` permits passive observation and active tampering by a network attacker on that path.
- Arbitrary outbound destinations create a data-exfiltration and internal-network connection primitive for whoever controls the Firestore command.
- The destination may be recorded in local logs.

This is best understood as an impact multiplier for KLY-02/KLY-06, not an independently internet-reachable WebSocket service.

**Mitigation**

- Require `wss://` only, with a fixed vendor-owned host and short-lived session token.
- Apply certificate pinning or another independently signed session identity for high-privilege support traffic.
- Enforce egress filtering from the IoT VLAN.

### KLY-12 — Backup enabled without explicit sensitive-data exclusions

**Severity:** Medium  
**Status:** Confirmed manifest/configuration; actual backup execution not confirmed

The main app has `android:allowBackup="true"`, an empty `<full-backup-content/>`, and a `<cloud-backup/>` rule with no listed exclusions. The updater also enables backup. Android recommends disabling backup for sensitive apps or explicitly excluding sensitive files. See [Android Auto Backup](https://developer.android.com/identity/data/autobackup).

On this customized Android device, the installed backup transport and whether Firebase auth state is included were not verified. Therefore this is a potential exposure, not a confirmed cloud copy.

**Mitigation**

- Set `allowBackup=false` for the appliance app, or explicitly exclude Firebase auth, DataStore, databases, logs, credentials, and device identity.
- Verify the actual backup transport and extraction behavior on the production firmware.

### KLY-13 — Broad telemetry and support upload surface

**Severity:** Medium  
**Status:** Confirmed capability; server retention and use not assessed

The API includes endpoints for clock analytics, interaction events, internal monitor reports, ordinary/critical logs, and crash bundles. The app also reports version/firmware state, performs an external-IP lookup, maintains a heartbeat, and can upload these categories on a cloud command.

The code establishes collection and upload capabilities; it does not by itself establish the vendor's retention period, privacy policy compliance, human access, or whether every event is currently enabled.

**Mitigation**

- Document the exact data dictionary and retention/access policy.
- Minimize event contents and pseudonymize device identity where possible.
- Provide an owner-visible telemetry control that does not disable core local playback.
- Never log passwords/tokens; redact serials, URLs, command text, database contents, and personal reminder/gift fields.

### KLY-14 — Cloud authority can change behavior and remove content

**Severity:** Medium  
**Status:** Confirmed client capability; vendor operator permissions not assessed

Firestore synchronizes many settings bidirectionally, including brightness, sound controls, feeds/favorites, current content IDs, playback mode, night-mode schedule/appearance, screen state, filters, reminders, and hidden content. The command plane can run `deleteKlydos`, `updateApp`, migrations, pool synchronization, time sync, resets, diagnostics, and other operations.

The REST delta sync can update content, collections, artists, and explore categories. Same-ID records are replaced locally. The app also consumes hidden-content state and later deletes unreachable/unreferenced assets during cleanup.

This confirms that the cloud architecture can add, update, hide, and cause deletion of content on the clock. It does not prove that arbitrary Klydo employees or external users can do so; backend roles and rules were not audited.

**Mitigation**

- Maintain owner-controlled off-device snapshots of database metadata and media.
- Use signed content manifests and append-only archival storage for preservation.
- Require owner consent for application updates and destructive commands.
- Provide a local-only operating mode with a documented export/import format.

### KLY-15 — Vendor cloud is a single point of availability and policy control

**Severity:** Medium  
**Status:** Architecture risk

The app uses Firebase Authentication/Firestore plus Klydo API, time, IP, media/CDN, and update services. Cached media can continue to play locally for some period, but new content, account-backed settings, commands, gifts, ratings, collections, metadata recovery, and updates depend on external services. Cleanup and TTL behavior may reduce the useful cached set over time.

If the vendor shuts down, suffers an outage, changes authentication/rules, loses signing keys, or introduces charges, the owner does not currently control a complete supported replacement backend. DNS redirection alone is insufficient because Firebase authentication/Firestore behavior and HTTPS identity must also be reproduced or the APK must be modified.

**Mitigation**

- Create periodic offline archives now, while the service works.
- Document database/media relationships and all required endpoints.
- Keep the ADB integration local and independent of Klydo cloud availability.
- Plan a separate local player/importer rather than relying on a transparent clone of the vendor backend.

## 5. Home Assistant/HACS-specific risks

### HA-01 — Never expose arbitrary shell input

**Severity:** High if implemented  
**Status:** Preventable design risk

Because the device ADB shell can invoke root, a generic service such as `klydo_clock.shell`, a configurable command template, or concatenating user values into `sh -c` would make any Home Assistant caller with service access a root-equivalent clock administrator. Templated automation data can contain spaces, quotes, semicolons, substitutions, redirections, and newlines.

**Required controls**

- Every operation maps to a hard-coded, reviewed command.
- No entity or action accepts arbitrary shell text.
- Validate animation IDs and similar values with a strict allowlist/length limit and preferably resolve them from a catalog rather than a free-form field.
- Do not use `su` to mutate device files or run caller-supplied commands. Release 0.1.2 uses fixed root reads of four selected DataStore scalars and an on-device favorites hash; control writes are normal remote key events.
- Prefer key events, package-manager queries, Android settings APIs, and narrowly scoped intents.
- Apply timeouts, output-size limits, serialization, and rate limits.
- Treat unknown output as unknown state, not success.

### HA-02 — HACS/dependency supply-chain authority

**Severity:** Medium  
**Status:** Preventable design risk

A custom integration runs inside Home Assistant and will hold uninterrupted network access to the clock's ADB endpoint. A malicious integration update or compromised Python dependency could use that access for any action described in KLY-01.

**Required controls**

- Keep dependencies minimal and pinned to reviewed compatible ranges.
- Publish reproducible releases/tags and use branch protection/review.
- Do not auto-download binaries or execute helper scripts from the internet.
- Document exactly what network destination and commands the integration uses.
- Review HACS updates before installation; do not install untrusted forks.
- Prefer a dedicated Home Assistant network identity and firewall rule to broad LAN access.

### HA-03 — Diagnostics, permissions, and automation abuse

**Severity:** Medium  
**Status:** Preventable design risk

Home Assistant diagnostics can be downloaded and shared. Integration logs and entity attributes are also visible to users with varying permissions. Home Assistant explicitly warns integrations to redact tokens, keys, location, and personal information in diagnostics; see [Home Assistant integration diagnostics](https://developers.home-assistant.io/docs/core/integration/diagnostics/).

**Required controls**

- Redact device IP if the user requests privacy; always redact any future ADB key, serial, tokens, command output, file paths containing IDs, Wi-Fi data, and media metadata that may be personal.
- Never include raw `dumpsys`, `logcat`, database rows, environment variables, or full command transcripts in diagnostics.
- Keep sensitive state out of entity attributes.
- Use standard Home Assistant entity/service permissions; document that users able to press restart/display controls can disrupt the clock.
- Debounce rapid next/previous, screen, and restart actions.
- Serialize ADB calls so polling cannot race with a mutating command.
- Report unavailable/unknown honestly after timeouts or conflicting state.

### Implemented safeguards and remaining limits in 0.1.2

- Published commands are fixed enum values; no arbitrary shell service, editable command template, cloud login or credential extraction is exposed.
- Controls directly edit no files, databases, APKs or firmware. The stock app saves its own state and may upload changes through its existing cloud connection.
- UI-based controls check the foreground/menu context, stop on unsupported output and confirm state changes. Whole multi-step operations are serialized against polling. This does not prevent interference from a physical remote, another ADB client or the vendor cloud.
- Command timeouts and bounded loops are implemented. UI parsing has a size bound, but there is no general pre-buffer transport-output cap, command queue limit or explicit user-action rate limiter. Do not claim every recommendation above has been implemented.
- Diagnostics use an explicit allowlist and omit addresses, serials, identity hashes, raw output and favorite hashes. This does not establish that every possible Home Assistant/dependency debug log is redacted.
- Root-readable app data remains sensitive even when reads are filtered. The hash confirms a favorites-list change; it does not authenticate the device or prove which party caused the change.
- Discovery uses untrusted mDNS plus unauthenticated ADB package/identity checks. A stable identifier hash prevents accidental identity churn, not impersonation by a malicious endpoint. Never treat “verified discovery” as a cryptographic trust guarantee.
- The stock advertisement includes a device identifier. Keep raw discovery records private, particularly given the serial-derived credential design. Broad mDNS forwarding increases where these records can be seen.
- 88 automated tests, Ruff, Hassfest and HACS validation passed for v0.1.2. They verify the integration's behavior and packaging, not vendor backend security, firewall isolation or resistance to a hostile network.

Network isolation and vendor remediation remain outstanding unless independently verified. No firewall, ADB-authentication, SELinux or firmware hardening was performed by this documentation/integration work. This public assessment omits device identifiers, credentials, private backup paths and decompiled vendor code. The underlying private evidence must not be uploaded to this repository.

## 6. Recommended network architecture

```text
Trusted admin workstation ----+
                              +-- firewall allow TCP 1379 --> Klydo Clock
Home Assistant ---------------+

All other LAN/IoT clients -------- firewall deny TCP 1379 --> Klydo Clock
Internet ------------------------- no inbound path ----------> Klydo Clock

Klydo Clock --> Internet: restrict to required HTTPS/DNS while stock cloud is used;
                           deny arbitrary plaintext WebSocket and all unnecessary
                           IPv4/IPv6 access to private or trusted networks.
```

The clock should not be placed on the same unrestricted segment as laptops, NAS devices, cameras, or other appliances. A compromised IoT device on the same flat network could otherwise become root on the clock without credentials, and the root-equivalent outbound cloud shell could use the clock as a foothold toward those systems.

Restricting inbound TCP 1379 does not disable the Firestore/WebSocket shell because that connection originates from the clock. If retaining Klydo cloud service, use an IoT VLAN or equivalent routed isolation and deny clock-initiated access to all trusted internal segments, including RFC1918, IPv6 unique-local (`fc00::/7`) and any globally addressed internal IPv6 prefixes. Same-subnet traffic may bypass the router; use routed separation or effective client isolation. If disabling vendor remote administration is the priority, block the clock's internet/Firebase access or obtain a vendor firmware remedy, accepting that stock synchronization and other cloud features will stop or degrade.

## 7. Immediate action checklist

- [ ] Reserve the clock's IP address.
- [ ] Restrict TCP 1379 to Home Assistant and one admin workstation.
- [ ] Place the clock on a separate IoT/guest VLAN or equivalent routed segment; do not rely only on same-subnet host firewall rules.
- [ ] Deny all other lateral traffic to/from the clock except explicitly required services, including IPv6 routes and `fc00::/7` unique-local addressing.
- [ ] Confirm port 1379 is not exposed by router port forwarding, UPnP, VPN peer routing, or remote-access software.
- [ ] Decide whether Klydo cloud access is required. If it is retained, restrict egress and monitor unexpected WebSocket destinations; if it is not, block internet/Firebase access and document the resulting feature loss.
- [ ] Move/encrypt the full device dump and apply owner-only permissions.
- [ ] Ensure the dump and decompiled output are excluded from source control and public backup/sharing.
- [ ] Preserve a clean APK, database snapshot, and media manifest with hashes.
- [ ] Keep the initial HACS integration strictly ADB-only and allowlisted.
- [ ] Do not edit the stock database or `/sdcard/gifs2` during the ADB-control phase.
- [ ] Record recovery steps before changing firmware, ADB authentication, SELinux, packages, or boot behavior.

## 8. Future vendor/remediation priorities

1. Remove production interactive shell/SQL/logcat commands.
2. Replace serial-derived Firebase passwords with unique, high-entropy or asymmetric provisioned device keys, documented lifecycle controls, and revocation.
3. Ship current production firmware: `user`, release keys, authenticated/disabled ADB, SELinux enforcing.
4. Remove `android.uid.system` from the display app; isolate privileged operations behind permission-protected services.
5. Redesign updates with private staging, signed manifests, hashes, expected signer validation, and owner-visible controls.
6. Unexport or permission-protect reboot, updater, restart, and install-result components.
7. Require fixed authenticated `wss://` support endpoints; remove `ws://` and arbitrary destinations.
8. Disable or strictly scope backups; minimize/redact telemetry and diagnostics.
9. Provide a supported local-only mode and content export/import path.
10. Publish a vulnerability disclosure contact and supported firmware lifetime.

## 9. Verification plan after mitigation

After firewalling:

1. Verify Home Assistant can connect to `<clock-ip>:1379`.
2. Verify the admin workstation can connect only when intended.
3. From at least one ordinary LAN client and one other IoT VLAN client, confirm TCP 1379 is unreachable.
4. Confirm the clock cannot initiate connections to trusted segments, including same-subnet peers where applicable and IPv6 global/unique-local routes. Check rule counters/logs; an IPv4-only rule is insufficient.
5. Confirm discovery (if enabled), next/previous, status, night controls and Favorite still work. Avoid simultaneous controllers during menu operations.
6. Review gateway logs for unexpected WebSocket destinations and unusual Google/Klydo traffic.
7. Re-run the package/property/listener inventory after every clock firmware or APK update.

Do not test the cloud shell, SQL stream, update staging, or exported reboot activity against a production clock unless a recovery path and explicit test window exist.

## 10. Evidence map

Local evidence used for this assessment:

- private local analysis artifacts (not published) — persistent JADX output of Klydo 623.3.
- the private owner-controlled backup (not published) — owner-authorized full device snapshot; contains secrets and must remain private.
- Installed main APK under the extracted `/data/app/com.klydoclock-.../base.apk`.
- Installed updater APK under the extracted `/data/app/klydo.clock.updator-.../base.apk`.
- Live read-only ADB properties, processes, packages, filesystem modes, and socket listeners captured on 2026-09-04.
- A controlled UID 1000-to-UID 0 `su` capability check on the tested clock.
- Persisted Firebase account creation/sign-in timestamps and Android package-manager installation time; all identifiers, credentials, and tokens are omitted.

Related documentation:

- [application reference](docs/APP.md) — technical description of the application and data flows.
- [HA_INT_PLAN.md](HA_INT_PLAN.md) — ADB-only Home Assistant/HACS integration plan.

## 11. Handling and disclosure note

This is a sanitized public assessment of the inspected firmware. It documents confirmed behavior and clearly labels unknown server-side authorization and unverified exploitation. It is not evidence of malicious vendor intent or a past compromise.

Do not attach tokens, serials, Wi-Fi information, raw discovery/ADB logs, APKs, databases, media or full device backups to public issues. Share only sanitized reproduction details. Coordinate any additional sensitive vulnerability evidence through an appropriate private channel; this project has not established or verified a vendor security contact. No vendor notification or completed remediation is claimed.
