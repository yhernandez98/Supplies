# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ComponentLabAssignTechWizard(models.TransientModel):
    _name = 'component.lab.assign.tech.wizard'
    _description = 'Asignar material del pool de laboratorio a un técnico'

    assignment_ids = fields.Many2many(
        'component.lab.assignment',
        string='Ítems en pool (laboratorio)',
        required=True,
        domain=[('state', '=', 'in_lab_pool')],
    )
    technician_user_id = fields.Many2one(
        'res.users',
        string='Técnico',
        required=True,
        domain=[('share', '=', False)],
    )
    expected_return_date = fields.Date(string='Fecha prevista libre')

    def action_apply(self):
        self.ensure_one()
        if not self.assignment_ids:
            raise UserError(_('Seleccione al menos un ítem del pool.'))
        self.assignment_ids.action_assign_technician(
            self.technician_user_id,
            self.expected_return_date,
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Asignación registrada'),
                'message': _('El material sigue en laboratorio; consta como entregado al técnico.'),
                'type': 'success',
            },
        }


class ComponentLabTechReturnWizard(models.TransientModel):
    _name = 'component.lab.tech.return.wizard'
    _description = 'Devolución técnico → responsable (sin mover a Existencias)'

    assignment_ids = fields.Many2many(
        'component.lab.assignment',
        string='Ítems con técnico',
        required=True,
        domain=[('state', '=', 'with_technician')],
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'assignment_ids' in fields_list:
            mine = self.env['component.lab.assignment'].search([
                ('state', '=', 'with_technician'),
                ('technician_user_id', '=', self.env.user.id),
            ])
            res['assignment_ids'] = [(6, 0, mine.ids)]
        return res

    def action_apply(self):
        self.ensure_one()
        if not self.assignment_ids:
            raise UserError(_('Seleccione al menos un ítem.'))
        self.assignment_ids.action_return_from_technician()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Solicitud de devolución registrada'),
                'message': _('Queda pendiente la aprobación del responsable de laboratorio.'),
                'type': 'success',
            },
        }


class ComponentLabResponsibleReturnWizardLine(models.TransientModel):
    _name = 'component.lab.responsible.return.wizard.line'
    _description = 'Línea devolución responsable a Existencias'

    wizard_id = fields.Many2one(
        'component.lab.responsible.return.wizard',
        required=True,
        ondelete='cascade',
    )
    assignment_id = fields.Many2one(
        'component.lab.assignment',
        string='Asignación',
        required=True,
        domain="[('state', 'in', ('in_lab_pool', 'returned_to_responsible'))]",
    )
    product_id = fields.Many2one(related='assignment_id.product_id', readonly=True)
    lot_id = fields.Many2one(related='assignment_id.lot_id', readonly=True)
    quantity = fields.Float(string='Cantidad', default=1.0, required=True)


