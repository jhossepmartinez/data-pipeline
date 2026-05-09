# Take-Home: Pipeline de Datos Northwind

## 1. Objetivo
Implementar un servicio pequeño que lea datos de negocio desde Northwind SQLite, los traduzca a un modelo canónico propio, ejecute un pipeline reproducible con logs estructurados (JSON) y correlation id, persista con esquema versionado, y exponga una superficie usable. Todo debe levantarse de forma reproducible (idealmente `docker compose up`, o una alternativa de un solo comando justificada).

## 2. Plazo
72 horas desde la recepción del correo.

## 3. Qué construir (en concreto)

- **Lectura de datos:** desde Northwind SQLite (URL fija de referencia). No mutar el archivo descargado. Copiarlo o importarlo al arranque.
- **Modelo canónico:** propio, fuerte, con entidades **Orden** y **Línea** y tipos explícitos.
- **Pipeline:** con etapas claras:
  1. ingest
  2. validate
  3. normalize
  4. dedupe
  5. consistency-checks
  6. persist
  7. serve/query
- **Persistencia:** en tu propia base con esquema versionado (migraciones o estrategia equivalente documentada).
- **Superficie de uso (al menos una):** REST + OpenAPI + API key, o CLI, o UI local de solo lectura. Debe permitir:
  - Ver órdenes procesadas / estado.
  - Consultar excepciones con motivo.
  - Disparar una re-ingesta y comprobar idempotencia (no duplica lo confirmado).

## 4. Fuente obligatoria
- **URL fija:** [https://raw.githubusercontent.com/jpwhite3/northwind-SQLite3/4f56e7f5906dfd23b25244c5bfe8fb5da6402efd/dist/northwind.db](https://raw.githubusercontent.com/jpwhite3/northwind-SQLite3/4f56e7f5906dfd23b25244c5bfe8fb5da6402efd/dist/northwind.db)
- El `.db` descargado es referencia fija. Cópialo o impórtalo a tu entorno operativo al iniciar. No lo uses como archivo mutable en runtime.

## 5. Requisitos obligatorios

- [ ] **README** con comando reproducible para descargar y verificar el archivo (opcional pero deseable: SHA-256 / tamaño ~24 MB).
- [ ] **Modelo canónico Orden/Línea** con tipos fuertes.
- [ ] **Pipeline explícito:** ingest → validate → normalize → dedupe → consistency-checks → persist → serve/query.
- [ ] **Idempotencia real + prueba** (clave natural clara).
- [ ] **Inconsistencias:** introduce o detecta datos problemáticos desde la misma fuente y expón cola/listado de excepciones con motivo.
- [ ] **Al menos 3 reglas de negocio no triviales**, implementadas y con tests. Elige al menos tres entre estas ideas (u otras equivalentes de complejidad similar):
  - Coherencia de totales de la orden vs suma de líneas.
  - Descuentos o impuestos que no cuadran.
  - Envío/flete separado vs ítems.
  - Cancelaciones o estados incompatibles con las líneas.
  - Detección de duplicados con ventana de tiempo + hash.
  - Multi-moneda con tipo de cambio simulado (mock) y documentado.
- [ ] **Persistencia real + migraciones/versionado explícito**.
- [ ] **Tests:** unitarios en dedupe/matching/reglas + ≥2 integración/e2e liviano.
- [ ] **`docker compose up`** o alternativa equivalente fuerte.

## 6. README: secciones obligatorias

1. Qué es / problema / usuarios (1–2 párrafos)
2. Arquitectura (diagrama Mermaid)
3. Fuente Northwind + verificación
4. Modelo canónico (ejemplo JSON)
5. Quickstart + tests
6. Decisiones + supuestos
7. Limitaciones
8. Threat model breve (auth/abuse/datos)
9. Uso de IA

## 7. Normas

- Puedes usar IA. En el README incluye cómo la usaste y qué validaste a mano.
- No subas secretos; deja `.env.example` completo.
- Si algo es ambiguo respecto del problema o del Northwind, puedes asumir, pero documenta el supuesto en el README (sección Decisiones / supuestos).

## 8. Entrega

- Repo público + README completo + commits razonables.
- Quickstart < 10 min en máquina limpia.
- Responder el correo con el link al repo antes del plazo.
