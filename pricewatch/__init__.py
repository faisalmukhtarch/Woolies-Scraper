"""PriceWatch: multi-provider grocery / retail price monitoring.

A small framework that reads a watchlist and checks current prices across
several retailers, using an official API where one exists and degrading
gracefully to best-effort sources where one does not.

Providers (see ``pricewatch.providers``):

* ``woolworths`` – official Woolworths Supermarkets API (developer.woolworths.com.au)
* ``amazon``     – Amazon PA-API 5.0 or Keepa (Amazon AU) as selectable backends
* ``coles``      – best-effort third-party wrapper (Coles has no official API)
* ``scrape``     – legacy Selenium scraper (Chemist Warehouse + Woolworths fallback)

Each provider is only activated when its required credentials are present, so
the tool runs with whatever feeds you have configured and skips the rest.
"""

from .models import PriceResult, WatchItem

__all__ = ["PriceResult", "WatchItem", "__version__"]

__version__ = "1.0.0"
