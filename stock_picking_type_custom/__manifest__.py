# -*- coding: utf-8 -*-
{
    'name': 'Personalización de Tipos de Operación de Stock',
    'version': '18.0.1.0.0',
    'category': 'Warehouse',
    'summary': 'Personaliza los nombres de los tipos de operación de entrega',
    'description': """
Módulo de Personalización de Tipos de Operación de Stock
=========================================================

Este módulo personaliza los nombres de los tipos de operación de entrega (outgoing)
para que incluyan "Órdenes de entrega" seguido del nombre del almacén.

Características:
---------------
* Actualiza automáticamente el nombre de las operaciones de tipo "outgoing"
* Formato: "Órdenes de entrega + [Nombre del Almacén]"
* Actualización masiva de tipos de operación existentes
* Actualización automática al crear nuevos tipos de operación
    """,
    'author': 'Supplies De Colombia SAS',
    'website': 'https://www.suppliesdecolombia.com',
    'depends': [
        'base',
        'stock',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/stock_picking_type_views.xml',
        'views/stock_picking_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
    'post_init_hook': 'post_init_hook',
}

