# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class AddEquipmentWizard(models.TransientModel):
    """Wizard para seleccionar múltiples equipos y agregarlos a la orden de mantenimiento."""
    _name = 'add.equipment.wizard'
    _description = 'Wizard: Agregar Equipos a Orden'

    maintenance_order_id = fields.Many2one(
        'maintenance.order',
        string='Orden de Mantenimiento',
        required=True,
        readonly=True
    )
    
    partner_id = fields.Many2one(
        'res.partner',
        related='maintenance_order_id.partner_id',
        string='Cliente',
        readonly=True
    )
    
    equipment_ids = fields.Many2many(
        'stock.lot',
        'add_equipment_wizard_lot_rel',
        'wizard_id',
        'lot_id',
        string='Equipos',
        domain="[('customer_id', '=', partner_id), ('is_main_product', '=', True)]",
        help='Equipos del cliente (inventario de clientes)'
    )
    
    maintenance_type = fields.Selection([
        ('preventive', 'Mantenimiento Preventivo'),
        ('corrective', 'Mantenimiento Correctivo'),
        ('remote_support', 'Soporte Técnico Remoto'),
        ('onsite_support', 'Soporte Técnico en Sitio'),
        ('diagnosis', 'Diagnóstico y Evaluación'),
        ('installation', 'Instalación y Configuración'),
        ('server_implementation', 'Implementación de Servidores'),
        ('server_migration', 'Migración de Servidores'),
        ('backup_recovery', 'Backup y Recuperación'),
        ('firewall_vpn', 'Firewall y VPN'),
        ('licensing_m365', 'Licenciamiento M365'),
        ('admin_m365', 'Administración M365'),
    ], string='Tipo de Mantenimiento', default='preventive', required=True)
    
    @api.model
    def default_get(self, fields_list):
        """Cargar equipos disponibles cuando se crea el wizard."""
        res = super().default_get(fields_list)
        if 'maintenance_order_id' in res and res['maintenance_order_id']:
            order = self.env['maintenance.order'].browse(res['maintenance_order_id'])
            if order.partner_id:
                res['partner_id'] = order.partner_id.id
                available_lots = self._get_available_equipment(order)
                if available_lots:
                    res['equipment_ids'] = [(6, 0, available_lots.ids)]
        return res
    
    def _get_available_equipment(self, order):
        """Obtener equipos disponibles del cliente (stock.lot) para la orden."""
        if not order or not order.partner_id:
            return self.env['stock.lot']
        try:
            lots = self.env['stock.lot'].search([
                ('customer_id', '=', order.partner_id.id),
                ('is_main_product', '=', True),
            ])
            computo_lots = lots.filtered(
                lambda l: l.product_id and (
                    not l.product_id.classification or
                    l.product_id.classification not in ('component', 'peripheral', 'complement')
                )
            )
            existing_lot_ids = order.maintenance_ids.mapped('lot_id').ids
            return computo_lots.filtered(lambda l: l.id not in existing_lot_ids)
        except Exception as e:
            _logger.error("Error al obtener equipos disponibles: %s", str(e))
            return self.env['stock.lot']
    
    @api.onchange('partner_id')
    def _onchange_partner_id_load_equipment(self):
        if self.partner_id and self.maintenance_order_id:
            self.equipment_ids = [(6, 0, self._get_available_equipment(self.maintenance_order_id).ids)]
    
    def action_add_equipment(self):
        """Agregar los equipos seleccionados a la orden de mantenimiento."""
        if not self.equipment_ids:
            raise UserError(_('Debe seleccionar al menos un equipo para agregar a la orden.'))
        
        maintenance_vals = []
        for lot in self.equipment_ids:
            existing = self.env['stock.lot.maintenance'].search([
                ('maintenance_order_id', '=', self.maintenance_order_id.id),
                ('lot_id', '=', lot.id),
            ], limit=1)
            if not existing:
                technician_id = self.maintenance_order_id.technician_ids[0].id if self.maintenance_order_id.technician_ids else self.env.user.id
                maintenance_vals.append({
                    'lot_id': lot.id,
                    'maintenance_order_id': self.maintenance_order_id.id,
                    'maintenance_date': self.maintenance_order_id.scheduled_date,
                    'maintenance_type': self.maintenance_type,
                    'technician_id': technician_id,
                    'status': 'draft',
                    'description': _('Mantenimiento programado desde orden %s') % self.maintenance_order_id.name,
                })
        
        if maintenance_vals:
            self.env['stock.lot.maintenance'].create(maintenance_vals)
            # ✅ Actualizar el ticket con los nuevos equipos
            self.maintenance_order_id._update_ticket_with_equipment()
        
        return {'type': 'ir.actions.act_window_close'}

