# -*- coding: utf-8 -*-
# Part of Inoviq Systems. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class StockScrap(models.Model):
    _inherit = 'stock.scrap'

    @api.depends('company_id', 'picking_id')
    def _compute_location_id(self):
        super()._compute_location_id()
        user = self.env.user
        if self.env.su or not user.has_group('inoviq_branch_access.group_branch_user'):
            return
        # default the scrap location to the user's own warehouse stock location
        for scrap in self:
            if scrap.picking_id:
                continue
            warehouse = user.warehouse_ids.filtered(
                lambda w: w.company_id == scrap.company_id)[:1]
            if warehouse:
                scrap.location_id = warehouse.lot_stock_id
