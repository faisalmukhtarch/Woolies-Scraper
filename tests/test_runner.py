import json

import pytest

from pricewatch.models import PriceResult
from pricewatch.providers.base import Provider, ProviderError
from pricewatch.runner import load_watchlist, run


class FakeProvider(Provider):
    name = "woolworths"

    def __init__(self, prices):
        self.prices = prices  # id -> (price, was) or Exception

    def is_available(self):
        return True

    def fetch(self, product_id, ref):
        v = self.prices.get(product_id)
        if isinstance(v, Exception):
            raise v
        price, was = v
        return self._result(ref, product_name=ref, current_price=price, was_price=was)


class UnavailableProvider(Provider):
    name = "coles"

    def is_available(self):
        return False

    def unavailable_reason(self):
        return "no key"

    def fetch(self, product_id, ref):  # pragma: no cover - never called
        raise AssertionError("should not be called")


@pytest.fixture
def watchlist_file(tmp_path):
    data = {
        "Woolworths": {"Milo": "1", "Bread": "2", "Broken": "3"},
        "Coles": {"Milk": "9"},
        "Unknown_Store": {"Thing": "5"},
    }
    p = tmp_path / "watchlist.json"
    p.write_text(json.dumps(data))
    return str(p)


def test_load_watchlist_maps_aliases(watchlist_file):
    items = load_watchlist(watchlist_file)
    providers = {i.provider for i in items}
    assert "woolworths" in providers
    assert "coles" in providers


def test_run_collects_deals_errors_and_skips(watchlist_file):
    providers = {
        "woolworths": FakeProvider({
            "1": (8.0, 10.0),                 # 20% drop -> deal
            "2": (3.0, 3.2),                  # small drop -> not a deal
            "3": ProviderError("boom"),       # error
        }),
        "coles": UnavailableProvider(),
    }
    report = run(watchlist_file, providers=providers, threshold=20)

    deals = report.deals(20)
    assert [d.ref for d in deals] == ["Milo"]

    assert any(r.error == "boom" for r in report.errors)
    # Coles skipped (unavailable), Unknown_Store unknown.
    assert report.skipped_providers.get("coles") == "no key"
    assert "unknown" in report.skipped_providers.get("unknown_store", "").lower() \
        or any(r.provider == "unknown_store" for r in report.results)


def test_deals_sorted_by_drop(watchlist_file):
    providers = {"woolworths": FakeProvider({
        "1": (5.0, 10.0),   # 50%
        "2": (8.0, 10.0),   # 20%
        "3": (7.0, 10.0),   # 30%
    })}
    report = run(watchlist_file, providers=providers, threshold=20)
    drops = [d.percentage_drop for d in report.deals(20)]
    assert drops == sorted(drops, reverse=True)


def test_provider_closed_after_run(watchlist_file):
    closed = {"count": 0}

    class ClosingProvider(FakeProvider):
        def close(self):
            closed["count"] += 1

    providers = {"woolworths": ClosingProvider({"1": (1.0, None), "2": (1.0, None), "3": (1.0, None)})}
    run(watchlist_file, providers=providers, threshold=20)
    assert closed["count"] == 1
