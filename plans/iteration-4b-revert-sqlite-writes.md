# Plan: Iteracion 4b — Revertir escrituras en SQLite fuente — Opcion A (demo orders en memoria)

## Estado: Listo para implementar

---

## 1. Contexto del problema

La implementacion actual de `POST /demo/seed-errors` **muta la base fuente SQLite** insertando `SourceOrder` y `SourceOrderDetail`. Esto viola el principio de diseno: **SQLite = solo lectura**.

Consecuencias del approach actual:
- `src/api/demo_seeder.py` hace `db.add(order)` + `db.commit()` en SQLite.
- `tests/test_api.py` necesita crear una base SQLite temporal, importar `BaseSource`, `SourceOrder`, etc.
- `src/database.py` necesita engines lazy con `reset_source_engine()` y `reset_target_engine()` solo para permitir que los tests cambien la DB fuente entre ejecuciones.
- El endpoint ejecuta `seed_demo_source_orders()` y **luego** `run_pipeline()`, como dos pasos separados.

## 2. Solucion: Opcion A (recomendada)

El endpoint `/demo/seed-errors` **nunca toca ninguna base de datos**. Construye objetos `SourceOrder` + `SourceOrderDetail` en memoria, se los pasa al pipeline como `extra_orders`, y el pipeline las procesa junto con las ordenes reales de Northwind. Las reglas de negocio generan las excepciones naturalmente.

**Flujo de datos:**
```
POST /demo/seed-errors
  |
  ├─► build_demo_source_orders()  ← crea 5 SourceOrder en memoria (sin DB)
  |
  ├─► run_pipeline(extra_orders=demo_orders)
  |     |
  |     ├─► fetch_orders()        ← lee Northwind SQLite (solo lectura)
  |     ├─► raw_orders = northwind_orders + demo_orders
  |     |
  |     ├─► Para cada orden:
  |     |     validate_source(source)  ──► R3 (900005)
  |     |     check_duplicate_lines(source)
  |     |     assign_currency(source)  ──► EUR para DEMO-R7
  |     |     normalize(source)
  |     |     apply_demo_corruption(order)  ──► rompe R1/R2/R5/R7
  |     |     check_canonical_duplicate_lines(order)  ──► R2 (900003)
  |     |     validate_currency_conversion(order)  ──► R7 (900001)
  |     |     validate_line_discounts(order)  ──► R5 (900002)
  |     |     validate_order_total(order)  ──► R1 (900004)
  |     |     persist_orders(target)  ──► INSERT en PostgreSQL
  |     |
  |     └─► return stats
  |
  └─► return SeedErrorsResponse(stats)
```

**Northwind SQLite: nunca se escribe. Solo lectura.**

## 3. Archivos a modificar

### 3.1. `src/database.py` — Revertir a eager engines

**Objetivo:** Eliminar la complejidad de lazy engines y resets. Volver al estado anterior: engines creados al importar el modulo.

**Codigo final:**
```python
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config import config

# Engine 1: SQLite (Source - Solo lectura)
source_engine = create_engine(
    config.source_db_url(),
    connect_args={"check_same_thread": False},
    echo=False,
)

# Engine 2: PostgreSQL (Target - Lectura/Escritura)
target_engine = create_engine(config.DATABASE_URL, echo=False)

# Session makers
SourceSessionLocal = sessionmaker(bind=source_engine)
TargetSessionLocal = sessionmaker(bind=target_engine)


@contextmanager
def get_source_session():
    """Sesion para leer de Northwind SQLite."""
    session = SourceSessionLocal()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def get_target_session():
    """Sesion para escribir/leer la base canonica PostgreSQL."""
    session = TargetSessionLocal()
    try:
        yield session
    finally:
        session.close()
```

**Eliminar:**
- `_create_engine()` helper
- `get_source_engine()`, `reset_source_engine()`
- `get_target_engine()`, `reset_target_engine()`
- Cualquier import de `StaticPool`

---

### 3.2. `src/api/demo_seeder.py` — Construir en memoria, no insertar

**Objetivo:** Dejar de insertar en SQLite. Construir objetos ORM en memoria y devolverlos.

**Codigo final:**
```python
from datetime import datetime
from decimal import Decimal

from src.models.source import SourceOrder, SourceOrderDetail

DEMO_SOURCE_IDS = [900001, 900002, 900003, 900004, 900005]

DEMO_SOURCE_ORDERS = [
    {
        "OrderID": 900001,
        "CustomerID": "DEMO-R7",
        "OrderDate": datetime(2023, 1, 1),
        "Freight": Decimal("0"),
        "details": [
            {"ProductID": 1, "UnitPrice": Decimal("100.00"), "Quantity": 1, "Discount": Decimal("0")},
        ],
    },
    {
        "OrderID": 900002,
        "CustomerID": "DEMO-R5",
        "OrderDate": datetime(2023, 1, 1),
        "Freight": Decimal("0"),
        "details": [
            {"ProductID": 2, "UnitPrice": Decimal("100.00"), "Quantity": 1, "Discount": Decimal("0.10")},
        ],
    },
    {
        "OrderID": 900003,
        "CustomerID": "DEMO-R2",
        "OrderDate": datetime(2023, 1, 1),
        "Freight": Decimal("0"),
        "details": [
            {"ProductID": 3, "UnitPrice": Decimal("100.00"), "Quantity": 1, "Discount": Decimal("0")},
        ],
    },
    {
        "OrderID": 900004,
        "CustomerID": "DEMO-R1",
        "OrderDate": datetime(2023, 1, 1),
        "Freight": Decimal("10.00"),
        "details": [
            {"ProductID": 4, "UnitPrice": Decimal("100.00"), "Quantity": 1, "Discount": Decimal("0")},
        ],
    },
    {
        "OrderID": 900005,
        "CustomerID": "DEMO-R3",
        "OrderDate": None,
        "Freight": Decimal("0"),
        "details": [
            {"ProductID": 5, "UnitPrice": Decimal("10.00"), "Quantity": 1, "Discount": Decimal("0")},
        ],
    },
]


def build_demo_source_orders() -> list[SourceOrder]:
    """
    Construye ordenes de demostracion invalidas en memoria.

    Returns:
        List[SourceOrder] lista de objetos listos para pasar al pipeline.
    """
    orders = []
    for spec in DEMO_SOURCE_ORDERS:
        order = SourceOrder(
            OrderID=spec["OrderID"],
            CustomerID=spec["CustomerID"],
            OrderDate=spec["OrderDate"],
            Freight=spec["Freight"],
        )
        order.details = [
            SourceOrderDetail(
                ProductID=d["ProductID"],
                UnitPrice=d["UnitPrice"],
                Quantity=d["Quantity"],
                Discount=d["Discount"],
            )
            for d in spec["details"]
        ]
        orders.append(order)
    return orders
```

**Eliminar:**
- `seed_demo_source_orders(db: Session)` por completo.
- Cualquier import de `sqlalchemy.orm.Session`.
- Cualquier logica de "existing / skipped / inserted" (eso ahora lo maneja el pipeline).

---

### 3.3. `src/main.py` — Aceptar `extra_orders`

**Objetivo:** Permitir que `run_pipeline` reciba ordenes adicionales en memoria.

**Cambios:**
1. Cambiar firma:
   ```python
   def run_pipeline(
       limit: int | None = None,
       extra_orders: list[SourceOrder] | None = None,
   ) -> dict:
   ```
2. Despues de `fetch_orders()`, concatenar:
   ```python
   raw_orders = fetch_orders(source_session, limit=limit)
   if extra_orders:
       raw_orders = raw_orders + extra_orders
   ```
3. El resto del pipeline se mantiene **exactamente igual**.

**Nota:** El conteo `"read": len(raw_orders)` incluira las ordenes de Northwind + las demo. Esto es correcto y consistente con `/ingest`.

---

### 3.4. `src/api/routes.py` — Endpoint puro sin escritura en SQLite

