from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from typing import Optional

from src.database import get_target_session
from src.api.auth import verify_api_key
from src.api.schemas import OrderResponse, ExceptionResponse, IngestResponse
from src.models.canonical import Order, ValidationException
from src.main import run_pipeline

router = APIRouter()


def get_db():
    with get_target_session() as session:
        yield session


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/orders", response_model=list[OrderResponse])
def list_orders(
    status: Optional[str] = Query(None),
    customer_id: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    query = db.query(Order).options(
        joinedload(Order.lines), joinedload(Order.exceptions)
    )
    if status:
        query = query.filter(Order.status == status)
    if customer_id:
        query = query.filter(Order.customer_id == customer_id)
    orders = query.offset(skip).limit(limit).all()
    return orders


@router.get("/orders/{source_order_id}", response_model=OrderResponse)
def get_order(
    source_order_id: int,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    order = (
        db.query(Order)
        .options(joinedload(Order.lines), joinedload(Order.exceptions))
        .filter_by(source_order_id=source_order_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.get("/exceptions", response_model=list[ExceptionResponse])
def list_exceptions(
    rule_name: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    query = db.query(ValidationException)
    if rule_name:
        query = query.filter(ValidationException.rule_name == rule_name)
    if severity:
        query = query.filter(ValidationException.severity == severity)
    exceptions = query.offset(skip).limit(limit).all()
    return exceptions


@router.post("/ingest", response_model=IngestResponse)
def trigger_ingest(
    api_key: str = Depends(verify_api_key),
):
    stats = run_pipeline()
    return IngestResponse(
        read=stats.get("read", 0),
        valid=stats.get("valid", 0),
        invalid=stats.get("invalid", 0),
        inserted=stats.get("inserted", 0),
        skipped=stats.get("skipped", 0),
    )
