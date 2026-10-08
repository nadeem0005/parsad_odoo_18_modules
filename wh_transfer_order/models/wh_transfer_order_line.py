from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import float_compare


class WhTransferOrderLine(models.Model):
    _name = 'wh.transfer.order.line'
    _description = 'Warehouse Transfer Order Line'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    order_id = fields.Many2one('wh.transfer.order', required=True, ondelete='cascade', index=True)
    product_id = fields.Many2one(
        'product.product', string='Product', required=True,
        domain="[('is_storable', '=', True)]")
    product_uom_id = fields.Many2one(
        'uom.uom', string='Unit', required=True,
        compute='_compute_product_uom', store=True, readonly=False, precompute=True)
    qty_demand = fields.Float(
        string='Demand', digits='Product Unit of Measure', required=True, default=1.0)
    qty_sent = fields.Float(
        string='Sent', digits='Product Unit of Measure', copy=False,
        help="Quantity actually shipped. Filled in by the shipper.")
    qty_received = fields.Float(
        string='Received', digits='Product Unit of Measure', copy=False, readonly=True,
        help="Always equal to the sent quantity once the order is received.")

    @api.depends('product_id')
    def _compute_product_uom(self):
        for line in self:
            line.product_uom_id = line.product_id.uom_id

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('qty_demand', 'qty_sent', 'qty_received')
    def _check_quantities(self):
        for line in self:
            rounding = line.product_uom_id.rounding or 0.01
            if line.qty_demand < 0 or line.qty_sent < 0 or line.qty_received < 0:
                raise ValidationError(_("Quantities cannot be negative."))
            if float_compare(line.qty_sent, line.qty_demand, precision_rounding=rounding) > 0:
                raise ValidationError(_(
                    "%s: you cannot send more than the demand.", line.product_id.display_name))

    @api.constrains('order_id', 'product_id')
    def _check_unique_product(self):
        for line in self:
            dupes = line.order_id.line_ids.filtered(lambda l: l.product_id == line.product_id)
            if len(dupes) > 1:
                raise ValidationError(_(
                    "Product %s appears more than once. Merge the quantities into one line.",
                    line.product_id.display_name))

    # ------------------------------------------------------------------
    # ORM: enforce who can edit what, and when (server side)
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get('wh_transfer_internal'):
            order_ids = {vals['order_id'] for vals in vals_list if vals.get('order_id')}
            orders = self.env['wh.transfer.order'].browse(order_ids)
            if any(o.state != 'draft' for o in orders):
                raise UserError(_("Products can only be added while the order is in draft."))
            if any(not o.can_confirm for o in orders):
                raise AccessError(_(
                    "Only a Creator of the source warehouse can add products to this order."))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('wh_transfer_internal'):
            draft_fields = {'product_id', 'product_uom_id', 'qty_demand'}
            for line in self:
                order = line.order_id
                if draft_fields & set(vals):
                    if order.state != 'draft':
                        raise UserError(_("Products and demand can only be changed in draft."))
                    if not order.can_confirm:
                        raise AccessError(_(
                            "Only a Creator of the source warehouse can edit the products."))
                if 'qty_sent' in vals and (order.state != 'confirmed' or not order.can_ship):
                    raise AccessError(_(
                        "Only a Shipper of the source warehouse can set the sent quantity, "
                        "and only on a confirmed order."))
                if 'qty_received' in vals:
                    raise AccessError(_(
                        "The received quantity cannot be edited: it is always what was shipped."))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_started(self):
        if any(line.order_id.state not in ('draft', 'cancel') for line in self):
            raise UserError(_("Lines can only be removed from a draft order."))
        if not self.env.context.get('wh_transfer_internal') and any(
                not line.order_id.can_confirm for line in self):
            raise AccessError(_("Only a Creator of the source warehouse can remove products."))
