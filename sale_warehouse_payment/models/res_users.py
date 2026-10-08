from odoo import models


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _get_assigned_sale_warehouse(self):
        """Warehouse assigned to the user (Warehouse Transfers tab) in the current company.

        With several assignments, the user's own Default Warehouse is used when it is one of
        them, otherwise the first one (by warehouse sequence). Empty if nothing is assigned.
        """
        assigned = self.wh_transfer_warehouse_ids.filtered(
            lambda w: w.company_id == self.env.company)
        if not assigned:
            return self.env['stock.warehouse']
        preferred = self.property_warehouse_id & assigned
        return (preferred or assigned)[:1]

    def _get_default_warehouse_id(self):
        warehouse = self._get_assigned_sale_warehouse()
        return warehouse or super()._get_default_warehouse_id()
