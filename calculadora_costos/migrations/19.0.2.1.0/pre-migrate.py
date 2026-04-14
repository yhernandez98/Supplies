# -*- coding: utf-8 -*-
"""Convierte calculadora_costos.plazo_meses de entero a texto para fields.Selection."""


def migrate(cr, version):
    cr.execute(
        """
        SELECT data_type
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'calculadora_costos'
          AND column_name = 'plazo_meses'
        """
    )
    row = cr.fetchone()
    if not row:
        return
    if row[0] not in ("integer", "bigint", "smallint"):
        return
    cr.execute(
        """
        ALTER TABLE calculadora_costos
        ALTER COLUMN plazo_meses TYPE VARCHAR
        USING CASE
            WHEN plazo_meses IS NULL THEN '24'
            WHEN plazo_meses IN (12, 24, 36, 48, 60) THEN plazo_meses::text
            ELSE '24'
        END
        """
    )
