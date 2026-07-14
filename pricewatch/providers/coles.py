"""Coles (best-effort) price provider.

Coles publishes **no** official third-party API. This adapter therefore targets
a third-party wrapper that does the scraping on their end (e.g. a RapidAPI
"Coles Product Price" API). You are outsourcing the risk, not removing it: these
feeds can change shape or disappear without notice, so this provider is designed
to fail softly and is skipped entirely when unconfigured.

Config (defaults target a RapidAPI-style host; override for another wrapper):

* ``COLES_API_KEY``   – wrapper API key (RapidAPI key)
* ``COLES_API_HOST``  – RapidAPI host header value
* ``COLES_API_BASE``  – full base URL
* ``COLES_PRODUCT_PATH`` – path template containing ``{id}``

Because wrapper response shapes vary, :meth:`_parse` scans the payload for the
first plausible name/price rather than assuming a fixed schema, and clearly
reports when it cannot find one.
"""

from __future__ import annotations

import os
from typing import Any, Optional

import requests

from ..models import PriceResult
from .base import Provider, ProviderError

DEFAULT_HOST = "coles-product-price-api.p.rapidapi.com"
DEFAULT_BASE = "https://coles-product-price-api.p.rapidapi.com"
DEFAULT_PRODUCT_PATH = "/product/{id}"
PRODUCT_URL = "https://www.coles.com.au/product/{id}"

_NAME_KEYS = ("name", "title", "product_name", "productName", "displayName", "description")
_PRICE_KEYS = ("price", "current_price", "currentPrice", "now", "salePrice", "pricing")
_WAS_KEYS = ("was", "was_price", "wasPrice", "originalPrice", "rrp", "regularPrice")


class ColesProvider(Provider):
    name = "coles"
    label = "Coles (best-effort)"

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_host: Optional[str] = None,
        base_url: Optional[str] = None,
        product_path: Optional[str] = None,
        session: Optional[requests.Session] = None,
        timeout: float = 20.0,
    ):
        self.api_key = api_key if api_key is not None else os.environ.get("COLES_API_KEY")
        self.api_host = api_host or os.environ.get("COLES_API_HOST") or DEFAULT_HOST
        self.base_url = (base_url or os.environ.get("COLES_API_BASE") or DEFAULT_BASE).rstrip("/")
        self.product_path = product_path or os.environ.get("COLES_PRODUCT_PATH") or DEFAULT_PRODUCT_PATH
        self.timeout = timeout
        self.session = session or requests.Session()

    def is_available(self) -> bool:
        return bool(self.api_key)

    def unavailable_reason(self) -> Optional[str]:
        if not self.api_key:
            return "COLES_API_KEY not set (no official API; configure a third-party wrapper)"
        return None

    def _headers(self) -> dict:
        # RapidAPI convention; harmless for other hosts.
        return {
            "Accept": "application/json",
            "X-RapidAPI-Key": self.api_key or "",
            "X-RapidAPI-Host": self.api_host,
        }

    def fetch(self, product_id: str, ref: str) -> PriceResult:
        url = f"{self.base_url}{self.product_path.format(id=product_id)}"
        try:
            resp = self.session.get(url, headers=self._headers(), timeout=self.timeout)
        except requests.RequestException as exc:
            raise ProviderError(f"network error: {exc}") from exc
        if resp.status_code == 404:
            raise ProviderError(f"product {product_id} not found (404)")
        if resp.status_code in (401, 403):
            raise ProviderError(f"auth rejected ({resp.status_code}) — check COLES_API_KEY/host")
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
        obj = payload
        # Unwrap a single-key envelope like {"data": {...}} or {"product": {...}}.
        if isinstance(obj, dict):
            for wrapper in ("data", "product", "result", "results"):
                inner = obj.get(wrapper)
                if isinstance(inner, dict):
                    obj = inner
                    break
                if isinstance(inner, list) and inner and isinstance(inner[0], dict):
                    obj = inner[0]
                    break
        if not isinstance(obj, dict):
            raise ProviderError("unexpected payload shape")

        name = _find(obj, _NAME_KEYS)
        price = _find_number(obj, _PRICE_KEYS)
        was = _find_number(obj, _WAS_KEYS)
        if price is None:
            raise ProviderError("could not locate a price field (wrapper schema changed?)")
        if was is not None and price is not None and was <= price:
            was = None
        return self._result(
            ref,
            product_name=str(name) if name else ref,
            current_price=price,
            was_price=was,
            currency="AUD",
            url=PRODUCT_URL.format(id=product_id),
        )


def _find(d: dict, keys) -> Optional[Any]:
    for k in keys:
        v = d.get(k)
        if isinstance(v, (str, int, float)) and v not in ("", None):
            return v
    return None


def _find_number(d: dict, keys) -> Optional[float]:
    for k in keys:
        v = d.get(k)
        if isinstance(v, dict):
            # e.g. {"pricing": {"now": 3.5}} — recurse one level.
            nested = _find_number(v, ("now", "value", "amount", "current", "price"))
            if nested is not None:
                return nested
            continue
        if isinstance(v, (int, float)):
            return float(v) if v > 0 else None
        if isinstance(v, str):
            cleaned = v.replace("$", "").replace(",", "").strip()
            try:
                f = float(cleaned)
            except ValueError:
                continue
            if f > 0:
                return f
    return None
