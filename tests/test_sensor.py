"""Sensor entity and device registry tests for IWK."""

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import device_registry as dr
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


async def test_sensors(hass, mock_client):
    """Test all sensor states and attributes."""
    entry = await _setup(hass)
    prefix = "sensor.iwk_home_"

    amount_due = hass.states.get(prefix + "amount_due")
    assert amount_due is not None
    assert amount_due.state == "32.0"
    assert amount_due.attributes["unit_of_measurement"] == "MYR"
    assert amount_due.attributes["address"] == "NO 1 JALAN CONTOH, KAJANG"
    assert amount_due.attributes["owner"] == "ZUBIR JAMAL"

    bill_number = hass.states.get(prefix + "bill_number")
    assert bill_number is not None
    assert bill_number.state == "10000000001"

    last_bill_amount = hass.states.get(prefix + "last_bill_amount")
    assert last_bill_amount is not None
    assert last_bill_amount.state == "32.0"
    assert len(last_bill_amount.attributes["history"]) == 1

    last_bill_date = hass.states.get(prefix + "last_bill_date")
    assert last_bill_date is not None
    assert last_bill_date.state == "2026-09-01"

    last_payment_amount = hass.states.get(prefix + "last_payment_amount")
    assert last_payment_amount is not None
    assert last_payment_amount.state == "32.0"

    last_payment_date = hass.states.get(prefix + "last_payment_date")
    assert last_payment_date is not None
    assert last_payment_date.state == "2026-08-15"

    ebill_status = hass.states.get(prefix + "ebill_status")
    assert ebill_status is not None
    assert ebill_status.state == "Subscribed"

    # Test device registry registration
    reg = dr.async_get(hass)
    device = reg.async_get_device_by_identifier((DOMAIN, TEST_SAN), entry.entry_id)
    assert device is not None
    assert device.manufacturer == "Indah Water Konsortium"
    assert device.model == "Sewerage account"
    assert device.serial_number == TEST_SAN
