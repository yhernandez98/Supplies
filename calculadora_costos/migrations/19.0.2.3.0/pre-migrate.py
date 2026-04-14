# -*- coding: utf-8 -*-
"""Renombra costo_servicios_completos -> costo_servicio_tecnico_mensual_cop en tablas del módulo."""


def migrate(cr, version):
    tables = (
        "calculadora_costos",
        "calculadora_equipo",
        "calculadora_renting",
    )
    for table in tables:
        cr.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_name = %s AND column_name = 'costo_servicios_completos'
            """,
            (table,),
        )
        if cr.fetchone():
            cr.execute(
                """
                ALTER TABLE "%s" RENAME COLUMN costo_servicios_completos TO costo_servicio_tecnico_mensual_cop
                """
                % table
            )
