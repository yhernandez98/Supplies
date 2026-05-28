# -*- coding: utf-8 -*-
# Copyright 2026 Supplies De Colombia SAS
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).

{
    'name': 'Integración CRM – Compras – Calculadora',
    'version': '19.0.1.0.1',
    'author': 'Supplies De Colombia SAS',
    'category': 'Sales/CRM',
    'summary': 'Orquesta cotización ganadora, calculadora de costos, propuesta al cliente y ruteo stock/compra',
    'depends': [
        'crm_sales_supplies',
        'calculadora_costos',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/sequences.xml',
        'views/commercial_integration_case_views.xml',
        'views/commercial_customer_proposal_views.xml',
        'views/calculadora_costos_views.xml',
        'views/purchase_order_views.xml',
        'views/purchase_alert_views.xml',
        'views/crm_lead_views.xml',
        'views/sale_order_views.xml',
        'views/res_config_settings_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
