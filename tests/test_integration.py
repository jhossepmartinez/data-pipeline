import unittest
from decimal import Decimal
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.canonical import BaseCanonical, Order, OrderLine, ValidationException
from src.pipeline.persist import persist_orders


class TestPersist(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        BaseCanonical.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def test_persist_inserts_new_orders(self):
        """persist_orders debe insertar ordenes nuevas."""
        session = self.Session()
        orders = [
            Order(
                source_order_id=1,
                total_amount=Decimal("100.00"),
                freight=Decimal("10.00"),
            ),
            Order(
                source_order_id=2,
                total_amount=Decimal("200.00"),
                freight=Decimal("20.00"),
            ),
        ]

        stats = persist_orders(session, orders)

        self.assertEqual(stats["inserted"], 2)
        self.assertEqual(stats["skipped"], 0)

        count = session.query(Order).count()
        self.assertEqual(count, 2)

    def test_persist_is_idempotent(self):
        """Correr dos veces no debe duplicar ordenes."""
        session = self.Session()
        orders = [
            Order(
                source_order_id=1,
                total_amount=Decimal("100.00"),
                freight=Decimal("10.00"),
            ),
        ]

        stats1 = persist_orders(session, orders)
        self.assertEqual(stats1["inserted"], 1)
        self.assertEqual(stats1["skipped"], 0)

        stats2 = persist_orders(session, orders)
        self.assertEqual(stats2["inserted"], 0)
        self.assertEqual(stats2["skipped"], 1)

        count = session.query(Order).count()
        self.assertEqual(count, 1)

    def test_persist_with_lines_and_exceptions(self):
        """persist_orders debe insertar ordenes con lineas y excepciones."""
        session = self.Session()
        order = Order(
            source_order_id=99,
            total_amount=Decimal("200.00"),
            freight=Decimal("10.00"),
            status="invalid",
            lines=[
                OrderLine(
                    product_id=1,
                    unit_price=Decimal("50.00"),
                    quantity=2,
                    discount=Decimal("0"),
                    line_total=Decimal("100.00"),
                ),
                OrderLine(
                    product_id=2,
                    unit_price=Decimal("90.00"),
                    quantity=1,
                    discount=Decimal("0"),
                    line_total=Decimal("90.00"),
                ),
            ],
            exceptions=[
                ValidationException(
                    rule_name="ORDER_TOTAL_MISMATCH",
                    message="Total mismatch",
                    expected_value=Decimal("100.00"),
                    actual_value=Decimal("200.00"),
                ),
            ],
        )

        persist_orders(session, [order])

        stored = session.query(Order).filter_by(source_order_id=99).first()
        self.assertIsNotNone(stored)
        self.assertEqual(len(stored.lines), 2)
        self.assertEqual(len(stored.exceptions), 1)
        self.assertEqual(stored.exceptions[0].rule_name, "ORDER_TOTAL_MISMATCH")


if __name__ == "__main__":
    unittest.main()
