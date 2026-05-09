# Plan: Iteracion 2 — Pipeline Completo (Dedupe + Orden Correcto + API REST)

## Objetivo

Cerrar los gaps respecto al pipeline explicito requerido y anadir la superficie de uso REST/OpenAPI.

Pipeline requerido:

```
ingest -> validate -> normalize -> dedupe -> consistency-checks -> persist -> serve/query
```

Pipeline actual:

```
ingest -> normalize -> validate -> persist   (faltan validate-source, dedupe, consistency-checks, serve/query)
```

---

## Cambios respecto a Iteracion 1

### 1. Reordenar el pipeline (src/main.py)

Cambiar el orden de ejecucion para que sea:

1. **ingest** — leer `SourceOrder` + `SourceOrderDetail` desde SQLite.
2. **validate-source** — validaciones estructurales/minimas sobre datos crudos (requerido, tipos, etc.).
   - *En esta iteracion:* placeholder o validacion basica (ej: `OrderID` no nulo, `details` no vacio).
3. **normalize** — transformar a modelo canonico, calcular `line_total` y `total_amount`.
4. **dedupe** — detectar lineas duplicadas dentro de una misma orden.
   - Si un `ProductID` aparece 2+ veces en la misma orden → **skip orden completa** y registrar `ValidationException`.
4. **dedupe** — detectar lineas duplicadas dentro de una misma orden.
5. **validate-discounts** — coherencia de descuentos por linea (R5).
6. **consistency-checks** — reglas de negocio (R1 y futuras).
    - R1 se mantiene como esta (coherencia de totales). Se deja para iteracion futura repensar su utilidad.
7. **persist** — INSERT idempotente en PostgreSQL.
8. **serve/query** — API REST con OpenAPI.

### 2. Modulo `src/pipeline/dedupe.py` (nuevo)

**Regla:** Si dentro de una orden hay dos o mas `SourceOrderDetail` con el mismo `ProductID`, la orden es invalida.

**Comportamiento:**
- Recibe: `SourceOrder` (crudo) o `Order` canonica (decidir).
- Recomendacion: ejecutar **antes de normalizar** sobre `SourceOrder` para no desperdiciar calculos.
- Si hay duplicados:
  - No se normaliza la orden.
  - Se devuelve una excepcion `ValidationException` con:
    - `rule_name`: `DUPLICATE_LINE_ITEMS`
    - `message`: lista de `ProductID` duplicados
    - `severity`: `error`
  - La orden se marca como `invalid` y no continua al pipeline.

**Ejemplo de logica:**

```python
def check_duplicate_lines(source_order: SourceOrder) -> list[ValidationException]:
    seen = set()
    duplicates = set()
    for detail in source_order.details:
        if detail.ProductID in seen:
            duplicates.add(detail.ProductID)
        seen.add(detail.ProductID)
    if duplicates:
        return [ValidationException(...)]
    return []
```

### 2b. Modulo `src/pipeline/validate_discounts.py` (nuevo) — R5

**Regla:** Cada linea debe cumplir `line_total = unit_price * quantity * (1 - discount)`.

**Comportamiento:**
- Recibe: `Order` canonica (post-normalize).
- Si hay discrepancia mayor a epsilon (0.01):
  - Se devuelve `ValidationException` por linea afectada con:
    - `rule_name`: `DISCOUNT_MISMATCH`
    - `message`: producto, valores esperado/actual
    - `expected_value` / `actual_value`
  - La orden se marca como `invalid`.

**Supuestos:**
1. Descuento solo a nivel de linea (no a nivel de orden).
2. Formula: `unit_price * quantity * (1 - discount)`.
3. Epsilon = 0.01 (mismo que R1).
4. No hay impuestos en el modelo actual (ver nota R6 abajo).

---

### 3. Modulo `src/pipeline/validate_source.py` (nuevo)

Validaciones estructurales sobre datos crudos antes de normalizar.

