# Sales Quick Flow (Odoo 18)

Confirm -> validate delivery (negative stock allowed) -> create & post invoice -> payment wizard.

## Install
1. Copy `sale_quick_flow/` into an addons path (e.g. `/opt/odoo/custom_addons`).
2. Restart Odoo, enable Developer Mode, Apps -> Update Apps List.
3. Install "Sales Quick Flow: Confirm, Deliver, Invoice & Pay"
   (CLI: `odoo -d DB -i sale_quick_flow --stop-after-init`).
4. Give users the group "Quick Sales Flow" (or Sales + Inventory User + Invoicing rights).

## Negative stock
The module switches on Odoo's standard "Allow Negative Stock" flag (stock.location,
product, product category) for the records involved, at confirmation time.
Disable this with system parameter `sale_quick_flow.allow_negative_stock = False`
and configure manually: Inventory > Configuration > Locations (Allow Negative Stock)
and Product Categories.

## Limits
* Lot/serial-tracked products must be validated manually.
* Standard `action_confirm` is unchanged (website, API, automations keep stock behaviour).
