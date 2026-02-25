# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PurchaseAlertComponentLine(models.Model):
    """Línea de componente, periférico o complemento para una alerta de compra."""
    _name = 'purchase.alert.component.line'
    _description = 'Línea de Componente/Periférico/Complemento en Alerta de Compra'
    _order = 'item_type, product_id'

    alert_id = fields.Many2one(
        'purchase.alert',
        string='Alerta',
        required=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        required=True,
        readonly=True,
    )
    quantity = fields.Float(
        string='Cantidad',
        required=True,
        readonly=True,
        help='Cantidad total necesaria (cantidad por unidad × cantidad solicitada)',
    )
    uom_id = fields.Many2one(
        'uom.uom',
        string='Unidad de Medida',
        readonly=True,
    )
    item_type = fields.Selection([
        ('component', 'Componente'),
        ('peripheral', 'Periférico'),
        ('complement', 'Complemento'),
    ], string='Tipo', required=True, readonly=True)
    item_type_display = fields.Char(
        string='Tipo (texto)',
        compute='_compute_item_type_display',
        readonly=True,
        store=False,
    )
    parent_product_id = fields.Many2one(
        'product.product',
        string='Producto Principal',
        readonly=True,
        help='Producto principal del cual proviene este componente, periférico o complemento',
    )
    
    @api.depends('item_type')
    def _compute_item_type_display(self):
        """Calcular el tipo para mostrar."""
        type_labels = {
            'component': 'Componente',
            'peripheral': 'Periférico',
            'complement': 'Complemento',
        }
        for line in self:
            line.item_type_display = type_labels.get(line.item_type, '')
    
    def unlink(self):
        """No permitir eliminar líneas manualmente - se eliminan automáticamente al actualizar."""
        raise UserError(_('No se pueden eliminar manualmente los componentes, periféricos o complementos. Use el botón "Actualizar Componentes" para refrescar la información.'))

