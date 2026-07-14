"""Command-line entry point.

Usage::

    python -m pricewatch [--watchlist watchlist.json] [--threshold 20]
                         [--no-email] [--no-desktop] [--json]
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

from .config import build_providers, drop_threshold
from .notify import format_digest, notify_desktop, notify_email
from .runner import run


def _print_report(report, threshold: int) -> None:
    print(f"PriceWatch — {datetime.now().strftime('%d %b %Y | %I:%M %p')}")
    print("=" * 55)

    if report.skipped_providers:
        print("\nInactive providers (skipped):")
        for name, reason in report.skipped_providers.items():
            print(f"  - {name}: {reason}")

    # Group successful results by provider for readable output.
    by_provider = {}
    for r in report.results:
        by_provider.setdefault(r.provider, []).append(r)

    for provider, results in by_provider.items():
        print(f"\n{provider.upper()}")
        print("-" * len(provider))
        for r in results:
            if r.ok:
                drop = f"  (-{r.percentage_drop}%)" if r.percentage_drop is not None else ""
                was = f"  was {r.was_price:.2f}" if r.was_price else ""
                print(f"  {r.product_name}: {r.format_price()}{was}{drop}")
            else:
                print(f"  {r.ref}: ERROR — {r.error}")

    deals = report.deals(threshold)
    print("\n" + "=" * 55)
    print(format_digest(deals, threshold))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="pricewatch", description="Multi-provider price monitor")
    parser.add_argument("--watchlist", default="watchlist.json", help="Path to watchlist JSON")
    parser.add_argument("--threshold", type=int, default=None, help="Drop %% to flag (default 20)")
    parser.add_argument("--no-email", action="store_true", help="Skip email notification")
    parser.add_argument("--no-desktop", action="store_true", help="Skip desktop notification")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args(argv)

    threshold = args.threshold if args.threshold is not None else drop_threshold()

    report = run(args.watchlist, providers=build_providers(), threshold=threshold)
    deals = report.deals(threshold)

    if args.json:
        import json as _json
        print(_json.dumps({
            "threshold": threshold,
            "results": [vars(r) for r in report.results],
            "skipped": report.skipped_providers,
            "deals": [r.ref for r in deals],
        }, indent=2, default=str))
    else:
        _print_report(report, threshold)

    if deals:
        if not args.no_desktop:
            notify_desktop(deals, threshold)
        if not args.no_email:
            notify_email(deals, threshold)

    return 0


if __name__ == "__main__":
    sys.exit(main())
