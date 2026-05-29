# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

# Estados Odoo stock.picking para el desglose de la caja TOTAL (sin Hecho ni Cancelado).
_PICKING_WAITING_FLOW_STATES = frozenset({'draft', 'waiting', 'confirmed'})
_PICKING_READY_STATE = 'assigned'
_PICKING_EXCLUDED_STATES = frozenset({'done', 'cancel'})


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
    open_status_count = fields.Integer(
        string='En Espera',
        compute='_compute_counts',
        store=False,
        help='Albaranes en borrador / en espera / confirmado (no Listo, Hecho ni Cancelado).',
    )
    done_status_count = fields.Integer(
        string='Listo',
        compute='_compute_counts',
        store=False,
        help='Albaranes en estado Listo (assigned). No incluye Hecho.',
    )
    open_status_label = fields.Char(
        string='Etiqueta pendientes',
        compute='_compute_status_labels',
        store=False,
    )
    done_status_label = fields.Char(
        string='Etiqueta terminadas',
        compute='_compute_status_labels',
        store=False,
    )
    waiting_count = fields.Integer(
        string='Sin Vencer',
        compute='_compute_counts',
        store=False,
        help='Operaciones activas cuya fecha programada no está vencida (hoy, futura o sin fecha).',
    )
    delay_count = fields.Integer(string='Con Demora', compute='_compute_counts', store=False)
    color = fields.Integer(string='Color', default=0)
    action_open_operations_data = fields.Text(compute='_compute_action_open_operations_data', store=False)

    @api.depends('picking_type_ids')
    def _compute_status_labels(self):
        """Etiquetas del desglose TOTAL (mismos nombres que en la lista de albaranes)."""
        label_waiting = _('En Espera')
        label_ready = _('Listo')
        for group in self:
            group.open_status_label = label_waiting
            group.done_status_label = label_ready

    @api.depends('picking_type_ids')
    def _compute_counts(self):
        """Conteos: TOTAL = En Espera + Listo; sin Hecho ni Cancelado."""
        from datetime import timedelta

        now = fields.Datetime.now()
        yesterday = now - timedelta(days=1)

        for group in self:
            if not group.picking_type_ids:
                group.total_count = 0
                group.open_status_count = 0
                group.done_status_count = 0
                group.waiting_count = 0
                group.delay_count = 0
                continue

            rows = self.env['stock.picking'].search_read(
                [
                    ('picking_type_id', 'in', group.picking_type_ids.ids),
                    ('state', 'not in', list(_PICKING_EXCLUDED_STATES)),
                ],
                ['scheduled_date', 'state'],
            )

            delay_count = 0
            waiting_count = 0
            waiting_flow_count = 0
            ready_count = 0
            for row in rows:
                state = row.get('state')
                if state in _PICKING_EXCLUDED_STATES:
                    continue
                if state == _PICKING_READY_STATE:
                    ready_count += 1
                elif state in _PICKING_WAITING_FLOW_STATES:
                    waiting_flow_count += 1
                else:
                    continue

                sched = row.get('scheduled_date')
                sched_dt = fields.Datetime.to_datetime(sched) if sched else False
                if sched_dt and sched_dt < yesterday:
                    delay_count += 1
                else:
                    waiting_count += 1

            group.open_status_count = waiting_flow_count
            group.done_status_count = ready_count
            group.total_count = waiting_flow_count + ready_count
            group.delay_count = delay_count
            group.waiting_count = waiting_count

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
                    'search_default_available': 1,
                },
            }
            group.action_open_operations_data = json.dumps(action_data)

    @api.model
    def _stock_picking_dashboard_views(self):
        """Lista/form estándar de Inventario (no la vista custom de Facturación)."""
        def _view_id(xmlid):
            view = self.env.ref(xmlid, raise_if_not_found=False)
            return view.sudo().id if view else False

        list_id = _view_id('stock.vpicktree') or _view_id('stock.view_picking_tree')
        form_id = _view_id('stock.view_picking_form')
        views = []
        if list_id:
            views.append((list_id, 'list'))
        if form_id:
            views.append((form_id, 'form'))
        return views

    def open_operations(self):
        """Abrir las operaciones de este grupo (método estándar para kanban click)."""
        self.ensure_one()
        if not self.picking_type_ids:
            return False

        action = {
            'name': self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'domain': [('picking_type_id', 'in', self.picking_type_ids.ids)],
            'context': {
                'search_default_available': 1,
            },
            'target': 'current',
        }
        views = self._stock_picking_dashboard_views()
        if views:
            action['views'] = views
            action['view_id'] = views[0][0]
        return action

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


