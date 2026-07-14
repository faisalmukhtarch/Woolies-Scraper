"""Standalone email step for CI.

Runs the full PriceWatch check and emails a digest of the deals it found via
SendGrid. Kept as a separate script so the GitHub Actions workflow can run the
price check and the email notification as distinct steps if desired.

The main CLI (`python -m pricewatch`) already emails automatically when
SENDGRID_API_KEY is set, so this is only needed for that split-step setup.
"""

import os

from pricewatch.config import build_providers, drop_threshold
from pricewatch.notify import notify_email
from pricewatch.runner import run


def send_email(watchlist_path: str = "watchlist.json") -> None:
    threshold = drop_threshold()
    report = run(watchlist_path, providers=build_providers(), threshold=threshold)
    deals = report.deals(threshold)
    sent = notify_email(deals, threshold)
    if sent:
        print(f"Email sent: {len(deals)} deal(s) at/over {threshold}%.")
    elif not os.environ.get("SENDGRID_API_KEY"):
        print("SENDGRID_API_KEY not set — skipping email.")
    else:
        print("Email not sent (see errors above).")


if __name__ == "__main__":
    send_email()
