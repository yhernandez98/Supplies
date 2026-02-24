# -*- coding: utf-8 -*-
"""Elimina la regla ir.rule que causaba pérdida de conexión al abrir Parámetros Financieros."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Elimina la regla parametros_financieros_rule si existe."""
    try:
        # Primero eliminar la regla, luego el xml_id
        cr.execute("""
            DELETE FROM ir_rule
            WHERE id IN (
                SELECT res_id FROM ir_model_data
                WHERE module = 'calculadora_costos'
                AND name = 'parametros_financieros_rule'
                AND model = 'ir.rule'
            )
        """)
        cr.execute("""
            DELETE FROM ir_model_data
            WHERE module = 'calculadora_costos'
            AND name = 'parametros_financieros_rule'
            AND model = 'ir.rule'
        """)
    except Exception as e:
        _logger.warning("Could not remove parametros_financieros_rule: %s", e)
