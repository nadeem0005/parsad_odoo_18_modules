# -*- coding: utf-8 -*-
"""Shared helpers for server-side price protection and partner-role validation.

How automatic computation is told apart from a manual override
---------------------------------------------------------------
Odoo 18 stores ``price_unit`` / ``discount`` as *computed, stored, editable*
fields (``compute=..., store=True, readonly=False``). The ORM fills them through
the compute mechanism, which never goes through ``create()`` / ``write()`` values.
So the only way a price reaches ``create()`` / ``write()`` is when somebody
*supplies* it: a client form, RPC, an import, or Python code.

For a user without price rights we therefore:

1. strip the protected fields out of the supplied values,
2. let Odoo create/write the record normally (the standard compute fills the price),
3. compare what the caller *asked for* with what the system produced (or, on
   write, with the value before the write) using the field's own precision.

If they are equal, nothing was overridden (this is the normal UI path: the client
echoes the price Odoo itself computed in the onchange). If they differ, it is a
manual override: the whole transaction is rolled back with an ``AccessError``
and the attempt is logged.
"""
import logging
import threading
from contextlib import contextmanager

from odoo import _, api, models
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import float_compare

_logger = logging.getLogger(__name__)

# Thread-local (NOT env.context!) so that RPC callers can never forge it.
_trusted = threading.local()


@contextmanager
def trusted_price_override():
    """Allow price values to be written by *trusted Python code* in this thread.

    Use it in glue code that legitimately creates priced lines on behalf of a
    normal user (down payments, delivery lines, loyalty rewards, ...)::

        from odoo.addons.inovqi_contact_order_control.models.price_protection_mixin \\
            import trusted_price_override
        with trusted_price_override():
            line_model.create(vals)
    """
    depth = getattr(_trusted, 'depth', 0)
    _trusted.depth = depth + 1
    try:
        yield
    finally:
        _trusted.depth = depth


def is_trusted_price_override():
    return getattr(_trusted, 'depth', 0) > 0


