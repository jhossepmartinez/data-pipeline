# Plan: Iteración 1 — Modelos + Migraciones + Regla R1 (Coherencia de Totales)

## Objetivo
Implementar un pipeline funcional con una sola regla de negocio:
> **R1:** El `total_amount` de una Orden debe ser igual a `Σ(Quantity × UnitPrice × (1 − Discount))` de todas sus líneas, más el `Freight`.

## Estructura de archivos

```
data-pipeline/
├── northwind.db                     # Fuente SQLite existente (solo lectura)
├── docker-compose.yml               # PostgreSQL
├── .env.example
├── requirements.txt
├── alembic.ini
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── (generado auto) 001_initial_canonical_schema.py
└── src/
    ├── __init__.py
    ├── database.py                  # Dos engines + session makers
    ├── config.py                    # Settings desde env vars
    ├── models/
    │   ├── __init__.py
    │   ├── source.py                # SourceOrder, SourceOrderDetail
    │   └── canonical.py             # Order, OrderLine, ValidationException
    ├── pipeline/
    │   ├── __init__.py
    │   ├── ingest.py                # SELECT desde SQLite
    │   ├── normalize.py             # Transformación + cálculo de totales
    │   ├── validate.py              # R1: Coherencia totales
    │   └── persist.py               # INSERT idempotente en PostgreSQL
    └── main.py                      # Entrypoint CLI
```

## Stack Tecnológico
- **uv**: Gestor de paquetes y entornos virtuales (reemplaza pip)
- **SQLAlchemy 2.0**: ORM para ambas bases
- **Alembic**: Migraciones versionadas
- **psycopg2-binary**: Driver PostgreSQL
- **PostgreSQL 16**: Base operativa (Docker)
- **python-dotenv**: Variables de entorno

## Arquitectura de bases de datos

| Aspecto | SQLite (`northwind.db`) | PostgreSQL (nueva) |
|---------|------------------------|-------------------|
| **Propósito** | Fuente de datos original | Base operativa canónica |
| **Acceso** | Solo lectura | Lectura y escritura |
| **Contenido** | Tablas originales de Northwind | Tablas canónicas + excepciones |
| **Migraciones** | No | Sí (Alembic) |
| **Engine** | `sqlite://` | `postgresql+psycopg2://` |

## Paso a paso

### 1. Infraestructura
- `docker-compose.yml`: PostgreSQL 16 con volumen persistente
- `requirements.txt`: Dependencias Python
- `.env.example`: Variables de entorno documentadas

### 2. Database Layer (`src/database.py`)
- `source_engine` → SQLite (solo lectura)
- `target_engine` → PostgreSQL (lectura/escritura)
- Context managers para sesiones seguras

### 3. Modelos Fuente (`src/models/source.py`)
Definición explícita basada en `models.md`:
- `SourceOrder` → tabla `Orders`
- `SourceOrderDetail` → tabla `Order Details`
- Relación `one-to-many` con `relationship()`

### 4. Modelos Canónicos (`src/models/canonical.py`)
- `Order`: Orden canónica con `source_order_id` (clave natural), `total_amount`, `status`
- `OrderLine`: Líneas de orden con `line_total` calculado
- `ValidationException`: Excepciones de validación con `rule_name`, `expected_value`, `actual_value`

### 5. Alembic
- `alembic init alembic`
- Configurar `env.py` para usar `BaseCanonical.metadata`
- Generar migración inicial con `--autogenerate`
- Aplicar con `alembic upgrade head`

### 6. Pipeline

#### Ingest (`src/pipeline/ingest.py`)
Leer órdenes desde SQLite con eager loading de líneas:
```python
session.query(SourceOrder).options(joinedload(SourceOrder.details))
```

#### Normalize (`src/pipeline/normalize.py`)
Transformar `SourceOrder` → `Order` canónico:
```
line_total = UnitPrice × Quantity × (1 - Discount)
total_amount = Σ(line_total) + Freight
```

#### Validate R1 (`src/pipeline/validate.py`)
```python
calculated_total = Σ(lines.line_total) + freight
if |total_amount - calculated_total| > epsilon:
    → ValidationException(rule_name="ORDER_TOTAL_MISMATCH")
```

#### Persist (`src/pipeline/persist.py`)
Idempotencia por `source_order_id`:
```python
existing = query.filter_by(source_order_id=order.source_order_id).first()
if existing: continue  # Skip si ya existe
```

### 7. Entrypoint (`src/main.py`)
Orquestar: ingest → normalize → validate → persist → report

### 8. Testing
- Unit: `normalize` calcula correctamente
- Unit: `validate` detecta mismatch
- Unit/Int: `persist` es idempotente
- E2E: Pipeline completo con 5 órdenes reales

## Decisiones clave

1. **Modelos explícitos vs automap**: Se elige definición explícita para mejor legibilidad, autocompletion, y revisionabilidad en el PR.

2. **Cálculo de total_amount**: Se calcula en `normalize()` y se almacena. La validación R1 recalcula y compara contra el valor almacenado.

3. **Idempotencia**: Skip si `source_order_id` ya existe. Estrategia simple y cumple "no duplica lo confirmado".

4. **Product model**: Se incluye en `canonical.py` vacío (solo `id`, `source_product_id`, `product_name`) para schema completo, pero no se llena en pipeline todavía.

5. **Logs estructurados**: Se dejan para iteración 2 para mantener scope mínimo.

## Comandos de verificación

```bash
docker compose up -d
pip install -r requirements.txt
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
python -m src.main
```

## Estado de la regla de negocio R1

| Campo | Valor |
|-------|-------|
| Nombre | Coherencia de totales de la orden vs suma de líneas |
| Fórmula | `total_amount = Σ(Quantity × UnitPrice × (1 − Discount)) + Freight` |
| Épsilon | 0.01 (tolerancia por redondeo) |
| Excepción | `ORDER_TOTAL_MISMATCH` |
| Severity | `error` |
