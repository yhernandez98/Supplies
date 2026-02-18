# -*- coding: utf-8 -*-
{
    'name': "Dashboard de Inventario Simplificado",
    'summary': "Vista mejorada del dashboard de inventario agrupando operaciones por tipo",
    'description': '''
        Este módulo mejora el dashboard de inventario agrupando las operaciones por tipo
        (Recibidos, Traslados, Órdenes de entrega, etc.) en lugar de por cliente/empresa,
        facilitando la navegación para el personal de inventario.
    ''',
    'author': 'Supplies de Colombia',
    'category': 'Inventory/Inventory',
    'version': '18.0.0.0.2',
    'depends': [
        'stock',
        'product_suppiles',  # Para usar el campo inventory_plate en stock.lot y mover productos relacionados
        'mesa_ayuda_inventario',  # Para acceso a inventario de clientes
    ],
    'assets': {
        'web.assets_backend': [
            'inventory_dashboard_simple/static/src/css/dashboard_kanban.css',
        ],
    },
    'data': [
        'security/ir.model.access.csv',
        'views/internal_reference_views.xml',
        'views/stock_lot_views.xml',
        'views/stock_quant_views.xml',
        'wizard/delivery_route_trigger_wizard_views.xml',
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

