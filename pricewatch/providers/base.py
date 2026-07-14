"""Provider abstraction.

A provider knows how to turn a product identifier into a
:class:`~pricewatch.models.PriceResult`. Providers are intentionally thin and
independent so that a failure in one (a rotated key, a rate limit, a changed
page) degrades gracefully instead of taking the whole run down.
"""

from __future__ import annotations

import abc
from typing import Optional

from ..models import PriceResult


class ProviderError(Exception):
    """Raised for an expected, per-item failure (bad id, 404, rate limit).

    The runner catches these and records them on the :class:`PriceResult`
    rather than aborting the run.
    """


class Provider(abc.ABC):
    """Base class for all price sources.

    Subclasses must set :attr:`name` and implement :meth:`fetch`. They should
    also implement :meth:`is_available` to report whether their credentials /
    dependencies are present; unavailable providers are skipped entirely.
    """

    #: Short key matching the watchlist section and config, e.g. ``"woolworths"``.
    name: str = "base"

    #: Human-readable label used in output headings.
    label: str = "Base"

    def is_available(self) -> bool:  # pragma: no cover - trivial default
        """Return True when the provider is configured and ready to use."""
        return True

    def unavailable_reason(self) -> Optional[str]:
        """Optional human-readable explanation of why the provider is inactive."""
        return None

    @abc.abstractmethod
    def fetch(self, product_id: str, ref: str) -> PriceResult:
        """Look up ``product_id`` and return a :class:`PriceResult`.

        Implementations should raise :class:`ProviderError` for expected
        per-item problems; the runner converts any exception into a failed
        result so one bad item never stops the batch.
        """

    def _result(self, ref: str, **kwargs) -> PriceResult:
        """Convenience factory that stamps the provider name onto a result."""
        return PriceResult(ref=ref, provider=self.name, **kwargs)

    def close(self) -> None:
        """Release any resources (browser, session). Safe to call repeatedly."""