class ComponentLabResponsibleReturnWizard(models.TransientModel):
    _name = 'component.lab.responsible.return.wizard'
    _description = 'Responsable: devolver material de laboratorio a Existencias'

    line_ids = fields.One2many(
        'component.lab.responsible.return.wizard.line',
        'wizard_id',
        string='Seriales',
    )
    note = fields.Text(string='Nota')

    def _get_internal_picking_type(self, source, dest):
        PickingType = self.env['stock.picking.type']
        picking_type = PickingType.search([
            ('code', '=', 'internal'),
            ('default_location_src_id', '=', source.id),
            ('default_location_dest_id', '=', dest.id),
        ], limit=1)
        if not picking_type:
            picking_type = PickingType.search([
                ('code', '=', 'internal'),
                ('company_id', '=', self.env.company.id),
            ], limit=1)
        if not picking_type:
            raise UserError(_('No se encontró un tipo de operación interna para realizar el traslado.'))
        return picking_type

    def _get_transfer_locations(self):
        Location = self.env['stock.location']
        exist = Location.search([('complete_name', 'ilike', 'Supp/Existencias')], limit=1)
        if not exist:
            exist = Location.search([
                ('name', 'ilike', 'Existencias'),
                ('complete_name', 'ilike', 'Supp'),
            ], limit=1)
        if not exist:
            exist = Location.search([('name', 'ilike', 'Existencias')], limit=1)
        lab = Location.search([('complete_name', 'ilike', 'Supp/Laboratorio')], limit=1)
        if not lab:
            lab = Location.search([
                ('name', 'ilike', 'Laboratorio'),
                ('complete_name', 'ilike', 'Supp'),
            ], limit=1)
        if not lab:
            lab = Location.search([('name', 'ilike', 'Laboratorio')], limit=1)
        return exist, lab

    def action_process(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('Agregue al menos una línea.'))

        exist, lab = self._get_transfer_locations()
        if not exist or not lab:
            raise UserError(_('No se encontraron ubicaciones Supp/Existencias y Supp/Laboratorio.'))

        sm = self.env.user.has_group('stock.group_stock_manager')
        assignments = self.env['component.lab.assignment']
        seen_lots = set()

        Quant = self.env['stock.quant']
        for line in self.line_ids:
            ass = line.assignment_id
            if ass.state not in ('in_lab_pool', 'returned_to_responsible'):
                raise UserError(_('El serial %s no está disponible para devolución a Existencias en este flujo.') % ass.lot_id.display_name)
            if ass.responsible_user_id != self.env.user and not sm:
                raise UserError(_('Solo el responsable de laboratorio de cada ítem (o inventario) puede devolver a Existencias.'))
            if ass.lot_id.id in seen_lots:
                raise UserError(_('No repita el mismo serial en varias líneas.'))
            seen_lots.add(ass.lot_id.id)
            if line.quantity <= 0:
                raise UserError(_('La cantidad debe ser mayor a cero.'))

            available_qty = sum(Quant.search([
                ('location_id', 'child_of', lab.id),
                ('product_id', '=', ass.product_id.id),
                ('lot_id', '=', ass.lot_id.id),
                ('quantity', '>', 0),
            ]).mapped('quantity'))
            if line.quantity > available_qty:
                raise UserError(_(
                    'Serial %(lot)s: cantidad insuficiente en laboratorio.\nDisponible: %(av)s / Solicitado: %(rq)s'
                ) % {'lot': ass.lot_id.display_name, 'av': available_qty, 'rq': line.quantity})

            assignments |= ass

        picking_type = self._get_internal_picking_type(lab, exist)
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': lab.id,
            'location_dest_id': exist.id,
            'origin': _('Devolución pool lab. → Existencias (responsable)'),
            'note': self.note or '',
            'component_lab_pool_exit': True,
        })

        Move = self.env['stock.move']
        MoveLine = self.env['stock.move.line']
        for line in self.line_ids:
            ass = line.assignment_id
            move = Move.create({
                'description_picking': _('Devolución lab. pool: %s') % (ass.product_id.display_name or ass.product_id.name),
                'picking_id': picking.id,
                'product_id': ass.product_id.id,
                'product_uom': ass.product_id.uom_id.id,
                'product_uom_qty': line.quantity,
                'location_id': lab.id,
                'location_dest_id': exist.id,
            })
            MoveLine.create({
                'move_id': move.id,
                'picking_id': picking.id,
                'product_id': ass.product_id.id,
                'product_uom_id': ass.product_id.uom_id.id,
                'location_id': lab.id,
                'location_dest_id': exist.id,
                'lot_id': ass.lot_id.id,
                'qty_done': line.quantity,
            })

        picking.action_confirm()
        picking.action_assign()
        picking.button_validate()

        assignments.write({
            'state': 'returned_to_exist',
            'exit_picking_id': picking.id,
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Traslado a Existencias validado'),
                'message': _('Operación %s. Las asignaciones pasaron a «Devuelto a Existencias».') % picking.name,
                'type': 'success',
                'sticky': True,
            },
        }
