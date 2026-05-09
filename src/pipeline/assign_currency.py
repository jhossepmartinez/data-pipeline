from src.models.source import SourceOrder


def assign_currency(source_order: SourceOrder) -> str:
    """
    Simula la asignacion de moneda a una orden cruda.

    En el pipeline real este valor vendria de source_order.Currency.
    En este MVP todas las ordenes son USD salvo que:
    - Se inyecte `_mock_currency` en tests.
    - El CustomerID indique DEMO-R7 (EUR para demo de regla R7).
    """
    if hasattr(source_order, "_mock_currency"):
        return source_order._mock_currency
    if source_order.CustomerID and source_order.CustomerID.startswith("DEMO-R7"):
        return "EUR"
    return "USD"
