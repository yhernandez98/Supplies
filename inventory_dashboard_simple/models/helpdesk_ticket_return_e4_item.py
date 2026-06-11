# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from markupsafe import Markup

from .stock_picking_return_e4_dictamen_line import RETURN_E4_DESTINATION_SELECTION

RETURN_E4_LINE_ROLE_LABELS = {
    'principal': 'Principal',
    'associated': 'Asociado',
    'standalone': 'Serial',
    'bundled': 'Componente',
}

RETURN_E4_ITEM_VERIFICATION_STATE = [
    ('assigned', 'Asignado'),
    ('dictated', 'Verificado'),
]

RETURN_E4_ITEM_EQUIPMENT_ESTADO = RETURN_E4_ITEM_VERIFICATION_STATE + [
    ('transferred', 'Trasladado'),
]


class HelpdeskTicketReturnE4Item(models.Model):
    _name = 'helpdesk.ticket.return.e4.item'
    _description = 'Ítem verificación E4 en ticket'
    _order = 'is_bundled_component, line_role, sequence, id'

    ticket_id = fields.Many2one(
        'helpdesk.ticket',
        string='Ticket',
        required=True,
        ondelete='cascade',
        index=True,
    )
    dictamen_line_id = fields.Many2one(
        'stock.picking.return.e4.dictamen.line',
        string='Línea verificación E4',
        ondelete='cascade',
        index=True,
    )
    lot_id = fields.Many2one(
        'stock.lot',
        string='Serial',
        required=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        related='lot_id.product_id',
        store=True,
        readonly=True,
    )
    line_role = fields.Selection(
        [
            ('principal', 'Principal'),
            ('associated', 'Asociado'),
            ('standalone', 'Serial'),
            ('bundled', 'Componente'),
        ],
        string='Rol',
        required=True,
        readonly=True,
    )
    line_role_label = fields.Char(
        string='Rol',
        compute='_compute_line_role_label',
    )
    principal_lot_id = fields.Many2one(
        'stock.lot',
        string='Serial padre',
        readonly=True,
    )
    destination = fields.Selection(
        RETURN_E4_DESTINATION_SELECTION,
        string='Destino',
    )
    verification_state = fields.Selection(
        RETURN_E4_ITEM_VERIFICATION_STATE,
        string='Estado',
        help='Estado de verificación que el técnico define por equipo.',
    )
    equipment_estado = fields.Selection(
        RETURN_E4_ITEM_EQUIPMENT_ESTADO,
        string='Estado',
        compute='_compute_equipment_estado',
        inverse='_inverse_equipment_estado',
    )
    line_note = fields.Char(string='Nota')
    is_bundled_component = fields.Boolean(
        string='Componente empaquetado',
        default=False,
        readonly=True,
    )
    dictamen_state = fields.Selection(
        related='dictamen_line_id.state',
        string='Estado E4',
        readonly=True,
    )
    state_label = fields.Char(
        string='Estado',
        compute='_compute_state_label',
    )
    sequence = fields.Integer(default=10)
    report_include = fields.Boolean(
        string='Incluir en informe',
        default=True,
        help='Marque los equipos que desea incluir en el informe de revisión E4.',
    )
    report_review_note = fields.Text(
        string='Notas de revisión',
        help='Observaciones del técnico sobre este equipo para el informe E4.',
    )
    report_informe_html = fields.Html(
        string='Informe',
        sanitize=False,
        help='Informe de revisión redactado por el técnico (editor enriquecido).',
    )
    has_report_informe = fields.Boolean(
        string='Tiene informe',
        compute='_compute_has_report_informe',
    )
    show_informe_button = fields.Boolean(
        string='Mostrar botón informe',
        compute='_compute_show_informe_button',
    )

    def _return_e4_informe_anchor_item(self):
        """Ítem que almacena el informe (principal para su grupo de componentes)."""
        self.ensure_one()
        if self.is_bundled_component and self.principal_lot_id:
            principal = self.ticket_id.invdash_return_e4_item_ids.filtered(
                lambda i: i.line_role == 'principal'
                and i.lot_id == self.principal_lot_id,
            )[:1]
            return principal or self
        return self

    def _return_e4_informe_bundled_items(self):
        """Componentes empaquetados del principal en el mismo ticket."""
        self.ensure_one()
        if self.line_role != 'principal' or not self.lot_id:
            return self.env['helpdesk.ticket.return.e4.item']
        return self.ticket_id.invdash_return_e4_item_ids.filtered(
            lambda i: i.is_bundled_component
            and i.principal_lot_id == self.lot_id,
        ).sorted(key=lambda i: (i.sequence, i.id))

    @api.depends('verification_state', 'dictamen_state')
    def _compute_equipment_estado(self):
        for item in self:
            if item.dictamen_state == 'transferred':
                item.equipment_estado = 'transferred'
            else:
                item.equipment_estado = item.verification_state or False

    def _inverse_equipment_estado(self):
        for item in self:
            if item.dictamen_state == 'transferred' or item.is_bundled_component:
                continue
            value = item.equipment_estado
            if value == 'transferred':
                continue
            item.verification_state = value or False

    @api.depends('line_role')
    def _compute_line_role_label(self):
        for item in self:
            item.line_role_label = RETURN_E4_LINE_ROLE_LABELS.get(
                item.line_role, item.line_role or '',
            )

    @api.depends('is_bundled_component')
    def _compute_show_informe_button(self):
        for item in self:
            item.show_informe_button = not item.is_bundled_component

    @api.depends(
        'report_informe_html',
        'is_bundled_component',
        'principal_lot_id',
        'ticket_id.invdash_return_e4_item_ids.report_informe_html',
        'ticket_id.invdash_return_e4_item_ids.line_role',
        'ticket_id.invdash_return_e4_item_ids.principal_lot_id',
    )
    def _compute_has_report_informe(self):
        for item in self:
            anchor = item._return_e4_informe_anchor_item()
            content = anchor.report_informe_html or ''
            if hasattr(content, 'strip'):
                item.has_report_informe = bool(content.strip())
            else:
                item.has_report_informe = bool(content)

    def action_open_informe_wizard(self):
        self.ensure_one()
        anchor = self._return_e4_informe_anchor_item()
        anchor._return_e4_ensure_default_informe_html()
        serial = anchor.lot_id.name or anchor.product_id.display_name or anchor.display_name
        bundled = anchor._return_e4_informe_bundled_items()
        if anchor.line_role == 'principal' and bundled:
            title = _('Informe — %s (+ componentes)') % serial
        else:
            title = _('Informe — %s') % serial
        return {
            'type': 'ir.actions.act_window',
            'name': title,
            'res_model': 'helpdesk.ticket.return.e4.item.informe.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_item_id': anchor.id,
            },
        }

    def _return_e4_build_default_informe_html(self):
        """Ficha técnica del equipo (principal + componentes si aplica)."""
        self.ensure_one()
        anchor = self._return_e4_informe_anchor_item()
        if not anchor.lot_id:
            return Markup('')
        Ticket = self.env['helpdesk.ticket']
        parts = []
        if anchor.line_role == 'principal':
            parts.extend(Ticket._return_e4_lot_detail_sections(
                anchor.lot_id, role='principal',
            ))
            bundled = anchor._return_e4_informe_bundled_items()
            if bundled:
                parts.extend(Ticket._return_e4_lot_detail_sections(
                    bundled.mapped('lot_id'), role='bundled',
                ))
        else:
            role = anchor.line_role if anchor.line_role != 'standalone' else 'principal'
            parts.extend(Ticket._return_e4_lot_detail_sections(
                anchor.lot_id, role=role,
            ))
        return Markup('').join(parts) if parts else Markup('')

    def _return_e4_ensure_default_informe_html(self):
        """Precarga la ficha en el ítem ancla si el informe aún está vacío."""
        anchors = self.env['helpdesk.ticket.return.e4.item']
        for item in self:
            anchors |= item._return_e4_informe_anchor_item()
        for anchor in anchors:
            if anchor.report_informe_html:
                continue
            default_html = anchor._return_e4_build_default_informe_html()
            if default_html:
                anchor.report_informe_html = default_html

    def _return_e4_informe_detail_title(self):
        self.ensure_one()
        anchor = self._return_e4_informe_anchor_item()
        serial = anchor.lot_id.name or anchor.lot_id.display_name or ''
        if anchor.line_role == 'principal' and anchor._return_e4_informe_bundled_items():
            return _('Principal + componentes — %s') % serial
        role = RETURN_E4_LINE_ROLE_LABELS.get(anchor.line_role, anchor.line_role or '')
        return '%s — %s' % (role, serial)

    def _report_informe_plaintext(self):
        """Texto plano del informe para PDF."""
        self.ensure_one()
        if self.is_bundled_component:
            return _('Incluido en informe del principal')
        anchor = self._return_e4_informe_anchor_item()
        if anchor.report_informe_html:
            from odoo.tools import html2plaintext
            return html2plaintext(anchor.report_informe_html).strip()
        return (self.report_review_note or '').strip()

    @api.depends('verification_state', 'dictamen_state')
    def _compute_state_label(self):
        labels = dict(RETURN_E4_ITEM_EQUIPMENT_ESTADO)
        for item in self:
            if item.dictamen_state == 'transferred':
                item.state_label = labels['transferred']
            elif item.verification_state:
                item.state_label = labels.get(
                    item.verification_state, item.verification_state,
                )
            else:
                item.state_label = ''

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('invdash_skip_dictamen_sync') and (
            'destination' in vals or 'verification_state' in vals
        ):
            self._invdash_sync_dictamen_from_item()
            if 'destination' in vals:
                self._invdash_sync_bundled_items_from_principal()
        return res

    def _invdash_sync_bundled_items_from_principal(self):
        """Componentes empaquetados heredan el destino del principal en el mismo ticket."""
        for item in self.filtered(lambda i: i.line_role == 'principal' and i.destination):
            bundled = item.ticket_id.invdash_return_e4_item_ids.filtered(
                lambda i: i.is_bundled_component
                and i.principal_lot_id == item.lot_id
            )
            if bundled:
                bundled.with_context(invdash_skip_dictamen_sync=True).write({
                    'destination': item.destination,
                })

    def _invdash_sync_dictamen_from_item(self):
        for item in self.filtered('dictamen_line_id'):
            if item.dictamen_line_id.state == 'transferred':
                continue
            dl_vals = {
                'destination': item.destination or False,
            }
            if item.verification_state:
                dl_vals['state'] = item.verification_state
            dictamen = item.dictamen_line_id.with_context(invdash_skip_ticket_sync=True)
            dictamen.write(dl_vals)
            if 'destination' in dl_vals:
                dictamen._set_state_from_values()
