# -*- coding: utf-8 -*-
"""Calcular invdash_serial_multi_location tras añadir la consulta."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    Lot = env["stock.lot"]
    if "invdash_serial_multi_location" not in Lot._fields:
        return
    batch = 4000
    offset = 0
    while True:
        chunk = Lot.search([], offset=offset, limit=batch)
        if not chunk:
            break
        chunk._compute_invdash_serial_multi_location()
        env.cr.commit()
        offset += batch
    _logger.info("Migración 19.0.0.0.71: invdash_serial_multi_location calculado.")
