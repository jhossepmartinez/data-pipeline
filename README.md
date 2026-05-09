# Data Pipeline — Northwind SQLite to PostgreSQL

Pipeline de datos que lee ordenes de negocio desde **Northwind SQLite** (solo lectura), las valida contra reglas de negocio, y persiste el resultado en **PostgreSQL**.

Todo corre dentro de contenedores Docker. No necesitas instalar Python, uv, ni PostgreSQL en tu maquina.

---

## Arquitectura

```
Northwind SQLite (solo lectura, montado como volumen)
        |
        v
  fetch_orders()        ← lee sin mutar
        |
        v
  Pipeline de validacion:
    - R3: validate_source()          (order_date, order_id, details)
    - R2: check_duplicate_lines()    (productos duplicados en una orden)
    - assign_currency()              (USD/EUR/GBP)
    - normalize()                    (calcula totales, lineas)
    - R7: validate_currency_conversion()
    - R5: validate_line_discounts()
    - R1: validate_order_total()
        |
        v
  persist_orders()      → PostgreSQL (canonico)
```

---

## Requisitos

- Docker + Docker Compose
- Archivo `data/raw/northwind.db` descargado manualmente (ver paso 2)

**No necesitas:** Python, uv, PostgreSQL, ni ninguna dependencia local.

---

## Setup paso a paso (para revisores)

### 1. Clonar el repo

```bash
git clone <repo-url>
cd data-pipeline
```

### 2. Descargar Northwind SQLite (paso manual obligatorio)

**No incluimos `northwind.db` en el repo.** Debes descargarlo manualmente para garantizar que usas la version esperada.

```bash
# Crear directorio si no existe
mkdir -p data/raw

# Descargar desde el repo oficial
curl -L -o data/raw/northwind.db \
  https://raw.githubusercontent.com/jpwhite3/northwind-SQLite3/\
4f56e7f5906dfd23b25244c5bfe8fb5da6402efd/dist/northwind.db
```

El pipeline **verifica el hash SHA-256** del archivo antes de ejecutarse. Si el hash no coincide, el pipeline falla con un mensaje claro:

```
RuntimeError: Hash mismatch para Northwind DB.
  Esperado: 2f4f5c68dfcd33ba27373eae48c7a4869800c68095ee0f9f0da494f83382a877
  Actual:   <hash-del-archivo-que-subiste>
```

### 3. Levantar PostgreSQL (Docker)

```bash
# Construir imagenes y levantar PostgreSQL
docker compose up -d db

# Verificar que este saludable
docker compose ps
```

### 4. Correr tests

```bash
docker compose run --rm test
```

**Esperado: 53 tests passed.**  
Las migraciones de Alembic se ejecutan automaticamente antes de los tests.

### 5. Levantar la API

```bash
docker compose up -d api
```

La API estara disponible en `http://localhost:8000`.

### 6. Health check

```bash
curl http://localhost:8000/health
```

Respuesta esperada:
```json
{"status":"ok"}
```

### 7. Testear endpoints de la API

#### 7a. Ver endpoints disponibles

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/ingest` | Corre el pipeline completo |
| GET | `/orders` | Lista ordenes canonicas (paginado) |
| GET | `/orders?status=invalid` | Filtra por estado |
| GET | `/orders/{id}` | Detalle de una orden |
| GET | `/exceptions` | Lista excepciones de validacion |
| GET | `/exceptions?rule_name=...` | Filtra por regla |
| POST | `/demo/seed-errors` | Inserta 5 ordenes demo invalidas (idempotente, **solo demo**) |
| POST | `/demo/reset-and-seed` | **TRUNCA** PostgreSQL + corre pipeline completo (Northwind + 5 demo) |

**ATENCION:** `/demo/reset-and-seed` es **destructivo**. Borra todas las tablas canonicas antes de insertar. Usalo solo para demos o reiniciar desde cero.

Todos los endpoints (salvo `/health`) requieren header:
```
X-API-Key: dev-key
```

#### 7b. Flujo completo de demo (recomendado)

```bash
# Paso 1: Resetear target + seedear ordenes invalidas de demostracion
# ATENCION: esto BORRA todos los datos existentes en PostgreSQL
curl -X POST -H "X-API-Key: dev-key" http://localhost:8000/demo/reset-and-seed | jq
# Esperado: {"read":16287,"valid":16282,"invalid":5,"inserted":16287,"skipped":0,"orders":[900001,...]}

