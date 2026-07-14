"""Amazon (AU) price provider with two selectable backends.

Set ``AMAZON_BACKEND`` to choose:

* ``keepa``  (default) — Keepa API. A paid subscription with **no** Amazon
  Associates requirement. Good for price history + current price.
    - ``KEEPA_API_KEY``
* ``paapi`` — official Amazon Product Advertising API 5.0. Requires an approved
  Associates account and ongoing qualifying sales; fresh accounts are throttled.
    - ``PAAPI_ACCESS_KEY``, ``PAAPI_SECRET_KEY``, ``PAAPI_PARTNER_TAG``

The watchlist ``product_id`` is an ASIN for both backends.
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import os
from typing import Optional

import requests

from ..models import PriceResult
from .base import Provider, ProviderError

PRODUCT_URL = "https://www.amazon.com.au/dp/{asin}"


def _make_backend() -> "AmazonBackend":
    backend = (os.environ.get("AMAZON_BACKEND") or "keepa").strip().lower()
    if backend == "paapi":
        return PaApiBackend()
    return KeepaBackend()


class AmazonProvider(Provider):
    name = "amazon"
    label = "Amazon AU"

    def __init__(self, backend: "Optional[AmazonBackend]" = None):
        self.backend = backend or _make_backend()

    def is_available(self) -> bool:
        return self.backend.is_available()

    def unavailable_reason(self) -> Optional[str]:
        return self.backend.unavailable_reason()

    def fetch(self, product_id: str, ref: str) -> PriceResult:
        name, price, was = self.backend.lookup(product_id)
        if price is None:
            raise ProviderError("no current price available for ASIN")
        return self._result(
            ref,
            product_name=name or ref,
            current_price=price,
            was_price=was,
            currency="AUD",
            url=PRODUCT_URL.format(asin=product_id),
            extra={"backend": self.backend.key},
        )


class AmazonBackend:
    key = "base"

    def is_available(self) -> bool:  # pragma: no cover - overridden
        return False

    def unavailable_reason(self) -> Optional[str]:  # pragma: no cover
        return None

    def lookup(self, asin: str):  # pragma: no cover - overridden
        """Return ``(name, current_price, was_price)``."""
        raise NotImplementedError


class KeepaBackend(AmazonBackend):
    """Keepa API backend. Docs: https://keepa.com/#!api

    Keepa returns prices in cents and uses AU domain id 5. The ``csv`` arrays
    hold historical [timestamp, value, ...] pairs; index 0 is the Amazon price,
    index 1 the marketplace/new price. ``-1`` means "no offer".
    """

    key = "keepa"
    DOMAIN_AU = 5
    ENDPOINT = "https://api.keepa.com/product"

    def __init__(self, api_key: Optional[str] = None, session: Optional[requests.Session] = None,
                 timeout: float = 30.0):
        self.api_key = api_key if api_key is not None else os.environ.get("KEEPA_API_KEY")
        self.session = session or requests.Session()
        self.timeout = timeout

    def is_available(self) -> bool:
        return bool(self.api_key)

    def unavailable_reason(self) -> Optional[str]:
        if not self.api_key:
            return "KEEPA_API_KEY not set (subscribe at keepa.com)"
        return None

    def lookup(self, asin: str):
        params = {
            "key": self.api_key,
            "domain": self.DOMAIN_AU,
            "asin": asin,
            "stats": 1,
            "history": 0,
        }
        try:
            resp = self.session.get(self.ENDPOINT, params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            raise ProviderError(f"network error: {exc}") from exc
        if resp.status_code == 429:
            raise ProviderError("Keepa rate/token limit reached (429)")
        if resp.status_code >= 400:
            raise ProviderError(f"Keepa HTTP {resp.status_code}")
        data = resp.json()
        products = data.get("products") or []
        if not products:
            raise ProviderError(f"ASIN {asin} not found on Keepa")
        product = products[0]
        name = product.get("title")
        current = _keepa_current(product)
        was = _keepa_reference(product)
        # Only treat "was" as a discount when it is genuinely higher.
        if current is not None and was is not None and was <= current:
            was = None
        return name, current, was


def _keepa_cents(value) -> Optional[float]:
    if value is None or value == -1:
        return None
    try:
        return round(int(value) / 100.0, 2)
    except (TypeError, ValueError):
        return None


def _keepa_current(product: dict) -> Optional[float]:
    stats = product.get("stats") or {}
    current = stats.get("current") or []
    # stats.current indices mirror the csv indices: 0=Amazon, 1=New.
    for idx in (1, 0):
        if idx < len(current):
            price = _keepa_cents(current[idx])
            if price is not None:
                return price
    return None


def _keepa_reference(product: dict) -> Optional[float]:
    """Use the recent average as the reference/"was" price for drop detection."""
    stats = product.get("stats") or {}
    for field in ("avg30", "avg90", "avg"):
        avg = stats.get(field) or []
        for idx in (1, 0):
            if idx < len(avg):
                price = _keepa_cents(avg[idx])
                if price is not None:
                    return price
    return None


class PaApiBackend(AmazonBackend):
    """Amazon Product Advertising API 5.0 backend (GetItems, AU marketplace).

    Implements the AWS SigV4 signing PA-API 5.0 requires. Only the small subset
    needed for a price/availability lookup is included.
    """

    key = "paapi"
    HOST = "webservices.amazon.com.au"
    REGION = "us-west-2"  # PA-API AU requests are signed against us-west-2.
    MARKETPLACE = "www.amazon.com.au"
    PATH = "/paapi5/getitems"
    SERVICE = "ProductAdvertisingAPI"
    TARGET = "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.GetItems"

    def __init__(self, access_key=None, secret_key=None, partner_tag=None,
                 session: Optional[requests.Session] = None, timeout: float = 30.0):
        self.access_key = access_key if access_key is not None else os.environ.get("PAAPI_ACCESS_KEY")
        self.secret_key = secret_key if secret_key is not None else os.environ.get("PAAPI_SECRET_KEY")
        self.partner_tag = partner_tag if partner_tag is not None else os.environ.get("PAAPI_PARTNER_TAG")
        self.session = session or requests.Session()
        self.timeout = timeout

    def is_available(self) -> bool:
        return bool(self.access_key and self.secret_key and self.partner_tag)

    def unavailable_reason(self) -> Optional[str]:
        missing = [n for n, v in (
            ("PAAPI_ACCESS_KEY", self.access_key),
            ("PAAPI_SECRET_KEY", self.secret_key),
            ("PAAPI_PARTNER_TAG", self.partner_tag),
        ) if not v]
        if missing:
            return f"missing {', '.join(missing)} (requires Amazon Associates approval)"
        return None

    def lookup(self, asin: str):
        payload = {
            "ItemIds": [asin],
            "Resources": [
                "ItemInfo.Title",
                "Offers.Listings.Price",
                "Offers.Listings.SavingBasis",
            ],
            "PartnerTag": self.partner_tag,
            "PartnerType": "Associates",
            "Marketplace": self.MARKETPLACE,
        }
        body = json.dumps(payload)
        headers = self._signed_headers(body)
        url = f"https://{self.HOST}{self.PATH}"
        try:
            resp = self.session.post(url, data=body, headers=headers, timeout=self.timeout)
        except requests.RequestException as exc:
            raise ProviderError(f"network error: {exc}") from exc
        if resp.status_code == 429:
            raise ProviderError("PA-API throttled (429) — request rate scales with sales")
        if resp.status_code >= 400:
            raise ProviderError(f"PA-API HTTP {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        items = (data.get("ItemsResult") or {}).get("Items") or []
        if not items:
            raise ProviderError(f"ASIN {asin} returned no items")
        return self._parse_item(items[0])

    @staticmethod
    def _parse_item(item: dict):
        title = (((item.get("ItemInfo") or {}).get("Title") or {}).get("DisplayValue"))
        listings = ((item.get("Offers") or {}).get("Listings") or [])
        price = was = None
        if listings:
            listing = listings[0]
            price_obj = listing.get("Price") or {}
            price = price_obj.get("Amount")
            saving_basis = listing.get("SavingBasis") or {}
            was = saving_basis.get("Amount")
        if price is not None and was is not None and was <= price:
            was = None
        return title, price, was

    # --- AWS SigV4 signing ------------------------------------------------
    def _signed_headers(self, body: str) -> dict:
        now = datetime.datetime.now(datetime.timezone.utc)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")

        canonical_headers = (
            f"content-encoding:amz-1.0\n"
            f"content-type:application/json; charset=utf-8\n"
            f"host:{self.HOST}\n"
            f"x-amz-date:{amz_date}\n"
            f"x-amz-target:{self.TARGET}\n"
        )
        signed_headers = "content-encoding;content-type;host;x-amz-date;x-amz-target"
        payload_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
        canonical_request = "\n".join([
            "POST", self.PATH, "", canonical_headers, signed_headers, payload_hash,
        ])

        algorithm = "AWS4-HMAC-SHA256"
        scope = f"{date_stamp}/{self.REGION}/{self.SERVICE}/aws4_request"
        string_to_sign = "\n".join([
            algorithm, amz_date, scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ])

        signing_key = self._signature_key(date_stamp)
        signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

        authorization = (
            f"{algorithm} Credential={self.access_key}/{scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )
        return {
            "content-encoding": "amz-1.0",
            "content-type": "application/json; charset=utf-8",
            "host": self.HOST,
            "x-amz-date": amz_date,
            "x-amz-target": self.TARGET,
            "Authorization": authorization,
        }

    def _signature_key(self, date_stamp: str) -> bytes:
        def _sign(key: bytes, msg: str) -> bytes:
            return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

        k_date = _sign(f"AWS4{self.secret_key}".encode("utf-8"), date_stamp)
        k_region = _sign(k_date, self.REGION)
        k_service = _sign(k_region, self.SERVICE)
        return _sign(k_service, "aws4_request")
