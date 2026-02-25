# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class HelpdeskTimerPauseRequest(models.Model):
    """
    Solicitud de pausa del temporizador de un ticket. El técnico pide pausar;
    un responsable (jefe del equipo o manager) debe autorizar. Mientras tanto
    el temporizador sigue corriendo. Si autoriza, se toma el tiempo de solicitud.
    """
    _name = 'helpdesk.timer.pause.request'
    _description = 'Solicitud de pausa del temporizador'
    _order = 'request_datetime desc'

    name = fields.Char(string='Referencia', compute='_compute_name', store=True, readonly=True)
    analytic_line_id = fields.Many2one(
        'account.analytic.line',
        string='Línea de hoja de horas',
        required=True,
        ondelete='cascade',
        readonly=True,
    )
    requested_by_id = fields.Many2one(
        'res.users',
        string='Solicitado por',
        required=True,
        readonly=True,
        default=lambda self: self.env.user,
    )
    request_datetime = fields.Datetime(string='Fecha/hora solicitud', required=True, readonly=True, default=fields.Datetime.now)
    time_at_request = fields.Float(
        string='Tiempo en solicitud (h)',
        readonly=True,
        help='Tiempo transcurrido en el momento de la solicitud (horas). Al autorizar, la pausa usará este valor.',
    )
    state = fields.Selection([
        ('pending', 'Pendiente de autorización'),
        ('approved', 'Autorizada'),
        ('rejected', 'Rechazada'),
    ], string='Estado', default='pending', required=True, copy=False)
    approver_id = fields.Many2one('res.users', string='Autorizado/Rechazado por', readonly=True)
    approve_datetime = fields.Datetime(string='Fecha/hora resolución', readonly=True)
    rejection_reason = fields.Char(string='Motivo rechazo', readonly=True)
    # Quién debe autorizar (jefe / líder del equipo). Informativo para la vista.
    approver_to_notify_id = fields.Many2one(
        'res.users',
        string='Pendiente para (autorizador)',
        readonly=True,
        help='Usuario que debe autorizar o rechazar la pausa (p. ej. líder del equipo).',
    )

    @api.depends('analytic_line_id', 'request_datetime')
    def _compute_name(self):
        for rec in self:
            if rec.analytic_line_id and rec.request_datetime:
                rec.name = _('Pausa %s - %s') % (
                    rec.analytic_line_id.display_name or rec.analytic_line_id.id,
                    fields.Datetime.to_string(rec.request_datetime),
                )
            else:
                rec.name = _('Solicitud de pausa')

    def _get_approver_for_line(self, line):
        """Obtener el usuario que puede autorizar (jefe): líder del equipo del ticket o grupo manager."""
        approver = self.env.user
        ticket = None
        if hasattr(line, 'helpdesk_ticket_id') and line.helpdesk_ticket_id:
            ticket = line.helpdesk_ticket_id
        elif hasattr(line, 'task_id') and line.task_id and getattr(line.task_id, 'helpdesk_ticket_id', None):
            ticket = line.task_id.helpdesk_ticket_id
        if ticket and getattr(ticket, 'team_id', None) and ticket.team_id:
            leader = getattr(ticket.team_id, 'user_id', None) or getattr(ticket.team_id, 'leader_id', None)
            if leader:
                approver = leader
        if approver == self.env.user:
            # El solicitante no puede ser su propio aprobador: usar grupo manager
            group = self.env.ref('stock.group_stock_manager', raise_if_not_found=False)
            if group and group.users:
                approver = group.users[0]
        return approver

    @api.model
    def _get_approver_for_line(self, line):
        """Obtener el usuario que puede autorizar (jefe): líder del equipo del ticket o grupo manager."""
        approver = self.env.user
        ticket = None
        if hasattr(line, 'helpdesk_ticket_id') and line.helpdesk_ticket_id:
            ticket = line.helpdesk_ticket_id
        elif hasattr(line, 'task_id') and line.task_id and getattr(line.task_id, 'helpdesk_ticket_id', None):
            ticket = line.task_id.helpdesk_ticket_id
        if ticket and getattr(ticket, 'team_id', None) and ticket.team_id:
            leader = getattr(ticket.team_id, 'user_id', None) or getattr(ticket.team_id, 'leader_id', None)
            if leader:
                approver = leader
        if approver == self.env.user:
            group = self.env.ref('stock.group_stock_manager', raise_if_not_found=False)
            if group and group.users:
                approver = group.users[0]
        return approver

    def _can_approve_or_reject(self):
        """Solo el responsable (approver_to_notify_id) o un manager pueden aprobar/rechazar."""
        self.ensure_one()
        if self.env.user.has_group('stock.group_stock_manager'):
            return True
        return self.approver_to_notify_id and self.approver_to_notify_id == self.env.user

    def action_approve(self):
        """El jefe autoriza: aplicamos la pausa con el tiempo de solicitud y cerramos la solicitud."""
        self.ensure_one()
        if not self._can_approve_or_reject():
            raise UserError(_('No tiene permiso para autorizar esta solicitud. Solo el responsable indicado o un administrador pueden hacerlo.'))
        if self.state != 'pending':
            raise UserError(_('Solo se pueden autorizar solicitudes en estado Pendiente.'))
        line = self.analytic_line_id
        if not line.exists():
            raise UserError(_('La línea de hoja de horas ya no existe.'))
        # Fijar el tiempo al momento de la solicitud (no al de la autorización)
        if self.time_at_request is not None and self.time_at_request >= 0:
            line.unit_amount = self.time_at_request
        # Llamar a la pausa real sin crear otra solicitud (contexto para saltar nuestro override)
        if hasattr(line, 'action_timer_pause'):
            line.with_context(from_approved_pause_request=True).action_timer_pause()
        self.write({
            'state': 'approved',
            'approver_id': self.env.user.id,
            'approve_datetime': fields.Datetime.now(),
        })
        return True

    def action_reject(self):
        """El jefe rechaza: el temporizador sigue corriendo, solo cerramos la solicitud."""
        self.ensure_one()
        if not self._can_approve_or_reject():
            raise UserError(_('No tiene permiso para rechazar esta solicitud. Solo el responsable indicado o un administrador pueden hacerlo.'))
        if self.state != 'pending':
            raise UserError(_('Solo se pueden rechazar solicitudes en estado Pendiente.'))
        self.write({
            'state': 'rejected',
            'approver_id': self.env.user.id,
            'approve_datetime': fields.Datetime.now(),
        })
        return True
