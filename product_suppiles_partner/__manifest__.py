# -*- coding: utf-8 -*-
{
    'name': "Product Supplies Partner",
    'summary': "Relación de productos serializados con contactos",
    'description': '''
        Permite relacionar productos serializados (lotes/series) con contactos.
        Características:
        - Asignar seriales a contactos
        - Ver desde el contacto todos sus productos asignados
        - Ver desde el serial a qué contacto está asignado
        - Relación bidireccional completa
    ''',
    'author': 'Supplies De Colombia SAS',
    'website': 'https://www.supplies.com',
    'license': 'LGPL-3',
    'category': 'Inventory',
    'version': '19.0.1.0.0',
    'depends': [
        'base',
        'stock',
        'product',
        'product_suppiles',
        'report_xlsx',
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizard/partner_supplies_report_wizard.xml',
        'report/partner_supplies_report_templates.xml',
        'report/partner_supplies_report_action.xml',
        'views/res_partner_views.xml',
        'views/stock_lot_views.xml',
        'views/menuitems.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

