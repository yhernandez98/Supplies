# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MesaRetiroInactivateEquipmentPromptWizard(models.TransientModel):
    _name = 'mesa.retiro.inactivate.equipment.prompt.wizard'
    _description = '¿Devolución de equipos? (inactivar usuario)'

    retiro_wizard_id = fields.Many2one(
        'mesa.service.retiro.usuario.equipo.wizard',
        string='Wizard retiro',
        required=True,
        ondelete='cascade',
    )
    partner_id = fields.Many2one(
        'res.partner',
        related='retiro_wizard_id.partner_id',
        readonly=True,
    )
    contact_id = fields.Many2one(
        'res.partner',
        related='retiro_wizard_id.contact_id',
        readonly=True,
    )
    equipment_count = fields.Integer(
        string='Equipos asignados',
        compute='_compute_equipment_count',
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        parent_id = (
            self.env.context.get('default_retiro_wizard_id')
            or self.env.context.get('active_id')
        )
        if parent_id and 'retiro_wizard_id' in fields_list:
            res['retiro_wizard_id'] = parent_id
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('retiro_wizard_id'):
                parent_id = (
                    self.env.context.get('default_retiro_wizard_id')
                    or self.env.context.get('active_id')
                )
                if parent_id:
                    vals['retiro_wizard_id'] = parent_id
        return super().create(vals_list)

    def _parent_retiro_wizard(self):
        self.ensure_one()
        parent = self.retiro_wizard_id
        if not parent:
            parent_id = (
                self.env.context.get('default_retiro_wizard_id')
                or self.env.context.get('active_id')
            )
            if parent_id:
                parent = self.env['mesa.service.retiro.usuario.equipo.wizard'].browse(
                    parent_id
                ).exists()
        return parent

    @api.depends(
        'retiro_wizard_id',
        'retiro_wizard_id.partner_id',
        'retiro_wizard_id.contact_id',
    )
    def _compute_equipment_count(self):
        for wiz in self:
            parent = wiz._parent_retiro_wizard()
            if not parent:
                wiz.equipment_count = 0
                continue
            wiz.equipment_count = len(parent._lots_for_user_return_candidates())

    def action_yes_return_equipment(self):
        """Abre la selección de equipos a devolver."""
        self.ensure_one()
        parent = self._parent_retiro_wizard()
        if not parent:
            raise UserError(_('No se encontró el asistente de retiro.'))
        return parent._action_open_user_equipment_select_wizard(
            inactivate_flow=True,
        )

    def action_no_return_equipment(self):
        """Sin devolución de equipos; continuar con licencias del usuario."""
        self.ensure_one()
        parent = self._parent_retiro_wizard()
        if not parent:
            raise UserError(_('No se encontró el asistente de retiro.'))
        return parent._action_inactivate_user_license_prompt()
