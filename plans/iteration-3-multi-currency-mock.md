# Plan: Iteracion 3 — Multi-moneda con tipo de cambio simulado (Mock) — R7

## Objetivo

Anadir soporte multi-moneda al pipeline usando un **mock** de tipos de cambio (no API externa). Todas las ordenes se normalizaran a USD (moneda base) y se validara la coherencia de la conversion.

Pipeline objetivo tras esta iteracion:

```
ingest -> assign-currency -> validate-source -> dedupe -> normalize -> validate-currency (R7) -> validate-discounts (R5) -> consistency-checks (R1) -> persist -> serve/query
```

---

## Supuestos mock (documentados y explícitos)

1. **Northwind SQLite no tiene campo de moneda.** Se simula durante `ingest` asignando una moneda a cada `SourceOrder`.
2. **Moneda base del sistema:** USD.
3. **Tasas mock:** son valores fijos ficticios (no consumimos API externa).
   - USD → USD: `1.0`
   - EUR → USD: `1.10`
   - GBP → USD: `1.30`
4. **Tasa fija por moneda (sin fecha):** en este MVP la fecha de la orden no afecta la tasa. Documentado como limitacion.
5. **Conversion a nivel de orden:** `total_amount_base = total_amount * exchange_rate`. Se aplica sobre el total de la orden, no linea por linea. Documentado como simplificacion del MVP.
6. **Redondeo:** `total_amount_base` se redondea a 2 decimales (`.quantize(Decimal('0.01'))`).
7. **Solo 3 monedas soportadas:** USD, EUR, GBP. Cualquier otra genera excepcion.
8. **Asignacion mock:** 100 % de ordenes reciben USD por defecto. En tests se puede inyectar EUR/GBP via atributo `_mock_currency`.

---

## 1. Modelo de datos

### 1.1. Cambios en `src/models/canonical.py`

Anadir 3 columnas a `Order`:

```python
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

    lines = relationship(...)
    exceptions = relationship(...)
```

### 1.2. Alembic migration

Crear migracion:

```bash
alembic revision -m "add_currency_fields"
```

Editar el archivo generado en `alembic/versions/002_add_currency_fields.py`:

```python
"""add_currency_fields

Revision ID: 002
Revises: 001
Create Date: 2025-05-09 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "canonical_orders",
        sa.Column("original_currency", sa.String(), nullable=True),
    )
    op.add_column(
        "canonical_orders",
        sa.Column("exchange_rate", sa.Numeric(precision=10, scale=6), nullable=True),
    )
    op.add_column(
        "canonical_orders",
        sa.Column("total_amount_base", sa.Numeric(precision=10, scale=2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("canonical_orders", "total_amount_base")
    op.drop_column("canonical_orders", "exchange_rate")
    op.drop_column("canonical_orders", "original_currency")
```

Aplicar migracion:

```bash
alembic upgrade head
```

---

## 2. Modulos nuevos

### 2.1. `src/exchange/__init__.py`

Vacío (solo para que sea paquete Python).

### 2.2. `src/exchange/mock_rates.py`

```python
from decimal import Decimal
from datetime import date
from typing import Optional

# Tasas mock fijas: moneda -> USD
RATES = {
    "USD": Decimal("1.0"),
    "EUR": Decimal("1.10"),
    "GBP": Decimal("1.30"),
}


def get_rate(currency: str, as_of_date: Optional[date] = None) -> Decimal:
    """
    Devuelve la tasa de cambio mock para convertir `currency` a USD.

    Args:
        currency: Codigo de moneda (USD, EUR, GBP).
        as_of_date: Ignorado en este MVP (tasas fijas).

    Raises:
        ValueError: Si la moneda no esta soportada.
    """
    currency = currency.upper()
    if currency not in RATES:
        raise ValueError(f"Unsupported currency: {currency}. Supported: {list(RATES.keys())}")
    return RATES[currency]
```

### 2.3. `src/pipeline/assign_currency.py`

```python
from src.models.source import SourceOrder


def assign_currency(source_order: SourceOrder) -> str:
    """
    Simula la asignacion de moneda a una orden cruda.

    En el pipeline real este valor vendria de source_order.Currency.
    En este MVP todas las ordenes son USD salvo que se inyecte
    `_mock_currency` en tests.
    """
    if hasattr(source_order, "_mock_currency"):
        return source_order._mock_currency
    return "USD"
```

