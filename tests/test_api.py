import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["API_KEY"] = "test-key"

from src.api.main import app
from src.api.routes import get_db
from src.models.canonical import BaseCanonical, Order, ValidationException

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine)


def override_get_db():
    with TestingSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    BaseCanonical.metadata.create_all(bind=engine)
    yield
    BaseCanonical.metadata.drop_all(bind=engine)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_orders_without_auth():
    response = client.get("/orders")
    assert response.status_code == 401


def test_orders_with_auth_empty():
    response = client.get("/orders", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    assert response.json() == []


def test_get_order_not_found():
    response = client.get("/orders/999", headers={"X-API-Key": "test-key"})
    assert response.status_code == 404


def test_exceptions_empty():
    response = client.get("/exceptions", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    assert response.json() == []


def test_list_orders_with_data():
    db = TestingSessionLocal()
    order = Order(
        source_order_id=1,
        customer_id="CUST1",
        status="valid",
        total_amount=0,
        freight=0,
    )
    db.add(order)
    db.commit()
    db.close()
    response = client.get("/orders", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["source_order_id"] == 1


def test_list_exceptions_with_filter():
    db = TestingSessionLocal()
    order = Order(source_order_id=2, status="invalid", total_amount=0, freight=0)
    db.add(order)
    db.commit()
    exc = ValidationException(
        order_id=order.id,
        rule_name="DUPLICATE_LINE_ITEMS",
        message="dup",
        severity="error",
    )
    db.add(exc)
    db.commit()
    db.close()
    response = client.get(
        "/exceptions?rule_name=DUPLICATE_LINE_ITEMS",
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1


def test_ingest():
    from unittest.mock import patch

    with patch(
        "src.api.routes.run_pipeline",
        return_value={
            "read": 5,
            "valid": 3,
            "invalid": 2,
            "inserted": 3,
            "skipped": 0,
        },
    ):
        response = client.post("/ingest", headers={"X-API-Key": "test-key"})
        assert response.status_code == 200
        data = response.json()
        assert data["read"] == 5
        assert data["inserted"] == 3
