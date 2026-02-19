# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class LicenseEquipmentAddMultipleWizardLine(models.TransientModel):
    _name = 'license.equipment.add.multiple.wizard.line'
    _description = 'Línea del asistente añadir varios'

    wizard_id = fields.Many2one('license.equipment.add.multiple.wizard', required=True, ondelete='cascade')
    lot_id = fields.Many2one('stock.lot', string='Equipo')
    contact_id = fields.Many2one('res.partner', string='Contacto')
    selected = fields.Boolean(string='Seleccionar', default=False)


class LicenseEquipmentAddMultipleWizard(models.TransientModel):
    _name = 'license.equipment.add.multiple.wizard'
    _description = 'Asistente para añadir varios equipos o contactos a la asignación'

    assignment_id = fields.Many2one(
        'license.assignment',
        string='Asignación',
        required=True,
        ondelete='cascade',
        readonly=True,
    )
    add_type = fields.Selection([
        ('equipment', 'Equipos (Lote/Serie)'),
        ('contact', 'Contactos (Usuarios)'),
    ], string='Añadir por', required=True, default='equipment', readonly=True)
    line_ids = fields.One2many(
        'license.equipment.add.multiple.wizard.line',
        'wizard_id',
        string='Líneas',
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        assignment_id = self.env.context.get('default_assignment_id') or self.env.context.get('active_id')
        add_type = self.env.context.get('default_add_type', 'equipment')
        if not assignment_id:
            return res
        assignment = self.env['license.assignment'].browse(assignment_id)
        if not assignment.exists():
            return res
        line_vals = []
        if add_type == 'equipment':
            domain = self._get_available_lot_domain_for_assignment(assignment)
            lots = self.env['stock.lot'].search(domain) if domain != [('id', '=', False)] else self.env['stock.lot']
            existing = set(
                assignment.equipment_ids.filtered(lambda e: e.lot_id and e.state == 'assigned').mapped('lot_id').ids
            )
            for lot in lots:
                if lot.id in existing:
                    continue
                line_vals.append((0, 0, {'lot_id': lot.id, 'selected': False}))
        else:
            domain = self._get_available_contact_domain_for_assignment(assignment)
            contacts = self.env['res.partner'].search(domain) if domain != [('id', '=', False)] else self.env['res.partner']
            existing = set(
                assignment.equipment_ids.filtered(lambda e: e.contact_id and e.state == 'assigned').mapped('contact_id').ids
            )
            for contact in contacts:
                if contact.id in existing:
                    continue
                line_vals.append((0, 0, {'contact_id': contact.id, 'selected': False}))
        res['line_ids'] = line_vals
        return res

    def _get_available_lot_domain_for_assignment(self, assignment):
        if not assignment or not assignment.location_id:
            return [('id', '=', False)]
        location = assignment.location_id
        computo_category = self.env['product.asset.category'].search([('name', '=', 'COMPUTO')], limit=1)
        quants = self.env['stock.quant'].search([
            ('location_id', 'child_of', location.id),
            ('lot_id', '!=', False),
            ('quantity', '>', 0),
        ])
        lot_ids = []
        for quant in quants:
            if quant.lot_id and quant.lot_id.product_id and quant.lot_id.product_id.asset_category_id:
                if computo_category and quant.lot_id.product_id.asset_category_id.id == computo_category.id:
                    if quant.lot_id.id not in lot_ids:
                        lot_ids.append(quant.lot_id.id)
        return [('id', 'in', lot_ids)] if lot_ids else [('id', '=', False)]

    def _get_available_contact_domain_for_assignment(self, assignment):
        if not assignment or not assignment.partner_id:
            return [('id', '=', False)]
        return [
            ('parent_id', '=', assignment.partner_id.id),
            ('is_company', '=', False),
        ]

    def action_confirm(self):
        """Crea una línea license.equipment por cada línea marcada como seleccionada."""
        self.ensure_one()
        selected = self.line_ids.filtered(lambda l: l.selected)
        if not selected:
            raise UserError(_('Marque al menos un elemento para añadir.'))
        LicenseEquipment = self.env['license.equipment']
        created = 0
        if self.add_type == 'equipment':
            existing_lots = set(
                self.assignment_id.equipment_ids.filtered(lambda e: e.lot_id and e.state == 'assigned').mapped('lot_id').ids
            )
            # Fecha de asignación = inicio de contrato, o hoy si se agrega después (ej. contrato en enero, agregó el 27)
            today = fields.Date.context_today(self)
            start = self.assignment_id.start_date
            assignment_date = max(start, today) if start else today
            for line in selected:
                if line.lot_id and line.lot_id.id not in existing_lots:
                    LicenseEquipment.create({
                        'assignment_id': self.assignment_id.id,
                        'lot_id': line.lot_id.id,
                        'contact_id': False,
                        'state': 'assigned',
                        'assignment_date': assignment_date,
                    })
                    created += 1
        else:
            existing_contacts = set(
                self.assignment_id.equipment_ids.filtered(lambda e: e.contact_id and e.state == 'assigned').mapped('contact_id').ids
            )
            today = fields.Date.context_today(self)
            start = self.assignment_id.start_date
            assignment_date = max(start, today) if start else today
            for line in selected:
                if line.contact_id and line.contact_id.id not in existing_contacts:
                    LicenseEquipment.create({
                        'assignment_id': self.assignment_id.id,
                        'contact_id': line.contact_id.id,
                        'lot_id': False,
                        'state': 'assigned',
                        'assignment_date': assignment_date,
                    })
                    created += 1
        if created == 0:
            raise UserError(_('Todos los elementos seleccionados ya estaban asignados.'))
        return {'type': 'ir.actions.act_window_close'}

    def action_select_all(self):
        """Marca todas las líneas como seleccionadas y reabre el wizard para que no se cierre."""
        self.ensure_one()
        self.line_ids.write({'selected': True})
        return self._reopen_wizard()

    def action_unselect_all(self):
        """Desmarca todas las líneas y reabre el wizard para que no se cierre."""
        self.ensure_one()
        self.line_ids.write({'selected': False})
        return self._reopen_wizard()

    def _reopen_wizard(self):
        """Devuelve una acción que reabre este mismo wizard para mantener el diálogo abierto con los datos actualizados."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': dict(self.env.context),
        }
