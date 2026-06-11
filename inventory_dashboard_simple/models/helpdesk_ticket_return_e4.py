# -*- coding: utf-8 -*-
import base64

from markupsafe import Markup, escape

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .helpdesk_ticket_return_e4_item import RETURN_E4_LINE_ROLE_LABELS
from .stock_picking_return_e4 import RETURN_E4_DESTINATION_LABELS

INVDASH_E4_TICKET_CLOSE_STAGE_NAMES = (
    'resuelto', 'resolved', 'cerrado', 'closed',
)

RETURN_E4_REPORT_STATE_LABELS = {
    'none': 'Sin iniciar',
    'draft': 'Borrador',
    'done': 'Finalizado',
}

RETURN_E4_DEFAULT_VERIFICATION_CATEGORY = 'VERIFICACIÓN / Verificaciones'

# Clase de activo (nombre o código) → sufijo de categoría helpdesk «Verificación - …»
RETURN_E4_ASSET_CLASS_TO_VERIFICATION_SUFFIX = {
    'all in one': 'AIO',
    'all-in-one': 'AIO',
    'aio': 'AIO',
    'laptop': 'Laptop',
    'notebook': 'Laptop',
    'portatil': 'Laptop',
    'portátil': 'Laptop',
    'torre': 'Torre',
    'desktop': 'Torre',
    'pc de escritorio': 'Torre',
    'impresora': 'Impresora',
    'printer': 'Impresora',
}

RETURN_E4_ASSET_CLASS_CODE_TO_VERIFICATION_SUFFIX = {
    'AIO': 'AIO',
    'LAPTOP': 'Laptop',
    'TORRE': 'Torre',
    'IMPRESORA': 'Impresora',
    'PRINTER': 'Impresora',
}


