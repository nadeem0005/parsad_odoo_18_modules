# -*- coding: utf-8 -*-
{
    'name': 'Inovqi Contact & Order Control',
    'version': '18.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Contact business roles, role-filtered partner selection and '
               'server-enforced price protection on Sales and Purchase orders.',
    'description': """
Inovqi Contact & Order Control
==============================
* Business Roles (Vendor / Customer / Employee) on contacts.
* Only vendors can be selected on Purchase Orders, only customers on Sales Orders.
* Unit price (and discount) on order lines can only be overridden by members of
  the "Inovqi Order Price Manager" group - enforced on the server (ORM), not only in the UI.
* Audit log of every blocked attempt.
""",
    'author': 'InovqiSystems',
    'website': 'https://www.inovqi.com',
    'license': 'LGPL-3',
    'depends': ['base', 'contacts', 'sale_management', 'purchase'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
        'views/purchase_order_views.xml',
        'views/price_violation_log_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
