from sqlalchemy.orm import Session

from src.models.canonical import Order, OrderLine, ValidationException


def reset_target_db(db: Session) -> None:
    """
    Trunca todas las tablas canonicas.

    ATENCION: operacion destructiva. Solo usar en demos / tests.
    """
    db.query(ValidationException).delete()
    db.query(OrderLine).delete()
    db.query(Order).delete()
    db.commit()
