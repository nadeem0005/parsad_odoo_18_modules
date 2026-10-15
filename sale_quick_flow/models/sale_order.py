import logging

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare

_logger = logging.getLogger(__name__)

# Multi-step routes (pick -> pack -> ship) release pickings one after another.
MAX_PICKING_PASSES = 6


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    has_payable_invoice = fields.Boolean(
        compute='_compute_has_payable_invoice',
        help="Technical: a posted customer invoice with an unpaid balance exists.",
    )

    # ------------------------------------------------------------------
    # Computes / helpers
    # ------------------------------------------------------------------
    def _compute_has_payable_invoice(self):
        for order in self:
            order.has_payable_invoice = bool(order._get_payable_invoice())

    def _get_payable_invoice(self):
        """Oldest posted customer invoice of this order with a positive residual."""
        self.ensure_one()
        invoices = self.invoice_ids.filtered(
            lambda m: m.move_type == 'out_invoice'
            and m.state == 'posted'
            and float_compare(m.amount_residual, 0.0, precision_rounding=m.currency_id.rounding) > 0
        )
        return invoices.sorted('id')[:1]

    # ------------------------------------------------------------------
    # Main entry point (called by the replaced "Confirm" button)
    # ------------------------------------------------------------------
    def action_confirm_and_process(self):
        """Confirm -> validate delivery -> create & post invoice -> open payment wizard.

        Everything runs in ONE transaction: if any step fails, the user gets the error
        message and nothing is left half-processed (order stays as it was).
        The standard ``action_confirm`` is untouched, so website/API/automation
        confirmations keep the stock Odoo behaviour.
        """
        self.ensure_one()
        if self.state not in ('draft', 'sent'):
            raise UserError(_("Only quotations can be confirmed with this action."))

        # 1. Standard confirmation
        res = self.action_confirm()
        if isinstance(res, dict):  # a standard wizard/warning must be handled first
            return res

        # 2. Delivery
        try:
            self._auto_validate_deliveries()
        except UserError as e:
            raise UserError(_("Delivery validation failed for %(order)s:\n%(error)s",
                              order=self.name, error=e.args[0])) from e

        # 3. Invoice
        try:
            invoice = self._auto_create_and_post_invoice()
        except UserError as e:
            raise UserError(_("Invoicing failed for %(order)s:\n%(error)s",
                              order=self.name, error=e.args[0])) from e

        # 4. Payment wizard
        return self._get_quick_payment_action(invoice)

    # ------------------------------------------------------------------
    # Delivery
    # ------------------------------------------------------------------
    def _ensure_negative_stock_allowed(self):
        """Enable Odoo 18's standard 'Allow Negative Stock' flag on the locations / products /
        categories involved, so validation is never blocked by insufficient stock.
        Can be disabled with the system parameter sale_quick_flow.allow_negative_stock = False.
        """
        self.ensure_one()
        param = self.env['ir.config_parameter'].sudo().get_param(
            'sale_quick_flow.allow_negative_stock', 'True')
        if str(param).lower() in ('false', '0', ''):
            return
        pending = self.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel'))
        moves = pending.move_ids
        locations = moves.location_id | moves.move_line_ids.location_id
        locations = self.env['stock.location'].sudo().search([
            ('id', 'child_of', locations.ids), ('usage', '=', 'internal')])
        products = moves.product_id.sudo()
        for records in (locations, products.product_tmpl_id, products.categ_id):
            if 'allow_negative_stock' in records._fields:
                todo = records.filtered(lambda r: not r.allow_negative_stock)
                if todo:
                    todo.write({'allow_negative_stock': True})

    def _auto_validate_deliveries(self):
        self.ensure_one()
        self.invalidate_recordset(['picking_ids'])
        if not self.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel')):
            return  # services only / nothing to deliver
        self._ensure_negative_stock_allowed()

        for _pass in range(MAX_PICKING_PASSES):
            pending = self.picking_ids.filtered(
                lambda p: p.state not in ('done', 'cancel')).sorted('id')
            if not pending:
                return
            progressed = False
            for picking in pending:
                if picking.state == 'waiting':  # waits for a previous step; next pass
                    continue
                self._force_validate_picking(picking)
                progressed = True
            if not progressed:
                break

        left = self.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel'))
        if left:
            raise UserError(_("These transfers could not be completed automatically: %s",
                              ', '.join(left.mapped('name'))))

    def _force_validate_picking(self, picking):
        if picking.state == 'draft':
            picking.action_confirm()
        picking.action_assign()  # reserve what exists; the rest is forced below

        moves = picking.move_ids.filtered(lambda m: m.state not in ('done', 'cancel'))
        for move in moves:
            if move.product_id.tracking != 'none':
                raise UserError(_(
                    "Product '%s' is tracked by lot/serial number. Lots/serials must be "
                    "chosen manually, so this transfer cannot be validated automatically.",
                    move.product_id.display_name))
            if float_compare(move.quantity, move.product_uom_qty,
                             precision_rounding=move.product_uom.rounding) < 0:
                move.quantity = move.product_uom_qty  # creates/updates the move lines
            move.picked = True

        res = picking.with_context(
            skip_immediate=True,
            skip_backorder=True,
            skip_sms=True,
            button_validate_picking_ids=picking.ids,
        ).button_validate()
        if isinstance(res, dict):
            raise UserError(_("Transfer %s requires manual confirmation.", picking.name))
        if picking.state != 'done':
            raise UserError(_("Transfer %(name)s ended in state '%(state)s'.",
                              name=picking.name, state=picking.state))

    # ------------------------------------------------------------------
    # Invoice
    # ------------------------------------------------------------------
    def _auto_create_and_post_invoice(self):
        self.ensure_one()
        payable = self._get_payable_invoice()
        if payable:
            return payable

        draft = self.invoice_ids.filtered(
            lambda m: m.move_type == 'out_invoice' and m.state == 'draft')
        invoice = draft[:1]
        if not invoice:
            if self.invoice_status != 'to invoice':
                raise UserError(_("Nothing is available to invoice on this order."))
            invoice = self._create_invoices()  # standard: quantities, prices, taxes, partner
        invoice.action_post()
        return invoice

    # ------------------------------------------------------------------
    # Payment wizard
    # ------------------------------------------------------------------
    def _get_quick_payment_action(self, invoice):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Register Payment"),
            'res_model': 'sale.quick.payment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_order_id': self.id,
                'default_move_id': invoice.id,
            },
        }

    def action_open_quick_payment(self):
        self.ensure_one()
        invoice = self._get_payable_invoice()
        if not invoice:
            raise UserError(_("There is no posted invoice with an unpaid balance on this order."))
        return self._get_quick_payment_action(invoice)
