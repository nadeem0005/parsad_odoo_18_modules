{
    'name': 'Warehouse Transfer Orders',
    'version': '18.0.3.1.0',
    'category': 'Inventory/Inventory',
    'summary': 'Create, ship and receive stock between warehouses from one document, with permission levels',
    'description': """
Warehouse Transfer Orders
=========================
One document to move products from one warehouse to another.

Permission levels (independent roles)
-------------------------------------
* Creator  - sender side: creates, edits, confirms and cancels orders that
             start from his warehouses. Cannot ship or receive.
* Shipper  - only ships orders that start from his warehouses.
* Receiver - only receives orders that arrive at his warehouses; the received
             quantity is always what was shipped.
* Manager  - everything, on every warehouse.

Each user is given the warehouses he works with in his user form.

Flow
----
Draft -> Confirmed -> (Ship) In Transit -> (Receive) Done.
Behind the scenes the order drives two linked pickings through the
company transit location. Users never have to open the Transfers screen:
the linked pickings are locked and can only be processed from the order.
The received quantity always equals the shipped quantity, so nothing is left in transit.
""",
    'author': 'inoviqsystems',
    'license': 'LGPL-3',
    'depends': ['stock', 'mail'],
    'data': [
        'security/wh_transfer_order_groups.xml',
        'security/ir.model.access.csv',
        'security/wh_transfer_order_security.xml',
        'data/ir_sequence_data.xml',
        'views/wh_transfer_order_views.xml',
        'views/stock_picking_views.xml',
        'views/res_users_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
}