### 2.4. `src/pipeline/validate_currency.py`

```python
import logging
from decimal import Decimal

from src.models.canonical import Order, ValidationException

logger = logging.getLogger(__name__)


def validate_currency_conversion(
    order: Order, epsilon: Decimal = Decimal("0.01")
) -> list[ValidationException]:
    """
    R7: Coherencia de conversion de moneda.

    Verifica que total_amount_base = total_amount * exchange_rate (redondeado).
    """
    expected = (
        Decimal(str(order.total_amount)) * Decimal(str(order.exchange_rate))
    ).quantize(Decimal("0.01"))

    logger.info(
        "order_id=%s currency=%s rate=%s total=%s base=%s expected=%s",
        order.source_order_id,
        order.original_currency,
        order.exchange_rate,
        order.total_amount,
        order.total_amount_base,
        expected,
    )

    if abs(Decimal(str(order.total_amount_base)) - expected) > epsilon:
        return [
            ValidationException(
                order_id=order.id,
                rule_name="CURRENCY_CONVERSION_MISMATCH",
                message=(
                    f"Currency conversion mismatch for {order.original_currency}: "
                    f"expected {expected} (total {order.total_amount} * rate {order.exchange_rate}), "
                    f"got {order.total_amount_base}"
                ),
                expected_value=expected,
                actual_value=order.total_amount_base,
            )
        ]
    return []
```

---

## 3. Cambios en modulos existentes

### 3.1. `src/pipeline/normalize.py`

Anadir parametros `currency` y calculos de conversion.

```python
from decimal import Decimal
from src.models.source import SourceOrder
from src.models.canonical import Order, OrderLine
from src.exchange.mock_rates import get_rate


def normalize(source_order: SourceOrder, currency: str = "USD") -> Order:
    """Transforma SourceOrder a modelo canonico, calculando totales y conversion de moneda."""
    canonical_lines = []
    lines_sum = Decimal("0")

    for detail in source_order.details:
        line_total = (
            Decimal(str(detail.UnitPrice))
            * Decimal(str(detail.Quantity))
            * (Decimal("1") - Decimal(str(detail.Discount)))
        )
        lines_sum += line_total

        canonical_lines.append(
            OrderLine(
                product_id=detail.ProductID,
                unit_price=detail.UnitPrice,
                quantity=detail.Quantity,
                discount=detail.Discount,
                line_total=line_total,
            )
        )

    total_amount = lines_sum + Decimal(str(source_order.Freight))
    exchange_rate = get_rate(currency)
    total_amount_base = (total_amount * exchange_rate).quantize(Decimal("0.01"))

    return Order(
        source_order_id=source_order.OrderID,
        customer_id=source_order.CustomerID,
        order_date=source_order.OrderDate,
        freight=source_order.Freight,
        total_amount=total_amount,
        original_currency=currency,
        exchange_rate=exchange_rate,
        total_amount_base=total_amount_base,
        status="pending",
        lines=canonical_lines,
    )
```

### 3.2. `src/main.py`

Importar y ejecutar `assign_currency` y `validate_currency_conversion`.

Diferencia a aplicar:

1. Anadir imports:
```python
from src.pipeline.assign_currency import assign_currency
from src.pipeline.validate_currency import validate_currency_conversion
```

2. En el bucle de ordenes, despues de `dedupe` y antes de `normalize`:
```python
        # 2. Dedupe check
        exceptions = check_duplicate_lines(source_order)
        if exceptions:
            ...
            continue

        # 3. Assign currency
        currency = assign_currency(source_order)

        # 4. Normalize
        order = normalize(source_order, currency=currency)

        # 5. Currency conversion check (R7)
        exceptions = validate_currency_conversion(order)

        # 6. Discount checks (R5)
        if not exceptions:
            exceptions = validate_line_discounts(order)

        # 7. Consistency checks (R1)
        if not exceptions:
            exceptions = validate_order_total(order)

        if exceptions:
            order.status = "invalid"
            order.exceptions = exceptions
            invalid_count += 1
        else:
            order.status = "valid"
            valid_count += 1
```

Nota: el conteo de invalidas por dedupe/source-validation sigue igual (continue). Solo las ordenes que llegan a normalize se marcan valid/invalid y se persisten.

### 3.3. `src/api/schemas.py`

Anadir a `OrderResponse`:

```python
class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_order_id: int
    customer_id: Optional[str] = None
    order_date: Optional[datetime] = None
    freight: Optional[Decimal] = None
    total_amount: Optional[Decimal] = None
    status: str
    # NUEVO
    original_currency: Optional[str] = None
    exchange_rate: Optional[Decimal] = None
    total_amount_base: Optional[Decimal] = None
    created_at: Optional[datetime] = None
    lines: List[OrderLineResponse] = []
    exceptions: List[ExceptionResponse] = []
```

---

## 4. Tests a anadir

### 4.1. `tests/test_mock_rates.py`

| Test | Descripcion |
|------|-------------|
| `test_usd_rate_is_one` | `get_rate("USD")` devuelve `1.0`. |
| `test_eur_rate_is_expected` | `get_rate("EUR")` devuelve `1.10`. |
| `test_gbp_rate_is_expected` | `get_rate("GBP")` devuelve `1.30`. |
| `test_unsupported_currency_raises` | `get_rate("JPY")` lanza `ValueError`. |
| `test_case_insensitive` | `get_rate("eur")` funciona. |

Ejemplo:
```python
import unittest
from decimal import Decimal
from src.exchange.mock_rates import get_rate


class TestMockRates(unittest.TestCase):
    def test_usd_rate_is_one(self):
        self.assertEqual(get_rate("USD"), Decimal("1.0"))

    def test_eur_rate_is_expected(self):
        self.assertEqual(get_rate("EUR"), Decimal("1.10"))

    def test_unsupported_currency_raises(self):
        with self.assertRaises(ValueError):
            get_rate("JPY")
```

### 4.2. `tests/test_assign_currency.py`

| Test | Descripcion |
|------|-------------|
| `test_default_is_usd` | Orden sin atributo especial devuelve `"USD"`. |
| `test_mock_injection_eur` | Orden con `_mock_currency = "EUR"` devuelve `"EUR"`. |

### 4.3. `tests/test_validate_currency.py`

| Test | Descripcion |
|------|-------------|
| `test_valid_conversion_passes` | Orden con `total_amount=100`, `rate=1.1`, `base=110.00` pasa. |
| `test_mismatch_detected` | Orden con valores desfasados genera `CURRENCY_CONVERSION_MISMATCH`. |
| `test_epsilon_tolerance` | Diferencia menor a 0.01 no genera excepcion. |
| `test_usd_base_equals_total` | Orden USD tiene `total_amount_base == total_amount`. |

Ejemplo:
```python
import unittest
from decimal import Decimal
from datetime import datetime

from src.models.source import SourceOrder, SourceOrderDetail
from src.pipeline.normalize import normalize
from src.pipeline.validate_currency import validate_currency_conversion


class TestValidateCurrency(unittest.TestCase):
    def test_usd_base_equals_total(self):
        source = SourceOrder(
            OrderID=1,
            CustomerID="A",
            OrderDate=datetime(2023, 1, 1),
            Freight=Decimal("10"),
            details=[
                SourceOrderDetail(ProductID=1, UnitPrice=Decimal("10"), Quantity=1)
            ],
        )
        order = normalize(source, currency="USD")
        self.assertEqual(order.total_amount_base, order.total_amount)
        excs = validate_currency_conversion(order)
        self.assertEqual(len(excs), 0)

    def test_eur_conversion_passes(self):
        source = SourceOrder(
            OrderID=2,
            CustomerID="B",
            OrderDate=datetime(2023, 1, 1),
            Freight=Decimal("0"),
            details=[
                SourceOrderDetail(ProductID=1, UnitPrice=Decimal("100"), Quantity=1)
            ],
        )
        order = normalize(source, currency="EUR")
        # 100 * 1.10 = 110.00
        self.assertEqual(order.total_amount_base, Decimal("110.00"))
        excs = validate_currency_conversion(order)
        self.assertEqual(len(excs), 0)

    def test_mismatch_detected(self):
        from src.models.canonical import Order, OrderLine
        order = Order(
            source_order_id=3,
            original_currency="EUR",
            exchange_rate=Decimal("1.10"),
            total_amount=Decimal("100.00"),
            total_amount_base=Decimal("999.00"),  # Obviamente mal
            freight=Decimal("0"),
            lines=[OrderLine(product_id=1, unit_price=100, quantity=1, discount=0, line_total=100)],
        )
        excs = validate_currency_conversion(order)
        self.assertEqual(len(excs), 1)
        self.assertEqual(excs[0].rule_name, "CURRENCY_CONVERSION_MISMATCH")
```

### 4.4. Actualizar `tests/test_business_rules.py`

Anadir/assert en `TestNormalize` que `normalize` con default currency incluya:
- `order.original_currency == "USD"`
- `order.exchange_rate == Decimal("1.0")`
- `order.total_amount_base == order.total_amount`

No romper tests existentes (default currency hace esto transparente).

---

## 5. Archivos nuevos / modificados

**Nuevos:**
- `src/exchange/__init__.py`
- `src/exchange/mock_rates.py`
- `src/pipeline/assign_currency.py`
- `src/pipeline/validate_currency.py`
- `alembic/versions/002_add_currency_fields.py`
- `tests/test_mock_rates.py`
- `tests/test_assign_currency.py`
- `tests/test_validate_currency.py`

**Modificados:**
- `src/models/canonical.py` — 3 columnas nuevas en `Order`.
- `src/pipeline/normalize.py` — parametro `currency`, calculos de conversion.
- `src/main.py` — pasos `assign_currency` y `validate_currency_conversion`.
- `src/api/schemas.py` — campos nuevos en `OrderResponse`.
- `tests/test_business_rules.py` — asserts de campos nuevos en normalize.

---

## 6. Decisiones clave

1. **Mock fijo, no API externa:** se prioriza estabilidad y reproducibilidad. Se documenta claramente que las tasas no son reales.
2. **Tasa fija sin fecha:** simplifica el MVP. Se documenta como deuda tecnica.
3. **Conversion a nivel de orden:** se aplica `exchange_rate` sobre `total_amount`. En produccion futura se evaluara conversion linea por linea.
4. **Moneda asignada en pipeline, no en origen:** Northwind no tiene el campo. `assign_currency.py` actua como adapter.
5. **Campos nullable en DB:** `original_currency`, `exchange_rate` y `total_amount_base` son nullable para no romper ordenes previas sin datos. El pipeline siempre los pobla para ordenes nuevas.
6. **Redondeo explicito:** se usa `.quantize(Decimal('0.01'))` para evitar flotantes y garantizar consistencia.

---

## 7. Comandos de verificacion

```bash
# 1. Crear y aplicar migracion
alembic revision -m "add_currency_fields"
# Editar el archivo generado con el contenido del punto 1.2
alembic upgrade head

# 2. Instalar dependencias (si hubiera nuevas, en este caso no)
uv pip install -e ".[dev]"

# 3. Correr tests nuevos y existentes
uv run pytest tests/ -v

# 4. Pipeline manual
python -m src.main

# 5. Verificar API muestra campos nuevos
curl -H "X-API-Key: dev-key" http://localhost:8000/orders | jq
```

---

## 8. Limitaciones documentadas (para iteraciones futuras)

- **Tasas mock:** no reflejan mercado real. Iteracion futura: integrar proveedor de tipos de cambio (ej. ECB, Open Exchange Rates).
- **Tasa fija por moneda:** no hay variacion temporal. Iteracion futura: tabla `exchange_rates(date, currency, rate)`.
- **Conversion a nivel de orden:** si en el futuro lineas de una misma orden tienen monedas distintas, se debe mover la conversion a `OrderLine`.
- **Solo 3 monedas:** ampliar `RATES` o hacerlo configurable via entorno.
- **Moneda simulada:** cuando el sistema fuente (Northwind o reemplazo) tenga columna `Currency`, eliminar `assign_currency.py` y leer directamente de origen.

---

## 9. Estado de las reglas de negocio (post iteracion 3)

| Regla | Estado | Notas |
|-------|--------|-------|
| R1: Coherencia totales | Existente | `ORDER_TOTAL_MISMATCH` |
| R2: Deteccion duplicados | **Nueva** (Iter 2) | `DUPLICATE_LINE_ITEMS` |
| R3: Validacion fuente | **Nueva** (Iter 2) | `SOURCE_VALIDATION_FAILED` |
| R4: Idempotencia | Existente | `persist.py` |
| R5: Coherencia descuentos | **Nueva** (Iter 2) | `DISCOUNT_MISMATCH` |
| **R7: Coherencia conversion moneda** | **Nueva** (Iter 3) | `CURRENCY_CONVERSION_MISMATCH` |
| R8: Tasas de cambio reales | Pendiente | Requiere API externa y tabla historica |
