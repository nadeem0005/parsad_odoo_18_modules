# Sales Quick Flow (Odoo 18)

Confirm -> validate delivery (stock must be available) -> payment wizard ->
amount > 0: create & post invoice + register payment; amount = 0: credit sale (no invoice).

## Install
1. Copy `sale_quick_flow/` into an addons path, restart Odoo.
2. Apps -> Update Apps List -> install (or upgrade with `-u sale_quick_flow`).
3. Assign the "Quick Sales Flow" group to users.

## Rules
* Insufficient stock => error listing the products; order stays a quotation.
* Lot/serial-tracked products must be validated manually.
* Standard `action_confirm` is unchanged for website/API/automations.
