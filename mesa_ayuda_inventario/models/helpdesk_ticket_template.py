# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class HelpdeskTicketTemplate(models.Model):
    """Plantillas para crear tickets con valores por defecto (categoría, descripción, prioridad, equipo)."""
    _name = 'helpdesk.ticket.template'
    _description = 'Plantilla de ticket'

    name = fields.Char(string='Nombre', required=True)
    category_id = fields.Many2one('helpdesk.ticket.category', string='Categoría')
    team_id = fields.Many2one('helpdesk.team', string='Equipo')
    description = fields.Html(string='Descripción por defecto')
    priority = fields.Selection([
        ('0', 'Baja'),
        ('1', 'Normal'),
        ('2', 'Alta'),
        ('3', 'Muy alta'),
    ], string='Prioridad')

    def action_create_ticket(self):
        """Abrir formulario de nuevo ticket con valores de la plantilla."""
        self.ensure_one()
        return {
            'name': _('Nuevo ticket'),
            'type': 'ir.actions.act_window',
            'res_model': 'helpdesk.ticket',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_name': self.name,
                'default_category_id': self.category_id.id,
                'default_team_id': self.team_id.id,
                'default_description': self.description or '',
                'default_priority': self.priority if self.priority else '1',
            },
        }
