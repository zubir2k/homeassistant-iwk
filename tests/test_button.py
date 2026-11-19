"""Button entity tests for IWK."""

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.iwk.const import DOMAIN
from tests.conftest import TEST_SAN, make_account


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


async def test_refresh_button(hass, mock_client):
    """Test pressing the manual refresh button."""
    await _setup(hass)
    _, init_client = mock_client
    init_client.get_accounts.reset_mock()

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.iwk_home_refresh"},
        blocking=True,
    )
    init_client.get_accounts.assert_awaited()


async def test_subscribe_ebill_button(hass, mock_client):
    """Test pressing the subscribe ebill button."""
    _, init_client = mock_client
    # Set to Not Subscribed so button can proceed
    init_client.get_accounts.side_effect = lambda: {
        TEST_SAN: make_account(ebill_status="Not Subscribed")
    }

    entry = await _setup(hass)

    # Enable the button which is disabled by default
    registry = er.async_get(hass)
    entity_id = "button.iwk_home_subscribe_to_ebill"
    button_entry = registry.async_get(entity_id)
    if button_entry and button_entry.disabled:
        registry.async_update_entity(entity_id, disabled_by=None)
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": entity_id},
        blocking=True,
    )
    init_client.subscribe_ebill.assert_awaited_with(TEST_SAN, ownership="Owner")
