# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MesaServiceRetiroUserEquipmentSelectWizard(models.TransientModel):
    _name = 'mesa.service.retiro.user.equipment.select.wizard'
    _description = 'Selección de equipos a devolver (retiro por usuario)'

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
    candidate_lot_ids = fields.Many2many(
        'stock.lot',
        'mesa_retiro_user_eq_cand_rel',
        'wizard_id',
        'lot_id',
        string='Equipos del usuario',
    )
    lot_ids = fields.Many2many(
        'stock.lot',
        'mesa_retiro_user_eq_sel_rel',
        'wizard_id',
        'lot_id',
        string='Equipos a devolver',
        domain="[('id', 'in', candidate_lot_ids)]",
    )
    inactivate_flow = fields.Boolean(
        compute='_compute_inactivate_flow',
    )

    @api.depends('retiro_wizard_id', 'retiro_wizard_id.inactivate_flow_active')
    def _compute_inactivate_flow(self):
        for wiz in self:
            wiz.inactivate_flow = bool(
                wiz.retiro_wizard_id and wiz.retiro_wizard_id.inactivate_flow_active
            )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        parent_id = self.env.context.get('default_retiro_wizard_id')
        if not parent_id:
            return res
        parent = self.env['mesa.service.retiro.usuario.equipo.wizard'].browse(parent_id).exists()
        if not parent:
            return res
        lots = parent._lots_for_user_return_candidates()
        if 'candidate_lot_ids' in fields_list:
            res['candidate_lot_ids'] = [(6, 0, lots.ids)]
        if 'lot_ids' in fields_list:
            res['lot_ids'] = [(6, 0, [])]
        return res

    def action_confirm(self):
        self.ensure_one()
        parent = self.retiro_wizard_id
        if not parent:
            raise UserError(_('No se encontró el asistente de retiro.'))
        if not self.lot_ids:
            raise UserError(_('Seleccione al menos un equipo a devolver.'))
        parent.write({
            'user_return_lot_ids': [(6, 0, self.lot_ids.ids)],
            'user_return_license_line_ids': [(5, 0, 0)],
            'user_return_license_prompt_done_lot_ids': [(5, 0, 0)],
            'user_return_current_lot_id': False,
            'user_tab_license_line_ids': [(5, 0, 0)],
        })
        return parent._action_user_return_license_chain()

    def action_skip_no_equipment(self):
        """Flujo inactivar: sin devolución de equipos."""
        self.ensure_one()
        parent = self.retiro_wizard_id
        if not parent or not (
            parent.inactivate_flow_active
            or self.env.context.get('mesa_retiro_inactivate_flow')
        ):
            raise UserError(_('Esta acción solo aplica al inactivar usuario.'))
        parent.write({
            'user_return_lot_ids': [(5, 0, 0)],
            'user_return_license_line_ids': [(5, 0, 0)],
            'user_return_license_prompt_done_lot_ids': [(5, 0, 0)],
            'user_return_current_lot_id': False,
        })
        return parent._action_inactivate_user_license_prompt()
