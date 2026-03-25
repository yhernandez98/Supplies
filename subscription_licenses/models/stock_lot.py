# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
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
        inverse='_inverse_license_user_ids',
        store=False,
        readonly=False,
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

    def _inverse_license_user_ids(self):
        """Permite edición en línea desde la subpestaña 'Licencias del Usuario'."""
        for lot in self:
            if not hasattr(lot, 'related_partner_id') or not lot.related_partner_id:
                continue

            location_partner_id, lot_location_id = lot._get_license_scope_data()
            domain = [
                ('contact_id', '=', lot.related_partner_id.id),
                ('state', '=', 'assigned'),
            ]
            if location_partner_id:
                domain.append(('partner_id', '=', location_partner_id))
            if lot_location_id:
                domain.append(('location_id', '=', lot_location_id))

            current = self.env['license.equipment'].search(domain)
            desired = lot.license_user_ids.filtered(lambda r: r and r.exists())

            # Quitar los que ya no quedaron en la grilla
            (current - desired).unlink()

            # Completar datos de los que quedaron/crearon
            for rec in desired:
                vals = {}
                if not rec.contact_id or rec.contact_id.id != lot.related_partner_id.id:
                    vals['contact_id'] = lot.related_partner_id.id
                if not rec.assignment_date:
                    vals['assignment_date'] = fields.Date.today()
                if vals:
                    rec.write(vals)
    
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

    def _get_license_scope_data(self):
        """Obtiene cliente/ubicación relevantes para filtrar licencias del lote actual."""
        self.ensure_one()
        location_partner_id = False
        lot_location_id = False

        try:
            if hasattr(self, 'location_partner_id') and self.location_partner_id:
                location_partner_id = self.location_partner_id.id
        except Exception:
            pass

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

        return location_partner_id, lot_location_id

    def action_manage_equipment_licenses(self):
        """Abre la gestión de licencias del equipo actual, permitiendo crear asignaciones."""
        self.ensure_one()
        location_partner_id, lot_location_id = self._get_license_scope_data()

        domain = [('lot_id', '=', self.id)]
        if location_partner_id:
            domain.append(('partner_id', '=', location_partner_id))
        if lot_location_id:
            domain.append(('location_id', '=', lot_location_id))

        return {
            'name': _('Licencias del Equipo: %s') % (self.name or self.display_name),
            'type': 'ir.actions.act_window',
            'res_model': 'license.equipment',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {
                'search_default_assigned': 1,
                'default_lot_id': self.id,
                'default_contact_id': getattr(self, 'related_partner_id', False) and self.related_partner_id.id or False,
                'default_partner_id': location_partner_id or False,
                'default_location_id': lot_location_id or False,
            },
            'target': 'current',
        }

    def action_manage_user_licenses(self):
        """Abre la gestión de licencias del usuario del equipo, permitiendo crear asignaciones."""
        self.ensure_one()
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

        location_partner_id, lot_location_id = self._get_license_scope_data()
        domain = [('contact_id', '=', self.related_partner_id.id)]
        if location_partner_id:
            domain.append(('partner_id', '=', location_partner_id))
        if lot_location_id:
            domain.append(('location_id', '=', lot_location_id))

        return {
            'name': _('Licencias del Usuario: %s') % self.related_partner_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'license.equipment',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {
                'search_default_assigned': 1,
                'default_contact_id': self.related_partner_id.id,
                'default_lot_id': False,
                'default_partner_id': location_partner_id or False,
                'default_location_id': lot_location_id or False,
            },
            'target': 'current',
        }

    def action_open_license_assignment_pick_wizard(self):
        """Abre un wizard para seleccionar la asignación sin usar el dropdown inline.

        Esto evita el recorte del selector dentro de la grilla editable.
        """
        self.ensure_one()
        tab_type = self.env.context.get('license_tab_type') or 'equipment'

        if tab_type not in ('equipment', 'user'):
            tab_type = 'equipment'

        if tab_type == 'user' and not getattr(self, 'related_partner_id', False):
            # Se reutiliza el mismo mensaje/validación que ya se usa en otras acciones.
            raise UserError(_('Este equipo no tiene un usuario relacionado asignado.'))

        return {
            'name': _('Agregar Asignación de Licencia'),
            'type': 'ir.actions.act_window',
            'res_model': 'license.assignment.pick.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_lot_id': self.id,
                'default_license_tab_type': tab_type,
            }
        }
