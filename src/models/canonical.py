from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Numeric,
    ForeignKey,
    Text,
    func,
)
from sqlalchemy.orm import declarative_base, relationship

BaseCanonical = declarative_base()


class Order(BaseCanonical):
    __tablename__ = "canonical_orders"

    id = Column(Integer, primary_key=True)
    source_order_id = Column(Integer, unique=True, nullable=False, index=True)
    customer_id = Column(String)
    order_date = Column(DateTime)
    freight = Column(Numeric(10, 2), default=0)
    total_amount = Column(Numeric(10, 2))
    status = Column(String, default="pending")
    created_at = Column(DateTime, server_default=func.now())

    # NUEVO: campos multi-moneda
    original_currency = Column(String, default="USD")
    exchange_rate = Column(Numeric(10, 6), default=1.0)
    total_amount_base = Column(Numeric(10, 2))

    lines = relationship(
        "OrderLine", back_populates="order", cascade="all, delete-orphan"
    )
    exceptions = relationship(
        "ValidationException", back_populates="order", cascade="all, delete-orphan"
    )


class OrderLine(BaseCanonical):
    __tablename__ = "canonical_order_lines"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("canonical_orders.id"), nullable=False)
    product_id = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    quantity = Column(Integer, nullable=False)
    discount = Column(Numeric(5, 4), default=0)
    line_total = Column(Numeric(10, 2))

    order = relationship("Order", back_populates="lines")


class ValidationException(BaseCanonical):
    __tablename__ = "validation_exceptions"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("canonical_orders.id"), nullable=False)
    rule_name = Column(String, nullable=False)
    severity = Column(String, default="error")
    message = Column(Text, nullable=False)
    expected_value = Column(Numeric(10, 2), nullable=True)
    actual_value = Column(Numeric(10, 2), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    order = relationship("Order", back_populates="exceptions")
