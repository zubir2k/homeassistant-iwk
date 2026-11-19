"""Base entity for IWK."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from iwk import IWKAccount

from .const import DOMAIN
from .coordinator import IWKCoordinator


class IWKEntity(CoordinatorEntity[IWKCoordinator]):
    """One IWK sewerage account = one device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: IWKCoordinator, san: str, key: str) -> None:
        super().__init__(coordinator)
        self.san = san
        self._attr_unique_id = f"{san}_{key}"
        acc = coordinator.data.get(san) if coordinator.data else None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, san)},
            name=f"IWK {acc.nickname if acc and acc.nickname else san}",
            manufacturer="Indah Water Konsortium",
            model="Sewerage account",
            serial_number=san,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://customerportal.iwk.com.my/en/manage_sewerage_account",
        )

    @property
    def account(self) -> IWKAccount | None:
        return self.coordinator.data.get(self.san) if self.coordinator.data else None

    @property
    def available(self) -> bool:
        return super().available and self.account is not None
