# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HelpdeskTicketReturnE4ItemInformeWizard(models.TransientModel):
    _name = 'helpdesk.ticket.return.e4.item.informe.wizard'
    _description = 'Editor informe E4 por equipo'

    item_id = fields.Many2one(
        'helpdesk.ticket.return.e4.item',
        string='Equipo',
        required=True,
        ondelete='cascade',
    )
    ticket_id = fields.Many2one(
        related='item_id.ticket_id',
        readonly=True,
    )
    lot_id = fields.Many2one(
        related='item_id.lot_id',
        readonly=True,
    )
    product_id = fields.Many2one(
        related='item_id.product_id',
        readonly=True,
    )
    line_role_label = fields.Char(
        related='item_id.line_role_label',
        readonly=True,
    )
    informe_group_summary = fields.Char(
        string='Equipos incluidos',
        compute='_compute_informe_group_summary',
    )
    informe_is_principal_group = fields.Boolean(
        compute='_compute_informe_group_summary',
    )
    informe_html = fields.Html(
        string='Informe',
        sanitize=False,
    )
    informe_readonly = fields.Boolean(
        compute='_compute_informe_readonly',
    )

    @api.depends('item_id', 'item_id.line_role', 'item_id.lot_id')
    def _compute_informe_group_summary(self):
        for wiz in self:
            item = wiz.item_id
            bundled = item._return_e4_informe_bundled_items()
            if item.line_role == 'principal' and bundled:
                labels = [
                    (b.product_id.display_name or b.lot_id.display_name or '')
                    for b in bundled
                ]
                wiz.informe_is_principal_group = True
                wiz.informe_group_summary = ', '.join(filter(None, labels))
            else:
                wiz.informe_is_principal_group = False
                wiz.informe_group_summary = False

    @api.depends('item_id', 'item_id.ticket_id.invdash_return_e4_report_state')
    def _compute_informe_readonly(self):
        for wiz in self:
            ticket = wiz.item_id.ticket_id
            wiz.informe_readonly = (
                ticket.invdash_return_e4_report_state == 'done'
                if ticket
                else False
            )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        item = self.env['helpdesk.ticket.return.e4.item'].browse(
            self.env.context.get('default_item_id'),
        ).exists()
        if item and 'informe_html' in fields_list and not res.get('informe_html'):
            anchor = item._return_e4_informe_anchor_item()
            anchor._return_e4_ensure_default_informe_html()
            res['informe_html'] = anchor.report_informe_html or False
        return res

    def action_save_informe(self):
        self.ensure_one()
        if self.informe_readonly:
            raise UserError(_('El informe del ticket ya está finalizado y no se puede editar.'))
        anchor = self.item_id._return_e4_informe_anchor_item()
        anchor.write({'report_informe_html': self.informe_html or False})
        bundled = anchor._return_e4_informe_bundled_items()
        if bundled:
            bundled.with_context(invdash_skip_dictamen_sync=True).write({
                'report_informe_html': False,
            })
        ticket = anchor.ticket_id
        if ticket and ticket.invdash_return_e4_report_state == 'none':
            ticket.write({'invdash_return_e4_report_state': 'draft'})
        return {'type': 'ir.actions.act_window_close'}
