import unittest
from decimal import Decimal
from datetime import datetime

from src.models.source import SourceOrder, SourceOrderDetail
from src.pipeline.assign_currency import assign_currency


class TestAssignCurrency(unittest.TestCase):
    def test_default_is_usd(self):
        source = SourceOrder(
            OrderID=1,
            CustomerID="A",
            OrderDate=datetime(2023, 1, 1),
            Freight=Decimal("0"),
            details=[],
        )
        self.assertEqual(assign_currency(source), "USD")

    def test_mock_injection_eur(self):
        source = SourceOrder(
            OrderID=2,
            CustomerID="B",
            OrderDate=datetime(2023, 1, 1),
            Freight=Decimal("0"),
            details=[],
        )
        source._mock_currency = "EUR"
        self.assertEqual(assign_currency(source), "EUR")


if __name__ == "__main__":
    unittest.main()
