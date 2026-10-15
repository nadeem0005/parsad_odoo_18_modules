from psycopg2 import OperationalError

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare
from odoo.tools.misc import format_amount


class SaleQuickPaymentWizard(models.TransientModel):
    _name = 'sale.quick.payment.wizard'
    _description = 'Sales Order Quick Payment'

    sale_order_id = fields.Many2one('sale.order', required=True, readonly=True)
    move_id = fields.Many2one(
        'account.move', string="Invoice", required=True, readonly=True,
        domain="[('move_type', '=', 'out_invoice'), ('state', '=', 'posted')]")
    partner_id = fields.Many2one(related='move_id.partner_id', string="Customer")
    company_id = fields.Many2one(related='move_id.company_id')
    currency_id = fields.Many2one(related='move_id.currency_id')
    amount_total = fields.Monetary(related='move_id.amount_total', string="Invoice Total",
                                   currency_field='currency_id')
    amount_residual = fields.Monetary(related='move_id.amount_residual', string="Remaining Balance",
                                      currency_field='currency_id')
    payment_type = fields.Selection(
        [('full', "Full payment"), ('partial', "Partial payment")],
        string="Payment Type", default='full', required=True)
    amount = fields.Monetary(string="Amount to Pay", currency_field='currency_id', required=True)
    journal_id = fields.Many2one(
        'account.journal', string="Payment Journal", required=True,
        domain="[('type', 'in', ('bank', 'cash')), ('company_id', '=', company_id)]")
    payment_date = fields.Date(default=fields.Date.context_today, required=True)
    memo = fields.Char(string="Memo")

    # ------------------------------------------------------------------
    # Defaults
    # ------------------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if res.get('move_id'):
            move = self.env['account.move'].browse(res['move_id'])
            rounding = move.currency_id.rounding
            if move.state != 'posted' or float_compare(
                    move.amount_residual, 0.0, precision_rounding=rounding) <= 0:
                raise UserError(_("Invoice %s has no unpaid balance.", move.name))
            res.setdefault('payment_type', 'full')
            res['amount'] = move.amount_residual
            res.setdefault('memo', move.name)
            if not res.get('journal_id'):
                journal = self.env['account.journal'].search([
                    ('type', 'in', ('bank', 'cash')),
                    ('company_id', '=', move.company_id.id)], limit=1)
                res['journal_id'] = journal.id
        return res

    # ------------------------------------------------------------------
    # Validation (shared by UI constraint and server-side action)
    # ------------------------------------------------------------------
    def _check_amount(self, amount, residual, payment_type, currency):
        rounding = currency.rounding
        if float_compare(residual, 0.0, precision_rounding=rounding) <= 0:
            raise ValidationError(_("This invoice is already fully paid."))
        if float_compare(amount, 0.0, precision_rounding=rounding) <= 0:
            raise ValidationError(_("The payment amount must be greater than zero."))
        cmp = float_compare(amount, residual, precision_rounding=rounding)
        if cmp > 0:
            raise ValidationError(_(
                "The payment amount (%(amount)s) cannot exceed the remaining balance (%(residual)s).",
                amount=format_amount(self.env, amount, currency),
                residual=format_amount(self.env, residual, currency)))
        if payment_type == 'full' and cmp != 0:
            raise ValidationError(_(
                "A full payment must equal the remaining balance (%s).",
                format_amount(self.env, residual, currency)))
        if payment_type == 'partial' and cmp >= 0:
            raise ValidationError(_(
                "A partial payment must be less than the remaining balance. "
                "Choose 'Full payment' to settle the whole balance."))

    @api.constrains('amount', 'payment_type', 'move_id')
    def _constrain_amount(self):
        for wiz in self:
            wiz._check_amount(wiz.amount, wiz.move_id.amount_residual,
                              wiz.payment_type, wiz.currency_id)

    @api.onchange('payment_type')
    def _onchange_payment_type(self):
        for wiz in self:
            wiz.amount = wiz.amount_residual if wiz.payment_type == 'full' else 0.0

    @api.onchange('amount')
    def _onchange_amount(self):
        for wiz in self:
            if wiz.move_id and float_compare(
                    wiz.amount, wiz.amount_residual,
                    precision_rounding=wiz.currency_id.rounding) > 0:
                return {'warning': {
                    'title': _("Invalid amount"),
                    'message': _(
                        "The payment amount cannot exceed the remaining balance (%s).",
                        format_amount(self.env, wiz.amount_residual, wiz.currency_id)),
                }}

    # ------------------------------------------------------------------
    # Action
    # ------------------------------------------------------------------
    def action_register_payment(self):
        self.ensure_one()
        move = self.move_id

        # Lock the invoice so two users cannot overpay concurrently, then re-read the
        # real balance (it may have changed since the wizard was opened).
        try:
            self.env.cr.execute(
                "SELECT id FROM account_move WHERE id = %s FOR NO KEY UPDATE NOWAIT", [move.id])
        except OperationalError as e:
            raise UserError(_("This invoice is being processed by another user. Please retry.")) from e
        move.invalidate_recordset(['state', 'payment_state', 'amount_residual'])

        if move.state != 'posted':
            raise UserError(_("Invoice %s is not posted.", move.name))
        self._check_amount(self.amount, move.amount_residual, self.payment_type, move.currency_id)

        register = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=move.ids,
        ).create({
            'amount': self.amount,
            'currency_id': move.currency_id.id,
            'journal_id': self.journal_id.id,
            'payment_date': self.payment_date,
            'communication': self.memo or move.name,
        })
        # Standard payment creation, posting and invoice reconciliation
        payments = register._create_payments()

        move.invalidate_recordset(['payment_state', 'amount_residual'])
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Payment registered"),
                'message': _("%(payment)s recorded. Remaining balance on %(invoice)s: %(residual)s",
                             payment=', '.join(payments.mapped('name')),
                             invoice=move.name,
                             residual=format_amount(self.env, move.amount_residual, move.currency_id)),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