class HelpdeskTicketReturnE4(models.Model):
    _inherit = 'helpdesk.ticket'

    invdash_return_e4_dictamen_line_id = fields.Many2one(
        'stock.picking.return.e4.dictamen.line',
        string='Línea principal E4',
        ondelete='set null',
        copy=False,
        index=True,
        help='Principal o serial suelto que agrupa este ticket.',
    )
    invdash_return_e4_picking_id = fields.Many2one(
        'stock.picking',
        string='Albarán E4',
        related='invdash_return_e4_dictamen_line_id.picking_id',
        store=True,
        readonly=True,
    )
    invdash_return_e4_principal_lot_id = fields.Many2one(
        'stock.lot',
        string='Equipo principal',
        related='invdash_return_e4_dictamen_line_id.lot_id',
        readonly=True,
    )
    invdash_return_e4_item_ids = fields.One2many(
        'helpdesk.ticket.return.e4.item',
        'ticket_id',
        string='Equipos a verificar',
        copy=False,
    )
    invdash_return_e4_item_count = fields.Integer(
        compute='_compute_invdash_return_e4_item_count',
    )
    invdash_return_e4_is_dictamen_ticket = fields.Boolean(
        compute='_compute_invdash_return_e4_is_dictamen_ticket',
        store=True,
    )
    invdash_return_e4_destination = fields.Selection(
        string='Destino (referencia)',
        related='invdash_return_e4_dictamen_line_id.destination',
        readonly=True,
    )
    invdash_return_e4_dictamen_note = fields.Text(
        string='Notas generales',
        copy=False,
    )
    invdash_return_e4_dictamen_state = fields.Char(
        compute='_compute_invdash_return_e4_dictamen_state',
        string='Estado verificación E4',
    )
    invdash_return_e4_transfer_picking_ids = fields.Many2many(
        'stock.picking',
        'helpdesk_ticket_return_e4_transfer_rel',
        'ticket_id',
        'picking_id',
        string='Traslados E4 ejecutados',
        copy=False,
        readonly=True,
    )
    invdash_return_e4_transfer_summary_html = fields.Html(
        string='Resumen traslados E4',
        copy=False,
        readonly=True,
        sanitize=False,
    )
    invdash_return_e4_transfer_at = fields.Datetime(
        string='Traslados E4 ejecutados el',
        copy=False,
        readonly=True,
    )
    invdash_return_e4_transfer_user_id = fields.Many2one(
        'res.users',
        string='Traslados E4 por',
        copy=False,
        readonly=True,
    )
    invdash_return_e4_transfers_done = fields.Boolean(
        compute='_compute_invdash_return_e4_transfers_done',
        string='Traslados E4 hechos',
    )
    invdash_return_e4_can_mark_resolved = fields.Boolean(
        compute='_compute_invdash_return_e4_can_mark_resolved',
        string='Puede cerrar ticket E4',
    )
    invdash_return_e4_show_close_ticket_button = fields.Boolean(
        compute='_compute_invdash_return_e4_show_close_ticket_button',
        string='Mostrar botón cerrar ticket E4',
    )
    invdash_return_e4_report_observation = fields.Text(
        string='Observaciones del informe',
        copy=False,
        help='Texto libre que se incluirá en el informe PDF de revisión E4.',
    )
    invdash_return_e4_report_state = fields.Selection(
        [
            ('none', 'Sin iniciar'),
            ('draft', 'Borrador'),
            ('done', 'Finalizado'),
        ],
        string='Estado informe E4',
        default='none',
        copy=False,
        tracking=True,
    )
    invdash_return_e4_report_draft_user_id = fields.Many2one(
        'res.users',
        string='Borrador guardado por',
        copy=False,
        readonly=True,
    )
    invdash_return_e4_report_draft_at = fields.Datetime(
        string='Borrador guardado el',
        copy=False,
        readonly=True,
    )
    invdash_return_e4_report_final_user_id = fields.Many2one(
        'res.users',
        string='Informe finalizado por',
        copy=False,
        readonly=True,
    )
    invdash_return_e4_report_final_at = fields.Datetime(
        string='Informe finalizado el',
        copy=False,
        readonly=True,
    )
    invdash_return_e4_report_pdf_attachment_id = fields.Many2one(
        'ir.attachment',
        string='PDF informe E4',
        copy=False,
        readonly=True,
        ondelete='set null',
    )
    invdash_return_e4_report_can_edit = fields.Boolean(
        compute='_compute_invdash_return_e4_report_can_edit',
    )
    invdash_return_e4_origin_ticket_id = fields.Many2one(
        'helpdesk.ticket',
        string='Origen',
        ondelete='set null',
        index=True,
        copy=False,
        help='Ticket de verificación E4 desde el que se generó este seguimiento de traslado.',
    )
    invdash_return_e4_followup_ticket_ids = fields.One2many(
        'helpdesk.ticket',
        'invdash_return_e4_origin_ticket_id',
        string='Tickets origen',
        copy=False,
        help='Tickets creados al ejecutar traslados E4 (excepto Existencias).',
    )
    invdash_return_e4_followup_picking_id = fields.Many2one(
        'stock.picking',
        string='Albarán traslado E4',
        copy=False,
        readonly=True,
        ondelete='set null',
    )
    invdash_return_e4_followup_destination = fields.Selection(
        selection=[
            ('warranty', 'Garantía'),
            ('repair', 'Reparación'),
            ('scrap_initial', 'PreBaja'),
        ],
        string='Destino traslado',
        copy=False,
        readonly=True,
    )
    invdash_return_e4_followup_destination_label = fields.Char(
        string='Destino',
        compute='_compute_invdash_return_e4_followup_destination_label',
    )

    @api.depends('invdash_return_e4_followup_destination')
    def _compute_invdash_return_e4_followup_destination_label(self):
        for ticket in self:
            ticket.invdash_return_e4_followup_destination_label = (
                RETURN_E4_DESTINATION_LABELS.get(
                    ticket.invdash_return_e4_followup_destination,
                    ticket.invdash_return_e4_followup_destination or '',
                )
            )

    @api.depends('invdash_return_e4_report_state')
    def _compute_invdash_return_e4_report_can_edit(self):
        for ticket in self:
            ticket.invdash_return_e4_report_can_edit = (
                ticket.invdash_return_e4_report_state != 'done'
            )

    def _return_e4_heal_ticket_data(self):
        """Sincroniza cliente y técnico del ticket con el albarán E4 / dictamen."""
        self.ensure_one()
        anchor = self.invdash_return_e4_dictamen_line_id
        if not anchor:
            return
        group = anchor._return_e4_group_dictamen_lines()
        group._return_e4_heal_group_consistency()
        partner = anchor.picking_id._return_e4_resolve_ticket_partner(anchor.lot_id)
        vals = {}
        if partner and self.partner_id != partner:
            vals['partner_id'] = partner.id
        if self.user_id:
            anchor._return_e4_propagate_technician_to_group(self.user_id)
        team_vals = anchor._return_e4_ticket_team_and_stage_vals()
        if self.team_id.id != team_vals.get('team_id'):
            vals['team_id'] = team_vals['team_id']
        if vals:
            self.with_context(invdash_skip_dictamen_sync=True).write(vals)

    @api.depends('invdash_return_e4_item_ids')
    def _compute_invdash_return_e4_item_count(self):
        for ticket in self:
            ticket.invdash_return_e4_item_count = len(ticket.invdash_return_e4_item_ids)

    @api.depends('invdash_return_e4_dictamen_line_id', 'invdash_return_e4_item_ids')
    def _compute_invdash_return_e4_is_dictamen_ticket(self):
        for ticket in self:
            ticket.invdash_return_e4_is_dictamen_ticket = bool(
                ticket.invdash_return_e4_dictamen_line_id
                or ticket.invdash_return_e4_item_ids
            )

    @api.depends(
        'invdash_return_e4_item_ids',
        'invdash_return_e4_item_ids.destination',
        'invdash_return_e4_item_ids.dictamen_line_id.state',
    )
    def _compute_invdash_return_e4_dictamen_state(self):
        state_labels = {
            'unassigned': 'Sin asignar',
            'assigned': 'Asignado',
            'dictated': 'Verificado',
            'transferred': 'Trasladado',
        }
        for ticket in self:
            lines = ticket.invdash_return_e4_item_ids.mapped('dictamen_line_id')
            if not lines:
                ticket.invdash_return_e4_dictamen_state = ''
                continue
            states = set(lines.mapped('state'))
            if states == {'transferred'}:
                label = state_labels['transferred']
            elif 'dictated' in states and states <= {'dictated', 'transferred'}:
                label = _('Verificado (pend. traslado)')
            elif 'assigned' in states:
                label = state_labels['assigned']
            else:
                label = state_labels.get(next(iter(states)), '')
            pending = len(lines.filtered(lambda l: l.state != 'transferred'))
            total = len(lines)
            ticket.invdash_return_e4_dictamen_state = '%s — %s/%s' % (label, total - pending, total)

    @api.depends('invdash_return_e4_is_dictamen_ticket', 'stage_id', 'stage_id.name')
    def _compute_invdash_return_e4_show_close_ticket_button(self):
        for ticket in self:
            ticket.invdash_return_e4_show_close_ticket_button = bool(
                ticket.invdash_return_e4_is_dictamen_ticket
                and not ticket._is_stage_resuelto_or_closed()
            )

    @api.depends('invdash_return_e4_is_dictamen_ticket', 'stage_id', 'stage_id.name',
                 'invdash_return_e4_item_ids.destination',
                 'invdash_return_e4_item_ids.is_bundled_component',
                 'invdash_return_e4_item_ids.dictamen_line_id.state')
    def _compute_invdash_return_e4_can_mark_resolved(self):
        for ticket in self:
            ticket.invdash_return_e4_can_mark_resolved = bool(
                ticket.invdash_return_e4_is_dictamen_ticket
                and not ticket._is_stage_resuelto_or_closed()
                and not ticket._return_e4_ticket_items_missing_destination()
            )

    def _return_e4_ticket_items_missing_destination(self):
        """Filas del ticket sin destino/ruta definida (excluye componentes empaquetados)."""
        self.ensure_one()
        return self.invdash_return_e4_item_ids.filtered(
            lambda i: i.dictamen_line_id
            and i.dictamen_line_id.state != 'transferred'
            and not i.is_bundled_component
            and not i.destination
        )

    @api.depends(
        'invdash_return_e4_item_ids.dictamen_line_id.state',
        'invdash_return_e4_transfer_at',
    )
    def _compute_invdash_return_e4_transfers_done(self):
        for ticket in self:
            lines = ticket.invdash_return_e4_item_ids.mapped('dictamen_line_id')
            ticket.invdash_return_e4_transfers_done = bool(
                ticket.invdash_return_e4_transfer_at
                or (lines and all(l.state == 'transferred' for l in lines))
            )

    @api.model
    def _invdash_stage_triggers_e4_transfer(self, stage_id):
        if not stage_id:
            return False
        comodel = self._fields['stage_id'].comodel_name
        stage = self.env[comodel].browse(stage_id)
        if not stage.exists():
            return False
        return (stage.name or '').strip().lower() in INVDASH_E4_TICKET_CLOSE_STAGE_NAMES

    def _return_e4_build_transfer_summary_html(self, created_pickings, dictamen_lines):
        self.ensure_one()
        Picking = self.env['stock.picking']
        for picking in created_pickings:
            picking._return_e4_ensure_unique_picking_name()
        rows = []
        for dl in dictamen_lines.sorted(
            key=lambda l: (l.line_role, l.lot_id.name or ''),
        ):
            dest = RETURN_E4_DESTINATION_LABELS.get(dl.destination, dl.destination or '—')
            internal = dl.internal_picking_id
            pick_label = Picking._return_e4_format_picking_label(internal)
            rows.append(
                '<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
                    escape(RETURN_E4_LINE_ROLE_LABELS.get(dl.line_role, dl.line_role)),
                    escape(dl.lot_id.display_name or ''),
                    escape(dest),
                    escape(pick_label),
                )
            )
        pick_links = []
        for p in created_pickings:
            pick_links.append(
                '<li><a href="#" data-oe-model="stock.picking" data-oe-id="%s">%s</a> '
                '(%s → %s)</li>' % (
                    p.id,
                    escape(Picking._return_e4_format_picking_label(p)),
                    escape(p.location_id.display_name or ''),
                    escape(p.location_dest_id.display_name or ''),
                )
            )
        return Markup(
            '<p><strong>%s</strong> %s — %s</p>'
            '<table class="table table-sm"><thead><tr>'
            '<th>%s</th><th>%s</th><th>%s</th><th>%s</th>'
            '</tr></thead><tbody>%s</tbody></table>'
            '<p><strong>%s</strong></p><ul>%s</ul>'
        ) % (
            escape(_('Traslados E4 ejecutados')),
            escape(fields.Datetime.to_string(self.invdash_return_e4_transfer_at or fields.Datetime.now())),
            escape(self.invdash_return_e4_transfer_user_id.name or ''),
            escape(_('Rol')),
            escape(_('Serial')),
            escape(_('Destino')),
            escape(_('Albarán traslado')),
            Markup(''.join(rows)),
            escape(_('Traslados internos creados')),
            Markup(''.join(pick_links)) if pick_links else Markup('<li>%s</li>' % escape(_('(ninguno)'))),
        )

    def _return_e4_destination_code_for_picking(self, picking):
        """Código de destino E4 según ubicación destino del albarán."""
        if not picking or not picking.location_dest_id:
            return False
        LocHelper = self.env['return.route.location']
        dest_by_code = LocHelper.get_return_e4_destination_locations()
        dest_loc_id = picking.location_dest_id.id
        for code, loc in dest_by_code.items():
            if loc.id == dest_loc_id:
                return code
        return False

    def _return_e4_pick_initial_helpdesk_stage(self):
        """Etapa abierta para tickets de seguimiento E4 (pendiente de asignación)."""
        self.ensure_one()
        if hasattr(self, '_mesa_followup_pick_open_stage'):
            stage = self._mesa_followup_pick_open_stage(team=self.team_id)
            if stage:
                return stage
        Ticket = self.env['helpdesk.ticket']
        finfo = Ticket._fields.get('stage_id')
        if not finfo:
            return self.env['helpdesk.stage']
        Stage = self.env[finfo.comodel_name]
        domain = []
        if hasattr(Stage, 'closed'):
            domain.append(('closed', '=', False))
        if hasattr(Stage, 'team_ids') and self.team_id:
            domain = ['|', ('team_ids', '=', False), ('team_ids', 'in', self.team_id.id)] + domain
        return Stage.search(domain, order='sequence, id', limit=1)

    def _return_e4_followup_category_for_destination(self, dest_code):
        """Categoría provisional por destino (ajustable según reglas de negocio)."""
        Category = self.env['helpdesk.ticket.category'].sudo()
        keywords = {
            'warranty': ('GARANTÍA', 'Garantía'),
            'repair': ('REPARACIÓN', 'Reparación', 'REPARACION'),
            'scrap_initial': ('PREBAJA', 'PreBaja', 'BAJA'),
        }.get(dest_code, ())
        for kw in keywords:
            cat = Category.search([
                '|',
                ('complete_name', 'ilike', kw),
                ('name', 'ilike', kw),
            ], limit=1)
            if cat:
                return cat
        return self.category_id

    def _return_e4_build_followup_ticket_description(self, picking, dictamen_lines, dest_code):
        """HTML con seriales del traslado para el ticket de seguimiento."""
        self.ensure_one()
        Picking = self.env['stock.picking']
        lines = dictamen_lines.filtered(
            lambda dl: dl.internal_picking_id == picking,
        )
        if not lines:
            lots = picking.move_line_ids.mapped('lot_id')
            rows = []
            for lot in lots:
                rows.append(
                    '<tr><td>%s</td><td>%s</td></tr>' % (
                        escape(lot.display_name or lot.name or '—'),
                        escape(lot.product_id.display_name or ''),
                    )
                )
        else:
            rows = []
            for dl in lines.sorted(key=lambda l: (l.line_role, l.lot_id.name or '')):
                rows.append(
                    '<tr><td>%s</td><td>%s</td><td>%s</td></tr>' % (
                        escape(RETURN_E4_LINE_ROLE_LABELS.get(dl.line_role, dl.line_role)),
                        escape(dl.lot_id.display_name or ''),
                        escape(dl.product_id.display_name or ''),
                    )
                )
        dest_label = RETURN_E4_DESTINATION_LABELS.get(dest_code, dest_code or '—')
        pick_label = Picking._return_e4_format_picking_label(picking)
        if lines:
            header_cols = '<th>%s</th><th>%s</th><th>%s</th>' % (
                escape(_('Rol')), escape(_('Serial')), escape(_('Producto')),
            )
            empty_colspan = 3
        else:
            header_cols = '<th>%s</th><th>%s</th>' % (
                escape(_('Serial')), escape(_('Producto')),
            )
            empty_colspan = 2
        body_rows = (
            Markup(''.join(rows))
            if rows
            else Markup(
                '<tr><td colspan="%s">%s</td></tr>' % (empty_colspan, escape(_('(sin seriales)')))
            )
        )
        return Markup(
            '<p>%s <strong>%s</strong> — %s</p>'
            '<p>%s: %s<br/>%s: %s → %s</p>'
            '<table class="table table-sm"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>'
        ) % (
            escape(_('Traslado E4')),
            escape(dest_label),
            escape(pick_label),
            escape(_('Ticket origen')),
            escape(self.display_name or self.name or ''),
            escape(_('Ruta')),
            escape(picking.location_id.display_name or ''),
            escape(picking.location_dest_id.display_name or ''),
            Markup(header_cols),
            body_rows,
        )

    def _return_e4_followup_assigned_user(self):
        """Responsable del equipo para tickets generados desde traslados E4."""
        self.ensure_one()
        team = self.team_id
        if not team:
            raise UserError(_(
                'No se pueden crear tickets de seguimiento E4: '
                'el ticket origen no tiene equipo de soporte.'
            ))
        responsible = team.invdash_responsible_user_id
        if not responsible:
            raise UserError(_(
                'No se pueden crear tickets de seguimiento E4: configure el campo '
                '«Responsable» en el equipo «%s».'
            ) % (team.display_name,))
        return responsible

    def _return_e4_create_followup_tickets_from_transfers(
        self, created_pickings, dictamen_lines,
    ):
        """Un ticket de seguimiento por albarán interno (excepto Existencias)."""
        self.ensure_one()
        if not self.invdash_return_e4_is_dictamen_ticket:
            return self.env['helpdesk.ticket']
        Ticket = self.env['helpdesk.ticket'].sudo()
        assigned_user = self._return_e4_followup_assigned_user()
        stage = self._return_e4_pick_initial_helpdesk_stage()
        if not stage:
            self.message_post(
                body=_(
                    'No se crearon tickets de seguimiento E4: no hay etapa abierta en el embudo.'
                ),
                subtype_xmlid='mail.mt_note',
            )
            return Ticket.browse()
        created = Ticket.browse()
        for picking in created_pickings:
            dest_code = self._return_e4_destination_code_for_picking(picking)
            if not dest_code or dest_code == 'stock':
                continue
            existing = Ticket.search([
                ('invdash_return_e4_origin_ticket_id', '=', self.id),
                ('invdash_return_e4_followup_picking_id', '=', picking.id),
            ], limit=1)
            if existing:
                created |= existing
                continue
            lines = dictamen_lines.filtered(
                lambda dl: dl.internal_picking_id == picking,
            )
            principal_lot = self.invdash_return_e4_principal_lot_id
            if not principal_lot and lines:
                principal_line = lines.filtered(
                    lambda dl: dl.line_role == 'principal',
                )[:1]
                principal_lot = principal_line.lot_id if principal_line else lines[:1].lot_id
            if not principal_lot:
                principal_lot = picking.move_line_ids[:1].lot_id
            dest_label = RETURN_E4_DESTINATION_LABELS.get(dest_code, dest_code)
            Picking = self.env['stock.picking']
            pick_label = Picking._return_e4_format_picking_label(picking)
            title = _('E4 %(dest)s — %(picking)s') % {
                'dest': dest_label,
                'picking': pick_label,
            }
            if len(title) > 200:
                title = title[:197] + '...'
            category = self._return_e4_followup_category_for_destination(dest_code)
            vals = {
                'name': title,
                'partner_id': self.partner_id.id if self.partner_id else False,
                'team_id': self.team_id.id if self.team_id else False,
                'user_id': assigned_user.id,
                'category_id': category.id if category else False,
                'priority': self.priority,
                'description': self._return_e4_build_followup_ticket_description(
                    picking, dictamen_lines, dest_code,
                ),
                'lot_id': principal_lot.id if principal_lot else False,
                'stage_id': stage.id,
                'invdash_return_e4_origin_ticket_id': self.id,
                'invdash_return_e4_followup_picking_id': picking.id,
                'invdash_return_e4_followup_destination': dest_code,
            }
            if self.company_id:
                vals['company_id'] = self.company_id.id
            followup = Ticket.create(vals)
            created |= followup
        if created:
            links = Markup('').join(
                Markup(
                    '<li><a href="#" data-oe-model="helpdesk.ticket" data-oe-id="%s">%s</a></li>'
                ) % (t.id, escape(t.name or ''))
                for t in created
            )
            self.message_post(
                body=Markup('<p>%s</p><ul>%s</ul>') % (
                    escape(_('Tickets de seguimiento E4 creados:')),
                    links,
                ),
                subtype_xmlid='mail.mt_note',
            )
        return created

    def _return_e4_post_transfer_on_ticket(self, created_pickings, dictamen_lines, already_done=False):
        self.ensure_one()
        if already_done:
            body = Markup('<p>%s</p>') % escape(_(
                'Traslados E4: los equipos ya estaban trasladados.'
            ))
        else:
            summary = self._return_e4_build_transfer_summary_html(
                created_pickings, dictamen_lines,
            )
            link = [(4, pid) for pid in created_pickings.ids]
            self.with_context(
                invdash_skip_dictamen_sync=True,
                invdash_skip_e4_close_transfer=True,
            ).write({
                'invdash_return_e4_transfer_summary_html': summary,
                'invdash_return_e4_transfer_at': fields.Datetime.now(),
                'invdash_return_e4_transfer_user_id': self.env.user.id,
                'invdash_return_e4_transfer_picking_ids': link,
            })
            self._return_e4_create_followup_tickets_from_transfers(
                created_pickings, dictamen_lines,
            )
            body = summary
        self.message_post(
            body=body,
            subtype_xmlid='mail.mt_note',
        )

    def _return_e4_validate_ticket_destinations(self):
        """Exige destino en cada fila editable de la tabla del ticket."""
        self.ensure_one()
        missing_items = self._return_e4_ticket_items_missing_destination()
        if missing_items:
            serials = ', '.join(
                (i.lot_id.display_name or i.lot_id.name or '?')
                for i in missing_items[:12]
            )
            raise UserError(_(
                'Indique el destino (ruta) de cada equipo en la tabla «Equipos a verificar»:\n%s'
            ) % serials)

    def _return_e4_execute_transfers_from_ticket(self):
        """Ejecuta traslados internos según destinos del ticket (acción explícita del técnico)."""
        self.ensure_one()
        if self.invdash_return_e4_transfers_done:
            self._return_e4_post_transfer_on_ticket(
                self.invdash_return_e4_transfer_picking_ids,
                self.invdash_return_e4_item_ids.mapped('dictamen_line_id'),
                already_done=True,
            )
            return True
        self.invdash_return_e4_item_ids.filtered(
            'dictamen_line_id',
        )._invdash_sync_dictamen_from_item()
        self._return_e4_validate_ticket_destinations()
        picking = self.invdash_return_e4_picking_id
        if not picking or not picking._is_return_route_e4_picking():
            raise UserError(_('Este ticket E4 ya no está vinculado a un albarán de devolución válido.'))
        dictamen_lines = self.invdash_return_e4_item_ids.mapped('dictamen_line_id')
        pending = dictamen_lines.filtered(lambda l: l.state != 'transferred')
        if not pending:
            self._return_e4_post_transfer_on_ticket(
                self.env['stock.picking'], pending, already_done=True,
            )
            return True
        result = picking.with_context(
            invdash_return_e4_from_ticket=True,
        )._return_e4_finalize_dictamen_transfer_batch(pending)
        self._return_e4_post_transfer_on_ticket(
            result['created_pickings'], result['dictamen_lines'],
        )
        return True

    def _return_e4_sync_e4_order_on_ticket_close(self):
        """Al cerrar el ticket: sincroniza dictamen al albarán E4 sin mover stock."""
        self.ensure_one()
        picking = self.invdash_return_e4_picking_id
        if not picking or not picking._is_return_route_e4_picking():
            raise UserError(_('Este ticket E4 ya no está vinculado a un albarán de devolución válido.'))

        # Traslados ya ejecutados desde el botón: no repetir sync ni chatter (evita cuelgue al resolver).
        if self.invdash_return_e4_transfer_at:
            if (
                picking.state not in ('done', 'cancel')
                and picking.invdash_return_e4_all_dictamen_done
            ):
                picking.with_context(
                    mail_notrack=True,
                    tracking_disable=True,
                )._complete_return_e4_route_picking_after_classification()
            return

        self.invdash_return_e4_item_ids.filtered(
            'dictamen_line_id',
        )._invdash_sync_dictamen_from_item()
        self._return_e4_validate_ticket_destinations()
        dictamen_lines = self.invdash_return_e4_item_ids.mapped('dictamen_line_id')
        picking_ctx = {'mail_notrack': True, 'tracking_disable': True}
        if picking.invdash_return_e4_all_dictamen_done:
            picking.with_context(**picking_ctx).message_post(body=_(
                'Verificación E4 completada al cerrar ticket %s. Progreso: %s'
            ) % (
                self.display_name or self.name,
                picking.invdash_return_e4_dictamen_progress or '—',
            ))
            picking.with_context(**picking_ctx)._complete_return_e4_route_picking_after_classification()
        elif dictamen_lines and all(
            l.state in ('dictated', 'transferred') for l in dictamen_lines
        ):
            picking.with_context(**picking_ctx).message_post(body=_(
                'Verificación registrada al cerrar ticket %s. Traslados pendientes '
                '(use «Ejecutar traslados E4» o logística). Progreso: %s'
            ) % (
                self.display_name or self.name,
                picking.invdash_return_e4_dictamen_progress or '—',
            ))

    def action_return_e4_execute_transfers(self):
        """Botón en ticket: traslada según destinos indicados en la tabla."""
        for ticket in self:
            ticket._return_e4_execute_transfers_from_ticket()
        return True

    def action_return_e4_mark_resolved(self):
        """Cierra el ticket E4 por servidor (evita cuelgue del statusbar sin web_save)."""
        for ticket in self:
            if not ticket.invdash_return_e4_is_dictamen_ticket:
                raise UserError(_('Este ticket no es de verificación E4.'))
            if ticket._is_stage_resuelto_or_closed():
                raise UserError(_('Este ticket ya está en etapa final.'))
            ticket._return_e4_validate_ticket_destinations()
            if hasattr(ticket, '_mesa_followup_pick_resolved_stage'):
                stage = ticket._mesa_followup_pick_resolved_stage()
            else:
                stage = self.env['helpdesk.stage'].sudo().search(
                    [('name', '=ilike', 'resuelto')],
                    limit=1,
                )
            if not stage:
                raise UserError(_(
                    'No se encontró la etapa «Resuelto» para este equipo de helpdesk.'
                ))
            ticket.write({'stage_id': stage.id})
        return True

    def action_open_return_e4_transfer_pickings(self):
        self.ensure_one()
        pickings = self.invdash_return_e4_transfer_picking_ids
        if not pickings:
            raise UserError(_('Este ticket aún no tiene traslados E4 ejecutados.'))
        if len(pickings) == 1:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'stock.picking',
                'res_id': pickings.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return {
            'type': 'ir.actions.act_window',
            'name': _('Traslados E4'),
            'res_model': 'stock.picking',
            'domain': [('id', 'in', pickings.ids)],
            'view_mode': 'list,form',
            'target': 'current',
        }

    def write(self, vals):
        to_sync_on_close = self.env['helpdesk.ticket']
        if (
            'stage_id' in vals
            and vals.get('stage_id')
            and not self.env.context.get('invdash_skip_e4_close_transfer')
            and self._invdash_stage_triggers_e4_transfer(vals['stage_id'])
        ):
            to_sync_on_close = self.filtered(
                lambda t: t.invdash_return_e4_is_dictamen_ticket
                and not t._is_stage_resuelto_or_closed()
            )
        res = super().write(vals)
        if to_sync_on_close:
            for ticket in to_sync_on_close:
                ticket._return_e4_sync_e4_order_on_ticket_close()
        if self.env.context.get('invdash_skip_dictamen_sync'):
            return res
        if 'user_id' in vals and not self.env.context.get(
            'invdash_propagating_technician'
        ) and not self.env.context.get('invdash_skip_dictamen_sync'):
            for ticket in self.filtered('invdash_return_e4_is_dictamen_ticket'):
                anchor = ticket.invdash_return_e4_dictamen_line_id
                if anchor and ticket.user_id:
                    anchor._return_e4_propagate_technician_to_group(ticket.user_id)
        if 'invdash_return_e4_dictamen_note' in vals:
            note = vals.get('invdash_return_e4_dictamen_note') or ''
            for ticket in self.filtered('invdash_return_e4_item_ids'):
                ticket.invdash_return_e4_item_ids.filtered(
                    lambda i: i.dictamen_line_id and i.dictamen_line_id.state != 'transferred'
                ).mapped('dictamen_line_id').write({'dictamen_note': note})
        return res

    def action_open_return_e4_picking(self):
        self.ensure_one()
        picking = self.invdash_return_e4_picking_id
        if not picking:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': _('Albarán E4'),
            'res_model': 'stock.picking',
            'res_id': picking.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _return_e4_report_selected_items(self):
        self.ensure_one()
        return self.invdash_return_e4_item_ids.filtered('report_include').sorted(
            key=lambda i: (i.is_bundled_component, i.sequence, i.id),
        )

    def _return_e4_report_informe_anchors(self):
        """Un informe por asociado/standalone y uno compartido por principal+componentes."""
        self.ensure_one()
        included = self._return_e4_report_selected_items()
        anchor_ids = set()
        anchors = self.env['helpdesk.ticket.return.e4.item']
        for item in included:
            anchor = item._return_e4_informe_anchor_item()
            if anchor.id not in anchor_ids:
                anchor_ids.add(anchor.id)
                anchors |= anchor
        anchors._return_e4_ensure_default_informe_html()
        return anchors.sorted(
            key=lambda i: (i.is_bundled_component, i.sequence, i.id),
        )

    def _return_e4_ensure_report_editable(self):
        self.ensure_one()
        if self.invdash_return_e4_report_state == 'done':
            raise UserError(_(
                'El informe ya está finalizado. Use «Reabrir borrador» para editarlo.'
            ))

    def _return_e4_get_verification_report(self):
        report = self.env.ref(
            'inventory_dashboard_simple.action_report_return_e4_ticket_review',
            raise_if_not_found=False,
        )
        if not report:
            raise UserError(_('No se encontró la plantilla del informe de verificación E4.'))
        return report

    def _return_e4_render_verification_report_pdf(self):
        self.ensure_one()
        report = self._return_e4_get_verification_report()
        report_ref = report.report_name
        pdf_content, _ = report.sudo()._render_qweb_pdf(
            report_ref, res_ids=[self.id], data=None,
        )
        if not pdf_content:
            raise UserError(_('No se pudo generar el PDF del informe de revisión E4.'))
        if isinstance(pdf_content, str):
            pdf_content = pdf_content.encode('utf-8')
        return pdf_content

    def _return_e4_report_notification(self, title, message, notif_type='success'):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': message,
                'type': notif_type,
                'sticky': False,
            },
        }

    def action_return_e4_save_report_draft(self):
        self.ensure_one()
        if not self.invdash_return_e4_is_dictamen_ticket:
            raise UserError(_('Este informe solo aplica a tickets de verificación E4.'))
        self._return_e4_ensure_report_editable()
        now = fields.Datetime.now()
        self.write({
            'invdash_return_e4_report_state': 'draft',
            'invdash_return_e4_report_draft_user_id': self.env.user.id,
            'invdash_return_e4_report_draft_at': now,
        })
        self.message_post(
            body=Markup('<p>%s</p>') % escape(_(
                'Informe de revisión E4 guardado como borrador.'
            )),
            subtype_xmlid='mail.mt_note',
        )
        return self._return_e4_report_notification(
            _('Borrador guardado'),
            _('Puede continuar el informe más tarde. Los cambios quedaron registrados en el ticket.'),
        )

    def action_return_e4_finalize_report(self):
        self.ensure_one()
        if not self.invdash_return_e4_is_dictamen_ticket:
            raise UserError(_('Este informe solo aplica a tickets de verificación E4.'))
        self._return_e4_ensure_report_editable()
        if not self._return_e4_report_selected_items():
            raise UserError(_(
                'Marque al menos un equipo en la columna «Incluir en informe».'
            ))
        pdf_content = self._return_e4_render_verification_report_pdf()
        ticket_name = (self.name or str(self.id)).replace('/', '_')
        attachment_name = 'Informe_E4_%s.pdf' % ticket_name
        if self.invdash_return_e4_report_pdf_attachment_id:
            self.invdash_return_e4_report_pdf_attachment_id.sudo().unlink()
        attachment = self.env['ir.attachment'].sudo().create({
            'name': attachment_name,
            'type': 'binary',
            'datas': base64.b64encode(pdf_content).decode('ascii'),
            'res_model': 'helpdesk.ticket',
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })
        now = fields.Datetime.now()
        self.write({
            'invdash_return_e4_report_state': 'done',
            'invdash_return_e4_report_final_user_id': self.env.user.id,
            'invdash_return_e4_report_final_at': now,
            'invdash_return_e4_report_pdf_attachment_id': attachment.id,
        })
        self.message_post(
            body=Markup('<p>%s</p>') % escape(_(
                'Informe de revisión E4 finalizado y guardado en el ticket.'
            )),
            attachment_ids=[attachment.id],
            subtype_xmlid='mail.mt_note',
        )
        return self._return_e4_report_notification(
            _('Informe finalizado'),
            _('El PDF quedó adjunto al ticket. Puede descargarlo desde el historial o el campo PDF informe E4.'),
        )

    def action_return_e4_reopen_report_draft(self):
        self.ensure_one()
        if not self.invdash_return_e4_is_dictamen_ticket:
            raise UserError(_('Este informe solo aplica a tickets de verificación E4.'))
        if self.invdash_return_e4_report_state != 'done':
            raise UserError(_('Solo puede reabrir un informe que ya fue finalizado.'))
        self.write({'invdash_return_e4_report_state': 'draft'})
        self.message_post(
            body=Markup('<p>%s</p>') % escape(_(
                'Informe de revisión E4 reabierto como borrador.'
            )),
            subtype_xmlid='mail.mt_note',
        )
        return self._return_e4_report_notification(
            _('Informe reabierto'),
            _('Puede editar el informe y volver a finalizarlo cuando termine.'),
        )

    def action_return_e4_report_select_all_items(self):
        for ticket in self.filtered('invdash_return_e4_is_dictamen_ticket'):
            ticket._return_e4_ensure_report_editable()
            ticket.invdash_return_e4_item_ids.write({'report_include': True})
        return True

    def action_return_e4_report_clear_items(self):
        for ticket in self.filtered('invdash_return_e4_is_dictamen_ticket'):
            ticket._return_e4_ensure_report_editable()
            ticket.invdash_return_e4_item_ids.write({'report_include': False})
        return True

    def action_return_e4_generate_verification_report(self):
        self.ensure_one()
        if not self.invdash_return_e4_is_dictamen_ticket:
            raise UserError(_('Este informe solo aplica a tickets de verificación E4.'))
        if not self._return_e4_report_selected_items():
            raise UserError(_(
                'Marque al menos un equipo en la columna «Incluir en informe».'
            ))
        return self._return_e4_get_verification_report().report_action(self)

    def action_return_e4_generate_life_sheets_report(self):
        self.ensure_one()
        if not self.invdash_return_e4_is_dictamen_ticket:
            raise UserError(_('Este informe solo aplica a tickets de verificación E4.'))
        lots = self._return_e4_report_selected_items().mapped('lot_id')
        if not lots:
            raise UserError(_(
                'Marque al menos un equipo en la columna «Incluir en informe».'
            ))
        report = self.env.ref(
            'mesa_ayuda_inventario.action_report_stock_lot_life_sheet',
            raise_if_not_found=False,
        )
        if not report:
            raise UserError(_('No se encontró el reporte de hoja de vida.'))
        return report.report_action(lots)

    def _return_e4_lot_detail_sections(self, lot_records, role='principal'):
        """Bloques HTML de ficha por serial (solo filas con valor)."""
        try:
            from odoo.addons.mesa_ayuda_inventario.wizard.acta_lot_detail_html import (
                mesa_acta_lot_devolucion_ticket_detail_html,
            )
        except ImportError:
            return []
        sections = []
        for lot in lot_records:
            if not lot:
                continue
            detail_html = mesa_acta_lot_devolucion_ticket_detail_html(self.env, lot)
            if not detail_html:
                continue
            if role == 'principal':
                heading = Markup(
                    '<p class="o_return_e4_detail_heading"><strong>%s</strong></p>'
                ) % escape(_('Equipo principal'))
            elif role == 'associated':
                heading = Markup(
                    '<p class="o_return_e4_detail_heading"><strong>%s — %s</strong></p>'
                ) % (escape(_('Asociado')), escape(lot.display_name or ''))
            else:
                heading = Markup(
                    '<p class="o_return_e4_detail_heading"><strong>%s — %s</strong></p>'
                ) % (
                    escape(RETURN_E4_LINE_ROLE_LABELS.get(role, role)),
                    escape(lot.display_name or ''),
                )
            sections.extend([heading, detail_html])
        return sections

