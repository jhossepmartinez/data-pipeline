import unittest
from decimal import Decimal
from datetime import datetime

from src.models.source import SourceOrder, SourceOrderDetail
from src.pipeline.normalize import normalize
from src.pipeline.validate_discounts import validate_line_discounts
from src.models.canonical import Order, OrderLine


class TestValidateDiscounts(unittest.TestCase):
    def test_valid_discounts_pass(self):
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
        excs = validate_line_discounts(order)
        self.assertEqual(len(excs), 0)

    def test_mismatched_discount_detected(self):
        order = Order(
            source_order_id=1,
            total_amount=Decimal("100.00"),
            freight=Decimal("0"),
            lines=[
                OrderLine(
                    product_id=1,
                    unit_price=Decimal("10.00"),
                    quantity=2,
                    discount=Decimal("0"),
                    line_total=Decimal("25.00"),  # Expected: 20.00
                ),
            ],
        )
        excs = validate_line_discounts(order)
        self.assertEqual(len(excs), 1)
        self.assertEqual(excs[0].rule_name, "DISCOUNT_MISMATCH")
        self.assertIn("Product 1", excs[0].message)
        self.assertEqual(excs[0].expected_value, Decimal("20.00"))
        self.assertEqual(excs[0].actual_value, Decimal("25.00"))

    def test_epsilon_tolerance(self):
        order = Order(
            source_order_id=2,
            total_amount=Decimal("100.00"),
            freight=Decimal("0"),
            lines=[
                OrderLine(
                    product_id=1,
                    unit_price=Decimal("10.00"),
                    quantity=3,
                    discount=Decimal("0.3333"),
                    # Expected ~ 20.001, within epsilon 0.01 if line_total=20.00
                    line_total=Decimal("20.00"),
                ),
            ],
        )
        excs = validate_line_discounts(order)
        self.assertEqual(len(excs), 0)

    def test_multiple_lines_one_failure(self):
        order = Order(
            source_order_id=3,
            total_amount=Decimal("100.00"),
            freight=Decimal("0"),
            lines=[
                OrderLine(
                    product_id=1,
                    unit_price=Decimal("10.00"),
                    quantity=1,
                    discount=Decimal("0"),
                    line_total=Decimal("10.00"),
                ),
                OrderLine(
                    product_id=2,
                    unit_price=Decimal("20.00"),
                    quantity=1,
                    discount=Decimal("0"),
                    line_total=Decimal("25.00"),  # Wrong
                ),
            ],
        )
        excs = validate_line_discounts(order)
        self.assertEqual(len(excs), 1)
        self.assertIn("Product 2", excs[0].message)


if __name__ == "__main__":
    unittest.main()
