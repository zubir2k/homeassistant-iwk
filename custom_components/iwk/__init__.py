"""IWK (Indah Water) integration."""

from __future__ import annotations

import contextlib
import html
import logging
import secrets
import time
from typing import Any

import voluptuous as vol
from aiohttp import web
from homeassistant.components import persistent_notification
from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import NoURLAvailableError, get_url

from iwk import IWKClient, IWKError

from .const import (
    ATTR_AMOUNT,
    ATTR_SAN,
    CONF_LANG,
    DEFAULT_LANG,
    DOMAIN,
    SERVICE_CREATE_PAYMENT,
    SERVICE_REFRESH,
    SERVICE_SUBSCRIBE_EBILL,
)
from .coordinator import IWKCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON]
PAYMENT_GATEWAY_URL = "https://securepay.e-ghl.com/IPG/Payment.aspx"
PAY_LINK_TTL = 15 * 60
_PAY_LINKS = f"{DOMAIN}_pay_links"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    client = IWKClient(
        session,
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        entry.data.get(CONF_LANG, DEFAULT_LANG),
    )
    coordinator = IWKCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_reload_on_options))

    _register_services(hass)
    if _PAY_LINKS not in hass.data:
        hass.data[_PAY_LINKS] = {}
        hass.http.register_view(IWKPayView(hass))
        hass.http.register_view(IWKBillPdfView(hass))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return ok


async def _reload_on_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _find(hass: HomeAssistant, san: str) -> IWKCoordinator:
    for coord in hass.data.get(DOMAIN, {}).values():
        if coord.data and san in coord.data:
            return coord
    raise HomeAssistantError(f"IWK account {san} not found")


