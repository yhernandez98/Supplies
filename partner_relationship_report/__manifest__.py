# -*- coding: utf-8 -*-
{
    'name': "Report Relationship Product Supplies",
    'summary': "Report Relationship Product",
    'description': '''
        Caracteristicas:
        - Reporte de relaciones de contacto con productos y seriales
    ''',
    'author': 'Supplies De Colombia SAS',
    'contributors': ['Sebastian Cogollo, correocogollo@gmail.com'],
    'website': 'https://www.supplies.com',
    'license': 'LGPL-3',
    'category': 'Contacts',
    'version': '19.0.0.0.1',
    'depends': ['base', 'contacts', 'stock', 'report_xlsx'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/partner_relationship_wizard.xml',
        'report/partner_relationship_report_templates.xml',
        'report/partner_relationship_report_action.xml',
        'views/partner_relationship_menu.xml',

    ],
    'application': False,
    'installable': True,
    'auto_install': False,
}
