# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class LicenseAssignmentPickWizard(models.TransientModel):
    _name = 'license.assignment.pick.wizard'
    _description = 'Pick license assignment for equipment/user'

    lot_id = fields.Many2one('stock.lot', required=True, readonly=True)
    license_tab_type = fields.Selection(
        [('equipment', 'Por Equipo'), ('user', 'Por Usuario')],
        required=True,
        readonly=True,
    )

    related_partner_id = fields.Many2one(
        'res.partner',
        readonly=True,
        compute='_compute_related_partner_id',
    )

    available_assignment_ids = fields.Many2many(
        'license.assignment',
        compute='_compute_available_assignment_ids',
        store=False,
        help='Asignaciones disponibles según la ubicación/cliente del equipo.',
    )

    assignment_id = fields.Many2one(
        'license.assignment',
        string='Asignación',
        required=True,
        domain="[('id', 'in', available_assignment_ids)]",
        help='Elige la asignación de licencia.',
    )

    @api.depends('lot_id')
    def _compute_related_partner_id(self):
        for rec in self:
            lot = rec.lot_id
            rec.related_partner_id = getattr(lot, 'related_partner_id', False) if lot else False

    @api.depends('lot_id', 'license_tab_type')
    def _compute_available_assignment_ids(self):
        for rec in self:
            rec.available_assignment_ids = [(5, 0, 0)]
            if not rec.lot_id or not rec.license_tab_type:
                continue

            location_partner_id, lot_location_id = rec.lot_id._get_license_scope_data()

            # Regla segura: si no se puede resolver ni cliente ni ubicación, no exponer resultados.
            if not (location_partner_id or lot_location_id):
                continue

            domain = [('state', '=', 'active')]
            if rec.license_tab_type == 'equipment':
                domain.append(('license_applies_to_equipment', '=', True))
                domain.append(('license_applies_to_user', '=', False))
            else:
                domain.append(('license_applies_to_user', '=', True))

            if location_partner_id:
                domain.append(('partner_id', '=', location_partner_id))
            if lot_location_id:
                domain.append(('location_id', '=', lot_location_id))

            assignments = self.env['license.assignment'].search(domain)
            LicenseEquipment = self.env['license.equipment']

            lot_user = getattr(rec.lot_id, 'related_partner_id', False) if rec.lot_id else False
            if rec.license_tab_type == 'user' and lot_user:
                # Solo contratos que este usuario aún no tiene cubiertos con una línea asignada
                # (evita error por duplicado y deja claro «qué falta» en el desplegable).
                taken_aids = LicenseEquipment.search([
                    ('contact_id', '=', lot_user.id),
                    ('state', '=', 'assigned'),
                ]).mapped('assignment_id').ids
                assignments = assignments.filtered(lambda a: a.id not in taken_aids)
            elif rec.license_tab_type == 'equipment' and rec.lot_id:
                taken_aids = LicenseEquipment.search([
                    ('lot_id', '=', rec.lot_id.id),
                    ('state', '=', 'assigned'),
                ]).mapped('assignment_id').ids
                assignments = assignments.filtered(lambda a: a.id not in taken_aids)

            rec.available_assignment_ids = assignments

    def action_confirm(self):
        self.ensure_one()

        if not self.assignment_id:
            raise UserError(_('Debes seleccionar una asignación.'))

        assignment = self.assignment_id
        today = fields.Date.context_today(self)
        start = assignment.start_date
        assignment_date = max(start, today) if start else today

        LicenseEquipment = self.env['license.equipment']

        if self.license_tab_type == 'equipment':
            existing = LicenseEquipment.search([
                ('assignment_id', '=', assignment.id),
                ('lot_id', '=', self.lot_id.id),
                ('state', '=', 'assigned'),
            ], limit=1)
            if existing:
                raise UserError(_('Esta asignación ya está creada para est