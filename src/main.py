import argparse
import logging
from decimal import Decimal

from src.database import get_source_session, get_target_session
from src.models.canonical import Order
from src.models.source import SourceOrder
from src.pipeline.ingest import fetch_orders
from src.pipeline.validate_source import validate_source
from src.pipeline.dedupe import check_duplicate_lines, check_canonical_duplicate_lines
from src.pipeline.assign_currency import assign_currency
from src.pipeline.normalize import normalize
from src.pipeline.validate_currency import validate_currency_conversion
from src.pipeline.validate_discounts import validate_line_discounts
from src.pipeline.validate import validate_order_total
from src.pipeline.persist import persist_orders
from src.pipeline.demo_corruption import apply_demo_corruption
from src.pipeline.northwind_verify import verify_northwind_hash
from src.api.demo_seeder import build_demo_source_orders

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def run_pipeline(
    limit: int | None = None,
    extra_orders: list[SourceOrder] | None = None,
    skip_source_read: bool = False,
) -> dict:
    """Orquesta el pipeline completo: ingest -> validate-source -> dedupe -> normalize -> consistency-checks -> persist."""
    verify_northwind_hash()
    if skip_source_read:
        raw_orders = []
    else:
        with get_source_session() as source_session:
            raw_orders = fetch_orders(source_session, limit=limit)
    if extra_orders:
        raw_orders = raw_orders + extra_orders
    print(f"Ingest: {len(raw_orders)} ordenes leidas de SQLite")

    orders_to_persist: list[Order] = []
    valid_count = 0
    invalid_count = 0

    for source_order in raw_orders:
        # 1. Source validation
        exceptions = validate_source(source_order)
        if exceptions:
            invalid_count += 1
            # Persistir orden minima para trazabilidad de errores de fuente
            order = Order(
                source_order_id=source_order.OrderID,
                customer_id=source_order.CustomerID,
                order_date=source_order.OrderDate,
                freight=source_order.Freight,
                total_amount=Decimal("0"),
                status="invalid",
                lines=[],
                exceptions=exceptions,
            )
            orders_to_persist.append(order)
            continue

        # 2. Dedupe check
        exceptions = check_duplicate_lines(source_order)
        if exceptions:
            invalid_count += 1
            # Crear orden minima para persistir trazabilidad
            order = Order(
                source_order_id=source_order.OrderID,
                customer_id=source_order.CustomerID,
                order_date=source_order.OrderDate,
                freight=source_order.Freight,
                total_amount=Decimal("0"),
                status="invalid",
                lines=[],
                exceptions=exceptions,
            )
            orders_to_persist.append(order)
            continue

        # 3. Assign currency
        currency = assign_currency(source_order)

        # 4. Normalize
        order = normalize(source_order, currency=currency)

        # 4b. Demo corruption: corromper ordenes demo para que fallen reglas
        order = apply_demo_corruption(order, source_order.OrderID)

        # 4c. Dedupe check en modelo canonico (para demo R2)
        exceptions = check_canonical_duplicate_lines(order)
        if exceptions:
            order.status = "invalid"
            order.exceptions = exceptions
            invalid_count += 1
            orders_to_persist.append(order)
            continue

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

        orders_to_persist.append(order)

    print(f"Validate: {valid_count} validas, {invalid_count} invalidas")

    with get_target_session() as target_session:
        stats = persist_orders(target_session, orders_to_persist)
        print(f"Persist: {stats['inserted']} insertadas, {stats['skipped']} omitidas")

        # Verificar counts en PostgreSQL
        from src.models.canonical import (
            OrderLine,
            ValidationException,
            Order as CanonicalOrder,
        )

        order_count = target_session.query(CanonicalOrder).count()
        line_count = target_session.query(OrderLine).count()
        exc_count = target_session.query(ValidationException).count()
        print(f"\nVerificacion PostgreSQL:")
        print(f"  canonical_orders: {order_count}")
        print(f"  canonical_order_lines: {line_count}")
        print(f"  validation_exceptions: {exc_count}")

    print("\nPipeline completado.")

    return {
        "read": len(raw_orders),
        "valid": valid_count,
        "invalid": invalid_count,
        "inserted": stats["inserted"],
        "skipped": stats["skipped"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Northwind Pipeline")
    parser.add_argument(
        "--with-demo",
        action="store_true",
        help="Incluir 5 ordenes de demostracion invalidas para verificar deteccion de errores",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limitar la cantidad de ordenes a procesar",
    )
    args = parser.parse_args()

    extra = build_demo_source_orders() if args.with_demo else None
    run_pipeline(limit=args.limit, extra_orders=extra)
