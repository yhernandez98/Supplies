# -*- coding: utf-8 -*-

import html as html_stdlib

from markupsafe import Markup, escape

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import mail as mail_tools
from odoo.tools import html2plaintext
from datetime import datetime, timedelta
import logging
import base64
import re
import traceback

_logger = logging.getLogger(__name__)


def _mesa_acta_table_html_is_equipment_block(table_html):
    """Excluye tablas del acta de contactos (Nombre/Correo) que también tienen 3 columnas."""
    if not table_html:
        return False
    low = re.sub(r'\s+', ' ', table_html).lower()
    if 'data-mesa-acta-participant-partner-id' in low or 'data-mesa-acta-participant-user-id' in low:
        return False
    if 'data-mesa-acta-equipment="1"' in low or "data-mesa-acta-equipment='1'" in low:
        return True
    thead = ''
    m = re.search(r'<thead\b[^>]*>([\s\S]*?)</thead>', table_html, re.I)
    if m:
        thead = re.sub(r'\s+', ' ', m.group(1)).lower()
    if 'nombre' in thead and ('correo' in thead or 'mail' in thead):
        return False
    if 'serie' in thead and 'placa' in thead:
        return True
    return False


def _mesa_html_slice_balanced_div(html, open_idx):
    """Devuelve el fragmento ``<div>...</div>`` balanceado desde ``open_idx`` (índice del ``<`` inicial)."""
    n = len(html)
    if open_idx < 0 or open_idx >= n:
        return ''
    if html[open_idx : open_idx + 4].lower() != '<div':
        return ''
    i = open_idx
    depth = 0
    while i < n:
        if html[i] != '<':
            i += 1
            continue
        if re.match(r'<div\b', html[i:], re.I):
            depth += 1
            gt = html.find('>', i)
            if gt == -1:
                return ''
            i = gt + 1
            continue
        if html[i : i + 6].lower() == '</div>':
            depth -= 1
            i += 6
            if depth == 0:
                return html[open_idx:i]
            continue
        i += 1
    return ''


