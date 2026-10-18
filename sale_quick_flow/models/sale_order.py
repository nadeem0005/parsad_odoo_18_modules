import logging

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare

_logger = logging.getLogger(__name__)

# Multi-step routes (pick -> pack -> ship) release pickings one after another.
MAX_PICKING_PASSES = 6


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    has_pending_payment = fields.Boolean(
        compute='_compute_has_pending_payment',
        help="Technical: the order still has an amount to invoice / collect.",
    )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _compute_has_pending_payment(self):
        for order in self:
            order.has_pending_payment = order._get_quick_payment_due() > 0

    def _get_payable_invoice(self):
        """Oldest posted customer invoice of this order with a positive residual."""
        self.ensure_one()
        invoices = self.invoice_ids.filtered(
            lambda m: m.move_type == 'out_invoice'
            and m.state == 'posted'
            and float_compare(m.amount_residual, 0.0, precision_rounding=m.currency_id.rounding) > 0
        )
        return invoices.sorted('id')[:1]

    def _get_quick_payment_due(self):
        """Amount still collectable: invoice residual if an invoice exists,
        otherwise the order total (invoice not created yet)."""
        self.ensure_one()
        if self.state != 'sale':
            return 0.0
        posted = self.invoice_ids.filtered(
            lambda m: m.move_type == 'out_invoice' and m.state == 'posted')
        if not posted:
            return self.amount_total if self.invoice_status == 'to invoice' else 0.0
        payable = self._get_payable_invoice()
        return payable.amount_residual if payable else 0.0

    # ------------------------------------------------------------------
    # Main entry point (called by the replaced "Confirm" button)
    # ------------------------------------------------------------------
    def action_confirm_and_process(self):
        """Confirm -> validate delivery (stock must be available) -> open payment wizard.

        The invoice is created later by the wizard, only when the amount paid is > 0.
        Everything runs in ONE transaction: if stock is missing or any step fails,
        the user sees the error and the order stays a quotation.
        """
        self.ensure_one()
        if self.state not in ('draft', 'sent'):
            raise UserError(_("Only quotations can be confirmed with this action."))

        res = self.action_confirm()  # standard confirmation
        if isinstance(res, dict):
            return res

        try:
            self._auto_validate_deliveries()
        except UserError as e:
            raise UserError(_("%(order)s cannot be confirmed:\n%(error)s",
                              order=self.name, error=e.args[0])) from e

        return self._get_quick_payment_action()

    # ------------------------------------------------------------------
    # Delivery (no negative stock)
    # ------------------------------------------------------------------
    def _auto_validate_deliveries(self):
        self.ensure_one()
        self.invalidate_recordset(['picking_ids'])
        if not self.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel')):
            return  # services only / nothing to deliver

        for _pass in range(MAX_PICKING_PASSES):
            pending = self.picking_ids.filtered(
                lambda p: p.state not in ('done', 'cancel')).sorted('id')
            if not pending:
                return
            progressed = False
            for picking in pending:
                if picking.state == 'waiting':  # waits for a previous step; next pass
                    continue
                self._validate_picking_with_stock(picking)
                progressed = True
            if not progressed:
                break

        left = self.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel'))
        if left:
            raise UserError(_("These transfers could not be completed automatically: %s",
                              ', '.join(left.mapped('name'))))

    def _validate_picking_with_stock(self, picking):
        if picking.state == 'draft':
            picking.action_confirm()
        picking.action_assign()  # reserve available stock

        moves = picking.move_ids.filtered(lambda m: m.state not in ('done', 'cancel'))
        short = moves.filtered(lambda m: m.state != 'assigned')
        if short:
            lines = [
                _("- %(product)s: required %(need)s, available %(have)s",
                  product=m.product_id.display_name,
                  need=m.product_uom_qty, have=m.quantity)
                for m in short
            ]
            raise UserError(
                _("Not enough stock. Make the products available in inventory first:\n")
                + "\n".join(lines))

        for move in moves:
            if move.product_id.tracking != 'none':
                raise UserError(_(
                    "Product '%s' is tracked by lot/serial number. Lots/serials must be "
                    "chosen manually, so this transfer cannot be validated automatically.",
                    move.product_id.display_name))
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
    # Invoice (called by the wizard when amount > 0)
    # ------------------------------------------------------------------
    def _auto_create_and_post_invoice(self):
        self.ensure_one()
        payable = self._get_payable_invoice()
        if payable:
            return payable

        invoice = self.invoice_ids.filtered(
            lambda m: m.move_type == 'out_invoice' and m.state == 'draft')[:1]
        if not invoice:
            if self.invoice_status != 'to invoice':
                raise UserError(_("Nothing is available to invoice on this order."))
            invoice = self._create_invoices()  # standard: quantities, prices, taxes, partner
        invoice.action_post()
        return invoice

    # ------------------------------------------------------------------
    # Payment wizard
    # ------------------------------------------------------------------
    def _get_quick_payment_action(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Register Payment"),
            'res_model': 'sale.quick.payment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_sale_order_id': self.id},
        }

    def action_open_quick_payment(self):
        self.ensure_one()
        if self._get_quick_payment_due() <= 0:
            raise UserError(_("Nothing is left to invoice or collect on this order."))
        return self._get_quick_payment_action()
