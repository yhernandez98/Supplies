# -*- coding: utf-8 -*-
{
    'name': 'Debug lista de precios (contacto)',
    'version': '19.0.1.0.2',
    'summary': 'Botón en contacto para diagnosticar property_product_pricelist (ORM, ir.property, por compañía).',
    'author': 'Supplies De Colombia SAS',
    'category': 'Technical',
    'depends': ['sale', 'contacts'],
    'data': [
        'security/ir.model.access.csv',
        'views/partner_pricelist_debug_wizard_views.xml',
        'views/res_partner_views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
