{
    'name': 'Calculadora de Costos y Renting',
    'version': '19.0.4.0.0',
    'author': 'Felipe Valbuena',
    'category': 'Sales/Finance',
    'summary': 'Calculadora financiera para costeo de equipos, renting y servicios técnicos',
    'description': """
Calculadora de Costos y Renting
================================

Este módulo proporciona una calculadora unificada para:

* Costeo de equipos portátiles e informáticos
* Cálculo de opciones de renting/leasing
* Proyecciones de flujos de caja mensuales
* Cálculos financieros (tasas de interés, pagos periódicos PMT)

Características:
---------------
* Calculadora unificada para equipos y renting
* Cálculo automático de costos en USD y COP
* Conversión de moneda usando TRM
* Cálculo de tasas de interés (nominal, mensual, efectiva anual)
* Cálculo de pagos mensuales con función PMT
* Comparación de plazos (12 a 60 meses) para suscripción
* Integración con suscripciones no contables
* Integración con módulos de Odoo (Productos, Ventas, CRM)
    """,
    'depends': [
        'base',
        'product',
        'sale',
    ],
    'external_dependencies': {
        'python': [],
    },
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'reports/calculadora_report.xml',
        'views/calculadora_views.xml',
        'views/menu.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'icon': 'static/description/calculadora.png',
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
