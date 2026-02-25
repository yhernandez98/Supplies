# -*- coding: utf-8 -*-
from odoo import api, fields, models


class StockPicking(models.Model):
    """Extender Stock Picking."""
    _inherit = 'stock.picking'

    has_leasing_products = fields.Boolean(
        string='Contiene Productos de Leasing',
        compute='_compute_has_leasing_products',
        store=False,
        help='Indica si esta transferencia contiene productos de leasing'
    )
    leasing_products_count = fields.Integer(
        string='Productos de Leasing',
        compute='_compute_has_leasing_products',
        store=False,
        help='Cantidad de productos de leasing en esta transferencia'
    )

    @api.depends('move_ids.product_id.is_leasing')
    def _compute_has_leasing_products(self):
        """Calcular si la transferencia contiene productos de leasing.
        Usa move_ids (Odoo 19); move_ids_without_package puede no existir."""
        for picking in self:
            moves = getattr(picking, 'move_ids_without_package', picking.move_ids)
            leasing_moves = moves.filtered(
                lambda m: m.product_id and m.product_id.is_leasing
            )
            picking.has_leasing_products = bool(leasing_moves)
            picking.leasing_products_count = len(leasing_moves)