def _register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_REFRESH):
        return

    async def refresh(call: ServiceCall) -> None:
        for coord in hass.data.get(DOMAIN, {}).values():
            await coord.async_request_refresh()

    async def subscribe(call: ServiceCall) -> ServiceResponse:
        san = call.data[ATTR_SAN]
        coord = _find(hass, san)
        acc = coord.data[san]
        try:
            res = await coord.client.subscribe_ebill(
                san,
                ownership=call.data.get("ownership") or acc.ownership or "Owner",
                channel=call.data.get("channel", "Email"),
            )
        except IWKError as err:
            raise HomeAssistantError(str(err)) from err
        await coord.async_request_refresh()
        return {"result": res}

    async def create_payment(call: ServiceCall) -> ServiceResponse:
        san = call.data[ATTR_SAN]
        coord = _find(hass, san)
        acc = coord.data[san]
        amount = call.data.get(ATTR_AMOUNT) or acc.amount_due or 0
        if amount < 1:
            raise HomeAssistantError("Nothing to pay (IWK minimum is RM1.00)")
        email = call.data.get("email") or coord.client.profile.get("email")
        if not email:
            raise HomeAssistantError("An email is required for the receipt")
        try:
            res = await coord.client.create_payment(acc, float(amount), email)
        except IWKError as err:
            raise HomeAssistantError(str(err)) from err

        pay_id = secrets.token_urlsafe(24)
        hass.data[_PAY_LINKS][pay_id] = (time.time() + PAY_LINK_TTL, res.get("data"))
        path = f"/api/{DOMAIN}/pay/{pay_id}"
        with contextlib.suppress(NoURLAvailableError):
            path = get_url(hass, prefer_external=True) + path
        name = acc.nickname or san
        persistent_notification.async_create(
            hass,
            f"Pay **RM{amount:.2f}** for {name} (bill {acc.bill_no}).\n\n"
            f"[Open eGHL payment page]({path}) (valid 15 minutes)",
            title="IWK payment",
            notification_id=f"{DOMAIN}_pay_{san}",
        )
        return {
            "path": path,
            "amount": round(float(amount), 2),
            "bill_no": acc.bill_no,
            "raw": res,
        }

    hass.services.async_register(DOMAIN, SERVICE_REFRESH, refresh)
    hass.services.async_register(
        DOMAIN,
        SERVICE_SUBSCRIBE_EBILL,
        subscribe,
        schema=vol.Schema(
            {
                vol.Required(ATTR_SAN): cv.string,
                vol.Optional("ownership"): vol.In(["Owner", "Tenant", "Others"]),
                vol.Optional("channel", default="Email"): cv.string,
            }
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_PAYMENT,
        create_payment,
        schema=vol.Schema(
            {
                vol.Required(ATTR_SAN): cv.string,
                vol.Optional(ATTR_AMOUNT): vol.Coerce(float),
                vol.Optional("email"): cv.string,
            }
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )


class IWKPayView(HomeAssistantView):
    """One-time page that auto-posts the IWK pre-order to eGHL."""

    url = f"/api/{DOMAIN}/pay/{{pay_id}}"
    name = f"api:{DOMAIN}:pay"
    requires_auth = (
        False  # opened in a plain browser tab; protected by a random one-time id
    )

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request, pay_id: str) -> web.Response:
        links: dict[str, Any] = self.hass.data.get(_PAY_LINKS, {})
        now = time.time()
        for k in [k for k, (exp, _) in links.items() if exp < now]:
            links.pop(k, None)
        item = links.pop(pay_id, None)
        if not item:
            return web.Response(
                status=404, text="Payment link expired or already used."
            )
        data = item[1]
        if isinstance(data, str) and "<form" in data.lower():
            body = data
        else:
            if isinstance(data, str):
                try:
                    import json

                    data = json.loads(data)
                except ValueError:
                    return web.Response(
                        status=502, text=f"Unexpected IWK response: {data[:300]}"
                    )
            fields = "".join(
                f"<input type='hidden' name='{html.escape(str(k))}' value='{html.escape(str(v))}'/>"
                for k, v in (data or {}).items()
            )
            body = (
                f"<form id='f' method='post' action='{PAYMENT_GATEWAY_URL}'>{fields}"
                "<noscript><button>Continue to payment</button></noscript></form>"
            )
        page = (
            "<!doctype html><html><head><meta charset='utf-8'><title>IWK payment</title></head>"
            f'<body onload="var f=document.forms[0]; if(f) f.submit();">'
            f"<p>Redirecting to eGHL...</p>{body}</body></html>"
        )
        return web.Response(text=page, content_type="text/html")


class IWKBillPdfView(HomeAssistantView):
    """Authenticated proxy for bill PDFs.

    Requires HA auth: either a logged-in session/bearer token or a signed
    `?authSig=` link (the `pdf_url` attributes, re-signed every refresh).
    The IWK-side PDF URL never leaves Home Assistant, and only bills that
    appear in the account's own history can be fetched.
    """

    url = f"/api/{DOMAIN}/bill/{{entry_id}}/{{san}}/{{ref}}.pdf"
    name = f"api:{DOMAIN}:bill_pdf"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(
        self, request: web.Request, entry_id: str, san: str, ref: str
    ) -> web.Response:
        coordinator: IWKCoordinator | None = self.hass.data.get(DOMAIN, {}).get(
            entry_id
        )
        acc = coordinator.data.get(san) if coordinator and coordinator.data else None
        row = next(
            (
                h
                for h in (acc.history if acc else [])
                if h.get("bill_no") == ref and h.get("pdf")
            ),
            None,
        )
        if not row:
            return web.Response(status=404, text="Bill not found.")
        try:
            pdf = await coordinator.client.fetch_pdf(row["pdf"])
        except IWKError as err:
            _LOGGER.warning("IWK bill PDF %s: %s", ref, err)
            return web.Response(status=502, text="Could not fetch the bill from IWK.")
        safe = "".join(c for c in ref if c.isalnum()) or "bill"
        return web.Response(
            body=pdf,
            content_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="IWK-{safe}.pdf"',
                "Cache-Control": "private, no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )
