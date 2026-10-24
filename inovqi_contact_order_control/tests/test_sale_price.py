# -*- coding: utf-8 -*-
from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import Form, tagged

from .common import InovqiCommon


@tagged('post_install', '-at_install')
class TestSalePriceProtection(InovqiCommon):

    def test_normal_user_cannot_change_unit_price(self):
        so = self._new_so(self.user_normal)
        line = so.order_line
        self.assertEqual(line.price_unit, 100.0)
        with self.assertRaises(AccessError):
            line.write({'price_unit': 1.0})
        self.assertEqual(line.price_unit, 100.0)

    def test_normal_user_cannot_create_line_with_custom_price(self):
        so = self._new_so(self.user_normal)
        with self.assertRaises(AccessError):
            self.env(user=self.user_normal)['sale.order.line'].create({
                'order_id': so.id, 'product_id': self.product.id,
                'product_uom_qty': 1.0, 'price_unit': 0.01})

    def test_normal_user_cannot_change_discount(self):
        so = self._new_so(self.user_normal)
        with self.assertRaises(AccessError):
            so.order_line.write({'discount': 50.0})

    def test_normal_user_cannot_change_pricelist(self):
        so = self._new_so(self.user_normal)
        other = self.env['product.pricelist'].create({'name': 'Cheap'})
        with self.assertRaises(AccessError):
            so.write({'pricelist_id': other.id})

    def test_price_manager_can_change_price_discount_and_pricelist(self):
        so = self._new_so(self.user_price_manager)
        so.order_line.write({'price_unit': 55.0, 'discount': 10.0})
        self.assertEqual(so.order_line.price_unit, 55.0)
        self.assertEqual(so.order_line.discount, 10.0)
        other = self.env['product.pricelist'].create({'name': 'Special'})
        so.write({'pricelist_id': other.id})
        self.assertEqual(so.pricelist_id, other)

    def test_import_cannot_bypass_protection(self):
        so = self._new_so(self.user_normal)
        result = self.env(user=self.user_normal)['sale.order.line'].load(
            ['order_id/.id', 'product_id/.id', 'product_uom_qty', 'price_unit'],
            [[str(so.id), str(self.product.id), '1', '0.5']])
        self.assertFalse(result.get('ids'))
        self.assertTrue(result.get('messages'))

    def test_pricelist_computation_still_works(self):
        pricelist = self.env['product.pricelist'].create({
            'name': 'Inovqi Fixed',
            'item_ids': [Command.create({
                'applied_on': '0_product_variant', 'product_id': self.product.id,
                'compute_price': 'fixed', 'fixed_price': 80.0})],
        })
        so = self._new_so(pricelist_id=pricelist.id)          # created by superuser
        so_user = so.with_user(self.user_normal)
        so_user.write({'order_line': [Command.create({
            'product_id': self.product.id, 'product_uom_qty': 1.0})]})
        self.assertEqual(set(so.order_line.mapped('price_unit')), {80.0})

    def test_duplicate_does_not_copy_manual_override(self):
        so = self._new_so(self.user_normal)
        so.order_line.with_user(self.user_price_manager).write({'price_unit': 50.0})
        self.assertEqual(so.order_line.price_unit, 50.0)
        copy = so.copy()
        self.assertEqual(copy.order_line.price_unit, 100.0)
        copy_by_user = so.with_user(self.user_normal).copy()
        self.assertEqual(copy_by_user.order_line.price_unit, 100.0)

    def test_form_flow_for_normal_user(self):
        form = Form(self.env['sale.order'].with_user(self.user_normal))
        form.partner_id = self.customer_only
        with form.order_line.new() as line:
            line.product_id = self.product
            line.product_uom_qty = 3.0
            with self.assertRaises(AssertionError):    # read-only in the UI
                line.price_unit = 1.0
        so = form.save()
        self.assertEqual(so.order_line.price_unit, 100.0)
        self.assertEqual(so.order_line.product_uom_qty, 3.0)

    def test_form_flow_for_price_manager(self):
        form = Form(self.env['sale.order'].with_user(self.user_price_manager))
        form.partner_id = self.customer_only
        with form.order_line.new() as line:
            line.product_id = self.product
            line.price_unit = 77.0
        so = form.save()
        self.assertEqual(so.order_line.price_unit, 77.0)
