{
    'name': 'Sales: Assigned Warehouse, Payment Status & Salesperson Lock',
    'version': '18.0.1.2.0',
    'category': 'Sales/Sales',
    'summary': 'Default sale warehouse from the user assignment, paid / pending amounts on orders, '
               'payment report and salesperson restriction',
    'description': """
Sales: Assigned Warehouse, Payment Status & Salesperson Lock
============================================================
* Sale orders take the warehouse assigned to the salesperson (or to the logged-in
  user while no salesperson is set), taken from the Warehouse Transfers tab of the
  user, instead of the company default. With a single assigned warehouse the field is
  fixed; with several, the first is the default and only the assigned ones can be
  selected. Without assignment the standard behaviour applies.
* The Orders list and the order form show Paid, Pending and a Payment Status
  (Not Paid / Partially Paid / Fully Paid), computed from the customer invoices
  and their registered payments, so partial payments are visible at a glance.
* Sales > Reporting > Payment Status: pivot, graph and list analysis.
* Salespeople who are not administrators:
    - cannot change the Salesperson of an order (always themselves);
    - only see their own orders.
""",
    'author': 'Your Company',
    'license': 'LGPL-3',
    'depends': ['sale_stock', 'account', 'wh_transfer_order'],
    'data': [
        'security/sale_security.xml',
        'views/sale_order_views.xml',
        'views/payment_report_views.xml',
    ],
    'installable': True,
    'application': False,
}
