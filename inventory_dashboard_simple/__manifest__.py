# -*- coding: utf-8 -*-
# Copyright 2026 Supplies De Colombia SAS
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
{
    'name': "Dashboard de Inventario Simplificado",
    'summary': "Vista mejorada del dashboard de inventario agrupando operaciones por tipo",
    'description': '''
        Este módulo mejora el dashboard de inventario agrupando las operaciones por tipo
        (Recibidos, Traslados, Órdenes de entrega, etc.) en lugar de por cliente/empresa,
        facilitando la navegación para el personal de inventario.
    ''',
    'author': 'Supplies De Colombia SAS',
    'category': 'Inventory/Inventory',
    'version': '19.0.0.0.220',
    'depends': [
        'stock',
        'product_suppiles',  # Para usar el campo inventory_plate en stock.lot y mover productos relacionados
        'product_suppiles_partner',  # Usuario en serial + herencia vista E1
        'mesa_ayuda_inventario',  # Para acceso a inventario de clientes
        'subscription_nocount',  # Servicio / Suscripción en stock.lot (pending info + badge)
    ],
    'assets': {
        'web.assets_backend': [
            'inventory_dashboard_simple/static/src/css/dashboard_kanban.css',
            'inventory_dashboard_simple/static/src/css/lab_hub_theme.css',
            'inventory_dashboard_simple/static/src/css/delivery_route_wizard_theme.css',
            'inventory_dashboard_simple/static/src/js/delivery_route_wizard_theme.js',
            'inventory_dashboard_simple/static/src/js/delivery_route_m2o_no_search_more.js',
            'inventory_dashboard_simple/static/src/js/inventory_lab_hub_theme.js',
            'inventory_dashboard_simple/static/src/css/stock_lot_pending_info_menu_badge.css',
            'inventory_dashboard_simple/static/src/js/stock_lot_pending_info_menu_badge.js',
            'inventory_dashboard_simple/static/src/css/return_e4_picking_views.css',
            'inventory_dashboard_simple/static/src/css/return_e4_ticket_views.css',
        ],
    },
    'data': [
        'security/ir.model.access.csv',
        'data/helpdesk_ticket_category_e4_dictamen.xml',
        'data/component_lab_acta_sequence.xml',
        'data/supplies_assignment_sequence.xml',
        'data/supplies_reassignment_sequence.xml',
        'views/internal_reference_views.xml',
        'views/stock_lot_views.xml',
        'views/stock_lot_serial_conflict_views.xml',
        'views/stock_quant_views.xml',
        'views/supplies_assignment_views.xml',
        'views/supplies_hub_dashboard_templates.xml',
        'wizard/delivery_route_trigger_wizard_views.xml',
        'wizard/delivery_route_validation_wizard_views.xml',
        'wizard/return_route_e4_classification_wizard_views.xml',
        'views/helpdesk_team_views.xml',
        'views/helpdesk_ticket_return_e4_views.xml',
        'wizard/helpdesk_ticket_return_e4_item_informe_wizard_views.xml',
        'views/stock_picking_return_e4_views.xml',
        'reports/helpdesk_ticket_return_e4_verification_report.xml',
        'views/delivery_route_picking_views.xml',
        'views/delivery_route_billing_views.xml',
        'views/stock_lot_delivery_route_fields_views.xml',
        'wizard/component_transfer_wizard_views.xml',
        'views/component_lab_pending_views.xml',
        'views/component_lab_pool_views.xml',
        'views/component_lab_hub_dashboard_templates.xml',
        'reports/component_lab_assignment_report.xml',
        'reports/component_lab_acta_report.xml',
        'reports/supplies_assignment_report.xml',
        'views/stock_picking_supplies_lab_inherit.xml',
        'wizard/quant_editor_wizard_views.xml',
        'views/inventory_dashboard_views.xml',
        'views/product_relation_search_views.xml',
        'views/menuitems.xml',
    ],
    'pre_init_hook': 'pre_init_hook',
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}