# Paso 2: Ver ordenes invalidas generadas por las reglas de negocio
curl -H "X-API-Key: dev-key" "http://localhost:8000/orders?status=invalid" | jq
# Esperado: 5 ordenes DEMO-* con status="invalid"

# Paso 3: Ver todas las excepciones generadas
curl -H "X-API-Key: dev-key" "http://localhost:8000/exceptions" | jq
# Esperado: 5 excepciones (R1, R2, R3, R5, R7)

# Paso 4: Filtrar excepciones por regla especifica
curl -H "X-API-Key: dev-key" \
  "http://localhost:8000/exceptions?rule_name=CURRENCY_CONVERSION_MISMATCH" | jq
# Esperado: 1 excepcion de la orden DEMO-R7
```

#### 7c. Flujo idempotente (sin reset)

**Nota:** `POST /demo/seed-errors` **solo procesa las 5 ordenes demo** (no re-lee Northwind). Si ya existen en la base, se omiten.

```bash
# Primera vez en base limpia: inserta 5 ordenes demo
curl -X POST -H "X-API-Key: dev-key" http://localhost:8000/demo/seed-errors | jq
# {"inserted":5,"skipped":0,"orders":[900001,900002,900003,900004,900005]}

# Segunda vez: ya existen, se omiten (idempotente)
curl -X POST -H "X-API-Key: dev-key" http://localhost:8000/demo/seed-errors | jq
# {"inserted":0,"skipped":5,"orders":[900001,900002,900003,900004,900005]}
```

#### 7d. Ingesta completa (Northwind real)

```bash
# Corre el pipeline leyendo todas las ordenes de Northwind
curl -X POST -H "X-API-Key: dev-key" http://localhost:8000/ingest | jq
```

---

## Reglas de negocio validadas

| Regla | Descripcion | Demo Order |
|-------|-------------|------------|
| R1 | `ORDER_TOTAL_MISMATCH` — total_amount != sum(lines) + freight | 900004 |
| R2 | `DUPLICATE_LINE_ITEMS` — product_id repetido en lineas | 900003 |
| R3 | `SOURCE_VALIDATION_FAILED` — order_date, order_id o details faltan | 900005 |
| R5 | `DISCOUNT_MISMATCH` — line_total != unit_price * qty * (1 - discount) | 900002 |
| R7 | `CURRENCY_CONVERSION_MISMATCH` — total_amount_base != total_amount * rate | 900001 |

### Datos demo para verificar deteccion de errores

Las 5 ordenes demo (IDs 900001-900005) se construyen **en memoria** (nunca se muta SQLite). Fueron agregadas intencionalmente para que el revisor pueda verificar que el pipeline realmente detecta errores, ya que las 16,282 ordenes originales de Northwind son todas validas.

**Como funcionan las demo:**
1. Se construyen objetos `SourceOrder` en Python (sin tocar ninguna base de datos)
2. Se pasan al pipeline como `extra_orders`
3. El pipeline las procesa igual que las ordenes reales
4. `apply_demo_corruption()` modifica los valores post-normalizacion para que fallen las reglas
5. Las reglas de negocio generan excepciones naturalmente
6. Se persisten en PostgreSQL con `status="invalid"` y sus `ValidationException`

---

## Tests

### Correr tests

```bash
# Todos los tests (dentro de Docker)
docker compose run --rm test

# Solo tests de API
docker compose run --rm test pytest tests/test_api.py -v

# Solo tests unitarios de reglas
docker compose run --rm test pytest tests/test_business_rules.py tests/test_validate_currency.py \
  tests/test_validate_discounts.py tests/test_validate_source.py tests/test_dedupe.py -v

