from decimal import Decimal
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class OrderLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    unit_price: Decimal
    quantity: int
    discount: Decimal
    line_total: Optional[Decimal] = None


class ExceptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_name: str
    severity: str
    message: str
    expected_value: Optional[Decimal] = None
    actual_value: Optional[Decimal] = None
    created_at: Optional[datetime] = None


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_order_id: int
    customer_id: Optional[str] = None
    order_date: Optional[datetime] = None
    freight: Optional[Decimal] = None
    total_amount: Optional[Decimal] = None
    status: str
    original_currency: Optional[str] = None
    exchange_rate: Optional[Decimal] = None
    total_amount_base: Optional[Decimal] = None
    created_at: Optional[datetime] = None
    lines: List[OrderLineResponse] = []
    exceptions: List[ExceptionResponse] = []


class IngestResponse(BaseModel):
    read: int
    valid: int
    invalid: int
    inserted: int
    skipped: int
