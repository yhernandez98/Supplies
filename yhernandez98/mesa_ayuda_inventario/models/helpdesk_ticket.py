# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class HelpdeskTicket(models.Model):
    """Extensión del módulo nativo helpdesk.ticket para agregar campos de mantenimiento."""
    _inherit = 'helpdesk.ticket'  # ✅ Extendiendo el modelo nativo
    
    # Campos adicionales para integración con mantenimientos
    lot_id = fields.Many2one(
        'stock.lot',
        string='Equipo',
        domain="[('customer_id', '=', partner_id)]",
        tracking=True,
        help='Equipo relacionado con el ticket'
    )
    
    maintenance_order_id = fields.Many2one(
        'maintenance.order',
        string='Orden de Mantenimiento',
        tracking=True,
        help='Orden de mantenimiento relacionada'
    )
    
    maintenance_id = fields.Many2one(
        'stock.lot.maintenance',
        string='Mantenimiento',
        tracking=True,
        help='Mantenimiento relacionado'
    )
    
    # Categoría personalizada para distinguir tickets de mantenimiento
    maintenance_category = fields.Selection([
        ('maintenance', 'Mantenimiento'),
        ('repair', 'Reparación'),
        ('support', 'Soporte'),
        ('change', 'Cambio de Equipo'),
        ('other', 'Otro'),
    ], string='Categoría Mantenimiento', tracking=True)
    
    def action_convert_to_maintenance_order(self):
        """Convertir ticket en orden de mantenimiento."""
        self.ensure_one()
        # Crear orden de mantenimiento directamente
        maintenance_order = self.env['maintenance.order'].create({
            'partner_id': self.partner_id.id if self.partner_id else False,
            'description': (self.name or '') + '\n\n' + (self.description or ''),
        })
        self.maintenance_order_id = maintenance_order.id
        self.message_post(body=_('Se creó una orden de mantenimiento: %s') % maintenance_order.name)
        return {
            'name': _('Orden de Mantenimiento'),
            'type': 'ir.actions.act_window',
            'res_model': 'maintenance.order',
            'res_id': maintenance_order.id,
            'view_mode': 'form',
            'target': 'current',
        }
