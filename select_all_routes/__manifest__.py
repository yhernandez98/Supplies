# __manifest__.py
{
    'name': 'Select All Routes',
    'summary': 'Adds buttons to quickly select and deselect all available stock routes on a product.',
    'version': '18.0.1.0.0',
    'category': 'Inventory/Stock',
    'author': 'Supplies De Colombia SAS',
    'license': 'AGPL-3',
    'depends': [
        'product', 
        'stock',
    ],
    'data': [
        # La vista XML es crucial para que Odoo muestre los botones
        'views/product_template_views.xml',
    ],
    'installable': True,
    'application': False,
}