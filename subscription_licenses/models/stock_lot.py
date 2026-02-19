# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)


class StockLot(models.Model):
    """Extender stock.lot para mostrar licencias asignadas"""
    _inherit = 'stock.lot'

    # Campo One2many directo para licencias asignadas a este equipo
    license_equipment_ids = fields.One2many(
        'license.equipment',
        'lot_id',
        string='Licencias Asignadas al Equipo',
        domain="[('state', '=', 'assigned')]",
        help='Licencias asignadas directamente a este equipo'
    )
    
    # Campo Many2many computado para licencias asignadas al usuario relacionado
    license_user_ids = fields.Many2many(
        'license.equipment',
        string='Licencias Asignadas al Usuario',
        compute='_compute_license_user_ids',
        store=False,
        help='Licencias asignadas al usuario relacionado de este equipo'
    )
    
    @api.depends('related_partner_id', 'location_partner_id')
    def _compute_license_user_ids(self):
        """Calcula las licencias asignadas al usuario relacionado"""
        for lot in self:
            if not hasattr(lot, 'related_partner_id') or not lot.related_partner_id:
                lot.license_user_ids = False
                continue
            
            # Obtener cliente y ubicación del lote
            location_partner_id = False
            lot_location_id = False
            
            # Obtener el cliente de la ubicación
            try:
                if hasattr(lot, 'location_partner_id') and lot.location_partner_id:
                    location_partner_id = lot.location_partner_id.id
            except Exception:
                pass
            
            # Obtener la ubicación del lote (desde quants)
            try:
                quant = self.env['stock.quant'].search([
                    ('lot_id', '=', lot.id),
                    ('quantity', '>', 0),
                    ('location_id.usage', '=', 'internal'),
                ], order='quantity desc, in_date desc', limit=1)
                
                if quant and quant.location_id:
                    lot_location_id = quant.location_id.id
            except Exception:
                pass
            
            # Construir dominio
            domain = [
                ('contact_id', '=', lot.related_partner_id.id),
                ('state', '=', 'assigned')
            ]
            
            # Filtrar por cliente si tenemos location_partner_id
            if location_partner_id:
                domain.append(('partner_id', '=', location_partner_id))
            
            # Filtrar por ubicación si tenemos lot_location_id
            if lot_location_id:
                domain.append(('location_id', '=', lot_location_id))
            
            # Buscar las licencias
            try:
                license_equipment = self.env['license.equipment'].search(domain)
                lot.license_user_ids = license_equipment
            except Exception as e:
                _logger.warning("Error al calcular license_user_ids: %s", str(e))
                lot.license_user_ids = False
    
    def action_view_user_licenses(self):
        """Abrir vista de licencias asignadas al usuario relacionado"""
        self.ensure_one()
        
        # Verificar si el campo related_partner_id existe
        if not hasattr(self, 'related_partner_id') or not self.related_partner_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin Usuario'),
                    'message': _('Este equipo no tiene un usuario relacionado asignado.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        # Obtener cliente y ubicación del lote
        location_partner_id = False
        lot_location_id = False
        
        # Obtener el cliente de la ubicación
        try:
            if hasattr(self, 'location_partner_id') and self.location_partner_id:
                location_partner_id = self.location_partner_id.id
        except Exception:
            pass
        
        # Obtener la ubicación del lote (desde quants)
        try:
            quant = self.env['stock.quant'].search([
                ('lot_id', '=', self.id),
                ('quantity', '>', 0),
                ('location_id.usage', '=', 'internal'),
            ], order='quantity desc, in_date desc', limit=1)
            
            if quant and quant.location_id:
                lot_location_id = quant.location_id.id
        except Exception:
            pass
        
        # Construir dominio
        domain = [
            ('contact_id', '=', self.related_partner_id.id),
            ('state', '=', 'assigned')
        ]
        
        # Filtrar por cliente si tenemos location_partner_id
        if location_partner_id:
            domain.append(('partner_id', '=', location_partner_id))
        
        # Filtrar por ubicación si tenemos lot_location_id
        if lot_location_id:
            domain.append(('location_id', '=', lot_location_id))
        
        # Retornar acción para abrir vista de license.equipment
        return {
            'name': _('Licencias del Usuario: %s') % self.related_partner_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'license.equipment',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {
                'search_default_assigned': 1,
                'default_contact_id': self.related_partner_id.id,
            },
            'target': 'current',
        }
