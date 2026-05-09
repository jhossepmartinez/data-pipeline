from sqlalchemy.orm import Session
from src.models.canonical import Order


def persist_orders(target_session: Session, orders: list[Order]) -> dict:
    """
    Persiste ordenes en PostgreSQL de forma idempotente.

    Clave natural: source_order_id
    Si ya existe, se omite (skip).
    """
    stats = {"inserted": 0, "skipped": 0}

    for order in orders:
        existing = (
            target_session.query(Order)
            .filter_by(source_order_id=order.source_order_id)
            .first()
        )

        if existing:
            stats["skipped"] += 1
            continue

        target_session.add(order)
        stats["inserted"] += 1

    target_session.commit()
    return stats
