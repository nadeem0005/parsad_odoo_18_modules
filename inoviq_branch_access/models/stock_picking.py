# -*- coding: utf-8 -*-
# Part of Inoviq Systems. See LICENSE file for full copyright and licensing details.

from odoo import api, models
from odoo.exceptions import ValidationError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    @api.constrains('picking_type_id')
    def _check_inoviq_branch_picking_type(self):
        user = self.env.user
        if self.env.su or not user.has_group('inoviq_branch_access.group_branch_user'):
            return
        for picking in self:
            wh = picking.picking_type_id.warehouse_id
            if wh and wh not in user.warehouse_ids:
                raise ValidationError(
                    "You can only create transfers from your own warehouse(s): %s"
                    % ", ".join(user.warehouse_ids.mapped('name'))
                )
