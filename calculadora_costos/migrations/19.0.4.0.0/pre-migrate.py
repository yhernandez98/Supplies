# -*- coding: utf-8 -*-
"""
Copia monto_equipo -> price_unit (cantidad 1) antes de que el ORM elimine la columna antigua.
"""


def migrate(cr, version):
    cr.execute(
        """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'calculadora_costos_line'
        )
        """
    )
    if not cr.fetchone()[0]:
        return
    cr.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'calculadora_costos_line'
        """
    )
    cols = {row[0] for row in cr.fetchall()}
    if "price_unit" in cols and "product_qty" in cols:
        return
    if "monto_equipo" in cols:
        if "product_qty" not in cols:
            cr.execute(
                """
                ALTER TABLE calculadora_costos_line
                ADD COLUMN product_qty double precision DEFAULT 1.0 NOT NULL
                """
            )
        if "price_unit" not in cols:
            cr.execute(
                """
                ALTER TABLE calculadora_costos_line
                ADD COLUMN price_unit double precision DEFAULT 0.0
                """
            )
        cr.execute(
            """
            UPDATE calculadora_costos_line
            SET product_qty = 1.0,
                price_unit = COALESCE(monto_equipo, 0.0)
            """
        )
    else:
        if "product_qty" not in cols:
            cr.execute(
                """
                ALTER TABLE calculadora_costos_line
                ADD COLUMN product_qty double precision DEFAULT 1.0 NOT NULL
                """
            )
        if "price_unit" not in cols:
            cr.execute(
                """
                ALTER TABLE calculadora_costos_line
                ADD COLUMN price_unit double precision DEFAULT 0.0
                """
            )
