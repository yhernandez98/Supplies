# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class MaintenanceOrderWizard(models.TransientModel):
    """Wizard para crear orden de mantenimiento seleccionando equipos."""
    _name = 'maintenance.order.wizard'
    _description = 'Wizard: Crear Orden de Mantenimiento'

    maintenance_order_id = fields.Many2one(
        'maintenance.order',
        string='Orden de Mantenimiento',
        help='Orden existente a la cual agregar equipos (si se está editando)'
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        required=True,
        help='Cliente para el cual se creará la orden de mantenimiento'
    )
    
    technician_ids = fields.Many2many(
        'res.users',
        'maintenance_order_wizard_technician_rel',
        'wizard_id',
        'user_id',
        string='Técnicos Asignados',
        default=lambda self: [(6, 0, [self.env.user.id])] if self.env.user else False,
        required=True,
        help='Técnicos responsables de realizar el mantenimiento'
    )
    
    scheduled_date = fields.Datetime(
        string='Fecha Programada',
        required=True,
        default=fields.Datetime.now,
        help='Fecha y hora programada para realizar el mantenimiento'
    )
    
    deadline_date = fields.Datetime(
        string='Fecha Límite',
        help='Fecha límite para completar el mantenimiento'
    )
    
    description = fields.Text(
        string='Descripción',
        help='Descripción general de la orden de mantenimiento'
    )
    
    line_ids = fields.One2many(
        'maintenance.order.wizard.line',
        'wizard_id',
        string='Equipos',
        help='Equipos a incluir en la orden de mantenimiento'
    )
    
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """Cargar equipos del cliente al seleccionar cliente, filtrando por ubicación del cliente."""
        if self.partner_id:
            # Buscar lotes del cliente que sean productos principales (no component/peripheral/complement)
            # Filtrar por ubicación del cliente (customer_location_id)
            lots = self.env['stock.lot'].search([
                ('customer_id', '=', self.partner_id.id),
                ('is_main_product', '=', True),
            ])
            
            # Filtrar solo productos que NO tienen classification o tienen classification diferente a component/peripheral/complement
            # Esto identifica productos "computo"
            computo_lots = lots.filtered(
                lambda l: not l.product_id.classification or 
                l.product_id.classification not in ('component', 'peripheral', 'complement')
            )
            
            # Filtrar solo los que tienen stock en la ubicación del cliente
            # Obtener todas las ubicaciones del cliente
            partner_locations = self.env['stock.location'].search([
                ('partner_id', '=', self.partner_id.id),
            ])
            
            if partner_locations:
                # Filtrar lotes que tienen stock en alguna ubicación del cliente
                filtered_lots = self.env['stock.lot']
                for lot in computo_lots:
                    # Verificar si el lote tiene stock en alguna ubicación del cliente
                    quants = self.env['stock.quant'].search([
                        ('lot_id', '=', lot.id),
                        ('location_id', 'in', partner_locations.ids),
                        ('quantity', '>', 0),
                    ], limit=1)
                    if quants:
                        filtered_lots |= lot
                computo_lots = filtered_lots
            
            # Si hay una orden existente, excluir los lotes que ya están en esa orden
            if self.maintenance_order_id:
                existing_lot_ids = self.maintenance_order_id.maintenance_ids.mapped('lot_id').ids
                computo_lots = computo_lots.filtered(lambda l: l.id not in existing_lot_ids)
            
            # Crear líneas del wizard
            lines = []
            for lot in computo_lots:
                lines.append((0, 0, {
                    'lot_id': lot.id,
                    'product_id': lot.product_id.id,
                    'maintenance_type': 'preventive',
                }))
            
            self.line_ids = lines
    
    def action_create_order(self):
        """Crear la orden de mantenimiento con los equipos seleccionados o agregar a orden existente."""
        if not self.line_ids:
            raise UserError(_('Debe seleccionar al menos un equipo para crear la orden.'))
        
        # Si hay una orden existente, agregar equipos a ella
        if self.maintenance_order_id:
            order = self.maintenance_order_id
        else:
            # Crear la orden de mantenimiento
            order = self.env['maintenance.order'].create({
                'partner_id': self.partner_id.id,
                'technician_ids': [(6, 0, self.technician_ids.ids)],
                'scheduled_date': self.scheduled_date,
                'deadline_date': self.deadline_date,
                'description': self.description,
                'state': 'draft',
            })
        
        # Crear mantenimientos individuales para cada equipo seleccionado
        maintenance_vals = []
        for line in self.line_ids:
            if line.selected:
                # Verificar que no exista ya un mantenimiento para este lote en esta orden
                existing = self.env['stock.lot.maintenance'].search([
                    ('maintenance_order_id', '=', order.id),
                    ('lot_id', '=', line.lot_id.id),
                ], limit=1)
                if not existing:
                    # Asignar el primer técnico como técnico principal del mantenimiento
                    technician_id = self.technician_ids[0].id if self.technician_ids else self.env.user.id
                    maintenance_vals.append({
                        'lot_id': line.lot_id.id,
                        'maintenance_order_id': order.id,
                        'maintenance_date': self.scheduled_date,
                        'maintenance_type': line.maintenance_type,
                        'technician_id': technician_id,
                        'status': 'draft',
                        'description': line.description or _('Mantenimiento programado desde orden %s') % order.name,
                    })
        
        if maintenance_vals:
            self.env['stock.lot.maintenance'].create(maintenance_vals)
        
        # Abrir la vista de la orden
        return {
            'name': _('Orden de Mantenimiento'),
            'type': 'ir.actions.act_window',
            'res_model': 'maintenance.order',
            'res_id': order.id,
            'view_mode': 'form',
            'target': 'current',
        }


class MaintenanceOrderWizardLine(models.TransientModel):
    """Líneas del wizard para seleccionar equipos."""
    _name = 'maintenance.order.wizard.line'
    _description = 'Línea Wizard: Equipo para Mantenimiento'

    wizard_id = fields.Many2one(
        'maintenance.order.wizard',
        required=True,
        ondelete='cascade'
    )
    
    selected = fields.Boolean(
        string='Seleccionar',
        default=True,
        help='Marcar para incluir este equipo en la orden'
    )
    
    lot_id = fields.Many2one(
        'stock.lot',
        string='Número de Serie',
        required=True,
        help='Número de serie del equipo'
    )
    
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        required=True,
        help='Producto del equipo'
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
    
    description = fields.Text(
        string='Descripción',
        help='Descripción específica para este equipo'
    )

