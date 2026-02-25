# -*- coding: utf-8 -*-
{
    'name': "Reporte de Lotes y Ubicaciones",
    'summary': "Genera reporte Excel con todos los lotes/series y sus ubicaciones actuales",
    'description': '''
        Características:
        - Reporte de todos los números de serie/lote
        - Ubicaciones actuales de cada lote/serie
        - Exportación a Excel
        - Filtros por ubicación, producto y fechas
        - Información detallada de stock
    ''',
    'author': 'Supplies De Colombia SAS',
    'license': 'LGPL-3',
    'category': 'Inventory/Reports',
    'version': '19.0.0.0.1',
    'depends': [
        'stock',
        'product',
        'base',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/wizard_views.xml',
        'views/menuitems.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}

