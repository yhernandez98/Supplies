# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MesaServiceRetiroUserLicensePromptWizard(models.TransientModel):
    _name = 'mesa.service.retiro.user.license.prompt.wizard'
    _description = '¿Retirar licencias del equipo? (retiro por usuario)'

    retiro_wizard_id = fields.Many2one(
        'mesa.service.retiro.usuario.equipo.wizard',
        string='Wizard retiro',
        required=True,
        ondelete='cascade',
    )
    lot_id = fields.Many2one(
        'stock.lot',
        string='Equipo',
        required=True,
        readonly=True,
    )
    equipment_label = fields.Char(
        string='Equipo',
        compute='_compute_equipment_label',
    )
    license_count = fields.Integer(
        string='Licencias del equipo',
        compute='_compute_license_count',
    )

    @api.depends('lot_id')
    def _compute_equipment_label(self):
        for wiz in self:
            lot = wiz.lot_id
            if not lot:
                wiz.equipment_label = ''
                continue
            plate = lot.inventory_plate or ''
            serial = lot.name or ''
            wiz.equipment_label = '%s — %s' % (plate, serial) if plate else serial

    @api.depends('lot_id', 'retiro_wizard_id')
    def _compute_license_count(self):
        for wiz in self:
            parent = wiz.retiro_wizard_id
            if not parent or not wiz.lot_id:
                wiz.license_count = 0
                continue
            lines = parent._collect_equipment_tab_license_lines(
                parent.partner_id,
                wiz.lot_id.inventory_plate or '',
                wiz.lot_id,
            )
            wiz.license_count = len(lines)

    def _mark_lot_prompt_done(self):
        self.ensure_one()
        self.retiro_wizard_id.user_return_license_prompt_done_lot_ids = [
            (4, self.lot_id.id)
        ]

    def action_skip_licenses(self):
        """No retirar licencias de este equipo; continuar con el siguiente."""
        self.ensure_one()
        self._mark_lot_prompt_done()
        return self.retiro_wizard_id._action_user_return_license_chain()

    def action_remove_licenses(self):
        """Abre la selección de licencias del equipo (como por placa)."""
        self.ensure_one()
        parent = self.retiro_wizard_id
        if not parent:
            raise UserError(_('No se encontró el asistente de retiro.'))
        parent.user_return_current_lot_id = self.lot_id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Licencias del equipo a retirar'),
            'res_model': 'mesa.service.retiro.license.select.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_retiro_wizard_id': parent.id,
                'default_return_lot_id': self.lot_id.id,
                'mesa_retiro_user_license_for_lot': True,
            },
        }
