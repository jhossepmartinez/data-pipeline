from datetime import datetime
from decimal import Decimal

from src.models.source import SourceOrder, SourceOrderDetail

DEMO_SOURCE_IDS = [900001, 900002, 900003, 900004, 900005]

DEMO_SOURCE_ORDERS = [
    {
        "OrderID": 900001,
        "CustomerID": "DEMO-R7",
        "OrderDate": datetime(2023, 1, 1),
        "Freight": Decimal("0"),
        "details": [
            {
                "ProductID": 1,
                "UnitPrice": Decimal("100.00"),
                "Quantity": 1,
                "Discount": Decimal("0"),
            },
        ],
    },
    {
        "OrderID": 900002,
        "CustomerID": "DEMO-R5",
        "OrderDate": datetime(2023, 1, 1),
        "Freight": Decimal("0"),
        "details": [
            {
                "ProductID": 2,
                "UnitPrice": Decimal("100.00"),
                "Quantity": 1,
                "Discount": Decimal("0.10"),
            },
        ],
    },
    {
        "OrderID": 900003,
        "CustomerID": "DEMO-R2",
        "OrderDate": datetime(2023, 1, 1),
        "Freight": Decimal("0"),
        "details": [
            {
                "ProductID": 3,
                "UnitPrice": Decimal("100.00"),
                "Quantity": 1,
                "Discount": Decimal("0"),
            },
        ],
    },
    {
        "OrderID": 900004,
        "CustomerID": "DEMO-R1",
        "OrderDate": datetime(2023, 1, 1),
        "Freight": Decimal("10.00"),
        "details": [
            {
                "ProductID": 4,
                "UnitPrice": Decimal("100.00"),
                "Quantity": 1,
                "Discount": Decimal("0"),
            },
        ],
    },
    {
        "OrderID": 900005,
        "CustomerID": "DEMO-R3",
        "OrderDate": None,
        "Freight": Decimal("0"),
        "details": [
            {
                "ProductID": 5,
                "UnitPrice": Decimal("10.00"),
                "Quantity": 1,
                "Discount": Decimal("0"),
            },
        ],
    },
]


def build_demo_source_orders() -> list[SourceOrder]:
    """
    Construye ordenes de demostracion invalidas en memoria.

    Returns:
        List[SourceOrder] lista de objetos listos para pasar al pipeline.
    """
    orders = []
    for spec in DEMO_SOURCE_ORDERS:
        order = SourceOrder(
            OrderID=spec["OrderID"],
            CustomerID=spec["CustomerID"],
            OrderDate=spec["OrderDate"],
            Freight=spec["Freight"],
        )
        order.details = [
            SourceOrderDetail(
                ProductID=d["ProductID"],
                UnitPrice=d["UnitPrice"],
                Quantity=d["Quantity"],
                Discount=d["Discount"],
            )
            for d in spec["details"]
        ]
        orders.append(order)
    return orders
