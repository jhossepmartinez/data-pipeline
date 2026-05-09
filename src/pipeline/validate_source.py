from src.models.source import SourceOrder
from src.models.canonical import ValidationException


def validate_source(source_order: SourceOrder) -> list[ValidationException]:
    """Validaciones estructurales minimas sobre datos crudos."""
    exceptions: list[ValidationException] = []

    if source_order.OrderID is None:
        exceptions.append(
            ValidationException(
                order_id=None,
                rule_name="SOURCE_VALIDATION_FAILED",
                message="OrderID is null",
                severity="error",
            )
        )

    if not source_order.details:
        exceptions.append(
            ValidationException(
                order_id=source_order.OrderID,
                rule_name="SOURCE_VALIDATION_FAILED",
                message="details is empty",
                severity="error",
            )
        )

    if source_order.OrderDate is None:
        exceptions.append(
            ValidationException(
                order_id=source_order.OrderID,
                rule_name="SOURCE_VALIDATION_FAILED",
                message="OrderDate is null",
                severity="error",
            )
        )

    return exceptions