class InovqiPriceProtectionMixin(models.AbstractModel):
    _name = 'inovqi.price.protection.mixin'
    _description = 'Inovqi Price Protection Helpers'

    # To be defined by the concrete models --------------------------------
    _inovqi_price_group = None        # xmlid of the group allowed to override
    _inovqi_candidate_fields = ()     # protected field names (if they exist)

    # ------------------------------------------------------------------
    # Policy
    # ------------------------------------------------------------------
    def _inovqi_protected_fields(self):
        return [name for name in self._inovqi_candidate_fields if name in self._fields]

    def _inovqi_user_is_price_manager(self):
        return self.env.su or self.env.user.has_group(self._inovqi_price_group)

    def _inovqi_enforcement_active(self):
        """True when the current caller must NOT override protected fields."""
        if self.env.su or is_trusted_price_override():
            return False
        return not self.env.user.has_group(self._inovqi_price_group)

    # ------------------------------------------------------------------
    # create / write / copy helpers
    # ------------------------------------------------------------------
    def _inovqi_strip_create_vals(self, vals_list):
        """Return (clean_vals_list, requested) - requested is None if nothing to check."""
        if not self._inovqi_enforcement_active():
            return vals_list, None
        names = self._inovqi_protected_fields()
        if not names:
            return vals_list, None
        clean, requested = [], []
        for vals in vals_list:
            vals = dict(vals)
            requested.append({name: vals.pop(name) for name in names if name in vals})
            clean.append(vals)
        if not any(requested):
            return vals_list, None
        return clean, requested

    def _inovqi_validate_created(self, requested):
        if not requested:
            return
        for record, wanted in zip(self, requested):
            for name, value in wanted.items():
                if not self._inovqi_same(name, value, record[name]):
                    self._inovqi_reject(record, name, value, record[name], 'create')

    def _inovqi_strip_write_vals(self, vals):
        """Return (clean_vals, requested, previous)."""
        if not self._inovqi_enforcement_active():
            return vals, None, None
        names = [name for name in self._inovqi_protected_fields() if name in vals]
        if not names:
            return vals, None, None
        requested = {name: vals[name] for name in names}
        clean = {key: val for key, val in vals.items() if key not in requested}
        previous = {rec.id: {name: rec[name] for name in names} for rec in self}
        return clean, requested, previous

    def _inovqi_validate_written(self, requested, previous):
        if not requested:
            return
        for record in self:
            for name, value in requested.items():
                if self._inovqi_same(name, value, record[name]):
                    continue  # the standard computation produced exactly this value
                if self._inovqi_same(name, value, previous[record.id][name]):
                    continue  # value unchanged: not an override
                self._inovqi_reject(record, name, value, record[name], 'write')

    def _inovqi_drop_protected_from_copy(self, data_list):
        """Duplicated lines get the *system* price, never a copied override."""
        if not self._inovqi_enforcement_active():
            return data_list
        for data in data_list:
            for name in self._inovqi_protected_fields():
                data.pop(name, None)
        return data_list

    # ------------------------------------------------------------------
    # Comparison / rejection
    # ------------------------------------------------------------------
    def _inovqi_same(self, name, requested, current):
        field = self._fields[name]
        if field.type == 'float':
            digits = field.get_digits(self.env) if hasattr(field, 'get_digits') else None
            precision = digits[1] if digits else 2
            try:
                return float_compare(float(requested or 0.0), float(current or 0.0),
                                     precision_digits=precision) == 0
            except (TypeError, ValueError):
                return False
        if field.type == 'many2one':
            req_id = requested.id if isinstance(requested, models.BaseModel) else requested
            cur_id = current.id if isinstance(current, models.BaseModel) else current
            return (req_id or False) == (cur_id or False)
        return requested == current

    def _inovqi_repr(self, name, value):
        if isinstance(value, models.BaseModel):
            return value.display_name or ''
        field = self._fields[name]
        if field.type == 'many2one' and value:
            return self.env[field.comodel_name].browse(value).display_name or str(value)
        return str(value)

    def _inovqi_order_name(self, record):
        order = record.order_id if 'order_id' in record._fields else record
        return order.display_name or ''

    def _inovqi_reject(self, record, name, requested, current, operation):
        field = self._fields[name]
        group = self.env.ref(self._inovqi_price_group, raise_if_not_found=False)
        message = _(
            "You are not allowed to change the '%(field)s' manually on %(order)s. "
            "The value is computed automatically by Odoo (vendor prices, pricelists, "
            "product data). To override it, ask an administrator to add you to the "
            "group '%(group)s'.",
            field=field.string,
            order=self._inovqi_order_name(record) or record._description,
            group=group.full_name if group else self._inovqi_price_group,
        )
        user = self.env.user
        requested_txt = self._inovqi_repr(name, requested)
        current_txt = self._inovqi_repr(name, current)
        _logger.warning(
            "Blocked manual change of %s.%s (id=%s, %s) by user %s (id=%s): requested=%s, system/current=%s",
            record._name, name, record.id, self._inovqi_order_name(record),
            user.login, user.id, requested_txt, current_txt)
        self.env['inovqi.price.violation.log']._log_attempt({
            'user_id': user.id,
            'model_name': record._name,
            'res_id': record.id if operation == 'write' else 0,
            'record_name': self._inovqi_order_name(record),
            'field_name': name,
            'operation': operation,
            'requested_value': requested_txt,
            'current_value': current_txt,
            'message': message,
        })
        raise AccessError(message)

    # ------------------------------------------------------------------
    # Partner role validation (server side, complements the view domains)
    # ------------------------------------------------------------------
    def _inovqi_assert_partner_role(self, partners, role_field, role_label):
        """Raise if one of ``partners`` (res.partner recordset) lacks the role.

        A contact qualifies when it, or its commercial entity (parent company),
        carries the flag. System-created orders (superuser / sudo) are exempt.
        """
        if self.env.su or is_trusted_price_override() or not partners:
            return
        partners = partners.sudo().exists()
        invalid = partners.filtered(
            lambda p: not (p[role_field] or p.commercial_partner_id[role_field]))
        if invalid:
            raise ValidationError(_(
                "'%(partner)s' is not classified as %(role)s. Ask a Contact Role Manager "
                "to tick '%(role)s' under Business Roles on the contact.",
                partner=', '.join(invalid.mapped('display_name')),
                role=role_label,
            ))

    # ------------------------------------------------------------------
    # UI helper: make price nodes read-only for unauthorised users
    # ------------------------------------------------------------------
    @api.model
    def _inovqi_lock_price_nodes(self, arch, line_field='order_line',
                                 line_fields=('price_unit', 'discount'), order_fields=()):
        for name in line_fields:
            for node in arch.xpath("//field[@name='%s']//field[@name='%s']" % (line_field, name)):
                node.set('readonly', '1')
        for name in order_fields:
            for node in arch.xpath("//field[@name='%s']" % name):
                node.set('readonly', '1')
