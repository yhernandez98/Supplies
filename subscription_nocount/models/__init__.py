from . import subscription
from . import subscription_monthly_billable
from . import account_move
from . import account_move_line
from . import subscription_wizard
from . import product_template
from . import equipment_change_history
from . import equipment_change_wizard
from . import stock_lot
from . import stock_quant
from . import ir_ui_menu
# Odoo 19: sale.subscription.pricing no existe en el registro (modelo renombrado/restructurado).
# No cargar subscription_pricing para evitar TypeError al registrar. Reactivar cuando el modelo exista.
# from . import subscription_pricing