import unittest
from datetime import datetime
from decimal import Decimal

from src.models.source import SourceOrder, SourceOrderDetail
from src.pipeline.dedupe import check_duplicate_lines


class TestDedupe(unittest.TestCase):
    def test_duplicate_product_ids_generate_exception(self):
        order = SourceOrder(
            OrderID=10248,
            CustomerID="VINET",
            OrderDate=datetime(2023, 1, 1),
            details=[
                SourceOrderDetail(ProductID=1, UnitPrice=Decimal("10"), Quantity=1),
                SourceOrderDetail(ProductID=1, UnitPrice=Decimal("12"), Quantity=1),
                SourceOrderDetail(ProductID=2, UnitPrice=Decimal("5"), Quantity=1),
            ],
        )
        excs = check_duplicate_lines(order)
        self.assertEqual(len(excs), 1)
        self.assertEqual(excs[0].rule_name, "DUPLICATE_LINE_ITEMS")
        self.assertIn("1", excs[0].message)

    def test_unique_product_ids_pass(self):
        order = SourceOrder(
            OrderID=10248,
            CustomerID="VINET",
            OrderDate=datetime(2023, 1, 1),
            details=[
                SourceOrderDetail(ProductID=1, UnitPrice=Decimal("10"), Quantity=1),
                SourceOrderDetail(ProductID=2, UnitPrice=Decimal("5"), Quantity=1),
            ],
        )
        excs = check_duplicate_lines(order)
        self.assertEqual(len(excs), 0)


if __name__ == "__main__":
    unittest.main()
