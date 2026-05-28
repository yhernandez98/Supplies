# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    integration_execution_policy = fields.Selection(
        [
            ('customer_approved', 'Solo aprobación cliente'),
            ('crm_quote_approved', 'Solo aprobación CRM de cotización proveedor'),
            ('either', 'Cualquiera de las dos aprobaciones'),
        ],
        string='Política ejecución integración',
        default='customer_approved',
        required=True,
        help='Define cuándo el caso de integración puede ejecutar operación de compra/entrega.',
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    integration_execution_policy = fields.Selection(
        related='company_id.integration_execution_policy',
        readonly=False,
    )
