"""Config flow tests for IWK."""

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResultType
from iwk import IWKAuthError, IWKCaptchaError, IWKError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.iwk.const import CONF_LANG, CONF_SCAN_INTERVAL, DOMAIN


async def test_user_flow_success(hass, mock_client):
    """Test successful user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "testuser",
            CONF_PASSWORD: "secretpassword",
            CONF_LANG: "en",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "IWK (testuser)"
    assert result["data"][CONF_USERNAME] == "testuser"
    assert result["data"][CONF_PASSWORD] == "secretpassword"
    assert result["result"].unique_id == "12345"


async def test_user_flow_invalid_auth(hass, mock_client):
    """Test user flow with incorrect credentials."""
    flow_client, _ = mock_client
    flow_client.login.side_effect = IWKAuthError("Invalid username or password")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "baduser",
            CONF_PASSWORD: "wrongpassword",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_captcha_error(hass, mock_client):
    """Test user flow with reCAPTCHA verification failure."""
    flow_client, _ = mock_client
    flow_client.login.side_effect = IWKCaptchaError("reCAPTCHA score too low")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "botuser",
            CONF_PASSWORD: "password",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "captcha"}


async def test_user_flow_cannot_connect(hass, mock_client):
    """Test user flow with network connection error."""
    flow_client, _ = mock_client
    flow_client.login.side_effect = IWKError("Network connection reset")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "user",
            CONF_PASSWORD: "password",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_already_configured(hass, mock_client):
    """Test user flow when entry with unique id is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="12345",
        data={CONF_USERNAME: "testuser", CONF_PASSWORD: "pw"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "testuser",
            CONF_PASSWORD: "pw",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow(hass, mock_client):
    """Test re-authentication flow updating credentials."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="12345",
        data={CONF_USERNAME: "testuser", CONF_PASSWORD: "oldpassword"},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "newpassword"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "newpassword"


async def test_options_flow(hass, mock_client):
    """Test updating integration options (scan interval)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="12345",
        data={CONF_USERNAME: "testuser", CONF_PASSWORD: "password"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_SCAN_INTERVAL: 12},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_SCAN_INTERVAL] == 12
