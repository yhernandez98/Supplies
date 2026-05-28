# -*- coding: utf-8 -*-
"""Recalcular contacto/ubicación mostrados con fallback por nombre de ubicación."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    Lot = env["stock.lot"]
    if not hasattr(Lot, "_compute_display_location_contact"):
        return
    batch = 4000
    offset = 0
    while True:
        chunk = Lot.search([], offset=offset, limit=batch)
        if not chunk:
            break
        chunk._compute_display_location_contact()
        env.cr.commit()
        offset += batch
    _logger.info(
        "Migracion 19.0.0.0.85: display_contact_id/display_location_id recalculados."
    )
