# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import datetime, date
import logging

_logger = logging.getLogger(__name__)


def _parse_start_dt(start_dt):
    """Convierte start_dt a datetime para calcular delta."""
    if not start_dt:
        return None
    try:
        if isinstance(start_dt, str):
            return getattr(fields.Datetime, 'from_string', lambda x: x)(start_dt) or None
        if isinstance(start_dt, date) and not isinstance(start_dt, datetime):
            return datetime.combine(start_dt, datetime.min.time())
        return start_dt
    except Exception:
        return None


def _elapsed_hours(line, now=None):
    """Calcula horas transcurridas desde timer_start (o date) hasta now."""
    now = now or fields.Datetime.now()
    start_dt = getattr(line, 'timer_start', None) or (line.date if hasattr(line, 'date') else None)
    start_dt = _parse_start_dt(start_dt)
    if not start_dt:
        return None
    try:
        delta = now - start_dt
        return max(0.0, min(delta.total_seconds() / 3600.0, 24.0))
    except (TypeError, ValueError):
        return None


class AccountAnalyticLine(models.Model):
    """
    Extensión para que al detener el temporizador en un ticket (Helpdesk),
    el campo "Tiempo utilizado" use el tiempo REAL transcurrido (cronómetro).
    - action_timer_stop: fija unit_amount antes de abrir el wizard.
    - write: si guardan unit_amount y la línea tenía timer en marcha, corregimos al tiempo real.
    - Por categoría del ticket: "Usar tiempo real" fuerza cronómetro; "Tiempo mínimo" exige mínimo de horas.
    """
    _inherit = 'account.analytic.line'

    def _get_helpdesk_ticket(self):
        """Obtiene el ticket de mesa de ayuda asociado a esta línea (vía helpdesk_ticket_id o task_id)."""
        self.ensure_one()
        if hasattr(self, 'helpdesk_ticket_id') and self.helpdesk_ticket_id:
            return self.helpdesk_ticket_id
        if hasattr(self, 'task_id') and self.task_id and getattr(self.task_id, 'helpdesk_ticket_id', None):
            return self.task_id.helpdesk_ticket_id
        return self.env['helpdesk.ticket'].browse()

    def write(self, vals):
        """
        - Si la categoría del ticket tiene "Usar tiempo real del cronómetro", al guardar unit_amount
          se usa el tiempo transcurrido del timer si es mayor que lo escrito.
        - Si la categoría tiene "Tiempo mínimo por registro", se exige unit_amount >= mínimo.
        """
        if self.env.context.get('skip_timer_unit_amount_correct'):
            return super().write(vals)
        if 'unit_amount' not in vals or vals.get('unit_amount') is None:
            return super().write(vals)
        now = fields.Datetime.now()
        written = float(vals.get('unit_amount', 0) or 0)
        to_correct = {}
        HelpdeskTicket = self.env.get('helpdesk.ticket')
        HelpdeskCategory = self.env.get('helpdesk.ticket.category')
        for line in self:
            ticket = line._get_helpdesk_ticket() if HelpdeskTicket and HelpdeskCategory else None
            category = ticket.category_id if ticket else None
            # Solo forzar tiempo real si la categoría lo exige (o si no hay categoría, mantener comportamiento anterior)
            exigir_real = category and category.control_tiempo_registro == 'exigir_tiempo_real'
            if not category or exigir_real:
                elapsed = _elapsed_hours(line, now=now)
                if elapsed is not None and elapsed > 0 and written < elapsed - 0.001:
                    to_correct[line.id] = elapsed
            # Validar mínimo por categoría
            if category and category.control_tiempo_registro == 'minimo_horas' and (category.tiempo_minimo_horas or 0) > 0:
                final_amount = to_correct.get(line.id, written)
                if final_amount < category.tiempo_minimo_horas - 0.001:
                    raise ValidationError(_(
                        'Para la categoría "%s" el tiempo registrado no puede ser menor a %s horas por registro.',
                        category.complete_name or category.name,
                        category.tiempo_minimo_horas,
                    ))
        if not to_correct:
            return super().write(vals)
        for line in self:
            v = dict(vals)
            if line.id in to_correct:
                v['unit_amount'] = to_correct[line.id]
                _logger.info(
                    'mesa_ayuda_inventario: unit_amount corregido de %.4f a %.4f h (tiempo real) en line id=%s',
                    written, v['unit_amount'], line.id
                )
            line.with_context(skip_timer_unit_amount_correct=True).write(v)
        return True

    def action_timer_stop(self):
        """
        Antes de abrir el wizard "Confirmar el tiempo utilizado", fijamos
        unit_amount al tiempo real del cronómetro para que el modal lo muestre.
        Si el modal abre antes y muestra 00:15, write() lo corregirá al guardar.
        """
        now = fields.Datetime.now()
        for line in self:
            elapsed = _elapsed_hours(line, now=now)
            if elapsed is not None:
                line.unit_amount = elapsed
                _logger.debug(
                    'mesa_ayuda_inventario: timer stop - line id=%s, elapsed=%.4f h (%.1f min)',
                    line.id, elapsed, elapsed * 60
                )
        return super().action_timer_stop()

    def action_timer_pause(self):
        """
        En lugar de pausar de inmediato, crear una solicitud de pausa que debe
        ser autorizada por el jefe (líder del equipo). El temporizador sigue
        corriendo hasta que autoricen. Si autorizan, se usa el tiempo de solicitud.
        """
        if self.env.context.get('from_approved_pause_request'):
            return super().action_timer_pause()
        # Calcular tiempo transcurrido en este momento (igual que en action_timer_stop)
        now = fields.Datetime.now()
        PauseRequest = self.env['helpdesk.timer.pause.request']
        for line in self:
            start_dt = getattr(line, 'timer_start', None) or line.date
            time_at_request = 0.0
            if start_dt:
                try:
                    if isinstance(start_dt, str):
                        start_dt = getattr(fields.Datetime, 'from_string', lambda x: x)(start_dt) or start_dt
                    elif isinstance(start_dt, date) and not isinstance(start_dt, datetime):
                        start_dt = datetime.combine(start_dt, datetime.min.time())
                except Exception:
                    start_dt = None
                if start_dt:
                    delta = now - start_dt
                    time_at_request = max(0.0, min(delta.total_seconds() / 3600.0, 24.0))
            # Evitar solicitudes duplicadas pendientes
            existing = PauseRequest.search([
                ('analytic_line_id', '=', line.id),
                ('state', '=', 'pending'),
            ], limit=1)
            if existing:
                continue
            approver = PauseRequest._get_approver_for_line(line)
            PauseRequest.create({
                'analytic_line_id': line.id,
                'requested_by_id': self.env.user.id,
                'request_datetime': now,
                'time_at_request': time_at_request,
                'approver_to_notify_id': approver.id if approver else False,
            })
        # No llamar a super: el timer sigue corriendo hasta que autoricen
        return True
