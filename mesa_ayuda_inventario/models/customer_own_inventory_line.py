# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class CustomerOwnInventoryLine(models.Model):
    """Líneas de productos asociados (componentes, periféricos, complementos) al inventario propio."""
    _name = 'customer.own.inventory.line'
    _description = 'Línea de Inventario Propio (Asociados)'
    _order = 'own_inventory_id, item_type, id'

    own_inventory_id = fields.Many2one(
        'customer.own.inventory',
        string='Equipo principal',
        required=True,
        ondelete='cascade',
        index=True,
        help='Producto propio del cliente al que se asocia este elemento'
    )
    related_own_inventory_id = fields.Many2one(
        'customer.own.inventory',
        string='Producto asociado',
        required=True,
        ondelete='cascade',
        index=True,
        help='Producto propio (componente, periférico o complemento) asociado al equipo principal'
    )
    item_type = fields.Selection(
        [
            ('component', 'Componente'),
            ('peripheral', 'Periférico'),
            ('complement', 'Complemento'),
        ],
        string='Tipo',
        required=True,
        default='component',
        help='Tipo de asociación'
    )
    product_id = fields.Many2one(
        'product.product',
        related='related_own_inventory_id.product_id',
        string='Producto',
        readonly=True
    )
    serial_number = fields.Char(
        related='related_own_inventory_id.serial_number',
        string='Número de serie',
        readonly=True
    )

    @api.constrains('own_inventory_id', 'related_own_inventory_id')
    def _check_same_partner(self):
        for line in self:
            if line.own_inventory_id and line.related_own_inventory_id:
                if line.own_inventory_id.partner_id != line.related_own_inventory_id.partner_id:
                    raise ValidationError(_(
                        'El equipo principal y el producto asociado deben pertenecer al mismo cliente.'
                    ))
                if line.own_inventory_id.id == line.related_own_inventory_id.id:
                    raise ValidationError(_(
                        'Un producto no puede asociarse a sí mismo.'
                    ))

    @api.constrains('own_inventory_id', 'related_own_inventory_id', 'item_type')
    def _check_unique_related(self):
        for line in self:
            if not line.own_inventory_id or not line.related_own_inventory_id:
                continue
            existing = self.search([
                ('own_inventory_id', '=', line.own_inventory_id.id),
                ('related_own_inventory_id', '=', line.related_own_inventory_id.id),
                ('id', '!=', line.id),
            ], limit=1)
            if existing:
                labels = dict(line._fields['item_type'].selection)
                raise ValidationError(_(
                    'Este producto ya está asociado a este equipo como %s.'
                ) % labels.get(line.item_type, line.item_type))
