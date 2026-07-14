"""The orchestration layer: load a watchlist, check prices, report drops."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .config import build_providers, drop_threshold, resolve_provider_name
from .models import PriceResult, WatchItem
from .providers.base import Provider


@dataclass
class RunReport:
    results: List[PriceResult] = field(default_factory=list)
    skipped_providers: Dict[str, str] = field(default_factory=dict)

    def deals(self, threshold: int) -> List[PriceResult]:
        found = [
            r for r in self.results
            if r.ok and r.percentage_drop is not None and r.percentage_drop >= threshold
        ]
        found.sort(key=lambda r: r.percentage_drop, reverse=True)
        return found

    @property
    def errors(self) -> List[PriceResult]:
        return [r for r in self.results if not r.ok]


def load_watchlist(path: str) -> List[WatchItem]:
    """Parse a watchlist JSON file into a flat list of :class:`WatchItem`.

    Supports both the section-per-provider format::

        {"Woolworths": {"Milo": "192985"}, "Coles": {"...": "..."}}

    and legacy section names (``Chemist_Warehouse`` etc.), which are mapped to
    canonical provider keys via :func:`resolve_provider_name`.
    """
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    items: List[WatchItem] = []
    for section, entries in data.items():
        provider = resolve_provider_name(section)
        if not isinstance(entries, dict):
            continue
        for ref, product_id in entries.items():
            items.append(WatchItem(provider=provider, ref=ref, product_id=str(product_id)))
    return items


def check_item(provider: Provider, item: WatchItem) -> PriceResult:
    """Fetch one item, converting any exception into a failed result."""
    try:
        return provider.fetch(item.product_id, item.ref)
    except Exception as exc:  # ProviderError and anything unexpected
        return PriceResult(ref=item.ref, provider=item.provider, error=str(exc))


def run(watchlist_path: str, providers: Optional[Dict[str, Provider]] = None,
        threshold: Optional[int] = None) -> RunReport:
    """Check every watchlist item against its (available) provider."""
    providers = providers if providers is not None else build_providers()
    items = load_watchlist(watchlist_path)
    report = RunReport()

    # Group items by provider so we open each browser/session at most once.
    by_provider: Dict[str, List[WatchItem]] = {}
    for item in items:
        by_provider.setdefault(item.provider, []).append(item)

    for provider_name, provider_items in by_provider.items():
        provider = providers.get(provider_name)
        if provider is None:
            report.skipped_providers[provider_name] = "unknown provider"
            for it in provider_items:
                report.results.append(
                    PriceResult(ref=it.ref, provider=provider_name, error="unknown provider")
                )
            continue
        if not provider.is_available():
            report.skipped_providers[provider_name] = provider.unavailable_reason() or "unavailable"
            continue
        try:
            for it in provider_items:
                report.results.append(check_item(provider, it))
        finally:
            provider.close()

    return report
