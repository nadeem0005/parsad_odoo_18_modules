{
    'name': 'Inoviq Branch Access (Single Warehouse Users)',
    'version': '18.0.1.3.0',
    'summary': 'Restrict a user to one or more warehouses: stock, transfers and sales',
    'description': """
Inoviq Branch Access
====================
Adds a "Branch User" access group and a "Warehouses" field on the user.

A user who is a Branch User can only:

* see the stock (quants, moves, moves history) of his own warehouse(s)
* create transfers (operation types) of his own warehouse(s); the destination can be any location
* see incoming transfers addressed to his warehouse
* create / see sales orders of his own warehouse(s)
* see Inventory > Reporting for his own warehouse(s)

Menus hidden for Branch Users: Receipts, Deliveries, Internal, Physical Inventory,
Overview, Inventory > Products, Sales > Products, Sales > To Invoice.
Inventory adjustments (counting / applying) are blocked for Branch Users.

No Purchase, Invoicing, Settings or Apps access is granted.
    """,
    'author': 'Inoviq Systems',
    'company': 'Inoviq Systems',
    'maintainer': 'Inoviq Systems',
    'category': 'Inventory/Inventory',
    'depends': ['stock', 'sale_stock'],
    'data': [
        'security/security.xml',
        'views/res_users_views.xml',
        'views/stock_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
