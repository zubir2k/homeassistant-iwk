"""Buttons for IWK."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from iwk import IWKError

from .const import DOMAIN
from .coordinator import IWKConfigEntry, IWKCoordinator
from .entity import IWKEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: IWKConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    entities: list[ButtonEntity] = []
    for san in coordinator.data:
        entities += [
            IWKRefreshButton(coordinator, san),
            IWKSubscribeEBillButton(coordinator, san),
        ]
    async_add_entities(entities)


class IWKRefreshButton(IWKEntity, ButtonEntity):
    _attr_translation_key = "refresh"
    _attr_icon = "mdi:refresh"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: IWKCoordinator, san: str) -> None:
        super().__init__(coordinator, san, "refresh")

    async def async_press(self) -> None:
        await self.coordinator.async_request_refresh()


class IWKSubscribeEBillButton(IWKEntity, ButtonEntity):
    """Experimental: subscribe this account to eBill by email."""

    _attr_translation_key = "subscribe_ebill"
    _attr_icon = "mdi:email-plus-outline"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: IWKCoordinator, san: str) -> None:
        super().__init__(coordinator, san, "subscribe_ebill")

    async def async_press(self) -> None:
        acc = self.account
        if acc and (acc.ebill_status or "").lower() == "subscribed":
            raise HomeAssistantError(f"{self.san} is already subscribed to eBill")
        try:
            res = await self.coordinator.client.subscribe_ebill(
                self.san,
                ownership=(acc.ownership if acc and acc.ownership else "Owner"),
            )
        except IWKError as err:
            raise HomeAssistantError(f"eBill subscription failed: {err}") from err
        _LOGGER.info("IWK eBill subscribe %s: %s", self.san, res)
        await self.coordinator.async_request_refresh()
