from psycopg2 import OperationalError

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_is_zero
from odoo.tools.misc import format_amount


class SaleQuickPaymentWizard(models.TransientModel):
    _name = 'sale.quick.payment.wizard'
    _description = 'Sales Order Quick Payment'

    sale_order_id = fields.Many2one('sale.order', required=True, readonly=True)
    partner_id = fields.Many2one(related='sale_order_id.partner_id', string="Customer")
    company_id = fields.Many2one(related='sale_order_id.company_id')
    currency_id = fields.Many2one(related='sale_order_id.currency_id')
    amount_total = fields.Monetary(related='sale_order_id.amount_total', string="Order Total",
                                   currency_field='currency_id')
    amount_residual = fields.Monetary(compute='_compute_amount_residual', string="Remaining Balance",
                                      currency_field='currency_id')
    payment_type = fields.Selection(
        [('full', "Full payment"),
         ('partial', "Partial payment (0 = credit sale, no invoice)")],
        string="Payment Type", default='full', required=True)
    amount = fields.Monetary(string="Amount to Pay", currency_field='currency_id', required=True)
    journal_id = fields.Many2one(
        'account.journal', string="Payment Journal",
        domain="[('type', 'in', ('bank', 'cash')), ('company_id', '=', company_id)]")
    payment_date = fields.Date(default=fields.Date.context_today, required=True)
    memo = fields.Char(string="Memo")

    @api.depends('sale_order_id')
    def _compute_amount_residual(self):
        for wiz in self:
            wiz.amount_residual = wiz.sale_order_id._get_quick_payment_due()

    # ------------------------------------------------------------------
    # Defaults
    # ------------------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if res.get('sale_order_id'):
            order = self.env['sale.order'].browse(res['sale_order_id'])
            due = order._get_quick_payment_due()
            if due <= 0:
                raise UserError(_("Nothing is left to invoice or collect on %s.", order.name))
            res.setdefault('payment_type', 'full')
            res['amount'] = due
            res.setdefault('memo', order.name)
            if not res.get('journal_id'):
                res['journal_id'] = self.env['account.journal'].search([
                    ('type', 'in', ('bank', 'cash')),
                    ('company_id', '=', order.company_id.id)], limit=1).id
        return res

    # ------------------------------------------------------------------
    # Validation (shared by UI constraint and server-side action)
    # ------------------------------------------------------------------
    def _check_amount(self, amount, due, payment_type, currency):
        rounding = currency.rounding
        if float_compare(due, 0.0, precision_rounding=rounding) <= 0:
            raise ValidationError(_("This order is already fully paid."))
        if float_compare(amount, 0.0, precision_rounding=rounding) < 0:
            raise ValidationError(_("The payment amount cannot be negative."))
        cmp = float_compare(amount, due, precision_rounding=rounding)
        if cmp > 0:
            raise ValidationError(_(
                "The payment amount (%(amount)s) cannot exceed the remaining balance (%(due)s).",
                amount=format_amount(self.env, amount, currency),
                due=format_amount(self.env, due, currency)))
        if payment_type == 'full' and cmp != 0:
            raise ValidationError(_(
                "A full payment must equal the remaining balance (%s).",
                format_amount(self.env, due, currency)))
        if payment_type == 'partial' and cmp >= 0:
            raise ValidationError(_(
                "A partial payment must be less than the remaining balance. "
                "Choose 'Full payment' to settle the whole balance."))

    @api.constrains('amount', 'payment_type')
    def _constrain_amount(self):
        for wiz in self:
            wiz._check_amount(wiz.amount, wiz.amount_residual, wiz.payment_type, wiz.currency_id)

    @api.onchange('payment_type')
    def _onchange_payment_type(self):
        for wiz in self:
            wiz.amount = wiz.amount_residual if wiz.payment_type == 'full' else 0.0

    @api.onchange('amount')
    def _onchange_amount(self):
        for wiz in self:
            if wiz.sale_order_id and float_compare(
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
    def _lock_rows(self, table, ids):
        try:
            self.env.cr.execute(
                f"SELECT id FROM {table} WHERE id IN %s FOR NO KEY UPDATE NOWAIT", [tuple(ids)])
        except OperationalError as e:
            raise UserError(_("This order is being processed by another user. Please retry.")) from e

    def _notify(self, title, message):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': title, 'message': message, 'type': 'success', 'sticky': False,
                       'next': {'type': 'ir.actions.act_window_close'}},
        }

    def action_register_payment(self):
        self.ensure_one()
        order = self.sale_order_id
        currency = order.currency_id

        # Lock + re-read: the balance may have changed since the wizard was opened.
        self._lock_rows('sale_order', order.ids)
        order.invalidate_recordset(['invoice_ids', 'invoice_status', 'amount_total', 'state'])
        due = order._get_quick_payment_due()
        self._check_amount(self.amount, due, self.payment_type, currency)

        # Amount 0 => credit sale: order confirmed + delivered, NO invoice.
        if float_is_zero(self.amount, precision_rounding=currency.rounding):
            return self._notify(
                _("Credit sale"),
                _("%s is confirmed and delivered. No invoice was created.", order.name))

        if not self.journal_id:
            raise UserError(_("Please select a payment journal."))

        invoice = order._auto_create_and_post_invoice()
        self._lock_rows('account_move', invoice.ids)
        invoice.invalidate_recordset(['state', 'payment_state', 'amount_residual'])
        self._check_amount(self.amount, invoice.amount_residual, self.payment_type,
                           invoice.currency_id)

        register = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids,
        ).create({
            'amount': self.amount,
            'currency_id': invoice.currency_id.id,
            'journal_id': self.journal_id.id,
            'payment_date': self.payment_date,
            'communication': self.memo or invoice.name,
        })
        payments = register._create_payments()  # standard posting + reconciliation

        invoice.invalidate_recordset(['payment_state', 'amount_residual'])
        return self._notify(
            _("Payment registered"),
            _("%(payment)s recorded for invoice %(invoice)s. Remaining balance: %(residual)s",
              payment=', '.join(payments.mapped('name')), invoice=invoice.name,
              residual=format_amount(self.env, invoice.amount_residual, invoice.currency_id)))
