"""Legacy Selenium scraper, wrapped as a provider.

This preserves the original project's ability to read prices from sites without
an official API — Chemist Warehouse — and to act as a Woolworths fallback when
no API key is configured. Selenium/Firefox are imported lazily so the rest of
the framework runs without them installed.

Two provider keys share this implementation:

* ``chemist_warehouse`` – https://www.chemistwarehouse.com.au/buy/{id}
* ``woolworths_scrape`` – https://www.woolworths.com.au/shop/productdetails/{id}
"""

from __future__ import annotations

import re
from typing import Optional

from ..models import PriceResult
from .base import Provider, ProviderError

CW_BASE = "https://www.chemistwarehouse.com.au/buy/"
WOOLIES_BASE = "https://www.woolworths.com.au/shop/productdetails/"


class SeleniumScraper(Provider):
    """Shared Selenium engine. A single browser is reused across items."""

    def __init__(self, headless: bool = True, page_timeout: float = 25.0):
        self.headless = headless
        self.page_timeout = page_timeout
        self._driver = None

    def is_available(self) -> bool:
        try:
            import selenium  # noqa: F401
            import bs4  # noqa: F401
        except ImportError:
            return False
        return True

    def unavailable_reason(self) -> Optional[str]:
        if not self.is_available():
            return "selenium/bs4 not installed (pip install selenium beautifulsoup4)"
        return None

    def _get_driver(self):
        if self._driver is not None:
            return self._driver
        from selenium import webdriver
        from selenium.webdriver.firefox.options import Options

        options = Options()
        if self.headless:
            options.add_argument("--headless")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
        )
        driver = webdriver.Firefox(options=options)
        driver.set_window_size(1920, 1080)
        self._driver = driver
        return driver

    def close(self) -> None:
        if self._driver is not None:
            try:
                self._driver.quit()
            finally:
                self._driver = None

    def _soup(self, url: str, wait_selector: str):
        from bs4 import BeautifulSoup
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.common.exceptions import TimeoutException

        driver = self._get_driver()
        driver.get(url)
        try:
            WebDriverWait(driver, self.page_timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
            )
        except TimeoutException as exc:
            raise ProviderError(f"timed out waiting for {wait_selector}") from exc
        return BeautifulSoup(driver.page_source, "html.parser")


class ChemistWarehouseProvider(SeleniumScraper):
    name = "chemist_warehouse"
    label = "Chemist Warehouse"

    def fetch(self, product_id: str, ref: str) -> PriceResult:
        url = CW_BASE + product_id
        soup = self._soup(url, "div[itemprop='name']")

        name_el = soup.find("div", {"itemprop": "name"})
        if name_el is None:
            raise ProviderError("product name not found")
        price_el = soup.find("span", {"class": "product__price"})
        if price_el is None:
            raise ProviderError("price not found")
        price = _money(price_el.text)
        was = None
        savings_el = soup.find("div", {"class": "Savings"})
        if savings_el is not None and price is not None:
            saving = _money(savings_el.text)
            if saving:
                was = round(price + saving, 2)
        if price is None:
            raise ProviderError("could not parse price")
        return self._result(
            ref, product_name=name_el.text.strip(),
            current_price=price, was_price=was, currency="AUD", url=url,
        )


class WoolworthsScrapeProvider(SeleniumScraper):
    name = "woolworths_scrape"
    label = "Woolworths (scrape fallback)"

    def fetch(self, product_id: str, ref: str) -> PriceResult:
        url = WOOLIES_BASE + product_id
        soup = self._soup(url, "h1.shelfProductTile-title")

        name_el = soup.find("h1", {"class": "shelfProductTile-title"})
        if name_el is None:
            raise ProviderError("product name not found")
        dollars_el = soup.find(class_="price-dollars")
        cents_el = soup.find(class_="price-cents")
        if dollars_el is None or cents_el is None:
            raise ProviderError("price not found")
        dollars = dollars_el.text.strip()
        cents = cents_el.text.strip()
        if not (dollars.isdigit() and cents.isdigit()):
            raise ProviderError(f"invalid price parts: '{dollars}'.'{cents}'")
        price = float(f"{dollars}.{cents}")
        was = None
        was_el = soup.find(class_="price-was")
        if was_el is not None:
            m = re.findall(r"\d+\.\d+", was_el.text)
            if m:
                was = float(m[0])
        return self._result(
            ref, product_name=name_el.text.strip(),
            current_price=price, was_price=was, currency="AUD", url=url,
        )


def _money(text: str) -> Optional[float]:
    m = re.findall(r"\$?\s*(\d+(?:\.\d+)?)", text or "")
    return float(m[0]) if m else None
