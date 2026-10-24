# Design notes - Odoo 18 technical decisions

## 1. Automatic computation vs manual override
In Odoo 18 `price_unit` and `discount` are *stored computed fields with `readonly=False`* (`compute=..., store=True, readonly=False`).
The ORM writes computed values through the compute/flush mechanism, **not** through the values passed to `create()`/`write()`.
Therefore a price can only appear in `create()`/`write()` vals if a caller supplied it (web client, RPC, import, Python).

For callers outside the price group we:
1. **Strip** the protected fields from the vals;
2. let Odoo create/write normally so the **standard compute fills the price** (vendor price, pricelist, qty break, UoM change...);
3. **Compare** the requested value with the resulting value (and, on write, with the pre-write value) at the field's own decimal precision.
   Equal -> nothing was overridden (this is what the web client sends after an onchange). Different -> `AccessError`, full rollback, audit row.

This avoids the classic mistake of "block every write to price_unit", which breaks onchange round-trips, qty-break pricing, product changes and imports of unchanged values. It also does not depend on private Odoo fields such as `technical_price_unit`.

## 2. Why the exemptions are not an `env.context` flag
Context is client-controlled over RPC, so a context bypass key would be a hole. Exemptions are:
* `env.su` (superuser: cron, procurement, website sudo) and
* `trusted_price_override()` - a **thread-local** section entered only by Python code (used for the down-payment wizard).

## 3. Read-only UI
`_get_view` is extended on `sale.order` / `purchase.order` to set `readonly="1"` on `price_unit`/`discount` inside `order_line` (all sub-views: list, form, kanban) for non-managers. A single `xpath` would only hit the first sub-view, and a structural xpath would break the install if Odoo's arch changes; the post-processing hook cannot. Arch generation is group-aware in Odoo's view cache. Read-only fields are not sent by the client, so the stored computation fills them. This is cosmetic: the security is the ORM check.

## 4. Role filtering
* Field-level `domain` on `partner_id` (standard domain preserved + role clause), so every UI that uses the field gets it.
* The clause accepts the flag on the contact **or its commercial entity**, so persons under a flagged company stay selectable; invoice/delivery addresses use their own domains and are untouched.
* Not security-relevant on its own, so it is re-checked on the server on create/write (post-create so `default_partner_id` contexts are covered).

## 5. Other decisions
* Duplicates (`copy_data`) drop protected values for non-managers: a copy gets the *system* price, not a copied manual override.
* `discount` and the sale order `pricelist_id` are also locked (both change the effective price).
* Audit rows are written with a separate cursor because the validation error rolls back the main transaction.
* No bulk backfill: per the spec, nothing is auto-classified; a snippet to migrate from `customer_rank`/`supplier_rank` is in the README.
* Contact role editing is enforced in `create()`/`write()` (not `groups=` on the field) so everybody can still *see* the roles.
* `ir.model.access.csv` only covers the audit model: no other new models.

## 6. Not verified in a live Odoo instance
This sandbox has no Odoo/PostgreSQL. Python and XML were syntax-checked, but the module and its tests have **not** been executed. Run the test command from the README on a test database first.
