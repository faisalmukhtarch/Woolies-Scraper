from pricewatch.models import PriceResult


def test_ok_and_special_and_drop():
    r = PriceResult(ref="Milo", provider="woolworths", product_name="Milo 460g",
                    current_price=8.0, was_price=10.0)
    assert r.ok
    assert r.on_special
    assert r.percentage_drop == 20
    assert r.format_price() == "$8.00"


def test_no_special_when_was_missing():
    r = PriceResult(ref="x", provider="p", current_price=5.0)
    assert r.ok
    assert not r.on_special
    assert r.percentage_drop is None


def test_error_result_not_ok():
    r = PriceResult(ref="x", provider="p", error="boom")
    assert not r.ok
    assert not r.on_special
    assert r.percentage_drop is None
    assert r.format_price() == "n/a"


def test_was_not_higher_is_not_special():
    r = PriceResult(ref="x", provider="p", current_price=5.0, was_price=5.0)
    assert not r.on_special
