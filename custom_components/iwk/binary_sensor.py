"""Binary sensors for IWK."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import IWKConfigEntry, IWKCoordinator
from .entity import IWKEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: IWKConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    entities = []
    for san in coordinator.data:
        entities += [IWKPaymentDue(coordinator, san), IWKEBill(coordinator, san)]
    async_add_entities(entities)


class IWKPaymentDue(IWKEntity, BinarySensorEntity):
    _attr_translation_key = "payment_due"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:cash-clock"

    def __init__(self, coordinator: IWKCoordinator, san: str) -> None:
        super().__init__(coordinator, san, "payment_due")

    @property
    def is_on(self) -> bool | None:
        a = self.account
        return None if a is None or a.amount_due is None else a.amount_due > 0


class IWKEBill(IWKEntity, BinarySensorEntity):
    _attr_translation_key = "ebill"
    _attr_icon = "mdi:email-check-outline"

    def __init__(self, coordinator: IWKCoordinator, san: str) -> None:
        super().__init__(coordinator, san, "ebill")

    @property
    def is_on(self) -> bool | None:
        a = self.account
        if a is None or a.ebill_status is None:
            return None
        return a.ebill_status.lower() == "subscribed"
