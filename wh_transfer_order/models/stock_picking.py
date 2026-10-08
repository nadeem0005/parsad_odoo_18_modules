from odoo import _, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    wh_transfer_id = fields.Many2one(
        'wh.transfer.order', string='Transfer Order', copy=False, index='btree_not_null',
        readonly=True)
    wh_transfer_leg = fields.Selection(
        [('out', 'Dispatch'), ('in', 'Receipt')], string='Transfer Leg', copy=False, readonly=True)

    def button_validate(self):
        if (any(picking.wh_transfer_id for picking in self)
                and not self.env.context.get('wh_transfer_validate')):
            raise UserError(_(
                "This transfer belongs to a Warehouse Transfer Order. "
                "Please ship or receive it from the transfer order itself."))
        return super().button_validate()

    def action_cancel(self):
        res = super().action_cancel()
        self.wh_transfer_id._update_state()
        return res
