# -*- coding: utf-8 -*-
from odoo import api, fields, models


class StockMove(models.Model):
    """Extender Stock Move para mostrar información de leasing"""
    _inherit = 'stock.move'

    is_leasing = fields.Boolean(
        string='Es Leasing',
        related='product_id.is_leasing',
        store=True,
        readonly=True,
        help='Indica si este movimiento es de un producto de leasing'
    )
    leasing_brand_id = fields.Many2one(
        'leasing.brand',
        string='Marca de Leasing',
        related='product_id.leasing_brand_id',
        store=True,
        readonly=True,
        help='Marca del contrato de leasing'
    )
    leasing_contract_id = fields.Many2one(
        'leasing.contract',
        string='Contrato de Leasing',
        related='product_id.leasing_contract_id',
        store=True,
        readonly=True,
        help='Contrato de leasing del producto'
    )

