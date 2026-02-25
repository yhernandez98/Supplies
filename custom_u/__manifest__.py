# -*- coding: utf-8 -*-
{
    'name': 'Módulo Unificado Personalizado',
    'version': '18.0.3.1',
    'summary': 'Módulo unificado completo con gestión de contactos, productos, productos serializados y reportes',
    'description': """
        Módulo unificado para Odoo 18.0 que combina todas las funcionalidades personalizadas:
        
        ========================================
        FUNCIONALIDADES DE CONTACTOS
        ========================================
        - Campo tipo_contacto: Proveedor, Cliente, Proveedor y Cliente
        - Integración automática con customer_rank y supplier_rank
        - Validaciones y constraints robustos
        - Interfaz mejorada con estilos personalizados
        
        ========================================
        FUNCIONALIDADES DE PRODUCTOS
        ========================================
        - Campo tipo_producto con opciones en español
        - Sincronización bidireccional con campo nativo 'type'
        - Herramientas de utilidad para sincronización masiva
        - Validaciones de consistencia de datos
        
        ========================================
        FUNCIONALIDADES DE CREACIÓN AUTOMÁTICA
        ========================================
        - Creación automática de contactos individuales para empresas
        - Plantillas personalizables para nombres y emails
        - Generación inteligente de emails con variables
        - Validaciones robustas y creación optimizada
        
        ========================================
        CARACTERÍSTICAS TÉCNICAS
        ========================================
        - Compatibilidad completa con Odoo 18.0
        - Sincronización automática entre campos nativos y personalizados
        - Interfaz unificada y consistente
        - Validaciones robustas para integridad de datos
        - Herramientas de utilidad para mantenimiento
        - Documentación completa y ejemplos de uso
    """,
    'author': 'Felipe Valbuena',
    'category': 'Productivity/Productivity',
    'depends': [
        'base',
        'contacts', 
        'product',
        'stock',
        'product_suppiles_partner',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/res_partner_views.xml',
        'views/product_template_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'custom_u/static/src/css/radio_styles.css',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
    'external_dependencies': {
        'python': [],
    },
}
