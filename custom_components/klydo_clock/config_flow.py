"""UI setup, reconfiguration and options."""

import ipaddress
import re

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

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

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo):
        """Verify advertised stock-port ADB devices before offering setup."""
        # ADB is shared by many Android products. Never probe other ADB ports,
        # trust a service-instance serial, or treat its hostname as a Klydo ID.
        if discovery_info.type != "_adb._tcp.local." or discovery_info.port != DEFAULT_PORT:
            return self.async_abort(reason="not_klydo")
        address = discovery_info.ip_address
        if (
            address.is_unspecified
            or address.is_multicast
            or address.is_loopback
            or address.is_link_local
        ):
            return self.async_abort(reason="invalid_host")
        candidate = {CONF_HOST: str(address), CONF_PORT: DEFAULT_PORT}
        # Do not open a second ADB connection for a clock already at this address.
        if any(
            entry.data.get(CONF_HOST) == candidate[CONF_HOST]
            and entry.data.get(CONF_PORT) == DEFAULT_PORT
            for entry in self._async_current_entries()
        ):
            return self.async_abort(reason="already_configured")
        self.context["discovery_host"] = candidate[CONF_HOST]
        if self._async_in_progress(match_context={"discovery_host": candidate[CONF_HOST]}):
            return self.async_abort(reason="already_in_progress")
        try:
            identity = await self._validate(candidate)
        except KlydoError:
            return self.async_abort(reason="cannot_verify")
        existing = await self.async_set_unique_id(identity.unique_id)
        if existing and existing.source == config_entries.SOURCE_IGNORE:
            self._abort_if_unique_id_configured()
        # The integration's entry update listener handles reloads. Identity must
        # match through ADB before an advertisement can change an existing entry.
        self._abort_if_unique_id_configured(updates=candidate, reload_on_update=False)
        self._discovered_data = candidate
        self.context["title_placeholders"] = {"name": "Klydo Clock"}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(self, user_input=None):
        """Let the user accept discovery and recheck identity before saving."""
        if user_input is not None:
            try:
                identity = await self._validate(self._discovered_data)
            except KlydoError:
                return self.async_abort(reason="cannot_verify")
            if identity.unique_id != self.unique_id:
                return self.async_abort(reason="unique_id_mismatch")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="Klydo Clock", data=self._discovered_data)
        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            data_schema=vol.Schema({}),
            description_placeholders={"host": self._discovered_data[CONF_HOST]},
        )

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
