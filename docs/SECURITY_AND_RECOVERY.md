# Security and stock recovery

The stock ADB endpoint tested for this project grants root control without authentication. Before regular use, restrict its port to Home Assistant and designated administrators. Neither the integration nor the development machine can establish that a guest network or the internet cannot reach it; verify firewall policy at your router and from those networks.

The integration executes only fixed commands. It does not read Firebase credentials, query/edit the Klydo database, download media, alter APKs, expose a generic shell service, or transmit clock information to a cloud API. Diagnostic exports use an allowlist and contain no address, serial, hashed identity, entry ID, or raw command response. GitHub/HACS downloads occur during installation/updates, not normal device polling.

## Recovery for the 0.1.0 command set

1. Disable or remove the integration if it interferes with the clock. Stop other ADB controllers.
2. Navigation only changes the selected animation; use the clock's physical controls to return to the prior animation. No setting, executable or database is written by this integration.
3. If the stock app is unresponsive, use the manufacturer's normal restart/power-cycle procedure. The integration never reboots the device automatically.
4. Re-enable the integration once the stock app and network are working. Use Reconfigure if its IP address changed.

## Backups and later development

A private, file-level backup of the test clock's APKs, app data, OEM files and media existed before development. Its archive hashes were recorded and compared to the device during capture. It is **not a bootable disk image** and a full restoration has not been rehearsed. Preserve it privately; it can contain credentials, identifiers and copyrighted media. None of those files belongs in this repository.

Before adding app-stop, panel-power, night-mode or content-selection commands, establish and test a recovery procedure for that operation, record the initial state, and confirm a reversible setter plus reliable state readback. Do not claim that copying app-data files over a running app constitutes a safe stock restore. Seek manufacturer recovery guidance if a device no longer boots.
