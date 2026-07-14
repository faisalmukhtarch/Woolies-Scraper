"""Runtime configuration and provider registry.

Reads settings from the environment and assembles the set of providers, marking
each as active/inactive based on whether its credentials are present.
"""

from __future__ import annotations

import os
from typing import Dict

from .providers.amazon import AmazonProvider
from .providers.base import Provider
from .providers.coles import ColesProvider
from .providers.scrape import ChemistWarehouseProvider, WoolworthsScrapeProvider
from .providers.woolworths import WoolworthsProvider

# Discount threshold (percent) at or above which an item is flagged / notified.
DEFAULT_DROP_THRESHOLD = 20


def drop_threshold() -> int:
    raw = os.environ.get("PRICEWATCH_DROP_THRESHOLD")
    if raw:
        try:
            return int(raw)
        except ValueError:
            pass
    return DEFAULT_DROP_THRESHOLD


def build_providers() -> Dict[str, Provider]:
    """Instantiate every known provider, keyed by name.

    Instantiation is cheap and side-effect free (no network, no browser), so we
    build them all and let the runner consult :meth:`Provider.is_available`.
    """
    providers = [
        WoolworthsProvider(),
        AmazonProvider(),
        ColesProvider(),
        ChemistWarehouseProvider(),
        WoolworthsScrapeProvider(),
    ]
    return {p.name: p for p in providers}


# Aliases so a watchlist can use friendly / legacy section names.
PROVIDER_ALIASES = {
    "chemist_warehouse": "chemist_warehouse",
    "chemistwarehouse": "chemist_warehouse",
    "cw": "chemist_warehouse",
    "woolworths": "woolworths",
    "woolies": "woolworths",
    "woolworths_scrape": "woolworths_scrape",
    "amazon": "amazon",
    "coles": "coles",
}


def resolve_provider_name(section: str) -> str:
    """Map a watchlist section heading to a canonical provider key.

    Unknown sections are still normalized (lowercased, spaces to underscores)
    so downstream keying is predictable.
    """
    normalized = section.strip().lower().replace(" ", "_")
    return PROVIDER_ALIASES.get(normalized, normalized)
