# -*- coding: utf-8 -*-
{
    'name': 'Creación Automática de Almacenes',
    'version': '19.0.1.0.5',
    'category': 'Warehouse',
    'summary': 'Crea automáticamente almacenes desde contactos',
    'description': """
Módulo de Creación Automática de Almacenes
==========================================

Este módulo permite crear automáticamente un almacén (stock.warehouse) 
desde el formulario de contactos (res.partner) cuando el contacto tiene 
el tipo_contacto = "cliente" o "ambos".

Características:
---------------
* Botón "Crear Almacén" visible solo para contactos tipo "cliente"
* Creación automática de almacén con configuración predeterminada
* Validación de duplicados
* Asignación automática de compañía y partner
* Configuración de pasos de recepción y entrega
    """,
    'author': 'Supplies De Colombia SAS',
    'website': 'https://www.suppliesdecolombia.com',
    'depends': [
        'base',
        'contacts',
        'stock',
        'custom_u',  # Requerido para el campo tipo_contacto
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/res_partner_views.xml',
        'wizard/cleanup_routes_wizard_view.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'warehouse_auto_create/static/src/css/warehouse_button.css',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}

