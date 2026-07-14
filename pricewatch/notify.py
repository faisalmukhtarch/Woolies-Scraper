"""Notifications: build a digest and deliver it via email and/or desktop.

Both channels are optional and degrade gracefully:

* Email uses SendGrid when ``SENDGRID_API_KEY`` is set.
* Desktop uses ``plyer`` when it is installed and a display is available.
"""

from __future__ import annotations

import os
from typing import List

from .models import PriceResult


def format_digest(deals: List[PriceResult], threshold: int) -> str:
    """Return a plain-text summary of items at/over the drop threshold."""
    if not deals:
        return f"No items dropped by {threshold}% or more."
    lines = [f"Price drops ≥ {threshold}%:", ""]
    for r in deals:
        lines.append(
            f"  • [{r.provider}] {r.product_name}: {r.format_price()} "
            f"(-{r.percentage_drop}%)  {r.url or ''}".rstrip()
        )
    return "\n".join(lines)


def format_html_digest(deals: List[PriceResult], threshold: int) -> str:
    if not deals:
        return f"<p>No items dropped by {threshold}% or more.</p>"
    rows = "".join(
        f"<li>[{r.provider}] <strong>{r.product_name}</strong>: "
        f"{r.format_price()} (-{r.percentage_drop}%) "
        f"<a href='{r.url}'>link</a></li>"
        for r in deals
    )
    return f"<h3>Price drops &ge; {threshold}%</h3><ul>{rows}</ul>"


def notify_desktop(deals: List[PriceResult], threshold: int) -> bool:
    """Show a desktop toast. Returns True if a notification was shown."""
    if not deals:
        return False
    try:
        from plyer import notification
    except ImportError:
        return False
    message = ", ".join(f"{r.ref} (-{r.percentage_drop}%)" for r in deals)
    try:
        notification.notify(
            title=f"Price Drop > {threshold}%",
            message=message,
            timeout=10,
        )
        return True
    except Exception:
        # No display / unsupported backend — not fatal.
        return False


def notify_email(deals: List[PriceResult], threshold: int,
                 to_email: str = None, from_email: str = None) -> bool:
    """Send the digest via SendGrid. Returns True on a 2xx response."""
    api_key = os.environ.get("SENDGRID_API_KEY")
    if not api_key:
        return False
    to_email = to_email or os.environ.get("PRICEWATCH_EMAIL_TO") or "faisalmukhtarch@gmail.com"
    from_email = from_email or os.environ.get("PRICEWATCH_EMAIL_FROM") or to_email
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
    except ImportError:
        return False

    subject = (
        f"PriceWatch: {len(deals)} deal(s) ≥ {threshold}%"
        if deals else "PriceWatch: no deals today"
    )
    message = Mail(
        from_email=from_email,
        to_emails=to_email,
        subject=subject,
        html_content=format_html_digest(deals, threshold),
    )
    try:
        sg = SendGridAPIClient(api_key)
        resp = sg.send(message)
        return 200 <= resp.status_code < 300
    except Exception as exc:  # pragma: no cover - network dependent
        print(f"Email notification failed: {exc}")
        return False
