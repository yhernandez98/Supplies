# -*- coding: utf-8 -*-
from odoo import fields, models


class SubscriptionProductGrouped(models.Model):
    """Añade license_type_id a subscription.product.grouped (comodel en este módulo)."""
    _inherit = 'subscription.product.grouped'

    license_type_id = fields.Many2one(
        'product.license.type',
        string='Tipo de Licencia',
        readonly=True,
        help='Tipo de licencia asociado',
    )
