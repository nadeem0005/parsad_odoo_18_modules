# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import AccessError

ROLE_FIELDS = ('is_vendor', 'is_customer', 'is_employee_contact')
ROLE_MANAGER_GROUP = 'inovqi_contact_order_control.group_contact_role_manager'


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_vendor = fields.Boolean(
        string="Vendor", copy=False, index=True, tracking=True,
        help="This contact can be selected as vendor on Purchase Orders.")
    is_customer = fields.Boolean(
        string="Customer", copy=False, index=True, tracking=True,
        help="This contact can be selected as customer on Sales Orders.")
    is_employee_contact = fields.Boolean(
        string="Employee", copy=False, index=True, tracking=True,
        help="This contact is classified as an employee for Inovqi business purposes.")
    inovqi_can_edit_roles = fields.Boolean(compute='_compute_inovqi_can_edit_roles')

    # ------------------------------------------------------------------
    @api.model
    def _inovqi_user_can_edit_roles(self):
        return self.env.su or self.env.user.has_group(ROLE_MANAGER_GROUP)

    @api.depends_context('uid')
    def _compute_inovqi_can_edit_roles(self):
        allowed = self._inovqi_user_can_edit_roles()
        for partner in self:
            partner.inovqi_can_edit_roles = allowed

    def _inovqi_deny_role_change(self):
        raise AccessError(_(
            "Only members of the group 'Contact Role Manager' may change the Business "
            "Roles (Vendor / Customer / Employee) of a contact."))

    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        if not self._inovqi_user_can_edit_roles():
            for vals in vals_list:
                if any(vals.get(name) for name in ROLE_FIELDS):
                    self._inovqi_deny_role_change()
        return super().create(vals_list)

    def write(self, vals):
        if any(name in vals for name in ROLE_FIELDS) and not self._inovqi_user_can_edit_roles():
            for partner in self:
                for name in ROLE_FIELDS:
                    if name in vals and bool(vals[name]) != partner[name]:
                        self._inovqi_deny_role_change()
        return super().write(vals)
