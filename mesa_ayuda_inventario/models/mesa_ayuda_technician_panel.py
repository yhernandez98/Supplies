# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class MesaAyudaTechnicianPanel(models.TransientModel):
    """Panel orientado al técnico conectado: accesos filtrados por su usuario."""
    _name = 'mesa.ayuda.technician.panel'
    _description = 'Panel técnico (visitas asignadas)'

    user_id = fields.Many2one(
        'res.users',
        string='Técnico',
        default=lambda self: self.env.user,
        required=True,
        readonly=True,
    )
    visit_count = fields.Integer(
        string='Visitas activas',
        compute='_compute_visit_count',
    )

    @api.depends('user_id')
    def _compute_visit_count(self):
        Mo = self.env['maintenance.order']
        for panel in self:
            uid = panel.user_id.id if panel.user_id else panel.env.user.id
            panel.visit_count = Mo.search_count([
                ('technician_ids', 'in', [uid]),
                ('state', 'in', ('draft', 'scheduled', 'in_progress')),
            ])

    @api.model
    def action_open_panel(self):
        """Abre el panel técnico en ventana emergente (usuario actual)."""
        panel = self.create({'user_id': self.env.user.id})
        return {
            'type': 'ir.actions.act_window',
            'name': _('Panel técnico'),
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': panel.id,
            'target': 'new',
        }

    def action_open_assigned_visits(self):
        """Listado emergente de órdenes de visita donde participa el técnico conectado."""
        self.ensure_one()
        uid = self.user_id.id or self.env.user.id
        list_view = self.env.ref('mesa_ayuda_inventario.view_maintenance_order_list_technician_assigned')
        form_view = self.env.ref('mesa_ayuda_inventario.view_maintenance_order_form')
        search_view = self.env.ref('mesa_ayuda_inventario.view_maintenance_order_search_technician_assigned')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Visitas asignadas'),
            'res_model': 'maintenance.order',
            'view_mode': 'list,form',
            'views': [(list_view.id, 'list'), (form_view.id, 'form')],
            'search_view_id': search_view.id,
            'domain': [
                ('technician_ids', 'in', [uid]),
                ('state', 'in', ('draft', 'scheduled', 'in_progress')),
            ],
            # Sin barra de búsqueda/filtros (js_class mesa_technician_visit_list); más registros por página.
            'limit': 200,
            'context': {
                'create': False,
            },
            'target': 'new',
        }
