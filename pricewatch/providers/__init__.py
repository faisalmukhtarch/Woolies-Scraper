"""Provider adapters for each supported retailer.

Every provider subclasses :class:`pricewatch.providers.base.Provider` and is
registered in :func:`pricewatch.config.build_providers`, which only activates
the ones whose credentials are present in the environment.
"""

from .base import Provider, ProviderError

__all__ = ["Provider", "ProviderError"]
