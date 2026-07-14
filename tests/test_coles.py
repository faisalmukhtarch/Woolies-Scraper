import pytest

from pricewatch.providers.base import ProviderError
from pricewatch.providers.coles import ColesProvider
from tests.conftest import FakeResponse, FakeSession


def make(session):
    return ColesProvider(api_key="k", session=session)


def test_unavailable_without_key():
    p = ColesProvider(api_key="")
    assert not p.is_available()
    assert "no official API" in p.unavailable_reason()


def test_flat_payload():
    payload = {"name": "Coles Milk 2L", "price": 3.10, "was": 4.00}
    r = make(FakeSession(response=FakeResponse(200, payload))).fetch("123", "Milk")
    assert r.current_price == 3.10
    assert r.was_price == 4.00
    assert r.percentage_drop == 22


def test_data_envelope_and_string_price():
    payload = {"data": {"title": "Bread", "current_price": "$2.50"}}
    r = make(FakeSession(response=FakeResponse(200, payload))).fetch("1", "Bread")
    assert r.current_price == 2.50
    assert r.was_price is None


def test_nested_pricing_object():
    payload = {"product": {"name": "Eggs", "pricing": {"now": 5.5}}}
    r = make(FakeSession(response=FakeResponse(200, payload))).fetch("1", "Eggs")
    assert r.current_price == 5.5


def test_list_results_envelope():
    payload = {"results": [{"name": "Rice", "price": 6.0}]}
    r = make(FakeSession(response=FakeResponse(200, payload))).fetch("1", "Rice")
    assert r.current_price == 6.0


def test_no_price_raises():
    payload = {"name": "MysteryItem"}
    with pytest.raises(ProviderError):
        make(FakeSession(response=FakeResponse(200, payload))).fetch("1", "x")


def test_rapidapi_headers_sent():
    session = FakeSession(response=FakeResponse(200, {"name": "x", "price": 1.0}))
    ColesProvider(api_key="secret", session=session).fetch("1", "x")
    headers = session.calls[0]["headers"]
    assert headers["X-RapidAPI-Key"] == "secret"
