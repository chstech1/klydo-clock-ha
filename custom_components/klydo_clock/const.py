"""Klydo integration constants."""

from homeassistant.const import Platform

DOMAIN = "klydo_clock"
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.SELECT,
]
DEFAULT_PORT = 1379
DEFAULT_POLL_INTERVAL = 15
DEFAULT_TIMEOUT = 10
CONF_POLL_INTERVAL = "poll_interval"
CONF_COMMAND_TIMEOUT = "command_timeout"
CONF_DIAGNOSTIC_SENSORS = "diagnostic_sensors"