Para esta iteracion, cubrir como minimo:
- `OrderID` no es `None`.
- `details` no esta vacio (una orden sin lineas es invalida).
- Opcional: `OrderDate` no es `None`.

Si falla → `ValidationException` con `rule_name = SOURCE_VALIDATION_FAILED` y se skipea la orden.

### 4. API REST (`src/api/` nuevo)

**Framework:** FastAPI (genera OpenAPI automaticamente, ligero, tipado).

**Endpoints minimos:**

| Metodo | Path | Descripcion |
|--------|------|-------------|
| GET | `/orders` | Listar ordenes procesadas (paginado, filtros por `status`, `customer_id`) |
| GET | `/orders/{source_order_id}` | Ver una orden y sus lineas |
| GET | `/exceptions` | Listar excepciones (paginado, filtro por `rule_name`, `severity`) |
| POST | `/ingest` | Disparar re-ingesta manualmente (idem con el pipeline) |
| GET | `/health` | Healthcheck |

**Modelos Pydantic:**
- `OrderResponse` — serializacion de `Order` + `lines`.
- `ExceptionResponse` — serializacion de `ValidationException`.
- `IngestResponse` — resumen del pipeline (cuantas ordenes leidas, validas, invalidas, insertadas).

**Seguridad:**
- API key via header `X-API-Key`.
- Valor leido de `API_KEY` en `.env`.
- Middleware simple que rechaza 401 si no coincide.

**Servidor:**
- `uvicorn src.api.main:app --reload` en desarrollo.
- Puerto configurable via `API_PORT` (default 8000).

### 5. Actualizar `src/main.py`

Nuevo flujo orquestado:

```python
def run_pipeline(limit=None):
    raw_orders = fetch_orders(...)

    for source_order in raw_orders:
        # 1. Source validation
        exceptions = validate_source(source_order)
        if exceptions: ...continue

        # 2. Dedupe check
        exceptions = check_duplicate_lines(source_order)
        if exceptions: ...continue

        # 3. Normalize
        order = normalize(source_order)

        # 4. Discount checks (R5)
        exceptions = validate_line_discounts(order)

        # 5. Consistency checks (R1, etc.)
        if not exceptions:
            exceptions = validate_order_total(order)

        if exceptions:
            order.status = "invalid"
            order.exceptions = exceptions
        else:
            order.status = "valid"

        # 6. Persist
        ...
```

Nota: `persist.py` solo debe insertar ordenes con `status = "valid"`. Las `invalid` se pueden persistir tambien (con sus excepciones) para tener trazabilidad, o solo persistir las excepciones sin la orden. **Decision:** persistir orden + excepciones para que la API pueda mostrar ordenes invalidas con su motivo.

### 6. Tests a anadir (`tests/`)

| Test | Que cubre |
|------|-----------|
| `test_validate_source.py` | Orden sin `OrderID` es invalida. Orden sin detalles es invalida. |
| `test_dedupe.py` | Orden con ProductID duplicado genera `DUPLICATE_LINE_ITEMS`. Orden con productos unicos pasa. |
| `test_validate_discounts.py` | Descuento correcto pasa. Descuento desfasado genera `DISCOUNT_MISMATCH`. Epsilon tolera redondeo. |
| `test_api_orders.py` | GET `/orders` devuelve lista. GET `/orders/{id}` devuelve 404 si no existe. |
| `test_api_exceptions.py` | GET `/exceptions` devuelve excepciones. Filtro por `rule_name` funciona. |
| `test_api_ingest.py` | POST `/ingest` dispara pipeline y devuelve resumen. Re-ingesta es idempotente. |
| `test_api_auth.py` | Sin API key devuelve 401. Con API key correcta pasa. |

### 7. Dependencias nuevas (`requirements.txt`)

```
fastapi>=0.100.0
uvicorn[standard]>=0.23.0
pydantic>=2.0.0
```

### 8. Archivos nuevos / modificados

