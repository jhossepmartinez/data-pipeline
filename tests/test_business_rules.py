import unittest
from decimal import Decimal
from datetime import datetime

from src.models.source import SourceOrder, SourceOrderDetail
from src.models.canonical import Order, OrderLine
from src.pipeline.normalize import normalize
from src.pipeline.validate import validate_order_total


class TestNormalize(unittest.TestCase):
    def test_normalize_computes_correct_total(self):
        """normalize() debe calcular line_total y total_amount correctamente."""
        source = SourceOrder(
            OrderID=10248,
            CustomerID="VINET",
            OrderDate=datetime(2023, 1, 1),
            Freight=Decimal("10.00"),
            details=[
                SourceOrderDetail(
                    ProductID=1,
                    UnitPrice=Decimal("10.00"),
                    Quantity=2,
                    Discount=Decimal("0"),
                ),
                SourceOrderDetail(
                    ProductID=2,
                    UnitPrice=Decimal("5.00"),
                    Quantity=1,
                    Discount=Decimal("0.10"),
                ),
            ],
        )

        order = normalize(source)

        # Line 1: 10.00 * 2 * (1 - 0) = 20.00
        self.assertEqual(order.lines[0].line_total, Decimal("20.00"))
        # Line 2: 5.00 * 1 * (1 - 0.10) = 4.50
        self.assertEqual(order.lines[1].line_total, Decimal("4.50"))
        # Total: 20.00 + 4.50 + 10.00 = 34.50
        self.assertEqual(order.total_amount, Decimal("34.50"))
        self.assertEqual(order.source_order_id, 10248)
        self.assertEqual(order.status, "pending")
        self.assertEqual(order.original_currency, "USD")
        self.assertEqual(order.exchange_rate, Decimal("1.0"))
        self.assertEqual(order.total_amount_base, order.total_amount)

    def test_normalize_with_zero_freight(self):
        """normalize() con freight = 0."""
        source = SourceOrder(
            OrderID=10249,
            CustomerID="TOMSP",
            Freight=Decimal("0"),
            details=[
                SourceOrderDetail(
                    ProductID=1,
                    UnitPrice=Decimal("100.00"),
                    Quantity=1,
                    Discount=Decimal("0"),
                ),
            ],
        )

        order = normalize(source)
        self.assertEqual(order.total_amount, Decimal("100.00"))
        self.assertEqual(order.freight, Decimal("0"))


class TestValidateR1(unittest.TestCase):
    def test_valid_order_passes(self):
        """Orden con totales coherentes no genera excepciones."""
        order = Order(
            source_order_id=1,
            total_amount=Decimal("110.00"),
            freight=Decimal("10.00"),
            lines=[
                OrderLine(
                    unit_price=Decimal("50.00"),
                    quantity=2,
                    discount=Decimal("0"),
                    line_total=Decimal("100.00"),
                ),
            ],
        )

        exceptions = validate_order_total(order)
        self.assertEqual(len(exceptions), 0)

    def test_invalid_order_detects_mismatch(self):
        """Orden con total incorrecto genera ORDER_TOTAL_MISMATCH."""
        order = Order(
            source_order_id=2,
            total_amount=Decimal("200.00"),
            freight=Decimal("10.00"),
            lines=[
                OrderLine(
                    unit_price=Decimal("50.00"),
                    quantity=2,
                    discount=Decimal("0"),
                    line_total=Decimal("100.00"),
                ),
            ],
        )

        exceptions = validate_order_total(order)
        self.assertEqual(len(exceptions), 1)
        self.assertEqual(exceptions[0].rule_name, "ORDER_TOTAL_MISMATCH")
        self.assertEqual(exceptions[0].expected_value, Decimal("110.00"))  # 100 + 10
        self.assertEqual(exceptions[0].actual_value, Decimal("200.00"))

    def test_epsilon_tolerance(self):
        """Diferencias menores a 0.01 no deben generar excepcion."""
        order = Order(
            source_order_id=3,
            total_amount=Decimal("100.005"),
            freight=Decimal("0"),
            lines=[
                OrderLine(
                    unit_price=Decimal("50.00"),
                    quantity=2,
                    discount=Decimal("0"),
                    line_total=Decimal("100.00"),
                ),
            ],
        )

        exceptions = validate_order_total(order)
        self.assertEqual(len(exceptions), 0)

    def test_epsilon_fails_just_above(self):
        """Diferencias mayores a 0.01 deben generar excepcion."""
        order = Order(
            source_order_id=4,
            total_amount=Decimal("100.02"),
            freight=Decimal("0"),
            lines=[
                OrderLine(
                    unit_price=Decimal("50.00"),
                    quantity=2,
                    discount=Decimal("0"),
                    line_total=Decimal("100.00"),
                ),
            ],
        )

        exceptions = validate_order_total(order)
        self.assertEqual(len(exceptions), 1)


if __name__ == "__main__":
    unittest.main()
