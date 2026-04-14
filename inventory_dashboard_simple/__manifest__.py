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
    'version': '19.0.0.0.50',
    'depends': [
        'stock',
        'product_suppiles',  # Para usar el campo inventory_plate en stock.lot y mover productos relacionados
        'mesa_ayuda_inventario',  # Para acceso a inventario de clientes
    ],
    'assets': {
        'web.assets_backend': [
            'inventory_dashboard_simple/static/src/css/dashboard_kanban.css',
            'inventory_dashboard_simple/static/src/css/lab_hub_theme.css',
            'inventory_dashboard_simple/static/src/js/inventory_lab_hub_theme.js',
        ],
    },
    'data': [
        'security/ir.model.access.csv',
        'data/component_lab_acta_sequence.xml',
        'views/internal_reference_views.xml',
        'views/stock_lot_views.xml',
        'views/stock_quant_views.xml',
        'wizard/delivery_route_trigger_wizard_views.xml',
        'wizard/component_transfer_wizard_views.xml',
        'views/component_lab_pending_views.xml',
        'views/component_lab_pool_views.xml',
        'views/component_lab_hub_dashboard_templates.xml',
        'reports/component_lab_assignment_report.xml',
        'reports/component_lab_acta_report.xml',
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

