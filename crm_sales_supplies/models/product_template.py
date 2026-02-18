# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_leasing = fields.Boolean(
        string='Es Leasing',
        default=False,
        help='Marca si este producto está incluido en un contrato de leasing'
    )
    leasing_contract_id = fields.Many2one(
        'leasing.contract',
        string='Contrato de Leasing',
        help='Contrato de leasing al que pertenece este producto'
    )
    leasing_brand_id = fields.Many2one(
        'leasing.brand',
        string='Marca de Leasing',
        related='leasing_contract_id.brand_id',
        store=True,
        readonly=True,
        help='Marca del contrato de leasing (ej: HP, Dell, etc.)'
    )
    leasing_provider_ids = fields.Many2many(
        'res.partner',
        'product_leasing_provider_rel',
        'product_tmpl_id',
        'provider_id',
        string='Proveedores de Leasing',
        related='leasing_contract_id.provider_ids',
        readonly=True,
        help='Proveedores asignados por la marca para despachar este producto'
    )

    @api.onchange('leasing_contract_id')
    def _onchange_leasing_contract_id(self):
        """Actualiza el campo is_leasing cuando cambia el contrato"""
        if self.leasing_contract_id:
            self.is_leasing = True
        else:
            self.is_leasing = False

