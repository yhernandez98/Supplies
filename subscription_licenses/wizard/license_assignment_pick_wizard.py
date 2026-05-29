# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


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

    assignment_ids = fields.Many2many(
        'license.assignment',
        string='Asignaciones',
        domain="[('id', 'in', available_assignment_ids)]",
        help='Seleccione una o varias asignaciones de licencia.',
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

    def _assignment_date_for(self, assignment):
        today = fields.Date.context_today(self)
        start = assignment.start_date
        return max(start, today) if start else today

    def _assign_equipment_license(self, assignment):
        """Crea o actualiza línea de licencia de equipo para una asignación."""
        self.ensure_one()
        LicenseEquipment = self.env['license.equipment']
        assignment_date = self._assignment_date_for(assignment)

        existing = LicenseEquipment.search([
            ('assignment_id', '=', assignment.id),
            ('lot_id', '=', self.lot_id.id),
            ('state', '=', 'assigned'),
        ], limit=1)
        if existing:
            return False

        LicenseEquipment.create({
            'assignment_id': assignment.id,
            'lot_id': self.lot_id.id,
            'contact_id': False,
            'state': 'assigned',
            'assignment_date': assignment_date,
        })
        return True

    def _assign_user_license(self, assignment):
        """Crea o actualiza línea de licencia de usuario para una asignación."""
        self.ensure_one()
        LicenseEquipment = self.env['license.equipment']
        related_partner_id = self.related_partner_id
        if not related_partner_id:
            raise UserError(_('El equipo no tiene un usuario relacionado asignado.'))

        assignment_date = self._assignment_date_for(assignment)

        existing = LicenseEquipment.search([
            ('assignment_id', '=', assignment.id),
            ('contact_id', '=', related_partner_id.id),
            ('state', '=', 'assigned'),
        ], limit=1)

        if existing:
            if not existing.lot_id:
                existing.write({'lot_id': self.lot_id.id})
                LicenseEquipment.search([
                    ('assignment_id', '=', assignment.id),
                    ('lot_id', '=', self.lot_id.id),
                    ('contact_id', '=', False),
                    ('state', '=', 'assigned'),
                ]).unlink()
                return True
            if existing.lot_id.id == self.lot_id.id:
                return False
            existing.write({'lot_id': self.lot_id.id})
            LicenseEquipment.search([
                ('assignment_id', '=', assignment.id),
                ('lot_id', '=', self.lot_id.id),
                ('contact_id', '=', False),
                ('state', '=', 'assigned'),
            ]).unlink()
            return True

        LicenseEquipment.create({
            'assignment_id': assignment.id,
            'lot_id': self.lot_id.id,
            'contact_id': related_partner_id.id,
            'state': 'assigned',
            'assignment_date': assignment_date,
        })
        LicenseEquipment.search([
            ('assignment_id', '=', assignment.id),
            ('lot_id', '=', self.lot_id.id),
            ('contact_id', '=', False),
            ('state', '=', 'assigned'),
        ]).unlink()
        return True

    def _process_assignments(self):
        """Asigna las licencias seleccionadas. Devuelve (creadas, omitidas, sin_cupo)."""
        self.ensure_one()
        if not self.assignment_ids:
            raise UserError(_('Debes seleccionar al menos una asignación.'))

        created = 0
        skipped = 0
        no_capacity = []
        for assignment in self.assignment_ids:
            label = assignment._capacity_license_label()
            try:
                if self.license_tab_type == 'equipment':
                    assignment.check_capacity_before_add_equipment(self.lot_id)
                    if self._assign_equipment_license(assignment):
                        created += 1
                    else:
                        skipped += 1
                else:
                    assignment.check_capacity_before_add_user(self.related_partner_id)
                    if self._assign_user_license(assignment):
                        created += 1
                    else:
                        skipped += 1
            except ValidationError as err:
                detail = err.args[0] if err.args else str(err)
                no_capacity.append('%s\n   %s' % (label, detail))

        if no_capacity and not created and not skipped:
            raise UserError(
                _('No hay licencias disponibles en:\n\n%s')
                % '\n\n'.join(no_capacity)
            )

        if not created and skipped and not no_capacity:
            raise UserError(_('Las asignaciones seleccionadas ya estaban vinculadas a este equipo o usuario.'))

        return created, skipped, no_capacity

    def _action_reopen_pick_wizard(self):
        """Reabre el wizard vacío para seguir agregando licencias."""
        self.ensure_one()
        ctx = {
            'default_lot_id': self.lot_id.id,
            'default_license_tab_type': self.license_tab_type,
            'force_license_partner_id': self.env.context.get('force_license_partner_id') or False,
            'force_license_location_id': self.env.context.get('force_license_location_id') or False,
            'from_route_lot_editor': self.env.context.get('from_route_lot_editor') or False,
        }
        return {
            'name': _('Agregar Asignación de Licencia'),
            'type': 'ir.actions.act_window',
            'res_model': 'license.assignment.pick.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': ctx,
        }

    def _finalize_with_capacity_warnings(self, no_capacity, next_action):
        """Si hubo licencias sin cupo, aviso y luego la acción de destino."""
        if not no_capacity:
            return next_action
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Algunas licencias no se agregaron'),
                'message': _(
                    'Sin licencias disponibles en:\n\n%(failed)s\n\n'
                    'Revise la cantidad en Licenciamientos o quite esas licencias de la selección.'
                ) % {'failed': '\n\n'.join(no_capacity)},
                'type': 'warning',
                'sticky': True,
                'next': next_action,
            },
        }

    def action_confirm(self):
        self.ensure_one()
        _created, _skipped, no_capacity = self._process_assignments()
        action = self.lot_id._action_return_license_editor_form(
            license_tab_type=self.license_tab_type,
        )
        return self._finalize_with_capacity_warnings(no_capacity, action)

    def action_confirm_and_add_more(self):
        """Agrega las licencias elegidas y permanece en este wizard para seguir."""
        self.ensure_one()
        _created, _skipped, no_capacity = self._process_assignments()
        action = self._action_reopen_pick_wizard()
        return self._finalize_with_capacity_warnings(no_capacity, action)

    def action_cancel(self):
        self.ensure_one()
        return self.lot_id._action_return_license_editor_form(
            license_tab_type=self.license_tab_type,
        )
