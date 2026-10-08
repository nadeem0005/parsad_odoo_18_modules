from odoo import _, api, fields, models
from odoo.exceptions import AccessError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # ------------------------------------------------------------------
    # Payment status (from the customer invoices and their payments)
    # ------------------------------------------------------------------
    inv_paid_amount = fields.Monetary(
        string='Paid', compute='_compute_inv_payment', store=True,
        currency_field='currency_id',
        help="Amount already paid on the posted customer invoices of this order.")
    inv_pending_amount = fields.Monetary(
        string='Pending', compute='_compute_inv_payment', store=True,
        currency_field='currency_id',
        help="Order total minus what was paid (includes the part not invoiced yet).")
    inv_payment_status = fields.Selection(
        [('unpaid', 'Not Paid'), ('partial', 'Partially Paid'), ('paid', 'Fully Paid')],
        string='Payment Status', compute='_compute_inv_payment', store=True)
    inv_paid_percent = fields.Float(
        string='Paid %', compute='_compute_inv_paid_percent')

    # ------------------------------------------------------------------
    # Warehouse restriction (follows the assignment of the order's salesperson)
    # ------------------------------------------------------------------
    allowed_warehouse_ids = fields.Many2many(
        'stock.warehouse', compute='_compute_warehouse_access',
        help="Warehouses that can be selected on this order.")
    warehouse_locked = fields.Boolean(
        compute='_compute_warehouse_access',
        help="True when the salesperson has exactly one assigned warehouse.")

    # ------------------------------------------------------------------
    # Salesperson restriction
    # ------------------------------------------------------------------
    salesperson_locked = fields.Boolean(compute='_compute_salesperson_locked')

    @api.depends(
        'state', 'amount_total', 'currency_id', 'company_id',
        'order_line.invoice_lines.move_id.state',
        'order_line.invoice_lines.move_id.move_type',
        'order_line.invoice_lines.move_id.amount_total',
        'order_line.invoice_lines.move_id.amount_residual')
    def _compute_inv_payment(self):
        for order in self:
            currency = order.currency_id or order.company_id.currency_id
            paid = 0.0
            if order.state == 'sale':
                invoices = order.order_line.invoice_lines.move_id.filtered(
                    lambda m: m.state == 'posted' and m.move_type == 'out_invoice')
                for invoice in invoices:
                    invoice_paid = invoice.amount_total - invoice.amount_residual
                    paid += invoice.currency_id._convert(
                        invoice_paid, currency, order.company_id,
                        invoice.invoice_date or fields.Date.context_today(order))
            paid = currency.round(paid)
            order.inv_paid_amount = paid
            order.inv_pending_amount = max(currency.round(order.amount_total - paid), 0.0)
            if order.state != 'sale':
                order.inv_payment_status = False
            elif currency.compare_amounts(paid, order.amount_total) >= 0:
                order.inv_payment_status = 'paid'
            elif currency.is_zero(paid):
                order.inv_payment_status = 'unpaid'
            else:
                order.inv_payment_status = 'partial'

    @api.depends('inv_paid_amount', 'amount_total')
    def _compute_inv_paid_percent(self):
        for order in self:
            if order.amount_total:
                order.inv_paid_percent = min(
                    100.0, max(0.0, order.inv_paid_amount / order.amount_total * 100.0))
            else:
                order.inv_paid_percent = 100.0 if order.state == 'sale' else 0.0

    # ------------------------------------------------------------------
    # Warehouse: the assignment of the salesperson (or of the logged-in user)
    # ------------------------------------------------------------------
    @api.depends('user_id', 'company_id')
    def _compute_warehouse_id(self):
        super()._compute_warehouse_id()
        for order in self:
            if order.state in ('draft', 'sent') or not order.ids:
                user = (order.user_id or self.env.user).with_company(order.company_id.id)
                warehouse = user._get_assigned_sale_warehouse()
                if warehouse:
                    order.warehouse_id = warehouse

    @api.model
    def _get_assigned_warehouses(self, user, company):
        """Warehouses assigned to `user` in `company` (empty recordset = no restriction)."""
        return user.wh_transfer_warehouse_ids.filtered(lambda w: w.company_id == company)

    @api.depends('user_id', 'company_id')
    def _compute_warehouse_access(self):
        all_warehouses = {}
        for order in self:
            user = order.user_id or self.env.user
            assigned = self._get_assigned_warehouses(user, order.company_id)
            if assigned:
                order.allowed_warehouse_ids = assigned
            else:
                company = order.company_id
                if company not in all_warehouses:
                    all_warehouses[company] = self.env['stock.warehouse'].search(
                        [('company_id', '=', company.id)])
                order.allowed_warehouse_ids = all_warehouses[company]
            order.warehouse_locked = len(assigned) == 1

    def _check_assigned_warehouse(self, warehouse_id, user, company):
        if self.env.su or not warehouse_id:
            return
        assigned = self._get_assigned_warehouses(user, company)
        if assigned and warehouse_id not in assigned.ids:
            raise AccessError(_(
                "The warehouse of this order must be one of the warehouses assigned to %s.",
                user.name))

    # ------------------------------------------------------------------
    # Salesperson lock
    # ------------------------------------------------------------------
    @api.model
    def _is_salesperson_restricted(self):
        """True for salespeople who are neither Sales Administrators nor system admins."""
        if self.env.su:
            return False
        user = self.env.user
        return (user.has_group('sales_team.group_sale_salesman')
                and not user.has_group('sales_team.group_sale_manager')
                and not user.has_group('base.group_system'))

    @api.depends_context('uid')
    def _compute_salesperson_locked(self):
        locked = self._is_salesperson_restricted()
        for order in self:
            order.salesperson_locked = locked

    @api.depends('partner_id')
    def _compute_user_id(self):
        super()._compute_user_id()
        if self._is_salesperson_restricted():
            for order in self:
                if not order._origin.id:
                    order.user_id = self.env.user

    @api.model_create_multi
    def create(self, vals_list):
        restricted = self._is_salesperson_restricted()
        for vals in vals_list:
            if restricted and vals.get('user_id') and vals['user_id'] != self.env.uid:
                raise AccessError(_("You can only create orders for yourself."))
            if vals.get('warehouse_id'):
                user = self.env['res.users'].browse(vals.get('user_id') or self.env.uid)
                company = self.env['res.company'].browse(
                    vals.get('company_id') or self.env.company.id)
                self._check_assigned_warehouse(vals['warehouse_id'], user, company)
        return super().create(vals_list)

    def write(self, vals):
        if 'user_id' in vals and self._is_salesperson_restricted() \
                and vals['user_id'] != self.env.uid:
            raise AccessError(_("You cannot change the salesperson of an order."))
        if vals.get('warehouse_id'):
            for order in self:
                user = self.env['res.users'].browse(
                    vals.get('user_id') or order.user_id.id or self.env.uid)
                company = self.env['res.company'].browse(
                    vals.get('company_id') or order.company_id.id)
                order._check_assigned_warehouse(vals['warehouse_id'], user, company)
        return super().write(vals)
