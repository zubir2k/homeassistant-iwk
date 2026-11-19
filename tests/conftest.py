"""Fixtures for IWK tests."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from iwk import IWKAccount

pytest_plugins = ["pytest_homeassistant_custom_component"]

TEST_SAN = "01234567890"


def make_account(
    san: str = TEST_SAN,
    amount_due: float = 32.0,
    ebill_status: str = "Subscribed",
) -> IWKAccount:
    """Create a mock IWKAccount populated with realistic billing history."""
    history = [
        {
            "type": "Bill",
            "is_payment": False,
            "date": date(2026, 9, 1),
            "bill_no": "10000000001",
            "amount": 32.0,
            "pdf": "https://customerportal.iwk.com.my/bill/10000000001.pdf",
        },
        {
            "type": "Payment",
            "is_payment": True,
            "date": date(2026, 8, 15),
            "bill_no": "PAY-1",
            "amount": -32.0,
            "pdf": None,
        },
    ]
    return IWKAccount(
        san=san,
        nickname="Home",
        owner_name="ZUBIR JAMAL",
        address="NO 1 JALAN CONTOH, KAJANG",
        amount_due=amount_due,
        bill_no="10000000001",
        old_san="01234567",
        ctos_tag=None,
        dca_tag=None,
        ebill_status=ebill_status,
        ebill_channel="Email",
        ebill_registered_date="2026-01-01",
        ownership="Owner",
        account_status="Active",
        history=history,
    )


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations in Home Assistant test harness."""
    yield


@pytest.fixture(autouse=True)
async def cleanup_entries(hass):
    """Clean up and unload any config entries after each test."""
    yield
    from homeassistant.config_entries import ConfigEntryState

    from custom_components.iwk.const import DOMAIN

    for entry in list(hass.config_entries.async_entries(DOMAIN)):
        if entry.state is ConfigEntryState.LOADED:
            await hass.config_entries.async_unload(entry.entry_id)
            await hass.async_block_till_done()


@pytest.fixture
def mock_client():
    """Patch the IWKClient everywhere it is constructed."""
    with (
        patch("custom_components.iwk.async_get_clientsession"),
        patch("custom_components.iwk.config_flow.async_get_clientsession"),
        patch("custom_components.iwk.IWKClient", autospec=True) as init_cls,
        patch("custom_components.iwk.config_flow.IWKClient", autospec=True) as flow_cls,
    ):
        for cls in (init_cls, flow_cls):
            client = cls.return_value
            client.profile = {
                "memberid": "12345",
                "username": "testuser",
                "email": "test@example.com",
            }
            client.login = AsyncMock(return_value="mock-token")
            client.get_profile = AsyncMock(
                return_value={
                    "memberid": "12345",
                    "username": "testuser",
                    "email": "test@example.com",
                }
            )
            client.get_accounts = AsyncMock(
                side_effect=lambda: {TEST_SAN: make_account()}
            )
            client.create_payment = AsyncMock(
                return_value={"status": True, "data": {"TransactionID": "TX-12345"}}
            )
            client.subscribe_ebill = AsyncMock(
                return_value={"status": True, "msg": "Subscribed"}
            )
            client.fetch_pdf = AsyncMock(return_value=b"%PDF-1.4 mock pdf content")
        yield flow_cls.return_value, init_cls.return_value
