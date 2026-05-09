import unittest
from decimal import Decimal
from datetime import datetime

from src.models.source import SourceOrder, SourceOrderDetail
from src.models.canonical import Order, OrderLine, ValidationException
from src.pipeline.assign_currency import assign_currency
from src.pipeline.normalize import normalize
from src.pipeline.validate_currency import validate_currency_conversion


class TestValidateCurrency(unittest.TestCase):
    def test_usd_base_equals_total(self):
        source = SourceOrder(
            OrderID=1,
            CustomerID="A",
            OrderDate=datetime(2023, 1, 1),
            Freight=Decimal("10"),
            details=[
                SourceOrderDetail(
                    ProductID=1,
                    UnitPrice=Decimal("10"),
                    Quantity=1,
                    Discount=Decimal("0"),
                )
            ],
        )
        order = normalize(source, currency="USD")
        self.assertEqual(order.total_amount_base, order.total_amount)
        excs = validate_currency_conversion(order)
        self.assertEqual(len(excs), 0)

    def test_eur_conversion_passes(self):
        source = SourceOrder(
            OrderID=2,
            CustomerID="B",
            OrderDate=datetime(2023, 1, 1),
            Freight=Decimal("0"),
            details=[
                SourceOrderDetail(
                    ProductID=1,
                    UnitPrice=Decimal("100"),
                    Quantity=1,
                    Discount=Decimal("0"),
                )
            ],
        )
        order = normalize(source, currency="EUR")
        # 100 * 1.10 = 110.00
        self.assertEqual(order.total_amount_base, Decimal("110.00"))
        excs = validate_currency_conversion(order)
        self.assertEqual(len(excs), 0)

    def test_mismatch_detected(self):
        order = Order(
            source_order_id=3,
            original_currency="EUR",
            exchange_rate=Decimal("1.10"),
            total_amount=Decimal("100.00"),
            total_amount_base=Decimal("999.00"),  # Obviamente mal
            freight=Decimal("0"),
            lines=[
                OrderLine(
                    product_id=1, unit_price=100, quantity=1, discount=0, line_total=100
                )
            ],
        )
        excs = validate_currency_conversion(order)
        self.assertEqual(len(excs), 1)
        self.assertEqual(excs[0].rule_name, "CURRENCY_CONVERSION_MISMATCH")

    def test_epsilon_tolerance(self):
        order = Order(
            source_order_id=4,
            original_currency="EUR",
            exchange_rate=Decimal("1.10"),
            total_amount=Decimal("100.00"),
            total_amount_base=Decimal("110.005"),  # Diferencia menor a 0.01
            freight=Decimal("0"),
            lines=[
                OrderLine(
                    product_id=1, unit_price=100, quantity=1, discount=0, line_total=100
                )
            ],
        )
        excs = validate_currency_conversion(order)
        self.assertEqual(len(excs), 0)

    def test_pipeline_usd_order_valid(self):
        """Flujo completo: assign -> normalize -> validate pasa para USD."""
        source = SourceOrder(
            OrderID=10,
            CustomerID="X",
            OrderDate=datetime(2023, 1, 1),
            Freight=Decimal("5"),
            details=[
                SourceOrderDetail(
                    ProductID=1,
                    UnitPrice=Decimal("20"),
                    Quantity=2,
                    Discount=Decimal("0"),
                )
            ],
        )
        currency = assign_currency(source)
        order = normalize(source, currency=currency)
        excs = validate_currency_conversion(order)
        self.assertEqual(len(excs), 0)
        self.assertEqual(order.original_currency, "USD")
        self.assertEqual(order.total_amount_base, order.total_amount)

    def test_pipeline_eur_order_valid(self):
        """Flujo completo: assign -> normalize -> validate pasa para EUR."""
        source = SourceOrder(
            OrderID=11,
            CustomerID="Y",
            OrderDate=datetime(2023, 1, 1),
            Freight=Decimal("0"),
            details=[
                SourceOrderDetail(
                    ProductID=2,
                    UnitPrice=Decimal("50"),
                    Quantity=1,
                    Discount=Decimal("0"),
                )
            ],
        )
        source._mock_currency = "EUR"
        currency = assign_currency(source)
        order = normalize(source, currency=currency)
        excs = validate_currency_conversion(order)
        self.assertEqual(len(excs), 0)
        self.assertEqual(order.original_currency, "EUR")
        self.assertEqual(order.total_amount_base, Decimal("55.00"))  # 50 * 1.10

    def test_pipeline_gbp_order_valid(self):
        """Flujo completo: assign -> normalize -> validate pasa para GBP."""
        source = SourceOrder(
            OrderID=12,
            CustomerID="Z",
            OrderDate=datetime(2023, 1, 1),
            Freight=Decimal("0"),
            details=[
                SourceOrderDetail(
                    ProductID=3,
                    UnitPrice=Decimal("100"),
                    Quantity=1,
                    Discount=Decimal("0"),
                )
            ],
        )
        source._mock_currency = "GBP"
        currency = assign_currency(source)
        order = normalize(source, currency=currency)
        excs = validate_currency_conversion(order)
        self.assertEqual(len(excs), 0)
        self.assertEqual(order.original_currency, "GBP")
        self.assertEqual(order.total_amount_base, Decimal("130.00"))  # 100 * 1.30

    def test_pipeline_mismatch_invalidates_order(self):
        """Simula la pipeline: una orden con datos corruptos se invalida por R7."""
        source = SourceOrder(
            OrderID=13,
            CustomerID="W",
            OrderDate=datetime(2023, 1, 1),
            Freight=Decimal("0"),
            details=[
                SourceOrderDetail(
                    ProductID=1,
                    UnitPrice=Decimal("100"),
                    Quantity=1,
                    Discount=Decimal("0"),
                )
            ],
        )
        source._mock_currency = "EUR"
        currency = assign_currency(source)
        order = normalize(source, currency=currency)

        # Simular corrupcion manual (ej. bug de redondeo o data race)
        order.total_amount_base = Decimal("999.00")

        excs = validate_currency_conversion(order)
        self.assertEqual(len(excs), 1)
        self.assertEqual(excs[0].rule_name, "CURRENCY_CONVERSION_MISMATCH")

        # En main.py esto marcaria la orden como invalida
        if excs:
            order.status = "invalid"
            order.exceptions = excs
        self.assertEqual(order.status, "invalid")

    def test_pipeline_mixed_orders_counts(self):
        """Simula el loop de main.py con multiples monedas y validaciones."""
        sources = [
            SourceOrder(
                OrderID=20,
                CustomerID="A",
                OrderDate=datetime(2023, 1, 1),
                Freight=Decimal("0"),
                details=[
                    SourceOrderDetail(
                        ProductID=1,
                        UnitPrice=Decimal("10"),
                        Quantity=1,
                        Discount=Decimal("0"),
                    )
                ],
            ),
            SourceOrder(
                OrderID=21,
                CustomerID="B",
                OrderDate=datetime(2023, 1, 1),
                Freight=Decimal("0"),
                details=[
                    SourceOrderDetail(
                        ProductID=1,
                        UnitPrice=Decimal("100"),
                        Quantity=1,
                        Discount=Decimal("0"),
                    )
                ],
            ),
            SourceOrder(
                OrderID=22,
                CustomerID="C",
                OrderDate=datetime(2023, 1, 1),
                Freight=Decimal("0"),
                details=[
                    SourceOrderDetail(
                        ProductID=1,
                        UnitPrice=Decimal("50"),
                        Quantity=1,
                        Discount=Decimal("0"),
                    )
                ],
            ),
        ]
        # Inyectar monedas mixtas
        sources[0]._mock_currency = "USD"
        sources[1]._mock_currency = "EUR"
        sources[2]._mock_currency = "GBP"

        # Corromper la orden GBP para que falle
        sources[2].details[0].UnitPrice = Decimal("50")
        # pero luego corrompemos el resultado esperado manualmente

        valid_count = 0
        invalid_count = 0
        for src in sources:
            currency = assign_currency(src)
            order = normalize(src, currency=currency)

            if order.source_order_id == 22:
                # Corromper a proposito para forzar fallo
                order.total_amount_base = Decimal("1.00")

            excs = validate_currency_conversion(order)
            if excs:
                order.status = "invalid"
                order.exceptions = excs
                invalid_count += 1
            else:
                order.status = "valid"
                valid_count += 1

        self.assertEqual(valid_count, 2)
        self.assertEqual(invalid_count, 1)

        # Verificar totales base correctos para las validas
        # No tenemos acceso directo a 'order' fuera del loop, rehacemos asserts individuales
        usd_order = normalize(sources[0], currency="USD")
        eur_order = normalize(sources[1], currency="EUR")
        self.assertEqual(usd_order.total_amount_base, Decimal("10.00"))
        self.assertEqual(eur_order.total_amount_base, Decimal("110.00"))


if __name__ == "__main__":
    unittest.main()
