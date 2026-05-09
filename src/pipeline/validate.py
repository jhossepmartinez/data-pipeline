import logging
from decimal import Decimal
from src.models.canonical import Order, ValidationException

logger = logging.getLogger(__name__)


def validate_order_total(order: Order) -> list[ValidationException]:
    """
    R1: Coherencia de totales.

    Calculated Total = sum(line_total) + freight
    Si |total_amount - calculated_total| > epsilon: excepcion.
    """
    lines_sum = sum(line.line_total for line in order.lines)
    calculated_total = lines_sum + order.freight
    epsilon = Decimal("0.01")

    # Log validation check details
    logger.info(
        "order_id=%s, expected_sum=%s, total_sum=%s",
        order.source_order_id,
        calculated_total,
        order.total_amount,
    )

    lines_log = " ".join(
        f"({i + 1}, {line.product_id}, {line.line_total})"
        for i, line in enumerate(order.lines)
    )
    logger.info("lines: %s", lines_log)

    if abs(order.total_amount - calculated_total) > epsilon:
        return [
            ValidationException(
                order_id=order.id,
                rule_name="ORDER_TOTAL_MISMATCH",
                message=(
                    f"Order total {order.total_amount} != lines sum {lines_sum} "
                    f"+ freight {order.freight} = {calculated_total}"
                ),
                expected_value=calculated_total,
                actual_value=order.total_amount,
            )
        ]
    return []
