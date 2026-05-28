# -*- coding: utf-8 -*-
"""Incluir tránsito (y todo child_of Supp) en exclusión de pendientes de información."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    Lot = env["stock.lot"]
    if "is_stock_in_supp_existencias" not in Lot._fields:
        return
    batch = 4000
    offset = 0
    while True:
        chunk = Lot.search([], offset=offset, limit=batch)
        if not chunk:
            break
        chunk._compute_is_stock_in_supp_existencias()
        if "invdash_pending_info" in Lot._fields:
            chunk._compute_invdash_pending_info()
        env.cr.commit()
        offset += batch
    _logger.info(
        "Migración 19.0.0.0.68: exclusión Supp incluye tránsito y subárbol completo."
    )
