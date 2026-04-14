# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ComponentLabAssignment(models.Model):
    _name = 'component.lab.assignment'
    _description = 'Asignación de material en laboratorio (pool)'
    _order = 'id desc'

    name = fields.Char(string='Referencia', compute='_compute_name', store=True)
    intake_picking_id = fields.Many2one(
        'stock.picking',
        string='Ingreso a laboratorio',
        required=True,
        ondelete='cascade',
        index=True,
    )
    lot_id = fields.Many2one('stock.lot', string='Serial', required=True, index=True)
    product_id = fields.Many2one('product.product', string='Producto', required=True)
    responsible_user_id = fields.Many2one(
        'res.users',
        string='Responsable (lab.)',
        required=True,
        domain=[('share', '=', False)],
    )
    technician_user_id = fields.Many2one(
        'res.users',
        string='Técnico (asignado)',
        domain=[('share', '=', False)],
    )
    state = fields.Selection(
        [
            ('in_lab_pool', 'En pool laboratorio (disponible)'),
            ('tech_request_pending_approval', 'Pendiente aprobación solicitud técnico'),
            ('with_technician', 'Con técnico'),
            ('tech_return_pending_approval', 'Pendiente aprobación devolución técnico'),
            ('returned_to_responsible', 'Con responsable (en lab.)'),
            ('returned_to_exist', 'Devuelto a Existencias'),
        ],
        string='Estado',
        default='in_lab_pool',
        required=True,
        index=True,
    )
    expected_return_date = fields.Date(string='Fecha prevista libre')
    remaining_days = fields.Integer(
        string='Días restantes',
        compute='_compute_remaining_days',
    )
    is_overdue = fields.Boolean(
        string='Vencido',
        compute='_compute_remaining_days',
    )
    extension_request_date = fields.Date(string='Prórroga solicitada para')
    extension_request_reason = fields.Text(string='Motivo prórroga')
    extension_request_state = fields.Selection(
        [
            ('none', 'Sin solicitud'),
            ('pending', 'Pendiente aprobación'),
            ('approved', 'Aprobada'),
            ('rejected', 'Rechazada'),
        ],
        string='Estado prórroga',
        default='none',
    )
    extension_approved_by = fields.Many2one('res.users', string='Prórroga aprobada por', readonly=True)
    extension_approved_on = fields.Datetime(string='Fecha aprobación prórroga', readonly=True)
    acta_ids = fields.One2many('component.lab.acta', 'assignment_id', string='Actas')
    current_assign_acta_number = fields.Char(string='Acta entrega técnico')
    pending_return_acta_number = fields.Char(string='Acta devolución pendiente')
    pending_request_acta_number = fields.Char(string='Acta solicitud técnico pendiente')
    requested_by_user_id = fields.Many2one('res.users', string='Solicitado por')
    exit_picking_id = fields.Many2one(
        'stock.picking',
        string='Albarán a Existencias',
        readonly=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        related='intake_picking_id.company_id',
        store=True,
    )
    availability_display = fields.Char(
        string='Disponibilidad',
        compute='_compute_availability_display',
    )
    lab_eligible_product_ids = fields.Many2many(
        'product.product',
        string='Productos en laboratorio (filtro)',
        compute='_compute_lab_eligible_stock',
        help='Solo para dominios de vista: productos con serial y cantidad > 0 en ubicación laboratorio.',
    )
    lab_eligible_lot_ids = fields.Many2many(
        'stock.lot',
        string='Seriales en laboratorio (filtro)',
        compute='_compute_lab_eligible_stock',
        help='Solo para dominios de vista: lotes con cantidad > 0 en ubicación laboratorio.',
    )

    _sql_constraints = [
        (
            'assignment_lot_intake_unique',
            'unique(lot_id, intake_picking_id)',
            'Ya existe una asignación para este serial en este ingreso a laboratorio.',
        ),
    ]

    @api.depends('lot_id', 'product_id')
    def _compute_name(self):
        for rec in self:
            lot = rec.lot_id.name or ''
            prod = rec.product_id.display_name or ''
            rec.name = f'{lot} — {prod}' if lot else prod

    def _search_default_lab_location(self):
        """Misma lógica que el wizard de traslado (Supp/Laboratorio, etc.)."""
        Location = self.env['stock.location']
        lab = Location.search([
            ('complete_name', 'ilike', 'Supp/Laboratorio'),
        ], limit=1)
        if not lab:
            lab = Location.search([
                ('name', 'ilike', 'Laboratorio'),
                ('complete_name', 'ilike', 'Supp'),
            ], limit=1)
        if not lab:
            lab = Location.search([
                ('name', 'ilike', 'Laboratorio'),
            ], limit=1)
        return lab

    def _resolve_lab_stock_location(self):
        """Ubicación física del pool: destino del ingreso si existe; si no, laboratorio por nombre."""
        self.ensure_one()
        picking = self.intake_picking_id
        if picking and picking.location_dest_id:
            return picking.location_dest_id
        return self._search_default_lab_location()

    @api.depends(
        'intake_picking_id',
        'intake_picking_id.location_dest_id',
        'company_id',
    )
    def _compute_lab_eligible_stock(self):
        Quant = self.env['stock.quant']
        Product = self.env['product.product']
        Lot = self.env['stock.lot']
        for rec in self:
            rec.lab_eligible_product_ids = Product
            rec.lab_eligible_lot_ids = Lot
            lab_loc = rec._resolve_lab_stock_location()
            if not lab_loc:
                continue
            company = rec.company_id or rec.intake_picking_id.company_id if rec.intake_picking_id else self.env.company
            domain = [
                ('location_id', 'child_of', lab_loc.id),
                ('quantity', '>', 0),
                ('lot_id', '!=', False),
            ]
            if company:
                domain.append(('company_id', '=', company.id))
            quants = Quant.search(domain)
            lots = quants.mapped('lot_id')
            rec.lab_eligible_lot_ids = lots
            rec.lab_eligible_product_ids = lots.mapped('product_id')

    @api.depends('state', 'technician_user_id', 'expected_return_date')
    def _compute_availability_display(self):
        for rec in self:
            if rec.state == 'in_lab_pool':
                rec.availability_display = _('Disponible en laboratorio')
            elif rec.state == 'with_technician':
                extra = ''
                if rec.expected_return_date:
                    days = rec.remaining_days
                    if days is False:
                        extra = _(' (previsto libre: %s)') % rec.expected_return_date
                    elif rec.is_overdue:
                        extra = _(' (vencido hace %s día(s))') % abs(days)
                    else:
                        extra = _(' (faltan %s día(s), fecha: %s)') % (days, rec.expected_return_date)
                tech = rec.technician_user_id.display_name if rec.technician_user_id else ''
                rec.availability_display = _('No disponible — con técnico %s%s') % (tech, extra)
            elif rec.state == 'tech_return_pending_approval':
                rec.availability_display = _('Pendiente aprobación del responsable de laboratorio')
            elif rec.state == 'tech_request_pending_approval':
                requester = rec.requested_by_user_id.display_name if rec.requested_by_user_id else _('técnico')
                rec.availability_display = _('Solicitud pendiente de aprobación (%s)') % requester
            elif rec.state == 'returned_to_responsible':
                rec.availability_display = _('Con responsable en laboratorio')
            else:
                rec.availability_display = _('Devuelto a Existencias')

    @api.depends('expected_return_date', 'state')
    def _compute_remaining_days(self):
        today = fields.Date.today()
        for rec in self:
            rec.remaining_days = 0
            rec.is_overdue = False
            if rec.state != 'with_technician' or not rec.expected_return_date:
                continue
            delta = (rec.expected_return_date - today).days
            rec.remaining_days = delta
            rec.is_overdue = delta < 0

    def action_assign_technician(self, technician, expected_date=None):
        """API para wizard: pasa de pool a técnico."""
        technician.ensure_one()
        sm = self.env.user.has_group('stock.group_stock_manager')
        acta_number = self.env['component.lab.acta']._next_name()
        for rec in self:
            if rec.state != 'in_lab_pool':
                raise UserError(_('Solo puede asignar ítems en «pool laboratorio». Serial: %s') % rec.lot_id.display_name)
            if rec.responsible_user_id != self.env.user and not sm:
                raise UserError(_('Solo el responsable de laboratorio (o inventario) puede asignar a técnicos.'))
        self.write({
            'technician_user_id': technician.id,
            'expected_return_date': expected_date,
            'current_assign_acta_number': acta_number,
            'pending_return_acta_number': False,
            'state': 'with_technician',
        })
        for rec in self:
            self.env['component.lab.acta'].create_from_assignment(
                rec, 'assign_technician', note=_('Entrega bajo acta %s') % acta_number, acta_name=acta_number
            )

    def action_return_from_technician(self):
        """El técnico solicita devolución; queda pendiente aprobación del responsable."""
        sm = self.env.user.has_group('stock.group_stock_manager')
        u = self.env.user
        for rec in self:
            if rec.state != 'with_technician':
                raise UserError(_('Solo aplica a ítems «con técnico». Serial: %s') % rec.lot_id.display_name)
            ok = rec.technician_user_id == u or rec.responsible_user_id == u or sm
            if not ok:
                raise UserError(_('Solo el técnico asignado, el responsable o inventario puede registrar esta devolución.'))
        for rec in self:
            rec.write({
                'pending_return_acta_number': rec.current_assign_acta_number or self.env['component.lab.acta']._next_name(),
                'state': 'tech_return_pending_approval',
            })
            acta_name = rec.pending_return_acta_number or rec.current_assign_acta_number
            self.env['component.lab.acta'].create_from_assignment(
                rec, 'tech_return_request', note=_('Solicitud devolución bajo acta %s') % acta_name, acta_name=acta_name
            )

    def action_request_from_technician(self):
        """El técnico solicita elementos del pool; queda pendiente aprobación del responsable."""
        sm = self.env.user.has_group('stock.group_stock_manager')
        requester = self.env.user
        acta_number = self.env['component.lab.acta']._next_name()
        for rec in self:
            if rec.state != 'in_lab_pool':
                raise UserError(_('Solo puede solicitar ítems disponibles en pool. Serial: %s') % rec.lot_id.display_name)
            if rec.responsible_user_id == requester:
                continue
            if requester.share and not sm:
                raise UserError(_('El usuario solicitante no tiene permisos para crear solicitudes de laboratorio.'))
        self.write({
            'state': 'tech_request_pending_approval',
            'requested_by_user_id': requester.id,
            'pending_request_acta_number': acta_number,
        })

    def action_approve_tech_request(self, expected_date=None):
        sm = self.env.user.has_group('stock.group_stock_manager')
        for rec in self:
            if rec.state != 'tech_request_pending_approval':
                raise UserError(_('El activo no está pendiente de aprobación de solicitud.'))
            if rec.responsible_user_id != self.env.user and not sm:
                raise UserError(_('Solo el responsable de laboratorio (o inventario) puede aprobar solicitudes.'))
            if not rec.requested_by_user_id:
                raise UserError(_('La solicitud no tiene técnico solicitante.'))
            acta_name = rec.pending_request_acta_number or self.env['component.lab.acta']._next_name()
            rec.write({
                'technician_user_id': rec.requested_by_user_id.id,
                'expected_return_date': expected_date or rec.expected_return_date or False,
                'current_assign_acta_number': acta_name,
                'pending_request_acta_number': False,
                'requested_by_user_id': False,
                'state': 'with_technician',
            })
            self.env['component.lab.acta'].create_from_assignment(
                rec, 'assign_technician', note=_('Aprobación solicitud técnico bajo acta %s') % acta_name, acta_name=acta_name
            )

    def action_reject_tech_request(self, reason=''):
        sm = self.env.user.has_group('stock.group_stock_manager')
        for rec in self:
            if rec.state != 'tech_request_pending_approval':
                raise UserError(_('El activo no está pendiente de aprobación de solicitud.'))
            if rec.responsible_user_id != self.env.user and not sm:
                raise UserError(_('Solo el responsable de laboratorio (o inventario) puede rechazar solicitudes.'))
            rec.write({
                'state': 'in_lab_pool',
                'pending_request_acta_number': False,
                'requested_by_user_id': False,
            })

    def action_approve_technician_return(self):
        sm = self.env.user.has_group('stock.group_stock_manager')
        for rec in self:
            if rec.state != 'tech_return_pending_approval':
                raise UserError(_('El activo no está pendiente de aprobación de devolución.'))
            if rec.responsible_user_id != self.env.user and not sm:
                raise UserError(_('Solo el responsable de laboratorio (o inventario) puede aprobar la devolución del técnico.'))
            acta_name = rec.pending_return_acta_number or rec.current_assign_acta_number
            rec.write({
                'technician_user_id': False,
                'expected_return_date': False,
                'extension_request_date': False,
                'extension_request_reason': False,
                'extension_request_state': 'none',
                'extension_approved_by': False,
                'extension_approved_on': False,
                'current_assign_acta_number': False,
                'pending_return_acta_number': False,
                'state': 'in_lab_pool',
            })
            self.env['component.lab.acta'].create_from_assignment(
                rec, 'tech_return_approved', acta_name=acta_name
            )

    def action_reject_technician_return(self, reason=''):
        sm = self.env.user.has_group('stock.group_stock_manager')
        for rec in self:
            if rec.state != 'tech_return_pending_approval':
                raise UserError(_('El activo no está pendiente de aprobación de devolución.'))
            if rec.responsible_user_id != self.env.user and not sm:
                raise UserError(_('Solo el responsable de laboratorio (o inventario) puede rechazar la devolución del técnico.'))
            acta_name = rec.pending_return_acta_number or rec.current_assign_acta_number
            rec.write({'state': 'with_technician', 'pending_return_acta_number': False})
            self.env['component.lab.acta'].create_from_assignment(
                rec,
                'tech_return_rejected',
                note=reason or _('Devolución rechazada por responsable.'),
                acta_name=acta_name,
            )

    def action_mark_available_in_pool(self):
        sm = self.env.user.has_group('stock.group_stock_manager')
        for rec in self:
            if rec.state != 'returned_to_responsible':
                raise UserError(_('Solo puede pasar a disponible un activo que esté con responsable en laboratorio.'))
            if rec.responsible_user_id != self.env.user and not sm:
                raise UserError(_('Solo el responsable de laboratorio (o inventario) puede dejar el activo disponible.'))
        self.write({'state': 'in_lab_pool'})

    def action_request_extension(self, new_date, reason=''):
        if not new_date:
            raise UserError(_('Debe indicar una fecha de prórroga.'))
        parsed_new_date = fields.Date.to_date(new_date)
        sm = self.env.user.has_group('stock.group_stock_manager')
        for rec in self:
            if rec.state != 'with_technician':
                raise UserError(_('Solo aplica para activos con técnico asignado.'))
            if rec.expected_return_date and parsed_new_date <= rec.expected_return_date:
                raise UserError(_('La nueva fecha debe ser mayor a la fecha estimada actual.'))
            if rec.technician_user_id != self.env.user and not sm:
                raise UserError(_('Solo el técnico asignado (o inventario) puede solicitar prórroga.'))
        self.write({
            'extension_request_date': parsed_new_date,
            'extension_request_reason': reason or False,
            'extension_request_state': 'pending',
            'extension_approved_by': False,
            'extension_approved_on': False,
        })

    def action_approve_extension(self):
        sm = self.env.user.has_group('stock.group_stock_manager')
        for rec in self:
            if rec.state != 'with_technician' or rec.extension_request_state != 'pending':
                raise UserError(_('No hay solicitud de prórroga pendiente para este activo.'))
            if rec.responsible_user_id != self.env.user and not sm:
                raise UserError(_('Solo el responsable de laboratorio (o inventario) puede aprobar prórrogas.'))
            rec.write({
                'expected_return_date': rec.extension_request_date,
                'extension_request_state': 'approved',
                'extension_approved_by': self.env.user.id,
                'extension_approved_on': fields.Datetime.now(),
            })

    def action_reject_extension(self, reason=''):
        sm = self.env.user.has_group('stock.group_stock_manager')
        for rec in self:
            if rec.state != 'with_technician' or rec.extension_request_state != 'pending':
                raise UserError(_('No hay solicitud de prórroga pendiente para este activo.'))
            if rec.responsible_user_id != self.env.user and not sm:
                raise UserError(_('Solo el responsable de laboratorio (o inventario) puede rechazar prórrogas.'))
            rec.write({
                'extension_request_state': 'rejected',
                'extension_request_date': False,
                'extension_request_reason': reason or False,
                'extension_approved_by': False,
                'extension_approved_on': False,
            })

    def action_open_assign_tech_wizard(self):
        self.ensure_one()
        action = self.env.ref('inventory_dashboard_simple.action_component_lab_assign_tech_wizard').read()[0]
        action['context'] = {'default_assignment_ids': [(6, 0, self.ids)]}
        return action

    def action_open_tech_return_wizard(self):
        self.ensure_one()
        action = self.env.ref('inventory_dashboard_simple.action_component_lab_tech_return_wizard').read()[0]
        action['context'] = {'default_assignment_ids': [(6, 0, self.ids)]}
        return action

    def action_open_responsible_return_wizard(self):
        self.ensure_one()
        line_cmd = [(0, 0, {'assignment_id': self.id, 'quantity': 1.0})]
        action = self.env.ref('inventory_dashboard_simple.action_component_lab_responsible_return_wizard').read()[0]
        action['context'] = {'default_line_ids': line_cmd}
        return action
