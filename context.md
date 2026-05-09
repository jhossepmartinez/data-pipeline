Researching this project and being most confident with typescript i tought i would go with ts. But after talking with gemini and doing some research of the industry standard for handling data pipelines i went with SQLAlchemy and Alembic as the data stack, i could also have gone with DJango for a single framework pipeline but i think this allows for a more robust and system ownership approach, where as Django would abstract much of our implementation.

I scanned the db data and saw many tables, but the most important and what the task is focused on are the tables "Orders" and "Order Details"

Basicamente copio la info que pillo con dbeaver de ambas tablas:

Orders:
Column Name	#	Data Type	Length	Not Null	Auto Increment	Default	Description
OrderID	1	INTEGER	[NULL]	true	true	[NULL]	[NULL]
CustomerID	2	TEXT	[NULL]	false	false	[NULL]	[NULL]
EmployeeID	3	INTEGER	[NULL]	false	false	[NULL]	[NULL]
OrderDate	4	DATETIME	[NULL]	false	false	[NULL]	[NULL]
RequiredDate	5	DATETIME	[NULL]	false	false	[NULL]	[NULL]
ShippedDate	6	DATETIME	[NULL]	false	false	[NULL]	[NULL]
ShipVia	7	INTEGER	[NULL]	false	false	[NULL]	[NULL]
Freight	8	NUMERIC	[NULL]	false	false	0	[NULL]
ShipName	9	TEXT	[NULL]	false	false	[NULL]	[NULL]
ShipAddress	10	TEXT	[NULL]	false	false	[NULL]	[NULL]
ShipCity	11	TEXT	[NULL]	false	false	[NULL]	[NULL]
ShipRegion	12	TEXT	[NULL]	false	false	[NULL]	[NULL]
ShipPostalCode	13	TEXT	[NULL]	false	false	[NULL]	[NULL]
ShipCountry	14	TEXT	[NULL]	false	false	[NULL]	[NULL]

Order Details:
Column Name	#	Data Type	Length	Not Null	Auto Increment	Default	Description
OrderID	1	INTEGER	[NULL]	true	false	[NULL]	[NULL]
ProductID	2	INTEGER	[NULL]	true	false	[NULL]	[NULL]
UnitPrice	3	NUMERIC	[NULL]	true	false	0	[NULL]
Quantity	4	INTEGER	[NULL]	true	false	1	[NULL]
Discount	5	REAL	[NULL]	true	false	0	[NULL]

Products:
Column Name	#	Data Type	Length	Not Null	Auto Increment	Default	Description
ProductID	1	INTEGER	[NULL]	true	true	[NULL]	[NULL]
ProductName	2	TEXT	[NULL]	true	false	[NULL]	[NULL]
SupplierID	3	INTEGER	[NULL]	false	false	[NULL]	[NULL]
CategoryID	4	INTEGER	[NULL]	false	false	[NULL]	[NULL]
QuantityPerUnit	5	TEXT	[NULL]	false	false	[NULL]	[NULL]
UnitPrice	6	NUMERIC	[NULL]	false	false	0	[NULL]
UnitsInStock	7	INTEGER	[NULL]	false	false	0	[NULL]
UnitsOnOrder	8	INTEGER	[NULL]	false	false	0	[NULL]
ReorderLevel	9	INTEGER	[NULL]	false	false	0	[NULL]
Discontinued	10	TEXT	[NULL]	true	false	'0'	[NULL]


se las paso a gpt
