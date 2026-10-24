# -*- coding: utf-8 -*-
from odoo import Command
from odoo.tests import Form, tagged

from .common import InovqiCommon


@tagged('post_install', '-at_install')
class TestRegression(InovqiCommon):

    # -- Sales -----------------------------------------------------------
    def test_quotation_create_and_confirm(self):
        so = self._new_so(self.user_normal, qty=2.0)
        self.assertEqual(so.state, 'draft')
        so.action_confirm()
        self.assertEqual(so.state, 'sale')

    def test_sale_taxes_and_totals(self):
        so = self._new_so(self.user_normal, qty=2.0)
        self.assertAlmostEqual(so.amount_untaxed, 200.0)
        self.assertAlmostEqual(so.amount_tax, 20.0)
        self.assertAlmostEqual(so.amount_total, 220.0)

    def test_sale_lines_can_be_added_and_quantities_changed(self):
        so = self._new_so(self.user_normal, qty=1.0)
        so.write({'order_line': [Command.create({
            'product_id': self.product.id, 'product_uom_qty': 4.0})]})
        self.assertEqual(len(so.order_line), 2)
        so.order_line[0].write({'product_uom_qty': 5.0})
        self.assertAlmostEqual(so.amount_untaxed, 900.0)
        self.assertEqual(set(so.order_line.mapped('price_unit')), {100.0})

    def test_sale_line_can_be_removed(self):
        so = self._new_so(self.user_normal, qty=1.0)
        so.write({'order_line': [Command.create({
            'product_id': self.product.id, 'product_uom_qty': 1.0})]})
        so.write({'order_line': [Command.delete(so.order_line[1].id)]})
        self.assertEqual(len(so.order_line), 1)

    def test_sale_invoice_and_delivery(self):
        so = self._new_so(self.user_normal, qty=2.0)
        so.action_confirm()
        if 'stock.picking' in self.env:
            self.assertTrue(so.picking_ids, "A delivery order should be created")
        journal = self.env['account.journal'].search(
            [('type', '=', 'sale'), ('company_id', '=', self.env.company.id)], limit=1)
        if not journal:
            self.skipTest("No accounting chart installed: invoice step skipped")
        invoice = so._create_invoices()
        self.assertAlmostEqual(invoice.amount_total, 220.0)

    def test_manager_override_flows_to_totals(self):
        so = self._new_so(self.user_price_manager, qty=2.0)
        so.order_line.write({'price_unit': 50.0})
        self.assertAlmostEqual(so.amount_total, 110.0)
        so.action_confirm()
        self.assertEqual(so.state, 'sale')

    # -- Purchases -------------------------------------------------------
    def test_purchase_create_and_confirm(self):
        po = self._new_po(self.user_normal, qty=3.0)
        po.button_confirm()
        self.assertEqual(po.state, 'purchase')
        if 'stock.picking' in self.env and 'picking_ids' in po._fields:
            self.assertTrue(po.picking_ids, "A receipt should be created")

    def test_purchase_taxes_and_totals(self):
        po = self._new_po(self.user_normal, qty=3.0)
        self.assertAlmostEqual(po.amount_untaxed, 120.0)
        self.assertAlmostEqual(po.amount_tax, 12.0)
        self.assertAlmostEqual(po.amount_total, 132.0)

    def test_purchase_lines_can_be_added_and_quantities_changed(self):
        po = self._new_po(self.user_normal, qty=1.0)
        po.write({'order_line': [Command.create({
            'product_id': self.product.id, 'product_qty': 2.0})]})
        self.assertEqual(len(po.order_line), 2)
        po.order_line[0].write({'product_qty': 4.0})
        self.assertAlmostEqual(po.amount_untaxed, 240.0)

    def test_purchase_duplicate_by_normal_user(self):
        po = self._new_po(self.user_normal)
        po.order_line.with_user(self.user_price_manager).write({'price_unit': 10.0})
        copy = po.with_user(self.user_normal).copy()
        self.assertEqual(copy.order_line.price_unit, 40.0)
