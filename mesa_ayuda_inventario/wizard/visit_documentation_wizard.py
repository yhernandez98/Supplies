# -*- coding: utf-8 -*-

import base64
import re

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import html2plaintext
from odoo.tools import mail as mail_tools


class MesaAyudaVisitDocumentationWizard(models.TransientModel):
    _name = 'mesa.ayuda.visit.documentation.wizard'
    _description = 'Informe de visita (documentación para ticket)'

    maintenance_order_id = fields.Many2one(
        'maintenance.order',
        string='Visita',
        required=True,
        readonly=True,
    )
    ticket_id = fields.Many2one(
        'helpdesk.ticket',
        string='Ticket',
        related='maintenance_order_id.ticket_id',
        readonly=True,
    )
    partner_id = fields.Many2one(
        related='maintenance_order_id.partner_id',
        readonly=True,
    )
    body_html = fields.Html(
        string='Informe de lo realizado',
        sanitize=False,
        help='Describe lo ejecutado en terreno. Al guardar se adjunta al ticket y queda guardado en la visita para reabrirlo.',
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        oid = self.env.context.get('default_maintenance_order_id') or self.env.context.get('active_id')
        if oid and 'maintenance_order_id' in fields_list:
            res['maintenance_order_id'] = oid
        if oid and 'body_html' in fields_list:
            order = self.env['maintenance.order'].browse(oid).exists()
            if order and order.visit_documentation_html:
                res['body_html'] = order.visit_documentation_html
        return res

    def action_save_and_close(self):
        self.ensure_one()
        order = self.maintenance_order_id
        ticket = order.ticket_id
        if not ticket:
            raise UserError(_('Esta visita no tiene ticket asociado. No se puede adjuntar el informe.'))
        body = (self.body_html or '').strip()
        if mail_tools.is_html_empty(self.body_html):
            raise UserError(_('Escribe el informe antes de guardar.'))

        # Primero la orden (fuente única); el ticket muestra lo mismo vía visit_acta_html relacionado
        order.write({'visit_documentation_html': body})

        title = _('Informe de visita %s') % (order.name or order.id)
        html_doc = (
            '<!DOCTYPE html><html><head><meta charset="utf-8"/><title>%s</title></head><body>%s</body></html>'
            % (title, body)
        )
        fname = re.sub(r'[^\w\-]+', '_', 'Informe_visita_%s' % (order.name or str(order.id))) + '.html'
        att = self.env['ir.attachment'].sudo().create({
            'name': fname,
            'type': 'binary',
            'mimetype': 'text/html',
            'datas': base64.b64encode(html_doc.encode('utf-8')),
            'res_model': 'helpdesk.ticket',
            'res_id': ticket.id,
            'description': _('Documentación de visita generada desde la lista de visitas asignadas.'),
        })
        snippet = (html2plaintext(body) or '').strip()[:800]

        # 1) Chatter + adjunto (historial)
        ticket.sudo().message_post(
            body=_(
                '<p><b>Informe de visita</b> (%s)</p><p>%s</p>'
            ) % (order.name or '', snippet or _('(ver adjunto HTML)')),
            attachment_ids=[att.id],
        )

        # 2) Pestaña «Descripción» del ticket: el usuario suele mirar ahí, no solo el chatter
        desc_field = ticket._fields.get('description')
        if desc_field:
            header = _('<p><strong>Informe de visita %s</strong> — %s</p>') % (
                order.name or '',
                fields.Datetime.context_timestamp(self, fields.Datetime.now()).strftime('%Y-%m-%d %H:%M'),
            )
            prev = ticket.description or ''
            if desc_field.type == 'html':
                block = '<hr/>%s%s' % (header, body)
                ticket.sudo().write({'description': prev + block})
            else:
                block = '\n\n%s\n%s' % (html2plaintext(header), html2plaintext(body))
                ticket.sudo().write({'description': (prev + block) if prev else block.lstrip()})

        return {'type': 'ir.actions.act_window_close'}
