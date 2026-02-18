# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class LotInfoWizard(models.TransientModel):
    """Wizard para completar información del lote cuando se agrega un número de serie."""
    
    _name = 'lot.info.wizard'
    _description = 'Wizard para Completar Información del Lote'

    quant_id = fields.Many2one(
        'stock.quant',
        string='Quant',
        required=True,
        help='Quant relacionado'
    )
    
    lot_id = fields.Many2one(
        'stock.lot',
        string='Número de Serie / Lote',
        required=True,
        help='Lote seleccionado'
    )
    
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        related='lot_id.product_id',
        readonly=True,
        store=False
    )
    
    location_id = fields.Many2one(
        'stock.location',
        string='Ubicación',
        related='quant_id.location_id',
        readonly=True,
        store=False
    )
    
    inventory_plate = fields.Char(
        string='Placa de Inventario',
        help='Placa de inventario del lote'
    )
    
    security_plate = fields.Char(
        string='Placa de Seguridad',
        help='Placa de seguridad del lote'
    )
    
    internal_ref = fields.Char(
        string='Referencia Interna',
        help='Referencia interna del lote'
    )
    
    owner_id = fields.Many2one(
        'res.partner',
        string='Propietario',
        help='Propietario del quant'
    )
    
    @api.model
    def default_get(self, fields_list):
        """Cargar valores por defecto desde el quant y el lote."""
        res = super(LotInfoWizard, self).default_get(fields_list)
        
        # Obtener quant_id y lot_id del contexto
        quant_id = self.env.context.get('default_quant_id', False)
        lot_id = self.env.context.get('default_lot_id', False)
        
        # Si no hay quant_id pero hay información en el contexto, crear un quant temporal
        if not quant_id:
            # Intentar buscar o crear quant basado en el contexto
            location_id = self.env.context.get('default_location_id', False)
            product_id = self.env.context.get('default_product_id', False)
            owner_id = self.env.context.get('default_owner_id', False)
            
            if location_id and product_id and lot_id:
                # Buscar quant existente
                quant = self.env['stock.quant'].search([
                    ('location_id', '=', location_id),
                    ('product_id', '=', product_id),
                    ('lot_id', '=', lot_id),
                    ('owner_id', '=', owner_id or False),
                ], limit=1)
                
                if quant:
                    quant_id = quant.id
                else:
                    # Si no existe, crear uno temporal (no se guardará hasta que se guarde el quant original)
                    # Por ahora, solo usamos la información del contexto
                    pass
        
        if quant_id:
            quant = self.env['stock.quant'].browse(quant_id)
            if quant.exists():
                res['quant_id'] = quant_id
                res['location_id'] = quant.location_id.id if quant.location_id else False
                res['owner_id'] = quant.owner_id.id if hasattr(quant, 'owner_id') and quant.owner_id else False
            else:
                # Si el quant no existe, usar información del contexto
                res['location_id'] = self.env.context.get('default_location_id', False)
                res['owner_id'] = self.env.context.get('default_owner_id', False)
        else:
            # Usar información del contexto
            res['location_id'] = self.env.context.get('default_location_id', False)
            res['owner_id'] = self.env.context.get('default_owner_id', False)
        
        if lot_id:
            lot = self.env['stock.lot'].browse(lot_id)
            if lot.exists():
                res['lot_id'] = lot_id
                res['inventory_plate'] = lot.inventory_plate or ''
                res['security_plate'] = lot.security_plate or ''
                # Referencia interna: usar ref si existe, sino inventory_plate
                if hasattr(lot, 'ref') and lot.ref:
                    res['internal_ref'] = lot.ref or ''
                elif lot.inventory_plate:
                    res['internal_ref'] = lot.inventory_plate or ''
                else:
                    res['internal_ref'] = ''
        
        return res
    
    def action_save(self):
        """Guardar la información del lote y actualizar el quant."""
        self.ensure_one()
        
        if not self.lot_id:
            raise UserError(_('Debe seleccionar un lote.'))
        
        # Actualizar información del lote
        lot_vals = {}
        if self.inventory_plate:
            lot_vals['inventory_plate'] = self.inventory_plate.strip()
        else:
            lot_vals['inventory_plate'] = False
            
        if self.security_plate:
            lot_vals['security_plate'] = self.security_plate.strip()
        else:
            lot_vals['security_plate'] = False
        
        # Referencia interna
        if hasattr(self.lot_id, 'ref'):
            if self.internal_ref:
                lot_vals['ref'] = self.internal_ref.strip()
            else:
                lot_vals['ref'] = False
        
        # Actualizar el lote
        if lot_vals:
            self.lot_id.sudo().write(lot_vals)
            _logger.info("Información del lote %s actualizada: %s", self.lot_id.name, lot_vals)
        
        # Si no hay quant_id pero hay información en el contexto, intentar encontrar o crear el quant
        if not self.quant_id and self.location_id and self.product_id and self.lot_id:
            # Buscar quant existente
            quant = self.env['stock.quant'].search([
                ('location_id', '=', self.location_id.id),
                ('product_id', '=', self.product_id.id),
                ('lot_id', '=', self.lot_id.id),
            ], limit=1)
            
            if quant:
                self.quant_id = quant
        
        # Actualizar el quant (owner_id si se cambió)
        if self.quant_id:
            quant_vals = {}
            if hasattr(self.quant_id, 'owner_id'):
                if self.owner_id:
                    quant_vals['owner_id'] = self.owner_id.id
                else:
                    quant_vals['owner_id'] = False
            
            # Asegurarse de que location_id se preserve (CRÍTICO para evitar que quede en "ninguno")
            if self.quant_id.location_id:
                quant_vals['location_id'] = self.quant_id.location_id.id
            
            # Asegurarse de que lot_id esté asignado
            if not self.quant_id.lot_id or self.quant_id.lot_id.id != self.lot_id.id:
                quant_vals['lot_id'] = self.lot_id.id
            
            if quant_vals:
                try:
                    self.quant_id.sudo().write(quant_vals)
                    _logger.info("Quant %s actualizado: %s", self.quant_id.id, quant_vals)
                    
                    # Invalidar cache para forzar actualización de campos computed
                    self.quant_id.invalidate_recordset(['lot_inventory_plate', 'lot_security_plate', 'lot_internal_ref'])
                except Exception as e:
                    _logger.error("Error al actualizar quant %s: %s", self.quant_id.id, str(e))
                    raise UserError(_('Error al actualizar el quant: %s') % str(e))
        
        # Mostrar mensaje de éxito
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Información guardada'),
                'message': _('La información del lote se ha guardado correctamente.'),
                'type': 'success',
                'sticky': False,
            }
        }

