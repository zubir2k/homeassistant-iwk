![IndahWater](/custom_components/iwk/brand/logo.png)

[![GitHub Repo stars](https://img.shields.io/github/stars/zubir2k/homeassistant-iwk?style=social)](https://github.com/zubir2k/homeassistant-iwk/stargazers)
[![hacs_badge](https://img.shields.io/badge/HACS-Integration-41BDF5.svg)](https://github.com/hacs/integration)
[![Buy](https://img.shields.io/badge/Belanja-Coffee-yellow.svg)](https://zubirco.de/buymecoffee)
[![GitHub Release](https://img.shields.io/github/release/zubir2k/homeassistant-iwk.svg)](https://github.com/zubir2k/homeassistant-iwk/releases/)

An **unofficial**, community-built Home Assistant custom integration for [Indah Water Konsortium (IWK)](https://www.iwk.com.my) sewerage accounts. Monitor outstanding balances, bill history, payments, and view bill PDFs directly inside Home Assistant.

---

## Features

- **Single Login, Multiple SANs**: Discovers and manages every Sewerage Account Number (SAN) linked to your IWK portal login.
- **Balance & Due Alerts**: Tracks amount due, bill numbers, and provides a binary sensor alert when payment is required.
- **Bill & Payment History**: Access past billing records, payment amounts, and transaction dates.
- **Bill PDF Viewing**: Generates secure, signed proxy URLs to view and download official IWK bill PDFs directly from Home Assistant.
- **Payment Link Action**: One-click action to create a secure pre-order checkout link for eGHL payment gateway.
- **eBill Status & Subscription**: View registered eBill delivery channels (Email/SMS) and subscribe directly from Home Assistant.
- **Zero Browser Overhead**: Automatically mints reCAPTCHA v3 tokens over lightweight HTTP requests without requiring Chrome, Puppeteer, or Selenium.
- **Resilient Transport**: Powered by [`python-iwk`](https://pypi.org/project/python-iwk/) with built-in exponential backoff and jitter against transient gateway hiccups.

---

## Installation

### With Marketplace / HACS (Recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=zubir2k&repository=homeassistant-iwk&category=integration)

> [!TIP]
> If you are unable to use the button above, navigate to **HACS → Integrations**, search for `IWK (Indah Water)`, and click **Download**.

### Manual Installation

1. Copy the `custom_components/iwk` folder from this repository into your Home Assistant's `config/custom_components/` directory.
2. Restart Home Assistant.
3. Proceed to the [Setup](#setup) section.

> [!WARNING]
> If installing manually, subscribe to repository releases to be notified of updates.

---

## Setup

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=iwk)

> [!TIP]
> If the button above does not open directly:
> 1. Go to **Settings → Devices & Services**.
> 2. Click **+ Add Integration** in the bottom right corner.
> 3. Search for **IWK (Indah Water)**.

Enter the registered email / username and password you use on the [IWK Customer Portal](https://customerportal.iwk.com.my). All active sewerage accounts (SANs) will be discovered automatically and registered as separate devices.

---

## Entities (Per Sewerage Account / SAN)

| Entity | Type | Unit / State | Notes |
| :--- | :--- | :--- | :--- |
| `sensor.<name>_amount_due` | Sensor | `MYR` | Total outstanding balance. Attributes: `owner`, `address`, `bill_no`, `old_san`, `ctos_tag`. |
| `sensor.<name>_bill_number` | Sensor | Text | Latest bill reference number. |
| `sensor.<name>_last_bill_amount` | Sensor | `MYR` | Latest bill charge. Attributes: `bill_date`, `history` (12 bills), `pdf_url`. |
| `sensor.<name>_last_bill_date` | Sensor | Date | Date of the most recent bill. |
| `sensor.<name>_last_payment_amount` | Sensor | `MYR` | Amount paid in the latest payment transaction. |
| `sensor.<name>_last_payment_date` | Sensor | Date | Timestamp of the latest recorded payment. |
| `sensor.<name>_ebill_status` | Sensor (Diag) | Text | eBill registration status. Attributes: `channel`, `registered_date`, `ownership`. |
| `binary_sensor.<name>_payment_due` | Binary Sensor | `Problem` | `on` when `amount_due > 0` (outstanding balance unpaid). |
| `binary_sensor.<name>_ebill` | Binary Sensor | Status | `on` when account is subscribed to eBill delivery. |
| `button.<name>_refresh` | Button (Diag) | Action | Manually polls IWK portal for immediate status updates. |
| `button.<name>_subscribe_ebill` | Button (Config)| Action | One-click button to subscribe the account to eBill delivery (disabled by default). |

---

## Actions (Services)

The integration exposes three actionable services:

### 1. `iwk.refresh`
Trigger an immediate background refresh across all configured IWK accounts.

```yaml
action: iwk.refresh
```

### 2. `iwk.create_payment_link`
Generate a temporary, one-time checkout URL that automatically forwards to the IWK eGHL payment gateway with your bill pre-filled.

```yaml
action: iwk.create_payment_link
data:
  san: "01234567890"
  amount: 32.00
  email: "user@example.com"
```

### 3. `iwk.subscribe_ebill`
Subscribe a sewerage account to paperless eBill delivery by email.

```yaml
action: iwk.subscribe_ebill
data:
  san: "01234567890"
  ownership: "Owner"
  channel: "Email"
```

---

## How It Works

- **Polling Frequency**: IWK sewerage bills are issued on a semi-annual or quarterly basis, so polling runs automatically every **6 hours** to track payments and new statements without unnecessary load.
- **Secure Bill Proxy**: IWK bill URLs require valid session credentials. The integration transparently proxies PDF requests through an internal, signed URL (`/api/iwk/bill/...`) so you can view bill PDFs directly in Lovelace cards or automations securely.

---

## License

This project is licensed under the [MIT License](LICENSE).
