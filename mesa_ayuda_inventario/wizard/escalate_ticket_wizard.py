# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class HelpdeskTicketEscalateWizard(models.TransientModel):
    """Wizard para escalar un ticket a otro equipo y/o otro responsable (ej. Nivel 2)."""
    _name = 'helpdesk.ticket.escalate.wizard'
    _description = 'Escalar ticket a otro equipo o responsable'

    ticket_id = fields.Many2one(
        'helpdesk.ticket',
        string='Ticket',
        required=True,
        readonly=True,
        ondelete='cascade',
    )
    team_id = fields.Many2one(
        'helpdesk.team',
        string='Nuevo equipo',
        help='Ej. Nivel 2. Dejar en blanco para no cambiar el equipo. Se configura en Mesa de Ayuda → Configuración → Equipos.',
    )
    user_id = fields.Many2one(
        'res.users',
        string='Asignar a',
        help='Responsable del ticket (y de la orden de mantenimiento enlazada, si existe).',
    )

    def action_escalate(self):
        """Aplicar escalación: cambiar equipo y/o asignado en el ticket."""
        self.ensure_one()
        vals = {}
        if self.team_id:
            vals['team_id'] = self.team_id.id
        if self.user_id:
            vals['user_id'] = self.user_id.id
        if not vals:
            return {'type': 'ir.actions.act_window_close'}
        self.ticket_id.write(vals)
        msg = _('Ticket escalado')
        if self.team_id:
            msg += _(': equipo → %s') % self.team_id.name
        if self.user_id:
            msg += _('; asignado a %s') % self.user_id.name
        self.ticket_id.message_post(body=msg)
        return {'type': 'ir.actions.act_window_close'}
