# -*- coding: utf-8 -*-
{
    'name': 'Gestor Fácil de Permisos',
    'version': '19.0.1.0.0',
    'category': 'Tools',
    'summary': 'Gestión simplificada de permisos y roles de usuarios',
    'description': """
        Módulo para gestionar permisos de usuarios de forma más simple y visual.
        
        Características:
        - Vista de usuarios y sus permisos por módulo
        - Roles predefinidos (Solo Lectura, Sin Acceso, etc.)
        - Wizard para asignar permisos rápidamente
        - Vista de módulos y modelos disponibles
    """,
    'author': 'Supplies de Colombia',
    'website': '',
    'depends': ['base', 'stock', 'purchase', 'sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/permission_manager_views.xml',
        'views/permission_views.xml',
        'views/menuitems.xml',
        'data/permission_roles_data.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
