# Inovqi Contact & Order Control

Odoo 18 Community module by **InovqiSystems** - technical name `inovqi_contact_order_control`, version `18.0.1.0.0`.
Depends on: `base`, `contacts`, `sale_management`, `purchase`. No third-party Python dependencies, no core changes.

## Features

| # | Feature | Where |
|---|---------|-------|
| 1 | **Business Roles** on contacts: `is_vendor`, `is_customer`, `is_employee_contact` (independent booleans, all default to *off*; never auto-classified). New *Business Roles* tab on the contact form, search filters *Vendors / Customers / Employees / No Business Role*. | `models/res_partner.py`, `views/res_partner_views.xml` |
| 2 | **Purchase Orders** only offer vendors (`is_vendor`) | domain on `purchase.order.partner_id` + server check |
| 3 | **Sales Orders** only offer customers (`is_customer`) | domain on `sale.order.partner_id` + server check |
| 4 | **Purchase price protection** (`price_unit`, `discount`) | `models/purchase_order_line.py` |
| 5 | **Sales price protection** (`price_unit`, `discount`, order `pricelist_id`) | `models/sale_order_line.py`, `models/sale_order.py` |
| 6 | **Security groups** | `security/security.xml` |
| + | **Audit log** of blocked attempts (*Settings > Blocked Price Changes*) | `models/price_violation_log.py` |

### Role semantics
* A contact qualifies as vendor/customer when **it or its commercial entity (parent company)** carries the flag. So a person under a flagged company can be chosen; invoice/delivery child contacts keep working untouched (no role needed on them).
* The role is validated when the partner of an order is **set or changed** (create, edit, duplicate, import, RPC) - not retroactively: existing orders stay editable if a contact is un-flagged later.
* Orders created by the system (superuser/`sudo`: reordering rules, MTO/dropship, website checkout, cron) are exempt.
* The partner field on the SO/PO form has "Create" disabled: contacts must be classified before being used.

## Groups and permissions

| Group | Purpose | Implied by |
|-------|---------|-----------|
| **Contact Role Manager** | Change Vendor/Customer/Employee flags (+ contact creation rights). No price rights. | Settings Administrator (`base.group_system`) |
| **Sales Price Manager** | Override sales line price/discount and the order pricelist | `Inovqi Order Price Manager` |
| **Purchase Price Manager** | Override purchase line price/discount | `Inovqi Order Price Manager` |
| **Inovqi Order Price Manager** | Umbrella: both of the above. Grants nothing else. | - |

**Administrator policy (explicit decision):** the standard Settings Administrator receives the *Contact Role Manager* permission but **not** any price-override permission. Price power is deliberately an explicit grant: add the user to *Inovqi Order Price Manager* (Settings > Users > Access Rights > "Inovqi Order Pricing"). The superuser/OdooBot (system operations, cron) is never restricted.

## How price protection works
See `DESIGN_NOTES.md`. In short: for users outside the price group, any protected value supplied through UI, RPC, import or ORM is compared with what Odoo's own computation produces; a mismatch rolls the transaction back with an `AccessError` and writes a log row. The UI additionally renders the fields read-only. Normal computation (vendor prices, pricelists, qty breaks, taxes, currency, totals) is untouched.

Protected: `price_unit` and `discount` on `sale.order.line` / `purchase.order.line`, and `pricelist_id` on `sale.order`
(switch off with system parameter `inovqi_contact_order_control.protect_sale_pricelist = False`).

## Installation
1. Copy the folder `inovqi_contact_order_control` into an addons path of your Odoo 18 CE server.
2. Restart Odoo, enable developer mode, *Apps > Update Apps List*.
3. Install **Inovqi Contact & Order Control** (or `odoo -d DB -i inovqi_contact_order_control --stop-after-init`).

## Upgrade
`odoo -d DB -u inovqi_contact_order_control --stop-after-init` then restart (clears view/ORM caches).

## Post-install configuration (important)
1. **Classify existing contacts.** Nothing is auto-classified, so until contacts are flagged nobody can be selected on new orders. Use the list view: select contacts > *Action > Export/Update* is not available for booleans in bulk in all builds, so the quickest way is a one-off shell/server action, e.g. (run as a Contact Role Manager or in `odoo shell`):
   ```python
   Partner = env['res.partner']
   Partner.search([('supplier_rank', '>', 0)]).write({'is_vendor': True})
   Partner.search([('customer_rank', '>', 0)]).write({'is_customer': True})
   ```
2. Add trusted users to **Inovqi Order Price Manager** (or the Sales/Purchase sub-group).
3. Add contact administrators to **Contact Role Manager**.

## Tests
```
odoo -d TESTDB -i inovqi_contact_order_control --test-tags /inovqi_contact_order_control --stop-after-init
```
Covers: role filtering (vendor-only / customer-only / both / neither), invoice & delivery addresses, normal user vs price manager vs forged RPC/import writes, automatic vendor pricing, pricelist computation, duplicates, form (UI) flows, quotation/PO confirmation, taxes & totals, adding/removing lines, invoicing (skipped without a chart of accounts) and deliveries/receipts (skipped without `stock`).

## Known integration points / limits
* **Glue code that legitimately writes prices for a normal user** (down payments are already handled; delivery lines from `delivery`, loyalty/coupon rewards from `sale_loyalty`, etc.) must wrap the call:
  ```python
  from odoo.addons.inovqi_contact_order_control.models.price_protection_mixin import trusted_price_override
  with trusted_price_override():
      ...
  ```
  The flag is thread-local, so RPC clients cannot forge it (unlike a context key).
* Taxes, UoM, currency, vendor pricelists (`product.supplierinfo`), customer pricelist items and product costs are **not** locked by this module. Restrict edit access to those through standard access rights (Sales/Purchase managers only), otherwise they remain a back door.
* A product with no vendor price gives a 0 price for a normal user; a price manager must fill it in.
* Option lines (`sale.order.option`): adding an option whose price was edited by the user is rejected by the line check.

## Files
| File | Purpose |
|------|---------|
| `__manifest__.py` | Module metadata, dependencies, data load order |
| `models/price_protection_mixin.py` | Core engine: strip/compare/reject logic, thread-local trusted section, partner role validation, read-only UI helper |
| `models/price_violation_log.py` | Audit model (written via an independent cursor so it survives the rollback) |
| `models/res_partner.py` | Role fields, role-edit protection |
| `models/sale_order.py` / `sale_order_line.py` | Customer domain + role check, pricelist/price/discount protection, read-only UI |
| `models/purchase_order.py` / `purchase_order_line.py` | Vendor domain + role check, price/discount protection, read-only UI |
| `models/sale_advance_payment_inv.py` | Trusted section for the down-payment wizard |
| `security/security.xml` | Categories, groups, admin policy |
| `security/ir.model.access.csv` | Read-only access to the audit log |
| `views/res_partner_views.xml` | Business Roles tab and search filters |
| `views/sale_order_views.xml`, `views/purchase_order_views.xml` | Partner field options (no on-the-fly creation) |
| `views/price_violation_log_views.xml` | Audit log list/form/action/menu |
| `tests/` | `common.py` fixtures, `test_contact_roles.py`, `test_sale_price.py`, `test_purchase_price.py`, `test_regression.py` |
| `README.md`, `DESIGN_NOTES.md` | This document and the Odoo 18 technical decisions |
