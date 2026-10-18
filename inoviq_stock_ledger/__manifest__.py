{
    'name': 'Stock Ledger - Opening & Closing on Moves History',
    'version': '18.0.1.0.0',
    'summary': 'Opening, In, Out and Closing quantity on every line of Moves History',
    'description': """
Stock Ledger - Opening & Closing on Moves History
=================================================
Adds a running balance to Inventory > Reporting > Moves History
(and the Moves History opened from the product form):

* Warehouse
* Opening Qty  (balance before the move)
* In           (quantity received into the warehouse)
* Out          (quantity issued from the warehouse)
* Closing Qty  (balance after the move)

The balance is calculated per product and per warehouse, in date order.
    """,
    'author': 'Inoviq Systems',
    'company': 'Inoviq Systems',
    'maintainer': 'Inoviq Systems',
    'category': 'Inventory/Inventory',
    'depends': ['stock'],
    'data': [
        'views/stock_move_line_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
