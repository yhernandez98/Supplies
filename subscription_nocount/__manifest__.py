# -*- coding: utf-8 -*-
# Copyright 2026 Supplies De Colombia SAS
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).

{
    'name': 'Subscription No Accounting',
    'version': '19.0.1.0.54',
    'author': 'Supplies De Colombia SAS',
    'category': 'Sales/Subscriptions',
    'depends': ['mail', 'sale_subscription', 'stock', 'account', 'product_suppiles', 'product_suppiles_partner', 'report_xlsx'],
    'assets': {
        'web.assets_backend': [
            'subscription_nocount/static/src/css/subscription_statusbar.css',
            'subscription_nocount/static/src/css/subscription_form_pastel.css',
            'subscription_nocount/static/src/css/subscription_expiring_menu_badge.css',
            'subscription_nocount/static/src/js/subscription_expiring_menu_badge.js',
        ],
    },
    'data': [
        'data/subscription_models.xml',
        'security/ir.model.access.csv',
        'data/subscription_journal.xml',
        'data/subscription_cron.xml',
        'reports/proforma_detailed_report.xml',
        'reports/export_licenses_equipos_report.xml',
        'reports/export_monthly_licenses_equipos_report.xml',
        'views/subscription_dashboard_templates.xml',
        'views/subscription_views.xml',
        'views/product_views.xml',
        'views/pricelist_views.xml',
        'views/stock_lot_form_inherit_subscription_fields.xml',
    ],
    'application': True,
    'license': 'LGPL-3',
    'post_init_hook': 'post_init_hook',
}
