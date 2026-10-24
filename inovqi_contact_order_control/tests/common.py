# -*- coding: utf-8 -*-
from odoo import Command
from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools.safe_eval import safe_eval

NORMAL_GROUPS = ('base.group_user,sales_team.group_sale_salesman,'
                 'purchase.group_purchase_user,base.group_partner_manager')


@tagged('post_install', '-at_install')
class InovqiCommon(TransactionCase):
    """Shared fixtures. NB: ``self.env`` is the superuser; real permission checks
    always go through ``with_user`` / ``self.env(user=...)``."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        Partner = cls.env['res.partner']
        cls.vendor_only = Partner.create({'name': 'Inovqi Vendor Only', 'is_vendor': True})
        cls.customer_only = Partner.create({'name': 'Inovqi Customer Only', 'is_customer': True})
        cls.both = Partner.create({'name': 'Inovqi Both', 'is_vendor': True, 'is_customer': True})
        cls.neither = Partner.create({'name': 'Inovqi Neither'})

        cls.sale_tax = cls.env['account.tax'].create({
            'name': 'Inovqi Sale 10%', 'amount': 10.0, 'amount_type': 'percent',
            'type_tax_use': 'sale', 'company_id': company.id})
        cls.purchase_tax = cls.env['account.tax'].create({
            'name': 'Inovqi Purchase 10%', 'amount': 10.0, 'amount_type': 'percent',
            'type_tax_use': 'purchase', 'company_id': company.id})
        template = cls.env['product.template'].create({
            'name': 'Inovqi Product', 'type': 'consu',
            'list_price': 100.0, 'standard_price': 60.0,
            'taxes_id': [Command.set(cls.sale_tax.ids)],
            'supplier_taxes_id': [Command.set(cls.purchase_tax.ids)],
            'seller_ids': [Command.create({
                'partner_id': cls.both.id, 'min_qty': 1.0, 'price': 40.0})],
        })
        cls.product = template.product_variant_id

        cls.user_normal = mail_new_test_user(
            cls.env, login='inovqi_normal', groups=NORMAL_GROUPS)
        cls.user_price_manager = mail_new_test_user(
            cls.env, login='inovqi_price_mgr',
            groups=NORMAL_GROUPS + ',inovqi_contact_order_control.group_order_price_manager')
        cls.user_role_manager = mail_new_test_user(
            cls.env, login='inovqi_role_mgr',
            groups=NORMAL_GROUPS + ',inovqi_contact_order_control.group_contact_role_manager')

    # -- helpers ---------------------------------------------------------
    def _env_for(self, user=None):
        return self.env(user=user) if user else self.env

    def _new_so(self, user=None, partner=None, qty=2.0, **extra):
        vals = {
            'partner_id': (partner or self.both).id,
            'order_line': [Command.create({
                'product_id': self.product.id, 'product_uom_qty': qty})],
        }
        vals.update(extra)
        return self._env_for(user)['sale.order'].create(vals)

    def _new_po(self, user=None, partner=None, qty=3.0, **extra):
        vals = {
            'partner_id': (partner or self.both).id,
            'order_line': [Command.create({
                'product_id': self.product.id, 'product_qty': qty})],
        }
        vals.update(extra)
        return self._env_for(user)['purchase.order'].create(vals)

    def _selectable(self, model, partners):
        """Partners from ``partners`` that the model's partner_id domain lets through."""
        domain = self.env[model]._fields['partner_id'].domain
        if isinstance(domain, str):
            domain = safe_eval(domain, {'company_id': self.env.company.id})
        return self.env['res.partner'].search(list(domain) + [('id', 'in', partners.ids)])
