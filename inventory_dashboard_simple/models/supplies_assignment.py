# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SuppliesAssignment(models.Model):
    _name = 'supplies.assignment'
    _description = 'Asignaciones Supplies'
    _order = 'id desc'

    name = fields.Char(
        string='Referencia',
        required=True,
        copy=False,
        default=lambda self: _('Nuevo'),
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Asignado a',
        readonly=True,
        states={'draft': [('readonly', False)]},
    )
    user_id = fields.Many2one(
        'res.users',
        string='Usuario Odoo del asignado',
        related='employee_id.user_id',
        store=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        required=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
    )
    lot_id = fields.Many2one(
        'stock.lot',
        string='Serial',
        required=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
    )
    quantity = fields.Float(
        string='Cantidad',
        default=1.0,
        required=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
    )
    source_location_id = fields.Many2one(
        'stock.location',
        string='Ubicación origen',
        readonly=True,
    )
    destination_location_id = fields.Many2one(
        'stock.location',
        string='Ubicación asignación',
        readonly=True,
    )
    assignment_picking_id = fields.Many2one(
        'stock.picking',
        string='Traslado de asignación',
        readonly=True,
    )
    return_picking_id = fields.Many2one(
        'stock.picking',
        string='Traslado de devolución',
        readonly=True,
    )
    assignment_date = fields.Datetime(string='Fecha asignación', readonly=True)
    return_date = fields.Datetime(string='Fecha devolución', readonly=True)
    delivery_user_id = fields.Many2one('res.users', string='Entrega (usuario)', readonly=True)
    delivery_employee_id = fields.Many2one('hr.employee', string='Empleado que entrega', compute='_compute_employee_signature_data', store=False)
    receiver_employee_id = fields.Many2one('hr.employee', string='Empleado que recibe', compute='_compute_employee_signature_data', store=False)
    delivery_job_name = fields.Char(string='Cargo entrega', compute='_compute_employee_signature_data', store=False)
    receiver_job_name = fields.Char(string='Cargo recibe', compute='_compute_employee_signature_data', store=False)
    signature_delivery = fields.Binary(string='Firma entrega', attachment=True)
    signature_receiver = fields.Binary(string='Firma recibe', attachment=True)
    signature_state = fields.Selection(
        [('pending', 'Pendiente firmas'), ('signed', 'Firmada')],
        string='Estado de firmas',
        default='pending',
        required=True,
        index=True,
    )
    return_signature_delivery = fields.Binary(string='Firma devolución entrega', attachment=True)
    return_signature_receiver = fields.Binary(string='Firma devolución recibe', attachment=True)
    return_signature_state = fields.Selection(
        [('pending', 'Pendiente firmas devolución'), ('signed', 'Firmada devolución')],
        string='Estado firmas devolución',
        default='pending',
        required=True,
        index=True,
    )
    return_pending_signature = fields.Boolean(string='Devolución pendiente por firmas', default=False, index=True)
    return_signature_request_date = fields.Datetime(string='Fecha solicitud devolución', readonly=True)
    note = fields.Text(string='Nota')
    state = fields.Selection(
        [
            ('draft', 'Borrador'),
            ('assigned', 'Asignado'),
            ('returned', 'Devuelto'),
        ],
        string='Estado',
        default='draft',
        required=True,
        index=True,
    )
    availability_display = fields.Char(
        string='Disponibilidad',
        compute='_compute_availability_display',
    )

    @api.depends('state', 'employee_id', 'user_id', 'destination_location_id', 'signature_state')
    def _compute_availability_display(self):
        for rec in self:
            assignee_name = rec.employee_id.name or rec.user_id.display_name or ''
            if rec.state == 'assigned':
                base = _('No disponible en existencias - asignado a %s') % assignee_name
                if rec.signature_state == 'pending':
                    rec.availability_display = base + _(' (pendiente por firmas)')
                else:
                    rec.availability_display = base
            elif rec.state == 'returned':
                rec.availability_display = _('Disponible en existencias')
            else:
                rec.availability_display = _('Pendiente de asignación')

    @api.depends('delivery_user_id', 'employee_id', 'user_id')
    def _compute_employee_signature_data(self):
        Emp = self.env['hr.employee'].sudo()
        for rec in self:
            rec.delivery_employee_id = Emp.search([('user_id', '=', rec.delivery_user_id.id)], limit=1) if rec.delivery_user_id else False
            rec.receiver_employee_id = rec.employee_id or (Emp.search([('user_id', '=', rec.user_id.id)], limit=1) if rec.user_id else False)
            rec.delivery_job_name = rec.delivery_employee_id.job_id.name if rec.delivery_employee_id and rec.delivery_employee_id.job_id else ''
            rec.receiver_job_name = rec.receiver_employee_id.job_id.name if rec.receiver_employee_id and rec.receiver_employee_id.job_id else ''

    @api.model_create_multi
    def create(self, vals_list):
        Emp = self.env['hr.employee'].sudo()
        for vals in vals_list:
            # Compatibilidad con llamados antiguos que enviaban user_id.
            if not vals.get('employee_id') and vals.get('user_id'):
                emp = Emp.search([('user_id', '=', vals.get('user_id'))], limit=1)
                if emp:
                    vals['employee_id'] = emp.id
            if vals.get('name', _('Nuevo')) == _('Nuevo'):
                vals['name'] = self.env['ir.sequence'].next_by_code('supplies.assignment') or _('Nuevo')
            if not vals.get('delivery_user_id'):
                vals['delivery_user_id'] = self.env.user.id
        records = super().create(vals_list)
        records._sync_product_from_lot()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'lot_id' in vals:
            self._sync_product_from_lot()
        if 'signature_delivery' in vals or 'signature_receiver' in vals:
            for rec in self:
                rec.signature_state = 'signed' if rec.signature_delivery and rec.signature_receiver else 'pending'
        if 'return_signature_delivery' in vals or 'return_signature_receiver' in vals:
            for rec in self:
                rec.return_signature_state = 'signed' if rec.return_signature_delivery and rec.return_signature_receiver else 'pending'
        return res

    def _sync_product_from_lot(self):
        for rec in self:
            if rec.lot_id and rec.product_id != rec.lot_id.product_id:
                rec.product_id = rec.lot_id.product_id.id

    def _normalize_report_text(self, value):
        """Corrige texto con mojibake comun (ej: AdministraciÃ³n)."""
        txt = value or ''
        if not txt:
            return ''
        txt = str(txt)
        # Intentamos reparar varias capas de codificacion incorrecta sin perder caracteres.
        for _i in range(3):
            changed = False
            for enc in ('latin1', 'cp1252'):
                try:
                    repaired = txt.encode(enc).decode('utf-8')
                except Exception:
                    continue
                if repaired and repaired != txt:
                    txt = repaired
                    changed = True
            if not changed:
                break

        replacements = {
            'Ã¡': 'á', 'Ã©': 'é', 'Ã­': 'í', 'Ã³': 'ó', 'Ãº': 'ú',
            'Ã': 'Á', 'Ã‰': 'É', 'Ã': 'Í', 'Ã“': 'Ó', 'Ãš': 'Ú',
            'Ã±': 'ñ', 'Ã‘': 'Ñ', 'Ã¼': 'ü', 'Ãœ': 'Ü',
            'Â¿': '¿', 'Â¡': '¡', 'Â': '',
            'A±o': 'Año', 'a±o': 'año', '±': 'ñ',
            '\ufffd': '',
        }
        for bad, good in replacements.items():
            txt = txt.replace(bad, good)
        return txt

    def _find_exist_location(self):
        Location = self.env['stock.location']
        exist = Location.search([('complete_name', 'ilike', 'Supp/Existencias')], limit=1)
        if not exist:
            exist = Location.search([
                ('name', 'ilike', 'Existencias'),
                ('complete_name', 'ilike', 'Supp'),
            ], limit=1)
        if not exist:
            exist = Location.search([('name', 'ilike', 'Existencias')], limit=1)
        return exist

    def _find_or_create_assigned_location(self):
        Location = self.env['stock.location']
        assigned = Location.search([('complete_name', 'ilike', 'Supp/Asignaciones Supplies')], limit=1)
        if assigned:
            return assigned
        assigned = Location.search([('name', '=', 'Asignaciones Supplies')], limit=1)
        if assigned:
            return assigned

        parent = self._find_exist_location()
        parent_id = parent.location_id.id if parent and parent.location_id else False
        usage = 'internal'
        vals = {
            'name': 'Asignaciones Supplies',
            'usage': usage,
            'location_id': parent_id,
            'company_id': self.env.company.id,
        }
        return Location.create(vals)

    def _get_internal_picking_type(self, source, dest):
        PickingType = self.env['stock.picking.type']
        picking_type = PickingType.search([
            ('code', '=', 'internal'),
            ('default_location_src_id', '=', source.id),
            ('default_location_dest_id', '=', dest.id),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        if not picking_type:
            picking_type = PickingType.search([
                ('code', '=', 'internal'),
                ('company_id', '=', self.env.company.id),
            ], limit=1)
        if not picking_type:
            raise UserError(_('No se encontró un tipo de operación interna para realizar el traslado.'))
        return picking_type

    def _available_qty_in_location(self, location, product, lot):
        quants = self.env['stock.quant'].search([
            ('location_id', 'child_of', location.id),
            ('product_id', '=', product.id),
            ('lot_id', '=', lot.id),
            ('quantity', '>', 0),
            ('company_id', '=', self.env.company.id),
        ])
        return sum(quants.mapped('quantity'))

    def _create_and_validate_picking(self, source, dest, origin_label):
        self.ensure_one()
        picking_type = self._get_internal_picking_type(source, dest)
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': source.id,
            'location_dest_id': dest.id,
            'origin': origin_label,
            'note': self.note or '',
        })
        move = self.env['stock.move'].create({
            'description_picking': self.product_id.display_name or self.product_id.name,
            'picking_id': picking.id,
            'product_id': self.product_id.id,
            'product_uom': self.product_id.uom_id.id,
            'product_uom_qty': self.quantity,
            'location_id': source.id,
            'location_dest_id': dest.id,
        })
        self.env['stock.move.line'].create({
            'move_id': move.id,
            'picking_id': picking.id,
            'product_id': self.product_id.id,
            'product_uom_id': self.product_id.uom_id.id,
            'location_id': source.id,
            'location_dest_id': dest.id,
            'lot_id': self.lot_id.id,
            'qty_done': self.quantity,
        })
        picking.action_confirm()
        picking.action_assign()
        validate_res = picking.button_validate()
        if isinstance(validate_res, dict) and validate_res.get('type'):
            return picking, validate_res
        return picking, False

    def action_confirm_assignment(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Solo puede confirmar asignaciones en borrador.'))
            if not rec.employee_id:
                raise UserError(_('Debe seleccionar el empleado a asignar.'))
            if rec.quantity <= 0:
                raise UserError(_('La cantidad debe ser mayor a cero.'))
            if rec.lot_id.product_id.id != rec.product_id.id:
                raise UserError(_('El serial no corresponde al producto seleccionado.'))
            active_for_lot = self.search([
                ('id', '!=', rec.id),
                ('lot_id', '=', rec.lot_id.id),
                ('state', '=', 'assigned'),
            ], limit=1)
            if active_for_lot:
                raise UserError(_('Este serial ya está asignado en otro registro activo.'))

            source = rec._find_exist_location()
            if not source:
                raise UserError(_('No se encontró la ubicación Supp/Existencias.'))
            dest = rec._find_or_create_assigned_location()
            available = rec._available_qty_in_location(source, rec.product_id, rec.lot_id)
            if rec.quantity > available:
                raise UserError(_(
                    'No hay cantidad suficiente del serial en Existencias.\n'
                    'Disponible: %(avail)s / Solicitado: %(req)s'
                ) % {'avail': available, 'req': rec.quantity})

            picking, validate_res = rec._create_and_validate_picking(
                source, dest, _('Asignación Supplies %s') % rec.name
            )
            rec.write({
                'source_location_id': source.id,
                'destination_location_id': dest.id,
                'assignment_picking_id': picking.id,
                'assignment_date': fields.Datetime.now(),
                'delivery_user_id': rec.delivery_user_id.id or self.env.user.id,
                'signature_state': 'pending',
                'state': 'assigned',
            })
            if validate_res:
                return validate_res

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Asignación confirmada'),
                'message': _('El producto quedó asignado y salió de Existencias.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_return_assignment(self):
        for rec in self:
            if rec.state != 'assigned':
                raise UserError(_('Solo puede devolver asignaciones en estado asignado.'))
            missing = []
            if not rec.return_signature_delivery:
                missing.append(_('Entrega'))
            if not rec.return_signature_receiver:
                missing.append(_('Recibe'))
            if missing:
                raise UserError(_(
                    'Para cerrar la devolución, el acta debe tener las firmas de devolución obligatorias. '
                    'Falta(n): %s'
                ) % ', '.join(missing))
            source = rec.destination_location_id or rec._find_or_create_assigned_location()
            dest = rec.source_location_id or rec._find_exist_location()
            if not source or not dest:
                raise UserError(_('No se pudieron resolver ubicaciones de devolución.'))
            available = rec._available_qty_in_location(source, rec.product_id, rec.lot_id)
            if rec.quantity > available:
                raise UserError(_(
                    'No hay cantidad suficiente del serial en ubicación de asignados.\n'
                    'Disponible: %(avail)s / Solicitado: %(req)s'
                ) % {'avail': available, 'req': rec.quantity})

            picking, validate_res = rec._create_and_validate_picking(
                source, dest, _('Devolución Asignación Supplies %s') % rec.name
            )
            rec.write({
                'return_picking_id': picking.id,
                'return_date': fields.Datetime.now(),
                'return_pending_signature': False,
                'state': 'returned',
            })
            if validate_res:
                return validate_res

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Devolución confirmada'),
                'message': _('El producto volvió a Existencias y quedó disponible.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_open_supplies_hub(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/inventory_dashboard_simple/supplies_hub',
            'target': 'self',
        }
