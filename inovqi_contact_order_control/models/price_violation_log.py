# -*- coding: utf-8 -*-
import logging

from odoo import SUPERUSER_ID, api, fields, models

_logger = logging.getLogger(__name__)


class InovqiPriceViolationLog(models.Model):
    """Immutable audit trail of blocked manual price changes.

    Rows are written through a *separate* database cursor so that they survive
    the rollback caused by the validation error that is raised right after.
    """
    _name = 'inovqi.price.violation.log'
    _description = 'Blocked Price Change Attempt'
    _order = 'create_date desc, id desc'

    user_id = fields.Many2one('res.users', string='User', readonly=True, ondelete='set null')
    model_name = fields.Char(string='Model', readonly=True)
    res_id = fields.Integer(string='Record ID', readonly=True)
    record_name = fields.Char(string='Order', readonly=True)
    field_name = fields.Char(string='Field', readonly=True)
    operation = fields.Selection(
        [('create', 'Create'), ('write', 'Write')], string='Operation', readonly=True)
    requested_value = fields.Char(string='Requested Value', readonly=True)
    current_value = fields.Char(string='System / Current Value', readonly=True)
    message = fields.Text(string='Message', readonly=True)

    @api.model
    def _log_attempt(self, values):
        """Persist a log row independently of the caller's transaction."""
        try:
            with self.env.registry.cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                env['inovqi.price.violation.log'].create(values)
        except Exception:  # never let logging mask the real validation error
            _logger.exception("Could not persist price violation log entry: %s", values)
