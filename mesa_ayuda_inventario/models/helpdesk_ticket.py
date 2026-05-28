# -*- coding: utf-8 -*-

import html as html_stdlib
import re

from markupsafe import Markup, escape

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import logging

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


def _mesa_helpdesk_category_path_upper(category):
    """Texto de categoría en mayúsculas; ``complete_name`` no existe en todas las versiones de helpdesk."""
    if not category:
        return ''
    return (getattr(category, 'complete_name', None) or category.name or '').upper()


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

# Campos de negocio que no se pueden escribir si el ticket ya está en etapa final (además de la vista en solo lectura).
_MESA_HELPDESK_WRITE_BLOCKED_WHEN_FINAL = frozenset({
    'name', 'description', 'partner_id', 'partner_name', 'email_from', 'email_cc', 'phone',
    'team_id', 'user_id', 'tag_ids', 'category_id', 'priority', 'stage_id',
    'lot_id', 'maintenance_order_id', 'urgency', 'impact', 'location_site',
    'date_deadline_response', 'date_deadline_resolution',
    'visit_helpdesk_category_locked', 'values_from_category', 'maintenance_category',
    'maintenance_id', 'mesa_acta_selected_lot_ids', 'mesa_acta_selected_contact_ids',
    'mesa_acta_followup_contact_id', 'mesa_parent_visit_ticket_id',
    'mesa_acta_origin_visit_ticket_id', 'mesa_acta_request_type',
    'custom_timer_start', 'custom_timer_accumulated_hours',
    'visit_acta_html',
})


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

    # NUNCA redefinir helpdesk.ticket.description (fields.Html...) — tumba el registro Odoo 19.
    # Este campo debe existir si la BD aún tiene vistas v.124–127 que lo nombran.
    mesa_ticket_detail_html = fields.Html(
        string='Detalle retiro (compatibilidad)',
        copy=False,
    )

    @api.constrains('user_id')
    def _check_assigned_required(self):
        """El campo Asignada a es obligatorio para poder guardar el ticket."""
        for ticket in self:
            if not ticket.user_id:
                raise UserError(_('El ticket debe tener un responsable asignado (Asignada a).'))
    
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
        string='Orden',
        tracking=True,
        help='Orden de mantenimiento relacionada (creada automáticamente por categoría o manualmente)'
    )

    # Mismo HTML que el asistente «informe de visita»: visible en el ticket y editable aquí o desde la visita
    visit_acta_html = fields.Html(
        string='Acta de visita técnica',
        related='maintenance_order_id.visit_documentation_html',
        readonly=False,
    )
    
    maintenance_id = fields.Many2one(
        'stock.lot.maintenance',
        string='Mantenimiento',
        tracking=True,
        help='Mantenimiento relacionado'
    )
    
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

    # Categoría personalizada para distinguir tickets de mantenimiento
    maintenance_category = fields.Selection([
        ('maintenance', 'Mantenimiento'),
        ('repair', 'Reparación'),
        ('support', 'Soporte'),
        ('change', 'Cambio de Equipo'),
        ('other', 'Otro'),
    ], string='Categoría Mantenimiento', tracking=True)

    visit_helpdesk_category_locked = fields.Boolean(
        string='Categoría de visita bloqueada',
        default=False,
        copy=False,
        help='Ticket generado desde una visita técnica (orden de servicio): la categoría de helpdesk no debe modificarse.',
    )

    # Equipos elegidos en el asistente «Insertar equipos» del acta (para generar tickets hijos al resolver la visita)
    mesa_acta_selected_lot_ids = fields.Many2many(
        'stock.lot',
        'mesa_helpdesk_ticket_acta_lot_rel',
        'ticket_id',
        'lot_id',
        string='Equipos insertados en acta (seguimiento)',
        copy=False,
        help='Se actualiza al confirmar «Insertar en el acta» desde este ticket.',
    )
    mesa_acta_selected_contact_ids = fields.Many2many(
        'res.partner',
        'mesa_helpdesk_ticket_acta_contact_rel',
        'ticket_id',
        'partner_id',
        string='Contactos del cliente (acta)',
        copy=False,
        help='Contactos del mismo comercial que el ticket; insertados desde «Contactos del cliente»; generan ticket hijo al completar.',
    )
    mesa_acta_followup_contact_id = fields.Many2one(
        'res.partner',
        string='Seguimiento por contacto del cliente',
        index=True,
        copy=False,
        help='Solo en tickets hijos creados por contacto del cliente en el acta (sin equipo asociado).',
    )
    # Ticket padre cuando este registro es un seguimiento generado al resolver una visita
    mesa_parent_visit_ticket_id = fields.Many2one(
        'helpdesk.ticket',
        string='Hijo de',
        ondelete='set null',
        index=True,
        copy=False,
        help='Ticket de visita técnica del que deriva este seguimiento (un ticket por equipo al resolver la visita).',
    )
    mesa_child_visit_ticket_ids = fields.One2many(
        'helpdesk.ticket',
        'mesa_parent_visit_ticket_id',
        string='Padre de',
        copy=False,
        help='Tickets de seguimiento generados al completar la visita (equipos y contactos del acta).',
    )
    mesa_show_visit_child_relations = fields.Boolean(
        string='Mostrar relación tickets hijos (visita)',
        compute='_compute_mesa_show_visit_child_relations',
        help='True en tickets de visita (no hijos): para mostrar el listado «Padre de» en el formulario.',
    )
    mesa_acta_followup_tickets_created = fields.Boolean(
        string='Tickets seguimiento acta ya generados',
        default=False,
        copy=False,
        help='Evita duplicar tickets hijos si se guarda de nuevo en Resuelto.',
    )
    mesa_acta_origin_visit_ticket_id = fields.Many2one(
        'helpdesk.ticket',
        string='Origen',
        ondelete='set null',
        index=True,
        copy=False,
        help='Ticket de visita técnica desde el que se generó esta solicitud (acta con botones marcados).',
    )
    mesa_acta_request_type = fields.Selection(
        [
            ('equipment_change', 'Cambio de Equipo'),
            ('component_change', 'Cambio de Componente'),
            ('maintenance_repair', 'Mantenimiento/Reparación'),
            ('retiro_usuario', 'Retiro de usuario/equipo'),
            ('retiro_licencias', 'Cancelación de licencias'),
            ('inactivar_usuario', 'Inactivación de usuario'),
        ],
        string='Tipo solicitud acta',
        copy=False,
        index=True,
        help='Solicitud acta o retiro desde panel/menú (oculta Realizado y Tickets hijos).',
    )
    mesa_hide_visit_acta_notebook_pages = fields.Boolean(
        string='Ocultar pestañas acta en ticket solicitud',
        compute='_compute_mesa_hide_visit_acta_notebook_pages',
        help='True en solicitudes acta o retiro: sin Realizado ni Tickets hijos.',
    )

    mesa_ticket_edit_blocked = fields.Boolean(
        string='Edición bloqueada (etapa final)',
        compute='_compute_mesa_ticket_edit_blocked',
        help='True en Resuelto/Cerrado/Cancelado: el formulario y guardado no permiten cambiar datos del ticket.',
    )

    mesa_category_readonly = fields.Boolean(
        string='Categoría solo lectura',
        compute='_compute_mesa_category_readonly',
        help='Categoría bloqueada por visita o por ticket en etapa final.',
    )

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

    @api.depends('mesa_acta_request_type')
    def _compute_mesa_hide_visit_acta_notebook_pages(self):
        for ticket in self:
            ticket.mesa_hide_visit_acta_notebook_pages = bool(ticket.mesa_acta_request_type)

    @api.depends(
        'visit_helpdesk_category_locked',
        'mesa_parent_visit_ticket_id',
        'mesa_acta_request_type',
        'category_id',
        'category_id.name',
        'maintenance_order_id',
        'maintenance_order_id.activity_type',
    )
    def _compute_mesa_show_visit_child_relations(self):
        for ticket in self:
            ticket.mesa_show_visit_child_relations = ticket._mesa_is_visit_ticket_for_children_ui()

    def _mesa_is_visit_ticket_for_children_ui(self):
        """True si el ticket es una visita (padre), no un seguimiento hijo: para mostrar listado de hijos."""
        self.ensure_one()
        if self.mesa_acta_request_type:
            return False
        if self.mesa_parent_visit_ticket_id:
            return False
        if self.visit_helpdesk_category_locked:
            return True
        visit_cat = self._mesa_default_visit_ticket_category()
        if visit_cat and self.category_id == visit_cat:
            return True
        path = _mesa_helpdesk_category_path_upper(self.category_id)
        if 'VISITA' in path and ('TÉCNICA' in path or 'TECNICA' in path):
            return True
        order = self.maintenance_order_id
        if order and getattr(order, 'activity_type', None) == 'visit':
            return True
        return False

    @api.model
    def _mesa_merge_kanban_done_if_available(self, vals):
        """Si el modelo tiene ``kanban_state``, fuerza «Listo» (done) al cerrar/completar."""
        vals = dict(vals or {})
        if 'kanban_state' in self._fields:
            vals['kanban_state'] = 'done'
        return vals

    @api.depends('stage_id', 'stage_id.name')
    def _compute_mesa_ticket_edit_blocked(self):
        for ticket in self:
            ticket.mesa_ticket_edit_blocked = ticket._is_stage_resuelto_or_closed()

    @api.depends('visit_helpdesk_category_locked', 'stage_id', 'stage_id.name')
    def _compute_mesa_category_readonly(self):
        for ticket in self:
            ticket.mesa_category_readonly = bool(
                ticket.visit_helpdesk_category_locked or ticket._is_stage_resuelto_or_closed()
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
                ticket.custom_timer_display = _('Parado')

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

    def _mesa_check_ticket_open_for_user_edits(self):
        """Bloquea acciones de edición si el ticket ya está en etapa final."""
        for ticket in self:
            if ticket._is_stage_resuelto_or_closed():
                raise UserError(
                    _('El ticket está en etapa final (Resuelto, Cerrado o Cancelado) y no admite cambios.')
                )

    def _mesa_stage_name_is_resolved_only(self):
        """Resuelto / Resolved (no Cerrado ni Cancelado): disparador de tickets hijos desde acta."""
        self.ensure_one()
        name = self._get_stage_name_lower()
        return name in ('resuelto', 'resolved') if name else False

    def _mesa_eligible_for_acta_followup_on_resolve(self):
        """Solo tickets de visita con orden y equipos y/o contactos del cliente en acta (wizard o HTML deducido)."""
        self.ensure_one()
        if self.mesa_parent_visit_ticket_id:
            return False
        if self.mesa_acta_followup_tickets_created:
            return False
        if not self.maintenance_order_id or (
            not self.mesa_acta_selected_lot_ids and not self.mesa_acta_selected_contact_ids
        ):
            return False
        if self.visit_helpdesk_category_locked:
            return True
        visit_cat = self._mesa_default_visit_ticket_category()
        if visit_cat and self.category_id == visit_cat:
            return True
        path = _mesa_helpdesk_category_path_upper(self.category_id)
        if 'VISITA' in path and ('TÉCNICA' in path or 'TECNICA' in path):
            return True
        order = self.maintenance_order_id
        if order and getattr(order, 'activity_type', None) == 'visit':
            return True
        return False

    def _mesa_serials_from_acta_html_tables(self, html_content):
        """Serie (primera celda) solo en tablas de equipo del acta (no tablas de contactos)."""
        if not html_content:
            return []
        serials = []
        for m in re.finditer(r'<table\b[^>]*>[\s\S]*?</table\s*>', html_content, re.I):
            table_html = m.group(0)
            if not _mesa_acta_table_html_is_equipment_block(table_html):
                continue
            m_tb = re.search(r'<tbody\b[^>]*>([\s\S]*?)</tbody\s*>', table_html, re.I)
            if not m_tb:
                continue
            chunk = m_tb.group(1)
            mrow = re.search(r'<tr[^>]*>\s*<td[^>]*>([\s\S]*?)</td>', chunk, re.I)
            if mrow:
                inner = mrow.group(1).strip()
                inner = re.sub(r'<[^>]+>', '', inner)
                inner = html_stdlib.unescape(inner).strip()
                if inner:
                    serials.append(inner)
        return serials

    def _mesa_strip_acta_serial_cell(self, raw):
        """Quita etiquetas HTML y prefijos tipo «Serie» del texto de la celda de serie del acta."""
        if not raw:
            return ''
        s = html_stdlib.unescape(str(raw)).strip()
        s = re.sub(r'<[^>]+>', '', s)
        s = re.sub(
            r'^(serie|serial|s\/?\s*n|n\/?\s*s|sn)\s*[:#.\-\s]*',
            '',
            s,
            flags=re.I,
        ).strip()
        return s

    def _mesa_strip_acta_plate_cell(self, raw):
        """Normaliza celda de placa (quita prefijo «Placa», etc.)."""
        if not raw:
            return ''
        s = html_stdlib.unescape(str(raw)).strip()
        s = re.sub(r'<[^>]+>', '', s)
        s = re.sub(
            r'^(placa|plate|inv\.?|inventario)\s*[:#.\-\s]*',
            '',
            s,
            flags=re.I,
        ).strip()
        if re.match(r'^(sin placa|n/?a)$', s, re.I):
            return ''
        return s

    def _mesa_find_lot_for_acta_row(self, serie_cell, plate_cell, candidates, Lot, partner):
        """Localiza un lote candidato o por búsqueda amplia (serie/placa del acta)."""
        token = self._mesa_strip_acta_serial_cell(serie_cell)
        plate = self._mesa_strip_acta_plate_cell(plate_cell)
        if token:
            exact = candidates.filtered(lambda l: (l.name or '').strip().lower() == token.lower())
  