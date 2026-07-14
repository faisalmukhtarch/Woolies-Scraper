"""Backward-compatible entry point.

The scraping logic now lives in the :mod:`pricewatch` package, which checks
prices across Woolworths (official API), Amazon (PA-API/Keepa), Coles
(best-effort wrapper) and the legacy Selenium scrapers, activating whichever
feeds are configured. This shim keeps ``python price-drop.py`` working.

Run the full CLI directly for more options::

    python -m pricewatch --help
"""

import sys

from pricewatch.cli import main

if __name__ == "__main__":
    sys.exit(main())
