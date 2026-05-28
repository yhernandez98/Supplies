# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class StockQuant(models.Model):
    """Extender stock.quant para agregar campos relacionados del lote."""
    _inherit = 'stock.quant'

    def _invdash_refresh_lot_pending_flags(self, lot_ids):
        """Al mover cantidad/ubicación, actualizar exclusión Supp y pendientes sin depender solo del cache."""
        if not lot_ids:
            return
        Lot = self.env['stock.lot']
        if 'is_stock_in_supp_existencias' not in Lot._fields:
            return
        lots = Lot.browse([i for i in lot_ids if i])
        lots = lots.exists()
        if not lots:
            return
        lots._compute_is_stock_in_supp_existencias()
        if 'invdash_pending_info' in Lot._fields:
            lots._compute_invdash_pending_info()
        if 'display_location_id' in Lot._fields and hasattr(Lot, '_compute_display_location_contact'):
            lots._compute_display_location_contact()
        if 'invdash_serial_multi_location' in Lot._fields and hasattr(Lot, '_compute_invdash_serial_multi_location'):
            lots._compute_invdash_serial_multi_location()

    @api.model_create_multi
    def create(self, vals_list):
        quants = super().create(vals_list)
        self._invdash_refresh_lot_pending_flags(quants.mapped('lot_id').ids)
        return quants

    def write(self, vals):
        lot_ids = list(set(self.mapped('lot_id').ids))
        res = super().write(vals)
        touch = bool(vals.keys() & {'location_id', 'quantity'})
        if touch:
            lot_ids = list(set(lot_ids + self.mapped('lot_id').ids))
            self._invdash_refresh_lot_pending_flags(lot_ids)
        return res

    def unlink(self):
        lot_ids = list(set(self.mapped('lot_id').ids))
        res = super().unlink()
        self._invdash_refresh_lot_pending_flags(lot_ids)
        return res

    # Campos editables del lote - computed para mostrar, editables para escribir
    lot_inventory_plate = fields.Char(
        string='Placa de Inventario',
        compute='_compute_lot_fields',
        inverse='_inverse_lot_inventory_plate',
        store=False,
        help='Placa de inventario del lote'
    )
    
    lot_security_plate = fields.Char(
        string='Placa de Seguridad',
        compute='_compute_lot_fields',
        inverse='_inverse_lot_security_plate',
        store=False,
        help='Placa de seguridad del lote'
    )
    
    lot_internal_ref = fields.Char(
        string='Referencia Interna',
        compute='_compute_lot_fields',
        inverse='_inverse_lot_internal_ref',
        store=False,
        help='Referencia interna del lote'
    )

    @api.depends('lot_id', 'lot_id.inventory_plate', 'lot_id.security_plate', 'lot_id.ref')
    def _compute_lot_fields(self):
        """Calcular campos del lote."""
        for quant in self:
            if quant.lot_id:
                lot = quant.lot_id
                quant.lot_inventory_plate = lot.inventory_plate or ''
                quant.lot_security_plate = lot.security_plate or ''
                if hasattr(lot, 'ref') and lot.ref:
                    quant.lot_internal_ref = lot.ref or ''
                elif lot.inventory_plate:
                    quant.lot_internal_ref = lot.inventory_plate or ''
                else:
                    quant.lot_internal_ref = ''
            else:
                quant.lot_inventory_plate = ''
                quant.lot_security_plate = ''
                quant.lot_internal_ref = ''

    def _inverse_lot_inventory_plate(self):
        """Actualizar placa de inventario en el lote."""
        for quant in self:
            if quant.lot_id and quant.lot_id.exists():
                value = quant.lot_inventory_plate.strip() if quant.lot_inventory_plate else False
                if quant.lot_id.inventory_plate != value:
                    quant.lot_id.sudo().write({'inventory_plate': value})
                    quant.lot_id.invalidate_recordset(['inventory_plate'])
                quant.invalidate_recordset(['lot_inventory_plate'])

    def _inverse_lot_security_plate(self):
        """Actualizar placa de seguridad en el lote."""
        for quant in self:
            if quant.lot_id and quant.lot_id.exists():
                value = quant.lot_security_plate.strip() if quant.lot_security_plate else False
                if quant.lot_id.security_plate != value:
                    quant.lot_id.sudo().write({'security_plate': value})
                    quant.lot_id.invalidate_recordset(['security_plate'])
                quant.invalidate_recordset(['lot_security_plate'])

    def _inverse_lot_internal_ref(self):
        """Actualizar referencia interna en el lote."""
        for quant in self:
            if quant.lot_id and quant.lot_id.exists():
                value = quant.lot_internal_ref.strip() if quant.lot_internal_ref else False
                if hasattr(quant.lot_id, 'ref'):
                    if quant.lot_id.ref != value:
                        quant.lot_id.sudo().write({'ref': value})
                        quant.lot_id.invalidate_recordset(['ref'])
                elif value:
                    if quant.lot_id.inventory_plate != value:
                        quant.lot_id.sudo().write({'inventory_plate': value})
                        quant.lot_id.invalidate_recordset(['inventory_plate'])
                quant.invalidate_recordset(['lot_internal_ref'])

    @api.onchange('lot_id')
    def _onchange_lot_id(self):
        """Actualizar campos relacionados cu