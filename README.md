# PriceWatch — multi-provider grocery & retail price monitor

Track price drops across multiple retailers from a single watchlist. PriceWatch
uses an **official API wherever one exists** and degrades gracefully to
best-effort sources where one does not. Each feed only activates when its
credentials are present, so you can run with whatever you've set up and the rest
is skipped.

## Providers at a glance

| Provider | Key | Source | Status |
|---|---|---|---|
| **Woolworths** | `woolworths` | Official Supermarkets API — [developer.woolworths.com.au](https://developer.woolworths.com.au) | ✅ Official (needs API key) |
| **Amazon AU** | `amazon` | PA-API 5.0 **or** Keepa | ✅ Official / paid (see below) |
| **Coles** | `coles` | Third-party wrapper (RapidAPI etc.) | ⚠️ Best-effort — Coles has **no** official API |
| **Chemist Warehouse** | `chemist_warehouse` | Legacy Selenium scraper | 🧪 Fallback (no API exists) |
| **Woolworths (scrape)** | `woolworths_scrape` | Legacy Selenium scraper | 🧪 Fallback for Woolworths |

**Why this split?**
- **Woolworths** publishes a genuine developer portal (Google sign-in, docs, API
  key). Cleanest, most durable feed — no proxy, no scraping.
- **Amazon** is official via **PA-API 5.0**, but that requires an approved
  Amazon Associates account and ~3 qualifying sales / 180 days, and throttles
  fresh accounts. **Keepa** is a paid alternative with no affiliate requirement —
  the default backend here.
- **Coles** has no public API. The `api.coles.com.au` endpoint is internal and
  against their ToS. This tool talks to a *third-party wrapper* instead: you
  outsource the risk (it can break or change shape without notice), so the Coles
  provider is designed to fail softly and is skipped when unconfigured.

## Install

```bash
pip install -r requirements.txt
```

Only `requests` is required for the API providers. `selenium` + `beautifulsoup4`
are needed only for the Selenium scrape providers, and `sendgrid` / `plyer` only
for notifications.

## Configure credentials

Set only the ones you want to use (as environment variables or a `.env`):

```bash
# Woolworths official API
export WOOLWORTHS_API_KEY="your-subscription-key"
# Optional overrides if your portal tier documents different values:
# export WOOLWORTHS_API_BASE="https://api.woolworths.com.au"
# export WOOLWORTHS_AUTH_HEADER="Ocp-Apim-Subscription-Key"   # or "Authorization"
# export WOOLWORTHS_PRODUCT_PATH="/apis/ui/product/detail/{id}"

# Amazon — choose a backend
export AMAZON_BACKEND="keepa"            # "keepa" (default) or "paapi"
export KEEPA_API_KEY="your-keepa-key"
# ...or for PA-API 5.0:
# export AMAZON_BACKEND="paapi"
# export PAAPI_ACCESS_KEY="..."
# export PAAPI_SECRET_KEY="..."
# export PAAPI_PARTNER_TAG="yourtag-20"

# Coles — third-party wrapper (e.g. RapidAPI)
export COLES_API_KEY="your-rapidapi-key"
# export COLES_API_HOST="coles-product-price-api.p.rapidapi.com"
# export COLES_API_BASE="https://coles-product-price-api.p.rapidapi.com"
# export COLES_PRODUCT_PATH="/product/{id}"

# Notifications (optional)
export SENDGRID_API_KEY="..."            # email digest
export PRICEWATCH_EMAIL_TO="you@example.com"

# Behaviour
export PRICEWATCH_DROP_THRESHOLD="20"    # flag drops >= this %
```

> **Note on Woolworths field mapping.** The exact request/response contract lives
> behind the developer portal and can vary by subscription tier. The adapter is
> written to be configurable (base URL, auth header, path) and the JSON→price
> mapping is isolated in `WoolworthsProvider._parse` — a one-line change to match
> what your portal documents.

## Watchlist

`watchlist.json` groups product IDs by provider. The label (key) is for your
reference; the value is the ID that provider needs.

```json
{
  "Woolworths": { "Milo": "192985" },
  "Coles":      { "Full Cream Milk 2L": "coles-product-id" },
  "Amazon":     { "Echo Dot": "B09B8V1LZ3" },
  "Chemist_Warehouse": { "Incentiv Choc": "74342" }
}
```

**Finding IDs**
- **Woolworths:** the number in `woolworths.com.au/shop/productdetails/{id}/...`
- **Chemist Warehouse:** the number in `chemistwarehouse.com.au/buy/{id}/...`
- **Amazon:** the **ASIN** (in the product URL `/dp/{ASIN}` or the details table)
- **Coles:** the product id used by your chosen wrapper

## Run

```bash
python -m pricewatch                 # uses watchlist.json, threshold 20%
python -m pricewatch --threshold 15 --no-email
python -m pricewatch --json          # machine-readable output
python price-drop.py                 # legacy entry point (same thing)
```

Output lists each provider's items with current price, "was" price and the
computed drop, flags everything at/over the threshold, and (unless suppressed)
sends a desktop toast and/or email digest.

## Tests

```bash
python -m pytest
```

The suite mocks all HTTP, so it runs offline and never touches a live API.

## Architecture

```
pricewatch/
  models.py            PriceResult / WatchItem
  config.py            env → provider registry, aliases, threshold
  runner.py            load watchlist → check per provider → RunReport
  notify.py            digest formatting + SendGrid/desktop delivery
  cli.py               argparse entry point
  providers/
    base.py            Provider ABC + ProviderError
    woolworths.py      official API
    amazon.py          PA-API 5.0 + Keepa backends
    coles.py           best-effort third-party wrapper
    scrape.py          legacy Selenium (Chemist Warehouse + Woolies fallback)
```

Adding a provider = subclass `Provider`, implement `is_available()` + `fetch()`,
and register it in `config.build_providers()`.
