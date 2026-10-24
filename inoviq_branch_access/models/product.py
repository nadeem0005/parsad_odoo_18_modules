# -*- coding: utf-8 -*-
# Part of Inoviq Systems. See LICENSE file for full copyright and licensing details.

from odoo import api, models
from odoo.exceptions import UserError

BRANCH_GROUP = 'inoviq_branch_access.group_branch_user'

BLOCKED_FORM_ARCH = (
    '<form create="0" edit="0" delete="0" duplicate="0">'
    '<div class="alert alert-info m-4" role="alert">'
    'Product details are not available for branch users.'
    '</div></form>'
)


def _inoviq_is_branch(env):
    return not env.su and env.user.has_group(BRANCH_GROUP)


def _inoviq_block_form(env, result):
    """Replace the product form by a notice, so the product page cannot be opened."""
    if _inoviq_is_branch(env) and 'form' in result.get('views', {}):
        result['views']['form']['arch'] = BLOCKED_FORM_ARCH
    return result


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.model
    @api.readonly
    def get_views(self, views, options=None):
        return _inoviq_block_form(self.env, super().get_views(views, options))

    def action_update_quantity_on_hand(self):
        if _inoviq_is_branch(self.env):
            raise UserError("Inventory adjustments are not allowed for branch users.")
        return super().action_update_quantity_on_hand()


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.model
    @api.readonly
    def get_views(self, views, options=None):
        return _inoviq_block_form(self.env, super().get_views(views, options))

    def action_update_quantity_on_hand(self):
        if _inoviq_is_branch(self.env):
            raise UserError("Inventory adjustments are not allowed for branch users.")
        return super().action_update_quantity_on_hand()
