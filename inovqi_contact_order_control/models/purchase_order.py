# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class PurchaseOrder(models.Model):
    _name = 'purchase.order'
    _inherit = ['purchase.order', 'inovqi.price.protection.mixin']

    _inovqi_price_group = 'inovqi_contact_order_control.group_purchase_price_manager'
    _inovqi_candidate_fields = ()

    # Standard domain (company) + vendor role. A child contact of a vendor
    # company is accepted through its commercial entity.
    partner_id = fields.Many2one(
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id), "
               "'|', ('is_vendor', '=', True), ('commercial_partner_id.is_vendor', '=', True)]")

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        orders._inovqi_assert_partner_role(orders.partner_id, 'is_vendor', _("Vendor"))
        return orders

    def write(self, vals):
        previous_partner = {}
        if 'partner_id' in vals:
            previous_partner = {order.id: order.partner_id.id for order in self}
        result = super().write(vals)
        if previous_partner:
            changed = self.filtered(lambda o: o.partner_id.id != previous_partner[o.id])
            changed._inovqi_assert_partner_role(changed.partner_id, 'is_vendor', _("Vendor"))
        return result

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type == 'form' and not self._inovqi_user_is_price_manager():
            self._inovqi_lock_price_nodes(arch)
        return arch, view
