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
        string='Equipos de la Empresa',
        domain="[('customer_id', '=', partner_id), ('is_main_product', '=', True)]",
        help='Equipos de la empresa ubicados en el cliente (stock.lot)'
    )
    
    own_equipment_ids = fields.Many2many(
        'customer.own.inventory',
        'add_equipment_wizard_own_rel',
        'wizard_id',
        'own_inventory_id',
        string='Equipos Propios del Cliente',
        domain="[('partner_id', '=', partner_id)]",
        help='Equipos que son propiedad del cliente (customer.own.inventory)'
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
                # Cargar equipos disponibles
                available_lots, available_own = self._get_available_equipment(order)
                if available_lots:
                    res['equipment_ids'] = [(6, 0, available_lots.ids)]
                if available_own:
                    res['own_equipment_ids'] = [(6, 0, available_own.ids)]
        return res
    
    def _get_available_equipment(self, order):
        """Obtener equipos disponibles del cliente para la orden."""
        if not order or not order.partner_id:
            return self.env['stock.lot'], self.env['customer.own.inventory']
        
        try:
            # Buscar lotes del cliente que sean productos principales
            lots = self.env['stock.lot'].search([
                ('customer_id', '=', order.partner_id.id),
                ('is_main_product', '=', True),
            ])
            
            # Filtrar solo productos "computo" (no componentes/periféricos/complementos)
            computo_lots = lots.filtered(
                lambda l: l.product_id and (
                    not l.product_id.classification or 
                    l.product_id.classification not in ('component', 'peripheral', 'complement')
                )
            )
            
            # Excluir los lotes que ya están en la orden
            existing_lot_ids = order.maintenance_ids.mapped('lot_id').ids
            available_lots = computo_lots.filtered(lambda l: l.id not in existing_lot_ids)
            
            # Buscar productos propios del cliente
            if 'customer.own.inventory' in self.env:
                own_products = self.env['customer.own.inventory'].search([
                    ('partner_id', '=', order.partner_id.id),
                    ('status', 'in', ['active', 'maintenance']),  # Solo productos activos o en mantenimiento
                ])
                # Excluir productos propios que ya están en la orden
                existing_own_ids = order.maintenance_ids.mapped('own_inventory_id').ids
                available_own = own_products.filtered(lambda p: p.id not in existing_own_ids)
            else:
                available_own = self.env['customer.own.inventory']
            
            return available_lots, available_own
        except Exception as e:
            _logger.error("Error al obtener equipos disponibles: %s", str(e))
            return self.env['stock.lot'], self.env['customer.own.inventory']
    
    @api.onchange('partner_id')
    def _onchange_partner_id_load_equipment(self):
        """Cargar equipos disponibles del cliente al seleccionar cliente."""
        if self.partner_id and self.maintenance_order_id:
            order = self.maintenance_order_id
            available_lots, available_own = self._get_available_equipment(order)
            self.equipment_ids = [(6, 0, available_lots.ids)]
            self.own_equipment_ids = [(6, 0, available_own.ids)]
    
    def action_add_equipment(self):
        """Agregar los equipos seleccionados a la orden de mantenimiento."""
        if not self.equipment_ids and not self.own_equipment_ids:
            raise UserError(_('Debe seleccionar al menos un equipo para agregar a la orden.'))
        
        # Crear mantenimientos individuales para cada equipo seleccionado
        maintenance_vals = []
        
        # Agregar equipos de stock.lot (inventario de la empresa)
        for lot in self.equipment_ids:
            # Verificar que no exista ya un mantenimiento para este lote en esta orden
            existing = self.env['stock.lot.maintenance'].search([
                ('maintenance_order_id', '=', self.maintenance_order_id.id),
                ('lot_id', '=', lot.id),
                ('own_inventory_id', '=', False),
            ], limit=1)
            if not existing:
                # Asignar el primer técnico como técnico principal del mantenimiento
                technician_id = self.maintenance_order_id.technician_ids[0].id if self.maintenance_order_id.technician_ids else self.env.user.id
                maintenance_vals.append({
                    'lot_id': lot.id,
                    'own_inventory_id': False,
                    'maintenance_order_id': self.maintenance_order_id.id,
                    'maintenance_date': self.maintenance_order_id.scheduled_date,
                    'maintenance_type': self.maintenance_type,
                    'technician_id': technician_id,
                    'status': 'draft',
                    'description': _('Mantenimiento programado desde orden %s') % self.maintenance_order_id.name,
                })
        
        # Agregar equipos propios del cliente (customer.own.inventory)
        for own_product in self.own_equipment_ids:
            # Verificar que no exista ya un mantenimiento para este producto propio en esta orden
            existing = self.env['stock.lot.maintenance'].search([
                ('maintenance_order_id', '=', self.maintenance_order_id.id),
                ('own_inventory_id', '=', own_product.id),
                ('lot_id', '=', False),
            ], limit=1)
            if not existing:
                # Asignar el primer técnico como técnico principal del mantenimiento
                technician_id = self.maintenance_order_id.technician_ids[0].id if self.maintenance_order_id.technician_ids else self.env.user.id
                maintenance_vals.append({
                    'lot_id': False,
                    'own_inventory_id': own_product.id,
                    'maintenance_order_id': self.maintenance_order_id.id,
                    'maintenance_date': self.maintenance_order_id.scheduled_date,
                    'maintenance_type': self.maintenance_type,
                    'technician_id': technician_id,
                    'status': 'draft',
                    'description': _('Mantenimiento programado desde orden %s - Equipo Propio del Cliente') % self.maintenance_order_id.name,
                })
        
        if maintenance_vals:
            self.env['stock.lot.maintenance'].create(maintenance_vals)
            # ✅ Actualizar el ticket con los nuevos equipos
            self.maintenance_order_id._update_ticket_with_equipment()
        
        return {'type': 'ir.actions.act_window_close'}

