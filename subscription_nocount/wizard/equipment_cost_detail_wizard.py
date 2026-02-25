# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class SubscriptionEquipmentCostDetailWizard(models.TransientModel):
    _name = 'subscription.equipment.cost.detail.wizard'
    _description = 'Wizard: Elementos Con Costo del serial'

    lot_id = fields.Many2one(
        'stock.lot',
        string='Serial/Lote',
        readonly=True,
        help='Serial cuyos elementos con costo se muestran.',
    )
    line_ids = fields.One2many(
        'subscription.equipment.cost.detail.wizard.line',
        'wizard_id',
        string='Elementos Con Costo',
        readonly=True,
    )

    @api.model
    def create(self, vals):
        wizard = super().create(vals)
        if wizard.lot_id and hasattr(wizard.lot_id, 'lot_supply_line_ids'):
            lines_with_cost = wizard.lot_id.lot_supply_line_ids.filtered(lambda l: l.has_cost)
            Line = self.env['subscription.equipment.cost.detail.wizard.line']
            for supply in lines_with_cost:
                item_label = supply.item_type or ''
                if hasattr(supply._fields.get('item_type'), 'selection') and supply.item_type:
                    item_label = dict(supply._fields['item_type'].selection).get(supply.item_type, supply.item_type)
                Line.create({
                    'wizard_id': wizard.id,
                    'product_id': supply.product_id.id if supply.product_id else False,
                    'product_name': supply.product_id.display_name if supply.product_id else '',
                    'related_lot_id': supply.related_lot_id.id if supply.related_lot_id else False,
                    'serial_name': supply.related_lot_id.name if supply.related_lot_id else '',
                    'item_type': item_label,
                    'cost': supply.cost or 0.0,
                    'quantity': supply.quantity or 1.0,
                })
        return wizard


class SubscriptionEquipmentCostDetailWizardLine(models.TransientModel):
    _name = 'subscription.equipment.cost.detail.wizard.line'
    _description = 'Línea del wizard: elemento con costo'

    wizard_id = fields.Many2one(
        'subscription.equipment.cost.detail.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one('product.product', string='Producto', readonly=True)
    product_name = fields.Char(string='Producto', readonly=True)
    related_lot_id = fields.Many2one('stock.lot', string='Serial', readonly=True)
    serial_name = fields.Char(string='Número de serie', readonly=True)
    item_type = fields.Char(string='Tipo', readonly=True)
    cost = fields.Float(string='Costo', digits=(16, 2), readonly=True)
    quantity = fields.Float(string='Cantidad', digits=(16, 2), readonly=True, default=1.0)
