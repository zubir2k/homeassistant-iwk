"""Data update coordinator for IWK."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.components.http.auth import async_sign_path
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from iwk import (
    IWKAccount,
    IWKAuthError,
    IWKCaptchaError,
    IWKClient,
    IWKError,
)

from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_HOURS, DOMAIN

_LOGGER = logging.getLogger(__name__)

type IWKConfigEntry = ConfigEntry["IWKCoordinator"]


class IWKCoordinator(DataUpdateCoordinator[dict[str, IWKAccount]]):
    """Polls every linked IWK account."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: IWKClient
    ) -> None:
        hours = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_HOURS)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=hours),
            config_entry=entry,
        )
        self.client = client
        self.entry_id = entry.entry_id
        # (san, ref_no) -> signed, expiring HA path to the bill PDF proxy
        self.pdf_urls: dict[tuple[str, str], str] = {}

    def pdf_path(self, san: str, ref: str) -> str:
        return f"/api/{DOMAIN}/bill/{self.entry_id}/{san}/{ref}.pdf"

    def _sign_pdf_urls(self, data: dict[str, IWKAccount]) -> None:
        """Re-sign PDF links each refresh; each stays valid until a bit after the next one."""
        expiry = (self.update_interval or timedelta(hours=6)) + timedelta(hours=2)
        urls: dict[tuple[str, str], str] = {}
        for san, acc in data.items():
            for h in acc.history:
                if h.get("pdf") and h.get("bill_no"):
                    try:
                        urls[(san, h["bill_no"])] = async_sign_path(
                            self.hass, self.pdf_path(san, h["bill_no"]), expiry
                        )
                    except Exception as err:  # noqa: BLE001 - http not ready / no content user
                        _LOGGER.debug("Could not sign PDF path: %s", err)
        self.pdf_urls = urls

    async def _async_update_data(self) -> dict[str, IWKAccount]:
        try:
            if not self.client.profile:
                await self.client.get_profile()
            data = await self.client.get_accounts()
        except IWKAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except IWKCaptchaError as err:
            raise UpdateFailed(f"reCAPTCHA failed: {err}") from err
        except IWKError as err:
            raise UpdateFailed(str(err)) from err
        self._sign_pdf_urls(data)
        return data
