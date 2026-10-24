# -*- coding: utf-8 -*-
from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged

from .common import InovqiCommon


@tagged('post_install', '-at_install')
class TestContactRoles(InovqiCommon):

    def _all(self):
        return self.vendor_only | self.customer_only | self.both | self.neither

    def test_roles_are_independent_and_default_false(self):
        self.assertTrue(self.vendor_only.is_vendor and not self.vendor_only.is_customer)
        self.assertTrue(self.customer_only.is_customer and not self.customer_only.is_vendor)
        self.assertFalse(self.neither.is_vendor or self.neither.is_customer or self.neither.is_employee_contact)

    def test_purchase_selection_list(self):
        self.assertEqual(self._selectable('purchase.order', self._all()), self.vendor_only | self.both)

    def test_sale_selection_list(self):
        self.assertEqual(self._selectable('sale.order', self._all()), self.customer_only | self.both)

    def test_child_of_customer_company_is_selectable_via_commercial_entity(self):
        child = self.env['res.partner'].create({
            'name': 'Child Person', 'parent_id': self.customer_only.id, 'type': 'contact'})
        self.assertIn(child, self._selectable('sale.order', child))
        self.assertNotIn(child, self._selectable('purchase.order', child))

    def test_server_side_partner_check_for_normal_user(self):
        with self.assertRaises(ValidationError):
            self._new_so(self.user_normal, partner=self.vendor_only)
        with self.assertRaises(ValidationError):
            self._new_so(self.user_normal, partner=self.neither)
        with self.assertRaises(ValidationError):
            self._new_po(self.user_normal, partner=self.customer_only)
        # allowed
        self.assertTrue(self._new_so(self.user_normal, partner=self.customer_only))
        self.assertTrue(self._new_po(self.user_normal, partner=self.vendor_only))

    def test_changing_partner_is_validated(self):
        so = self._new_so(self.user_normal, partner=self.customer_only)
        with self.assertRaises(ValidationError):
            so.write({'partner_id': self.vendor_only.id})
        so.write({'partner_id': self.both.id})
        self.assertEqual(so.partner_id, self.both)

    def test_existing_orders_not_retroactively_blocked(self):
        so = self._new_so(self.user_normal, partner=self.customer_only)
        self.customer_only.with_user(self.user_role_manager).write({'is_customer': False})
        so.write({'client_order_ref': 'still editable'})  # partner unchanged -> no check
        self.assertEqual(so.client_order_ref, 'still editable')

    def test_system_created_orders_are_exempt(self):
        # superuser env = reordering rules, website, cron, ...
        so = self.env['sale.order'].create({'partner_id': self.neither.id})
        self.assertTrue(so)

    def test_invoice_and_delivery_addresses_still_work(self):
        invoice = self.env['res.partner'].create({
            'name': 'Inv', 'parent_id': self.customer_only.id, 'type': 'invoice'})
        delivery = self.env['res.partner'].create({
            'name': 'Del', 'parent_id': self.customer_only.id, 'type': 'delivery'})
        so = self._new_so(self.user_normal, partner=self.customer_only)
        self.assertEqual(so.partner_invoice_id, invoice)
        self.assertEqual(so.partner_shipping_id, delivery)

    def test_role_editing_is_restricted(self):
        with self.assertRaises(AccessError):
            self.neither.with_user(self.user_normal).write({'is_customer': True})
        with self.assertRaises(AccessError):
            self.env['res.partner'].with_user(self.user_normal).create({'name': 'X', 'is_vendor': True})
        self.neither.with_user(self.user_role_manager).write({'is_employee_contact': True})
        self.assertTrue(self.neither.is_employee_contact)
        # writing the *same* value is not a change
        self.neither.with_user(self.user_normal).write({'is_employee_contact': True})

    def test_role_manager_is_not_a_price_manager(self):
        so = self._new_so(self.user_role_manager)
        with self.assertRaises(AccessError):
            so.order_line.write({'price_unit': 1.0})

    def test_settings_admin_gets_role_but_not_price_rights(self):
        admin_group = self.env.ref('base.group_system')
        role_group = self.env.ref('inovqi_contact_order_control.group_contact_role_manager')
        price_group = self.env.ref('inovqi_contact_order_control.group_order_price_manager')
        self.assertIn(role_group, admin_group.trans_implied_ids)
        self.assertNotIn(price_group, admin_group.trans_implied_ids)

    def test_search_filters(self):
        found = self.env['res.partner'].search([('is_vendor', '=', True), ('id', 'in', self._all().ids)])
        self.assertEqual(found, self.vendor_only | self.both)
