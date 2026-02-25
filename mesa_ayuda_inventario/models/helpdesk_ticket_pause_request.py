# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class HelpdeskTicketPauseRequest(models.Model):
    """
    Solicitud de pausa del cronómetro propio de un ticket. Al mover el ticket a "En espera"
    se crea esta solicitud; el cronómetro sigue sumando hasta que un responsable la apruebe.
    Si aprueba: se pausa (se acumula el tiempo y se detiene). Si rechaza: el tiempo sigue sumando.
    """
    _name = 'helpdesk.ticket.pause.request'
    _description = 'Solicitud de pausa (cronómetro del ticket)'
    _order = 'request_datetime desc'

    name = fields.Char(string='Referencia', compute='_compute_name', store=True, readonly=True)
    ticket_id = fields.Many2one(
        'helpdesk.ticket',
        string='Ticket',
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
        help='Tiempo transcurrido en el momento de la solicitud. Al autorizar, la pausa usará este valor como acumulado.',
    )
    state = fields.Selection([
        ('pending', 'Pendiente de autorización'),
        ('approved', 'Autorizada'),
        ('rejected', 'Rechazada'),
    ], string='Estado', default='pending', required=True, copy=False)
    approver_id = fields.Many2one('res.users', string='Autorizado/Rechazado por', readonly=True)
    approve_datetime = fields.Datetime(string='Fecha/hora resolución', readonly=True)
    rejection_reason = fields.Char(string='Motivo rechazo', readonly=True)
    approver_to_notify_id = fields.Many2one(
        'res.users',
        string='Pendiente para (autorizador)',
        readonly=True,
        help='Usuario que debe autorizar o rechazar (líder del equipo o manager).',
    )

    @api.depends('ticket_id', 'request_datetime')
    def _compute_name(self):
        for rec in self:
            if rec.ticket_id and rec.request_datetime:
                rec.name = _('Pausa %s - %s') % (
                    rec.ticket_id.name or '#%s' % rec.ticket_id.id,
                    fields.Datetime.to_string(rec.request_datetime),
                )
            else:
                rec.name = _('Solicitud de pausa (ticket)')

    @api.model
    def _get_approver_for_ticket(self, ticket):
        """Quién puede autorizar: líder del equipo del ticket o un manager."""
        approver = self.env.user
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
        self.ensure_one()
        if self.env.user.has_group('stock.group_stock_manager'):
            return True
        return self.approver_to_notify_id and self.approver_to_notify_id == self.env.user

    def action_approve(self):
        """Aprobar: pausar el cronómetro del ticket (acumular tiempo y detener)."""
        self.ensure_one()
        if not self._can_approve_or_reject():
            raise UserError(_('No tiene permiso para autorizar. Solo el responsable indicado o un administrador pueden hacerlo.'))
        if self.state != 'pending':
            raise UserError(_('Solo se pueden autorizar solicitudes en estado Pendiente.'))
        ticket = self.ticket_id
        if not ticket.exists():
            raise UserError(_('El ticket ya no existe.'))
        # Pausar: acumular el tiempo de la solicitud y detener el cronómetro
        hours = self.time_at_request if self.time_at_request is not None else 0
        ticket.write({
            'custom_timer_accumulated_hours': (ticket.custom_timer_accumulated_hours or 0) + hours,
            'custom_timer_start': False,
        })
        ticket.message_post(body=_('Solicitud de pausa autorizada. Cronómetro pausado (acumulado +%s h).') % round(hours, 2))
        self.write({
            'state': 'approved',
            'approver_id': self.env.user.id,
            'approve_datetime': fields.Datetime.now(),
        })
        _logger.info('mesa_ayuda_inventario: ticket pause request approved ticket=%s request=%s', ticket.name, self.id)
        return True

    def action_reject(self):
        """Rechazar: el cronómetro sigue sumando, solo se cierra la solicitud."""
        self.ensure_one()
        if not self._can_approve_or_reject():
            raise UserError(_('No tiene permiso para rechazar. Solo el responsable indicado o un administrador pueden hacerlo.'))
        if self.state != 'pending':
            raise UserError(_('Solo se pueden rechazar solicitudes en estado Pendiente.'))
        self.write({
            'state': 'rejected',
            'approver_id': self.env.user.id,
            'approve_datetime': fields.Datetime.now(),
        })
        if self.ticket_id.exists():
            self.ticket_id.message_post(body=_('Solicitud de pausa rechazada. El cronómetro sigue en marcha.'))
        return True
