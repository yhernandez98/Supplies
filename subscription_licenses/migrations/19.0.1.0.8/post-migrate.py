# -*- coding: utf-8 -*-
"""Completar tipo de contratacion faltante antes de forzar campo requerido."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # Evita error al aplicar required=True si existen registros antiguos sin valor.
    cr.execute(
        """
        UPDATE license_assignment
           SET contracting_type = 'monthly_monthly'
         WHERE contracting_type IS NULL
            OR contracting_type = ''
        """
    )
    _logger.info(
        "Migracion 19.0.1.0.8: contracting_type completado para registros sin valor."
    )