# Con coverage
docker compose run --rm test pytest --cov=src --cov-report=term-missing -v
```

### Coverage por categoria

**Total: 53 tests**

#### 1. Tests unitarios de reglas de negocio (28 tests)

Validan cada regla del pipeline de forma aislada:

| Suite | Tests | Regla | Cobertura |
|-------|-------|-------|-----------|
| `test_validate_source.py` | 4 | R3 | order_date faltante, order_id faltante, details vacios, orden valida |
| `test_dedupe.py` | 2 | R2 | product_ids duplicados, productids unicos |
| `test_business_rules.py` | 4 | R1 | total calculado correctamente, freight=0, mismatch detectado, epsilon tolerance |
| `test_validate_currency.py` | 7 | R7 | USD passthrough, EUR conversion, GBP conversion, mismatch detectado, epsilon, pipeline mixed orders |
| `test_validate_discounts.py` | 4 | R5 | descuento valido, mismatch detectado, epsilon, multiple lines |
| `test_assign_currency.py` | 2 | — | default USD, mock EUR injection |
| `test_mock_rates.py` | 5 | — | USD=1.0, EUR=1.10, GBP=1.27, unsupported, case-insensitive |

#### 2. Tests de integracion / persistencia (3 tests)

| Suite | Tests | Cobertura |
|-------|-------|-----------|
| `test_integration.py` | 3 | Insert de ordenes, idempotencia (ON CONFLICT DO NOTHING), persist con lineas y excepciones |

#### 3. Tests de API / E2E (14 tests)

| Test | Tipo | Cobertura |
|------|------|-----------|
| `test_health` | E2E | Health check basico |
| `test_orders_without_auth` | E2E | Autenticacion rechaza sin API key |
| `test_orders_with_auth_empty` | E2E | Lista vacia cuando no hay datos |
| `test_get_order_not_found` | E2E | 404 cuando orden no existe |
| `test_exceptions_empty` | E2E | Lista vacia de excepciones |
| `test_list_orders_with_data` | E2E | Listado con datos insertados directamente |
| `test_list_exceptions_with_filter` | E2E | Filtrado por rule_name |
| `test_ingest` | E2E (mock) | Endpoint /ingest con pipeline mockeado |
| `test_seed_errors_without_auth` | E2E | Autenticacion rechaza en /demo/seed-errors |
| `test_seed_errors_inserts_demo_orders_and_generates_exceptions` | **E2E completo** | Pipeline real: memoria → reglas de negocio → PostgreSQL |
| `test_seed_errors_is_idempotent` | **E2E idempotencia** | Segunda llamada: 0 insertadas, 5 skipped |
| `test_reset_and_seed_without_auth` | E2E | Autenticacion rechaza en /demo/reset-and-seed |
| `test_reset_and_seed_clears_and_inserts_demo` | **E2E destructivo** | Trunca + inserta + verifica |
| `test_reset_and_seed_is_repeatable` | **E2E destructivo** | Llamada repetida trunca e inserta de nuevo |

#### 4. Tests de verificacion de integridad de fuente (4 tests)

| Suite | Tests | Cobertura |
|-------|-------|-----------|
| `test_northwind_verify.py` | 4 | Hash correcto, hash incorrecto, DB faltante, hash file faltante |

### Tests por flujo del pipeline

```
Flujo completo (E2E):
  test_seed_errors_inserts_demo_orders_and_generates_exceptions
  test_reset_and_seed_clears_and_inserts_demo
  test_reset_and_seed_is_repeatable
  test_validate_currency.py::test_pipeline_* (4 tests)

Flujo de autenticacion:
  test_orders_without_auth
  test_seed_errors_without_auth
  test_reset_and_seed_without_auth

Flujo de idempotencia:
  test_seed_errors_is_idempotent
  test_integration.py::test_persist_is_idempotent

Flujo de validacion de reglas (unitarios):
  test_validate_source.py (4)
  test_dedupe.py (2)
  test_business_rules.py (4)
  test_validate_currency.py (7)
  test_validate_discounts.py (4)

Flujo de integridad de datos:
  test_northwind_verify.py (4)
  test_integration.py (3)
```

---

## Comandos Docker utiles

```bash
# Levantar todo (API + PostgreSQL)
docker compose up -d

# Ver logs
docker compose logs -f api
docker compose logs -f db

# Correr pipeline manualmente (solo Northwind, todas validas)
docker compose run --rm pipeline

# Correr pipeline con datos demo (muestra deteccion de errores)
docker compose run --rm pipeline --with-demo

# Correr tests
docker compose run --rm test

# Correr tests con coverage
docker compose run --rm test pytest --cov=src --cov-report=term-missing -v

# Shell dentro del contenedor de la app
docker compose run --rm pipeline bash

# Reiniciar desde cero (borra volumen de PostgreSQL)
docker compose down -v
docker compose up -d db
# Las migraciones se ejecutan automaticamente al correr cualquier servicio

