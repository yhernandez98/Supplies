# -*- coding: utf-8 -*-
{
    'name': 'DIAN NIT Colombia',
    'version': '19.0.1.0.0',
    'author': 'Felipe Valbuena',
    'website': 'https://www.example.com',
    'category': 'Localization/Colombia',
    'summary': 'Gestion completa de NIT colombiano con algoritmo DIAN para facturacion',
    'description': '''
        Modulo especializado para gestion de NIT colombiano con:
        - Algoritmo oficial de digito de verificacion DIAN
        - Sincronizacion automatica con campo VAT para facturacion
        - Validaciones robustas segun normativas colombianas
        - Campos adicionales para reportes DIAN
        - Interfaz optimizada para facturacion electronica
        - Integracion completa con modulos de contabilidad
        
        Caracteristicas principales:
        - Calculo automatico de digito de verificacion
        - Validacion cruzada NIT-DV segun algoritmo DIAN
        - Sincronizacion automatica con campo VAT
        - Campos para regimen tributario y codigo de responsabilidad
        - Interfaz de usuario intuitiva y profesional
        - Compatible con facturacion electronica colombiana
    ''',
    'depends': [
        'base',
        'contacts',
        'account',  # Para integracion con facturacion
        'l10n_latam_base',  # Para funcionalidad NIT latinoamericano
        'l10n_co',  # Para localizacion colombiana
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/res_partner_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'dian_nit_colombia/static/src/css/dian_styles.css',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
    'auto_install': False,
    'sequence': 100,
}

