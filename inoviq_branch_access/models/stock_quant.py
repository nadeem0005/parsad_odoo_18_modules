# -*- coding: utf-8 -*-
# Part of Inoviq Systems. See LICENSE file for full copyright and licensing details.

from odoo import api, models
from odoo.exceptions import UserError

BRANCH_GROUP = 'inoviq_branch_access.group_branch_user'


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    def _inoviq_is_branch_user(self):
        return not self.env.su and self.env.user.has_group(BRANCH_GROUP)

    @api.model
    def _is_inventory_mode(self):
        # No "inventory mode" (counted quantity editing) for branch users
        if self._inoviq_is_branch_user():
            return False
        return super()._is_inventory_mode()

    def action_apply_inventory(self):
        if self._inoviq_is_branch_user():
            raise UserError("Inventory adjustments are not allowed for branch users. "
                            "Please contact the head office.")
        return super().action_apply_inventory()

    def _apply_inventory(self):
        if self._inoviq_is_branch_user():
            raise UserError("Inventory adjustments are not allowed for branch users. "
                            "Please contact the head office.")
        return super()._apply_inventory()

    INOVIQ_INVENTORY_FIELDS = ('inventory_quantity', 'inventory_quantity_auto_apply')

    @api.model
    def action_view_inventory(self):
        if self._inoviq_is_branch_user():
            raise UserError("Inventory adjustments are not allowed for branch users. "
                            "Please contact the head office.")
        return super().action_view_inventory()

    @api.model_create_multi
    def create(self, vals_list):
        if self._inoviq_is_branch_user() and any(
                f in vals for vals in vals_list for f in self.INOVIQ_INVENTORY_FIELDS):
            raise UserError("Inventory adjustments are not allowed for branch users.")
        return super().create(vals_list)

    def write(self, vals):
        if self._inoviq_is_branch_user() and any(f in vals for f in self.INOVIQ_INVENTORY_FIELDS):
            raise UserError("Inventory adjustments are not allowed for branch users.")
        return super().write(vals)
