# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class MesaAyudaServicePanel(models.TransientModel):
    """Panel de accesos rápidos (mantenimiento en campo). Las acciones se conectan paso a paso."""
    _name = 'mesa.ayuda.service.panel'
    _description = 'Panel operaciones de campo'
    _rec_name = 'display_name'

    display_name = fields.Char(
        string='Título',
        default=lambda self: _('Operaciones de campo'),
        readonly=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='Usuario',
        default=lambda self: self.env.user,
        required=True,
        readonly=True,
        index=True,
    )
    kpi_orders_open = fields.Integer(
        string='Órdenes activas',
        compute='_compute_kpis',
        readonly=True,
    )
    kpi_orders_done_month = fields.Integer(
        string='Órdenes completadas (mes)',
        compute='_compute_kpis',
        readonly=True,
    )
    kpi_lot_open = fields.Integer(
        string='Mantenimientos en curso',
        compute='_compute_kpis',
        readonly=True,
    )
    kpi_lot_done_month = fields.Integer(
        string='Mantenimientos completados (mes)',
        compute='_compute_kpis',
        readonly=True,
    )

    @api.depends()
    def _compute_kpis(self):
        """Se recalcula al abrir o recargar (F5) el formulario."""
        vals = self._prepare_kpi_vals()
        for panel in self:
            panel.kpi_orders_open = vals['kpi_orders_open']
            panel.kpi_orders_done_month = vals['kpi_orders_done_month']
            panel.kpi_lot_open = vals['kpi_lot_open']
            panel.kpi_lot_done_month = vals['kpi_lot_done_month']

    @api.model
    def _get_or_create_user_panel(self):
        """Un registro transitorio por usuario (no crea uno nuevo en cada entrada al menú)."""
        panel = self.search([('user_id', '=', self.env.uid)], limit=1)
        if not panel:
            panel = self.create({'user_id': self.env.uid})
        return panel

    @api.model
    def action_open_panel(self):
        panel = self._get_or_create_user_panel()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Operaciones de campo'),
            'res_model': 'mesa.ayuda.service.panel',
            'view_mode': 'form',
            'res_id': panel.id,
            'target': 'current',
        }

    @api.model
    def _prepare_kpi_vals(self):
        Mo = self.env['maintenance.order']
        Ml = self.env['stock.lot.maintenance']
        today = fields.Date.context_today(self)
        month_start = fields.Datetime.to_datetime(today.replace(day=1))
        return {
            'kpi_orders_open': Mo.search_count([
                ('state', 'in', ('draft', 'scheduled', 'in_progress')),
            ]),
            'kpi_orders_done_month': Mo.search_count([
                ('state', '=', 'completed'),
                ('scheduled_date', '>=', month_start),
            ]),
            'kpi_lot_open': Ml.search_count([
                ('status', 'in', ('draft', 'scheduled', 'in_progress', 'pending')),
            ]),
            'kpi_lot_done_month': Ml.search_count([
                ('status', '=', 'completed'),
                ('maintenance_date', '>=', month_start),
            ]),
        }

    def _notify_configure_next(self, feature_label):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Acción: %s') % feature_label,
                'message': _(
                    'Aquí conectaremos el comportamiento exacto en el siguiente paso, según lo que indique.'
                ),
                'type': 'info',
                'sticky': False,
            },
        }

    def action_panel_crear_ticket(self):
        self.ensure_one()
        return self._notify_configure_next(_('Crear ticket'))

    def action_panel_crear_reparacion(self):
        self.ensure_one()
        return self._notify_configure_next(_('Crear reparación'))

    def action_panel_cambio_equipo(self):
        self.ensure_one()
        return self.env['ir.actions.act_window']._for_xml_id(
            'mesa_ayuda_inventario.action_mesa_panel_equipment_change_wizard'
        )

    def action_panel_solicitar_elemento(self):
        self.ensure_one()
        return self._notify_configure_next(_('Solicitar elemento'))

    def action_open_visit_calendar(self):
        return self.env['ir.actions.act_window']._for_xml_id(
            'mesa_ayuda_inventario.action_maintenance_order_calendar'
        )

    def action_panel_retiro_usuario_equipo(self):
        """Abre el wizard de retiro sin pasar por el selector de solicitudes."""
        return self.env['ir.actions.act_window']._for_xml_id(
            'mesa_ayuda_inventario.action_mesa_service_retiro_usuario_equipo_wizard'
        )