**Objetivo:** El endpoint ya no abre sesion source. Construye ordenes en memoria, las pasa al pipeline, y reporta resultados.

**Codigo final del endpoint:**
```python
from src.api.demo_seeder import build_demo_source_orders


@router.post("/demo/seed-errors", response_model=SeedErrorsResponse)
def trigger_seed_errors(
    api_key: str = Depends(verify_api_key),
):
    demo_orders = build_demo_source_orders()
    result = run_pipeline(extra_orders=demo_orders)
    return SeedErrorsResponse(
        inserted=result["inserted"],
        skipped=result["skipped"],
        orders=[o.OrderID for o in demo_orders],
    )
```

**Eliminar:**
- Import de `get_source_session`.
- Import de `seed_demo_source_orders` (reemplazar por `build_demo_source_orders`).

---

### 3.5. `src/pipeline/demo_corruption.py` — Mantener sin cambios

Este archivo **no se toca**. Es correcto: corrompe las ordenes demo post-normalizacion para que las reglas de negocio fallen.

---

### 3.6. `src/pipeline/dedupe.py` — Mantener `check_canonical_duplicate_lines`

La funcion `check_canonical_duplicate_lines` **se mantiene**. Fue creada para detectar duplicados en el modelo canonico (necesario porque no podemos insertar duplicados en SQLite por constraint de PK). Es parte de la solucion correcta.

---

### 3.7. `src/pipeline/assign_currency.py` — Mantener sin cambios

El hack de `DEMO-R7` → EUR **se mantiene**. Es necesario para que el pipeline asigne EUR a la orden demo 900001, y luego `demo_corruption` pueda corromper la conversion.

---

### 3.8. `tests/test_api.py` — Simplificar drasticamente

**Objetivo:** Eliminar toda la infraestructura de DB fuente temporal. Volver a usar solo el target en memoria (como en la Iteracion 4 original).

**Codigo final:**
```python
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


def test_seed_errors_without_auth():
    response = client.post("/demo/seed-errors")
    assert response.status_code == 401


def test_seed_errors_inserts_demo_orders_and_generates_exceptions():
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
    r1 = client.post("/demo/seed-errors", headers={"X-API-Key": "test-key"})
    assert r1.status_code == 200
    assert r1.json()["inserted"] == 5

    r2 = client.post("/demo/seed-errors", headers={"X-API-Key": "test-key"})
    assert r2.status_code == 200
    assert r2.json()["inserted"] == 0
    assert r2.json()["skipped"] == 5
```

**Eliminar:**
- Todo el codigo relacionado con `tempfile`, `temp_source_path`, `source_engine`, `SourceSessionLocal`, `_clean_source_db()`.
- Cualquier import de `BaseSource`, `SourceOrder`, `SourceOrderDetail`, `reset_source_engine`.
- Cualquier logica de `config.DATABASE_URL = "sqlite:///:memory:"` y `reset_target_engine()`.

---

## 4. Archivos que NO se tocan

| Archivo | Por que |
|---------|---------|
| `src/pipeline/demo_corruption.py` | Es correcto. Corrompe ordenes demo post-normalizacion. |
| `src/pipeline/dedupe.py` | `check_canonical_duplicate_lines` es necesario para R2 (no podemos duplicar en SQLite). |
| `src/pipeline/assign_currency.py` | `DEMO-R7` → EUR es necesario para que R7 falle. |
| `src/pipeline/validate_source.py` | Sin cambios. |
| `src/pipeline/validate.py` | Sin cambios. |
| `src/pipeline/validate_discounts.py` | Sin cambios. |
| `src/pipeline/validate_currency.py` | Sin cambios. |
| `src/pipeline/normalize.py` | Sin cambios. |
| `src/pipeline/ingest.py` | Sin cambios. |
| `src/pipeline/persist.py` | Sin cambios. |
| `src/pipeline/mock_rates.py` | Sin cambios. |
| `src/models/source.py` | Sin cambios. |
| `src/models/canonical.py` | Sin cambios. |
| `src/config.py` | Sin cambios. |
| `src/api/main.py` | Sin cambios. |
| `src/api/schemas.py` | `SeedErrorsResponse` ya existe y es correcto. |
| `src/api/auth.py` | Sin cambios. |

