# -*- coding: utf-8 -*-
from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import Form, tagged

from .common import InovqiCommon


@tagged('post_install', '-at_install')
class TestPurchasePriceProtection(InovqiCommon):

    def test_automatic_vendor_pricing_works_for_normal_user(self):
        po = self._new_po(self.user_normal)
        self.assertEqual(po.order_line.price_unit, 40.0)

    def test_normal_user_cannot_change_unit_price(self):
        po = self._new_po(self.user_normal)
        with self.assertRaises(AccessError):
            po.order_line.write({'price_unit': 1.0})
        self.assertEqual(po.order_line.price_unit, 40.0)

    def test_normal_user_cannot_create_line_with_custom_price(self):
        po = self._new_po(self.user_normal)
        with self.assertRaises(AccessError):
            self.env(user=self.user_normal)['purchase.order.line'].create({
                'order_id': po.id, 'product_id': self.product.id,
                'product_qty': 1.0, 'price_unit': 0.01})

    def test_normal_user_cannot_change_discount(self):
        po = self._new_po(self.user_normal)
        if 'discount' not in po.order_line._fields:
            self.skipTest("No discount field on purchase lines in this build")
        with self.assertRaises(AccessError):
            po.order_line.write({'discount': 20.0})

    def test_price_manager_can_change_unit_price(self):
        po = self._new_po(self.user_price_manager)
        po.order_line.write({'price_unit': 33.0})
        self.assertEqual(po.order_line.price_unit, 33.0)

    def test_sales_price_manager_is_not_a_purchase_price_manager(self):
        sale_only = self.user_normal.copy({
            'login': 'inovqi_sale_only', 'name': 'Sale only',
            'groups_id': [Command.link(
                self.env.ref('inovqi_contact_order_control.group_sale_price_manager').id)]})
        po = self._new_po(sale_only)
        with self.assertRaises(AccessError):
            po.order_line.write({'price_unit': 1.0})

    def test_quantity_change_recomputes_price_without_error(self):
        po = self._new_po(self.user_normal)
        po.order_line.write({'product_qty': 10.0})
        self.assertEqual(po.order_line.product_qty, 10.0)
        self.assertEqual(po.order_line.price_unit, 40.0)

    def test_form_flow_for_normal_user(self):
        form = Form(self.env['purchase.order'].with_user(self.user_normal))
        form.partner_id = self.both
        with form.order_line.new() as line:
            line.product_id = self.product
            line.product_qty = 2.0
            with self.assertRaises(AssertionError):
                line.price_unit = 1.0
        po = form.save()
        self.assertEqual(po.order_line.price_unit, 40.0)
