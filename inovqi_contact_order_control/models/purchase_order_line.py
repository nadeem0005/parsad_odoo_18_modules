# -*- coding: utf-8 -*-
from odoo import api, models


class PurchaseOrderLine(models.Model):
    _name = 'purchase.order.line'
    _inherit = ['purchase.order.line', 'inovqi.price.protection.mixin']

    _inovqi_price_group = 'inovqi_contact_order_control.group_purchase_price_manager'
    _inovqi_candidate_fields = ('price_unit', 'discount')

    @api.model_create_multi
    def create(self, vals_list):
        vals_list, requested = self._inovqi_strip_create_vals(vals_list)
        lines = super().create(vals_list)
        lines._inovqi_validate_created(requested)
        return lines

    def write(self, vals):
        vals, requested, previous = self._inovqi_strip_write_vals(vals)
        result = super().write(vals)
        self._inovqi_validate_written(requested, previous)
        return result

    def copy_data(self, default=None):
        data_list = super().copy_data(default=default)
        return self._inovqi_drop_protected_from_copy(data_list)