---

## 5. Tests que deben pasar

Ejecutar:
```bash
uv run pytest -v
```

**Esperado: 46 tests passed.**

Lista de suites:
- `tests/test_api.py` — 11 tests
- `tests/test_validate_source.py` — 4 tests
- `tests/test_dedupe.py` — 2 tests
- `tests/test_business_rules.py` — 4 tests
- `tests/test_validate_currency.py` — 7 tests
- `tests/test_validate_discounts.py` — 4 tests
- `tests/test_assign_currency.py` — 2 tests
- `tests/test_mock_rates.py` — 5 tests
- `tests/test_integration.py` — 3 tests

---

## 6. Verificacion manual (opcional)

```bash
# 1. Levantar API
uv run uvicorn src.api.main:app --reload --port 8000

# 2. Seedear errores de demostracion
#    (inserta 5 ordenes en memoria, las procesa el pipeline,
#     las reglas generan excepciones, se persisten en PostgreSQL)
curl -X POST -H "X-API-Key: dev-key" http://localhost:8000/demo/seed-errors | jq

# 3. Ver ordenes invalidas generadas por el pipeline
curl -H "X-API-Key: dev-key" "http://localhost:8000/orders?status=invalid" | jq

# 4. Ver excepciones por regla
curl -H "X-API-Key: dev-key" "http://localhost:8000/exceptions" | jq
```

---

## 3.9. `src/api/schemas.py` — Agregar `ResetAndSeedResponse`

**Objetivo:** Schema para el nuevo endpoint de reset + seed.

**Codigo a agregar:**
```python
class ResetAndSeedResponse(BaseModel):
    read: int
    valid: int
    invalid: int
    inserted: int
    skipped: int
    orders: List[int]
```

---

### 3.10. `src/pipeline/reset_target.py` — Nuevo modulo de reset

**Objetivo:** Funcion pura que trunca todas las tablas del target (PostgreSQL) para permitir correr el pipeline desde cero.

**Codigo final:**
```python
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
```

**No agregar a "Archivos que NO se tocan"** — este es un archivo nuevo.

---

### 3.11. `src/api/routes.py` — Agregar `POST /demo/reset-and-seed`

**Objetivo:** Endpoint que limpia el target, corre el pipeline con demo orders, y devuelve stats completos.

**Codigo a agregar:**
```python
from src.pipeline.reset_target import reset_target_db
from src.api.schemas import ResetAndSeedResponse


@router.post("/demo/reset-and-seed", response_model=ResetAndSeedResponse)
def trigger_reset_and_seed(
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    reset_target_db(db)
    demo_orders = build_demo_source_orders()
    result = run_pipeline(extra_orders=demo_orders)
    return ResetAndSeedResponse(
        read=result["read"],
        valid=result["valid"],
        invalid=result["invalid"],
        inserted=result["inserted"],
        skipped=result["skipped"],
        orders=[o.OrderID for o in demo_orders],
    )
```

**Notas:**
- Recibe `db: Session = Depends(get_db)` para poder truncar el target antes de correr el pipeline.
- El pipeline luego usa `get_target_session()` internamente para persistir. Esto es aceptable porque ambas sesiones apuntan al mismo engine/DB.

---

### 3.12. `tests/test_api.py` — Agregar tests de `reset-and-seed`

**Tests a agregar:**

