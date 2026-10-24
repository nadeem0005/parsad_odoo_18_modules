# -*- coding: utf-8 -*-
# Part of Inoviq Systems. See LICENSE file for full copyright and licensing details.

from odoo import api, models
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.constrains('warehouse_id')
    def _check_inoviq_branch_warehouse(self):
        user = self.env.user
        if self.env.su or not user.has_group('inoviq_branch_access.group_branch_user'):
            return
        for order in self:
            if order.warehouse_id and order.warehouse_id not in user.warehouse_ids:
                raise ValidationError(
                    "You can only sell from your own warehouse(s): %s"
                    % ", ".join(user.warehouse_ids.mapped('name'))
                )
