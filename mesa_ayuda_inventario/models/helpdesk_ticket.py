# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
<<<<<<< HEAD
=======
from datetime import datetime, timedelta
>>>>>>> fb2d0eddb44261c7833d37e32b0869ec9bdb22c2
import logging

_logger = logging.getLogger(__name__)

<<<<<<< HEAD

class HelpdeskTicket(models.Model):
    """Extensión del módulo nativo helpdesk.ticket para agregar campos de mantenimiento."""
    _inherit = 'helpdesk.ticket'  # ✅ Extendiendo el modelo nativo
=======
# Nombres de etapa que se consideran "En espera" (pausa = solicitud de aprobación)
STAGE_NAMES_EN_ESPERA = ('en espera', 'espera', 'on hold', 'pausa', 'waiting')
# Solo en "En progreso" se puede iniciar o continuar el cronómetro
STAGE_NAMES_EN_PROGRESO = ('en progreso', 'in progress', 'en progres')
# No se puede volver de "En progreso" a "Nuevo"
STAGE_NAMES_NUEVO = ('nuevo', 'new')
# Al pasar a estas se para el cronómetro (acumular y detener)
STAGE_NAMES_RESUELTO_CERRADO = ('resuelto', 'resolved', 'cerrado', 'closed', 'cancelado', 'canceled')
# Etapas que no permiten volver a "Nuevo" (una vez en progreso no se puede revertir)
STAGE_NAMES_AFTER_NUEVO = ('en progreso', 'en espera', 'resuelto', 'resolved', 'cancelado', 'canceled', 'cerrado', 'closed')
# Etapas que terminan el ticket: al pasar a estas se para/registra el cronómetro
STAGE_NAMES_RESUELTO_CERRADO = ('resuelto', 'resolved', 'cerrado', 'closed', 'cancelado', 'canceled')


