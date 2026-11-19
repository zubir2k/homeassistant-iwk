"""Config flow for IWK."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from iwk import IWKAuthError, IWKCaptchaError, IWKClient, IWKError

from .const import (
    CONF_LANG,
    CONF_SCAN_INTERVAL,
    DEFAULT_LANG,
    DEFAULT_SCAN_INTERVAL_HOURS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _schema(d: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_USERNAME, default=d.get(CONF_USERNAME, "")): str,
            vol.Required(CONF_PASSWORD, default=d.get(CONF_PASSWORD, "")): str,
            vol.Optional(CONF_LANG, default=d.get(CONF_LANG, DEFAULT_LANG)): vol.In(
                ["en", "my"]
            ),
        }
    )


class IWKConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _validate(
        self, data: dict[str, Any]
    ) -> tuple[dict[str, str], dict[str, Any]]:
        session = async_get_clientsession(self.hass)
        client = IWKClient(
            username=data[CONF_USERNAME],
            password=data[CONF_PASSWORD],
            session=session,
            lang=data.get(CONF_LANG, DEFAULT_LANG),
        )
        try:
            await client.login()
            profile = await client.get_profile()
        except IWKCaptchaError as err:
            _LOGGER.warning("IWK reCAPTCHA failed: %s", err)
            return {"base": "captcha"}, {}
        except IWKAuthError:
            return {"base": "invalid_auth"}, {}
        except IWKError as err:
            _LOGGER.warning("IWK error: %s", err)
            return {"base": "cannot_connect"}, {}
        return {}, profile

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors, profile = await self._validate(user_input)
            if not errors:
                await self.async_set_unique_id(
                    str(profile.get("memberid") or user_input[CONF_USERNAME]).lower()
                )
                self._abort_if_unique_id_configured()
                title = f"IWK ({profile.get('username') or user_input[CONF_USERNAME]})"
                return self.async_create_entry(title=title, data=user_input)
        return self.async_show_form(
            step_id="user", data_schema=_schema(user_input or {}), errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**entry.data, **user_input}
            errors, _ = await self._validate(data)
            if not errors:
                return self.async_update_reload_and_abort(entry, data=data)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return IWKOptionsFlow()


class IWKOptionsFlow(OptionsFlow):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        cur = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_HOURS
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=cur): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=48)
                    )
                }
            ),
        )
