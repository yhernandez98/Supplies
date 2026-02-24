# -*- coding: utf-8 -*-
<<<<<<< HEAD

import logging

=======
# Hooks vacíos (inventario propio eliminado; se mantiene el archivo por si se usa pre_init_hook en manifest).

import logging
>>>>>>> fb2d0eddb44261c7833d37e32b0869ec9bdb22c2
_logger = logging.getLogger(__name__)


def pre_init_hook(cr):
<<<<<<< HEAD
    """Añade la columna product_categ_id si no existe (antes de cargar el modelo, en install y upgrade)."""
    cr.execute("""
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'customer_own_inventory'
    """)
    if not cr.fetchone():
        return
    cr.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'customer_own_inventory'
          AND column_name = 'product_categ_id'
    """)
    if not cr.fetchone():
        _logger.info("mesa_ayuda_inventario: adding column product_categ_id to customer_own_inventory")
        cr.execute("""
            ALTER TABLE customer_own_inventory
            ADD COLUMN product_categ_id INTEGER REFERENCES product_category(id) ON DELETE SET NULL
        """)
        cr.execute("""
            CREATE INDEX customer_own_inventory_product_categ_id_idx
            ON customer_own_inventory (product_categ_id)
        """)
        cr.execute("""
            UPDATE customer_own_inventory co
            SET product_categ_id = pp.categ_id
            FROM product_product pp
            WHERE co.product_id = pp.id
        """)
=======
    """Reservado. Sin operaciones."""
    pass
>>>>>>> fb2d0eddb44261c7833d37e32b0869ec9bdb22c2
