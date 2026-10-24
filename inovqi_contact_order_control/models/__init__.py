# Order matters: the mixin must be loaded before the models that inherit it.
from . import price_violation_log
from . import price_protection_mixin
from . import res_partner
from . import sale_order
from . import sale_order_line
from . import sale_advance_payment_inv
from . import purchase_order
from . import purchase_order_line
