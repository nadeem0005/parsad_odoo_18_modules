from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import float_compare

GROUP_USER = 'wh_transfer_order.group_wh_transfer_user'
GROUP_SHIPPER = 'wh_transfer_order.group_wh_transfer_shipper'
GROUP_RECEIVER = 'wh_transfer_order.group_wh_transfer_receiver'
GROUP_MANAGER = 'wh_transfer_order.group_wh_transfer_manager'


class WhTransferOrder(models.Model):
    _name = 'wh.transfer.order'
    _description = 'Warehouse Transfer Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Reference', default='New', copy=False, readonly=True, index=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('in_transit', 'In Transit'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], default='draft', copy=False, tracking=True, index=True)

    source_warehouse_id = fields.Many2one(
        'stock.warehouse', string='From Warehouse', required=True, tracking=True,
        default=lambda self: self.env['stock.warehouse'].search(
            [('company_id', '=', self.env.company.id)], limit=1),
        domain="[('company_id', '=', company_id)]")
    dest_warehouse_id = fields.Many2one(
        'stock.warehouse', string='To Warehouse', required=True, tracking=True,
        domain="[('company_id', '=', company_id)]")
    source_location_id = fields.Many2one(
        'stock.location', string='Source Location', required=True,
        compute='_compute_source_location', store=True, readonly=False, precompute=True,
        domain="[('usage', '=', 'internal'), ('company_id', '=', company_id)]")
    dest_location_id = fields.Many2one(
        'stock.location', string='Destination Location', required=True,
        compute='_compute_dest_location', store=True, readonly=False, precompute=True,
        domain="[('usage', '=', 'internal'), ('company_id', '=', company_id)]")

    line_ids = fields.One2many('wh.transfer.order.line', 'order_id', string='Products', copy=True)
    # Same records, shown in a second list used while shipping / receiving.
    shipment_line_ids = fields.One2many(
        'wh.transfer.order.line', 'order_id', string='Shipment Lines')
    picking_ids = fields.One2many('stock.picking', 'wh_transfer_id', string='Transfers', copy=False)
    picking_count = fields.Integer(compute='_compute_picking_count')
    show_locations = fields.Boolean(compute='_compute_permissions')
    can_confirm = fields.Boolean(compute='_compute_permissions')
    can_ship = fields.Boolean(compute='_compute_permissions')
    can_receive = fields.Boolean(compute='_compute_permissions')
    note = fields.Html(string='Notes')

    # ------------------------------------------------------------------
    # Computes / constraints
    # ------------------------------------------------------------------
    @api.depends('source_warehouse_id')
    def _compute_source_location(self):
        for order in self:
            order.source_location_id = order.source_warehouse_id.lot_stock_id

    @api.depends('dest_warehouse_id')
    def _compute_dest_location(self):
        for order in self:
            order.dest_location_id = order.dest_warehouse_id.lot_stock_id

    @api.depends('picking_ids')
    def _compute_picking_count(self):
        for order in self:
            order.picking_count = len(order.picking_ids)

    @api.depends_context('uid')
    @api.depends('source_warehouse_id', 'dest_warehouse_id')
    def _compute_permissions(self):
        user = self.env.user
        is_manager = user.has_group(GROUP_MANAGER)
        is_creator = user.has_group(GROUP_USER)
        is_shipper = user.has_group(GROUP_SHIPPER)
        is_receiver = user.has_group(GROUP_RECEIVER)
        allowed = user.wh_transfer_warehouse_ids
        show_locations = user.has_group('stock.group_stock_multi_locations')
        for order in self:
            order.show_locations = show_locations
            order.can_confirm = is_creator and (
                is_manager or order.source_warehouse_id in allowed)
            order.can_ship = is_shipper and (
                is_manager or order.source_warehouse_id in allowed)
            order.can_receive = is_receiver and (
                is_manager or order.dest_warehouse_id in allowed)

    @api.constrains('source_warehouse_id', 'dest_warehouse_id', 'company_id')
    def _check_warehouses(self):
        for order in self:
            if order.source_warehouse_id == order.dest_warehouse_id:
                raise ValidationError(_("Source and destination warehouses must be different."))
            if (order.source_warehouse_id.company_id != order.company_id
                    or order.dest_warehouse_id.company_id != order.company_id):
                raise ValidationError(_("Both warehouses must belong to the order's company."))

    @api.constrains('source_warehouse_id')
    def _check_user_warehouses(self):
        user = self.env.user
        if user.has_group(GROUP_MANAGER):
            return
        allowed = user.wh_transfer_warehouse_ids
        for order in self:
            if order.source_warehouse_id not in allowed:
                raise ValidationError(_(
                    "You can only create transfer orders that start from one of your "
                    "warehouses. Ask a manager to assign your warehouses."))

    # ------------------------------------------------------------------
    # ORM
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('wh.transfer.order') or 'New'
        return super().create(vals_list)

    def write(self, vals):
        locked = {'source_warehouse_id', 'dest_warehouse_id', 'source_location_id',
                  'dest_location_id', 'company_id'}
        if locked & set(vals) and any(order.state != 'draft' for order in self):
            raise UserError(_("Warehouses and locations can only be changed on a draft order."))
        if (not self.env.context.get('wh_transfer_internal')
                and not self.env.user.has_group(GROUP_MANAGER)):
            if 'state' in vals or 'name' in vals:
                raise AccessError(_("The status can only be changed with the workflow buttons."))
            if (locked | {'line_ids'}) & set(vals) and any(
                    not order.can_confirm for order in self):
                raise AccessError(_(
                    "Only a Creator of the source warehouse can edit this transfer order."))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_active(self):
        if any(order.state not in ('draft', 'cancel') for order in self):
            raise UserError(_("Only draft or cancelled transfer orders can be deleted."))

    # ------------------------------------------------------------------
    # Permissions
    # ------------------------------------------------------------------
    def _check_permission(self, group_xmlid, label):
        if not self.env.user.has_group(group_xmlid):
            raise AccessError(_("You do not have the permission to %s transfer orders.", label))

    def _check_warehouse_permission(self, side, label):
        """Shipping needs access to the source warehouse, receiving to the destination."""
        user = self.env.user
        if user.has_group(GROUP_MANAGER):
            return
        for order in self:
            warehouse = order.source_warehouse_id if side == 'source' else order.dest_warehouse_id
            if warehouse not in user.wh_transfer_warehouse_ids:
                raise AccessError(_(
                    "You cannot %(action)s %(order)s: you are not assigned to the warehouse %(wh)s.",
                    action=label, order=order.name, wh=warehouse.display_name))

    # ------------------------------------------------------------------
    # Workflow actions
    # ------------------------------------------------------------------
    def action_confirm(self):
        self._check_permission(GROUP_USER, _("confirm"))
        self._check_warehouse_permission('source', _("confirm"))
        for order in self.with_context(wh_transfer_internal=True):
            if order.state != 'draft':
                raise UserError(_("Only draft orders can be confirmed."))
            order._check_before_confirm()
            order._create_pickings()
            # Pre-fill the quantity to ship with the demand; the shipper may lower it.
            for line in order.line_ids:
                line.qty_sent = line.qty_demand
            order.state = 'confirmed'
            order._message_log(body=_("Transfer order confirmed and waiting to be shipped."))
        return True

    def action_ship(self):
        self._check_permission(GROUP_SHIPPER, _("ship"))
        self._check_warehouse_permission('source', _("ship"))
        for order in self.with_context(wh_transfer_internal=True):
            if order.state != 'confirmed':
                raise UserError(_("Only confirmed orders can be shipped."))
            order._check_before_ship()
            picking_out = order._get_open_picking('out')
            picking_in = order._get_open_picking('in')
            if not picking_out or not picking_in:
                raise UserError(_("The linked pickings of this order could not be found."))

            order._fill_picking(picking_out, 'qty_sent')
            order._validate_picking(picking_out)

            # The receipt now only expects what was really sent.
            lines = order.line_ids
            for move in picking_in.move_ids.filtered(lambda m: m.state not in ('done', 'cancel')):
                line = lines.filtered(lambda l: l.product_id == move.product_id)[:1]
                if line and float_compare(
                        move.product_uom_qty, line.qty_sent,
                        precision_rounding=move.product_uom.rounding) != 0:
                    move.product_uom_qty = line.qty_sent
            order.state = 'in_transit'
            order._message_log(body=_("Goods shipped by %s.", self.env.user.name))
        return True

    def action_receive(self):
        self._check_permission(GROUP_RECEIVER, _("receive"))
        self._check_warehouse_permission('dest', _("receive"))
        for order in self.with_context(wh_transfer_internal=True):
            if order.state != 'in_transit':
                raise UserError(_("Only orders in transit can be received."))
            order._check_before_receive()
            picking_in = order._get_open_picking('in')
            if not picking_in:
                raise UserError(_("The receipt of this order could not be found."))

            # Exactly what was shipped is received: nothing can be left in transit.
            order._fill_picking(picking_in, 'qty_sent')
            order._validate_picking(picking_in)
            # Internal bookkeeping: the receiver has read-only access to the lines,
            # so this write is done with elevated rights after all checks passed.
            for line in order.line_ids.sudo():
                line.qty_received = line.qty_sent
            order.state = 'done'
            order._message_log(body=_(
                "Goods received by %s. The full shipped quantity was received.",
                self.env.user.name))
        return True

    def action_cancel(self):
        self._check_permission(GROUP_USER, _("cancel"))
        self._check_warehouse_permission('source', _("cancel"))
        for order in self.with_context(wh_transfer_internal=True):
            if order.state != 'confirmed':
                raise UserError(_(
                    "Only confirmed orders that were not shipped yet can be cancelled."))
            order.picking_ids.filtered(lambda p: p.state != 'cancel').action_cancel()
            order.state = 'cancel'
        return True

    def action_draft(self):
        self._check_permission(GROUP_MANAGER, _("reset"))
        for order in self:
            if order.state != 'cancel':
                raise UserError(_("Only cancelled orders can be reset to draft."))
            order.picking_ids.unlink()
            order.line_ids.with_context(wh_transfer_internal=True).write(
                {'qty_sent': 0.0, 'qty_received': 0.0})
            order.state = 'draft'
        return True

    def action_view_pickings(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('stock.action_picking_tree_all')
        action['domain'] = [('wh_transfer_id', '=', self.id)]
        action['context'] = {'create': False}
        return action

    # ------------------------------------------------------------------
    # Checks
    # ------------------------------------------------------------------
    def _check_before_confirm(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Add at least one product before confirming."))
        if any(line.qty_demand <= 0 for line in self.line_ids):
            raise UserError(_("All demand quantities must be greater than zero."))
        if not self.company_id.internal_transit_location_id:
            raise UserError(_("The company has no internal transit location configured."))

    def _check_before_ship(self):
        self.ensure_one()
        if not any(line.qty_sent > 0 for line in self.line_ids):
            raise UserError(_("Enter a sent quantity greater than zero on at least one line."))
        for line in self.line_ids.filtered(lambda l: l.qty_sent > 0):
            product = line.product_id.with_context(location=self.source_location_id.id)
            needed = line.product_uom_id._compute_quantity(line.qty_sent, product.uom_id)
            if float_compare(product.qty_available, needed,
                             precision_rounding=product.uom_id.rounding) < 0:
                raise UserError(_(
                    "Not enough stock of %(product)s in %(location)s: "
                    "%(available)s available, %(needed)s to ship.",
                    product=product.display_name,
                    location=self.source_location_id.display_name,
                    available=product.qty_available, needed=needed))

    def _check_before_receive(self):
        self.ensure_one()
        if not any(line.qty_sent > 0 for line in self.line_ids):
            raise UserError(_("Nothing was shipped on this order."))

    # ------------------------------------------------------------------
    # Picking helpers
    # ------------------------------------------------------------------
    def _get_open_picking(self, leg):
        self.ensure_one()
        return self.picking_ids.filtered(
            lambda p: p.wh_transfer_leg == leg and p.state not in ('done', 'cancel'))[:1]

    def _fill_picking(self, picking, qty_field):
        """Copy the quantities typed on the order onto the picking's moves."""
        self.ensure_one()
        picking.action_assign()
        for move in picking.move_ids.filtered(lambda m: m.state not in ('done', 'cancel')):
            line = self.line_ids.filtered(lambda l: l.product_id == move.product_id)[:1]
            qty = line[qty_field] if line else 0.0
            move.quantity = qty
            move.picked = qty > 0
            if float_compare(move.quantity, qty, precision_rounding=move.product_uom.rounding) != 0:
                raise UserError(_(
                    "Could not set %(qty)s for %(product)s. Check the stock availability.",
                    qty=qty, product=move.product_id.display_name))

    def _validate_picking(self, picking):
        picking.with_context(
            wh_transfer_validate=True,
            skip_backorder=True,
            picking_ids_not_to_backorder=picking.ids,
        ).button_validate()
        if picking.state != 'done':
            raise UserError(_(
                "The transfer %s could not be validated automatically. "
                "Products tracked by lot or serial number need extra information.",
                picking.name))

    def _prepare_move_vals(self, line, picking_type, src, dest):
        return {
            'name': line.product_id.display_name,
            'product_id': line.product_id.id,
            'product_uom_qty': line.qty_demand,
            'product_uom': line.product_uom_id.id,
            'location_id': src.id,
            'location_dest_id': dest.id,
            'picking_type_id': picking_type.id,
            'company_id': self.company_id.id,
        }

    def _prepare_picking_vals(self, leg, picking_type, src, dest, move_vals):
        return {
            'picking_type_id': picking_type.id,
            'location_id': src.id,
            'location_dest_id': dest.id,
            'origin': self.name,
            'company_id': self.company_id.id,
            'wh_transfer_id': self.id,
            'wh_transfer_leg': leg,
            'move_ids': [Command.create(vals) for vals in move_vals],
        }

    def _create_pickings(self):
        self.ensure_one()
        Picking = self.env['stock.picking']
        transit = self.company_id.internal_transit_location_id
        out_type = self.source_warehouse_id.int_type_id
        in_type = self.dest_warehouse_id.int_type_id

        # Leg 1: source -> transit
        out_vals = [self._prepare_move_vals(l, out_type, self.source_location_id, transit)
                    for l in self.line_ids]
        picking_out = Picking.create(self._prepare_picking_vals(
            'out', out_type, self.source_location_id, transit, out_vals))

        # Leg 2: transit -> destination, chained to the first leg's moves
        in_vals = []
        for line, out_move in zip(self.line_ids, picking_out.move_ids):
            vals = self._prepare_move_vals(line, in_type, transit, self.dest_location_id)
            vals['move_orig_ids'] = [Command.link(out_move.id)]
            in_vals.append(vals)
        picking_in = Picking.create(self._prepare_picking_vals(
            'in', in_type, transit, self.dest_location_id, in_vals))

        picking_out.action_confirm()
        picking_in.action_confirm()
        return picking_out | picking_in

    def _update_state(self):
        """Safety net: keep the order state in sync if a picking is cancelled elsewhere."""
        for order in self.filtered(lambda o: o.state in ('confirmed', 'in_transit')):
            pickings = order.picking_ids
            if pickings and all(p.state == 'cancel' for p in pickings):
                order.state = 'cancel'
