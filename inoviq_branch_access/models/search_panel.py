# -*- coding: utf-8 -*-
# Part of Inoviq Systems. See LICENSE file for full copyright and licensing details.

from odoo import api, models
from odoo.osv import expression

BRANCH_GROUP = 'inoviq_branch_access.group_branch_user'


class Base(models.AbstractModel):
    _inherit = 'base'

    @api.model
    def search_panel_select_range(self, field_name, **kwargs):
        """Side panels (e.g. 'Warehouses' in Reporting > Stock) must only list the
        warehouses of a Branch User."""
        field = self._fields.get(field_name)
        if (
            field is not None
            and field.type == 'many2one'
            and field.comodel_name == 'stock.warehouse'
            and not self.env.su
            and self.env.user.has_group(BRANCH_GROUP)
        ):
            kwargs['comodel_domain'] = expression.AND([
                kwargs.get('comodel_domain') or [],
                [('id', 'in', self.env.user.warehouse_ids.ids)],
            ])
        return super().search_panel_select_range(field_name, **kwargs)
