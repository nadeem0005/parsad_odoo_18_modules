# Stock Ledger - Opening & Closing on Moves History (Odoo 18)
Developed by Inoviq Systems.

## Install
1. Unzip into a folder that is in `addons_path`.
2. Restart Odoo, Apps > Update Apps List.
3. Install "Stock Ledger - Opening & Closing on Moves History".

## Result
Inventory > Reporting > Moves History (and the product's Moves History) get the columns:
Warehouse | Opening Qty | In | Out | Closing Qty

* Calculated per product and per warehouse in date order.
* Only Done moves. Moves inside one warehouse (Stock -> Shelf) are ignored.
* Transit: sending WH -> transit shows as Out of WH; transit -> BR1 shows as In to BR1.
* Columns can be hidden from the optional-columns toggle at the right of the list header.
* Totals of In and Out are shown at the bottom. Opening/Closing are balances so they are not summed.
