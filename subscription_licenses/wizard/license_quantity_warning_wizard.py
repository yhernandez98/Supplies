# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class LicenseQuantityWarningWizard(models.TransientModel):
    _name = 'license.quantity.warning.wizard'
    _description = 'Advertencia al modificar cantidad de licencias (contrato anual)'

    assignment_id = fields.Many2one(
        'license.assignment',
        string='Asignación',
        required=True,
        ondelete='cascade',
        readonly=True,
    )
    quantity_current = fields.Integer(
        string='Cantidad actual',
        readonly=True,
    )
    quantity_new = fields.Integer(
        string='Nueva cantidad',
        required=True,
        help='Cantidad de licencias que tendrá esta asignación.',
    )
    warning_message = fields.Html(
        string='Mensaje',
        compute='_compute_warning_message',
        readonly=True,
    )

    @api.depends('assignment_id')
    def _compute_warning_message(self):
        for rec in self:
            rec.warning_message = _(
                '<div style="padding: 12px; background-color: #fff3cd; border: 2px solid #ff9800; border-radius: 6px; margin-bottom: 12px;">'
                '<p style="margin: 0 0 10px 0; font-size: 15px;"><strong>⚠️ ADVERTENCIA - CONTRATO ANUAL</strong></p>'
                '<p style="margin: 0 0 8px 0;">Está a punto de <strong>modificar la cantidad de licencias</strong> de esta asignación.</p>'
                '<div style="background-color: #e3f2fd; padding: 12px; border-radius: 4px; border-left: 4px solid #2196f3; margin-top: 10px;">'
                '<p style="margin: 0 0 6px 0;"><strong>En contratos anuales:</strong></p>'
                '<ul style="margin: 0 0 0 16px; padding: 0;">'
                '<li>Puede <strong>aumentar</strong> la cantidad en cualquier momento.</li>'
                '<li><strong>No podrá reducir</strong> la cantidad durante el período del contrato.</li>'
                '</ul>'
                '</div>'
                '<p style="margin-top: 12px; margin-bottom: 0;"><strong>¿Confirma el cambio de cantidad?</strong></p>'
                '</div>'
            )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        assignment_id = self.env.context.get('default_assignment_id')
        if assignment_id:
            assignment = self.env['license.assignment'].browse(assignment_id)
            if assignment.exists():
                res.setdefault('quantity_current', assignment.quantity)
                res.setdefault('quantity_new', assignment.quantity)
        return res

    def action_confirm(self):
        self.ensure_one()
        if self.quantity_new <= 0:
            from odoo.exceptions import ValidationError
            raise ValidationError(_('La cantidad debe ser mayor a cero.'))
        assignment = self.assignment_id
        if self.quantity_new < assignment.quantity and assignment.contracting_type in ('annual_monthly_commitment', 'annual') and assignment.state == 'active':
            from odoo.exceptions import ValidationError
            raise ValidationError(
                _('No se puede reducir la cantidad de licencias en un contrato anual activo.')
            )
        assignment.write({'quantity': self.quantity_new})
        return {'type': 'ir.actions.act_window_close'}
