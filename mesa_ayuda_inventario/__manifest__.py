# -*- coding: utf-8 -*-
# Copyright 2026 Supplies De Colombia SAS
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
{
    'name': 'Mesa de Ayuda - Inventario de Clientes',
    'summary': 'Consulta y gestión de productos principales en inventario de clientes por número de serie',
    'description': '''
        Módulo para Mesa de Ayuda que permite a los técnicos:
        - Consultar inventario de clientes por número de serie
        - Ver solo productos principales (no componentes/periféricos/complementos)
        - Realizar modificaciones con trazabilidad completa
        - Registrar quién realiza cada modificación
    ''',
    'author': 'Supplies De Colombia SAS',
    'category': 'Inventory/Helpdesk',
    'version': '19.0.1.0.34',
    'depends': [
        'stock',
        'product_suppiles',
        'product_suppiles_partner',
        # Licencias por equipo/usuario (license.equipment, pestañas en stock.lot)
        'subscription_licenses',
        'mail',
        'web',
        'sign',  # Módulo que contiene el widget signature
        'helpdesk',  # ✅ Módulo nativo - Para integrar tickets
        'repair',  # ✅ Módulo nativo - Para reparaciones
        'sale_subscription',  # Para extender lista de precios recurrentes del cliente
        'calendar',  # ✅ Para calendario de visitas y mantenimientos programados
        'account',  # Para account.analytic.line (líneas de hoja de horas / timer)
        'hr_timesheet',  # Proporciona action_timer_stop en account.analytic.line (timer en tickets)
        # Módulos nativos opcionales (recomendados instalar):
        # 'knowledge', # Para base de conocimiento
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/maintenance_order_sequence.xml',
        'data/cron_attachment_cleanup.xml',  # ✅ Cron job para limpiar attachments temporales
        # TEMPORALMENTE DESACTIVADO:
        # 'data/sequences.xml',
        'views/stock_lot_maintenance_views.xml',
        'views/customer_inventory_views.xml',
        'views/stock_lot_form_views.xml',
        'views/component_change_views.xml',  # ✅ Vistas para cambios de componentes
        'views/maintenance_order_views.xml',
        'views/maintenance_order_calendar_views.xml',  # ✅ Vista de calendario para visitas
        'views/maintenance_order_wizard_views.xml',
        'views/add_equipment_wizard_tree_views.xml',
        'views/add_equipment_wizard_views.xml',
        'views/add_equipment_wizard_search_views.xml',
        'wizard/equipment_change_wizard_views.xml',  # ✅ Wizard para cambio de equipo
        'wizard/request_element_wizard_views.xml',  # ✅ Wizard para solicitar elemento/componente
        'wizard/activity_assignment_wizard_views.xml',  # ✅ Wizard para asignar actividades
        'wizard/escalate_ticket_wizard_views.xml',  # Escalar ticket a otro equipo/responsable
        'wizard/customer_query_wizard_views.xml',
        'wizard/service_order_solicitudes_wizard_views.xml',
        'wizard/service_order_retiro_usuario_equipo_wizard_views.xml',
        'views/alertas_renting_views.xml',  # Alertas > Equipos a terminar Renting (por fecha finalización)
        'views/helpdesk_ticket_category_views.xml',
        'views/helpdesk_ticket_views.xml',  # ✅ Activado - Vistas y acción de tickets
        'views/helpdesk_ticket_template_views.xml',
        'views/helpdesk_timer_pause_request_views.xml',
        'views/helpdesk_ticket_pause_request_views.xml',
        'views/repair_order_views.xml',  # ✅ Activado - Vistas de reparaciones
        'views/pricelist_admin_supplies_views.xml',
        'views/menuitems.xml',  # ✅ Cargar menús antes de debug_log_views
        'views/debug_log_views.xml',  # ✅ Herramienta de debug (después de menuitems para que el menú padre exista)
        'reports/stock_lot_life_sheet_report.xml',
        'reports/stock_lot_maintenance_report.xml',
        'reports/maintenance_order_report.xml',  # ✅ Reporte de orden completa
    ],
    'assets': {
        'web.assets_backend': [
            'mesa_ayuda_inventario/static/src/css/customer_inventory.css',
            'mesa_ayuda_inventario/static/src/js/view_switcher.js',
        ],
    },
    'application': True,
    'license': 'LGPL-3',
    'installable': True,
}

