{
    'name': 'Calculadora de Costos y Renting',
    'version': '18.0.1.0.0',
    'author': 'Supplies de Colombia',
    'category': 'Sales/Finance',
    'summary': 'Calculadora financiera para costeo de equipos, renting y servicios técnicos',
    'description': """
Calculadora de Costos y Renting
================================

Este módulo proporciona una calculadora unificada para:

* Costeo de equipos portátiles e informáticos
* Cálculo de opciones de renting/leasing
* Proyecciones de flujos de caja mensuales
* Cálculos financieros (tasas de interés, pagos periódicos, opciones de compra)

Características:
---------------
* Calculadora unificada para equipos y renting
* Cálculo automático de costos en USD y COP
* Conversión de moneda usando TRM
* Cálculo de tasas de interés (nominal, mensual, efectiva anual)
* Cálculo de pagos mensuales con función PMT
* Comparación de plazos (24, 36, 48 meses) para renting
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
        'data/parametros_financieros_data.xml',
        'views/parametros_financieros_views.xml',
        'reports/calculadora_report.xml',
        'views/calculadora_views.xml',
        'views/menu.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
