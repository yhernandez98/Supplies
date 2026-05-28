# -*- coding: utf-8 -*-
"""Recalcular pendientes al excluir perifericos y componentes."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    Lot = env["stock.lot"]
    if "invdash_pending_info" not in Lot._fields:
        return
    batch = 4000
    offset = 0
    while True:
        chunk = Lot.search([], offset=offset, limit=batch)
        if not chunk:
            break
        chunk._compute_invdash_pending_info()
        env.cr.commit()
        offset += batch
    _logger.info(
        "Migracion 19.0.0.0.72: pendientes recalculados excluyendo componentes y perifericos."
    )
