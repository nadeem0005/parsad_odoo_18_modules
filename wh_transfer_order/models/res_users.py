from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    wh_transfer_warehouse_ids = fields.Many2many(
        'stock.warehouse', 'wh_transfer_user_warehouse_rel', 'user_id', 'warehouse_id',
        string='Transfer Order Warehouses',
        help="Warehouses this user works with. He only sees and processes the warehouse "
             "transfer orders that start from or arrive at one of these warehouses. "
             "Transfer managers are not restricted.")

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['wh_transfer_warehouse_ids']
