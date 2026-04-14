# -*- coding: utf-8 -*-
"""
Migración de calculadora_costos.line: valor_usd/garantia_usd -> monto_equipo/monto_garantia
y moneda por línea. Ejecutar antes de que el ORM elimine columnas antiguas.
"""


def migrate(cr, version):
    cr.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = 'calculadora_costos_line'"
    )
    if not cr.fetchone():
        return
    cr.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'calculadora_costos_line'
        """
    )
    cols = {r[0] for r in cr.fetchall()}
    if "monto_equipo" in cols:
        return
    if "valor_usd" not in cols:
        return

    cr.execute(
        """
        ALTER TABLE calculadora_costos_line
        ADD COLUMN IF NOT EXISTS moneda_equipo VARCHAR
        """
    )
    cr.execute(
        """
        UPDATE calculadora_costos_line
        SET moneda_equipo = 'USD'
        WHERE moneda_equipo IS NULL
        """
    )

    if "valor_cop" in cols:
        cr.execute(
            """
            UPDATE calculadora_costos_line
            SET moneda_equipo = 'COP',
                valor_usd = COALESCE(valor_cop, 0),
                garantia_usd = COALESCE(garantia_cop, 0)
            WHERE COALESCE(valor_usd, 0) = 0
              AND COALESCE(valor_cop, 0) <> 0
            """
        )

    cr.execute(
        """
        ALTER TABLE calculadora_costos_line
        RENAME COLUMN valor_usd TO monto_equipo
        """
    )
    cr.execute(
        """
        ALTER TABLE calculadora_costos_line
        RENAME COLUMN garantia_usd TO monto_garantia
        """
    )

    if "valor_cop" in cols:
        cr.execute("ALTER TABLE calculadora_costos_line DROP COLUMN IF EXISTS valor_cop")
    if "garantia_cop" in cols:
        cr.execute("ALTER TABLE calculadora_costos_line DROP COLUMN IF EXISTS garantia_cop")
