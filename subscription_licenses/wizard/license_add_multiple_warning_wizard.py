# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class LicenseAddMultipleWarningWizard(models.TransientModel):
    _name = 'license.add.multiple.warning.wizard'
    _description = 'Advertencia al añadir equipos o contactos (contrato anual)'

    assignment_id = fields.Many2one(
        'license.assignment',
        string='Asignación',
        required=True,
        ondelete='cascade',
        readonly=True,
    )
    add_type = fields.Selection([
        ('equipment', 'Equipos'),
        ('contact', 'Contactos (Usuarios)'),
    ], string='Añadir', required=True, readonly=True)
    warning_message = fields.Html(
        string='Mensaje',
        compute='_compute_warning_message',
        readonly=True,
    )

    @api.depends('assignment_id', 'add_type')
    def _compute_warning_message(self):
        for rec in self:
            add_label = _('equipos') if rec.add_type == 'equipment' else _('contactos/usuarios')
            rec.warning_message = _(
                '<div style="padding: 12px; background-color: #fff3cd; border: 2px solid #ff9800; border-radius: 6px; margin-bottom: 12px;">'
                '<p style="margin: 0 0 10px 0; font-size: 15px;"><strong>⚠️ ADVERTENCIA IMPORTANTE</strong></p>'
                '<p style="margin: 0 0 8px 0;">Está a punto de <strong>agregar %s</strong> a esta asignación.</p>'
                '<div style="background-color: #ffebee; padding: 12px; border-radius: 4px; border-left: 4px solid #f44336; margin-top: 10px;">'
                '<p style="margin: 0 0 6px 0; color: #c62828;"><strong>🚫 Una vez que los asigne, NO PODRÁ QUITARLOS durante los 12 meses del contrato.</strong></p>'
                '<p style="margin: 0; color: #b71c1c;">Solo podrá agregar más %s durante el período. No podrá eliminar ni desasignar los que agregue ahora.</p>'
                '</div>'
                '<p style="margin-top: 12px; margin-bottom: 0;"><strong>¿Desea continuar?</strong></p>'
                '</div>'
            ) % (add_label, add_label)

    def action_accept(self):
        """Acepta la advertencia y abre el wizard normal de añadir varios."""
        self.ensure_one()
        name = _('Añadir varios equipos') if self.add_type == 'equipment' else _('Añadir varios contactos')
        return {
            'name': name,
            'type': 'ir.actions.act_window',
            'res_model': 'license.equipment.add.multiple.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_assignment_id': self.assignment_id.id,
                'default_add_type': self.add_type,
            },
        }
