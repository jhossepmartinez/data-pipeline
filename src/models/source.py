from sqlalchemy import Column, Integer, String, DateTime, Numeric, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

BaseSource = declarative_base()


class SourceOrder(BaseSource):
    __tablename__ = "Orders"

    OrderID = Column(Integer, primary_key=True, autoincrement=True)
    CustomerID = Column(String)
    EmployeeID = Column(Integer)
    OrderDate = Column(DateTime)
    RequiredDate = Column(DateTime)
    ShippedDate = Column(DateTime)
    ShipVia = Column(Integer)
    Freight = Column(Numeric(10, 2), default=0)
    ShipName = Column(String)
    ShipAddress = Column(String)
    ShipCity = Column(String)
    ShipRegion = Column(String)
    ShipPostalCode = Column(String)
    ShipCountry = Column(String)

    details = relationship("SourceOrderDetail", back_populates="order")


class SourceOrderDetail(BaseSource):
    __tablename__ = "Order Details"

    OrderID = Column(Integer, ForeignKey("Orders.OrderID"), primary_key=True)
    ProductID = Column(Integer, primary_key=True)
    UnitPrice = Column(Numeric(10, 2), nullable=False, default=0)
    Quantity = Column(Integer, nullable=False, default=1)
    Discount = Column(Numeric(5, 4), nullable=False, default=0)

    order = relationship("SourceOrder", back_populates="details")
