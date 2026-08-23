"""Config flow for PenguAstro."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    DeviceMetadata,
    PenguAstroApi,
    PenguAstroConnectionError,
    PenguAstroProtocolError,
    normalize_host,
)
from .const import (
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    MAX_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


async def _validate_host(hass, host: str) -> DeviceMetadata:
    api = PenguAstroApi(async_get_clientsession(hass), host)
    return await api.async_get_metadata()


class PenguAstroConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle PenguAstro config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = normalize_host(user_input[CONF_HOST])
            try:
                info = await _validate_host(self.hass, host)
            except PenguAstroConnectionError:
                errors["base"] = "cannot_connect"
            except PenguAstroProtocolError as err:
                errors["base"] = (
                    "not_dwarf3" if "DWARF 3" in str(err) else "invalid_response"
                )
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error validating DWARF 3")
                errors["base"] = "unknown"
            else:
                unique_id = info.mac or f"host:{host.lower()}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=info.name,
                    data={
                        CONF_HOST: host,
                        "device_name": info.name,
                        "mac": info.mac,
                        "firmware": info.firmware,
                    },
                )

        schema = vol.Schema({vol.Required(CONF_HOST): str})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            host = normalize_host(user_input[CONF_HOST])
            try:
                info = await _validate_host(self.hass, host)
            except PenguAstroConnectionError:
                errors["base"] = "cannot_connect"
            except PenguAstroProtocolError as err:
                errors["base"] = (
                    "not_dwarf3" if "DWARF 3" in str(err) else "invalid_response"
                )
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error reconfiguring DWARF 3")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info.mac or entry.unique_id)
                self._abort_if_unique_id_mismatch(reason="different_device")
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_HOST: host,
                        "device_name": info.name,
                        "mac": info.mac,
                        "firmware": info.firmware,
                    },
                )

        schema = vol.Schema(
            {vol.Required(CONF_HOST, default=entry.data.get(CONF_HOST, "")): str}
        )
        return self.async_show_form(
            step_id="reconfigure", data_schema=schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return PenguAstroOptionsFlow()


class PenguAstroOptionsFlow(OptionsFlowWithReload):
    """Change the polling/image refresh interval."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options.get(
            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_UPDATE_INTERVAL, default=current): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_UPDATE_INTERVAL, max=MAX_UPDATE_INTERVAL),
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
