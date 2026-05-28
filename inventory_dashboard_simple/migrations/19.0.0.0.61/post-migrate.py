# -*- coding: utf-8 -*-
"""Recalcular campos almacenados de ubicación / Supp / pendiente en lotes (rendimiento listados)."""


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    Lot = env["stock.lot"]
    needed = (
        "is_stock_in_supp_existencias" in Lot._fields
        and "display_location_id" in Lot._fields
        and "invdash_pending_info" in Lot._fields
    )
    if not needed:
        return

    batch = 4000
    offset = 0
    while True:
        chunk = Lot.search([], offset=offset, limit=batch)
        if not chunk:
            break
        chunk._compute_is_stock_in_supp_existencias()
        chunk._compute_display_location_contact()
        chunk._compute_invdash_pending_info()
        env.cr.commit()
        offset += batch
