import os

os.environ["API_KEY"] = "test-key"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from src.api.main import app
from src.api.routes import get_db
from src.database import target_engine
from src.models.canonical import BaseCanonical, Order, ValidationException

TestingSessionLocal = sessionmaker(bind=target_engine)


def override_get_db():
    with TestingSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    BaseCanonical.metadata.create_all(bind=target_engine)
    yield
    BaseCanonical.metadata.drop_all(bind=target_engine)


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


def test_seed_errors_without_auth():
    response = client.post("/demo/seed-errors")
    assert response.status_code == 401


def test_seed_errors_inserts_demo_orders_and_generates_exceptions():
    from unittest.mock import patch

    with patch("src.main.fetch_orders", return_value=[]):
        response = client.post("/demo/seed-errors", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    data = response.json()
    assert data["inserted"] == 5
    assert data["skipped"] == 0
    assert len(data["orders"]) == 5

    # Verificar que existen en /orders?status=invalid
    response = client.get("/orders?status=invalid", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    orders = response.json()
    demo_orders = [
        o for o in orders if o["customer_id"] and o["customer_id"].startswith("DEMO-")
    ]
    assert len(demo_orders) == 5

    # Verificar excepciones generadas por las reglas de negocio
    response = client.get("/exceptions", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    excs = response.json()
    rule_names = {e["rule_name"] for e in excs}
    assert rule_names >= {
        "CURRENCY_CONVERSION_MISMATCH",
        "DISCOUNT_MISMATCH",
        "DUPLICATE_LINE_ITEMS",
        "ORDER_TOTAL_MISMATCH",
        "SOURCE_VALIDATION_FAILED",
    }


def test_seed_errors_is_idempotent():
    from unittest.mock import patch

    with patch("src.main.fetch_orders", return_value=[]):
        r1 = client.post("/demo/seed-errors", headers={"X-API-Key": "test-key"})
    assert r1.status_code == 200
    assert r1.json()["inserted"] == 5

    with patch("src.main.fetch_orders", return_value=[]):
        r2 = client.post("/demo/seed-errors", headers={"X-API-Key": "test-key"})
    assert r2.status_code == 200
    assert r2.json()["inserted"] == 0
    assert r2.json()["skipped"] == 5


def test_reset_and_seed_without_auth():
    response = client.post("/demo/reset-and-seed")
    assert response.status_code == 401


def test_reset_and_seed_clears_and_inserts_demo():
    from unittest.mock import patch

    # 1. Insertar una orden directamente en el target
    db = TestingSessionLocal()
    order = Order(
        source_order_id=99999,
        customer_id="OLD",
        status="valid",
        total_amount=0,
        freight=0,
    )
    db.add(order)
    db.commit()
    db.close()

    # 2. Llamar reset-and-seed
    with patch("src.main.fetch_orders", return_value=[]):
        response = client.post(
            "/demo/reset-and-seed", headers={"X-API-Key": "test-key"}
        )
    assert response.status_code == 200
    data = response.json()
    assert data["inserted"] == 5
    assert data["orders"] == [900001, 900002, 900003, 900004, 900005]

    # 3. Verificar que la orden vieja ya no existe
    response = client.get("/orders", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    orders = response.json()
    old_orders = [o for o in orders if o["customer_id"] == "OLD"]
    assert len(old_orders) == 0

    # 4. Verificar que las 5 demo existen
    demo_orders = [
        o for o in orders if o["customer_id"] and o["customer_id"].startswith("DEMO-")
    ]
    assert len(demo_orders) == 5

    # 5. Verificar excepciones
    response = client.get("/exceptions", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    excs = response.json()
    rule_names = {e["rule_name"] for e in excs}
    assert rule_names >= {
        "CURRENCY_CONVERSION_MISMATCH",
        "DISCOUNT_MISMATCH",
        "DUPLICATE_LINE_ITEMS",
        "ORDER_TOTAL_MISMATCH",
        "SOURCE_VALIDATION_FAILED",
    }


def test_reset_and_seed_is_repeatable():
    from unittest.mock import patch

    # Primera llamada
    with patch("src.main.fetch_orders", return_value=[]):
        r1 = client.post("/demo/reset-and-seed", headers={"X-API-Key": "test-key"})
    assert r1.status_code == 200
    assert r1.json()["inserted"] == 5

    # Segunda llamada — trunca de nuevo e inserta de nuevo
    with patch("src.main.fetch_orders", return_value=[]):
        r2 = client.post("/demo/reset-and-seed", headers={"X-API-Key": "test-key"})
    assert r2.status_code == 200
    assert r2.json()["inserted"] == 5  # porque trunco primero
