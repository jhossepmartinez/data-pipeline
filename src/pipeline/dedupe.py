from src.models.source import SourceOrder
from src.models.canonical import ValidationException


def check_duplicate_lines(source_order: SourceOrder) -> list[ValidationException]:
    """
    Detecta lineas duplicadas dentro de una misma orden.

    Si un ProductID aparece 2+ veces en la misma orden,
    la orden es invalida.
    """
    seen: set[int] = set()
    duplicates: set[int] = set()

    for detail in source_order.details:
        if detail.ProductID in seen:
            duplicates.add(detail.ProductID)
        seen.add(detail.ProductID)

    if duplicates:
        return [
            ValidationException(
                order_id=None,
                rule_name="DUPLICATE_LINE_ITEMS",
                message=f"Duplicate ProductIDs: {sorted(duplicates)}",
                severity="error",
            )
        ]
    return []
