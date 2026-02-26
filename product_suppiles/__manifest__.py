# -*- coding: utf-8 -*-
{
    'name': "Product Supplies",
    'summary': "Product Supplies",
    'description': '''
        Caracteristicas:
        - Componentes en productos
    ''',
    'author': 'Supplies De Colombia SAS',
    'contributors': ['Supplies De Colombia SAS'],
    'website': 'https://www.supplies.com',
    'license': 'LGPL-3',
    'category': 'Inventory/Inventory',
    'version': '19.0.0.0.2',
    'installable': True,
    'depends': [
        'purchase',
        'stock',
        'stock_account',
        'purchase_stock',
        'sale_stock', 
        'product',
        'uom',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/asset_category_views.xml',
        'views/product_views.xml',
        'views/purchase_views.xml',
        'wizard/wizard_views.xml',
        'wizard/lot_supply_editor_wizard_views.xml',
        'views/sale_views.xml',
        'views/stock_lot_form_supplies_inherit.xml',
        'views/stock_lot_views.xml',
        'views/stock_picking_views.xml',
        'views/menuitems.xml',

    ],
    'assets': {
        'web.assets_backend': [
            'product_suppiles/static/src/css/stock_lot_associated_info.css',
            'product_suppiles/static/src/css/stock_lot_form_pastel.css',
            'product_suppiles/static/src/css/stock_picking_header_pastel.css',
            'product_suppiles/static/src/js/stock_lot_associated_info.js',
        ],
    },
    'post_init_hook': 'post_init_hook',
}
