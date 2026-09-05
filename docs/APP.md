# Klydo Clock Application: Architecture and Behavior

Status: Technical working notes 1.2  
Last updated: 2026-09-05 (UTC)  
Test application: `com.klydoclock` version 623.3  
Test updater: `klydo.clock.updator` version 25

## Current project summary

The separate Home Assistant integration is published at [chstech1/klydo-clock-ha](https://github.com/chstech1/klydo-clock-ha), with [v0.1.2](https://github.com/chstech1/klydo-clock-ha/releases/tag/v0.1.2) available for HACS. Add that repository as an **Integration**, download the release, and restart Home Assistant. The tested baseline is Home Assistant 2026.9.0 or newer.

It includes verified mDNS discovery, next/previous/refresh buttons, a Night mode switch, an Automatic night mode selector, a Toggle favorite button, and connection/app/storage status. The release passed 88 automated tests, Ruff, Hassfest and HACS validation. Live controls confirmed night on/off, automatic-mode changes and favorite toggling; the initial automatic setting and favorite state were restored. Full HACS installation/update acceptance on the owner's HA instance remains outstanding.

**Security assessment: the tested firmware is not acceptable on a flat, trusted home network.** Any client that can reach its unauthenticated ADB endpoint can obtain root. The stock app also contains an independent cloud-triggered shell with root-equivalent authority. The integration does not fix either condition. Isolate the clock and read [security assessment](../SECURITY.md) before treating it as a routine network appliance.

All integration runtime code is in `custom_components/klydo_clock/`. No device files, databases, APKs or firmware were directly edited for these controls, and no helper was installed on the clock. Normal remote key events cause the stock app to save its own settings and may trigger its existing cloud synchronization. Local control does not make the stock application cloud-free.

## 1. What the Klydo Clock is

The tested Klydo Clock is a portrait Android appliance built around a Rockchip PX30 board. The main Klydo application is both the Android home/launcher and the full-screen artwork player. It downloads animated “Klydos” and their metadata from Klydo services, stores them locally, displays them with clock/theme overlays, and synchronizes device settings through Google Firebase.

There is no normal owner username/password on this clock. The app automatically turns the hardware serial number into a device account, authenticates that device to Firebase, and uses the resulting token for Klydo's API and Firestore services.

At a high level:

```text
Klydo API / media CDN --------> metadata + media ----------+
                                                              |
Firebase Auth --> Firestore --> settings + commands ----------+--> Klydo Android app
                                                              |       |
Time/IP services ---------------------------------------------+       +--> Room database
                                                                      +--> /sdcard media
                                                                      +--> full-screen player
                                                                      +--> audio / BLE remote

Home Assistant -- local ADB/TCP 1379 -------------------------------> Android/Klydo controls
```

The Home Assistant path is independent of Firebase and can operate locally, but the stock app's content acquisition and many settings remain cloud-backed.

## 2. Test-device inventory

| Item | Observed value |
|---|---|
| Manufacturer/model properties | `rockchip` / `px30` |
| Board property | `rk30sdk` |
| CPU/application architecture | ARM64 |
| Android | 8.1.0, API 27 |
| Android security patch | 2020-07-05 |
| Build | `userdebug`, `test-keys`, debuggable |
| SELinux | Permissive |
| Physical display | 1080 × 1920 portrait |
| Main package | `com.klydoclock` 623.3 |
| Updater package | `klydo.clock.updator` 25 |
| Main app Linux identity | Android system UID 1000 |
| Main activity | `com.klydoclock.MainActivity` |
| ADB endpoint | TCP port 1379, listening on all interfaces |
| ADB host authorization | Disabled on the tested image |
| Root path | Shell can invoke `/system/xbin/su` |

These are facts about the inspected unit/firmware. A different production run or a future update may differ.

## 3. Installed application components

### 3.1 Main Klydo application

The main APK:

- Declares `MainActivity` as Android `HOME`, `DEFAULT`, and `LAUNCHER`.
- Runs as the platform `android.uid.system` shared UID and is signed with the same observed certificate identity as the platform/updater.
- Uses Hilt dependency injection, Kotlin coroutines/flows, Jetpack DataStore, Room/SQLite, Firebase Authentication, Cloud Firestore, OkHttp/Retrofit, Android Media3, and a native knob-reader library.
- Requires OpenGL ES 2.0 and Bluetooth LE according to the manifest.
- Requests internet, network/Wi-Fi management, broad external storage, location, phone-state, Bluetooth, audio, boot, and system-settings permissions.
- Inherits a much broader effective permission set through system UID 1000 than its manifest alone suggests.

The app is designed to stay running continuously. It maintains content synchronization, playback cycles, scheduled night mode, time synchronization, diagnostics, heartbeat, audio, Bluetooth, and cloud command listeners.

### 3.2 Updater application

The separate updater is also platform-signed and uses the system shared UID. It requests privileged installation, time/time-zone, cross-user, external storage, network, and privileged phone-state permissions.

Its main activity can:

1. Show an update/onboarding display.
2. Write `/sdcard/updator-version.txt`.
3. Use an already-present `/sdcard/u-main.apk`, or download one from a hard-coded Klydo Google Cloud Function.
4. Run `pm install -r` on that APK.
5. Delete the staging file.
6. Return to Klydo, falling back to a reboot if application launch fails.

The updater also has an exported restart activity that returns to the Klydo application.

### 3.3 BLE/remote-control firmware support

The main APK includes a Realsil DFU service and a `RemoteControlUpdateManager`. It can query the Klydo API for remote-control firmware version/download, store `/sdcard/remote.bin`, flash the paired BLE remote, and verify the result. Bluetooth LE is therefore not only an input channel; the clock also manages firmware for the physical remote.

### 3.4 Low-level hardware integration

`KnobHandler` loads the native library `knob_reader`. The application also manipulates Android system brightness and audio streams. At startup, `SystemVolumeInitializer` pins media and alarm streams to their Android maximum; Klydo then applies its own logical volume levels inside the app.

`SystemShellInitializer` runs a root command at startup:

```text
mount -o remount,fsync_mode=strict /data
```

The screen-off path also uses `su` to write directly to the backlight sysfs node. Root is therefore an expected part of the stock app's design, not merely an accidental capability available to ADB.

## 4. Startup and continuous services

Android launches `KlydoClockApplication`, which initializes crash handling, file logging, the API client, and an injected `AppInitializer`. Constructing that initializer activates or retains references to the following subsystems:

- System shell and system volume initialization.
- Authentication and Wi-Fi state.
- Device registration and version reporting.
- Screen brightness, screen state, and night mode.
- Animation, collection, artist, explore, favorites, reviews, gifts, and pending-content management.
- Machine/content sync and daily-feed scheduling.
- Time and time-zone sync.
- Heartbeat and Firebase command listener.
- Klydo cycling, return-to-feed, alarms/reminders, and silent times.
- Audio/ticks/notification playback.
- Cleanup, crash checks, ratings sync, analytics, interaction, logs, and internal monitors.
- Bluetooth bond/readiness, BLE remote firmware, and hardware knob input.

Many components begin work in their constructors by subscribing to state flows or authentication. This means force-starting the main activity restarts substantially more than just the visible player.

## 5. Authentication: why no owner account is visible

### 5.1 Automatic device account

`DeviceCredentialsProvider` performs the following locally:

```text
serial   = lowercase(Android hardware serial)
email    = serial + "@clocks.com"
password = 32-character lowercase MD5(serial)
```

The app then calls Firebase email/password authentication. The actual serial and derived password are deliberately omitted from these notes.

No Firebase user-creation call or create-account fallback was found in the installed APK. The client derives the credentials and immediately attempts `signInWithEmailAndPassword`, so a matching Firebase Authentication identity must already exist before that login can succeed. This explains why the clock works without the owner creating an account: it uses a device login hidden from the normal interface.

### 5.2 Provisioning timeline on the tested clock

The persisted Firebase user metadata and Android package-manager state provide the following timeline. Device identifiers and authentication material are intentionally omitted.

| Event | Timestamp | Evidence |
|---|---|---|
| Firebase device identity created | Before recorded app installation | Firebase user metadata `creationTimestamp` |
| Main Klydo APK first installed, as recorded by this Android installation | After device identity provisioning | Android package manager `firstInstallTime` |
| First sign-in retained in the inspected Firebase metadata | After recorded app installation | Firebase user metadata `lastSignInTimestamp` |

The cloud identity therefore existed about 83 days before the retained sign-in and roughly ten weeks before this Android installation records the main APK as first installed. Combined with the absence of account-creation code in the APK, this is strong evidence that the device identity was pre-provisioned by Klydo before ordinary customer setup—likely during manufacturing, inventory, or another batch-provisioning stage.

The exact provisioning system and physical stage cannot be determined from the device alone. Package-manager timestamps can also be reset by re-imaging. The evidence establishes pre-provisioning, but does not distinguish factory-line creation from a later inventory/backend process.

The app's later `registerProduct` flow appears separate: it observes synchronized registration state and presents a timed registration interface, but it does not create the Firebase Authentication identity used for the device login.

### 5.3 Firebase's role

Firebase is Google's hosted application-backend platform. Klydo uses at least two parts:

- **Firebase Authentication** — accepts the device email/password and issues short-lived ID tokens plus a refresh token.
- **Cloud Firestore** — a synchronized document database used for machine settings, state, commands, and command history.

Firebase is not the artwork CDN or the entire Klydo API. It is the identity and real-time control/settings layer.

### 5.4 Klydo API authentication

For normal Klydo API requests, `AuthInterceptor` obtains a current Firebase ID token and sends:

```http
Authorization: Bearer <firebase-id-token>
X-Klydo-Serial: <device-serial>
```

The SDK persists Firebase session material in the app's private data so the clock can refresh authentication without asking the owner.

## 6. Network services

### 6.1 Principal services observed in the APK

| Service | Purpose |
|---|---|
| `https://api.klydoclock.com/` | Main authenticated REST API |
| `https://time.klydoclock.com/` | Clock time lookup/synchronization |
| `https://ip.klydoclock.com/` | External IP/geographic/network metadata lookup |
| Klydo Cloudinary media paths | Animation/media delivery or legacy base URLs |
| Google Firebase Authentication | Device login/token refresh |
| Google Cloud Firestore | Synchronized machine settings and remote commands |
| Klydo Google Cloud Function | Legacy updater APK download |
| Caller-supplied WebSocket | Vendor support shell, SQL, DB export, and logcat sessions |

The main Retrofit client uses HTTPS, Klydo authentication and gzip interceptors, a 10-second connect timeout, 60-second read/write timeouts, and retry-on-connection-failure. It uses the Android/OkHttp default certificate trust and hostname verification. No Klydo-specific certificate pinning was found.

### 6.2 REST API inventory from version 623.3

Base URL paths found in `KlydoApiClient`:

| Category | Methods and paths |
|---|---|
| Connectivity/identity | `GET clock/connectivity-check`; `GET clock/get-clock-token`; `GET clock/get-num-of-accounts`; `POST clock/reset-accounts` |
| Time/network | `GET https://time.klydoclock.com/`; `GET https://ip.klydoclock.com/` |
| Individual content | `GET clock/get-klydo` by ID or main-loop; `POST clock/get-klydos`; `GET clock/get-klydo-stats`; `GET clock/artist/{artistId}` |
| Content pools/sync | `GET clock/sync-klydos`; `GET clock/get-firmware-klydos`; `POST clock/sync-data`; `GET clock/sync-data-v2`; base-mainloop URL; feed-cutoff time; OEM-size validation |
| Daily/gift content | get/request daily Klydos; request gift Klydos; get gift details |
| Collections/explore | get/delete collection metadata; list collection Klydos; redeem/redeem-v3; installed ping; explore categories; animation URL |
| Ratings/reviews | get review queue; rate one/batch; reset ratings |
| Updates | current Klydo APK/version; updater APK/version; BLE remote firmware/version |
| Telemetry | save Klydo analytics; upload analytics; interactions; internal-monitor reports; ordinary and critical logs |
| Crashes | request crash-bundle upload URL; report crash bundle uploaded |

The route inventory was derived from local static analysis; decompiled vendor code is not included in this repository.

## 7. Firestore data and synchronization

### 7.1 Machine document

Synchronized properties live under the Firestore `machines` collection at the document identified by the authenticated Firebase user ID. Each property is represented as a value plus time/source metadata. Many properties are bidirectional: a local UI change is uploaded, and a newer remote value is applied locally.

The keys found in `SyncedSettings` are grouped below.

| Area | Firestore/DataStore keys |
|---|---|
| Display | `brightness`, `showDials`, `screenState`, `nightMode`, `nightModeAppearance`, `nightModeTimes` |
| Animation audio | `playerVolume`, `klydosSound`, `masterSoundMixer` |
| Clock sounds | `chimesVol`, `chimes`, `chimeMode`, `ticksVol`, `ticks`, `defaultCustomChimeId` |
| Quiet hours | `quietTimesOn`, `quietTimes` |
| Content filters | `show13Plus`, `showPSF`, `freshHold` |
| Feeds/favorites/reviews | `feeds`, `favorites`, `reviewsFeed`, `ratedKlydos`, `reviewEndDates`, `hiddenKlydos` |
| Cycles | `feedCycleMode`, `favoritesCycleMode`, `collectionCycleMode`, `stayInFavorits`, `stayInFavoriteDuration` |
| Current position | `klydo`, `mode`, `curFeed`, `curFavs`, `curReviews`, collection/themed/explore current IDs |
| Collections/pending | `machineCollections`, `pendingKlydos` |
| Time | `timeOffset`, `timeFormat` |
| Alarms/reminders | `clockReminders`, `alarmVolume`, `reminderKlydosSettings` |
| Device flags | `onboardingDate`, `beta`, `isRetail`, `isKlydosRater`, `registerProduct`, `hideDev`, `isTester` |

Visible defaults include brightness 5 on a 0–10 scale; player/chime/alarm volumes 50; tick volume 25; animation sound, chimes, and ticks enabled; quiet time enabled from 22:00 to 07:00; dials hidden; 13+/PSF content enabled; and the master mixer categories enabled. Server state can supersede defaults.

### 7.2 Cloud command queue

After authentication the app watches:

```text
machines/<firebase-user-id>/commands
```

When a new document appears, `CommandManager` records pending/history state, finds the named executor, runs it, updates command history, and deletes the original queue document. The observed command names are:

| Command | Observed purpose |
|---|---|
| `test` | Basic command-path test |
| `playSound` | Play a requested sound |
| `fetchRatingFeed` | Refresh content to rate/review |
| `getGift` | Retrieve/process gift content |
| `resetRatings` | Reset rating state |
| `syncPool` | Synchronize content pool |
| `syncTime` | Run time synchronization |
| `runMigrations` | Execute application/data migrations |
| `runMonitors` | Run internal health monitors |
| `syncAllSettingsToFirestore` | Push local synchronized settings to the machine document |
| `syncAnalytics` | Upload queued analytics |
| `syncInteractions` | Upload queued UI interactions |
| `syncLogs` | Upload logs |
| `syncMonitorReports` | Upload health-monitor reports |
| `sendCrashBundle` | Prepare/upload crash diagnostics |
| `deleteKlydos` | Delete specified content records |
| `updateApp` | Check/download/install the Klydo APK |
| `logcat` | Stream Android logs to a supplied WebSocket |
| `sendRoomDB` | Send the complete Room database to a supplied WebSocket |
| `streamSQLQueries` | Receive database query text and return rows over a supplied WebSocket |
| `streamAdbShell` | Receive shell text, run it through `sh -c`, and return results over a supplied WebSocket |

The final four are vendor remote-support capabilities, not ports listening on the LAN. A Firestore command tells the app which `ws://` or `wss://` address to call outbound.

For `streamAdbShell`, every WebSocket text message other than the `keep-alive` and `finish` controls is executed as:

```text
Runtime.getRuntime().exec(["sh", "-c", received_command])
```

There is no shell-command allowlist. The manager returns stdout, stderr, and the exit code, with a 30-second timeout for each command and a two-minute inactivity timeout for the session. Those timeouts limit hangs, not authority.

The shell starts with the Klydo process identity, Android system UID 1000. In a controlled local test, a shell started as UID 1000 successfully invoked `/system/xbin/su 0` and became UID 0. Because this is the same Linux UID as the application and SELinux is permissive, the built-in cloud shell is root-equivalent on the tested firmware. This verifies capability; it is not evidence that Klydo or another party has used it.

The WebSocket is initiated outbound by the clock, and the command can supply any destination beginning with `ws://` or `wss://`. Restricting inbound ADB port 1379 therefore does not disable this cloud path. If activated, it can run local commands and initiate connections toward other systems reachable from the clock, although compromising another LAN device would still require an exposed service, credentials, or a vulnerability on that target.

No local log or cached Firestore evidence of an actual `streamAdbShell` session was found. Command documents are deleted after processing and relevant history may not be retained in the local cache, so that negative result is not proof that the capability has never been used.

## 8. Local database

The current Room database is named `klydo_database`. The inspected snapshot contains:

| Table | Rows | Role |
|---|---:|---|
| `klydos` | 485 | Main content metadata and media references |
| `klydo_metadata` | 485 | Device-local view/gift/TTL state |
| `pending_ratings` | 0 | Ratings waiting to upload |
| `android_metadata`, `room_master_table` | Internal | SQLite/Room bookkeeping |

### 8.1 `klydos` record contents

Each Klydo record includes:

- Identity: `id`, `mainLoop`, creator, name, timestamps, collection ID.
- Placement/visibility: index, unlisted, OEM, featured, pool, tags, 13+/PSF flags.
- Playback: loop URL, local main-loop identifier, duration, checksum.
- Display/theme: background, pendulum, rod, hands, dial colors; show-dials and pendulum-logo behavior.
- Counts/state: views, favorites, pool timestamp.
- Audio: chime, strike, and alarm URLs/file IDs.
- Capabilities: animation-sound mode/frequency/random behavior, alarm type, extras.

`mainLoop` is particularly important because it is both the content directory and MP4 filename.

### 8.2 `klydo_metadata`

The metadata table links one-to-one with `klydos` and cascades on deletion. It tracks whether the item is a gift, viewed/last viewed/arrival times, time to live, sender, and gift image/date/logo/letter fields.

### 8.3 Replacement semantics

The Room DAO uses insert-or-replace behavior for Klydo records. If cloud synchronization delivers an existing `id`, the local record can be replaced. A custom record using a vendor ID is therefore unsafe; a future stock sync may overwrite it.

## 9. Files and media layout

The current player resolves an animation as:

```text
/sdcard/gifs2/<mainLoop>/<mainLoop>.mp4
```

Other observed storage roots include:

```text
/sdcard/alarms
/sdcard/artists
/sdcard/chimes
/sdcard/collections
/sdcard/explore_categories
/sdcard/explore_welcome
/sdcard/gift_assets
/sdcard/pendulum_logos
/sdcard/strikes
/sdcard/updates
/sdcard/remote.bin
```

The extracted snapshot shows:

- 485 current MP4 animation files under the writable data-media `gifs2` tree, matching the 485 database rows.
- About 930 MB in that current `gifs2` tree.
- 4,502 WEBP files alongside current content/support assets.
- A separate `/oem/gifs2` tree of about 3.1 GB with 97,845 WEBP files and no MP4s, apparently preloaded or legacy frame-based content.
- About 8.5 GB for the complete extracted device snapshot.

A sampled current animation is H.264 MP4, 1080 × 1080, 30 fps. This square content is composited into the 1080 × 1920 portrait clock interface with Klydo's clock/theme UI.

## 10. Content synchronization lifecycle

The stock content path is approximately:

1. Authenticate the device to Firebase.
2. Call Klydo REST sync/feed endpoints.
3. Receive content, collection, artist, and explore-category changes.
4. Update Room records and synchronized lists/current positions.
5. Queue/download missing animation, audio, artist, logo, collection, and gift assets.
6. Validate that reachable content has required media.
7. Display only records whose expected local files are present.
8. Periodically upload ratings, analytics, and interactions.
9. Run cleanup to remove expired, orphaned, old, or unreferenced content/assets.

`clock/sync-data-v2` returns maps including Klydos, collections, artists, and explore categories to update. Daily feed calls retrieve or request fresh Klydos. The application also supports full/OEM pool endpoints and a pending-content queue for downloads/retries.

The player has checksum-recovery logic. If playback fails and a checksum exists, it verifies the local file; missing/broken media can be removed and queued for re-download. If metadata lacks the checksum, the app can refetch metadata from the server before deciding.

## 11. Deletion, hiding, expiration, and cleanup

The cloud can influence content removal in several ways:

- Delta/full synchronization can replace local records and source lists.
- The synchronized `hiddenKlydos` property removes items from visible modes.
- The explicit `deleteKlydos` command deletes requested database content.
- Time-to-live metadata marks temporary content for expiration.
- Orphan cleanup deletes records no longer reachable from feeds, favorites, collections, explore, ratings/reviews, current content, or other protected sources.
- Old-feed cleanup limits accumulated non-collection content while preserving a minimum feed threshold.

`CleanupScheduler` runs daily at 00:00. After database cleanup, it enumerates directories under `/sdcard/gifs2`. Any directory whose name is not a `mainLoop` value in the remaining database rows is recursively deleted. Similar reference-based cleanup applies to chimes, strikes, alarms, pendulum logos, artists, collections, and explore assets.

Consequences for custom content:

- Copying only an MP4/directory is temporary; cleanup can delete it.
- A matching database row is necessary for stock playback and cleanup survival.
- A row alone is insufficient if feed/mode reachability rules later classify it as an orphan.
- A custom ID/main-loop namespace must not collide with Klydo IDs.
- Cloud sync can replace a same-ID row, hide it, remove it from modes, or eventually cause its files to be cleaned.

## 12. Playback and navigation

The app uses Android Media3/ExoPlayer-style media components and maintains a `PlaybackState` containing the current Klydo, source/mode, theme colors, local video path, and revision.

Supported view modes found in the app are:

```text
FEED
FAVORITE
COLLECTIONS
EXPLORE
RATING
```

The manager builds arrays for the active mode and tracks a current index/content ID. It can move next/previous, go to an index, load/reload modes, insert pending items after the current position, return from explore, and handle playback/codec failures.

### 12.1 Validated ADB navigation

On the physical clock:

| Operation | Android input | Result |
|---|---|---|
| Previous animation | key event 21 (DPAD left) | Tested; current animation changed backward |
| Next animation | key event 22 (DPAD right) | Tested; current animation changed forward |

Release 0.1.2 also validates Enter (66) as the favorite toggle on a normal animation, moon/N (42) for the stock night sequence, and Down (20) plus left/right/Enter for guarded English settings-menu navigation. These keys are context-sensitive: Favorite is blocked when a menu/overlay is open, and automatic settings require an awake clock in Feed. DPAD center is not used as a substitute for Enter.

### 12.2 Targeted selection

The internal app can select by ID/index and tracks current IDs per mode. No safe exported intent or public local API for “play animation X” has yet been identified. ADB could manipulate UI or private data, but the ADB-only HACS plan defers targeted selection until a reversible and reliable mechanism is found.

## 13. Display, brightness, and night mode

The app has three related but distinct concepts.

### 13.1 Night-mode policy

`nightMode` selects how night mode is activated:

```text
OFF
SCHEDULE
AUTO
```

`nightModeTimes` stores the schedule. `AUTO` is the stock **DIM ROOM** option and uses ambient-light behavior; it is distinct from scheduled hours. Home Assistant exposes Off, Scheduled and Dim room. Schedule times remain configured on the clock.

### 13.2 Night appearance

`nightModeAppearance` determines the visual result:

```text
RED_THEME
DIMMED_RED_THEME
SCREEN_OFF
```

### 13.3 Current screen state

`screenState` is the currently applied state:

```text
DEFAULT
NIGHTMODE
OFF
```

The normal brightness setting is a logical 0–10 value. For ordinary display:

| Logical level | Android backlight value | Additional behavior |
|---:|---:|---|
| 0 | Direct off path | App darkener plus sysfs backlight write |
| 1–4 | 25 | Increasingly lighter dark overlay |
| 5 | 25 | No dark overlay |
| 6 | 50 | No dark overlay |
| 7 | 100 | No dark overlay |
| 8 | 150 | No dark overlay |
| 9 | 200 | No dark overlay |
| 10 | 255 | No dark overlay |

In night state, the effective logical brightness is 8 for `RED_THEME` and 4 for `DIMMED_RED_THEME`. In `OFF`, the app sets the Android brightness setting to 15 and executes:

```text
su -c "echo 0 > /sys/class/backlight/backlight/brightness"
```

Switching back to default/night state reapplies the appropriate brightness and re-enables Android animation scales.

### 13.4 Validated Home Assistant controls in 0.1.2

The **Night mode switch** reports current state, with `DEFAULT` off and `NIGHTMODE`/`OFF` on. It sends the stock moon key and confirms state after each press. From maximum normal brightness, entry proceeds through logical brightness 7 and 4 before night mode. Exit from night mode passes through screen-off and returns to normal at brightness 10. It is an immediate request rather than a schedule change, but network reads and multiple button presses take time. An already satisfied request does not send another key.

The **Automatic night mode selector** changes `nightMode` through verified stock English menus. It can take a minute or more. It requires an awake clock displaying Feed and closed menus. Changing the immediate switch does not disable automatic policy, so a saved schedule or dim-room rule can later reassert night mode. Set automatic policy to Off for manual control. Night appearance is not exposed as a separate integration control.

State comes from four filtered scalar entries in the current Jetpack DataStore file: screen state, automatic night policy, logical brightness and playback mode. The integration uses root only for fixed reads. It does not write DataStore or use stale legacy SharedPreferences as authoritative state. Missing/invalid values become unknown or unavailable. Favorite confirmation compares a hash computed on the clock; the favorites list is not downloaded.

Live tests confirmed the transitions and restoration of the prior automatic/favorite settings. Long-term scheduling, ambient-light thresholds, physical brightness persistence and other firmware/languages still require acceptance testing.

## 14. Audio, alarms, and reminders

Klydos can reference their own animation audio and may include chime, strike, and alarm assets. The app has logical volume controls for player, chimes, ticks, and alarms, plus a master mixer with categories:

```text
ALL
ANIMATION
CHIMES_AND_STRIKES
TICKS
```

It supports:

- Clock chimes and strikes.
- Tick sounds.
- Animation-specific audio modes, including play-once frequency/random configuration.
- Alarms and reminders with per-reminder animation/settings maps.
- Quiet/silent times.
- Previewing and stopping reminder/alarm sounds.
- Ad-hoc playback from HTTP, HTTPS, and file URIs in the relevant player path.

The system media/alarm streams are pinned high; user-facing volume is mainly the app's internal mix.

## 15. Application updates

### 15.1 Current in-app updater

The main app can query version endpoints, download the current APK to local update storage, and silently install it using Android `PackageInstaller`. The install result returns through `com.klydoclock.UPDATE_INSTALL_COMPLETE`, after which Klydo relaunches.

The Firestore command `updateApp` can initiate this flow. Android still enforces package/signature compatibility, but no extra Klydo-level checksum/signing-certificate verification was found in this path.

### 15.2 Legacy standalone updater

The standalone updater uses the external `/sdcard/u-main.apk` staging path and an older hard-coded Google Cloud Function. If the staging file exists, it skips the network download and tries to install that file. Android Package Manager's signature check remains the final authenticity boundary.

### 15.3 Remote firmware

Remote-control firmware is separately versioned and downloaded as `/sdcard/remote.bin`, then flashed over BLE through the included Realsil DFU stack. Klydo's DFU configuration disables the library's IC-compatibility and version checks, although it separately queries/verifies the reported remote version around the update. No Klydo-level firmware hash/signature check was found in the calling code; validation internal to the Realsil image/library was not audited.

## 16. Logging, monitoring, crashes, and analytics

The app maintains file logs and a global exception handler. Observed reporting categories include:

- Content/view analytics.
- Raw UI interaction events.
- Favorites/current-content statistics.
- Internal health-monitor reports.
- Normal and critical logs.
- Crash bundles using a server-provided upload URL.
- Heartbeat and application/version state.
- External-IP information.

There are scheduled upload and cleanup components as well as cloud commands to force synchronization. The exact vendor retention policy and which categories are enabled server-side were not available from the APK.

## 17. What happens if Klydo cloud is unavailable

### 17.1 Functions expected to remain locally available

Subject to a successful app start and intact local state:

- Playback of already-downloaded MP4s.
- Next/previous navigation through locally constructed lists.
- Local clock display/theme rendering.
- Physical/ADB input.
- Some local settings and schedules stored in DataStore.
- Audio whose files already exist.

### 17.2 Functions that degrade or stop

- Firebase device authentication and token refresh after cached credentials expire or are invalidated.
- Firestore settings synchronization, command channel, heartbeat, and cloud state.
- New daily/feed/gift/collection/explore content and metadata recovery.
- Downloads of missing or corrupt media.
- Ratings, analytics, interactions, logs, and crash uploads.
- Klydo APK and BLE remote firmware updates.
- Server time/IP-dependent functions.

Offline cold-boot behavior has not yet been tested end-to-end, so continued local playback after a long outage should be validated rather than assumed. TTL, orphan, and old-content cleanup could reduce the locally playable catalog even while the cloud is unavailable.

## 18. Home Assistant control over ADB

### 18.1 Does anything need to be installed on the clock?

For the current ADB-only integration: **no**. The tested firmware already exposes ADB over TCP 1379. Home Assistant can connect remotely over the LAN using a pure-Python ADB client.

This remains true after clock reboots as long as the firmware continues to start the ADB daemon on that port and the clock's IP remains reachable. A DHCP reservation is recommended.

### 18.2 Released behavior

| Feature | Implementation and limits |
|---|---|
| Discovery | Stock `_adb._tcp.local.` / `adb-*` advertisement on port 1379, followed by package/identity checks; no subnet scan |
| Identity | Hash of a stable device identifier preserves entity IDs; this is not cryptographic authentication |
| Buttons | Next, previous, refresh and favorite toggle; Favorite requires a normal awake animation with menus closed |
| Night switch | Confirmed current state and bounded stock remote sequence; exit restores maximum brightness |
| Automatic selector | Off, Scheduled or Dim room through checked English menus; saved times are configured on the clock |
| Status | Shared polling of connection, process, foreground, version, storage and selected display/app settings |
| Transport | One serialized asynchronous ADB client, fixed command inventory, per-command deadlines and bounded reconnect backoff |
| Failures | Unknown state is not success; possibly delivered commands are not automatically replayed |

The clock advertises its ADB service without adding anything to its firmware. Across VLANs, discovery requires appropriately scoped mDNS forwarding as well as a restricted ADB firewall rule. A DHCP reservation remains useful. Service records and reported device IDs are untrusted; a hostile endpoint can lie about its identity.

### 18.3 Not yet released or fully accepted

App launch/stop/restart, media-player semantics, independent panel power/brightness controls, current-animation metadata, targeted selection and playback-mode selection remain outside 0.1.2. Readability or theoretical ADB capability is not evidence that a safe HA control has shipped. Real reboot/Wi-Fi recovery, owner-side HACS lifecycle tests, long-term automatic night behavior and full-stock recovery remain acceptance work.

The original [HA_INT_PLAN.md](../HA_INT_PLAN.md) remains the roadmap. See [implementation status](IMPLEMENTATION_STATUS.md) for the current release. Firebase control, database modification, custom media, MQTT and a replacement app remain outside this integration.

## 19. Preserving Klydo content

An archival process is feasible now because the clock stores ordinary MP4s and a readable metadata database. A preservation snapshot should include:

- The Room database plus SQLite sidecar files while in a consistent state.
- `/sdcard/gifs2` and referenced audio/logo/artist/collection/gift assets.
- A generated manifest containing relative path, size, SHA-256, content ID, main-loop ID, creator/name, and snapshot time.
- The installed main/updater APKs and their certificate digests.
- The exact app/firmware versions and database schema.

The archive must live off the clock because stock cleanup can delete files. Use append-only/versioned storage so a later vendor deletion does not delete older snapshots.

Do not archive or publish Firebase tokens, derived credentials, Wi-Fi secrets, private gifts/reminders, or raw system logs with the content catalog.

## 20. Adding custom content to the stock application

It is technically plausible but fragile:

1. Transcode a safe MP4 matching the device/player expectations.
2. Choose collision-resistant custom `id` and `mainLoop` values.
3. Create a complete `klydos` row with valid non-null fields and theme/capability values.
4. Create linked metadata and place the file at the exact `gifs2` path.
5. Add the ID to a reachable feed/favorite/collection/mode list.
6. Ensure the checksum behavior does not classify the file as broken.
7. Prevent stock cleanup from treating the row/file as old, expired, orphaned, or unused.

The stock app and cloud can overwrite, hide, remove, or clean custom state. Database mutation while the app runs also risks Room cache/invalidation issues and races. For those reasons, custom-content injection should be a separate experimental project with full snapshots and rollback—not part of the ADB HACS integration.

## 21. Removing the cloud dependency

There are three materially different approaches.

### 21.1 Archive-only companion

Keep the stock app/cloud intact and periodically copy new content to owner-controlled storage before Klydo can remove it. This is the quickest way to preserve content, but the visible clock still depends on Klydo for new material and the remote command path remains active.

### 21.2 Patch/reimplement the Klydo backend contract

Redirect or modify the stock app so API, Firebase authentication/Firestore, media, time, updates, and support services point to owner-controlled replacements. This has high complexity because:

- HTTPS host identity and hard-coded endpoints must be addressed.
- Firebase is a real protocol/hosted platform, not a simple JSON file server.
- The device credential and Firestore document behavior must be reproduced or removed.
- The app is platform-signed/system-UID; updating it in place may require the accepted signing key or a firmware-level change.
- Many synchronized settings and schedulers assume the current data model.

This is possible as a reverse-engineering project, but it is closer to maintaining a private fork of the appliance firmware than to creating a Home Assistant integration.

### 21.3 Replace the player application

Build an owner-controlled full-screen player that reads a local manifest/media library and exposes a small authenticated local API, MQTT interface, or both. This is the cleanest long-term route for:

- Offline operation.
- Custom animations.
- Retaining every archived item.
- Home Assistant overlays/status panels.
- Deterministic schedules and transitions.
- Removing Firebase/Klydo command and telemetry dependencies.

The replacement can reuse the ordinary MP4 catalog and reconstructed metadata/themes while defining a safer local schema. ADB can bootstrap and recover it, but normal Home Assistant control should ultimately use a narrow authenticated API rather than permanent root ADB.

## 22. Can the stock app run in Docker as a content collector?

Not as an ordinary Linux container. The APK expects:

- An Android framework/runtime, package manager, Room/DataStore, Media3, and Google/Firebase libraries.
- The Android system UID and platform signature relationship.
- A hardware serial that maps to an existing Klydo Firebase device account.
- ARM64/native behavior, a display, storage layout, audio, and optionally BLE/knob hardware.
- Several privileged permissions and root/system calls.

An Android emulator, Waydroid-style environment, or custom Android virtual machine could be wrapped by container tooling, but it would still need a compatible system image, device identity, platform signing/permissions, Google/Firebase connectivity, and app-specific hardware shims. A stock emulator install will not automatically receive UID 1000 or the original platform privileges.

Docker is well suited to the surrounding pieces:

- Scheduled ADB archival from the real clock.
- Hash/manifest generation and deduplication.
- Media transcoding/validation.
- A self-hosted catalog/media server.
- MQTT/REST/WebSocket services for a future replacement player.
- Home Assistant overlay rendering.

A practical “keep receiving but never lose” arrangement needs either a second stock-compatible collector device/VM or periodic windows in which the original clock runs the stock app online and is archived before cleanup. Running a replacement face and the stock collector on the same device at the same time would require careful process, launcher, database, and display coordination and has not been validated.

## 23. Suggested long-term architecture

The clean separation is:

```text
Stock acquisition environment (isolated)
    Klydo cloud -> stock app -> append-only archive
                              |
                              v
Owner content pipeline
    validate/transcode -> metadata manifest -> local media server
                                              |
                                              v
Replacement clock player (no Klydo internet)
    local media + themes + HA overlays <-> narrow authenticated local API/MQTT
                                              |
                                              v
                                        Home Assistant
```

This preserves the option to receive new vendor content without allowing vendor deletion to propagate into the archive or giving the production clock face a permanent vendor command channel. It is a separate, larger project from the initial HACS integration.

## 24. Confirmed, inferred, and still unknown

### Confirmed

- Device/OS/app/updater versions and privilege model.
- Automatic serial-derived Firebase login algorithm.
- Absence of Firebase account-creation logic in the installed APK and a device identity creation timestamp that predates the recorded app installation and retained sign-in.
- Klydo API routes and Firestore settings/command structures present in version 623.3.
- Local Room schema and current snapshot row counts.
- MP4 path/naming and sampled codec/resolution/rate.
- Next/previous key events, night on/off, automatic setting changes and favorite toggling on the physical clock; v0.1.2 release validation.
- Stock mDNS ADB advertisement and verified discovery implementation in v0.1.1+.
- Daily cleanup and recursive deletion of unreferenced media directories.
- Silent APK installation paths and BLE remote firmware support.
- Vendor support shell, SQL, database export, and logcat code paths.
- A controlled UID 1000 test can invoke `/system/xbin/su 0` and reach UID 0, making the application shell root-equivalent on the tested firmware.

### Strongly inferred from code/data

- The `/oem/gifs2` WEBP tree is preloaded/legacy frame content.
- Existing local content should continue to play for at least some outages.
- A complete custom Klydo row/file/reachability setup can be made playable, subject to reconciliation and cleanup.

### Not yet verified

- Firestore security rules and exactly which vendor principals can write commands/settings.
- The exact factory, inventory, or backend event that created the pre-provisioned Firebase device identity.
- Server-side validation, retention, rate limits, and deletion behavior.
- Offline cold boot and duration of cached Firebase/session behavior.
- Independent brightness and target-animation setters; long-term schedule/ambient interaction with the validated manual night controls.
- Full media format envelope across every Klydo.
- Bootloader/Verified Boot state and whether the platform test key is a known/public key.
- Whether interactive SQL accepts any modifying statements through the Room readable-query path.
- The exact Bluetooth remote command protocol and security.
- Legal/contractual rights to redistribute Klydo artwork; preserving owner-accessible files does not automatically grant redistribution rights.

## 25. Evidence and related documents

Local analysis artifacts:

- private local analysis artifacts (not published) — JADX output for the stock Klydo APK.
- the private owner-controlled backup (not published) — private owner-authorized snapshot containing APKs, database, settings, and media.
- Live read-only ADB observations taken on 2026-09-04.
- Persisted Firebase account timestamps and Android package-manager installation timestamps; identifiers, credentials, and tokens are intentionally omitted.

Related notes:

- [security assessment](../SECURITY.md) — security findings, severity, and mitigations.
- [HA_INT_PLAN.md](../HA_INT_PLAN.md) — scoped ADB-only HACS integration plan.

The decompilation is reconstructed Java, not Klydo's original source. Decompiled names and control flow can be imperfect, so high-impact behavior should be confirmed dynamically in a controlled test window before changing the device.
