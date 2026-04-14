# -*- coding: utf-8 -*-
from markupsafe import escape

from odoo import api, fields, models, _


class LicenseAssignmentCancelWarningWizard(models.TransientModel):
    _name = 'license.assignment.cancel.warning.wizard'
    _description = 'Advertencia al cancelar una asignación de licencia'

    assignment_id = fields.Many2one(
        'license.assignment',
        string='Asignación',
        required=True,
        ondelete='cascade',
        readonly=True,
    )
    partner_name = fields.Char(
        string='Cliente',
        related='assignment_id.partner_id.name',
        readonly=True,
    )
    license_label = fields.Char(
        string='Licencia',
        compute='_compute_license_label',
        readonly=True,
    )
    warning_message = fields.Html(
        string='Mensaje',
        compute='_compute_warning_message',
        readonly=True,
    )

    @api.depends('assignment_id', 'assignment_id.license_display_name', 'assignment_id.selected_product_id')
    def _compute_license_label(self):
        for rec in self:
            a = rec.assignment_id
            if not a:
                rec.license_label = ''
                continue
            rec.license_label = (a.license_display_name or a.selected_product_id.display_name or '').strip()

    @api.depends(
        'assignment_id',
        'partner_name',
        'license_label',
        'assignment_id.quantity',
        'assignment_id.equipment_count',
        'assignment_id.user_count',
    )
    def _compute_warning_message(self):
        for rec in self:
            if not rec.assignment_id or not rec.assignment_id.exists():
                rec.warning_message = _(
                    '<div style="padding: 16px; background-color: #ffebee; border: 2px solid #f44336; border-radius: 6px;">'
                    '<p style="margin: 0; color: #c62828;"><strong>⚠️ Error:</strong> La asignación ya no existe o fue eliminada.</p>'
                    '</div>'
                )
                continue

            qty = rec.assignment_id.quantity or 0
            eq = rec.assignment_id.equipment_count or 0
            users = rec.assignment_id.user_count or 0
            partner = escape(rec.partner_name or _('el cliente'))
            lic = escape(rec.license_label or _('esta licencia'))

            rec.warning_message = _(
                '<div style="padding: 16px; background-color: #fff3cd; border: 2px solid #ff9800; border-radius: 6px; margin-bottom: 12px;">'
                '<p style="margin: 0 0 12px 0; font-size: 16px;"><strong>⚠️ ADVERTENCIA IMPORTANTE</strong></p>'
                '<p style="margin: 0 0 10px 0;">Está a punto de <strong>cancelar la asignación</strong> de <strong>{lic}</strong> para <strong>{partner}</strong>.</p>'
                '<div style="background-color: #ffebee; padding: 12px; border-radius: 4px; border-left: 4px solid #f44336; margin-top: 10px;">'
                '<p style="margin: 0 0 8px 0; color: #c62828;"><strong>📋 Consecuencias:</strong></p>'
                '<ul style="margin: 0; padding-left: 20px; color: #b71c1c;">'
                '<li style="margin-bottom: 6px;">La asignación dejará de estar <strong>activa</strong> y <strong>no contará</strong> como licencia vigente en la suscripción del cliente.</li>'
                '<li style="margin-bottom: 6px;">Se perderá el seguimiento operativo habitual sobre esta línea (cantidad configurada: <strong>{qty}</strong>; equipos: <strong>{eq}</strong>; usuarios: <strong>{users}</strong>).</li>'
                '<li style="margin-bottom: 0;">Los equipos y usuarios vinculados pueden quedar desalineados con el contrato: revise si debe liberar o reasignar licencias antes de continuar.</li>'
                '</ul>'
                '</div>'
                '<p style="margin-top: 12px; margin-bottom: 0;"><strong>¿Desea cancelar esta asignación?</strong></p>'
                '</div>'
            ).format(lic=lic, partner=partner, qty=qty, eq=eq, users=users)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        aid = self.env.context.get('default_assignment_id') or self.env.context.get('active_id')
        if aid:
            assignment = self.env['license.assignment'].browse(aid)
            if assignment.exists():
                res['assignment_id'] = assignment.id
        return res

    def action_confirm_cancel(self):
        """Confirma y cancela la asignación."""
        self.ensure_one()
        if not self.assignment_id or not self.assignment_id.exists():
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('La asignación ya no existe o fue eliminada.'),
                    'type': 'danger',
                    'sticky': True,
                },
            }
        self.assignment_id._apply_cancel_state()
        return {'type': 'ir.actions.act_window_close'}
