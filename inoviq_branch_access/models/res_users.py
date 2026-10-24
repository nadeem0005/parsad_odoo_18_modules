# -*- coding: utf-8 -*-
# Part of Inoviq Systems. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    warehouse_ids = fields.Many2many(
        'stock.warehouse',
        'inoviq_user_warehouse_rel', 'user_id', 'warehouse_id',
        string="Allowed Warehouses",
        help="Warehouses this user is limited to. Only used when the user is in the "
             "'Branch User' group. A Branch User without a warehouse sees nothing.",
    )

    def _inoviq_sync_default_warehouse(self):
        """Make the first allowed warehouse the default warehouse for sales orders."""
        for user in self:
            if user.warehouse_ids and user.property_warehouse_id not in user.warehouse_ids:
                warehouse = user.warehouse_ids[0]
                user.with_company(warehouse.company_id).property_warehouse_id = warehouse

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        users._inoviq_sync_default_warehouse()
        self.env.registry.clear_cache()
        return users

    def write(self, vals):
        res = super().write(vals)
        if 'warehouse_ids' in vals:
            self._inoviq_sync_default_warehouse()
            # record rules read user.warehouse_ids, so the rule cache must be refreshed
            self.env.registry.clear_cache()
        return res

    @api.model
    def context_get(self):
        """Add a flag to the user context so views can hide buttons for Branch Users
        (the user must log in again after being added to the group)."""
        context = super().context_get()
        if self.env.user.has_group('inoviq_branch_access.group_branch_user'):
            context = dict(context, inoviq_branch_user=True)
        return context