class StockPickingReturnE4DictamenLineTicket(models.Model):
    _inherit = 'stock.picking.return.e4.dictamen.line'

    helpdesk_ticket_id = fields.Many2one(
        'helpdesk.ticket',
        string='Ticket verificación',
        copy=False,
        readonly=True,
        index=True,
    )

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('invdash_skip_ticket_sync'):
            self._return_e4_sync_helpdesk_tickets(vals)
        return res

    def _return_e4_sync_helpdesk_tickets(self, vals):
        """Sincroniza cambios puntuales al ticket (técnico); destinos van por ítems del ticket."""
        sync_fields = {'technician_user_id'}
        if not sync_fields & set(vals.keys()):
            return
        for anchor in self.mapped(lambda l: l._return_e4_group_anchor()):
            ticket = anchor.helpdesk_ticket_id
            if not ticket:
                continue
            tech = anchor.technician_user_id
            if tech:
                ticket_vals = {
                    'user_id': tech.id,
                    **anchor._return_e4_ticket_team_and_stage_vals(),
                }
                ticket.with_context(invdash_skip_dictamen_sync=True).write(ticket_vals)

    @api.model
    def _return_e4_normalize_asset_class_key(self, value):
        text = (value or '').strip().lower()
        return ' '.join(text.replace('-', ' ').replace('_', ' ').split())

    def _return_e4_verification_suffix_for_asset_class(self, asset_class):
        if not asset_class:
            return False
        code = (asset_class.code or '').strip().upper()
        if code in RETURN_E4_ASSET_CLASS_CODE_TO_VERIFICATION_SUFFIX:
            return RETURN_E4_ASSET_CLASS_CODE_TO_VERIFICATION_SUFFIX[code]
        norm = self._return_e4_normalize_asset_class_key(asset_class.name)
        if norm in RETURN_E4_ASSET_CLASS_TO_VERIFICATION_SUFFIX:
            return RETURN_E4_ASSET_CLASS_TO_VERIFICATION_SUFFIX[norm]
        for key, suffix in RETURN_E4_ASSET_CLASS_TO_VERIFICATION_SUFFIX.items():
            if key in norm or norm in key:
                return suffix
        return (asset_class.name or '').strip() or False

    def _return_e4_search_verification_ticket_category(self, suffix):
        Category = self.env['helpdesk.ticket.category'].sudo()
        if not suffix:
            return Category.browse()
        candidates = [
            'VERIFICACIÓN / Verificación - %s' % suffix,
            'VERIFICACIÓN / Verificación-%s' % suffix,
        ]
        for complete_name in candidates:
            category = Category.search([
                ('complete_name', '=ilike', complete_name),
            ], limit=1)
            if category:
                return category
        return Category.search([
            ('name', '=ilike', 'Verificación - %s' % suffix),
            '|',
            ('parent_id.name', '=ilike', 'VERIFICACIÓN'),
            ('parent_id.complete_name', '=ilike', 'VERIFICACIÓN'),
        ], limit=1)

    @api.model
    def _return_e4_get_default_verification_ticket_category(self):
        Category = self.env['helpdesk.ticket.category'].sudo()
        category = Category.search([
            ('complete_name', '=ilike', RETURN_E4_DEFAULT_VERIFICATION_CATEGORY),
        ], limit=1)
        if category:
            return category
        return Category.search([
            ('name', '=ilike', 'Verificaciones'),
            '|',
            ('parent_id.name', '=ilike', 'VERIFICACIÓN'),
            ('parent_id.complete_name', '=ilike', 'VERIFICACIÓN'),
        ], limit=1)

    def _return_e4_get_dictamen_ticket_category(self, principal_lot=None):
        """Categoría helpdesk según clase de activo del producto principal."""
        asset_class = False
        if principal_lot and principal_lot.product_id:
            asset_class = principal_lot.product_id.asset_class_id
        if asset_class:
            suffix = self._return_e4_verification_suffix_for_asset_class(asset_class)
            category = self._return_e4_search_verification_ticket_category(suffix)
            if category:
                return category
        return self._return_e4_get_default_verification_ticket_category()

    def _return_e4_build_ticket_description_html(self, group_lines):
        anchor = self._return_e4_anchor_from_group_lines(group_lines)
        Ticket = self.env['helpdesk.ticket']
        parts = list(Ticket._return_e4_lot_detail_sections(
            anchor.lot_id,
            role='principal',
        ))
        associated = group_lines.filtered(
            lambda l: l.line_role == 'associated',
        ).sorted(key=lambda l: l.id)
        parts.extend(Ticket._return_e4_lot_detail_sections(
            associated.mapped('lot_id'),
            role='associated',
        ))
        bundled = group_lines.filtered(
            lambda l: l.line_role == 'bundled',
        ).sorted(key=lambda l: l.id)
        parts.extend(Ticket._return_e4_lot_detail_sections(
            bundled.mapped('lot_id'),
            role='bundled',
        ))
        if not parts:
            for dl in group_lines:
                parts.append(Markup('<p>%s — %s</p>') % (
                    escape(RETURN_E4_LINE_ROLE_LABELS.get(dl.line_role, dl.line_role)),
                    escape(dl.lot_id.display_name or ''),
                ))
        return Markup('').join(parts)

    def _return_e4_build_ticket_name(self, group_lines):
        """Asunto: Verificación + serial principal (detalle en el formulario del ticket)."""
        anchor = self._return_e4_anchor_from_group_lines(group_lines)
        lot = anchor.lot_id
        serial = (lot.name or lot.display_name or '').strip() or '—'
        return _('Verificación %s') % serial

    def _return_e4_rebuild_ticket_items(self, ticket, group_lines):
        """Tabla editable en ticket: principal, asociados visibles y componentes empaquetados."""
        group_lines._return_e4_heal_group_consistency()
        Item = self.env['helpdesk.ticket.return.e4.item'].sudo()
        existing_items = Item.search([('ticket_id', '=', ticket.id)])
        saved_report = {
            item.lot_id.id: {
                'report_include': item.report_include,
                'report_review_note': item.report_review_note or False,
                'report_informe_html': item.report_informe_html or False,
                'verification_state': item.verification_state or False,
            }
            for item in existing_items
        }
        existing_items.unlink()
        anchor = self._return_e4_anchor_from_group_lines(group_lines)
        picking = anchor.picking_id
        sequence = 10
        role_order = {'principal': 1, 'standalone': 2, 'associated': 3, 'bundled': 4}
        dictamen_sorted = group_lines.sorted(
            key=lambda l: (role_order.get(l.line_role, 9), l.id),
        )
        listed_lot_ids = set(group_lines.mapped('lot_id').ids)
        principal_dest = anchor.destination

        def _report_vals_for_lot(lot_id, line_role):
            saved = saved_report.get(lot_id, {})
            default_include = line_role != 'bundled'
            return {
                'report_include': saved.get('report_include', default_include),
                'report_review_note': saved.get('report_review_note') or False,
                'report_informe_html': saved.get('report_informe_html') or False,
                'verification_state': saved.get('verification_state') or False,
            }

        for dl in dictamen_sorted:
            report_vals = _report_vals_for_lot(dl.lot_id.id, dl.line_role)
            Item.create({
                'ticket_id': ticket.id,
                'dictamen_line_id': dl.id,
                'lot_id': dl.lot_id.id,
                'line_role': dl.line_role,
                'principal_lot_id': dl.principal_lot_id.id if dl.principal_lot_id else False,
                'destination': dl.destination or False,
                'line_note': dl.dictamen_note or False,
                'is_bundled_component': dl.line_role == 'bundled',
                'sequence': sequence,
                **report_vals,
            })
            sequence += 10

        if anchor.line_role == 'principal':
            bundled = picking._return_e4_bundled_lots_for_principal(
                anchor.lot_id,
                exclude_lot_ids=listed_lot_ids,
            )
            for row in bundled:
                lot = row['lot']
                report_vals = _report_vals_for_lot(lot.id, 'bundled')
                Item.create({
                    'ticket_id': ticket.id,
                    'lot_id': lot.id,
                    'line_role': 'bundled',
                    'principal_lot_id': anchor.lot_id.id,
                    'destination': principal_dest or False,
                    'is_bundled_component': True,
                    'sequence': sequence,
                    **report_vals,
                })
                sequence += 10

    def _return_e4_ensure_helpdesk_ticket(self):
        """Un ticket por principal (+ asociados y componentes empaquetados) o por serial suelto."""
        Ticket = self.env['helpdesk.ticket'].sudo()
        created = self.env['helpdesk.ticket']
        processed_anchors = set()

        for line in self:
            anchor = line._return_e4_group_anchor()
            if anchor.id in processed_anchors:
                continue
            group = anchor._return_e4_group_dictamen_lines()
            tech = anchor.technician_user_id
            if not tech:
                tech = group.mapped('technician_user_id')[:1]
            if not tech:
                continue
            processed_anchors.add(anchor.id)
            anchor._return_e4_propagate_technician_to_group(tech)
            group = anchor._return_e4_group_dictamen_lines()

            existing = group.mapped('helpdesk_ticket_id')[:1]
            lot = anchor.lot_id
            picking = anchor.picking_id
            partner = picking._return_e4_resolve_ticket_partner(lot)
            category = self._return_e4_get_dictamen_ticket_category(lot)
            team_vals = self._return_e4_ticket_team_and_stage_vals()
            if existing:
                ticket = existing
                ticket_vals = {
                    'user_id': tech.id,
                    'lot_id': lot.id,
                    'invdash_return_e4_dictamen_line_id': anchor.id,
                    **team_vals,
                }
                if partner:
                    ticket_vals['partner_id'] = partner.id
                ticket.with_context(invdash_skip_dictamen_sync=True).write(ticket_vals)
            else:
                ticket = Ticket.create({
                    'name': self._return_e4_build_ticket_name(group),
                    'partner_id': partner.id if partner else False,
                    'lot_id': lot.id,
                    'user_id': tech.id,
                    'description': self._return_e4_build_ticket_description_html(group),
                    'category_id': category.id if category else False,
                    'invdash_return_e4_dictamen_line_id': anchor.id,
                    **team_vals,
                })
                created |= ticket
                picking = anchor.picking_id
                picking.message_post(body=Markup(
                    '<p>Ticket E4: '
                    '<a href="#" data-oe-model="helpdesk.ticket" data-oe-id="%s">%s</a>'
                    ' — técnico %s</p>'
                ) % (
                    ticket.id,
                    escape(ticket.name or ticket.display_name),
                    escape(tech.name or ''),
                ))

            group.with_context(invdash_skip_ticket_sync=True).write({
                'helpdesk_ticket_id': ticket.id,
            })
            partner = picking._return_e4_resolve_ticket_partner(lot)
            if partner and not ticket.partner_id:
                ticket.with_context(invdash_skip_dictamen_sync=True).write({
                    'partner_id': partner.id,
                })
            self._return_e4_rebuild_ticket_items(ticket, group)

        return created

    def action_open_helpdesk_ticket(self):
        self.ensure_one()
        anchor = self._return_e4_group_anchor()
        if not anchor.helpdesk_ticket_id:
            if not anchor.technician_user_id:
                from odoo.exceptions import UserError
                raise UserError(_('Asigne un técnico al equipo principal antes de abrir el ticket.'))
            anchor._return_e4_ensure_helpdesk_ticket()
        ticket = anchor.helpdesk_ticket_id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Ticket verificación E4'),
            'res_model': 'helpdesk.ticket',
            'res_id': ticket.id,
            'view_mode': 'form',
            'target': 'current',
        }
