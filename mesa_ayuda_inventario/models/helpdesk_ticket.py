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
            if len(exact) == 1:
                return exact
            if len(exact) > 1 and plate:
                narrowed = exact.filtered(
                    lambda l: (l.inventory_plate or '').strip().lower() == plate.lower()
                )
                if len(narrowed) == 1:
                    return narrowed
        if plate:
            by_plate = candidates.filtered(
                lambda l: (l.inventory_plate or '').strip().lower() == plate.lower()
            )
            if len(by_plate) == 1:
                return by_plate
            dom_pl = [('inventory_plate', '=', plate)]
            if partner:
                dom_pl.append(('customer_id', 'child_of', partner.id))
            gpl = Lot.search(dom_pl, limit=2)
            if len(gpl) == 1:
                return gpl
        if token:
            subs = candidates.filtered(lambda l: token.lower() in (l.name or '').strip().lower())
            if len(subs) == 1:
                return subs
        if token:
            dom = [('name', '=', token)]
            if partner:
                dom.append(('customer_id', 'child_of', partner.id))
            found = Lot.search(dom, limit=1)
            if found:
                return found
            if partner:
                alt = Lot.search([('name', 'ilike', token)], limit=16)
                ok = alt.filtered(
                    lambda l: not l.customer_id or l.customer_id.commercial_partner_id == partner
                )
                if len(ok) == 1:
                    return ok
        return Lot.browse()

    def _mesa_backfill_acta_lots_if_empty(self):
        """Rellena o amplía ``mesa_acta_selected_lot_ids`` desde la orden y el HTML del acta (series/placas)."""
        self.ensure_one()
        Lot = self.env['stock.lot'].sudo()
        order = self.maintenance_order_id
        partner = self.partner_id.commercial_partner_id if self.partner_id else False
        candidates = self._mesa_candidate_main_lots_for_acta()
        seen = set()
        merged_ids = []

        def add_lid(lid):
            if lid and lid not in seen:
                seen.add(lid)
                merged_ids.append(lid)

        for lid in self.mesa_acta_selected_lot_ids.ids:
            add_lid(lid)
        if order:
            for lot in order.maintenance_ids.mapped('lot_id').filtered(lambda l: l):
                add_lid(lot.id)

        def _dedupe_key(blob):
            return hash(str(blob or ''))

        processed_keys = set()

        def _consume_triples(triples):
            for serie, placa, _prod in triples or []:
                lot = self._mesa_find_lot_for_acta_row(serie, placa, candidates, Lot, partner)
                if lot:
                    add_lid(lot.id)

        acta_html = (order.visit_documentation_html or '') if order else ''
        if acta_html:
            k = _dedupe_key(acta_html)
            if k not in processed_keys:
                processed_keys.add(k)
                triples = order._mesa_acta_parse_equipment_summary_rows(acta_html)
                if triples:
                    _consume_triples(triples)
                else:
                    for sn in self._mesa_serials_from_acta_html_tables(acta_html):
                        lot = self._mesa_find_lot_for_acta_row(sn, '', candidates, Lot, partner)
                        if lot:
                            add_lid(lot.id)

        summary_sources = []
        if order and getattr(order, 'mesa_visit_pdf_summary_html', None):
            summary_sources.append(order.mesa_visit_pdf_summary_html)
        if self.description:
            summary_sources.append(self.description)
        for blob in summary_sources:
            if not blob or not order:
                continue
            k = _dedupe_key(blob)
            if k in processed_keys:
                continue
            processed_keys.add(k)
            _consume_triples(order._mesa_parse_close_summary_li_rows(blob))
        before = set(self.mesa_acta_selected_lot_ids.ids)
        after = set(merged_ids)
        if merged_ids and after != before:
            self.sudo().write({'mesa_acta_selected_lot_ids': [(6, 0, merged_ids)]})

    def _mesa_backfill_acta_contacts_if_empty(self):
        """Amplía ``mesa_acta_selected_contact_ids`` desde ``data-mesa-acta-participant-partner-id`` (y legacy user-id)."""
        self.ensure_one()
        order = self.maintenance_order_id
        html = (order.visit_documentation_html or '') if order else ''
        if not html:
            return
        allowed_ids = set(self._mesa_candidate_contacts_for_acta().ids)
        seen = [x for x in dict.fromkeys(self.mesa_acta_selected_contact_ids.ids) if x in allowed_ids]
        Users = self.env['res.users'].sudo()
        for m in re.finditer(r'data-mesa-acta-participant-partner-id=["\'](\d+)["\']', html, re.I):
            pid = int(m.group(1))
            if pid in seen or pid not in allowed_ids:
                continue
            p = self.env['res.partner'].sudo().browse(pid)
            if p.exists() and p.active:
                seen.append(pid)
        for m in re.finditer(r'data-mesa-acta-participant-user-id=["\'](\d+)["\']', html, re.I):
            uid = int(m.group(1))
            u = Users.browse(uid)
            if not u.exists() or not u.active or not u.partner_id:
                continue
            pid = u.partner_id.id
            if pid in seen or pid not in allowed_ids:
                continue
            seen.append(pid)
        before = set(self.mesa_acta_selected_contact_ids.ids)
        after = set(seen)
        if seen and after != before:
            self.sudo().write({'mesa_acta_selected_contact_ids': [(6, 0, seen)]})

    def _mesa_followup_pick_open_stage(self, team=None):
        """Etapa inicial del embudo (``team`` opcional si el ticket aún no existe)."""
        if team is None and len(self) == 1:
            team = self.team_id
        Ticket = self.env['helpdesk.ticket']
        finfo = Ticket._fields.get('stage_id')
        if not finfo or not getattr(finfo, 'comodel_name', None):
            _logger.warning('mesa_acta_followup: sin metadatos de stage_id en helpdesk.ticket')
            return self.env['helpdesk.stage'].browse()
        comodel = finfo.comodel_name
        if comodel not in self.env:
            _logger.warning('mesa_acta_followup: modelo de etapa %s no cargado', comodel)
            return self.env[comodel].browse()
        Stage = self.env[comodel].sudo()
        team_clause = []
        if team and 'team_id' in Stage._fields:
            team_clause = ['|', ('team_id', '=', False), ('team_id', '=', team.id)]

        def _search(dom):
            full = team_clause + dom if team_clause else dom
            return Stage.search(full, limit=1, order='sequence, id')

        for label in ('nuevo', 'new', 'borrador', 'draft'):
            st = _search([('name', '=ilike', label)])
            if st:
                return st
        if 'fold' in Stage._fields:
            st = _search([('fold', '=', False)])
            if st:
                return st
        st = Stage.search(team_clause or [], limit=1, order='sequence, id')
        return st

    def _mesa_followup_pick_resolved_stage(self):
        """Etapa Resuelto/Cerrado (misma idea que al completar la orden: closed o nombre típico de cierre)."""
        self.ensure_one()
        finfo = self._fields.get('stage_id')
        if not finfo or not getattr(finfo, 'comodel_name', None):
            _logger.warning('mesa_acta_followup_resolved: ticket %s sin metadatos de stage_id', self.id)
            return self.env['helpdesk.ticket'].browse()
        comodel = finfo.comodel_name
        if comodel not in self.env:
            return self.env['helpdesk.ticket'].browse()
        Stage = self.env[comodel].sudo()
        team_clause = []
        if 'team_id' in Stage._fields and self.team_id:
            team_clause = ['|', ('team_id', '=', False), ('team_id', '=', self.team_id.id)]

        def _search(dom):
            full = team_clause + dom if team_clause else dom
            return Stage.search(full, limit=1, order='sequence, id')

        try:
            if 'closed' in Stage._fields:
                full = team_clause + [('closed', '=', True)] if team_clause else [('closed', '=', True)]
                st = Stage.search(full, limit=1, order='sequence desc, id desc')
                if st:
                    return st
        except Exception:
            pass
        for label in (
            'resuelto',
            'cerrado',
            'resolved',
            'closed',
            'solved',
            'finalizado',
            'completado',
            'done',
        ):
            st = _search([('name', '=ilike', label)])
            if st:
                return st
        return Stage.search(team_clause or [], limit=1, order='sequence desc, id desc')

    @api.model
    def _mesa_acta_followup_flag_label_map(self):
        return {
            'equipment_change': _('Cambio de Equipo'),
            'component_change': _('Cambio de Componente'),
            'maintenance_repair': _('Mantenimiento/Reparación'),
        }

    @api.model
    def _mesa_maintenance_category_for_acta_request_type(self, request_type):
        """Categoría mantenimiento por tipo de solicitud acta."""
        mapping = {
            'equipment_change': 'change',
            'maintenance_repair': 'repair',
            'component_change': 'maintenance',
        }
        return mapping.get(request_type)

    @api.model
    def _mesa_maintenance_category_for_acta_flags(self, flags):
        """Compatibilidad: primer tipo activo en orden equipo → componente → reparación."""
        from odoo.addons.mesa_ayuda_inventario.wizard.acta_html_blocks import MESA_ACTA_FOLLOWUP_FLAG_KEYS

        for key in MESA_ACTA_FOLLOWUP_FLAG_KEYS:
            if key in flags:
                return self._mesa_maintenance_category_for_acta_request_type(key)
        return False

    def _mesa_build_acta_standalone_ticket_title(self, visit_ticket, lot, request_type, reference_label=None):
        """Ej.: Solicitud Cambio de Equipo / Componente / Mantenimiento: SERIE - referencia."""
        labels = self._mesa_acta_followup_flag_label_map()
        tipo = labels.get(request_type, _('Acta'))
        serial = (lot.name or '').strip() or (lot.display_name or '') or _('Equipo')
        if visit_ticket:
            ref = (visit_ticket.name or '').strip()
        else:
            ref = (reference_label or '').strip() or _('Operaciones de campo')
        title = _('Solicitud %(tipo)s: %(serie)s - %(ref)s') % {
            'tipo': tipo,
            'serie': serial,
            'ref': ref,
        }
        if len(title) > 200:
            title = title[:197] + '...'
        return title

    @api.model
    def _mesa_acta_equipment_block_html_for_lot(self, lot, active_request_type='equipment_change'):
        """Bloque acta (tabla + Realizado con botón activo) para un lote, sin orden de visita."""
        from odoo.addons.mesa_ayuda_inventario.wizard.acta_html_blocks import (
            MESA_ACTA_FOLLOWUP_FLAG_KEYS,
            mesa_acta_equipment_block_html,
        )

        active = {active_request_type} if active_request_type in MESA_ACTA_FOLLOWUP_FLAG_KEYS else set()
        serial = escape(lot.name or '')
        plate = escape((lot.inventory_plate or '').strip() or _('Sin placa'))
        prod = escape(lot.product_id.display_name if lot.product_id else _('N/A'))
        return mesa_acta_equipment_block_html(
            lot.id,
            _('Serie'),
            _('Placa'),
            _('Producto'),
            serial,
            plate,
            prod,
            _('Realizado'),
            realizado_inner='<p><br></p>',
            lbl_equipment_change=_('Cambio de Equipo'),
            lbl_component_change=_('Cambio de Componente'),
            lbl_maintenance_repair=_('Mantenimiento/Reparación'),
            active_flag_keys=active,
        )

    @api.model
    def _mesa_create_panel_request_ticket(self, lot, partner, request_type='equipment_change'):
        """Ticket independiente desde panel operaciones (misma lógica que solicitud acta en visita)."""
        from odoo.addons.mesa_ayuda_inventario.wizard.acta_html_blocks import MESA_ACTA_FOLLOWUP_FLAG_KEYS

        if request_type not in MESA_ACTA_FOLLOWUP_FLAG_KEYS:
            raise UserError(_('Tipo de solicitud no válido.'))
        if not lot or not partner:
            raise UserError(_('Seleccione cliente y equipo.'))

        H = self.env['helpdesk.ticket'].sudo()
        Team = self.env['helpdesk.team'].sudo()
        default_team = Team.search([], limit=1, order='sequence, id')
        if not default_team:
            raise UserError(_('No hay equipo de mesa de ayuda configurado.'))
        stage = H._mesa_followup_pick_open_stage(team=default_team)
        if not stage:
            raise UserError(
                _('No se encontró etapa «Nuevo» en el embudo de helpdesk. Revise las etapas del equipo.')
            )
        default_category = H._mesa_default_visit_ticket_category() or H._mesa_first_helpdesk_category()

        assign_uid = self.env.user.id
        if default_team.member_ids:
            assign_uid = default_team.member_ids[0].id
        tu = getattr(default_team, 'user_id', False)
        if tu:
            assign_uid = tu.id

        acta_block = H._mesa_acta_equipment_block_html_for_lot(lot, active_request_type=request_type)
        from odoo.addons.mesa_ayuda_inventario.wizard.acta_lot_detail_html import mesa_acta_lot_equipment_detail_html

        desc = H._mesa_markup_html_fragments(acta_block, mesa_acta_lot_equipment_detail_html(self.env, lot))

        ref_label = partner.display_name or partner.name or ''
        title = H._mesa_build_acta_standalone_ticket_title(
            H.browse(), lot, request_type, reference_label=ref_label,
        )

        vals = {
            'name': title,
            'partner_id': partner.id,
            'team_id': default_team.id,
            'user_id': assign_uid,
            'category_id': default_category.id if default_category else False,
            'priority': '0',
            'description': desc,
            'lot_id': lot.id,
            'stage_id': stage.id,
            'visit_helpdesk_category_locked': False,
            'mesa_acta_request_type': request_type,
            'maintenance_category': H._mesa_maintenance_category_for_acta_request_type(request_type),
        }
        company = self.env.company.id
        if company:
            vals['company_id'] = company
        vals = H._mesa_merge_kanban_done_if_available(vals)
        return H.create(vals)

    @api.model
    def _mesa_create_retiro_followup_ticket(
        self, partner, title, description_html, lot=None,
        maintenance_category='change', request_type='retiro_usuario',
        lot_detail_html=None,
    ):
        """Ticket de seguimiento al registrar retiro (usuario y/o licencias) desde el panel o menú.

        lot_detail_html: None = ficha completa del equipo; Markup/str = HTML personalizado;
        False = no adjuntar ficha.
        """
        if request_type not in ('retiro_usuario', 'retiro_licencias', 'inactivar_usuario'):
            raise UserError(_('Tipo de retiro no válido.'))
        if not partner:
            raise UserError(_('Seleccione el cliente.'))
        H = self.env['helpdesk.ticket'].sudo()
        Team = self.env['helpdesk.team'].sudo()
        default_team = Team.search([], limit=1, order='sequence, id')
        if not default_team:
            raise UserError(_('No hay equipo de mesa de ayuda configurado.'))
        stage = H._mesa_followup_pick_open_stage(team=default_team)
        if not stage:
            raise UserError(
                _('No se encontró etapa «Nuevo» en el embudo de helpdesk. Revise las etapas del equipo.')
            )
        default_category = H._mesa_default_visit_ticket_category() or H._mesa_first_helpdesk_category()
        assign_uid = self.env.user.id
        if default_team.member_ids:
            assign_uid = default_team.member_ids[0].id
        tu = getattr(default_team, 'user_id', False)
        if tu:
            assign_uid = tu.id

        desc_parts = [description_html or '<p><br></p>']
        if lot_detail_html is not False:
            if lot_detail_html:
                desc_parts.append(lot_detail_html)
            elif lot:
                from odoo.addons.mesa_ayuda_inventario.wizard.acta_lot_detail_html import (
                    mesa_acta_lot_devolucion_ticket_detail_html,
                )
                desc_parts.append(mesa_acta_lot_devolucion_ticket_detail_html(self.env, lot))

        full_description = H._mesa_markup_html_fragments(*desc_parts)

        vals = {
            'name': (title or _('Retiro / consulta'))[:200],
            'partner_id': partner.id,
            'team_id': default_team.id,
            'user_id': assign_uid,
            'category_id': default_category.id if default_category else False,
            'priority': '0',
            'description': full_description,
            'lot_id': lot.id if lot else False,
            'stage_id': stage.id,
            'visit_helpdesk_category_locked': False,
            'maintenance_category': maintenance_category,
            'mesa_acta_request_type': request_type,
        }
        company = self.env.company.id
        if company:
            vals['company_id'] = company
        vals = H._mesa_merge_kanban_done_if_available(vals)
        ticket = H.create(vals)
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        model_rec = self.env['ir.model'].sudo().search([('model', '=', 'helpdesk.ticket')], limit=1)
        if activity_type and model_rec:
            self.env['mail.activity'].create({
                'res_model_id': model_rec.id,
                'res_id': ticket.id,
                'activity_type_id': activity_type.id,
                'summary': _('Seguimiento retiro — %s') % (partner.display_name or '')[:120],
                'note': _('Revisar ticket y trazabilidad de licencias/equipo.'),
                'user_id': self.env.user.id,
                'date_deadline': fields.Date.context_today(self),
            })
        ticket.message_post(
            body=_('Tarea creada automáticamente al registrar el retiro.'),
            subject=_('Tarea de seguimiento'),
        )
        if len(desc_parts) > 1:
            ticket.message_post(
                body=Markup(full_description),
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )
        return ticket

    @api.model
    def _mesa_markup_html_fragments(self, *fragments):
        """Une HTML para el campo description del ticket (cadena HTML, no Markup escapado)."""
        parts = []
        for part in fragments:
            if part is None:
                continue
            text = str(part).strip()
            if text:
                parts.append(text)
        if not parts:
            return '<p><br></p>'
        return '\n'.join(parts)

    def _mesa_description_with_acta_lot_detail(self, acta_html, lot):
        """Descripción: bloque acta + ficha ampliada del equipo."""
        self.ensure_one()
        if not lot:
            return self._mesa_markup_html_fragments(acta_html or '<p><br></p>')
        from odoo.addons.mesa_ayuda_inventario.wizard.acta_lot_detail_html import mesa_acta_lot_equipment_detail_html

        detail = mesa_acta_lot_equipment_detail_html(self.env, lot)
        return self._mesa_markup_html_fragments(acta_html or '<p><br></p>', detail)

    def _mesa_prepare_acta_standalone_ticket_vals(
        self, lot, request_type, order, stage, default_team, default_category,
        assign_uid_default, company,
    ):
        """Valores comunes para solicitud acta independiente (cambio equipo, componente o reparación)."""
        self.ensure_one()
        from odoo.addons.mesa_ayuda_inventario.wizard.acta_html_blocks import MESA_ACTA_FOLLOWUP_FLAG_KEYS

        if request_type not in MESA_ACTA_FOLLOWUP_FLAG_KEYS:
            return {}
        desc = ''
        if order:
            desc = order._mesa_acta_html_equipment_block_for_lot(lot)
        if not desc:
            desc = '<p><br></p>'
        desc = self._mesa_description_with_acta_lot_detail(desc, lot)
        title = self._mesa_build_acta_standalone_ticket_title(self, lot, request_type)
        vals = {
            'name': title,
            'partner_id': self.partner_id.id,
            'team_id': default_team.id,
            'user_id': assign_uid_default,
            'category_id': default_category.id if default_category else False,
            'priority': self.priority,
            'description': desc,
            'lot_id': lot.id,
            'maintenance_order_id': self.maintenance_order_id.id,
            'stage_id': stage.id,
            'visit_helpdesk_category_locked': False,
            'mesa_acta_followup_tickets_created': False,
            'mesa_acta_followup_contact_id': False,
            'mesa_acta_request_type': request_type,
            'mesa_acta_origin_visit_ticket_id': self.id,
        }
        maint_cat = self._mesa_maintenance_category_for_acta_request_type(request_type)
        if maint_cat:
            vals['maintenance_category'] = maint_cat
        if company:
            vals['company_id'] = company
        return vals

    def _mesa_try_create_acta_followup_tickets(self):
        """Tickets hijos por equipo y/o por contactos del cliente en el acta; descripción = bloque HTML; etapa Resuelto."""
        self.ensure_one()
        self._mesa_backfill_acta_lots_if_empty()
        self._mesa_backfill_acta_contacts_if_empty()
        self.flush_recordset(['mesa_acta_selected_lot_ids', 'mesa_acta_selected_contact_ids'])
        if not self._mesa_eligible_for_acta_followup_on_resolve():
            _logger.info(
                'mesa_acta_followup: ticket %s no elegible (orden/lotes o contactos/categoría o seguimiento ya creado).',
                self.id,
            )
            return
        from odoo.addons.mesa_ayuda_inventario.wizard.acta_html_blocks import MESA_ACTA_FOLLOWUP_FLAG_KEYS

        lots = self.mesa_acta_selected_lot_ids
        act_contacts = self.mesa_acta_selected_contact_ids
        order_pre = self.maintenance_order_id
        total_expected = len(act_contacts)
        for lot in lots:
            flags = order_pre._mesa_acta_equipment_followup_flags_for_lot(lot) if order_pre else set()
            active = [k for k in MESA_ACTA_FOLLOWUP_FLAG_KEYS if k in flags]
            total_expected += len(active) if active else 1
        if not total_expected:
            self.message_post(
                body=_(
                    'No se crearon tickets de seguimiento: no hay equipos ni contactos del cliente vinculados al acta. '
                    'Use «Insertar equipos» o «Contactos del cliente», o deje constancia en el HTML del acta.'
                ),
                subject=_('Seguimiento acta'),
            )
            _logger.warning('mesa_acta_followup: ticket %s sin lotes ni contactos tras backfill', self.id)
            return
        child_stage = self._mesa_followup_pick_resolved_stage()
        standalone_stage = self._mesa_followup_pick_open_stage()
        if not child_stage:
            child_stage = standalone_stage
            if child_stage:
                self.message_post(
                    body=_(
                        'Los tickets de seguimiento (sin botones del acta) se crearon en etapa abierta porque no se encontró '
                        'ninguna etapa «Resuelto/Cerrado» en el embudo. Configure una etapa con «Cerrado» o nombre equivalente.'
                    ),
                    subject=_('Seguimiento acta'),
                )
        if not child_stage:
            msg = _(
                'No se pudieron crear tickets de seguimiento: no se encontró etapa resuelta ni inicial en el modelo '
                '%(model)s para el equipo del ticket. Revise las etapas del helpdesk.'
            ) % {'model': self._fields['stage_id'].comodel_name}
            self.message_post(body=msg, subject=_('Seguimiento acta'))
            _logger.warning('mesa_acta_followup: sin etapa; ticket=%s model=%s', self.id, self._fields['stage_id'].comodel_name)
            return
        Ticket = self.env['helpdesk.ticket'].sudo()
        created = Ticket.browse()
        company = getattr(self, 'company_id', None) and self.company_id.id or self.env.company.id
        if not self.partner_id:
            _logger.warning('mesa_acta_followup: ticket %s sin cliente; no se crean hijos', self.id)
            return
        Team = self.env['helpdesk.team'].sudo()
        Category = self.env['helpdesk.ticket.category'].sudo()
        default_team = self.team_id or Team.search([], limit=1, order='sequence, id')
        default_category = (
            self.category_id
            or self._mesa_default_visit_ticket_category()
            or self._mesa_first_helpdesk_category()
        )
        if not default_team:
            _logger.warning('mesa_acta_followup: no hay equipo helpdesk; ticket %s', self.id)
            self.message_post(
                body=_('No se pudieron crear tickets de seguimiento: no hay equipo de mesa de ayuda configurado.'),
                subject=_('Seguimiento acta'),
            )
            return
        assign_uid_default = self.user_id.id
        if not assign_uid_default and default_team:
            tu = getattr(default_team, 'user_id', False)
            assign_uid_default = tu.id if tu else False
        if not assign_uid_default and default_team and getattr(default_team, 'member_ids', False):
            assign_uid_default = default_team.member_ids[0].id
        if not assign_uid_default:
            assign_uid_default = self.env.user.id
        order = self.maintenance_order_id

        def _create_one_child(vals):
            nonlocal created
            if company:
                vals['company_id'] = company
            vals = Ticket._mesa_merge_kanban_done_if_available(vals)
            try:
                created |= Ticket.create(vals)
            except Exception as err:
                return err
            return None

        for lot in lots:
            flags = order._mesa_acta_equipment_followup_flags_for_lot(lot) if order else set()
            active_flags = [k for k in MESA_ACTA_FOLLOWUP_FLAG_KEYS if k in flags]
            flag_labels = self._mesa_acta_followup_flag_label_map()

            if active_flags:
                if not standalone_stage:
                    self.message_post(
                        body=_(
                            'No se crearon solicitudes acta para el equipo %(equipo)s: opciones marcadas '
                            '(%(tipos)s) pero no hay etapa «Nuevo» en el embudo.'
                        )
                        % {
                            'equipo': escape(lot.display_name or lot.name or ''),
                            'tipos': ', '.join(flag_labels.get(k, k) for k in active_flags),
                        },
                        subject=_('Seguimiento acta'),
                    )
                    continue
                for request_type in active_flags:
                    vals = self._mesa_prepare_acta_standalone_ticket_vals(
                        lot,
                        request_type,
                        order,
                        standalone_stage,
                        default_team,
                        default_category,
                        assign_uid_default,
                        company,
                    )
                    err = _create_one_child(vals)
                    if err:
                        _logger.exception(
                            'mesa_acta_followup: no se pudo crear solicitud acta (%s) para lote %s: %s',
                            request_type,
                            lot.id,
                            err,
                        )
                        self.message_post(
                            body=_(
                                'No se pudo crear la solicitud «%(tipo)s» para el equipo %(equipo)s: %(err)s'
                            )
                            % {
                                'tipo': flag_labels.get(request_type, request_type),
                                'equipo': escape(lot.display_name or lot.name or ''),
                                'err': escape(str(err)),
                            },
                            subject=_('Seguimiento acta'),
                        )
                continue

            if not child_stage:
                continue
            equipo_label = (lot.name or '').strip() or (lot.display_name or '') or _('Equipo')
            title = _('Seguimiento: %(visit)s — %(equipo)s') % {
                'visit': self.name,
                'equipo': equipo_label,
            }
            if len(title) > 200:
                title = title[:197] + '...'
            desc = ''
            if order:
                desc = order._mesa_acta_html_equipment_block_for_lot(lot)
            vals = {
                'name': title,
                'partner_id': self.partner_id.id,
                'team_id': default_team.id,
                'user_id': assign_uid_default,
                'category_id': default_category.id if default_category else False,
                'priority': self.priority,
                'description': self._mesa_markup_html_fragments(desc or '<p><br></p>'),
                'lot_id': lot.id,
                'maintenance_order_id': self.maintenance_order_id.id,
                'stage_id': child_stage.id,
                'visit_helpdesk_category_locked': False,
                'mesa_acta_followup_tickets_created': False,
                'mesa_acta_followup_contact_id': False,
                'mesa_parent_visit_ticket_id': self.id,
            }
            err = _create_one_child(vals)
            if err:
                _logger.exception(
                    'mesa_acta_followup: no se pudo crear ticket hijo para lote %s desde ticket %s: %s',
                    lot.id,
                    self.id,
                    err,
                )
                self.message_post(
                    body=_(
                        'No se pudo crear el ticket de seguimiento (hijo) para el equipo %(equipo)s: %(err)s'
                    )
                    % {
                        'equipo': escape(lot.display_name or lot.name or ''),
                        'err': escape(str(err)),
                    },
                    subject=_('Seguimiento acta'),
                )

        for contact in act_contacts:
            persona = (contact.name or '').strip() or (contact.display_name or '').strip() or _('Contacto')
            title = _('Seguimiento: %(visit)s — %(persona)s') % {
                'visit': self.name,
                'persona': persona,
            }
            if len(title) > 200:
                title = title[:197] + '...'
            desc = ''
            if order:
                desc = order._mesa_acta_html_contact_block_for_partner(contact)
            vals = {
                'name': title,
                'partner_id': self.partner_id.id,
                'team_id': default_team.id,
                'user_id': assign_uid_default,
                'category_id': default_category.id if default_category else False,
                'priority': self.priority,
                'description': self._mesa_markup_html_fragments(desc or '<p><br></p>'),
                'mesa_parent_visit_ticket_id': self.id,
                'maintenance_order_id': self.maintenance_order_id.id,
                'stage_id': child_stage.id,
                'visit_helpdesk_category_locked': False,
                'mesa_acta_followup_tickets_created': False,
                'mesa_acta_followup_contact_id': contact.id,
            }
            err = _create_one_child(vals)
            if err:
                _logger.exception(
                    'mesa_acta_followup: no se pudo crear ticket hijo para contacto %s desde ticket %s: %s',
                    contact.id,
                    self.id,
                    err,
                )
                self.message_post(
                    body=_(
                        'No se pudo crear el ticket de seguimiento para el contacto %(persona)s: %(err)s'
                    )
                    % {'persona': escape(contact.display_name or contact.name or ''), 'err': escape(str(err))},
                    subject=_('Seguimiento acta'),
                )

        if created:
            intro = escape(_('Tickets generados desde el acta (seguimiento, solicitudes con botones y contactos):'))
            items = Markup('').join(
                Markup(
                    '<li style="margin-bottom:4px;"><a href="#" data-oe-model="helpdesk.ticket" data-oe-id="%d">%s</a></li>'
                )
                % (c.id, escape(c.name or ''))
                for c in created
            )
            body = Markup(
                '<p style="margin:0 0 6px 0;">%s</p><ul style="margin:0;padding-left:18px;">%s</ul>'
            ) % (intro, items)
            self.message_post(
                body=body,
                subject=_('Visitas: seguimiento acta'),
            )
        if len(created) == total_expected:
            self.sudo().write({'mesa_acta_followup_tickets_created': True})
        elif created:
            self.message_post(
                body=_(
                    'Solo se crearon %(ok)s de %(total)s tickets de seguimiento (equipos + contactos del cliente). '
                    'Revise los mensajes anteriores por errores; el seguimiento no se marcó como completado para poder reintentar.'
                )
                % {'ok': len(created), 'total': total_expected},
                subject=_('Seguimiento acta (parcial)'),
            )

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

    @api.model
    def _mesa_first_helpdesk_category(self):
        """Primera categoría disponible (el modelo no tiene campo ``sequence``)."""
        return self.env['helpdesk.ticket.category'].sudo().search([], limit=1, order='id')

    @api.model
    def _mesa_default_visit_ticket_category(self):
        """Categoría helpdesk por defecto para visitas técnicas (orden → ticket automático).
        Debe coincidir con la jerarquía tipo «SERVICIO AL CLIENTE / Visita técnica programada»."""
        Category = self.env['helpdesk.ticket.category'].sudo()
        candidates = Category.search([('name', '=ilike', 'Visita técnica programada')])
        for cat in candidates:
            path = _mesa_helpdesk_category_path_upper(cat)
            if 'SERVICIO' in path and 'CLIENTE' in path:
                return cat
        if 'complete_name' in Category._fields:
            cat = Category.search([('complete_name', 'ilike', 'visita técnica programada')], limit=1)
            if cat:
                return cat
        return Category.search([('name', 'ilike', 'visita técnica programada')], limit=1)

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
        vals = dict(vals or {})
        for ticket in self:
            if ticket._is_stage_resuelto_or_closed():
                bad = set(vals) & _MESA_HELPDESK_WRITE_BLOCKED_WHEN_FINAL
                if bad:
                    raise UserError(
                        _(
                            'No se puede modificar un ticket ya cerrado (Resuelto, Cerrado o Cancelado). '
                            'Campos no permitidos: %s'
                        )
                        % ', '.join(sorted(bad))
                    )
        # Si luego se vacía vals (rama cierre de cronómetro), seguir detectando cambio de etapa
        stage_id_was_in_vals = 'stage_id' in vals
        pre_was_resolved = {}
        if 'stage_id' in vals:
            for t in self:
                pre_was_resolved[t.id] = t._mesa_stage_name_is_resolved_only()
        if 'category_id' in vals and self.filtered('visit_helpdesk_category_locked'):
            vals.pop('category_id')
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
                    vals = self._mesa_merge_kanban_done_if_available(vals)
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
        if stage_id_was_in_vals:
            for ticket in self:
                if pre_was_resolved.get(ticket.id):
                    continue
                if ticket._mesa_stage_name_is_resolved_only():
                    ticket._mesa_try_create_acta_followup_tickets()
        return res

    def action_custom_timer_start(self):
        """Inicia o continúa el cronómetro. Solo permitido en etapa 'En progreso'. Para pausar, mueve a 'En espera'."""
        for ticket in self:
            ticket._mesa_check_ticket_open_for_user_edits()
            if ticket.custom_timer_start:
                continue
            if not ticket._is_stage_en_progreso():
                raise UserError(_('Solo se puede iniciar o continuar el cronómetro cuando el ticket está en la etapa "En progreso". Cambia la etapa del ticket primero.'))
            ticket.write({'custom_timer_start': fields.Datetime.now()})
        return True

    def action_custom_timer_stop(self):
        """Detiene el cronómetro y registra el tiempo en la hoja de horas (account.analytic.line)."""
        self.ensure_one()
        self._mesa_check_ticket_open_for_user_edits()
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
                ) % (
                    getattr(self.category_id, 'complete_name', None) or self.category_id.name,
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
                'name': _('Orden'),
                'type': 'ir.actions.act_window',
                'res_model': 'maintenance.order',
                'res_id': self.maintenance_order_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        self._mesa_check_ticket_open_for_user_edits()
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
        self.maintenance_order_id = maintenance_order.id
        self.message_post(body=_('Se creó una orden de mantenimiento: %s') % maintenance_order.name)
        return {
            'name': _('Orden'),
            'type': 'ir.actions.act_window',
            'res_model': 'maintenance.order',
            'res_id': maintenance_order.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_escalate_ticket(self):
        """Abrir wizard para escalar el ticket a otro equipo o responsable (ej. Nivel 2)."""
        self.ensure_one()
        self._mesa_check_ticket_open_for_user_edits()
        return {
            'name': _('Escalar ticket'),
            'type': 'ir.actions.act_window',
            'res_model': 'helpdesk.ticket.escalate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_id': self.id, 'default_ticket_id': self.id},
        }

    def _mesa_candidate_main_lots_for_acta(self):
        """Lotes producto principal vinculados al cliente: orden de visita, customer_id, ubicación cliente."""
        self.ensure_one()
        order = self.maintenance_order_id
        partner = self.partner_id.commercial_partner_id if self.partner_id else self.env['res.partner']
        if not partner:
            return self.env['stock.lot']
        Lot = self.env['stock.lot'].sudo()
        Quant = self.env['stock.quant'].sudo()
        Location = self.env['stock.location'].sudo()
        collected = Lot.browse()
        seen = set()

        def add_lot(lot):
            nonlocal collected, seen
            if not lot or lot.id in seen:
                return
            if not lot.is_main_product:
                return
            collected |= lot
            seen.add(lot.id)

        if order:
            for m in order.maintenance_ids.sorted('id'):
                if m.lot_id and m.lot_id.id not in seen:
                    collected |= m.lot_id
                    seen.add(m.lot_id.id)
        for lot in Lot.search(
            [('customer_id', '=', partner.id), ('is_main_product', '=', True)],
            order='product_id, name',
            limit=200,
        ):
            add_lot(lot)
        cust_loc = partner.property_stock_customer
        if cust_loc:
            for quant in Quant.search(
                [
                    ('location_id', 'child_of', cust_loc.id),
                    ('quantity', '>', 0),
                    ('lot_id', '!=', False),
                ],
                limit=400,
            ):
                add_lot(quant.lot_id)
        elif 'partner_id' in Location._fields:
            for loc in Location.search([('partner_id', '=', partner.id)]):
                for quant in Quant.search(
                    [
                        ('location_id', '=', loc.id),
                        ('quantity', '>', 0),
                        ('lot_id', '!=', False),
                    ],
                    limit=200,
                ):
                    add_lot(quant.lot_id)
        return collected.sorted(lambda l: ((l.product_id.name or ''), (l.name or '')))

    def action_acta_insert_equipment_table(self):
        """Abre un asistente para elegir productos principales del cliente e insertarlos en el acta."""
        self.ensure_one()
        self._mesa_check_ticket_open_for_user_edits()
        if not self.maintenance_order_id:
            raise UserError(_('Este ticket no tiene orden de visita vinculada.'))
        if not self._mesa_candidate_main_lots_for_acta():
            raise UserError(
                _(
                    'No hay productos principales disponibles para este cliente '
                    '(inventario con `is_main_product`, ubicación de cliente o equipos en la orden).'
                )
            )
        return {
            'name': _('Productos principales para el acta'),
            'type': 'ir.actions.act_window',
            'res_model': 'mesa.ayuda.acta.equipment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_ticket_id': self.id,
                'mesa_acta_equipment_wizard': True,
            },
        }

    def _mesa_candidate_contacts_for_acta(self):
        """Contactos del mismo comercial que el cliente del ticket (personas y empresa; no exige cuenta portal)."""
        self.ensure_one()
        Partner = self.env['res.partner'].sudo()
        if not self.partner_id:
            return Partner.browse()
        commercial = self.partner_id.commercial_partner_id
        if not commercial:
            return Partner.browse()
        return Partner.search(
            [('commercial_partner_id', '=', commercial.id), ('active', '=', True)],
            order='is_company desc, parent_id, name',
            limit=500,
        )

    def action_acta_insert_participants_table(self):
        """Abre asistente para elegir contactos del cliente e insertarlos en el acta (como insertar equipos)."""
        self.ensure_one()
        self._mesa_check_ticket_open_for_user_edits()
        if not self.maintenance_order_id:
            raise UserError(_('Este ticket no tiene orden de visita vinculada.'))
        if not self._mesa_candidate_contacts_for_acta():
            raise UserError(
                _(
                    'No hay contactos activos vinculados al comercial «%(cliente)s». '
                    'Revise que el ticket tenga el cliente correcto y que existan contactos bajo esa empresa en Contactos.'
                )
                % {'cliente': self.partner_id.commercial_partner_id.display_name or self.partner_id.display_name}
            )
        return {
            'name': _('Contactos del cliente en el acta'),
            'type': 'ir.actions.act_window',
            'res_model': 'mesa.ayuda.acta.participants.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_ticket_id': self.id,
                'mesa_acta_participants_wizard': True,
            },
        }

    def action_acta_open_other_operations_wizard(self):
        """Marcador para operaciones adicionales que defina el área (wizard ampliable)."""
        self.ensure_one()
        self._mesa_check_ticket_open_for_user_edits()
        return {
            'name': _('Otras operaciones'),
            'type': 'ir.actions.act_window',
            'res_model': 'mesa.ayuda.acta.other.operations.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_helpdesk_ticket_id': self.id},
        }
