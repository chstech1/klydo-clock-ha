# Discovery evidence and behavior

## Observed on the test clock

- A unicast DNS-SD service enumeration query to the known clock returned `_adb._tcp.local.`.
- Its PTR record pointed to an `adb-<device identifier>._adb._tcp.local.` instance.
- The SRV record advertised TCP port `1379` and the generic hostname `Android.local.`; the TXT record was empty.
- A normal multicast Zeroconf browse from the development host also resolved the clock's advertisement on port `1379`.
- Read-only Android queries returned an empty `net.hostname`, the generic device name `px30`, and a running `mdnsd` process.

Raw records contain a device identifier and local addresses. They are not committed. The tests use synthetic identifiers and documentation-only IP addresses.

## Matching and verification

The manifest matches `_adb._tcp.local.` instances named `adb-*`. The config flow discards every port other than `1379` before opening a connection. This restricts candidates to the observed stock endpoint without probing ordinary ADB endpoints on other ports. A device on the same port must still pass the integration's package-presence and hashed stable-identity checks.

A new clock receives a user confirmation card; identity is checked again on confirmation in case its address changed hands. An existing clock's address is updated only when ADB returns its saved identity, preserving the device and entity IDs. Same-IP advertisements are ignored before probing to avoid a second ADB connection to a configured endpoint. Pending discovery flows are deduplicated.

The service-instance identifier and generic hostname are never treated as proof of Klydo identity. No database access, clock modification, subnet scan, custom advertisement service or DHCP vendor-wide matcher is needed.

## Security boundary

Package presence and a stable identity hash detect ordinary mismatches; they are not cryptographic authentication. mDNS and the stock unauthenticated ADB endpoint can be impersonated on a hostile network. Limit multicast forwarding and ADB access to intended trusted controllers. Discovery does not secure the clock or disable its separate vendor cloud command channel.

## Limits

- The Home Assistant host needs to receive the mDNS advertisement and reach ADB. A VLAN boundary may require router mDNS forwarding; keep ADB restricted to approved clients.
- Link-local, unspecified, multicast and loopback endpoint addresses are ignored. Routable IPv4/IPv6 candidates can be verified.
- Automatic discovery is limited to the observed stock port and service naming pattern. Manual setup supports custom ports.
- ADB authentication remains unsupported in this release.
- A failed verification silently aborts the candidate flow; manual setup supplies actionable connection errors. Firmware/network failures can therefore prevent a discovered card.
- A DHCP reservation remains helpful. No DHCP discovery claim is made.
- The live advertisement was verified from the development host. End-to-end card appearance and a real DHCP address change on the owner's HA instance have not been tested.
