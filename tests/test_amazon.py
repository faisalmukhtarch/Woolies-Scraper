import pytest

from pricewatch.providers.amazon import AmazonProvider, KeepaBackend, PaApiBackend
from pricewatch.providers.base import ProviderError
from tests.conftest import FakeResponse, FakeSession


# ---- Keepa -----------------------------------------------------------------
def test_keepa_unavailable_without_key():
    b = KeepaBackend(api_key="")
    assert not b.is_available()


def test_keepa_lookup_current_and_reference():
    payload = {"products": [{
        "title": "Widget",
        "stats": {
            "current": [1500, 1299],   # [Amazon, New] in cents
            "avg30": [1800, 1799],
        },
    }]}
    b = KeepaBackend(api_key="k", session=FakeSession(response=FakeResponse(200, payload)))
    provider = AmazonProvider(backend=b)
    r = provider.fetch("B0TEST", "Widget")
    assert r.ok
    assert r.current_price == 12.99      # prefers New (index 1)
    assert r.was_price == 17.99
    assert r.percentage_drop == 28


def test_keepa_no_offer_marks_absent():
    payload = {"products": [{"title": "X", "stats": {"current": [-1, -1]}}]}
    b = KeepaBackend(api_key="k", session=FakeSession(response=FakeResponse(200, payload)))
    provider = AmazonProvider(backend=b)
    with pytest.raises(ProviderError):
        provider.fetch("B0", "X")


def test_keepa_missing_product():
    payload = {"products": []}
    b = KeepaBackend(api_key="k", session=FakeSession(response=FakeResponse(200, payload)))
    with pytest.raises(ProviderError):
        b.lookup("B0")


# ---- PA-API ----------------------------------------------------------------
def test_paapi_unavailable_reports_missing():
    b = PaApiBackend(access_key="", secret_key="", partner_tag="")
    assert not b.is_available()
    reason = b.unavailable_reason()
    assert "PAAPI_ACCESS_KEY" in reason


def test_paapi_signing_and_parse():
    payload = {"ItemsResult": {"Items": [{
        "ItemInfo": {"Title": {"DisplayValue": "Gadget"}},
        "Offers": {"Listings": [{
            "Price": {"Amount": 19.99},
            "SavingBasis": {"Amount": 29.99},
        }]},
    }]}}
    session = FakeSession(response=FakeResponse(200, payload))
    b = PaApiBackend(access_key="AK", secret_key="SK", partner_tag="tag-20", session=session)
    provider = AmazonProvider(backend=b)
    r = provider.fetch("B0GADGET", "Gadget")
    assert r.current_price == 19.99
    assert r.was_price == 29.99
    assert r.percentage_drop == 33
    # Signature header must be present and well-formed.
    auth = session.calls[0]["headers"]["Authorization"]
    assert auth.startswith("AWS4-HMAC-SHA256 Credential=AK/")
    assert "Signature=" in auth


def test_paapi_throttled():
    session = FakeSession(response=FakeResponse(429, text="slow down"))
    b = PaApiBackend(access_key="AK", secret_key="SK", partner_tag="t", session=session)
    with pytest.raises(ProviderError):
        b.lookup("B0")


def test_backend_selection_default_keepa(monkeypatch):
    monkeypatch.delenv("AMAZON_BACKEND", raising=False)
    monkeypatch.setenv("KEEPA_API_KEY", "k")
    p = AmazonProvider()
    assert p.backend.key == "keepa"


def test_backend_selection_paapi(monkeypatch):
    monkeypatch.setenv("AMAZON_BACKEND", "paapi")
    p = AmazonProvider()
    assert p.backend.key == "paapi"
