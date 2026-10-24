# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'inovqi.price.protection.mixin']

    _inovqi_price_group = 'inovqi_contact_order_control.group_sale_price_manager'
    _inovqi_candidate_fields = ('pricelist_id',)

    # Standard domain (type / company) + customer role. A child contact of a
    # customer company is accepted through its commercial entity.
    partner_id = fields.Many2one(
        domain="[('type', '!=', 'private'), ('company_id', 'in', (False, company_id)), "
               "'|', ('is_customer', '=', True), ('commercial_partner_id.is_customer', '=', True)]")

    def _inovqi_protected_fields(self):
        param = self.env['ir.config_parameter'].sudo().get_param(
            'inovqi_contact_order_control.protect_sale_pricelist', 'True')
        if str(param).strip().lower() in ('0', 'false', 'no'):
            return []
        return super()._inovqi_protected_fields()

    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        vals_list, requested = self._inovqi_strip_create_vals(vals_list)
        orders = super().create(vals_list)
        orders._inovqi_assert_partner_role(orders.partner_id, 'is_customer', _("Customer"))
        orders._inovqi_validate_created(requested)
        return orders

    def write(self, vals):
        previous_partner = {}
        if 'partner_id' in vals:
            previous_partner = {order.id: order.partner_id.id for order in self}
        vals, requested, previous = self._inovqi_strip_write_vals(vals)
        result = super().write(vals)
        if previous_partner:
            changed = self.filtered(lambda o: o.partner_id.id != previous_partner[o.id])
            changed._inovqi_assert_partner_role(changed.partner_id, 'is_customer', _("Customer"))
        self._inovqi_validate_written(requested, previous)
        return result

    # ------------------------------------------------------------------
    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type == 'form' and not self._inovqi_user_is_price_manager():
            self._inovqi_lock_price_nodes(
                arch, order_fields=self._inovqi_protected_fields() or ())
        return arch, view
