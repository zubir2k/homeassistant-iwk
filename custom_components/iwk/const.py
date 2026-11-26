"""Constants for the IWK integration."""

from __future__ import annotations

DOMAIN = "iwk"
VERSION = "0.1.2"

API_BASE = "https://customerportal.iwk.com.my/api/{lang}/5"
RECAPTCHA_SITE_KEY = "6Le7JKUrAAAAABiDWLLeqHj9iLVVxuKmwV1O6IMM"
RECAPTCHA_ACTION = "appLogin"

CONF_SCAN_INTERVAL = "scan_interval"
CONF_LANG = "lang"

DEFAULT_SCAN_INTERVAL_HOURS = 6
DEFAULT_LANG = "en"

SERVICE_CREATE_PAYMENT = "create_payment_link"
SERVICE_SUBSCRIBE_EBILL = "subscribe_ebill"
SERVICE_REFRESH = "refresh"

ATTR_SAN = "san"
ATTR_AMOUNT = "amount"
