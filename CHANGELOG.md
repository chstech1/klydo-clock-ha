# Changelog

## 0.1.1

Add verified mDNS auto-discovery for stock-port Klydo ADB advertisements, a setup confirmation card, and identity-checked address updates for existing clocks. Ignore unrelated ADB ports, suppress duplicate discovery flows and avoid reconnecting to already configured IP endpoints. Manual setup remains available.

## 0.1.0

Initial local ADB integration for stock Klydo Clock: UI setup and options, stable device identity, address reconfiguration, next/previous/refresh buttons, connection and app status, software/storage diagnostics, serialized asynchronous polling, reconnect handling, and HACS packaging.

Display, night-mode, app lifecycle and targeted-animation controls remain gated on physical validation. See `docs/IMPLEMENTATION_STATUS.md` for acceptance work still outstanding.
