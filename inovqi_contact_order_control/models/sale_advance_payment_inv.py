# -*- coding: utf-8 -*-
from odoo import models

from .price_protection_mixin import trusted_price_override


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = 'sale.advance.payment.inv'

    def create_invoices(self):
        """Down-payment lines carry a wizard-computed amount as ``price_unit``.

        The wizard is a legitimate system operation, so it runs in a trusted
        (thread-local, non-forgeable) section; direct ORM/RPC writes do not.
        """
        with trusted_price_override():
            return super().create_invoices()
