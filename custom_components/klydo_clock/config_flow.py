"""UI setup, reconfiguration and options."""

import ipaddress
import re

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback

from .adb_client import KlydoClient
from .const import (
    CONF_COMMAND_TIMEOUT,
    CONF_DIAGNOSTIC_SENSORS,
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from .exceptions import (
    KlydoAuthenticationError,
    KlydoError,
    KlydoResponseError,
    KlydoUnsupportedError,
)


def valid_host(value: str) -> str:
    """Accept a host only, never a URL, port or shell expression."""
    value = value.strip().lower()
    try:
        ipaddress.ip_address(value)
        return value
    except ValueError:
        pass
    if len(value) <= 253 and all(
        re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
        for label in value.rstrip(".").split(".")
    ):
        return value.rstrip(".")
    raise vol.Invalid("Enter an IP address or hostname")


def host_schema(defaults):
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): valid_host,
            vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=65535)
            ),
        }
    )


class KlydoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Identify clocks by device ID, independent of network address."""

    VERSION = 1

    async def _validate(self, user_input):
        client = KlydoClient(user_input[CONF_HOST], user_input[CONF_PORT])
        try:
            return await client.identify()
        finally:
            await client.close()

    async def _step_host(self, step_id, user_input):
        errors = {}
        defaults = {}
        if step_id == "reconfigure":
            defaults = self._get_reconfigure_entry().data
        if user_input is not None:
            try:
                user_input = host_schema(defaults)(user_input)
                identity = await self._validate(user_input)
            except vol.Invalid:
                errors["base"] = "invalid_host"
            except KlydoAuthenticationError:
                errors["base"] = "invalid_auth"
            except KlydoUnsupportedError:
                errors["base"] = "not_klydo"
            except KlydoResponseError:
                errors["base"] = "missing_identity"
            except KlydoError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(identity.unique_id)
                if step_id == "reconfigure":
                    self._abort_if_unique_id_mismatch()
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(), data_updates=user_input
                    )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Klydo Clock", data=user_input)
        return self.async_show_form(
            step_id=step_id, data_schema=host_schema(user_input or defaults), errors=errors
        )

    async def async_step_user(self, user_input=None):
        return await self._step_host("user", user_input)

    async def async_step_reconfigure(self, user_input=None):
        return await self._step_host("reconfigure", user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return KlydoOptionsFlow()


class KlydoOptionsFlow(config_entries.OptionsFlow):
    """Reload the entry when polling or diagnostic options change."""

    async def async_step_init(self, user_input=None):
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_POLL_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=300)),
                vol.Required(
                    CONF_COMMAND_TIMEOUT,
                    default=self.config_entry.options.get(CONF_COMMAND_TIMEOUT, DEFAULT_TIMEOUT),
                ): vol.All(vol.Coerce(int), vol.Range(min=2, max=30)),
                vol.Required(
                    CONF_DIAGNOSTIC_SENSORS,
                    default=self.config_entry.options.get(CONF_DIAGNOSTIC_SENSORS, True),
                ): bool,
            }
        )
        errors = {}
        if user_input is not None:
            try:
                validated = schema(user_input)
            except vol.Invalid:
                errors["base"] = "invalid_options"
            else:
                return self.async_create_entry(title="", data=validated)
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
