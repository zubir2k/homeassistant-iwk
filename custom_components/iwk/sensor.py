"""Sensors for IWK."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from iwk import IWKAccount

from .const import DOMAIN
from .coordinator import IWKConfigEntry, IWKCoordinator
from .entity import IWKEntity


@dataclass(frozen=True, kw_only=True)
class IWKSensorDescription(SensorEntityDescription):
    value_fn: Callable[[IWKAccount], Any]
    attrs_fn: Callable[[IWKAccount], dict[str, Any]] | None = None
    pdf_attrs: bool = False


SENSORS: tuple[IWKSensorDescription, ...] = (
    IWKSensorDescription(
        key="amount_due",
        translation_key="amount_due",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="MYR",
        suggested_display_precision=2,
        icon="mdi:cash",
        value_fn=lambda a: a.amount_due,
        attrs_fn=lambda a: {
            "bill_no": a.bill_no,
            "address": a.address,
            "owner": a.owner_name,
            "old_san": a.old_san,
            "ctos_tag": a.ctos_tag,
            "dca_tag": a.dca_tag,
        },
    ),
    IWKSensorDescription(
        key="bill_number",
        translation_key="bill_number",
        icon="mdi:file-document-outline",
        value_fn=lambda a: a.bill_no,
    ),
    IWKSensorDescription(
        key="last_bill_amount",
        translation_key="last_bill_amount",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="MYR",
        suggested_display_precision=2,
        icon="mdi:receipt-text-outline",
        value_fn=lambda a: a.last_bill["amount"] if a.last_bill else None,
        attrs_fn=lambda a: (
            {
                "bill_no": a.last_bill["bill_no"],
                "bill_date": a.last_bill["date"].isoformat()
                if a.last_bill["date"]
                else None,
                "history": [
                    {
                        "date": h["date"].isoformat() if h["date"] else None,
                        "type": h["type"],
                        "bill_no": h["bill_no"],
                        "amount": h["amount"],
                    }
                    for h in a.history[:12]
                ],
            }
            if a.last_bill
            else {}
        ),
        pdf_attrs=True,
    ),
    IWKSensorDescription(
        key="last_bill_date",
        translation_key="last_bill_date",
        device_class=SensorDeviceClass.DATE,
        icon="mdi:calendar-text",
        value_fn=lambda a: a.last_bill["date"] if a.last_bill else None,
    ),
    IWKSensorDescription(
        key="last_payment_amount",
        translation_key="last_payment_amount",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="MYR",
        suggested_display_precision=2,
        icon="mdi:cash-check",
        value_fn=lambda a: (
            abs(a.last_payment["amount"])
            if a.last_payment and a.last_payment["amount"] is not None
            else None
        ),
    ),
    IWKSensorDescription(
        key="last_payment_date",
        translation_key="last_payment_date",
        device_class=SensorDeviceClass.DATE,
        icon="mdi:calendar-check",
        value_fn=lambda a: a.last_payment["date"] if a.last_payment else None,
    ),
    IWKSensorDescription(
        key="ebill_status",
        translation_key="ebill_status",
        icon="mdi:email-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda a: a.ebill_status,
        attrs_fn=lambda a: {
            "channel": a.ebill_channel,
            "registered": a.ebill_registered_date,
            "ownership": a.ownership,
            "account_status": a.account_status,
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: IWKConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        IWKSensor(coordinator, san, desc)
        for san in coordinator.data
        for desc in SENSORS
    )


class IWKSensor(IWKEntity, SensorEntity):
    entity_description: IWKSensorDescription
    # signed links rotate every refresh and history is bulky: keep both out of the recorder
    _unrecorded_attributes = frozenset({"pdf_url", "history"})

    def __init__(
        self, coordinator: IWKCoordinator, san: str, desc: IWKSensorDescription
    ) -> None:
        super().__init__(coordinator, san, desc.key)
        self.entity_description = desc

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.account) if self.account else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if not self.account or not self.entity_description.attrs_fn:
            return None
        attrs = self.entity_description.attrs_fn(self.account)
        if self.entity_description.pdf_attrs and attrs:
            urls = self.coordinator.pdf_urls
            last = self.account.last_bill
            attrs["pdf_url"] = urls.get((self.san, last["bill_no"])) if last else None
            for row in attrs.get("history", []):
                if row.get("bill_no") and (self.san, row["bill_no"]) in urls:
                    row["pdf_url"] = urls[(self.san, row["bill_no"])]
        return attrs
