"""Woolworths official Supermarkets API provider.

Woolworths runs a real developer portal at https://developer.woolworths.com.au
where you register (Google sign-in), read the docs, and obtain an API key. The
Supermarkets APIs expose product lookups by search term, by EAN/UPC barcode, by
Woolworths Product ID, and by aisle/category.

Because the exact request/response contract lives behind that portal (and may
differ per subscription tier), this adapter is written to be *configurable*:

* ``WOOLWORTHS_API_BASE``   – API base URL (default below)
* ``WOOLWORTHS_API_KEY``    – your subscription key
* ``WOOLWORTHS_AUTH_HEADER``– header name the key is sent in
                              (default ``Ocp-Apim-Subscription-Key``, the common
                              Azure API Management style; some tiers use
                              ``Authorization: Bearer``)
* ``WOOLWORTHS_PRODUCT_PATH`` – path template for a by-id lookup, with ``{id}``

The JSON field mapping is factored into :meth:`_parse` so it is a one-line
change to match whatever your portal documents. Defaults follow the field names
used by the public woolworths.com.au product endpoint.
"""

from __future__ import annotations

import os
from typing import Any, Optional

import requests

from ..models import PriceResult
from .base import Provider, ProviderError

DEFAULT_BASE = "https://api.woolworths.com.au"
# The public site uses this shape; the developer portal may document another.
DEFAULT_PRODUCT_PATH = "/apis/ui/product/detail/{id}"
DEFAULT_AUTH_HEADER = "Ocp-Apim-Subscription-Key"
PRODUCT_URL = "https://www.woolworths.com.au/shop/productdetails/{id}"


class WoolworthsProvider(Provider):
    name = "woolworths"
    label = "Woolworths"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        auth_header: Optional[str] = None,
        product_path: Optional[str] = None,
        session: Optional[requests.Session] = None,
        timeout: float = 20.0,
    ):
        self.api_key = api_key if api_key is not None else os.environ.get("WOOLWORTHS_API_KEY")
        self.base_url = (base_url or os.environ.get("WOOLWORTHS_API_BASE") or DEFAULT_BASE).rstrip("/")
        self.auth_header = auth_header or os.environ.get("WOOLWORTHS_AUTH_HEADER") or DEFAULT_AUTH_HEADER
        self.product_path = product_path or os.environ.get("WOOLWORTHS_PRODUCT_PATH") or DEFAULT_PRODUCT_PATH
        self.timeout = timeout
        self.session = session or requests.Session()

    def is_available(self) -> bool:
        return bool(self.api_key)

    def unavailable_reason(self) -> Optional[str]:
        if not self.api_key:
            return "WOOLWORTHS_API_KEY not set (register at developer.woolworths.com.au)"
        return None

    def _headers(self) -> dict:
        headers = {"Accept": "application/json"}
        if self.auth_header.lower() == "authorization":
            headers["Authorization"] = f"Bearer {self.api_key}"
        else:
            headers[self.auth_header] = self.api_key or ""
        return headers

    def fetch(self, product_id: str, ref: str) -> PriceResult:
        path = self.product_path.format(id=product_id)
        url = f"{self.base_url}{path}"
        try:
            resp = self.session.get(url, headers=self._headers(), timeout=self.timeout)
        except requests.RequestException as exc:
            raise ProviderError(f"network error: {exc}") from exc

        if resp.status_code == 404:
            raise ProviderError(f"product {product_id} not found (404)")
        if resp.status_code in (401, 403):
            raise ProviderError(f"auth rejected ({resp.status_code}) — check WOOLWORTHS_API_KEY")
        if resp.status_code == 429:
            raise ProviderError("rate limited (429)")
        if resp.status_code >= 400:
            raise ProviderError(f"HTTP {resp.status_code}")

        try:
            payload = resp.json()
        except ValueError as exc:
            raise ProviderError(f"non-JSON response: {exc}") from exc

        return self._parse(payload, product_id, ref)

    def _parse(self, payload: Any, product_id: str, ref: str) -> PriceResult:
        """Map the API payload onto a :class:`PriceResult`.

        The public product endpoint nests fields under ``Product``; other tiers
        may return the product at the top level. We handle both, and treat the
        field names as the single place to adjust for your portal's schema.
        """
        product = payload
        if isinstance(payload, dict) and isinstance(payload.get("Product"), dict):
            product = payload["Product"]

        if not isinstance(product, dict):
            raise ProviderError("unexpected payload shape")

        name = _first(product, "Name", "DisplayName", "name", "displayName")
        price = _first_number(product, "Price", "price", "InstorePrice")
        was = _first_number(product, "WasPrice", "wasPrice", "SavePrice")

        # Some payloads express the discount as a saving amount rather than a
        # "was" price. Derive the was-price when only the saving is present.
        if was is None and price is not None:
            saving = _first_number(product, "Savings", "SavingsAmount")
            if saving:
                was = round(price + saving, 2)

        if price is None:
            raise ProviderError("no price field in response (adjust _parse mapping)")

        return self._result(
            ref,
            product_name=name or ref,
            current_price=price,
            was_price=was,
            currency="AUD",
            url=PRODUCT_URL.format(id=product_id),
        )


def _first(d: dict, *keys):
    for k in keys:
        v = d.get(k)
        if v not in (None, ""):
            return v
    return None


def _first_number(d: dict, *keys) -> Optional[float]:
    v = _first(d, *keys)
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    # Treat non-positive prices as "absent" — many feeds use 0 for unavailable.
    return f if f > 0 else None
