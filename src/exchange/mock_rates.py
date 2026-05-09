from decimal import Decimal
from datetime import date
from typing import Optional

# Tasas mock fijas: moneda -> USD
RATES = {
    "USD": Decimal("1.0"),
    "EUR": Decimal("1.10"),
    "GBP": Decimal("1.30"),
}


def get_rate(currency: str, as_of_date: Optional[date] = None) -> Decimal:
    """
    Devuelve la tasa de cambio mock para convertir `currency` a USD.

    Args:
        currency: Codigo de moneda (USD, EUR, GBP).
        as_of_date: Ignorado en este MVP (tasas fijas).

    Raises:
        ValueError: Si la moneda no esta soportada.
    """
    currency = currency.upper()
    if currency not in RATES:
        raise ValueError(
            f"Unsupported currency: {currency}. Supported: {list(RATES.keys())}"
        )
    return RATES[currency]
