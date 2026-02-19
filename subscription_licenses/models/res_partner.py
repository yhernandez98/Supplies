# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_license_provider = fields.Boolean(
        string='Es Proveedor de Licencias',
        default=False,
        help='Marcar si este contacto es un proveedor de licencias'
    )
