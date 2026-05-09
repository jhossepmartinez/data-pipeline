import logging
from decimal import Decimal

from src.models.canonical import Order, ValidationException

logger = logging.getLogger(__name__)


def validate_currency_conversion(
    order: Order, epsilon: Decimal = Decimal("0.01")
) -> list[ValidationException]:
    """
    R7: Coherencia de conversion de moneda.

    Verifica que total_amount_base = total_amount * exchange_rate (redondeado).
    """
    expected = (
        Decimal(str(order.total_amount)) * Decimal(str(order.exchange_rate))
    ).quantize(Decimal("0.01"))

    logger.info(
        "order_id=%s currency=%s rate=%s total=%s base=%s expected=%s",
        order.source_order_id,
        order.original_currency,
        order.exchange_rate,
        order.total_amount,
        order.total_amount_base,
        expected,
    )

    if abs(Decimal(str(order.total_amount_base)) - expected) > epsilon:
        return [
            ValidationException(
                order_id=order.id,
                rule_name="CURRENCY_CONVERSION_MISMATCH",
                message=(
                    f"Currency conversion mismatch for {order.original_currency}: "
                    f"expected {expected} (total {order.total_amount} * rate {order.exchange_rate}), "
                    f"got {order.total_amount_base}"
                ),
                expected_value=expected,
                actual_value=order.total_amount_base,
            )
        ]
    return []
