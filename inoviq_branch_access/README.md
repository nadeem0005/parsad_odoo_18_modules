# Inoviq Branch Access (Odoo 18)
Developed by Inoviq Systems.

## Install
Unzip into `addons_path`, restart Odoo, Apps > Update Apps List, install "Inoviq Branch Access".

## Create a branch user
1. Settings > Users > open/create the user.
2. Tab **Branch Access**: pick the warehouse(s).
3. Tab **Access Rights**: set **Inoviq Branch = Branch User (Own Warehouse Only)**.
   Do NOT give Purchase, Accounting/Invoicing, Administration or any Manager group.
4. Save. (Ask the user to log out/in once.)

## What a Branch User gets
* Inventory (user level) + Sales (all documents) - nothing else.
* Stock, moves, moves history, forecast, reorder rules, scrap: own warehouse only.
* Transfers: can create/edit only with an operation type of own warehouse; destination can be any location.
  Incoming transfers addressed to the warehouse are visible (read only).
* Sales orders / lines / sales analysis: own warehouse only; default warehouse = first allowed warehouse.
* Inventory > Reporting is visible (Stock, Locations, Moves History, Moves Analysis) - own warehouse data only.
* Hidden menus: Receipts, Deliveries, Internal, Physical Inventory, Overview, Inventory > Products,
  Sales > Products, Sales > To Invoice. Visible: Warehouse Transfers (your custom module) and Scrap.
* Side panels such as 'Warehouses' in Reporting > Stock list only the user's own warehouse(s).
* Other warehouses are not visible at all (warehouse list, side panels, filters). Locations stay visible as transfer destinations.
* Product pages cannot be opened (a notice is shown instead); the stock-adjustment pencil and Update Quantity are blocked.
* The user must log out and in again after being added to the group.
* Inventory adjustments (counting and applying) are blocked for Branch Users even by direct link.
* Scrap defaults to the user's own warehouse stock location.
* To change the hidden/shown menu lists edit `BRANCH_HIDDEN_MENUS` / `BRANCH_SHOWN_MENUS` in `models/ir_ui_menu.py`.
* No Settings / Apps / Purchase / Invoicing menus (these need other groups, which are not granted).

## Test checklist
* Branch user: Inventory > Reporting > Stock shows only own warehouse.
* Moves History shows only own moves.
* Product form On Hand shows only own warehouse quantity.
* Create internal transfer with own operation type to a BR/HO location: works.
* Create a transfer with another warehouse operation type: refused.
* Create a sales order: warehouse is the own one; selecting another is refused.
* Normal admin users are not affected.
