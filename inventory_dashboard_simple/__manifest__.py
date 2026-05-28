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
    'version': '19.0.0.0.99',
    'depends': [
        'stock',
        'product_suppiles',  # Para usar el campo inventory_plate en stock.lot y mover productos relacionados
        'mesa_ayuda_inventario',  # Para acceso a inventario de clientes
        'subscription_nocount',  # Servicio / Suscripción en stock.lot (pending info + badge)
    ],
    'assets': {
        'web.assets_backend': [
            'inventory_dashboard_simple/static/src/css/dashboard_kanban.css',
            'inventory_dashboard_simple/static/src/css/lab_hub_theme.css',
            'inventory_dashboard_simple/static/src/js/inventory_lab_hub_theme.js',
            'inventory_dashboard_simple/static/src/css/stock_lot_pending_info_menu_badge.css',
            'inventory_dashboard_simple/static/src/js/stock_lot_pending_info_menu_badge.js',
        ],
    },
    'data': [
        'security/ir.model.access.csv',
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
        'views/delivery_route_billing_views.xml',
        'wizard/component_transfer_wizard_views.xml',
        'views/component_lab_pending_views.xml',
        'views/compon