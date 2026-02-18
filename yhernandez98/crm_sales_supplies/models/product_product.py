# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    is_leasing = fields.Boolean(
        string='Es Leasing',
        related='product_tmpl_id.is_leasing',
        store=True,
        readonly=True,
        help='Marca si este producto está incluido en un contrato de leasing'
    )
    leasing_contract_id = fields.Many2one(
        'leasing.contract',
        string='Contrato de Leasing',
        related='product_tmpl_id.leasing_contract_id',
        store=True,
        readonly=True,
        help='Contrato de leasing al que pertenece este producto'
    )
    leasing_brand_id = fields.Many2one(
        'leasing.brand',
        string='Marca de Leasing',
        related='product_tmpl_id.leasing_brand_id',
        store=True,
        readonly=True,
        help='Marca del contrato de leasing (ej: HP, Dell, etc.)'
    )
    leasing_provider_ids = fields.Many2many(
        'res.partner',
        string='Proveedores de Leasing',
        related='product_tmpl_id.leasing_provider_ids',
        readonly=True,
        help='Proveedores asignados por la marca para despachar este producto'
    )

