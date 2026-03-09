# -*- coding: utf-8 -*-
"""Extiende subscription.product.grouped con license_type_id (comodel product.license.type)."""
from odoo import fields, models


class SubscriptionProductGrouped(models.Model):
    """Añade el campo license_type_id al modelo base (definido en subscription_nocount)
    para evitar que subscription_nocount dependa de product.license.type en tiempo de carga.
    """
    _inherit = 'subscription.product.grouped'

    license_type_id = fields.Many2one(
        'product.license.type',
        string='Tipo de Licencia',
        readonly=True,
        help='Tipo de licencia asociado',
    )
