# -*- coding: utf-8 -*-
# Part of Inoviq Systems. See LICENSE file for full copyright and licensing details.

from odoo import api, models

BRANCH_GROUP = 'inoviq_branch_access.group_branch_user'

# Menus hidden for Branch Users (module.xmlid). Children are hidden with their parent.
BRANCH_HIDDEN_MENUS = [
    # Inventory > Operations
    'stock.in_picking',                 # Receipts
    'stock.out_picking',                # Deliveries
    'stock.int_picking',                # Internal
    'stock.menu_action_inventory_tree', # Physical Inventory (Adjustments)
    # Inventory > Overview (operation type cards lead to Receipts/Deliveries/Internal)
    'stock.stock_picking_type_menu',
    # Inventory > Products (products, variants, lots, packages)
    'stock.menu_stock_inventory_control',
    # Sales > Products and Sales > To Invoice
    'sale.product_menu_catalog',
    'sale.menu_sale_invoicing',
]

# Menus a Branch User must see although Odoo restricts them to Inventory Managers
BRANCH_SHOWN_MENUS = [
    'stock.menu_warehouse_report',      # Inventory > Reporting
]


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    def _inoviq_menu_ids(self, xmlids):
        ids = []
        for xmlid in xmlids:
            menu = self.env.ref(xmlid, raise_if_not_found=False)
            if menu and menu._name == 'ir.ui.menu':
                ids.append(menu.id)
        return ids

    def _visible_menu_ids(self, debug=False):
        visible = super()._visible_menu_ids(debug)
        user = self.env.user
        if not user.has_group(BRANCH_GROUP):
            return visible
        visible = set(visible)  # never modify the cached set of the parent method
        Menu = self.sudo().with_context({'ir.ui.menu.full_list': True})
        # show Reporting (restricted to managers by default)
        visible.update(Menu._inoviq_menu_ids(BRANCH_SHOWN_MENUS))
        # hide the unwanted menus and everything below them
        hidden_roots = Menu._inoviq_menu_ids(BRANCH_HIDDEN_MENUS)
        if hidden_roots:
            hidden = Menu.search([('id', 'child_of', hidden_roots)]).ids
            visible.difference_update(hidden)
        return visible
