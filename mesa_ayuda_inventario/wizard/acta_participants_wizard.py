# -*- coding: utf-8 -*-

import json

from markupsafe import escape

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import mail as mail_tools

from .acta_html_blocks import mesa_acta_participant_partner_block_html


def _mesa_acta_participant_wizard_text(value):
    if value is None or value is False:
        return ''
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _mesa_partner_phone_for_acta(partner):
    """Teléfono(s) del contacto; algunas bases no tienen el campo ``mobile`` en ``res.partner``."""
    if not partner:
        return ''
    chunks = []
    if getattr(partner, 'phone', None):
        chunks.append(str(partner.phone).strip())
    for attr in ('mobile', 'mobile_phone'):
        v = getattr(partner, attr, None)
        if v:
            s = str(v).strip()
            if s and s not in chunks:
                chunks.append(s)
            break
    return ' / '.join(chunks) if chunks else ''


class MesaAyudaActaParticipantsWizard(models.TransientModel):
    _name = 'mesa.ayuda.acta.participants.wizard'
    _description = 'Elegir contactos del cliente para el acta de visita'

    ticket_id = fields.Many2one(
        'helpdesk.ticket',
        string='Ticket',
        required=True,
        readonly=True,
        ondelete='cascade',
    )
    filter_contact = fields.Char(
        string='Buscar',
        help='Filtra por nombre, correo o teléfono del contacto.',
    )
    candidate_contact_ids = fields.Many2many(
        'res.partner',
        'mesa_acta_part_wiz_cand_partner_rel',
        'wizard_id',
        'partner_id',
        string='Contactos disponibles',
    )
    selected_contact_ids = fields.Many2many(
        'res.partner',
        'mesa_acta_part_wiz_sel_partner_rel',
        'wizard_id',
        'partner_id',
        string='Contactos para el acta',
        domain="[('id', 'in', candidate_contact_ids)]",
    )
    has_acta_participant_lines = fields.Boolean(
        compute='_compute_has_acta_participant_lines',
    )

    @api.depends('selected_contact_ids')
    def _compute_has_acta_participant_lines(self):
        for wiz in self:
            wiz.has_acta_participant_lines = bool(wiz.selected_contact_ids)

    def _mesa_acta_all_candidate_contacts(self):
        self.ensure_one()
        if not self.ticket_id:
            return self.env['res.partner']
        return self.ticket_id._mesa_candidate_contacts_for_acta()

    def _mesa_acta_filtered_contacts(self):
        self.ensure_one()
        partners = self._mesa_acta_all_candidate_contacts()
        needle = (self.filter_contact or '').strip().lower()
        if not needle:
            return partners

        def match(p):
            parts = [
                p.display_name or '',
                p.name or '',
                p.email or '',
                p.phone or '',
                _mesa_partner_phone_for_acta(p),
            ]
            return needle in ' '.join(parts).lower()

        return partners.filtered(match)

    @api.onchange('filter_contact')
    def _onchange_filter_contact(self):
        if not self.ticket_id:
            return
        partners = self._mesa_acta_filtered_contacts()
        self.candidate_contact_ids = [(6, 0, partners.ids)]
        keep = self.selected_contact_ids.filtered(lambda p: p.id in partners.ids)
        if keep.ids != self.selected_contact_ids.ids:
            self.selected_contact_ids = [(6, 0, keep.ids)]

    def write(self, vals):
        res = super().write(vals)
        if 'filter_contact' in vals and any(self.mapped('ticket_id')):
            for wiz in self.filtered('ticket_id'):
                partners = wiz._mesa_acta_filtered_contacts()
                wiz.candidate_contact_ids = [(6, 0, partners.ids)]
                keep = wiz.selected_contact_ids.filtered(lambda p: p.id in partners.ids)
                if keep.ids != wiz.selected_contact_ids.ids:
                    wiz.selected_contact_ids = [(6, 0, keep.ids)]
        return res

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        tid = self.env.context.get('default_ticket_id')
        if not tid:
            return res
        ticket = self.env['helpdesk.ticket'].browse(tid).exists()
        if not ticket:
            return res
        partners = ticket._mesa_candidate_contacts_for_acta()
        if not partners:
            raise UserError(
                _(
                    'No hay contactos vinculados al cliente «%(cliente)s» en la ficha de contactos '
                    '(mismo comercial que el ticket). Revise que existan personas/contactos bajo esa empresa.'
                )
                % {'cliente': ticket.partner_id.commercial_partner_id.display_name or ticket.partner_id.display_name}
            )
        if 'ticket_id' in fields_list:
            res['ticket_id'] = ticket.id
        if 'candidate_contact_ids' in fields_list:
            res['candidate_contact_ids'] = [(6, 0, partners.ids)]
        if 'selected_contact_ids' in fields_list:
            res['selected_contact_ids'] = [(6, 0, [])]
        return res

    @api.model_create_multi
    def create(self, vals_list):
        ctx_tid = self.env.context.get('default_ticket_id')
        clean = []
        for vals in vals_list:
            v = dict(vals or {})
            if ctx_tid and not v.get('ticket_id'):
                v['ticket_id'] = ctx_tid
            clean.append(v)
        records = super().create(clean)
        for wiz in records:
            if wiz.ticket_id and not wiz.candidate_contact_ids:
                partners = wiz.ticket_id._mesa_candidate_contacts_for_acta()
                if partners:
                    wiz.candidate_contact_ids = partners
        return records

    def action_confirm_insert(self):
        self.ensure_one()
        order = self.ticket_id.maintenance_order_id
        if not order:
            raise UserError(_('El ticket no tiene orden de visita vinculada.'))
        partners = self.selected_contact_ids.filtered(lambda p: p.id in self.candidate_contact_ids.ids)
        allowed = self.ticket_id._mesa_candidate_contacts_for_acta()
        partners = partners.filtered(lambda p: p.id in allowed.ids)
        if not partners:
            raise UserError(_('Marque al menos un contacto del cliente para insertar en el acta.'))
        th_name = _('Nombre')
        th_email = _('Correo')
        th_phone = _('Teléfono')
        th_realizado = _('Realizado')
        blocks = []
        for partner in partners.sorted(lambda p: ((p.display_name or ''), (p.email or ''))):
            pid = partner.id
            name = escape(_mesa_acta_participant_wizard_text(partner.display_name or partner.name) or '')
            email = escape(_mesa_acta_participant_wizard_text(partner.email) or '')
            phone = escape(_mesa_acta_participant_wizard_text(_mesa_partner_phone_for_acta(partner)) or '')
            blocks.append(
                mesa_acta_participant_partner_block_html(
                    pid, th_name, th_email, th_phone, name, email, phone, th_realizado,
                )
            )
        blocks.append('<p></p>')
        table = ''.join(blocks)
        # ``visit_documentation_html`` puede ser ``markupsafe.Markup``; ``Markup + str`` escapa el fragmento nuevo.
        cur = str(order.visit_documentation_html or '')
        if mail_tools.is_html_empty(order.visit_documentation_html):
            order.write({'visit_documentation_html': table})
        else:
            order.write({'visit_documentation_html': cur + table})
        if partners:
            self.ticket_id.write({'mesa_acta_selected_contact_ids': [(4, pid) for pid in partners.ids]})
        return {'type': 'ir.actions.act_window_close'}
