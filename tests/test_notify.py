from pricewatch.models import PriceResult
from pricewatch.notify import format_digest, format_html_digest, notify_email


def _deal():
    return PriceResult(ref="Milo", provider="woolworths", product_name="Milo 460g",
                       current_price=8.0, was_price=10.0, url="http://x")


def test_format_digest_empty():
    assert "No items" in format_digest([], 20)


def test_format_digest_lists_deal():
    text = format_digest([_deal()], 20)
    assert "Milo 460g" in text
    assert "-20%" in text


def test_html_digest():
    html = format_html_digest([_deal()], 20)
    assert "<li>" in html and "Milo 460g" in html


def test_email_noop_without_key(monkeypatch):
    monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
    assert notify_email([_deal()], 20) is False
