# -*- coding: utf-8 -*-
{
    'name': 'Transferencia de Productos y Seriales',
    'version': '18.0.1.0.0',
    'category': 'Warehouse',
    'summary': 'Transferir unidades y seriales de un producto a otro',
    'description': """
Módulo de Transferencia de Productos y Seriales
================================================

Este módulo permite transferir unidades y seriales/lotes de un producto a otro producto,
creando los ajustes de inventario necesarios.

Características:
---------------
* Transferir unidades de un producto a otro
* Transferir seriales/lotes específicos entre productos
* Crear automáticamente los movimientos de inventario necesarios
* Actualizar los quants de stock
* Mantener el historial de los seriales transferidos
    """,
    'author': 'Felipe Valbuena Para Supplies de Colombia',
    'website': 'https://www.suppliesdecolombia.com',
    'depends': [
        'base',
        'stock',
        'product',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/product_transfer_wizard_views.xml',
        'views/menu_items.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}

