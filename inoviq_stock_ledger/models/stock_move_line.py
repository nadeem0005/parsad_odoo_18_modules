# -*- coding: utf-8 -*-
# Part of Inoviq Systems. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.tools import float_round

# Every done move line produces up to two ledger entries:
#   * an "in"  entry (+qty) for the warehouse that receives the goods
#   * an "out" entry (-qty) for the warehouse that issues the goods
# Moves inside the same warehouse (Stock -> Shelf) produce no entry.
# A running total is then calculated per (product, warehouse), ordered by date and id.
LEDGER_QUERY = """
WITH entries AS (
    SELECT ml.id AS line_id, ml.product_id, ml.date,
           'in' AS side, dl.warehouse_id AS wh,
           COALESCE(ml.quantity_product_uom, 0) AS qty
      FROM stock_move_line ml
      JOIN stock_location sl ON sl.id = ml.location_id
      JOIN stock_location dl ON dl.id = ml.location_dest_id
     WHERE ml.state = 'done'
       AND ml.product_id IN %(products)s
       AND ml.date <= %(max_date)s
       AND dl.usage = 'internal'
       AND (sl.usage <> 'internal'
            OR COALESCE(sl.warehouse_id, 0) <> COALESCE(dl.warehouse_id, 0))
    UNION ALL
    SELECT ml.id AS line_id, ml.product_id, ml.date,
           'out' AS side, sl.warehouse_id AS wh,
           -COALESCE(ml.quantity_product_uom, 0) AS qty
      FROM stock_move_line ml
      JOIN stock_location sl ON sl.id = ml.location_id
      JOIN stock_location dl ON dl.id = ml.location_dest_id
     WHERE ml.state = 'done'
       AND ml.product_id IN %(products)s
       AND ml.date <= %(max_date)s
       AND sl.usage = 'internal'
       AND (dl.usage <> 'internal'
            OR COALESCE(sl.warehouse_id, 0) <> COALESCE(dl.warehouse_id, 0))
)
SELECT line_id, side, wh, qty,
       SUM(qty) OVER (
           PARTITION BY product_id, COALESCE(wh, 0)
           ORDER BY date, line_id, side
           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
       ) AS closing
  FROM entries
"""


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    ledger_warehouse_id = fields.Many2one(
        'stock.warehouse', string="Warehouse", compute='_compute_ledger')
    ledger_opening_qty = fields.Float(
        string="Opening Qty", compute='_compute_ledger', digits='Product Unit of Measure')
    ledger_in_qty = fields.Float(
        string="In", compute='_compute_ledger', digits='Product Unit of Measure')
    ledger_out_qty = fields.Float(
        string="Out", compute='_compute_ledger', digits='Product Unit of Measure')
    ledger_closing_qty = fields.Float(
        string="Closing Qty", compute='_compute_ledger', digits='Product Unit of Measure')

    @api.depends('state', 'product_id', 'date', 'quantity',
                 'location_id', 'location_dest_id')
    def _compute_ledger(self):
        for line in self:
            line.ledger_warehouse_id = False
            line.ledger_opening_qty = 0.0
            line.ledger_in_qty = 0.0
            line.ledger_out_qty = 0.0
            line.ledger_closing_qty = 0.0

        lines = self.filtered(lambda l: l.id and l.state == 'done' and l.product_id)
        if not lines:
            return

        self.env['stock.move.line'].flush_model([
            'product_id', 'date', 'state', 'location_id',
            'location_dest_id', 'quantity_product_uom',
        ])
        self.env['stock.location'].flush_model(['usage', 'warehouse_id'])

        self.env.cr.execute(LEDGER_QUERY, {
            'products': tuple(lines.product_id.ids),
            'max_date': max(lines.mapped('date')),
        })
        # {line_id: {'in': (wh, qty, closing), 'out': (wh, qty, closing)}}
        entries = {}
        for line_id, side, wh, qty, closing in self.env.cr.fetchall():
            entries.setdefault(line_id, {})[side] = (wh, qty, closing)

        digits = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for line in lines:
            sides = entries.get(line.id)
            if not sides:
                continue
            # If goods move straight between two warehouses show the receiving side
            wh, qty, closing = sides.get('in') or sides['out']
            closing = float_round(closing, precision_digits=digits)
            qty = float_round(qty, precision_digits=digits)
            line.ledger_warehouse_id = wh or False
            line.ledger_closing_qty = closing
            line.ledger_opening_qty = float_round(closing - qty, precision_digits=digits)
            line.ledger_in_qty = qty if qty > 0 else 0.0
            line.ledger_out_qty = -qty if qty < 0 else 0.0
