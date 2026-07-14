import pytest

from pricewatch.providers.base import ProviderError
from pricewatch.providers.woolworths import WoolworthsProvider
from tests.conftest import FakeResponse, FakeSession


def make(session):
    return WoolworthsProvider(api_key="k", session=session)


def test_unavailable_without_key():
    p = WoolworthsProvider(api_key="")
    assert not p.is_available()
    assert "WOOLWORTHS_API_KEY" in p.unavailable_reason()


def test_parse_nested_product_with_was():
    payload = {"Product": {"Name": "Milo 460g", "Price": 8.0, "WasPrice": 10.0}}
    p = make(FakeSession(response=FakeResponse(200, payload)))
    r = p.fetch("192985", "Milo")
    assert r.ok
    assert r.product_name == "Milo 460g"
    assert r.current_price == 8.0
    assert r.was_price == 10.0
    assert r.percentage_drop == 20
    assert "192985" in r.url


def test_derives_was_from_savings():
    payload = {"Product": {"Name": "X", "Price": 8.0, "Savings": 2.0}}
    p = make(FakeSession(response=FakeResponse(200, payload)))
    r = p.fetch("1", "X")
    assert r.was_price == 10.0


def test_top_level_product():
    payload = {"name": "Y", "price": "3.50"}
    p = make(FakeSession(response=FakeResponse(200, payload)))
    r = p.fetch("1", "Y")
    assert r.current_price == 3.5
    assert r.was_price is None


def test_404_raises():
    p = make(FakeSession(response=FakeResponse(404)))
    with pytest.raises(ProviderError):
        p.fetch("1", "Y")


def test_auth_error_raises():
    p = make(FakeSession(response=FakeResponse(403)))
    with pytest.raises(ProviderError):
        p.fetch("1", "Y")


def test_missing_price_raises():
    payload = {"Product": {"Name": "NoPrice"}}
    p = make(FakeSession(response=FakeResponse(200, payload)))
    with pytest.raises(ProviderError):
        p.fetch("1", "Y")


def test_bearer_auth_header():
    session = FakeSession(response=FakeResponse(200, {"name": "Y", "price": 1.0}))
    p = WoolworthsProvider(api_key="tok", auth_header="Authorization", session=session)
    p.fetch("1", "Y")
    assert session.calls[0]["headers"]["Authorization"] == "Bearer tok"
