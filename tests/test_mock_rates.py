import unittest
from decimal import Decimal

from src.exchange.mock_rates import get_rate


class TestMockRates(unittest.TestCase):
    def test_usd_rate_is_one(self):
        self.assertEqual(get_rate("USD"), Decimal("1.0"))

    def test_eur_rate_is_expected(self):
        self.assertEqual(get_rate("EUR"), Decimal("1.10"))

    def test_gbp_rate_is_expected(self):
        self.assertEqual(get_rate("GBP"), Decimal("1.30"))

    def test_unsupported_currency_raises(self):
        with self.assertRaises(ValueError):
            get_rate("JPY")

    def test_case_insensitive(self):
        self.assertEqual(get_rate("eur"), Decimal("1.10"))
        self.assertEqual(get_rate("Gbp"), Decimal("1.30"))


if __name__ == "__main__":
    unittest.main()
