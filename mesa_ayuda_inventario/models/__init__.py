# -*- coding: utf-8 -*-

from . import ir_actions_act_window
from . import customer_inventory_lot
from . import res_partner
from . import stock_lot_maintenance
from . import maintenance_order
from . import debug_log  # ✅ Herramienta de debug
<<<<<<< HEAD
=======
from . import helpdesk_ticket_category
from . import helpdesk_ticket_template
>>>>>>> fb2d0eddb44261c7833d37e32b0869ec9bdb22c2
from . import helpdesk_ticket  # ✅ Extendiendo módulo nativo helpdesk.ticket
from . import repair_order  # ✅ Extendiendo módulo nativo repair.order
# TEMPORALMENTE DESACTIVADO:
from . import component_change  # ✅ Activado - Punto 3: Registro Cambios Componentes
<<<<<<< HEAD
from . import maintenance_dashboard  # ✅ Activado - Punto 4: Dashboard con Métricas
from . import stock_quant  # ✅ Extender stock.quant para actualizar customer_info
from . import customer_own_inventory  # ✅ Inventario propio de clientes
from . import customer_own_inventory_line  # ✅ Líneas asociados (componentes/periféricos/complementos)
from . import attachment_cleanup  # ✅ Limpieza automática de attachments temporales
=======
from . import stock_quant  # ✅ Extender stock.quant para actualizar customer_info
from . import attachment_cleanup  # ✅ Limpieza automática de attachments temporales
from . import account_analytic_line  # ✅ Timer: tiempo real al detener; pausa con autorización
from . import helpdesk_timer_pause_request  # ✅ Solicitud de pausa (timer Odoo / líneas)
from . import helpdesk_ticket_pause_request  # ✅ Solicitud de pausa cronómetro propio (tickets)
>>>>>>> fb2d0eddb44261c7833d37e32b0869ec9bdb22c2

