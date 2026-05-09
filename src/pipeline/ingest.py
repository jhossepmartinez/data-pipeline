from sqlalchemy.orm import joinedload
from src.models.source import SourceOrder


def fetch_orders(session, limit: int | None = None):
    """Lee ordenes desde SQLite con eager loading de lineas."""
    query = session.query(SourceOrder).options(joinedload(SourceOrder.details))
    if limit:
        query = query.limit(limit)
    return query.all()
