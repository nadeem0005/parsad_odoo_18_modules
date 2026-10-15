{
    'name': 'Sales Quick Flow: Confirm, Deliver, Invoice & Pay',
    'version': '18.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'One-click Sales Order flow: confirm, validate delivery (negative stock allowed), '
               'invoice, and register payment through a validated wizard.',
    'depends': ['sale_stock', 'stock_account', 'account'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'wizard/sale_quick_payment_wizard_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
