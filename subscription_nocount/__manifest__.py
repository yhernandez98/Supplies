{
    'name': 'Subscription No Accounting',
    'version': '19.0.1.0.6',
    'author': 'Supplies De Colombia SAS',
    'category': 'Sales/Subscriptions',
    'depends': ['mail', 'sale_subscription', 'stock', 'account', 'product_suppiles'],
    'assets': {
        'web.assets_backend': [
            'subscription_nocount/static/src/css/subscription_statusbar.css',
            'subscription_nocount/static/src/css/subscription_form_pastel.css',
        ],
    },
    'data': [
        'data/subscription_models.xml',
        'security/ir.model.access.csv',
        'data/subscription_journal.xml',
        'data/subscription_cron.xml',
        'views/subscription_dashboard_templates.xml',
        'views/subscription_views.xml',
        'views/product_views.xml',
        # Odoo 19: vista de sale.subscription.pricing desactivada (modelo no existe en registro).
        # 'views/pricelist_views.xml',
    ],
    'application': True,
    'license': 'LGPL-3',
    'installable': True,
    'post_init_hook': 'post_init_hook',
}
