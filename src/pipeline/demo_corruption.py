from decimal import Decimal

from src.models.canonical import Order, OrderLine

DEMO_SOURCE_IDS = {900001, 900002, 900003, 900004, 900005}


def apply_demo_corruption(order: Order, source_order_id: int) -> Order:
    """
    Corrompe intencionalmente ordenes demo despues de la normalizacion
    para que las reglas de negocio generen excepciones naturalmente.

    Solo afecta IDs de demo (900001-900005).
    """
    if source_order_id not in DEMO_SOURCE_IDS:
        return order

    if source_order_id == 900001:
        # R7: Currency conversion mismatch
        # normalize calcula 100 * 1.10 = 110; nosotros lo corrompemos a 999
        order.total_amount_base = Decimal("999.00")

    elif source_order_id == 900002:
        # R5: Discount mismatch
        # normalize calcula 100 * 1 * 0.90 = 90; nosotros lo corrompemos a 100
        for line in order.lines:
            line.line_total = Decimal("100.00")

    elif source_order_id == 900003:
        # R2: Duplicate line items
        # Duplicar la primera linea para que falle dedupe canonico
        if order.lines:
            first = order.lines[0]
            order.lines.append(
                OrderLine(
                    product_id=first.product_id,
                    unit_price=first.unit_price,
                    quantity=first.quantity,
                    discount=first.discount,
                    line_total=first.line_total,
                )
            )

    elif source_order_id == 900004:
        # R1: Order total mismatch
        # normalize calcula 100 + 10 = 110; nosotros lo corrompemos a 500
        # Tambien actualizar total_amount_base para que R7 no falle primero
        order.total_amount = Decimal("500.00")
        order.total_amount_base = Decimal("500.00")

    return order
