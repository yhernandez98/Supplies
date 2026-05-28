# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MesaServiceRetiroLicenseSelectWizard(models.TransientModel):
    _name = 'mesa.service.retiro.license.select.wizard'
    _description = 'Selección de licencias a retirar (equipo o usuario)'

    retiro_wizard_id = fields.Many2one(
        'mesa.service.retiro.usuario.equipo.wizard',
        string='Wizard retiro',
        required=True,
        ondelete='cascade',
    )
    for_user_tab = fields.Boolean(
        string='Modo licencias del usuario',
        default=False,
        help='True: pestaña Licencias del Usuario; False: licencias del equipo.',
    )
    lot_id = fields.Many2one(
        'stock.lot',
        string='Equipo',
        readonly=True,
    )
    return_lot_id = fields.Many2one(
        'stock.lot',
        string='Equipo (devolución usuario)',
        readonly=True,
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
    candidate_license_ids = fields.Many2many(
        'license.equipment',
        'mesa_retiro_lic_sel_cand_rel',
        'wizard_id',
        'license_equipment_id',
        string='Licencias disponibles',
    )
    license_equipment_ids = fields.Many2many(
        'license.equipment',
        'mesa_retiro_lic_sel_sel_rel',
        'wizard_id',
        'license_equipment_id',
        string='Licencias a retirar',
        domain="[('id', 'in', candidate_license_ids)]",
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

    def _is_user_tab_mode(self):
        self.ensure_one()
        return bool(
            self.for_user_tab
            or self.env.context.get('mesa_retiro_user_tab_licenses')
        )

    def _candidate_lines_for_wizard(self):
        self.ensure_one()
        parent = self.retiro_wizard_id
        if not parent:
            return self.env['license.equipment'].browse()
        if self._is_user_tab_mode():
            return parent._get_user_license_lines_for_removal()
        lot = self.return_lot_id or (
            parent.user_return_current_lot_id if parent.search_mode == 'user' else parent.lot_id
        )
        if parent.search_mode == 'user' and lot:
            return parent._get_equipment_license_lines_for_removal(lot=lot)
        if parent.search_mode == 'inventory':
            return parent._get_equipment_license_lines_for_removal()
        return self.env['license.equipment'].browse()

    def _refresh_candidate_licenses(self):
        for wiz in self:
            lines = wiz._candidate_lines_for_wizard()
            wiz.candidate_license_ids = [(6, 0, lines.ids)]
            keep = wiz.license_equipment_ids.filtered(lambda l: l.id in lines.ids)
            if keep.ids != wiz.license_equipment_ids.ids:
                wiz.license_equipment_ids = [(6, 0, keep.ids)]

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        parent_id = self.env.context.get('default_retiro_wizard_id')
        if not parent_id:
            return res
        parent = self.env['mesa.service.retiro.usuario.equipo.wizard'].browse(parent_id).exists()
        if not parent:
            return res
        user_tab = bool(
            self.env.context.get('mesa_retiro_user_tab_licenses')
            or self.env.context.get('default_for_user_tab')
        )
        if 'for_user_tab' in fields_list:
            res['for_user_tab'] = user_tab
        if user_tab:
            lines = parent._get_user_license_lines_for_removal()
        else:
            return_lot_id = self.env.context.get('default_return_lot_id')
            lot = self.env['stock.lot'].browse(return_lot_id).exists() if return_lot_id else parent.lot_id
            if parent.search_mode == 'user' and return_lot_id:
                lot = self.env['stock.lot'].browse(return_lot_id)
            lines = (
                parent._get_equipment_license_lines_for_removal(lot=lot)
                if lot else parent._get_equipment_license_lines_for_removal()
            )
        if 'candidate_license_ids' in fields_list:
            res['candidate_license_ids'] = [(6, 0, lines.ids)]
        if 'license_equipment_ids' in fields_list:
            res['license_equipment_ids'] = [(6, 0, [])]
        if not user_tab:
            return_lot_id = self.env.context.get('default_return_lot_id')
            lot = parent.lot_id
            if return_lot_id:
                lot = self.env['stock.lot'].browse(return_lot_id)
            elif parent.user_return_current_lot_id:
                lot = parent.user_return_current_lot_id
            if 'return_lot_id' in fields_list and lot:
                res['return_lot_id'] = lot.id
            if 'lot_id' in fields_list and lot:
                res['lot_id'] = lot.id
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for wiz in records:
            if wiz.retiro_wizard_id and not wiz.candidate_license_ids:
                wiz._refresh_candidate_licenses()
        return records

    def _parent_inactivate_flow(self):
        parent = self.retiro_wizard_id
        return bool(
            parent
            and (
                parent.inactivate_flow_active
                or self.env.context.get('mesa_retiro_inactivate_flow')
            )
        )

    def action_skip_user_licenses(self):
        """Flujo inactivar: continuar sin retirar licencias del usuario."""
        self.ensure_one()
        parent = self.retiro_wizard_id
        if not parent or not self._is_user_tab_mode() or not self._parent_inactivate_flow():
            raise UserError(_('Esta acción solo aplica al inactivar usuario.'))
        parent.user_tab_license_line_ids = [(5, 0, 0)]
        return parent._finalize_inactivate_user()

    def action_confirm(self):
        self.ensure_one()
        parent = self.retiro_wizard_id
        if not parent:
            raise UserError(_('No se encontró el asistente de retiro.'))
        if not self.license_equipment_ids:
            if self._is_user_tab_mode() and self._parent_inactivate_flow():
                return parent._finalize_inactivate_user()
            if self._is_user_tab_mode():
                raise UserError(_('Seleccione al menos una licencia del usuario.'))
            raise UserError(_('Seleccione al menos una licencia del equipo.'))

        if self._is_user_tab_mode():
            parent.user_tab_license_line_ids = [(6, 0, self.license_equipment_ids.ids)]
            if parent.inactivate_flow_active:
                return parent._finalize_inactivate_user()
            if parent.unlink_user_from_equipment and parent.user_return_lot_ids:
                return parent._action_user_return_license_chain()
            return parent._finalize_register_followup_user()

        if parent.search_mode == 'user':
            lot = self.return_lot_id or parent.user_return_current_lot_id
            parent.user_return_license_line_ids = [
                (4, lid) for lid in self.license_equipment_ids.ids
            ]
            if lot:
                parent.user_return_license_prompt_done_lot_ids = [(4, lot.id)]
            parent.user_return_current_lot_id = False
            if parent.client_requests_license_removal and not parent.user_tab_license_line_ids:
                return parent._action_open_user_license_select_wizard()
            return parent._action_user_return_license_chain()

        lot = self.return_lot_id or parent.lot_id or parent.user_return_current_lot_id
        parent.user_return_license_line_ids = [
            (4, lid) for lid in self.license_equipment_ids.ids
        ]
        if lot:
            parent.user_return_license_prompt_done_lot_ids = [(4, lot.id)]
        parent.user_return_current_lot_id = False
        if parent.user_return_lot_ids:
            return parent._action_user_return_license_chain()
        return parent._finalize_register_followup_inventory(
            license_lines_to_cancel=self.license_equipment_ids,
        )
