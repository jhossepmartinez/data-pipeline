import unittest
from datetime import datetime
from decimal import Decimal

from src.models.source import SourceOrder, SourceOrderDetail
from src.pipeline.validate_source import validate_source


class TestValidateSource(unittest.TestCase):
    def test_order_without_order_id_is_invalid(self):
        order = SourceOrder(
            OrderID=None,
            CustomerID="VINET",
            OrderDate=datetime(2023, 1, 1),
            details=[
                SourceOrderDetail(ProductID=1, UnitPrice=Decimal("10"), Quantity=1)
            ],
        )
        excs = validate_source(order)
        self.assertEqual(len(excs), 1)
        self.assertEqual(excs[0].rule_name, "SOURCE_VALIDATION_FAILED")
        self.assertIn("OrderID", excs[0].message)

    def test_order_without_details_is_invalid(self):
        order = SourceOrder(
            OrderID=10248,
            CustomerID="VINET",
            OrderDate=datetime(2023, 1, 1),
            details=[],
        )
        excs = validate_source(order)
        self.assertEqual(len(excs), 1)
        self.assertEqual(excs[0].rule_name, "SOURCE_VALIDATION_FAILED")
        self.assertIn("details", excs[0].message)

    def test_order_without_order_date_is_invalid(self):
        order = SourceOrder(
            OrderID=10248,
            CustomerID="VINET",
            OrderDate=None,
            details=[
                SourceOrderDetail(ProductID=1, UnitPrice=Decimal("10"), Quantity=1)
            ],
        )
        excs = validate_source(order)
        self.assertTrue(any("OrderDate" in e.message for e in excs))

    def test_valid_order_passes(self):
        order = SourceOrder(
            OrderID=10248,
            CustomerID="VINET",
            OrderDate=datetime(2023, 1, 1),
            details=[
                SourceOrderDetail(ProductID=1, UnitPrice=Decimal("10"), Quantity=1)
            ],
        )
        excs = validate_source(order)
        self.assertEqual(len(excs), 0)


if __name__ == "__main__":
    unittest.main()