class MaintenanceOrder(models.Model):
    """Orden de Mantenimiento que agrupa múltiples mantenimientos de equipos."""
    _name = 'maintenance.order'
    _description = 'Orden de Mantenimiento'
    _order = 'scheduled_date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Número de Orden',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('Nuevo'),
        help='Número único de la orden de mantenimiento'
    )
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
        help='Cliente para el cual se realizará el mantenimiento'
    )
    
    technician_ids = fields.Many2many(
        'res.users',
        'maintenance_order_technician_rel',
        'order_id',
        'user_id',
        string='Técnicos Asignados',
        tracking=True,
        help='Técnicos responsables de realizar el mantenimiento (selección manual; no se preasigna el usuario actual).'
    )
    
    scheduled_date = fields.Datetime(
        string='Fecha Programada',
        required=True,
        default=fields.Datetime.now,
        tracking=True,
        help='Fecha y hora programada para realizar el mantenimiento'
    )
    
    deadline_date = fields.Datetime(
        string='Fecha Límite',
        tracking=True,
        help='Fecha límite para completar el mantenimiento'
    )
    
    state = fields.Selection(
        [
            ('draft', 'Borrador'),
            ('scheduled', 'Programada'),
            ('in_progress', 'En Progreso'),
            ('completed', 'Completada'),
            ('cancelled', 'Cancelada'),
        ],
        string='Estado',
        default='draft',
        required=True,
        tracking=True,
        help='Estado de la orden de mantenimiento'
    )
    
    maintenance_ids = fields.One2many(
        'stock.lot.maintenance',
        'maintenance_order_id',
        string='Mantenimientos',
        help='Mantenimientos individuales de cada equipo'
    )
    
    # ✅ Campo computed para mostrar todos los cambios de componentes de los mantenimientos asociados
    all_component_change_ids = fields.One2many(
        'maintenance.component.change',
        string='Todos los Cambios de Componentes',
        compute='_compute_all_component_changes',
        help='Todos los cambios de componentes de los mantenimientos en esta orden'
    )
    
    @api.depends('maintenance_ids.component_change_ids')
    def _compute_all_component_changes(self):
        """Calcular todos los cambios de componentes de los mantenimientos asociados."""
        for order in self:
            all_changes = self.env['maintenance.component.change']
            for maintenance in order.maintenance_ids:
                all_changes |= maintenance.component_change_ids
            order.all_component_change_ids = all_changes
    
    description = fields.Text(
        string='Descripción',
        help='Descripción general de la orden de mantenimiento'
    )
    
    notes = fields.Text(
        string='Notas',
        help='Notas adicionales sobre la orden'
    )
    
    # ✅ Firmas múltiples de técnicos
    technician_signature_ids = fields.One2many(
        'maintenance.order.technician.signature',
        'order_id',
        string='Firmas de Técnicos',
        help='Firmas de todos los técnicos asignados a esta orden'
    )
    
    # Campos legacy para compatibilidad (se mantienen por ahora)
    technician_signature = fields.Binary(
        string='Firma del Técnico (Temporal)',
        help='Firma digital del técnico que se aplicará a todos los mantenimientos de esta orden',
        attachment=False
    )
    
    technician_signed_by = fields.Many2one(
        'res.users',
        string='Firmado por Técnico',
        readonly=True,
        help='Usuario técnico que firmó la orden'
    )
    
    technician_signed_date = fields.Datetime(
        string='Fecha Firma Técnico',
        readonly=True,
        help='Fecha y hora en que el técnico firmó'
    )
    
    customer_signature = fields.Binary(
        string='Firma del Cliente',
        help='Firma digital del cliente que se aplicará a todos los mantenimientos de esta orden',
        attachment=False
    )
    
    customer_signed_by = fields.Many2one(
        'res.partner',
        string='Firmado por Cliente',
        readonly=True,
        help='Cliente que firmó la orden'
    )
    
    customer_signed_date = fields.Datetime(
        string='Fecha Firma Cliente',
        readonly=True,
        help='Fecha y hora en que el cliente firmó'
    )
    
    is_signed = fields.Boolean(
        string='Está Firmado',
        compute='_compute_is_signed',
        help='Indica si la orden tiene ambas firmas (técnico y cliente)'
    )
    
    # ✅ Campo para el ticket automático
    ticket_id = fields.Many2one(
        'helpdesk.ticket',
        string='Ticket',
        readonly=True,
        tracking=True,
        help='Ticket creado automáticamente para esta orden de mantenimiento'
    )
    
    # ========== CAMPOS PARA VISITAS PROGRAMADAS ==========
    
    activity_type = fields.Selection(
        [
            ('visit', 'Visita y Mantenimiento'),
        ],
        string='Tipo de Actividad',
        default='visit',
        required=True,
        tracking=True,
        help='Todas las órdenes de este flujo son visita con mantenimiento en sitio.',
    )
    
    visit_purpose = fields.Text(
        string='Propósito de la visita',
        help='Objetivo de la visita en sitio.',
    )

    visit_documentation_html = fields.Html(
        string='Informe de visita (último guardado)',
        sanitize=False,
        help='Contenido guardado desde el asistente de documentación; se muestra de nuevo al reabrir la misma visita.',
    )

    mesa_visit_pdf_summary_html = fields.Html(
        string='Resumen cierre (PDF)',
        copy=False,
        help='Copia del resumen inyectado en el ticket al completar la visita; se usa en el informe PDF.',
    )

    mesa_pdf_summary_effective = fields.Html(
        string='Resumen PDF (efectivo)',
        compute='_compute_mesa_pdf_summary_effective',
        help='Resumen guardado en la orden o, si falta, extraído del bloque de cierre en la descripción del ticket.',
    )
    
    calendar_event_ids = fields.Many2many(
        'calendar.event',
        'maintenance_order_calendar_event_rel',
        'order_id',
        'event_id',
        string='Eventos de Calendario',
        readonly=True,
        help='Eventos de calendario asociados a esta orden'
    )
    
    calendar_label = fields.Char(
        string='Texto en calendario',
        compute='_compute_calendar_label',
        store=True,
    )
    
    @api.depends('mesa_visit_pdf_summary_html', 'ticket_id', 'ticket_id.description')
    def _compute_mesa_pdf_summary_effective(self):
        start_marker = '<!--MESA_ACTA_CIERRE_START-->'
        end_marker = '<!--MESA_ACTA_CIERRE_END-->'
        for order in self:
            if order.mesa_visit_pdf_summary_html:
                order.mesa_pdf_summary_effective = order.mesa_visit_pdf_summary_html
                continue
            ticket = order.ticket_id
            if not ticket:
                order.mesa_pdf_summary_effective = False
                continue
            desc = ticket.description or ''
            if isinstance(desc, Markup):
                desc = str(desc)
            if start_marker in desc and end_marker in desc:
                try:
                    i = desc.index(start_marker) + len(start_marker)
                    j = desc.index(end_marker)
                    order.mesa_pdf_summary_effective = desc[i:j].strip()
                except ValueError:
                    order.mesa_pdf_summary_effective = False
            else:
                order.mesa_pdf_summary_effective = False

    @api.depends('name', 'technician_ids', 'partner_id', 'ticket_id')
    def _compute_calendar_label(self):
        for order in self:
            order.calendar_label = order._format_calendar_event_name()
    
    @api.depends('technician_signature_ids', 'technician_signature_ids.signature', 'technician_ids', 'customer_signature')
    def _compute_is_signed(self):
        """True solo si cada técnico asignado tiene firma con trazo y el cliente firmó."""
        for order in self:
            techs = order.technician_ids
            if not techs:
                all_technicians_signed = True
            else:
                signed_ids = order.technician_signature_ids.filtered(lambda s: bool(s.signature)).mapped(
                    'technician_id'
                ).ids
                all_technicians_signed = all(t.id in signed_ids for t in techs)
            customer_signed = bool(order.customer_signature)
            order.is_signed = all_technicians_signed and customer_signed
    
    def action_add_technician_signature(self):
        """Agregar firma del técnico actual a la lista de firmas."""
        self.ensure_one()
        if not self.technician_signature:
            raise UserError(_('Debe proporcionar una firma primero.'))
        
        # Verificar si el técnico actual ya firmó
        existing_signature = self.technician_signature_ids.filtered(
            lambda s: s.technician_id.id == self.env.user.id
        )
        
        if existing_signature:
            # Actualizar la firma existente
            existing_signature.write({
                'signature': self.technician_signature,
                'signature_date': fields.Datetime.now(),
            })
        else:
            # Crear nueva firma
            self.env['maintenance.order.technician.signature'].create({
                'order_id': self.id,
                'technician_id': self.env.user.id,
                'signature': self.technician_signature,
                'signature_date': fields.Datetime.now(),
            })
        
        # Limpiar el campo temporal
        self.technician_signature = False
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Firma Agregada'),
                'message': _('Tu firma ha sido agregada a la orden.'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    @api.onchange('technician_signature')
    def _onchange_technician_signature(self):
        """Cuando se carga una firma del técnico, preparar para agregarla."""
        # Este método ya no hace nada automático, se usa action_add_technician_signature
        pass
    
    @api.onchange('customer_signature')
    def _onchange_customer_signature(self):
        """Cuando se carga una firma del cliente, guardar cliente y fecha automáticamente."""
        if self.customer_signature:
            if not self.customer_signed_by:
                # Usar el cliente de la orden
                if self.partner_id:
                    self.customer_signed_by = self.partner_id.id
            if not self.customer_signed_date:
                self.customer_signed_date = fields.Datetime.now()
            # La propagación se hace automáticamente en write() cuando se guarda
    
    def _propagate_signatures_to_maintenances(self):
        """Propagar las firmas de la orden a todos los mantenimientos relacionados."""
        if not self.maintenance_ids:
            return
        
        # Preparar valores para actualizar
        update_vals = {}
        if self.technician_signature:
            update_vals['technician_signature'] = self.technician_signature
            if self.technician_signed_by:
                update_vals['technician_signed_by'] = self.technician_signed_by.id
            if self.technician_signed_date:
                update_vals['technician_signed_date'] = self.technician_signed_date
        
        if self.customer_signature:
            update_vals['customer_signature'] = self.customer_signature
            if self.customer_signed_by:
                update_vals['customer_signed_by'] = self.customer_signed_by.id
            if self.customer_signed_date:
                update_vals['customer_signed_date'] = self.customer_signed_date
        
        if update_vals:
            # Actualizar todos los mantenimientos con contexto para evitar validaciones
            self.maintenance_ids.with_context(
                skip_signature_check=True,
                skip_status_validation=True
            ).write(update_vals)
    
    def _visit_sequence_display_digits(self):
        """MO-/VT-/VS-000004 → 000004 (solo dígitos/sufijo de secuencia)."""
        name = (self.name or '').strip()
        if not name or name == _('Nuevo') or name == 'Nuevo':
            return ''
        m = re.match(r'(?i)(?:VS|VT|MO)-(.+)$', name)
        if m:
            return m.group(1).strip()
        return name

    def _ticket_calendar_suffix(self):
        """Sufijo tipo (#00005) usando el ticket de helpdesk si existe."""
        self.ensure_one()
        if not self.ticket_id:
            return ''
        tname = (self.ticket_id.name or '').strip()
        if tname.startswith('#') and re.match(r'^#\d+$', tname):
            return ' (%s)' % tname
        return ' (#%05d)' % self.ticket_id.id

    def _format_calendar_event_name(self):
        """Texto compacto para calendario: Visita Técnica 000004 (#00005) — Técnicos."""
        self.ensure_one()
        num = self._visit_sequence_display_digits()
        if not num:
            raw = (self.name or '').strip()
            if raw and raw not in (_('Nuevo'), 'Nuevo'):
                num = raw
        tick = self._ticket_calendar_suffix()
        tech = ', '.join(self.technician_ids.mapped('name')) if self.technician_ids else _('Sin técnico')
        return _('Visita Técnica %(num)s%(tick)s — %(tech)s') % {
            'num': num,
            'tick': tick,
            'tech': tech,
        }

    def name_get(self):
        """Nombre mostrado alineado con calendario (número sin prefijo, ticket, técnicos)."""
        result = []
        for order in self:
            num_digits = order._visit_sequence_display_digits()
            if not num_digits and (not order.name or order.name == _('Nuevo') or order.name == 'Nuevo'):
                result.append((order.id, order.name or _('Nuevo')))
                continue
            num = num_digits or (order.name or '').strip()
            tick = order._ticket_calendar_suffix()
            base = _('Visita Técnica %(num)s%(tick)s') % {'num': num, 'tick': tick}
            if order.technician_ids:
                tech = ', '.join(order.technician_ids.mapped('name'))
                label = _('%(base)s — %(tech)s') % {'base': base, 'tech': tech}
            else:
                label = base
            result.append((order.id, label))
        return result
    
    @api.model
    def _maintenance_order_name_needs_sequence(self, name):
        """True si debemos asignar número desde la secuencia (marcadores de nuevo registro)."""
        if name is False or name is None:
            return True
        if not str(name).strip():
            return True
        s = str(name).strip()
        if s in ('/', 'Nuevo', 'New'):
            return True
        return s == _('Nuevo')

    @api.model
    def _next_maintenance_order_sequence_name(self):
        """Secuencia propia del módulo (code mesa.ayuda.maintenance.order); no usa 'maintenance.order' genérico."""
        seq = self.env.ref('mesa_ayuda_inventario.seq_mesa_ayuda_maintenance_order', raise_if_not_found=False)
        if seq:
            return seq.next_by_id()
        return self.env['ir.sequence'].next_by_code('mesa.ayuda.maintenance.order')

    def action_open_visit_documentation(self):
        """Compatibilidad: abre el ticket (el acta se edita en la pestaña «Acta de visita» del ticket)."""
        return self.action_view_ticket()

    @api.model_create_multi
    def create(self, vals_list):
        """Generar número de orden automáticamente y crear ticket."""
        for vals in vals_list:
            if self._maintenance_order_name_needs_sequence(vals.get('name')):
                vals['name'] = self._next_maintenance_order_sequence_name() or _('Nuevo')
        orders = super().create(vals_list)
        for order in orders:
            order._create_automatic_ticket()
        if order.technician_ids:
            order._ensure_signature_records_for_technicians()
        if order.technician_signature or order.customer_signature:
            order._propagate_signatures_to_maintenances()
        if order.scheduled_date and order.state in ('scheduled', 'in_progress'):
            order._create_calendar_events()
            order._schedule_reminder_activities()
        return orders
    
    def write(self, vals):
        """Sobrescribir write para propagar firmas y actualizar ticket."""
        # Verificar si se están guardando firmas
        signatures_changed = 'technician_signature' in vals or 'customer_signature' in vals
        
        result = super().write(vals)
        
        # Si se modificaron los técnicos después de escribir, asegurar que existan registros de firma para cada uno
        if 'technician_ids' in vals:
            for order in self:
                order._ensure_signature_records_for_technicians()
        
        # Si se cambiaron firmas, propagarlas a los mantenimientos
        if signatures_changed:
            for order in self:
                order._propagate_signatures_to_maintenances()
        
        # ✅ Si se modificó el estado, actualizar el ticket (pero no si ya se procesó en action_complete)
        # Verificar si viene del contexto de action_complete
        if 'state' in vals:
            skip_ticket_update = self.env.context.get('skip_ticket_update_on_complete', False)
            if vals['state'] == 'completed' and skip_ticket_update:
                # Ya se procesó en action_complete, no hacer nada más
                pass
            else:
                for order in self:
                    order._update_ticket_status()
            
            # ✅ Actualizar calendario según el estado
            for order in self:
                if vals['state'] == 'cancelled':
                    order._cancel_calendar_events()
                elif vals['state'] in ('scheduled', 'in_progress') and order.scheduled_date:
                    order._create_calendar_events()
                    order._schedule_reminder_activities()
        
        # ✅ Actualizar calendario si cambió fecha programada o técnicos
        calendar_fields = ['scheduled_date', 'deadline_date', 'technician_ids', 'activity_type', 'visit_purpose']
        if any(field in vals for field in calendar_fields):
            for order in self:
                if order.state not in ('cancelled', 'completed'):
                    if order.scheduled_date and order.technician_ids:
                        order._update_calendar_events()
                        if 'scheduled_date' in vals:
                            order._schedule_reminder_activities()
                    elif order.calendar_event_ids:
                        # Si se quitó fecha o técnicos, eliminar eventos
                        order._cancel_calendar_events()
        
        # ✅ Si se modificaron mantenimientos (equipos), actualizar el ticket
        # Esto se manejará desde el wizard cuando se agreguen equipos
        
        return result
    
    def _ensure_signature_records_for_technicians(self):
        """Asegurar que exista un registro de firma para cada técnico asignado."""
        self.ensure_one()
        if not self.technician_ids:
            return
        
        # Obtener IDs de técnicos que ya tienen registro de firma
        existing_signature_tech_ids = self.technician_signature_ids.mapped('technician_id').ids
        
        # Crear registros de firma para técnicos que aún no tienen
        for tech in self.technician_ids:
            if tech.id not in existing_signature_tech_ids:
                self.env['maintenance.order.technician.signature'].create({
                    'order_id': self.id,
                    'technician_id': tech.id,
                    'signature': False,
                })
    
    def action_apply_signatures_to_maintenances(self):
        """Método manual para aplicar las firmas de la orden a todos los mantenimientos."""
        self.ensure_one()
        if not self.maintenance_ids:
            raise UserError(_('No hay mantenimientos en esta orden para aplicar las firmas.'))
        
        self._propagate_signatures_to_maintenances()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Firmas Aplicadas'),
                'message': _('Las firmas se han aplicado a %d mantenimiento(s).') % len(self.maintenance_ids),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_confirm(self):
        """Confirmar la orden y cambiar estado a Programada."""
        for order in self:
            # ✅ Permitir confirmar sin equipos - los técnicos pueden agregar equipos después
            # if not order.maintenance_ids:
            #     raise UserError(_('No se puede confirmar una orden sin mantenimientos.'))
            order.state = 'scheduled'
            # Cambiar estado de los mantenimientos a 'scheduled' si están en 'draft'
            # Usar contexto para saltar la validación de cambio manual de estado
            order.maintenance_ids.filtered(lambda m: m.status == 'draft').with_context(
                skip_status_validation=True
            ).write({'status': 'scheduled'})
            # ✅ Actualizar ticket con el cambio de estado
            order._update_ticket_status()
            # ✅ Crear eventos de calendario y recordatorios
            if order.scheduled_date and order.technician_ids:
                order._create_calendar_events()
                order._schedule_reminder_activities()
    
    def action_start(self):
        """Iniciar la orden y cambiar estado a En Progreso."""
        for order in self:
            order.state = 'in_progress'
            # Cambiar estado de los mantenimientos a 'in_progress' si están en 'scheduled'
            # Usar contexto para saltar la validación de cambio manual de estado
            order.maintenance_ids.filtered(lambda m: m.status == 'scheduled').with_context(
                skip_status_validation=True
            ).write({'status': 'in_progress'})
            # ✅ Actualizar ticket con el cambio de estado
            order._update_ticket_status()
    
    def _cron_visit_end_datetime(self):
        """Momento de fin de ventana para cierre automático: deadline o inicio + 2 h."""
        self.ensure_one()
        if self.deadline_date:
            return self.deadline_date
        if self.scheduled_date:
            return self.scheduled_date + timedelta(hours=2)
        return False

    @api.model
    def cron_visit_orders_schedule_auto_start_stop(self):
        """Cron: poner en marcha al llegar ``scheduled_date``; completar al vencer plazo (``deadline_date`` o inicio+2h)."""
        now = fields.Datetime.now()
        Maintenance = self.env['maintenance.order'].sudo()

        to_start = Maintenance.search([
            ('state', '=', 'scheduled'),
            ('scheduled_date', '!=', False),
            ('scheduled_date', '<=', now),
        ])
        for order in to_start:
            try:
                order.action_start()
                _logger.info('Visita %s: inicio automático (fecha programada alcanzada).', order.name)
            except Exception as e:
                _logger.warning('Visita %s: inicio automático fallido: %s', order.name, e)

        to_eval = Maintenance.search([
            ('state', 'in', ('scheduled', 'in_progress')),
        ])
        for order in to_eval:
            end_dt = order._cron_visit_end_datetime()
            if not end_dt or end_dt > now:
                continue
            if order.state == 'scheduled' and order.scheduled_date and order.scheduled_date > now:
                continue
            try:
                if order.state == 'scheduled':
                    order.action_start()
                incomplete = order.maintenance_ids.filtered(lambda m: m.status != 'completed')
                if incomplete:
                    incomplete.with_context(skip_status_validation=True).write({'status': 'completed'})
                order.action_complete()
                _logger.info('Visita %s: cierre automático (fin de ventana programada).', order.name)
            except Exception as e:
                _logger.warning('Visita %s: cierre automático fallido: %s', order.name, e)
        return True
    
    def action_complete(self):
        """Completar la orden, cerrar el ticket y adjuntar el reporte."""
        for order in self:
            # Verificar que todos los mantenimientos estén completados
            incomplete = order.maintenance_ids.filtered(lambda m: m.status != 'completed')
            if incomplete:
                raise UserError(_('No se puede completar la orden. Hay %d mantenimiento(s) sin completar.') % len(incomplete))
            if not order.is_signed:
                raise UserError(
                    _(
                        'No puede completar la visita hasta registrar todas las firmas obligatorias: '
                        'cada técnico asignado debe firmar en la pestaña «Firmas» de la orden y el cliente debe firmar.'
                    )
                )
            
            # ✅ Actualizar ticket con todos los detalles, cerrarlo y adjuntar reporte ANTES de cambiar el estado
            if order.ticket_id:
                order._complete_ticket_with_details()
            
            # Cambiar el estado después de procesar el ticket (con contexto para evitar doble procesamiento)
            order.with_context(skip_ticket_update_on_complete=True).state = 'completed'
            order._cancel_calendar_events()
    
    def action_cancel(self):
        """Cancelar la orden."""
        for order in self:
            order.state = 'cancelled'
            # Cancelar mantenimientos pendientes
            order.maintenance_ids.filtered(lambda m: m.status in ('draft', 'scheduled', 'in_progress')).write({'status': 'cancelled'})
            # Cancelar el ticket asociado
            if order.ticket_id:
                order._cancel_ticket()
            # ✅ Cancelar eventos de calendario
            order._cancel_calendar_events()
    
    def action_view_maintenances(self):
        """Abrir vista de mantenimientos de esta orden."""
        self.ensure_one()
        return {
            'name': _('Mantenimientos de %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'stock.lot.maintenance',
            'view_mode': 'list,form',
            'domain': [('maintenance_order_id', '=', self.id)],
            'context': {
                'default_maintenance_order_id': self.id,
                'default_lot_id': False,
            },
        }
    
    def action_add_equipment(self):
        """Abrir wizard para agregar más equipos a la orden."""
        self.ensure_one()
        return {
            'name': _('Agregar Equipos a %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'add.equipment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_maintenance_order_id': self.id,
                'default_partner_id': self.partner_id.id,
            },
        }
    
    def action_view_ticket(self):
        """Ver el ticket asociado a esta orden."""
        self.ensure_one()
        if not self.ticket_id:
            raise UserError(_('Esta orden no tiene un ticket asociado.'))
        return {
            'name': _('Ticket'),
            'type': 'ir.actions.act_window',
            'res_model': 'helpdesk.ticket',
            'res_id': self.ticket_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_generate_pdf_report(self):
        """Generar reporte PDF de la orden completa con todos los equipos."""
        self.ensure_one()
        if not self.maintenance_ids:
            raise UserError(_('No se puede generar el reporte. Esta orden no tiene equipos asociados.'))
        return self.env.ref('mesa_ayuda_inventario.action_report_maintenance_order').report_action(self)
    
    def _create_automatic_ticket(self):
        """Crear ticket automáticamente para esta orden de mantenimiento."""
        self.ensure_one()
        if self.ticket_id:
            return self.ticket_id
        
        if not self.partner_id:
            # No crear ticket si no hay cliente
            return False
        
        ticket_name = _('Visita Técnica %s') % (self.name,)
        
        # Preparar descripción del ticket con formato HTML organizado
        tech_names = ', '.join(self.technician_ids.mapped('name')) if self.technician_ids else _('No asignados')
        scheduled_date_str = self.scheduled_date.strftime('%d/%m/%Y %H:%M') if self.scheduled_date else _('No programada')
        safe_name = escape(self.name or '')
        safe_partner = escape(self.partner_id.name or _('N/A'))
        safe_tech = escape(tech_names)
        safe_sched = escape(scheduled_date_str)
        
        ticket_description = f'''
<div class="mesa-vt-hero" data-mesa-vt-hero="1">
    <div class="mesa-vt-hero__inner">
        <span class="mesa-vt-hero__badge">Visita técnica</span>
        <h3 class="mesa-vt-hero__title"><span class="mesa-vt-hero__title-icon" aria-hidden="true">&#128196;</span> Información de la Visita Técnica</h3>
        <div class="mesa-vt-hero__grid">
            <div class="mesa-vt-hero__item"><span class="mesa-vt-hero__item-label">Referencia</span><span class="mesa-vt-hero__item-value">{safe_name}</span></div>
            <div class="mesa-vt-hero__item"><span class="mesa-vt-hero__item-label">Cliente</span><span class="mesa-vt-hero__item-value">{safe_partner}</span></div>
            <div class="mesa-vt-hero__item"><span class="mesa-vt-hero__item-label">Fecha programada</span><span class="mesa-vt-hero__item-value">{safe_sched}</span></div>
            <div class="mesa-vt-hero__item"><span class="mesa-vt-hero__item-label">Técnicos asignados</span><span class="mesa-vt-hero__item-value">{safe_tech}</span></div>
        </div>
</div>
</div>
'''
        
        # Agregar descripción adicional si existe
        if self.description:
            safe_desc = escape(self.description)
            ticket_description += f'<div class="mesa-vt-order-desc" style="margin-top: 15px;"><p><strong>Descripción:</strong></p><p>{safe_desc}</p></div>'
        
        # Crear el ticket
        visit_category = self.env['helpdesk.ticket']._mesa_default_visit_ticket_category()
        if not visit_category:
            _logger.warning(
                'No se encontró la categoría helpdesk «Visita técnica programada» (SERVICIO AL CLIENTE); '
                'el ticket de la orden %s se crea sin category_id.',
                self.name,
            )
        ticket_vals = {
            'name': ticket_name,
            'partner_id': self.partner_id.id,
            'description': ticket_description,
            'maintenance_order_id': self.id,
            'maintenance_category': 'maintenance',
            'user_id': self.technician_ids[0].id if self.technician_ids else self.env.user.id,
            'visit_helpdesk_category_locked': True,
        }
        if visit_category:
            ticket_vals['category_id'] = visit_category.id
        ticket = self.env['helpdesk.ticket'].create(ticket_vals)
        
        # Vincular el ticket a la orden
        self.ticket_id = ticket.id
        
        # Notificar en el chatter
        self.message_post(
            body=_('Ticket creado automáticamente: %s') % ticket.name,
            subject=_('Ticket Creado')
        )
        
        return ticket
    
    def _update_ticket_with_equipment(self):
        """Actualizar el ticket con información de los equipos agregados."""
        self.ensure_one()
        if not self.ticket_id:
            return
        
        # Crear tabla HTML organizada de equipos
        equipment_rows = []
        for maintenance in self.maintenance_ids:
            if maintenance.lot_id:
                # Equipo de la empresa (stock.lot)
                plate = maintenance.lot_id.inventory_plate or _('Sin placa')
                serial = maintenance.lot_id.name or _('N/A')
                product = maintenance.lot_id.product_id.name if maintenance.lot_id.product_id else _('N/A')
                equipment_type = _('Empresa')
                
                equipment_rows.append(
                    '<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'
                    % (
                        escape(serial),
                        escape(plate),
                        escape(product),
                        escape(equipment_type),
                    )
                )
        
        if equipment_rows:
            equipment_section = f'''
<div class="mesa-vt-equipment-section" data-mesa-equipment-block="1">
<h3>Equipos en esta Orden ({len(equipment_rows)} equipo(s))</h3>
<table>
<thead>
<tr>
<th>Número de Serie</th>
<th>Placa de Inventario</th>
<th>Producto</th>
<th>Tipo</th>
</tr>
</thead>
<tbody>
{''.join(equipment_rows)}
</tbody>
</table>
</div>
'''
            
            # Actualizar descripción manteniendo la información original
            current_description = self.ticket_id.description or ''
            # Eliminar la sección de equipos anterior si existe (tanto texto como HTML)
            import re as re_module
            # Quitar bloque de equipos (formato nuevo con data-mesa-equipment-block o formato antiguo)
            current_description = re_module.sub(
                r'<div\b[^>]*\bdata-mesa-equipment-block="1"[^>]*>[\s\S]*?</div>\s*',
                '',
                current_description,
                flags=re_module.DOTALL,
            )
            current_description = re_module.sub(
                r'<div[^>]*>.*?Equipos en esta Orden.*?</div>', '', current_description, flags=re_module.DOTALL
            )
            # Eliminar sección de texto de equipos
            if '--- Equipos en esta orden ---' in current_description:
                parts = current_description.split('--- Equipos en esta orden ---')
                current_description = parts[0].strip()
            
            # Combinar descripción original con nueva sección de equipos
            if current_description:
                self.ticket_id.description = current_description + equipment_section
            else:
                self.ticket_id.description = equipment_section
            
            # Notificar en el chatter del ticket
            self.ticket_id.message_post(
                body=_('Equipos actualizados en la orden de mantenimiento %s. Total: %d equipo(s).') % (
                    self.name,
                    len(equipment_rows)
                ),
                subject=_('Actualización de Equipos')
            )
    
    def _update_ticket_status(self):
        """Actualizar el estado del ticket según el estado de la orden."""
        self.ensure_one()
        if not self.ticket_id:
            return
        
        # Obtener la etiqueta del estado actual
        status_label = dict(self._fields['state'].selection).get(self.state, self.state)
        
        # Notificar en el chatter del ticket sobre el cambio de estado
        try:
            self.ticket_id.message_post(
                body=_('Estado de la orden de mantenimiento %s actualizado a: %s') % (
                    self.name,
                    status_label
                ),
                subject=_('Actualización de Estado')
            )
        except Exception as e:
            _logger.warning("No se pudo actualizar el mensaje del ticket: %s", str(e))
        
        # Intentar actualizar el stage del ticket si existe el modelo y el campo
        # Envolver todo en try-except para que no falle si el modelo no existe
        try:
            if hasattr(self.ticket_id, 'stage_id'):
                # Mapeo de estados de orden a nombres de stages comunes
                stage_name_mapping = {
                    'draft': 'Nuevo',
                    'scheduled': 'En Progreso',
                    'in_progress': 'En Progreso',
                    'completed': 'Cerrado',
                    'cancelled': 'Cancelado',
                }
                
                stage_name = stage_name_mapping.get(self.state)
                if stage_name:
                    # Intentar buscar stage - puede fallar si el modelo no existe
                    # Envolver la búsqueda del modelo en try-except
                    try:
                        stages = self.env['helpdesk.ticket.stage'].search([
                            ('name', 'ilike', stage_name)
                        ], limit=1)
                        if stages:
                            self.ticket_id.stage_id = stages[0].id
                    except KeyError:
                        # El modelo no existe, simplemente ignorar
                        pass
        except Exception as e:
            # Si hay cualquier otro error, solo loguearlo pero no fallar
            _logger.debug("No se pudo actualizar el stage del ticket: %s", str(e))
    
    def _cancel_ticket(self):
        """Cancelar el ticket asociado cuando se cancela la orden de mantenimiento."""
        self.ensure_one()
        if not self.ticket_id:
            _logger.warning("La orden %s no tiene ticket asociado para cancelar", self.name)
            return
        
        _logger.info("Iniciando proceso de cancelar ticket %s para la orden %s", self.ticket_id.name, self.name)
        
        try:
            # Actualizar la descripción del ticket con información de cancelación
            cancellation_message = _('=== VISITA TÉCNICA CANCELADA ===\n')
            cancellation_message += _('Visita Técnica: %s\n') % self.name
            cancellation_message += _('Cliente: %s\n') % (self.partner_id.name or 'N/A')
            cancellation_message += _('Fecha de Cancelación: %s\n') % fields.Datetime.now().strftime('%d/%m/%Y %H:%M:%S')
            cancellation_message += _('\nEsta visita técnica ha sido cancelada.')
            
            # Actualizar descripción del ticket
            new_description = (self.ticket_id.description or '') + '\n\n' + cancellation_message
            self.ticket_id.description = new_description
            
            # Buscar stage "Cancelado" y mover el ticket a ese stage
            ticket_cancelled = False
            try:
                if hasattr(self.ticket_id, 'stage_id') and self.ticket_id.stage_id:
                    stage_model = self.ticket_id.stage_id._name
                    _logger.info("🔍 Buscando stage de Cancelado para ticket %s", self.ticket_id.name)
                    
                    try:
                        # Buscar todos los stages disponibles
                        all_stages = self.env[stage_model].search([], order='sequence')
                        
                        # Estrategia 1: Buscar por nombre "Cancelado"
                        stage_names_to_search = ['Cancelado', 'Cancel', 'Cancelad', 'Anulado', 'Anular', 'Cancelled']
                        
                        for stage_name in stage_names_to_search:
                            try:
                                cancelled_stages = self.env[stage_model].search([
                                    ('name', 'ilike', stage_name)
                                ], limit=1)
                                
                                if cancelled_stages:
                                    self.ticket_id.sudo().write({'stage_id': cancelled_stages[0].id})
                                    self.ticket_id.invalidate_recordset(['stage_id'])
                                    ticket_cancelled = True
                                    _logger.info("✅ Ticket %s cancelado usando stage '%s': %s", self.ticket_id.name, stage_name, cancelled_stages[0].name)
                                    break
                            except Exception as search_error:
                                _logger.debug("Error al buscar stage '%s': %s", stage_name, str(search_error))
                        
                        # Estrategia 2: Si no se encuentra, usar un stage intermedio o el último
                        if not ticket_cancelled and all_stages:
                            # Intentar usar un stage que no sea "Nuevo" o "En Progreso"
                            intermediate_stages = all_stages.filtered(
                                lambda s: s.name.lower() not in ['nuevo', 'new', 'en progreso', 'in progress', 'en proceso']
                            )
                            if intermediate_stages:
                                target_stage = intermediate_stages[0]
                            else:
                                target_stage = all_stages[-1]  # Último stage
                            
                            try:
                                self.ticket_id.sudo().write({'stage_id': target_stage.id})
                                self.ticket_id.invalidate_recordset(['stage_id'])
                                ticket_cancelled = True
                                _logger.info("✅ Ticket %s movido a stage intermedio: %s", self.ticket_id.name, target_stage.name)
                            except Exception as stage_error:
                                _logger.error("❌ Error al mover ticket a stage: %s. Traceback: %s", str(stage_error), traceback.format_exc())
                    except Exception as model_error:
                        _logger.error("❌ Error al acceder al modelo '%s': %s. Traceback: %s", stage_model, str(model_error), traceback.format_exc())
                else:
                    _logger.warning("⚠️ El ticket no tiene campo stage_id o no tiene un stage asignado")
                    
            except Exception as e:
                _logger.error("❌ Error al cancelar el ticket automáticamente: %s. Traceback: %s", str(e), traceback.format_exc())
            
            # Notificar en el chatter del ticket
            status_message = _('La orden de mantenimiento %s ha sido cancelada.') % self.name
            if not ticket_cancelled:
                status_message += _(' ⚠️ El ticket no se pudo cancelar automáticamente, por favor cancelarlo manualmente.')
            
            self.ticket_id.message_post(
                body=status_message,
                subject=_('Orden Cancelada')
            )
            
            _logger.info("✅ Proceso de cancelar ticket finalizado para la orden %s. Ticket cancelado: %s", self.name, ticket_cancelled)
            
        except Exception as e:
            _logger.error("❌ Error al cancelar el ticket: %s. Traceback: %s", str(e), traceback.format_exc())
    
    def _mesa_acta_parse_equipment_summary_rows(self, html_content):
        """Serie, placa y producto: solo tablas de equipo del acta (cabecera Serie/Placa), no tablas de contactos."""
        rows = []
        if not html_content:
            return rows
        for m in re.finditer(r'<table\b[^>]*>[\s\S]*?</table\s*>', html_content, re.I):
            table_html = m.group(0)
            if not _mesa_acta_table_html_is_equipment_block(table_html):
                continue
            m_tb = re.search(r'<tbody\b[^>]*>([\s\S]*?)</tbody\s*>', table_html, re.I)
            if not m_tb:
                continue
            chunk = m_tb.group(1)
            m = re.search(
                r'<tr[^>]*>\s*<td[^>]*>([\s\S]*?)</td>\s*<td[^>]*>([\s\S]*?)</td>\s*<td[^>]*>([\s\S]*?)</td>',
                chunk,
                re.I,
            )
            if m:

                def _cell(raw):
                    t = re.sub(r'<[^>]+>', '', raw or '').strip()
                    return html_stdlib.unescape(t)

                rows.append((_cell(m.group(1)), _cell(m.group(2)), _cell(m.group(3))))
        return rows

    def _mesa_parse_close_summary_li_rows(self, html_content):
        """Triple serie/placa/producto desde <li> del resumen de cierre (mismo HTML que va a la descripción del ticket)."""
        rows = []
        if not html_content:
            return rows
        for m in re.finditer(r'<li\b[^>]*>([\s\S]*?)</li\s*>', html_content, re.I):
            inner = re.sub(r'<[^>]+>', '', m.group(1) or '')
            inner = html_stdlib.unescape(inner).strip()
            if not inner:
                continue
            # "Serie X · Placa Y — producto" (escape) o "Serie X - Placa Y — producto"
            ma = re.match(
                r'(?i)^serie\s+(.+?)\s*[·\.]\s*placa\s+(.+?)\s*[—–\-]\s*(.+)$',
                inner,
            )
            if not ma:
                ma = re.match(
                    r'(?i)^serie\s+(.+?)\s+-\s+placa\s+(.+?)\s*[—–\-]\s*(.+)$',
                    inner,
                )
            if ma:
                rows.append((ma.group(1).strip(), ma.group(2).strip(), ma.group(3).strip()))
        return rows

    def _mesa_acta_equipment_block_html_chunk_for_lot(self, lot):
        """Fragmento HTML del bloque de un equipo (desde la tabla con ``data-mesa-acta-equipment-lot-id``)."""
        self.ensure_one()
        if not lot:
            return ''
        html = str(self.visit_documentation_html or '')
        if not html:
            return ''
        anchor = re.search(
            rf'data-mesa-acta-equipment-lot-id=["\']{int(lot.id)}["\']',
            html,
            re.I,
        )
        if not anchor:
            return ''
        start = anchor.start()
        rest = html[start:]
        next_anchor = re.search(
            r'data-mesa-acta-equipment-lot-id=["\']\d+["\']',
            rest[80:],
            re.I,
        )
        end = start + 80 + next_anchor.start() if next_anchor else len(html)
        return html[start:end]

    def _mesa_acta_equipment_followup_flags_for_lot(self, lot):
        """Banderas activas en «Realizado» (botones del acta) para este lote."""
        from odoo.addons.mesa_ayuda_inventario.wizard.acta_html_blocks import MESA_ACTA_FOLLOWUP_FLAG_KEYS

        chunk = self._mesa_acta_equipment_block_html_chunk_for_lot(lot)
        if not chunk:
            return set()
        active = set()
        for key in MESA_ACTA_FOLLOWUP_FLAG_KEYS:
            if re.search(
                rf'data-mesa-acta-flag=["\']{re.escape(key)}["\'][^>]*data-mesa-acta-flag-active=["\']1["\']',
                chunk,
                re.I,
            ):
                active.add(key)
                continue
            if re.search(
                rf'data-mesa-acta-flag=["\']{re.escape(key)}["\'][^>]*\bchecked\b',
                chunk,
                re.I,
            ):
                active.add(key)
        return active

    def _mesa_acta_fallback_equipment_block_html(self, lot):
        """Mismo bloque visual que inserta el wizard de acta, con datos del lote y «Realizado» desde la línea de orden."""
        self.ensure_one()
        if not lot:
            return ''
        maint = self.maintenance_ids.filtered(lambda m: m.lot_id and m.lot_id.id == lot.id)[:1]
        realizado_inner = '<p><br></p>'
        if maint and maint.description and not mail_tools.is_html_empty(maint.description):
            realizado_inner = maint.description
        th_serie = _('Serie')
        th_placa = _('Placa')
        th_prod = _('Producto')
        th_realizado = _('Realizado')
        from odoo.addons.mesa_ayuda_inventario.wizard.acta_html_blocks import mesa_acta_equipment_block_html

        serial = escape(lot.name or '')
        plate_txt = (lot.inventory_plate or '').strip() or _('Sin placa')
        plate = escape(plate_txt)
        prod = escape(lot.product_id.display_name if lot.product_id else _('N/A'))
        return mesa_acta_equipment_block_html(
            lot.id, th_serie, th_placa, th_prod, serial, plate, prod, th_realizado,
            realizado_inner=realizado_inner,
            lbl_equipment_change=_('Cambio de Equipo'),
            lbl_component_change=_('Cambio de Componente'),
            lbl_maintenance_repair=_('Mantenimiento/Reparación'),
        )

    def _mesa_acta_html_equipment_block_for_lot(self, lot):
        """Fragmento HTML del acta (un bloque por equipo del wizard) que corresponde al lote, o plantilla equivalente."""
        self.ensure_one()
        ticket = self.ticket_id
        if not lot or not ticket:
            return ''
        html_content = (self.visit_documentation_html or '').strip()
        if not html_content:
            return self._mesa_acta_fallback_equipment_block_html(lot)
        token = (lot.name or '').strip()
        plate = (lot.inventory_plate or '').strip().lower()
        pos = 0
        while pos < len(html_content):
            m_tb = re.search(r'<tbody\b[^>]*>', html_content[pos:], re.I)
            if not m_tb:
                break
            tbody_tag_start = pos + m_tb.start()
            start_inner = pos + m_tb.end()
            rel = html_content[start_inner:]
            m_end = re.search(r'</tbody\s*>', rel, re.I)
            if not m_end:
                break
            chunk = rel[: m_end.start()]
            pos = start_inner + m_end.end()
            m = re.search(
                r'<tr[^>]*>\s*<td[^>]*>([\s\S]*?)</td>\s*<td[^>]*>([\s\S]*?)</td>',
                chunk,
                re.I,
            )
            if not m:
                continue

            def _plain_cell(raw):
                t = re.sub(r'<[^>]+>', '', raw or '').strip()
                return html_stdlib.unescape(t)

            c1 = ticket.sudo()._mesa_strip_acta_serial_cell(_plain_cell(m.group(1)))
            c2 = ticket.sudo()._mesa_strip_acta_plate_cell(_plain_cell(m.group(2)))
            match = (token and c1.lower() == token.lower()) or (plate and c2.lower() == plate)
            if not match:
                continue
            prefix = html_content[:tbody_tag_start]
            open_idx = -1
            for mdiv in re.finditer(r'<div\s+style="[^"]*margin-bottom:\s*16px[^"]*"', prefix, re.I):
                open_idx = mdiv.start()
            if open_idx < 0:
                return self._mesa_acta_fallback_equipment_block_html(lot)
            sliced = _mesa_html_slice_balanced_div(html_content, open_idx)
            if sliced:
                return sliced
            return self._mesa_acta_fallback_equipment_block_html(lot)
        return self._mesa_acta_fallback_equipment_block_html(lot)

    def _mesa_acta_fallback_contact_block_html(self, partner):
        """Bloque HTML tipo acta para un contacto del cliente (sin coincidencia en el HTML guardado)."""
        self.ensure_one()
        if not partner:
            return ''
        th_name = _('Nombre')
        th_email = _('Correo')
        th_phone = _('Teléfono')
        th_realizado = _('Realizado')
        realizado_inner = '<p><br></p>'
        from odoo.addons.mesa_ayuda_inventario.wizard.acta_html_blocks import mesa_acta_participant_partner_block_html

        name = escape(partner.display_name or partner.name or '')
        email = escape(partner.email or '')
        phone = escape(
            partner.phone
            or getattr(partner, 'mobile', None)
            or getattr(partner, 'mobile_phone', None)
            or ''
        )
        return mesa_acta_participant_partner_block_html(
            partner.id, th_name, th_email, th_phone, name, email, phone, th_realizado,
            realizado_inner=realizado_inner,
        )

    def _mesa_acta_html_contact_block_for_partner(self, partner):
        """Fragmento HTML del acta del bloque de contacto (``data-mesa-acta-participant-partner-id``; admite legacy user-id)."""
        self.ensure_one()
        if not partner:
            return ''
        html_content = (self.visit_documentation_html or '').strip()
        if not html_content:
            return self._mesa_acta_fallback_contact_block_html(partner)
        pat = r'<div\b[^>]*data-mesa-acta-participant-partner-id=["\']%d["\'][^>]*>' % partner.id
        m = re.search(pat, html_content, re.I)
        if m:
            open_idx = m.start()
            sliced = _mesa_html_slice_balanced_div(html_content, open_idx)
            if sliced:
                return sliced
            return self._mesa_acta_fallback_contact_block_html(partner)
        Users = self.env['res.users'].sudo()
        for uid in partner.user_ids.ids:
            u = Users.browse(uid)
            if u.exists() and u.active:
                legacy = self._mesa_acta_html_participant_block_for_user(u)
                if legacy:
                    return legacy
        return self._mesa_acta_fallback_contact_block_html(partner)

    def _mesa_acta_fallback_participant_block_html(self, user):
        """Bloque HTML tipo acta para un usuario del cliente (sin coincidencia en el HTML guardado)."""
        self.ensure_one()
        if not user:
            return ''
        th_name = _('Nombre')
        th_login = _('Usuario')
        th_email = _('Correo')
        th_realizado = _('Realizado')
        realizado_inner = '<p><br></p>'
        from odoo.addons.mesa_ayuda_inventario.wizard.acta_html_blocks import mesa_acta_participant_user_block_html

        name = escape(user.name or '')
        login = escape(user.login or '')
        email = escape(user.email or '')
        return mesa_acta_participant_user_block_html(
            user.id, th_name, th_login, th_email, name, login, email, th_realizado,
            realizado_inner=realizado_inner,
        )

    def _mesa_acta_html_participant_block_for_user(self, user):
        """Fragmento HTML del acta del bloque de usuario del cliente (data-mesa-acta-participant-user-id)."""
        self.ensure_one()
        if not user:
            return ''
        html_content = (self.visit_documentation_html or '').strip()
        if not html_content:
            return self._mesa_acta_fallback_participant_block_html(user)
        pat = r'<div\b[^>]*data-mesa-acta-participant-user-id=["\']%d["\'][^>]*>' % user.id
        m = re.search(pat, html_content, re.I)
        if not m:
            return self._mesa_acta_fallback_participant_block_html(user)
        open_idx = m.start()
        sliced = _mesa_html_slice_balanced_div(html_content, open_idx)
        if sliced:
            return sliced
        return self._mesa_acta_fallback_participant_block_html(user)

    def _mesa_build_ticket_close_summary_html(self, ticket):
        """Resumen de cierre: tablas separadas para equipos y contactos (sin mezclar con filas de personas)."""
        self.ensure_one()
        ticket._mesa_backfill_acta_lots_if_empty()
        ticket._mesa_backfill_acta_contacts_if_empty()
        rows = self._mesa_acta_parse_equipment_summary_rows(self.visit_documentation_html or '')
        if not rows and ticket.mesa_acta_selected_lot_ids:
            rows = []
            for lot in ticket.mesa_acta_selected_lot_ids:
                rows.append(
                    (
                        (lot.name or '').strip(),
                        (lot.inventory_plate or '').strip() or _('Sin placa'),
                        lot.product_id.display_name if lot.product_id else _('N/A'),
                    )
                )
        table_style = (
            'width:100%;border-collapse:collapse;margin-top:8px;'
            'font-size:13px;border:1px solid #dee2e6;border-radius:6px;overflow:hidden;'
        )
        th_style = (
            'padding:8px 10px;text-align:left;background:#e8eef4;border-bottom:1px solid #dee2e6;'
            'color:#2c3e50;font-weight:600;'
        )
        td_style = 'padding:8px 10px;border-bottom:1px solid #eef2f6;color:#212529;'
        parts = [
            '<p><strong>%s</strong></p>'
            % escape(_('Resumen de cierre de la visita')),
            '<p style="color:#495057;margin-bottom:12px;">%s</p>'
            % escape(
                _(
                    'Se documentó la visita en el acta. A continuación constan los equipos y las personas '
                    'registradas; el detalle por ítem está en la pestaña «Acta de visita».'
                )
            ),
        ]
        if rows:
            parts.append('<p style="margin:16px 0 4px 0;"><strong>%s</strong></p>' % escape(_('Equipos')))
            parts.append('<table style="%s"><thead><tr>' % table_style)
            parts.append(
                '<th style="%s">%s</th><th style="%s">%s</th><th style="%s">%s</th></tr></thead><tbody>'
                % (
                    th_style,
                    escape(_('Serie')),
                    th_style,
                    escape(_('Placa')),
                    th_style,
                    escape(_('Producto')),
                )
            )
            for serie, placa, prod in rows:
                parts.append(
                    '<tr><td style="%s">%s</td><td style="%s">%s</td><td style="%s">%s</td></tr>'
                    % (
                        td_style,
                        escape(serie or '-'),
                        td_style,
                        escape(placa or _('sin placa')),
                        td_style,
                        escape(prod or '-'),
                    )
                )
            parts.append('</tbody></table>')
        else:
            parts.append(
                '<p style="color:#6c757d;font-style:italic;margin-top:8px;">%s</p>'
                % escape(_('No se detectaron tablas de equipo en el acta; revise la pestaña «Acta de visita».'))
            )
        if ticket.mesa_acta_selected_contact_ids:
            parts.append(
                '<p style="margin:20px 0 4px 0;"><strong>%s</strong></p>'
                % escape(_('Personas de contacto en la visita'))
            )
            parts.append('<table style="%s"><thead><tr>' % table_style)
            parts.append(
                '<th style="%s">%s</th><th style="%s">%s</th><th style="%s">%s</th></tr></thead><tbody>'
                % (
                    th_style,
                    escape(_('Nombre')),
                    th_style,
                    escape(_('Correo')),
                    th_style,
                    escape(_('Teléfono')),
                )
            )
            for collab in ticket.mesa_acta_selected_contact_ids.sorted(
                lambda p: ((p.name or ''), (p.email or ''))
            ):
                nombre = (collab.name or '').strip() or (collab.display_name or '').strip() or '-'
                correo = collab.email or _('sin correo')
                tel = (
                    collab.phone
                    or getattr(collab, 'mobile', None)
                    or getattr(collab, 'mobile_phone', None)
                    or _('sin teléfono')
                )
                parts.append(
                    '<tr><td style="%s">%s</td><td style="%s">%s</td><td style="%s">%s</td></tr>'
                    % (
                        td_style,
                        escape(nombre),
                        td_style,
                        escape(str(correo)),
                        td_style,
                        escape(str(tel)),
                    )
                )
            parts.append('</tbody></table>')
        return ''.join(parts)

    def _complete_ticket_with_details(self):
        """Al completar la orden: resumen en descripción del ticket, tickets hijos por acta, cerrar etapa, PDF y chatter."""
        self.ensure_one()
        if not self.ticket_id:
            _logger.warning("La orden %s no tiene ticket asociado", self.name)
            return
        
        _logger.info("Iniciando proceso de completar ticket %s para la orden %s", self.ticket_id.name, self.name)
        
        try:
            # 1. Descripción del ticket: resumen breve (el acta completo sigue en la pestaña «Acta de visita»)
            acta_raw = (self.visit_documentation_html or '').strip()
            if acta_raw and not mail_tools.is_html_empty(self.visit_documentation_html):
                ticket = self.ticket_id
                summary_body = self._mesa_build_ticket_close_summary_html(ticket)
                self.mesa_visit_pdf_summary_html = summary_body
                desc_field = ticket._fields.get('description')
                if desc_field:
                    start_marker = '<!--MESA_ACTA_CIERRE_START-->'
                    end_marker = '<!--MESA_ACTA_CIERRE_END-->'
                    inner = (
                        '<div style="margin-top:16px;padding:14px 16px;border-left:4px solid #0d6efd;'
                        'background:#f8fafc;border-radius:6px;">'
                        '<h3 style="color:#0b5ed7;margin-top:0;font-size:1.05rem;">%s</h3>%s</div>'
                    ) % (_('Cierre de visita'), summary_body)
                    block = '%s%s%s' % (start_marker, inner, end_marker)
                    prev = ticket.description or ''
                    if start_marker in prev and end_marker in prev:
                        prev = re.sub(
                            r'<!--MESA_ACTA_CIERRE_START-->.*?<!--MESA_ACTA_CIERRE_END-->',
                            '',
                            prev,
                            count=1,
                            flags=re.DOTALL,
                        )
                    if desc_field.type == 'html':
                        # Markup evita doble escape en campos Html; el widget html en la vista muestra el acta formateado.
                        ticket.sudo().write({'description': Markup(prev or '') + Markup(block)})
                    else:
                        ticket.sudo().write({'description': (prev + html2plaintext(inner)).strip()})
            else:
                _logger.info(
                    'Orden %s completada sin contenido en acta de visita; no se inyecta bloque en descripción del ticket.',
                    self.name,
                )
                self.mesa_visit_pdf_summary_html = False

            # 1b. Tickets hijos desde el acta: mismo instante que «Completar» en la orden (no solo si la etapa final es «Resuelto»)
            visit_ticket = self.ticket_id.sudo()
            if hasattr(visit_ticket, '_mesa_try_create_acta_followup_tickets'):
                try:
                    visit_ticket._mesa_try_create_acta_followup_tickets()
                except Exception as followup_err:
                    _logger.error(
                        'Error al crear tickets hijos desde el acta al completar la orden %s: %s',
                        self.name,
                        str(followup_err),
                        exc_info=True,
                    )
            
            # 2. Cerrar el ticket (buscar stage "Cerrado" o "Resuelto")
            ticket_closed = False
            try:
                if hasattr(self.ticket_id, 'stage_id') and self.ticket_id.stage_id:
                    # Acceder al modelo de stages a través del campo stage_id del ticket
                    stage_model = self.ticket_id.stage_id._name
                    _logger.info("🔍 Modelo de stage encontrado a través del ticket: %s", stage_model)
                    
                    try:
                        # Buscar todos los stages disponibles primero para debug
                        all_stages = self.env[stage_model].search([], order='sequence')
                        stage_names = all_stages.mapped('name')
                        _logger.info("🔍 Stages disponibles en el sistema (%d): %s", len(all_stages), ', '.join(stage_names))
                        
                        # Estrategia 1: Buscar por campo 'closed' si existe
                        try:
                            closed_stage = self.env[stage_model].search([
                                ('closed', '=', True)
                            ], limit=1, order='sequence desc')
                            
                            if closed_stage:
                                tw = self.env['helpdesk.ticket'].sudo()._mesa_merge_kanban_done_if_available(
                                    {'stage_id': closed_stage[0].id}
                                )
                                self.ticket_id.sudo().write(tw)
                                self.ticket_id.invalidate_recordset(['stage_id'])
                                ticket_closed = True
                                _logger.info("✅ Ticket %s cerrado usando stage con closed=True: %s", self.ticket_id.name, closed_stage[0].name)
                        except Exception as e:
                            _logger.debug("Campo 'closed' no existe en stages: %s", str(e))
                        
                        # Estrategia 2: Buscar por nombre (variaciones comunes)
                        if not ticket_closed:
                            stage_names_to_search = ['Resuelto', 'Cerrado', 'Cerr', 'Resuel', 'Finalizado', 'Completado', 'Done', 'Solved']
                            
                            for stage_name in stage_names_to_search:
                                try:
                                    closed_stages_by_name = self.env[stage_model].search([
                                        ('name', 'ilike', stage_name)
                                    ], limit=1)
                                    
                                    if closed_stages_by_name:
                                        tw = self.env['helpdesk.ticket'].sudo()._mesa_merge_kanban_done_if_available(
                                            {'stage_id': closed_stages_by_name[0].id}
                                        )
                                        self.ticket_id.sudo().write(tw)
                                        self.ticket_id.invalidate_recordset(['stage_id'])
                                        ticket_closed = True
                                        _logger.info("✅ Ticket %s cerrado usando stage por nombre '%s': %s", self.ticket_id.name, stage_name, closed_stages_by_name[0].name)
                                        break
                                except Exception as search_error:
                                    _logger.debug("Error al buscar stage '%s': %s", stage_name, str(search_error))
                        
                        # Estrategia 3: Si no se encuentra, usar el último stage por sequence
                        if not ticket_closed and all_stages:
                            last_stage = all_stages[-1]  # El último por sequence
                            try:
                                tw = self.env['helpdesk.ticket'].sudo()._mesa_merge_kanban_done_if_available(
                                    {'stage_id': last_stage.id}
                                )
                                self.ticket_id.sudo().write(tw)
                                self.ticket_id.invalidate_recordset(['stage_id'])
                                ticket_closed = True
                                _logger.info("✅ Ticket %s movido al último stage disponible: %s (ID: %s)", self.ticket_id.name, last_stage.name, last_stage.id)
                            except Exception as stage_error:
                                _logger.error("❌ Error al mover ticket al último stage: %s. Traceback: %s", str(stage_error), traceback.format_exc())
                    except Exception as model_error:
                        _logger.error("❌ Error al acceder al modelo '%s': %s. Traceback: %s", stage_model, str(model_error), traceback.format_exc())
                else:
                    _logger.warning("⚠️ El ticket no tiene campo stage_id o no tiene un stage asignado")
                    
            except Exception as e:
                _logger.error("❌ Error al cerrar el ticket automáticamente: %s. Traceback: %s", str(e), traceback.format_exc())
            
            if not ticket_closed:
                _logger.warning("⚠️ El ticket %s NO se cerró automáticamente. Por favor cerrarlo manualmente.", self.ticket_id.name)
            
            # 3. Generar y adjuntar el reporte PDF
            pdf_attached = False
            try:
                report_action = self.env.ref('mesa_ayuda_inventario.action_report_maintenance_order', raise_if_not_found=False)
                if not report_action:
                    _logger.warning("⚠️ No se encontró la acción del reporte: mesa_ayuda_inventario.action_report_maintenance_order")
                else:
                    _logger.info("📄 Generando PDF para la orden %s (ID: %s)", self.name, self.id)
                    
                    # Intentar generar el PDF
                    try:
                        # Usar el método correcto para renderizar el PDF
                        # Obtener el report_ref desde el report_name del reporte
                        report_ref = report_action.report_name or 'mesa_ayuda_inventario.report_maintenance_order'
                        _logger.info("📄 Intentando generar PDF con report_ref: %s para orden ID: %s", report_ref, self.id)
                        
                        # Llamar al método con los parámetros correctos
                        pdf_content, dummy_report_format = report_action._render_qweb_pdf(report_ref, res_ids=[self.id], data=None)
                        _logger.info("📄 PDF generado para la orden %s. Tamaño: %s bytes", self.name, len(pdf_content) if pdf_content else 0)
                    except Exception as render_error:
                        _logger.error("❌ Error al renderizar PDF: %s. Traceback: %s", str(render_error), traceback.format_exc())
                        pdf_content = None
                    
                    if not pdf_content:
                        _logger.warning("⚠️ El reporte PDF está vacío o no se generó para la orden %s", self.name)
                    else:
                        # Crear adjunto del reporte
                        attachment_name = 'Reporte_Orden_Mantenimiento_%s.pdf' % self.name.replace('/', '_')
                        
                        # Asegurar que pdf_content sea bytes
                        if isinstance(pdf_content, str):
                            pdf_content = pdf_content.encode('utf-8')
                        elif not isinstance(pdf_content, bytes):
                            try:
                                pdf_content = bytes(pdf_content)
                            except:
                                pdf_content = str(pdf_content).encode('utf-8')
                        
                        try:
                            attachment = self.env['ir.attachment'].sudo().create({
                                'name': attachment_name,
                                'type': 'binary',
                                'datas': base64.b64encode(pdf_content).decode('ascii'),
                                'res_model': 'helpdesk.ticket',
                                'res_id': self.ticket_id.id,
                                'mimetype': 'application/pdf',
                            })
                            
                            pdf_attached = True
                            _logger.info("✅ PDF adjuntado al ticket %s (ID: %s): %s", self.ticket_id.name, self.ticket_id.id, attachment_name)
                            
                            # Notificar en el chatter del ticket
                            self.ticket_id.message_post(
                                body=_('✅ Reporte PDF de la orden de mantenimiento adjuntado: %s') % attachment_name,
                                subject=_('Reporte Adjuntado'),
                                attachment_ids=[attachment.id]
                            )
                        except Exception as attach_error:
                            _logger.error("❌ Error al crear adjunto: %s. Traceback: %s", str(attach_error), traceback.format_exc())
                            
            except Exception as e:
                _logger.error("❌ Error al generar o adjuntar el reporte PDF al ticket: %s. Traceback: %s", str(e), traceback.format_exc())
            
            if not pdf_attached:
                _logger.warning("⚠️ El reporte PDF NO se adjuntó al ticket %s", self.ticket_id.name)
            
            # 4. Notificar en el chatter del ticket sobre el cierre
            status_message = _('✅ Visita técnica completada.')
            if ticket_closed:
                status_message += _(' El ticket ha sido cerrado automáticamente.')
            else:
                status_message += _(' ⚠️ El ticket no se pudo cerrar automáticamente, por favor cerrarlo manualmente.')
            
            if pdf_attached:
                status_message += _(' Reporte PDF adjuntado.')
            else:
                status_message += _(' ⚠️ El reporte PDF no se pudo adjuntar.')
            
            self.ticket_id.message_post(
                body=status_message,
                subject=_('Orden Completada')
            )
            
            _logger.info("✅ Proceso de completar ticket finalizado para la orden %s. Ticket cerrado: %s, PDF adjuntado: %s", self.name, ticket_closed, pdf_attached)
            
        except Exception as e:
            _logger.error("❌ Error al completar el ticket con detalles: %s. Traceback: %s", str(e), traceback.format_exc())
    
    # ========== MÉTODOS PARA CALENDARIO Y VISITAS PROGRAMADAS ==========
    
    def _create_calendar_events(self):
        """Crear eventos de calendario para cada técnico asignado."""
        self.ensure_one()
        
        # No crear eventos si no hay fecha programada o técnicos
        if not self.scheduled_date or not self.technician_ids:
            return
        
        # Eliminar eventos existentes primero
        if self.calendar_event_ids:
            self.calendar_event_ids.unlink()
        
        # Calcular fecha de fin (usar deadline_date si existe, sino 2 horas después)
        start_date = self.scheduled_date
        if self.deadline_date:
            stop_date = self.deadline_date
        else:
            # Por defecto, 2 horas de duración
            from datetime import timedelta
            if isinstance(start_date, str):
                start_date = fields.Datetime.from_string(start_date)
            stop_date = start_date + timedelta(hours=2)
        
        # Preparar descripción del evento
        description_parts = []
        if self.partner_id:
            description_parts.append(f"Cliente: {self.partner_id.name}")
        if self.visit_purpose:
            description_parts.append(f"Propósito: {self.visit_purpose}")
        elif self.description:
            # Limpiar HTML si existe
            clean_description = re.sub('<[^<]+?>', '', self.description)
            clean_description = clean_description.replace('&nbsp;', ' ').strip()
            if clean_description:
                description_parts.append(f"Descripción: {clean_description[:200]}")
        
        description = '\n'.join(description_parts) if description_parts else ''
        
        # Crear un evento para cada técnico (o un evento compartido)
        # Opción 1: Un evento compartido con todos los técnicos
        event_vals = {
            'name': self._format_calendar_event_name(),
            'start': start_date,
            'stop': stop_date,
            'partner_ids': [(6, 0, [self.partner_id.id])] if self.partner_id else [],
            'user_id': self.technician_ids[0].id if self.technician_ids else self.env.user.id,
            'description': description or '',
            'location': self.partner_id.street if self.partner_id and self.partner_id.street else '',
            'categ_ids': [(6, 0, [])],  # Categorías opcionales
        }
        
        # Agregar todos los técnicos como participantes
        attendee_ids = []
        for technician in self.technician_ids:
            attendee_ids.append((0, 0, {
                'partner_id': technician.partner_id.id if technician.partner_id else False,
            }))
        
        if attendee_ids:
            event_vals['attendee_ids'] = attendee_ids
        
        try:
            event = self.env['calendar.event'].create(event_vals)
            self.write({'calendar_event_ids': [(4, event.id)]})
            
            # Notificar en el chatter
            self.message_post(
                body=_('✅ Evento de calendario creado automáticamente para %s') % (
                    ', '.join(self.technician_ids.mapped('name')) if self.technician_ids else 'técnicos asignados'
                ),
                subject=_('Evento de Calendario Creado')
            )
            
            _logger.info("✅ Evento de calendario creado para orden %s: %s", self.name, event.name)
        except Exception as e:
            _logger.error("❌ Error al crear evento de calendario para orden %s: %s. Traceback: %s", 
                         self.name, str(e), traceback.format_exc())
    
    def _update_calendar_events(self):
        """Actualizar eventos de calendario cuando cambian datos."""
        self.ensure_one()
        
        if not self.calendar_event_ids:
            # Si no hay eventos pero hay fecha y técnicos, crear
            if self.scheduled_date and self.technician_ids and self.state != 'cancelled':
                self._create_calendar_events()
            return
        
        # Actualizar eventos existentes
        start_date = self.scheduled_date
        if self.deadline_date:
            stop_date = self.deadline_date
        else:
            from datetime import timedelta
            if isinstance(start_date, str):
                start_date = fields.Datetime.from_string(start_date)
            stop_date = start_date + timedelta(hours=2)
        
        description_parts = []
        if self.partner_id:
            description_parts.append(f"Cliente: {self.partner_id.name}")
        if self.visit_purpose:
            description_parts.append(f"Propósito: {self.visit_purpose}")
        elif self.description:
            clean_description = re.sub('<[^<]+?>', '', self.description)
            clean_description = clean_description.replace('&nbsp;', ' ').strip()
            if clean_description:
                description_parts.append(f"Descripción: {clean_description[:200]}")
        
        description = '\n'.join(description_parts) if description_parts else ''
        
        update_vals = {
            'name': self._format_calendar_event_name(),
            'start': start_date,
            'stop': stop_date,
            'description': description or '',
            'location': self.partner_id.street if self.partner_id and self.partner_id.street else '',
        }
        
        try:
            self.calendar_event_ids.write(update_vals)
            _logger.info("✅ Eventos de calendario actualizados para orden %s", self.name)
        except Exception as e:
            _logger.error("❌ Error al actualizar eventos de calendario para orden %s: %s", 
                         self.name, str(e))
    
    def _cancel_calendar_events(self):
        """Cancelar o eliminar eventos de calendario cuando se cancela la orden."""
        self.ensure_one()
        
        if self.calendar_event_ids:
            try:
                # Eliminar los eventos
                self.calendar_event_ids.unlink()
                _logger.info("✅ Eventos de calendario eliminados para orden cancelada %s", self.name)
            except Exception as e:
                _logger.error("❌ Error al eliminar eventos de calendario para orden %s: %s", 
                             self.name, str(e))
    
    def _schedule_reminder_activities(self):
        """Programar actividades de recordatorio antes de la visita/mantenimiento."""
        self.ensure_one()
        
        if not self.scheduled_date or self.state in ('cancelled', 'completed'):
            return
        
        # Eliminar recordatorios existentes de esta orden
        existing_activities = self.activity_ids.filtered(
            lambda a: a.activity_type_id and 'recordatorio' in a.activity_type_id.name.lower()
        )
        if existing_activities:
            existing_activities.unlink()
        
        # Calcular fecha del recordatorio (1 día antes)
        from datetime import timedelta
        if isinstance(self.scheduled_date, str):
            scheduled_dt = fields.Datetime.from_string(self.scheduled_date)
        else:
            scheduled_dt = self.scheduled_date
        
        reminder_date = scheduled_dt - timedelta(days=1)
        
        # Solo crear recordatorio si la fecha programada es en el futuro
        if reminder_date > fields.Datetime.now():
            visit_label = _('Visita técnica')
            
            # Buscar tipo de actividad "Recordatorio" o crear uno genérico
            activity_type = self.env['mail.activity.type'].search([
                ('name', 'ilike', 'Recordatorio')
            ], limit=1)
            
            if not activity_type:
                # Usar un tipo genérico si no existe
                activity_type = self.env['mail.activity.type'].search([
                    ('category', '=', 'reminder')
                ], limit=1)
            
            # Crear actividad de recordatorio para cada técnico
            for technician in self.technician_ids:
                try:
                    self.activity_schedule(
                        activity_type_id=activity_type.id if activity_type else False,
                        date_deadline=reminder_date.date(),
                        summary=_('Recordatorio: %(visit)s %(ref)s — %(when)s') % {
                            'visit': visit_label,
                            'ref': self.name,
                            'when': scheduled_dt.strftime('%d/%m/%Y %H:%M'),
                        },
                        note=_('Recordatorio de %(visit)s %(ref)s\n\nCliente: %(client)s\nFecha: %(when)s\n%(extra)s') % {
                            'visit': visit_label,
                            'ref': self.name,
                            'client': self.partner_id.name if self.partner_id else 'N/A',
                            'when': scheduled_dt.strftime('%d/%m/%Y %H:%M'),
                            'extra': self.visit_purpose if self.visit_purpose else (self.description or ''),
                        },
                        user_id=technician.id
                    )
                except Exception as e:
                    _logger.warning("No se pudo crear actividad de recordatorio para técnico %s: %s", 
                                   technician.name, str(e))
    
    def action_view_calendar(self):
        """Abrir vista de calendario mostrando esta orden."""
        self.ensure_one()
        if not self.calendar_event_ids:
            raise UserError(_('Esta orden no tiene eventos de calendario asociados.'))
        
        return {
            'name': _('Calendario'),
            'type': 'ir.actions.act_window',
            'res_model': 'calendar.event',
            'view_mode': 'calendar,form',
            'domain': [('id', 'in', self.calendar_event_ids.ids)],
            'target': 'current',
        }


class MaintenanceOrderTechnicianSignature(models.Model):
    """Firmas individuales de técnicos en una orden de mantenimiento."""
    _name = 'maintenance.order.technician.signature'
    _description = 'Firma de Técnico en Orden de Mantenimiento'
    _order = 'technician_id'
    
    order_id = fields.Many2one(
        'maintenance.order',
        string='Orden de Mantenimiento',
        required=True,
        ondelete='cascade',
        index=True,
    )
    
    technician_id = fields.Many2one(
        'res.users',
        string='Técnico',
        required=True,
        help='Técnico que firmó'
    )
    
    signature = fields.Binary(
        string='Firma',
        attachment=False,
        required=False,
        help='Firma digital del técnico'
    )
    
    signature_date = fields.Datetime(
        string='Fecha de Firma',
        default=False,
        required=False,
        readonly=True,
        help='Fecha y hora en que el técnico firmó'
    )
    
    @api.onchange('signature')
    def _onchange_signature(self):
        """Cuando se carga una firma, establecer la fecha automáticamente (similar a customer_signature)."""
        if self.signature:
            if not self.signature_date:
                self.signature_date = fields.Datetime.now()
    
    @api.model
    def create(self, vals):
        """Crear registro de firma."""
        # Si se proporciona una firma, establecer la fecha automáticamente
        if 'signature' in vals and vals.get('signature'):
            # Verificar que la firma tenga contenido válido
            signature_value = vals.get('signature')
            if signature_value not in (False, None, '', b''):
                if not vals.get('signature_date'):
                    vals['signature_date'] = fields.Datetime.now()
        return super().create(vals)
    
    def write(self, vals):
        """Actualizar fecha de firma cuando se guarda una firma (similar a customer_signature)."""
        # Si se está guardando una firma, actualizar la fecha automáticamente
        if 'signature' in vals and vals.get('signature'):
            # Si hay firma, establecer la fecha automáticamente si no existe
            # No verificar el valor en detalle, solo si existe
            if not self.signature_date:
                vals['signature_date'] = fields.Datetime.now()
        result = super().write(vals)
        # Después de guardar, invalidar el caché para refrescar
        if 'signature' in vals:
            self.invalidate_recordset(['signature', 'signature_date'])
        return result

