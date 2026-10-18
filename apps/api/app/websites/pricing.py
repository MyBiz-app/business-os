"""The price list of the website service (decision 18.12). Prices are configuration, not
logic: change them here (minor units) after the competitor survey. Nothing is charged before
payments (#46) exist; an order only records the prices it was offered."""

from typing import Literal

Product = Literal["landing_only", "landing_with_system"]

# product -> currency -> (one-time setup, monthly), minor units.
PRICES: dict[str, dict[str, tuple[int, int]]] = {
    "landing_only": {"ILS": (79000, 4900), "USD": (22900, 1400), "EUR": (20900, 1300)},
    "landing_with_system": {"ILS": (49000, 2900), "USD": (13900, 800), "EUR": (12900, 700)},
}


def price_for(product: Product, currency: str) -> tuple[int, int]:
    table = PRICES[product]
    return table.get(currency, table["USD"])
