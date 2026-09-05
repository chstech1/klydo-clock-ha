# Changelog

## Documentation after 0.1.2

Update the security assessment, recovery instructions and acceptance status. Explain unauthenticated root access, the independent stock cloud shell, network isolation requirements, and the limits of discovery identity checks. No runtime or device changes.

## 0.1.2

Add a confirmed Night mode switch, an Automatic night mode selector (Off, Scheduled, Dim room), and a Toggle favorite button. Controls use normal stock remote key events with guarded menu navigation, selected-state reads and bounded verification. No direct device file/database writes or installed helper.

Manual night exit restores maximum brightness; automatic policy remains independent. Changing automatic mode can take a minute or more and requires an awake clock in Feed with menus closed. Favorite toggles are not automatically replayed after uncertain results.

88 automated tests, Ruff, Hassfest and HACS validation passed. Live night, automatic-setting and favorite checks passed; broader schedule/ambient and owner-side installation acceptance remain outstanding.

## 0.1.1

Add verified mDNS auto-discovery for stock-port Klydo ADB advertisements, a setup confirmation card, and identity-checked address updates for existing clocks. Ignore unrelated ADB ports, suppress duplicate discovery flows and avoid reconnecting to already configured IP endpoints. Manual setup remains available.

## 0.1.0

Initial local ADB integration for stock Klydo Clock: UI setup and options, stable device identity, address reconfiguration, next/previous/refresh buttons, connection and app status, software/storage diagnostics, serialized asynchronous polling, reconnect handling, and HACS packaging.

At the 0.1.0 release, display, night-mode, app lifecycle and targeted-animation controls remained gated on physical validation. Night controls were subsequently added in 0.1.2. See `docs/IMPLEMENTATION_STATUS.md` for acceptance work still outstanding.
