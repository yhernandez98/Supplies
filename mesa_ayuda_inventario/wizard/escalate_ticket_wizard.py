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
        help='Ej. Nivel 2. Al elegir equipo se asigna automáticamente el primer miembro del equipo. Se configura en Mesa de Ayuda → Configuración → Equipos.',
    )
    user_id = fields.Many2one(
        'res.users',
        string='Asignar a',
        help='Se rellena automáticamente según la regla del equipo: mismo número de tickets abiertos (balanceo). Puede cambiarse si lo desea.',
    )
    escalation_reason = fields.Text(
        string='Motivo de escalación',
        help='Indique por qué se escala este ticket (ej. requiere especialista, cliente solicitó nivel 2, etc.).',
    )

    def _get_team_member_least_open_tickets(self, team):
        """
        Igual que la asignación automática del equipo: el usuario con menos tickets abiertos.
        Respeta la lógica "Cada usuario tiene el mismo número de tickets abiertos".
        """
        members = getattr(team, 'member_ids', self.env['res.users'])
        if not members:
            return getattr(team, 'user_id', None)
        Ticket = self.env['helpdesk.ticket']
        # Tickets abiertos: no están en etapa "cerrada" (stage.fold=True en Odoo)
        best_user = None
        best_count = None
        for user in members:
            count = Ticket.search_count([
                ('user_id', '=', user.id),
                ('team_id', '=', team.id),
                ('stage_id.fold', '=', False),
            ])
            if best_count is None or count < best_count:
                best_count = count
                best_user = user
        return best_user

    @api.onchange('team_id')
    def _onchange_team_id_assign_user(self):
        """Asignar automáticamente como en el equipo: al miembro con menos tickets abiertos (balanceo)."""
        if self.team_id:
            self.user_id = self._get_team_member_least_open_tickets(self.team_id)
        else:
            self.user_id = False

    def action_escalate(self):
        """Aplicar escalación: cambiar equipo y/o asignado en el ticket y registrar motivo."""
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
        if self.escalation_reason:
            msg += _('<br/><br/><strong>Motivo:</strong> %s') % self.escalation_reason
        self.ticket_id.message_post(body=msg)
        return {'type': 'ir.actions.act_window_close'}
