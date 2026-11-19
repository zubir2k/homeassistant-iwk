"""Tests for integration lifecycle, views, and services."""

from urllib.parse import urlparse

import pytest
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.iwk.const import DOMAIN
from tests.conftest import TEST_SAN


async def _setup(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="12345",
        data={CONF_USERNAME: "testuser", CONF_PASSWORD: "pw"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_setup_and_unload(hass, mock_client):
    """Test full setup and teardown lifecycle."""
    entry = await _setup(hass)
    assert entry.entry_id in hass.data[DOMAIN]

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.entry_id not in hass.data[DOMAIN]


async def test_service_refresh(hass, mock_client):
    """Test iwk.refresh service call."""
    await _setup(hass)
    _, init_client = mock_client
    init_client.get_accounts.reset_mock()

    await hass.services.async_call(DOMAIN, "refresh", blocking=True)
    init_client.get_accounts.assert_awaited()


async def test_service_subscribe_ebill(hass, mock_client):
    """Test iwk.subscribe_ebill service call."""
    await _setup(hass)
    _, init_client = mock_client

    await hass.services.async_call(
        DOMAIN,
        "subscribe_ebill",
        {"san": TEST_SAN, "ownership": "Owner", "channel": "Email"},
        blocking=True,
    )
    init_client.subscribe_ebill.assert_awaited_with(
        TEST_SAN, ownership="Owner", channel="Email"
    )


async def test_service_create_payment_link(hass, mock_client):
    """Test iwk.create_payment_link service."""
    await _setup(hass)
    _, init_client = mock_client

    response = await hass.services.async_call(
        DOMAIN,
        "create_payment_link",
        {"san": TEST_SAN, "amount": 32.0, "email": "test@example.com"},
        blocking=True,
        return_response=True,
    )
    assert response["amount"] == 32.0
    assert response["bill_no"] == "10000000001"
    assert "/api/iwk/pay/" in response["path"]


async def test_service_create_payment_link_invalid_amount(hass, mock_client):
    """Test payment link service validation for sub-minimum payment."""
    await _setup(hass)

    with pytest.raises(HomeAssistantError, match="Nothing to pay"):
        await hass.services.async_call(
            DOMAIN,
            "create_payment_link",
            {"san": TEST_SAN, "amount": 0.50, "email": "test@example.com"},
            blocking=True,
        )


async def test_pay_view(hass, mock_client, hass_client):
    """Test eGHL payment redirection HTML view."""
    await _setup(hass)
    client = await hass_client()

    response = await hass.services.async_call(
        DOMAIN,
        "create_payment_link",
        {"san": TEST_SAN, "amount": 32.0, "email": "test@example.com"},
        blocking=True,
        return_response=True,
    )
    pay_path = urlparse(response["path"]).path

    resp = await client.get(pay_path)
    assert resp.status == 200
    text = await resp.text()
    assert "Redirecting to eGHL" in text

    # Second fetch should 404 (one-time link)
    resp_again = await client.get(pay_path)
    assert resp_again.status == 404


async def test_bill_pdf_view(hass, mock_client, hass_client):
    """Test authenticated proxy view for bill PDFs."""
    entry = await _setup(hass)
    client = await hass_client()

    pdf_path = f"/api/iwk/bill/{entry.entry_id}/{TEST_SAN}/10000000001.pdf"
    resp = await client.get(pdf_path)
    assert resp.status == 200
    assert resp.headers["Content-Type"] == "application/pdf"
    content = await resp.read()
    assert content == b"%PDF-1.4 mock pdf content"


async def test_bill_pdf_view_not_found(hass, mock_client, hass_client):
    """Test bill PDF proxy with unknown bill reference."""
    entry = await _setup(hass)
    client = await hass_client()

    pdf_path = f"/api/iwk/bill/{entry.entry_id}/{TEST_SAN}/non_existent_bill.pdf"
    resp = await client.get(pdf_path)
    assert resp.status == 404
