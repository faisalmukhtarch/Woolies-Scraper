"""Shared data models used across providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class WatchItem:
    """A single entry in the watchlist.

    Attributes:
        provider: Provider key (e.g. ``"woolworths"``, ``"amazon"``, ``"coles"``).
        ref: Human-friendly label used for display and notifications.
        product_id: The identifier the provider needs (Woolworths Product ID,
            Amazon ASIN, Coles product id, Chemist Warehouse id, ...).
    """

    provider: str
    ref: str
    product_id: str


@dataclass
class PriceResult:
    """The outcome of checking one item's price.

    A result is either a *success* (``error is None``) carrying a current price,
    or a *failure* (``error`` set) describing why the lookup could not complete.
    Failures are first-class so a single broken feed never aborts the run.
    """

    ref: str
    provider: str
    product_name: Optional[str] = None
    current_price: Optional[float] = None
    was_price: Optional[float] = None
    currency: str = "AUD"
    url: Optional[str] = None
    error: Optional[str] = None
    extra: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.error is None and self.current_price is not None

    @property
    def on_special(self) -> bool:
        return (
            self.ok
            and self.was_price is not None
            and self.was_price > self.current_price
        )

    @property
    def percentage_drop(self) -> Optional[int]:
        """Percentage discount off the ``was`` price, rounded to a whole number.

        Returns ``None`` when there is no meaningful "was" price to compare
        against (i.e. the item is not on special).
        """
        if not self.on_special:
            return None
        return round((1 - (self.current_price / self.was_price)) * 100)

    def format_price(self) -> str:
        if self.current_price is None:
            return "n/a"
        symbol = "$" if self.currency in ("AUD", "USD") else ""
        return f"{symbol}{self.current_price:.2f}"
