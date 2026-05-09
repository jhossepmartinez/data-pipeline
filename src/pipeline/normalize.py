from decimal import Decimal
from src.models.source import SourceOrder
from src.models.canonical import Order, OrderLine
from src.exchange.mock_rates import get_rate


def normalize(source_order: SourceOrder, currency: str = "USD") -> Order:
    """Transforma SourceOrder a modelo canonico, calculando totales y conversion de moneda."""
    canonical_lines = []
    lines_sum = Decimal("0")

    for detail in source_order.details:
        line_total = (
            Decimal(str(detail.UnitPrice))
            * Decimal(str(detail.Quantity))
            * (Decimal("1") - Decimal(str(detail.Discount)))
        )
        lines_sum += line_total

        canonical_lines.append(
            OrderLine(
                product_id=detail.ProductID,
                unit_price=detail.UnitPrice,
                quantity=detail.Quantity,
                discount=detail.Discount,
                line_total=line_total,
            )
        )

    total_amount = lines_sum + Decimal(str(source_order.Freight))
    exchange_rate = get_rate(currency)
    total_amount_base = (total_amount * exchange_rate).quantize(Decimal("0.01"))

    return Order(
        source_order_id=source_order.OrderID,
        customer_id=source_order.CustomerID,
        order_date=source_order.OrderDate,
        freight=source_order.Freight,
        total_amount=total_amount,
        original_currency=currency,
        exchange_rate=exchange_rate,
        total_amount_base=total_amount_base,
        status="pending",
        lines=canonical_lines,
    )