**Nuevos:**
- `src/pipeline/validate_source.py`
- `src/pipeline/dedupe.py`
- `src/pipeline/validate_discounts.py`
- `src/api/__init__.py`
- `src/api/main.py`
- `src/api/routes.py`
- `src/api/auth.py`
- `src/api/schemas.py`
- `tests/test_validate_source.py`
- `tests/test_dedupe.py`
- `tests/test_validate_discounts.py`
- `tests/test_api.py`

**Modificados:**
- `src/main.py` — reordenar pipeline, anadir dedupe y validate-source.
- `requirements.txt` — anadir FastAPI + uvicorn.
- `.env.example` — anadir `API_KEY`, `API_PORT`.

---

## Decisiones clave

1. **Dedupe antes de normalize:** para evitar calcular totales de datos que ya sabemos que van a ser rechazados.
2. **Persistir ordenes invalidas:** la API debe poder mostrar tanto ordenes validas como invalidas (con sus excepciones). Esto cumple el requisito *"consultar excepciones con motivo"*.
3. **R1 se mantiene como esta:** se deja para iteracion futura repensar si se convierte en post-persist check o se elimina.
4. **API key simple:** no JWT/OAuth. Un header `X-API-Key` contra una env var es suficiente para el scope.
5. **No dockerizar API todavia:** se documenta el comando `uvicorn`. Docker compose se actualiza en iteracion futura si es necesario.

---

## Comandos de verificacion

```bash
# Instalar dependencias nuevas
pip install -r requirements.txt

# Correr tests
pytest tests/ -v

# Levantar API local
uvicorn src.api.main:app --reload

# Probar pipeline completo
python -m src.main

# Healthcheck
curl http://localhost:8000/health

# Listar ordenes
curl -H "X-API-Key: dev-key" http://localhost:8000/orders

# Disparar ingest
curl -X POST -H "X-API-Key: dev-key" http://localhost:8000/ingest
```

---

## Nota de extension: Impuestos (R6 futura)

El esquema Northwind de origen **no incluye impuestos**. Para anadir una regla de coherencia de impuestos se requiere:

1. **Enriquecer el modelo canónico** con campos de impuesto:
   - `OrderLine.tax_rate` (ej. 0.21)
   - `OrderLine.tax_amount` (calculado)
   - `Order.tax_total` (suma de lineas)

2. **Definir supuestos de negocio:**
   - Fuente de verdad de la tasa: ¿fija, por producto, por region, por cliente?
   - Base imponible: ¿sobre subtotal con o sin descuento?
   - Redondeo: ¿por linea o por total?

3. **Implementacion propuesta:**
   ```python
   def validate_tax_total(order: Order) -> list[ValidationException]:
       subtotal = sum(line.line_total for line in order.lines)
       tax_total = sum(line.line_total * line.tax_rate for line in order.lines)
       expected = subtotal + order.freight + tax_total
       if abs(order.total_amount - expected) > epsilon:
           return [ValidationException(rule_name="TAX_TOTAL_MISMATCH", ...)]
       return []
   ```

4. **Cambios en el pipeline:**
   - `normalize.py`: calcular `tax_amount` por linea si se dispone de `tax_rate`.
   - `src/main.py`: ejecutar `validate_tax_total` despues de `validate_line_discounts` y antes de R1.

---

## Estado de las reglas de negocio

| Regla | Estado | Notas |
|-------|--------|-------|
| R1: Coherencia totales | Existente | Se mantiene en `consistency-checks` sin cambios |
| R2: Deteccion duplicados | **Nueva** | `DUPLICATE_LINE_ITEMS`, skip orden |
| R3: Validacion fuente | **Nueva** | `SOURCE_VALIDATION_FAILED`, validaciones estructurales minimas |
| R4: Idempotencia | Existente | Ya en `persist.py`, se prueba via API re-ingest |
| R5: Coherencia descuentos | **Nueva** | `DISCOUNT_MISMATCH`, valida `line_total` por linea |
| R6: Coherencia impuestos | **Pendiente** | Requiere enriquecer modelo con `tax_rate` / `tax_amount` |
