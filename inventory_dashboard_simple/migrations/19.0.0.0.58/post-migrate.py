# -*- coding: utf-8 -*-
"""Recalcular contacto/ubicación mostrados tras mejorar la resolución por jerarquía de ubicación."""


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    StockLot = env["stock.lot"]
    if (
        "display_contact_id" not in StockLot._fields
        or "invdash_pending_info" not in StockLot._fields
    ):
        return
    # Solo lotes que siguen en «pendientes»: mismo alcance que la vista
    todo = StockLot.search([("invdash_pending_info", "=", True)])
    if todo:
        todo._compute_display_location_contact()
