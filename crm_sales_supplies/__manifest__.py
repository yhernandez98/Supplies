# -*- coding: utf-8 -*-
# Copyright 2026 Supplies De Colombia SAS
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).

{
    'name': 'CRM Sales Supplies Integration',
    'version': '19.0.1.0.25',
    'author': 'Supplies De Colombia SAS',
    'category': 'Sales/CRM',
    'depends': [
        'crm',
        'sale',
        'purchase',
        'stock',
        'purchase_stock',
        'sale_stock',
        'sale_purchase',  # Para que nuestro has_sale_order y _compute_has_sale_order tengan prioridad (evita error NewId en onchange)
        'product_suppiles',
        'subscription_nocount',
        'custom_u',  # Requerido para el campo tipo_contacto
    ],
    'data': [
        'data/purchase_alert_data.xml',
        'data/leasing_data.xml',
        'security/ir.model.access.csv',
        'views/purchase_alert_views.xml',
        'views/crm_lead_views.xml',
        'views/crm_lead_solution_quote_views.xml',
        'views/crm_solution_quote_views.xml',
        'views/sale_order_solution_quote_views.xml',
        'views/sale_order_views.xml',
        'views/purchase_order_views.xml',
        'views/product_views.xml',
        'views/leasing_brand_views.xml',
        'views/leasing_contract_template_views.xml',
        'reports/leasing_contract_report.xml',
        'views/leasing_contract_views.xml',
        'views/stock_picking_views.xml',
        'wizard/purchase_quotation_wizard_views.xml',
        'wizard/crm_lead_purchase_alert_wizard_views.xml',
        'wizard/purchase_alert_validation_wizard_views.xml',
        'wizard/sale_order_request_quotation_wizard_views.xml',
        'wizard/purchase_alert_manual_quotation_wizard_views.xml',
        'wizard/leasing_contract_wizard_views.xml',
        'wizard/crm_solution_quote_wizard_views.xml',
        'views/menuitems.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
    'post_init_hook': 'post_init_hook',
    'assets': {
        'web.assets_backend': [
            'crm_sales_supplies/static/src/css/inventory_style.css',
            'crm_sales_supplies/static/src/js/inventory_view.js',
            'crm_sales_su