def _format_duration(hours):
    """Formatea horas como 'X h Y min' o 'Y min'."""
    if hours is None or hours < 0:
        return '0 min'
    total_m = int(round(hours * 60))
    if total_m >= 60:
        return '%d h %d min' % (total_m // 60, total_m % 60)
    return '%d min' % total_m


class HelpdeskTicket(models.Model):
    """Extensión del módulo nativo helpdesk.ticket para agregar campos de mantenimiento.
    Prioridad, SLA y orden de servicio se rellenan/crean según la categoría del ticket."""
    _inherit = 'helpdesk.ticket'  # ✅ Extendiendo el modelo nativo

    @api.constrains('user_id')
    def _check_assigned_required(self):
        """El campo Asignada a es obligatorio para poder guardar el ticket."""
        for ticket in self:
            if not ticket.user_id:
                raise UserError(_('El ticket debe tener un responsable asignado (Asignada a).'))
>>>>>>> fb2d0eddb44261c7833d37e32b0869ec9bdb22c2
    
    # Campos adicionales para integración con mantenimientos
    lot_id = fields.Many2one(
        'stock.lot',
        string='Equipo',
        domain="[('customer_id', '=', partner_id)]",
        tracking=True,
        help='Equipo relacionado con el ticket'
    )
    
    maintenance_order_id = fields.Many2one(
        'maintenance.order',
        string='Orden de Mantenimiento',
        tracking=True,
<<<<<<< HEAD
        help='Orden de mantenimiento relacionada'
=======
        help='Orden de mantenimiento relacionada (creada automáticamente por categoría o manualmente)'
>>>>>>> fb2d0eddb44261c7833d37e32b0869ec9bdb22c2
    )
    
    maintenance_id = fields.Many2one(
        'stock.lot.maintenance',
        string='Mantenimiento',
        tracking=True,
        help='Mantenimiento relacionado'
    )
    
<<<<<<< HEAD
=======
    category_id = fields.Many2one(
        'helpdesk.ticket.category',
        string='Categoría',
        tracking=True,
    )

    # Tipo GLPI: urgencia e impacto
    urgency = fields.Selection([
        ('1', 'Baja'),
        ('2', 'Media'),
        ('3', 'Alta'),
        ('4', 'Crítica'),
    ], string='Urgencia', default='2', tracking=True)
    impact = fields.Selection([
        ('1', 'Baja'),
        ('2', 'Media'),
        ('3', 'Alta'),
        ('4', 'Crítica'),
    ], string='Impacto', default='2', tracking=True)
    location_site = fields.Char(string='Ubicación / Sede', tracking=True)
    date_deadline_response = fields.Datetime(string='Compromiso respuesta (SLA)', tracking=True)
    date_deadline_resolution = fields.Datetime(string='Compromiso resolución (SLA)', tracking=True)

    # Si True, prioridad/urgencia/impacto/SLA fueron fijados por la categoría y el técnico no debe editarlos
    values_from_category = fields.Boolean(
        string='Valores fijados por categoría',
        default=False,
        help='Cuando está activo, Prioridad, Urgencia, Impacto y fechas SLA son solo lectura (definidos por la categoría).'
    )

>>>>>>> fb2d0eddb44261c7833d37e32b0869ec9bdb22c2
    # Categoría personalizada para distinguir tickets de mantenimiento
    maintenance_category = fields.Selection([
        ('maintenance', 'Mantenimiento'),
        ('repair', 'Reparación'),
        ('support', 'Soporte'),
        ('change', 'Cambio de Equipo'),
        ('other', 'Otro'),
    ], string='Categoría Mantenimiento', tracking=True)
<<<<<<< HEAD
    
    def action_convert_to_maintenance_order(self):
        """Convertir ticket en orden de mantenimiento."""
        self.ensure_one()
        # Crear orden de mantenimiento directamente
        maintenance_order = self.env['maintenance.order'].create({
            'partner_id': self.partner_id.id if self.partner_id else False,
            'description': (self.name or '') + '\n\n' + (self.description or ''),
        })
=======

    # ---------- Cronómetro propio (no usa el timer de Odoo). Pausa = estado "En espera" ----------
    custom_timer_start = fields.Datetime(
        string='Inicio cronómetro',
        readonly=True,
        copy=False,
        help='Cuando el cronómetro está en marcha. Si mueves el ticket a "En espera", se pausa (se acumula el tiempo y se detiene).',
    )
    custom_timer_accumulated_hours = fields.Float(
        string='Horas acumuladas (sesión)',
        default=0,
        readonly=True,
        copy=False,
        help='Horas ya contabilizadas antes de la pausa actual. Al detener el cronómetro se registra acumulado + tiempo actual.',
    )
    custom_timer_display = fields.Char(
        string='Tiempo cronómetro',
        compute='_compute_custom_timer_display',
        help='Tiempo actual o acumulado del cronómetro propio (pausa = estado En espera).',
    )
    custom_timer_can_stop = fields.Boolean(
        string='Puede detener cronómetro',
        compute='_compute_custom_timer_can_stop',
        help='True si hay cronómetro en marcha o tiempo acumulado para registrar.',
    )

    @api.depends('custom_timer_start', 'custom_timer_accumulated_hours')
    def _compute_custom_timer_can_stop(self):
        for ticket in self:
            ticket.custom_timer_can_stop = bool(ticket.custom_timer_start) or (ticket.custom_timer_accumulated_hours or 0) > 0

    @api.depends('custom_timer_start', 'custom_timer_accumulated_hours', 'stage_id')
    def _compute_custom_timer_display(self):
        now = fields.Datetime.now()
        for ticket in self:
            if ticket.custom_timer_start:
                elapsed = ticket._custom_timer_elapsed_hours()
                total = ticket.custom_timer_accumulated_hours + elapsed
                ticket.custom_timer_display = _('En marcha: %s (total sesión: %s)') % (
                    _format_duration(elapsed),
                    _format_duration(total),
                )
            elif ticket.custom_timer_accumulated_hours:
                # En Resuelto/Cerrado/Cancelado mostrar "Finalizado" en lugar de "Pausado"
                if ticket._is_stage_resuelto_or_closed():
                    ticket.custom_timer_display = _('Finalizado. Acumulado: %s') % _format_duration(ticket.custom_timer_accumulated_hours)
                else:
                    ticket.custom_timer_display = _('Pausado. Acumulado: %s') % _format_duration(ticket.custom_timer_accumulated_hours)
            else:
                # Siempre mostrar un tiempo (0 min si no hay cronómetro usado)
                ticket.custom_timer_display = _('Parado. Acumulado: 0 min')

    def _get_stage_name_lower(self, stage_id=None):
        """Nombre de la etapa en minúsculas (stage_id o el del ticket)."""
        stage = stage_id or (self.ensure_one() and self.stage_id)
        if not stage or not stage.name:
            return None
        return (stage.name or '').strip().lower()

    def _is_stage_en_espera(self):
        """True si la etapa actual se considera 'En espera' (pausa del cronómetro)."""
        self.ensure_one()
        name = self._get_stage_name_lower()
        return name in STAGE_NAMES_EN_ESPERA if name else False

    def _is_stage_en_progreso(self):
        """True si la etapa actual es 'En progreso' (única en la que se puede iniciar/continuar el cronómetro)."""
        self.ensure_one()
        name = self._get_stage_name_lower()
        return name in STAGE_NAMES_EN_PROGRESO if name else False

    def _is_stage_resuelto_or_closed(self):
        """True si la etapa actual es Resuelto/Cerrado/Cancelado (etapa final, no se puede cambiar)."""
        self.ensure_one()
        name = self._get_stage_name_lower()
        return name in STAGE_NAMES_RESUELTO_CERRADO if name else False

    def _custom_timer_elapsed_hours(self, now=None):
        """Horas transcurridas desde custom_timer_start hasta now (solo si el cronómetro está en marcha)."""
        self.ensure_one()
        if not self.custom_timer_start:
            return 0.0
        now = now or fields.Datetime.now()
        try:
            start = self.custom_timer_start
            if isinstance(start, str):
                start = fields.Datetime.from_string(start)
            delta = now - start
            return max(0.0, min(delta.total_seconds() / 3600.0, 24.0))
        except (TypeError, ValueError):
            return 0.0

    def _apply_category_defaults(self, category):
        """Devuelve un diccionario de valores a aplicar al ticket según la categoría (prioridad, SLA, urgencia, impacto)."""
        vals = {}
        if not category:
            return vals
        if category.default_priority:
            # helpdesk.ticket.priority en Odoo estándar es string ('0','1','2','3')
            vals['priority'] = category.default_priority
        if category.default_urgency:
            vals['urgency'] = category.default_urgency
        if category.default_impact:
            vals['impact'] = category.default_impact
        now = fields.Datetime.now()
        # Intervalo SLA: días + horas
        resp_days = category.sla_response_days or 0
        resp_hours = category.sla_response_hours or 0
        if resp_days or resp_hours:
            vals['date_deadline_response'] = now + timedelta(days=resp_days, hours=resp_hours)
        res_days = category.sla_resolution_days or 0
        res_hours = category.sla_resolution_hours or 0
        if res_days or res_hours:
            vals['date_deadline_resolution'] = now + timedelta(days=res_days, hours=res_hours)
        if vals:
            vals['values_from_category'] = True
        return vals

    def _create_maintenance_order_from_ticket(self):
        """Crea una orden de mantenimiento enlazada a este ticket (partner, descripción)."""
        self.ensure_one()
        if self.maintenance_order_id:
            return self.maintenance_order_id
        if not self.partner_id:
            return self.env['maintenance.order']
        desc = (self.name or '') + '\n\n' + (self.description or '')
        order_vals = {
            'partner_id': self.partner_id.id,
            'description': desc,
            'ticket_id': self.id,
        }
        if self.user_id:
            order_vals['technician_ids'] = [(6, 0, [self.user_id.id])]
        order = self.env['maintenance.order'].with_context(from_ticket=True).create(order_vals)
        self.maintenance_order_id = order.id
        self.message_post(body=_('Orden de servicio creada automáticamente por categoría: %s') % order.name)
        return order

    @api.model_create_multi
    def create(self, vals_list):
        tickets = super().create(vals_list)
        for ticket in tickets:
            cat = ticket.category_id
            if cat:
                defaults = ticket._apply_category_defaults(cat)
                if defaults:
                    ticket.write(defaults)
                if cat.auto_create_maintenance_order and not ticket.maintenance_order_id and ticket.partner_id:
                    ticket._create_maintenance_order_from_ticket()
        return tickets

    def write(self, vals):
        if 'stage_id' in vals and vals.get('stage_id'):
            new_stage_name = None
            try:
                stage_model = self._fields.get('stage_id') and self._fields['stage_id'].comodel_name
                if stage_model and stage_model in self.env:
                    new_stage = self.env[stage_model].browse(vals['stage_id'])
                    new_stage_name = (new_stage.name or '').strip().lower() if new_stage else None
            except (KeyError, AttributeError):
                pass
            if new_stage_name:
                for ticket in self:
                    cur = ticket._get_stage_name_lower()
                    # No volver a "Nuevo" una vez que el ticket salió de esa etapa
                    if new_stage_name in STAGE_NAMES_NUEVO and cur and cur not in STAGE_NAMES_NUEVO:
                        raise UserError(_('No se puede volver a la etapa "Nuevo" una vez que el ticket ha salido de ella.'))
                    # Resuelto/Cerrado/Cancelado es final: no se puede cambiar a otra etapa
                    if cur in STAGE_NAMES_RESUELTO_CERRADO and vals.get('stage_id') != ticket.stage_id.id:
                        raise UserError(_('Un ticket en etapa "Resuelto" (o Cerrado/Cancelado) no puede cambiar a otra etapa.'))
                # Al pasar a Resuelto/Cerrado/Cancelado: parar cronómetro (acumular y detener)
                if new_stage_name in STAGE_NAMES_RESUELTO_CERRADO:
                    to_stop = self.filtered(lambda t: t.custom_timer_start)
                    for ticket in to_stop:
                        elapsed = ticket._custom_timer_elapsed_hours()
                        super(HelpdeskTicket, ticket).write({
                            **vals,
                            'custom_timer_accumulated_hours': (ticket.custom_timer_accumulated_hours or 0) + elapsed,
                            'custom_timer_start': False,
                        })
                    rest = self - to_stop
                    if rest:
                        super(HelpdeskTicket, rest).write(vals)
                    vals = {}
                # Pausa: al pasar a "En espera" crear solicitud (cronómetro sigue hasta aprobar)
                elif new_stage_name in STAGE_NAMES_EN_ESPERA:
                    PauseRequest = self.env.get('helpdesk.ticket.pause.request')
                    if PauseRequest:
                        for ticket in self.filtered(lambda t: t.custom_timer_start):
                            elapsed = ticket._custom_timer_elapsed_hours()
                            existing = PauseRequest.search([
                                ('ticket_id', '=', ticket.id),
                                ('state', '=', 'pending'),
                            ], limit=1)
                            if not existing:
                                approver = PauseRequest._get_approver_for_ticket(ticket)
                                PauseRequest.create({
                                    'ticket_id': ticket.id,
                                    'requested_by_id': self.env.user.id,
                                    'request_datetime': fields.Datetime.now(),
                                    'time_at_request': elapsed,
                                    'approver_to_notify_id': approver.id if approver else False,
                                })
                                ticket.message_post(body=_('Solicitud de pausa creada. El cronómetro sigue en marcha hasta que un responsable la autorice en: Mesa de Ayuda → Configuración → Solicitudes de pausa (tickets).'))
        # Aplicar cambio de etapa (y el resto de vals) normalmente
        if vals:
            res = super().write(vals)
        else:
            res = True
        if 'category_id' in vals:
            for ticket in self:
                cat = ticket.category_id
                if cat:
                    defaults = ticket._apply_category_defaults(cat)
                    if defaults:
                        super(HelpdeskTicket, ticket).write(defaults)
                    if cat.auto_create_maintenance_order and not ticket.maintenance_order_id and ticket.partner_id:
                        ticket._create_maintenance_order_from_ticket()
        # Sincronizar asignado del ticket con la orden de mantenimiento (misma persona)
        if 'user_id' in vals:
            for ticket in self:
                if ticket.maintenance_order_id and ticket.user_id:
                    ticket.maintenance_order_id.technician_ids = [(6, 0, [ticket.user_id.id])]
        return res

    def action_custom_timer_start(self):
        """Inicia o continúa el cronómetro. Solo permitido en etapa 'En progreso'. Para pausar, mueve a 'En espera'."""
        for ticket in self:
            if ticket.custom_timer_start:
                continue
            if not ticket._is_stage_en_progreso():
                raise UserError(_('Solo se puede iniciar o continuar el cronómetro cuando el ticket está en la etapa "En progreso". Cambia la etapa del ticket primero.'))
            ticket.write({'custom_timer_start': fields.Datetime.now()})
        return True

    def action_custom_timer_stop(self):
        """Detiene el cronómetro y registra el tiempo en la hoja de horas (account.analytic.line)."""
        self.ensure_one()
        if not self.custom_timer_start and (self.custom_timer_accumulated_hours or 0) <= 0:
            raise UserError(_('No hay cronómetro en marcha ni tiempo acumulado para registrar.'))
        now = fields.Datetime.now()
        total_hours = self.custom_timer_accumulated_hours + self._custom_timer_elapsed_hours()
        if total_hours <= 0:
            raise UserError(_('El tiempo a registrar debe ser mayor que cero.'))
        # Validar tiempo mínimo por categoría (SLA / control por categoría)
        if self.category_id and self.category_id.control_tiempo_registro == 'minimo_horas' and (self.category_id.tiempo_minimo_horas or 0) > 0:
            if total_hours < self.category_id.tiempo_minimo_horas - 0.001:
                raise UserError(_(
                    'Para la categoría "%s" el tiempo registrado no puede ser menor a %s horas.',
                    self.category_id.complete_name or self.category_id.name,
                    self.category_id.tiempo_minimo_horas,
                ))
        # Compañía obligatoria en account.analytic.line
        company_id = (getattr(self, 'company_id', None) and self.company_id.id) or self.env.company.id
        # Proyecto: equipo de helpdesk puede tener project_id (Track & Bill Time)
        project_id = getattr(self.team_id, 'project_id', None) and self.team_id.project_id.id or False
        # Empleado para hr_timesheet
        employee = self.env.user.employee_id if hasattr(self.env.user, 'employee_id') else self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        line_vals = {
            'name': self.name or _('Ticket'),
            'date': now.date(),
            'unit_amount': total_hours,
            'user_id': self.env.uid,
            'project_id': project_id,
            'company_id': company_id,
        }
        if employee:
            line_vals['employee_id'] = employee.id
        # Enlazar al ticket si el modelo lo permite (helpdesk_timesheet añade helpdesk_ticket_id)
        if hasattr(self.env['account.analytic.line'], '_fields') and 'helpdesk_ticket_id' in self.env['account.analytic.line']._fields:
            line_vals['helpdesk_ticket_id'] = self.id
        line = self.env['account.analytic.line'].create(line_vals)
        self.write({'custom_timer_start': False, 'custom_timer_accumulated_hours': 0})
        self.message_post(body=_('Tiempo registrado: %s horas (cronómetro propio).') % round(total_hours, 2))
        _logger.info('mesa_ayuda_inventario: custom timer stop ticket %s, %.4f h, line id=%s', self.name, total_hours, line.id)
        return True

    def action_convert_to_maintenance_order(self):
        """Crear orden de mantenimiento manualmente si no existe (por categoría ya puede existir)."""
        self.ensure_one()
        if self.maintenance_order_id:
            return {
                'name': _('Orden de Mantenimiento'),
                'type': 'ir.actions.act_window',
                'res_model': 'maintenance.order',
                'res_id': self.maintenance_order_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        if not self.partner_id:
            raise UserError(_('El ticket debe tener un cliente para crear la orden de mantenimiento.'))
        desc = (self.name or '') + '\n\n' + (self.description or '')
        order_vals = {
            'partner_id': self.partner_id.id,
            'description': desc,
            'ticket_id': self.id,
        }
        if self.user_id:
            order_vals['technician_ids'] = [(6, 0, [self.user_id.id])]
        maintenance_order = self.env['maintenance.order'].create(order_vals)
>>>>>>> fb2d0eddb44261c7833d37e32b0869ec9bdb22c2
        self.maintenance_order_id = maintenance_order.id
        self.message_post(body=_('Se creó una orden de mantenimiento: %s') % maintenance_order.name)
        return {
            'name': _('Orden de Mantenimiento'),
            'type': 'ir.actions.act_window',
            'res_model': 'maintenance.order',
            'res_id': maintenance_order.id,
            'view_mode': 'form',
            'target': 'current',
        }
<<<<<<< HEAD
=======

    def action_escalate_ticket(self):
        """Abrir wizard para escalar el ticket a otro equipo o responsable (ej. Nivel 2)."""
        self.ensure_one()
        return {
            'name': _('Escalar ticket'),
            'type': 'ir.actions.act_window',
            'res_model': 'helpdesk.ticket.escalate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_id': self.id, 'default_ticket_id': self.id},
        }
>>>>>>> fb2d0eddb44261c7833d37e32b0869ec9bdb22c2
