# -*- coding: utf-8 -*-
from odoo import api, fields, models

RETURN_E4_CLASSIFIED_ROLE_SORT = {
    'principal': 0,
    'standalone': 1,
    'associated': 2,
    'bundled': 3,
}


class StockPickingReturnE4ClassifiedLine(models.Model):
    _name = 'stock.picking.return.e4.classified.line'
    _description = 'Línea archivada — traslado E4 devolución'
    _order = 'group_lot_id, line_role_sort, id'

    picking_id = fields.Many2one(
        'stock.picking',
        string='Albarán E4',
        required=True,
        ondelete='cascade',
        index=True,
    )
    line_role = fields.Selection(
        [
            ('principal', 'Principal'),
            ('associated', 'Asociado'),
            ('standalone', 'Serial'),
            ('bundled', 'Componente'),
        ],
        string='Tipo',
        required=True,
    )
    principal_lot_id = fields.Many2one(
        'stock.lot',
        string='Serial padre',
        readonly=True,
    )
    lot_id = fields.Many2one(
        'stock.lot',
        string='Serial',
        required=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        'product.product',
        related='lot_id.product_id',
        string='Producto',
        readonly=True,
    )
    quantity = fields.Float(string='Cantidad', readonly=True)
    destination = fields.Selection(
        [
            ('stock', 'Existencias'),
            ('warranty', 'Garantía'),
            ('repair', 'Reparación'),
            ('scrap_initial', 'PreBaja'),
        ],
        string='Destino clasificado',
        readonly=True,
    )
    destination_label = fields.Char(
        string='Destino',
        compute='_compute_destination_label',
        readonly=True,
    )
    group_lot_id = fields.Many2one(
        'stock.lot',
        string='Equipo principal',
        compute='_compute_group_lot_id',
        store=True,
        index=True,
        readonly=True,
    )
    group_product_id = fields.Many2one(
        'product.product',
        related='group_lot_id.product_id',
        string='Producto principal',
        readonly=True,
    )
    group_label = fields.Char(
        string='Conjunto',
        compute='_compute_group_label',
        store=True,
        index=True,
        readonly=True,
    )
    line_role_label = fields.Char(
        string='Tipo',
        compute='_compute_line_role_label',
        readonly=True,
    )
    line_role_sort = fields.Integer(
        compute='_compute_line_role_sort',
        store=True,
        readonly=True,
    )

    @api.depends('line_role', 'principal_lot_id', 'lot_id')
    def _compute_group_lot_id(self):
        for line in self:
            if line.line_role in ('associated', 'bundled') and line.principal_lot_id:
                line.group_lot_id = line.principal_lot_id
            elif line.line_role == 'principal':
                line.group_lot_id = line.lot_id
            else:
                line.group_lot_id = line.lot_id

    @api.depends('group_lot_id', 'group_lot_id.product_id', 'group_lot_id.name')
    def _compute_group_label(self):
        for line in self:
            lot = line.group_lot_id
            if not lot:
                line.group_label = ''
                continue
            product = lot.product_id.display_name if lot.product_id else ''
            serial = lot.name or ''
            if product and serial:
                line.group_label = '%s — %s' % (product, serial)
            else:
                line.group_label = product or serial or ''

    @api.depends('line_role')
    def _compute_line_role_sort(self):
        for line in self:
            line.line_role_sort = RETURN_E4_CLASSIFIED_ROLE_SORT.get(line.line_role, 9)

    @api.depends('line_role')
    def _compute_line_role_label(self):
        labels = dict(self._fields['line_role'].selection)
        for line in self:
            line.line_role_label = labels.get(line.line_role, line.line_role or '')

    @api.depends('destination')
    def _compute_destination_label(self):
        labels = {
            'stock': 'Existencias',
            'warranty': 'Garantía',
            'repair': 'Reparación',
            'scrap_initial': 'PreBaja',
        }
        for line in self:
            line.destination_label = labels.get(line.destination, '') or ''
