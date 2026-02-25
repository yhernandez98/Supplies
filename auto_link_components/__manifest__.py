{
    'name': 'Product Supplies Auto Relations',
    'version': '19.0.1.0.0',
    'author': 'Supplies De Colombia SAS',
    'category': 'Inventory',
    'summary': 'Automatiza la creación de relaciones entre componentes basándose en el número de lote',
    'description': """
        Este módulo extiende product_supplies para:
        - Crear automáticamente relaciones entre productos compuestos y sus componentes
        - Vincular componentes que compartan el mismo número de lote
        - Funcionar en recepciones de compra
    """,
    'depends': ['product_suppiles', 'stock', 'purchase'],
    'data': [
        'views/stock_picking_views.xml',
        'views/stock_lot_tree_view.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}