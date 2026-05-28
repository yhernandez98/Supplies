# -*- coding: utf-8 -*-
"""Índice parcial: lotes pendientes por contacto (acelera dominio + agrupación)."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    try:
        cr.execute(
            """
            CREATE INDEX IF NOT EXISTS stock_lot_invdash_pending_contact_partial_idx
            ON stock_lot (display_contact_id)
            WHERE invdash_pending_info IS TRUE
            """
        )
    except Exception as e:
        _logger.warning('Índice parcial pendientes/contacto: %s', e)
