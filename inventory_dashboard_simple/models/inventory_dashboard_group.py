# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class InventoryDashboardGroup(models.Model):
    """Modelo para agrupar operaciones de inventario por tipo."""
    _name = 'inventory.dashboard.group'
    _description = 'Grupo de Operaciones de Inventario'
    _order = 'sequence, name'
    _active_name = 'active'

    name = fields.Char(string='Tipo de Operación', required=True)
    sequence = fields.Integer(string='Secuencia', default=10)
    operation_type = fields.Char(string='Código de Operación')
    picking_type_ids = fields.Many2many(
        'stock.picking.type',
        'dashboard_group_picking_type_rel',
        'group_id',
        'picking_type_id',
        string='Tipos de Operación',
    )
    active = fields.Boolean(string='Mostrar en Dashboard', default=True, help='Si está desactivado, este grupo no se mostrará en el dashboard')
    total_count = fields.Integer(string='Total', compute='_compute_counts', store=False)
    waiting_count = fields.Integer(string='En Espera', compute='_compute_counts', store=False)
    delay_count = fields.Integer(string='Con Demora', compute='_compute_counts', store=False)
    color = fields.Integer(string='Color', default=0)
    action_open_operations_data = fields.Text(compute='_compute_action_open_operations_data', store=False)

    @api.depends('picking_type_ids')
    def _compute_counts(self):
        """Calcular conteos de operaciones por estado."""
        for group in self:
            if not group.picking_type_ids:
                group.total_count = 0
                group.waiting_count = 0
                group.delay_count = 0
                continue

            # Buscar todas las operaciones de estos tipos
            pickings = self.env['stock.picking'].search([
                ('picking_type_id', 'in', group.picking_type_ids.ids),
                ('state', '!=', 'cancel'),
            ])
            
            # Separar por fecha programada
            from odoo import fields as odoo_fields
            from datetime import timedelta
            now = odoo_fields.Datetime.now()
            # Fecha de ayer (un día antes de hoy) - solo las que tienen al menos un día de retraso
            yesterday = now - timedelta(days=1)
            
            # Con demora: fecha programada con al menos un día de retraso y no completado (prioridad)
            delay = pickings.filtered(
                lambda p: p.scheduled_date and 
                p.scheduled_date < yesterday and 
                p.state not in ('done', 'cancel')
            )
            group.delay_count = len(delay)
            
            # En espera: operaciones que NO están con demora y están en estados pendientes
            # Incluye: draft, waiting, assigned, y también las de hoy o futuras
            waiting = pickings.filtered(
                lambda p: p.state not in ('done', 'cancel') and
                p not in delay and  # Excluir las que ya están en demora
                (not p.scheduled_date or p.scheduled_date >= yesterday)
            )
            group.waiting_count = len(waiting)
            
            # Total es la suma de en espera y con demora
            group.total_count = group.waiting_count + group.delay_count

    @api.depends('picking_type_ids', 'name')
    def _compute_action_open_operations_data(self):
        """Calcular los datos de la acción para abrir operaciones."""
        for group in self:
            if not group.picking_type_ids:
                group.action_open_operations_data = ''
                continue
            # Retornar un JSON con los datos necesarios
            import json
            action_data = {
                'name': group.name,
                'res_model': 'stock.picking',
                'domain': [('picking_type_id', 'in', group.picking_type_ids.ids)],
                'context': {
                    'search_default_waiting': 1,
                    'search_default_delay': 1,
                },
            }
            group.action_open_operations_data = json.dumps(action_data)

    def open_operations(self):
        """Abrir las operaciones de este grupo (método estándar para kanban click)."""
        self.ensure_one()
        if not self.picking_type_ids:
            return False
        
        return {
            'name': self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'domain': [('picking_type_id', 'in', self.picking_type_ids.ids)],
            'context': {
                'search_default_waiting': 1,
                'search_default_delay': 1,
            },
            'target': 'current',
        }

    def action_open_operations(self):
        """Abrir las operaciones de este grupo (alias para compatibilidad)."""
        return self.open_operations()
    
    def action_open(self):
        """Método estándar que Odoo busca cuando se hace clic en una tarjeta kanban."""
        self.ensure_one()
        if not self.picking_type_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin operaciones'),
                    'message': _('Este grupo no tiene tipos de operación asignados.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }
        return self.open_operations()

    @api.model
    def init_groups(self):
        """Inicializar grupos de operaciones basándose en los tipos de operación existentes."""
        _logger.info("Inicializando grupos de dashboard de inventario...")
        # Buscar todos los tipos de operación
        PickingType = self.env['stock.picking.type']
        
        # Definir grupos y sus criterios
        groups_config = [
            {
                'name': 'Recibidos',
                'sequence': 10,
                'code': 'incoming',
                'filter_name': None,
            },
            {
                'name': 'Traslados Internos',
                'sequence': 20,
                'code': 'internal',
                'filter_name': None,
            },
            {
                'name': 'Órdenes de Entrega',
                'sequence': 30,
                'code': 'outgoing',
                'filter_name': None,
            },
            {
                'name': 'Alistamiento',
                'sequence': 40,
                'code': 'outgoing',
                'filter_name': 'alistamiento',
            },
            {
                'name': 'Verificación',
                'sequence': 50,
                'code': 'internal',
                'filter_name': 'verificación',
            },
            {
                'name': 'Reparaciones',
                'sequence': 60,
                'code': 'internal',
                'filter_name': 'reparación',
            },
            {
                'name': 'Devoluciones',
                'sequence': 70,
                'code': 'incoming',
                'filter_name': 'devolución',
            },
            {
                'name': 'Salida',
                'sequence': 80,
                'code': 'outgoing',
                'filter_name': 'salida',
            },
            {
                'name': 'Transporte',
                'sequence': 90,
                'code': 'outgoing',
                'filter_name': 'transporte',
            },
        ]
        
        # Buscar grupos existentes
        existing_groups = self.search([])
        existing_names = existing_groups.mapped('name')
        
        # Crear grupos que no existen
        for group_config in groups_config:
            if group_config['name'] in existing_names:
                continue
                
            # Buscar tipos de operación
            domain = [('code', '=', group_config['code'])]
            picking_types = PickingType.search(domain)
            
            # Filtrar por nombre si es necesario
            if group_config['filter_name']:
                picking_types = picking_types.filtered(
                    lambda pt: group_config['filter_name'].lower() in pt.name.lower()
                )
            
            # Si no hay tipos específicos pero hay del código general, usar todos
            if not picking_types and group_config['filter_name']:
                picking_types = PickingType.search([('code', '=', group_config['code'])])
            
            # Crear el grupo solo si hay tipos de operación
            if picking_types:
                try:
                    group = self.create({
                        'name': group_config['name'],
                        'sequence': group_config['sequence'],
                        'operation_type': group_config['code'],
                        'picking_type_ids': [(6, 0, picking_types.ids)],
                    })
                    _logger.info("Grupo creado: %s con %d tipos de operación", group_config['name'], len(picking_types))
                except Exception as e:
                    # Si falla, loguear y continuar con el siguiente
                    _logger.warning("Error creando grupo %s: %s", group_config['name'], str(e))
                    continue
        
        _logger.info("Inicialización de grupos completada")


