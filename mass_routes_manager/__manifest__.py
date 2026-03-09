{
    'name': 'Gestión Masiva de Rutas',
    'version': '19.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': 'Aplicar rutas masivamente a múltiples productos',
    'description': """
        Gestión Masiva de Rutas de Productos
        =====================================
        
        Este módulo permite aplicar rutas a múltiples productos simultáneamente:
        
        Características:
        ----------------
        * Seleccionar/Deseleccionar rutas en múltiples productos a la vez
        * Aplicar a todos los productos del sistema
        * Aplicar solo a productos seleccionados
        * Acciones desde el menú "Acción" en la vista de lista
        
        Uso:
        ----
        1. Ve a Inventario → Productos
        2. Selecciona los productos deseados (o ninguno para aplicar a todos)
        3. Click en "Acción" → Elegir opción de rutas
    """,
    'author': 'Ricardo',
    'depends': ['stock'],
    'data': [
        'views/product_template_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
    'pre_init_hook': 'pre_init_hook',
}