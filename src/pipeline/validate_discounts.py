import logging
from decimal import Decimal

from src.models.canonical import Order, OrderLine, ValidationException

logger = logging.getLogger(__name__)


def validate_line_discounts(
    order: Order, epsilon: Decimal = Decimal("0.01")
) -> list[ValidationException]:
    """
    R5: Coherencia de descuentos por linea.

    Verifica que line_total = unit_price * quantity * (1 - discount)
    para cada linea de la orden.
    """
    exceptions: list[ValidationException] = []

    for line in order.lines:
        expected = (
            Decimal(str(line.unit_price))
            * Decimal(str(line.quantity))
            * (Decimal("1") - Decimal(str(line.discount)))
        )

        if abs(Decimal(str(line.line_total)) - expected) > epsilon:
            exceptions.append(
                ValidationException(
                    order_id=order.id,
                    rule_name="DISCOUNT_MISMATCH",
                    message=(
                        f"Product {line.product_id}: line_total {line.line_total} != "
                        f"expected {expected} (unit_price={line.unit_price}, "
                        f"quantity={line.quantity}, discount={line.discount})"
                    ),
                    expected_value=expected,
                    actual_value=line.line_total,
                )
            )

    return exceptions
