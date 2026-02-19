<<<<<<< HEAD
{
    'name': 'Subscription Licenses',
    'version': '18.0.1.0.1',
    'author': 'Supplies De Colombia SAS',
    'category': 'Sales/Subscriptions',
    'depends': ['sale', 'stock', 'account', 'product', 'base', 'web', 'product_suppiles', 'subscription_nocount'],
    'external_dependencies': {'python': ['openpyxl']},
    'assets': {
        'web.assets_backend': [
            'subscription_licenses/static/src/css/list_group_visible.css',
            'subscription_licenses/static/src/css/subscription_licenses_theme.css',
            'subscription_licenses/static/src/js/subscription_licenses_theme.js',
        ],
    },
    'data': [
        'data/license_cron.xml',
        'views/license_category_views.xml',  # Cargar vistas básicas primero
        'views/license_provider_views.xml',  # Paso 1: Vistas del modelo básico (sin res_partner)
        'views/license_provider_partners_views.xml',  # Menú Proveedores (contactos con is_license_provider)
        'security/ir.model.access.csv',  # CSV después de que el modelo esté registrado
        'views/license_category_views.xml',
        'views/trm_views.xml',
        'views/exchange_rate_monthly_views.xml',
        'views/product_license_type_views.xml',
        'views/license_equipment_views.xml',
        'wizard/license_equipment_add_multiple_wizard_views.xml',
        'wizard/license_add_multiple_warning_wizard_views.xml',
        'wizard/license_equipment_delete_warning_wizard_views.xml',
        'wizard/license_quantity_warning_wizard_views.xml',
        'views/license_assignment_views.xml',
        'views/license_views.xml',
        'views/license_dashboard_templates.xml',
        'views/license_provider_delete_wizard_views.xml',  # Wizard de confirmación para eliminar proveedores
        # 'views/res_partner_views.xml',  # DESACTIVADO - se agregó en custom_u en su lugar
        'views/license_report_wizard_views.xml',
        'views/res_config_settings_views.xml',
        'views/subscription_views.xml',
        'views/stock_lot_views.xml',
        'reports/license_reports.xml',
        'reports/license_report_templates.xml',
        'views/menuitems.xml',
    ],
    'application': True,
    'license': 'LGPL-3',
    'installable': True,
    'pre_init_hook': 'pre_init_hook',
    'post_init_hook': 'post_init_hook',
}

=======
{
    'name': 'Subscription Licenses',
    'version': '18.0.1.0.1',
    'author': 'Supplies de Colombia',
    'category': 'Sales/Subscriptions',
    'depends': ['sale', 'stock', 'account', 'product', 'base', 'web', 'product_suppiles', 'subscription_nocount'],
    'external_dependencies': {'python': ['openpyxl']},
    'assets': {
        'web.assets_backend': [
            'subscription_licenses/static/src/css/list_group_visible.css',
            'subscription_licenses/static/src/css/subscription_licenses_theme.css',
            'subscription_licenses/static/src/js/subscription_licenses_theme.js',
        ],
    },
    'data': [
        'data/license_cron.xml',
        'views/license_category_views.xml',  # Cargar vistas básicas primero
        'views/license_provider_views.xml',  # Paso 1: Vistas del modelo básico (sin res_partner)
        'views/license_provider_partners_views.xml',  # Menú Proveedores (contactos con is_license_provider)
        'security/ir.model.access.csv',  # CSV después de que el modelo esté registrado
        'views/license_category_views.xml',
        'views/trm_views.xml',
        'views/exchange_rate_monthly_views.xml',
        'views/product_license_type_views.xml',
        'views/license_equipment_views.xml',
        'wizard/license_equipment_add_multiple_wizard_views.xml',
        'wizard/license_add_multiple_warning_wizard_views.xml',
        'wizard/license_equipment_delete_warning_wizard_views.xml',
        'wizard/license_quantity_warning_wizard_views.xml',
        'views/license_assignment_views.xml',
        'views/license_views.xml',
        'views/license_dashboard_templates.xml',
        'views/license_provider_delete_wizard_views.xml',  # Wizard de confirmación para eliminar proveedores
        # 'views/res_partner_views.xml',  # DESACTIVADO - se agregó en custom_u en su lugar
        'views/license_report_wizard_views.xml',
        'views/res_config_settings_views.xml',
        'views/subscription_views.xml',
        'views/stock_lot_views.xml',
        'reports/license_reports.xml',
        'reports/license_report_templates.xml',
        'views/menuitems.xml',
    ],
    'application': True,
    'license': 'LGPL-3',
    'installable': True,
    'icon': 'static/description/icon.png',
    'pre_init_hook': 'pre_init_hook',
    'post_init_hook': 'post_init_hook',
}

>>>>>>> e11752a4d811d6d401b34ac0a1c14ff2e732e782