# Reconstruir imagenes despues de cambios en codigo
docker compose build
```

---

## Estructura del proyecto

```
data-pipeline/
├── data/
│   └── raw/
│       ├── northwind.db              # SQLite fuente (NO incluido en repo)
│       └── northwind.db.sha256       # Hash esperado (SI incluido)
├── docker-compose.yml                # Orquestacion: db, api, pipeline, test
├── Dockerfile                        # Imagen de la app
├── pyproject.toml                    # Dependencias
├── README.md                         # Esta guia
├── alembic/                          # Migraciones de PostgreSQL
│   └── versions/
│       ├── 001_initial_canonical_schema.py
│       └── 002_add_currency_fields.py
├── src/
│   ├── api/                          # FastAPI REST
│   │   ├── main.py
│   │   ├── routes.py
│   │   ├── schemas.py
│   │   ├── auth.py
│   │   └── demo_seeder.py           # Construye ordenes demo en memoria
│   ├── pipeline/                     # Logica de negocio
│   │   ├── ingest.py
│   │   ├── normalize.py
│   │   ├── validate_source.py       # R3
│   │   ├── dedupe.py                # R2
│   │   ├── assign_currency.py
│   │   ├── validate_currency.py     # R7
│   │   ├── validate_discounts.py    # R5
│   │   ├── validate.py              # R1
│   │   ├── persist.py
│   │   ├── demo_corruption.py       # Corrompe ordenes demo post-normalizacion
│   │   ├── reset_target.py          # Trunca tablas (destructivo)
│   │   ├── northwind_verify.py      # Verifica hash SHA-256
│   │   └── mock_rates.py
│   ├── models/
│   │   ├── source.py
│   │   └── canonical.py
│   ├── config.py
│   ├── database.py
│   └── main.py                       # Entrypoint del pipeline
└── tests/                            # Tests unitarios + e2e
    ├── test_api.py                   # 14 tests de API / E2E
    ├── test_northwind_verify.py      # 4 tests de integridad de fuente
    ├── test_validate_source.py       # 4 tests de R3
    ├── test_dedupe.py                # 2 tests de R2
    ├── test_business_rules.py        # 4 tests de R1
    ├── test_validate_currency.py     # 7 tests de R7
    ├── test_validate_discounts.py    # 4 tests de R5
    ├── test_assign_currency.py       # 2 tests
    ├── test_mock_rates.py            # 5 tests
    └── test_integration.py           # 3 tests de persistencia
```

---

## Variables de entorno

| Variable | Default | Descripcion |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+psycopg2://pipeline_user:pipeline_pass@db:5432/pipeline_db` | PostgreSQL target |
| `SOURCE_DB_PATH` | `data/raw/northwind.db` | Ruta al SQLite fuente (dentro del contenedor) |
| `SOURCE_DB_HASH_PATH` | `data/raw/northwind.db.sha256` | Ruta al archivo de hash esperado |
| `API_KEY` | `dev-key` | Key para autenticar endpoints |
| `API_PORT` | `8000` | Puerto de la API |

Estas variables ya estan configuradas en `docker-compose.yml`. Solo necesitas cambiarlas si queres apuntar a otra base de datos.

---

## Notas para el revisor

1. **Docker-only:** No necesitas instalar nada en tu maquina. Todo corre en contenedores.
2. **Northwind es solo lectura:** el pipeline nunca escribe en `data/raw/northwind.db`. La verificacion de hash garantiza integridad.
3. **Demo orders en memoria:** `POST /demo/seed-errors` no muta la fuente. Construye objetos Python, los pasa al pipeline, y las reglas generan excepciones.
4. **Idempotencia:** correr `/ingest` o `/demo/seed-errors` dos veces no duplica datos en PostgreSQL. Usa `ON CONFLICT DO NOTHING` en `source_order_id`.
5. **Reset destructivo explicito:** `POST /demo/reset-and-seed` **trunca** todas las tablas canonicas antes de insertar. El path `/demo/reset-and-seed` lo deja claro.
6. **Tests autocontenidos:** `docker compose run --rm test` no requiere nada instalado localmente.
7. **Datos demo para verificar errores:** Las 16,282 ordenes de Northwind son todas validas. Agregamos 5 ordenes demo corruptas (en memoria) para que el revisor pueda verificar que el pipeline realmente detecta y reporta errores.
8. **Alembic para migraciones:** Las migraciones se ejecutan automaticamente al iniciar cualquier servicio (`api`, `pipeline`, `test`). No necesitas crear tablas manualmente.
9. **CLI con `--with-demo`:** El pipeline CLI (`docker compose run --rm pipeline --with-demo`) incluye las 5 ordenes demo para verificar deteccion de errores sin necesidad de la API.
