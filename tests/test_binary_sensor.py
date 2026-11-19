"""Binary sensor tests for IWK."""

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.iwk.const import DOMAIN
from tests.conftest import TEST_SAN, make_account


async def _setup(hass, mock_account=None):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="12345",
        data={CONF_USERNAME: "testuser", CONF_PASSWORD: "pw"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_binary_sensors(hass, mock_client):
    """Test payment due and ebill binary sensors."""
    await _setup(hass)

    due = hass.states.get("binary_sensor.iwk_home_payment_due")
    assert due is not None
    assert due.state == "on"

    ebill = hass.states.get(
        "binary_sensor.iwk_home_ebill_subscribed"
    ) or hass.states.get("binary_sensor.iwk_home_ebill")
    assert ebill is not None
    assert ebill.state == "on"


async def test_binary_sensors_zero_balance(hass, mock_client):
    """Test payment due turns off when balance is zero."""
    _, init_client = mock_client
    init_client.get_accounts.side_effect = lambda: {
        TEST_SAN: make_account(amount_due=0.0, ebill_status="Pending")
    }

    await _setup(hass)

    due = hass.states.get("binary_sensor.iwk_home_payment_due")
    assert due is not None
    assert due.state == "off"

    ebill = hass.states.get(
        "binary_sensor.iwk_home_ebill_subscribed"
    ) or hass.states.get("binary_sensor.iwk_home_ebill")
    assert ebill is not None
    assert ebill.state == "off"