```python
def test_reset_and_seed_without_auth():
    response = client.post("/demo/reset-and-seed")
    assert response.status_code == 401


def test_reset_and_seed_clears_and_inserts_demo():
    # 1. Insertar una orden directamente en el target
    db = TestingSessionLocal()
    order = Order(source_order_id=99999, customer_id="OLD", status="valid", total_amount=0, freight=0)
    db.add(order)
    db.commit()
    db.close()

    # 2. Llamar reset-and-seed
    response = client.post("/demo/reset-and-seed", headers={"X-API-Key": "test-key"})
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
    demo_orders = [o for o in orders if o["customer_id"] and o["customer_id"].startswith("DEMO-")]
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
    # Primera llamada
    r1 = client.post("/demo/reset-and-seed", headers={"X-API-Key": "test-key"})
    assert r1.status_code == 200
    assert r1.json()["inserted"] == 5

    # Segunda llamada — trunca de nuevo e inserta de nuevo
    r2 = client.post("/demo/reset-and-seed", headers={"X-API-Key": "test-key"})
    assert r2.status_code == 200
    assert r2.json()["inserted"] == 5  # porque trunco primero
```

---

## 4. Archivos que NO se tocan

| Archivo | Por que |
|---------|---------|
| `src/pipeline/demo_corruption.py` | Es correcto. Corrompe ordenes demo post-normalizacion. |
| `src/pipeline/dedupe.py` | `check_canonical_duplicate_lines` es necesario para R2. |
| `src/pipeline/assign_currency.py` | `DEMO-R7` → EUR es necesario para que R7 falle. |
| `src/pipeline/validate_source.py` | Sin cambios. |
| `src/pipeline/validate.py` | Sin cambios. |
| `src/pipeline/validate_discounts.py` | Sin cambios. |
| `src/pipeline/validate_currency.py` | Sin cambios. |
| `src/pipeline/normalize.py` | Sin cambios. |
| `src/pipeline/ingest.py` | Sin cambios. |
| `src/pipeline/persist.py` | Sin cambios. |
| `src/pipeline/mock_rates.py` | Sin cambios. |
| `src/models/source.py` | Sin cambios. |
| `src/models/canonical.py` | Sin cambios. |
| `src/config.py` | Sin cambios. |
| `src/api/main.py` | Sin cambios. |
| `src/api/auth.py` | Sin cambios. |

---

## 5. Tests que deben pasar

Ejecutar:
```bash
uv run pytest -v
```

**Esperado: 49 tests passed.** (46 originales + 3 nuevos de reset-and-seed)

---

## 6. Verificacion manual

### Flujo de Pablo (clona, levanta, prueba)

```bash
# 1. Clonar y levantar (Northwind ya esta cargada en tu entorno)
uv run uvicorn src.api.main:app --reload --port 8000

# 2. Resetear target + seedear ordenes demo + correr pipeline
#    (un solo comando para ver todo desde cero)
curl -X POST -H "X-API-Key: dev-key" http://localhost:8000/demo/reset-and-seed | jq

# 3. Ver ordenes invalidas (solo las 5 demo + cualquiera de Northwind)
curl -H "X-API-Key: dev-key" "http://localhost:8000/orders?status=invalid" | jq

# 4. Ver excepciones generadas por reglas
curl -H "X-API-Key: dev-key" "http://localhost:8000/exceptions" | jq

# 5. Llamar de nuevo — se reinicia desde cero
curl -X POST -H "X-API-Key: dev-key" http://localhost:8000/demo/reset-and-seed | jq
```

### Flujo idempotente (sin reset)

```bash
# Seedear sin borrar (anade a lo existente)
curl -X POST -H "X-API-Key: dev-key" http://localhost:8000/demo/seed-errors | jq

# Segunda vez: 0 insertadas, 5 skipped (idempotente)
curl -X POST -H "X-API-Key: dev-key" http://localhost:8000/demo/seed-errors | jq
```

---

## 7. Principios que se respetan

1. **SQLite es solo lectura:** `build_demo_source_orders()` nunca toca una base de datos.
2. **Pipeline unico punto de procesamiento:** todas las ordenes pasan por `run_pipeline()`.
3. **Excepciones generadas por reglas de negocio:** no se hardcodean.
4. **Idempotencia:** `/demo/seed-errors` usa `on_conflict_do_nothing`. Segunda llamada = 0 insertadas.
5. **Destructivo explicito:** `/demo/reset-and-seed` deja claro en el path que trunca datos.
6. **Tests limpios:** `test_api.py` usa solo SQLite en memoria para el target.
