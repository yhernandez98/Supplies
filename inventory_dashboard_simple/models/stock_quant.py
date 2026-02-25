# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class StockQuant(models.Model):
    """Extender stock.quant para agregar campos relacionados del lote."""
    _inherit = 'stock.quant'

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
        """Actualizar campos relacionados cuando cambia el lote."""
        if self.lot_id:
            self._compute_lot_fields()

    def action_correct_quantity_to_one(self):
        """
        Corrige la cantidad de los quants seleccionados a 1.
        Solo actúa sobre registros con cantidad > 1; reduce usando _update_available_quantity.
        """
        quants_to_fix = self.filtered(lambda q: (q.quantity or 0) > 1)
        if not quants_to_fix:
            raise UserError(_('Ningún registro seleccionado tiene cantidad mayor a 1.'))
        # Guardar datos antes de modificar (los registros pueden cambiar tras _update_available_quantity)
        to_apply = []
        for quant in quants_to_fix:
            current = quant.quantity or 0
            if current <= 1:
                continue
            delta = 1.0 - current
            to_apply.append((quant.product_id, quant.location_id, delta, quant.lot_id, quant.owner_id, quant.package_id))
        Quant = self.env['stock.quant'].sudo()
        for product_id, location_id, delta, lot_id, owner_id, package_id in to_apply:
            Quant._update_available_quantity(
                product_id,
                location_id,
                delta,
                lot_id=lot_id,
                owner_id=owner_id,
                package_id=package_id or False,
            )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Cantidad corregida'),
                'message': _('Se corrigió la cantidad a 1 en %s registro(s).') % len(to_apply),
                'type': 'success',
                'sticky': False,
            },
        }

