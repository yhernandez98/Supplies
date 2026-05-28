# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_is_zero


class ComponentTransferWizard(models.TransientModel):
    _name = 'component.transfer.wizard'
    _description = 'Wizard de traslado bidireccional de componentes'

    operation_type = fields.Selection(
        [
            ('lab_to_prep', 'Laboratorio (Existencias -> Alistamiento)'),
            ('prep_to_exist', 'Entrega Inventario (Alistamiento -> Existencias)'),
            ('exist_to_lab', 'Laboratorio (Existencias -> Supp/Laboratorio)'),
        ],
        string='Tipo de traslado',
        required=True,
        default='lab_to_prep',
    )

    source_location_id = fields.Many2one(
        'stock.location',
        string='Ubicación origen',
        compute='_compute_locations',
        readonly=True,
        store=False,
    )
    destination_location_id = fields.Many2one(
        'stock.location',
        string='Ubicación destino',
        compute='_compute_locations',
        readonly=True,
        store=False,
    )

    available_lot_ids = fields.Many2many(
        'stock.lot',
        string='Seriales disponibles',
        compute='_compute_available_lot_ids',
        store=False,
    )
    available_product_ids = fields.Many2many(
        'product.product',
        string='Productos disponibles',
        compute='_compute_available_product_ids',
        store=False,
    )

    line_ids = fields.One2many(
        'component.transfer.wizard.line',
        'wizard_id',
        string='Líneas a trasladar',
    )

    note = fields.Text(string='Nota')
    responsible_user_id = fields.Many2one(
        'res.users',
        string='Responsable',
        domain=[('share', '=', False)],
        help='Usuario interno responsable del traslado hacia laboratorio.',
    )
    loan_source_picking_id = fields.Many2one(
        'stock.picking',
        string='Préstamo a cerrar (salida lab.)',
        domain=(
            "['&', '&', ('component_lab_loan_active', '=', True), ('state', '=', 'done'), "
            "'|', ('lab_responsible_user_id', '=', uid), ('lab_technician_user_id', '=', uid)]"
        ),
        help='Al validar la devolución en inventario, el préstamo quedará pendiente de aprobación del responsable (lab.). '
             'Al elegirlo aquí, se rellenan solos producto y serial según ese albarán. '
             'Solo aparecen préstamos donde usted es responsable o técnico asignado.',
    )

    def _get_transfer_locations(self):
        """Retorna ubicaciones base requeridas por el flujo."""
        Location = self.env['stock.location']
        # Buscar con varios intentos porque en algunas bases el complete_name puede variar
        # (prefijos, mayúsculas, raíz de almacén, etc.).
        exist = Location.search([
            ('complete_name', 'ilike', 'Supp/Existencias'),
        ], limit=1)
        if not exist:
            exist = Location.search([
                ('name', 'ilike', 'Existencias'),
                ('complete_name', 'ilike', 'Supp'),
            ], limit=1)
        if not exist:
            exist = Location.search([
                ('name', 'ilike', 'Existencias'),
            ], limit=1)

        prep = Location.search([
            ('complete_name', 'ilike', 'Supp/Alistamiento'),
        ], limit=1)
        if not prep:
            prep = Location.search([
                ('name', 'ilike', 'Alistamiento'),
                ('complete_name', 'ilike', 'Supp'),
            ], limit=1)
        if not prep:
            prep = Location.search([
                ('name', 'ilike', 'Alistamiento'),
            ], limit=1)

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
        return exist, prep, lab

    @api.depends('operation_type')
    def _compute_locations(self):
        exist, prep, lab = self._get_transfer_locations()
        for rec in self:
            rec.source_location_id = False
            rec.destination_location_id = False
            if rec.operation_type == 'lab_to_prep':
                rec.source_location_id = exist
                rec.destination_location_id = prep
            elif rec.operation_type == 'prep_to_exist':
                rec.source_location_id = prep
                rec.destination_location_id = exist
            elif rec.operation_type == 'exist_to_lab':
                rec.source_location_id = exist
                rec.destination_location_id = lab
            elif rec.operation_type == 'lab_to_exist':
                rec.source_location_id = lab
                rec.destination_location_id = exist

    @api.depends('operation_type')
    def _compute_available_lot_ids(self):
        Quant = self.env['stock.quant']
        Lot = self.env['stock.lot']
        for rec in self:
            rec.available_lot_ids = Lot
            source = rec.source_location_id
            if not source:
                continue
            quants = Quant.search([
                ('location_id', 'child_of', source.id),
                ('quantity', '>', 0),
                ('lot_id', '!=', False),
            ])
            rec.available_lot_ids = quants.mapped('lot_id')

    @api.depends('available_lot_ids')
    def _compute_available_product_ids(self):
        Product = self.env['product.product']
        for rec in self:
            rec.available_product_ids = Product
            if rec.available_lot_ids:
                rec.available_product_ids = rec.available_lot_ids.mapped('product_id')

    @api.onchange('operation_type')
    def _onchange_operation_type(self):
        for rec in self:
            rec.line_ids = [(5, 0, 0)]
            rec.loan_source_picking_id = False

    @api.onchange('loan_source_picking_id')
    def _onchange_loan_source_picking_id(self):
        """Rellena seriales/productos del préstamo al devolver (Lab. → Existencias)."""
        for rec in self:
            if rec.operation_type != 'lab_to_exist' or not rec.loan_source_picking_id:
                continue
            cmds = [(5, 0, 0)]
            by_lot = {}
            for sml in rec.loan_source_picking_id.move_line_ids.sorted(lambda ml: ml.id):
                if not sml.lot_id or not sml.product_id:
                    continue
                qty = sml.quantity
                rounding = sml.product_uom_id.rounding
                if float_is_zero(qty, precision_rounding=rounding):
                    continue
                lid = sml.lot_id.id
                if lid not in by_lot:
                    by_lot[lid] = {'product_id': sml.product_id.id, 'qty': 0.0, 'rounding': rounding}
                by_lot[lid]['qty'] += qty
            for lid, data in by_lot.items():
                if float_is_zero(data['qty'], precision_rounding=data['rounding']):
                    continue
                cmds.append((0, 0, {
                    'product_id': data['product_id'],
                    'lot_id': lid,
                    'quantity': data['qty'],
                }))
            if len(cmds) > 1:
                rec.line_ids = cmds
            else:
                # Préstamo sin líneas con serial en el albarán: dejar tabla vacía para agregar manual
                rec.line_ids = [(5, 0, 0)]

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

    def _get_or_create_lab_pool_picking_type(self, source, dest):
        """Tipo interno PROPIO para ingreso pool: evita reutilizar secuencias de Alistamiento."""
        self.ensure_one()
        PickingType = self.env['stock.picking.type']
        Sequence = self.env['ir.sequence']
        company = self.env.company

        # Reusar si ya existe uno creado para este flujo y compañía.
        picking_type = PickingType.search([
            ('code', '=', 'internal'),
            ('company_id', '=', company.id),
            ('default_location_src_id', '=', source.id),
            ('default_location_dest_id', '=', dest.id),
            ('name', '=', 'Laboratorio: Ingreso Pool'),
        ], limit=1)
        if picking_type:
            return picking_type

        # Secuencia propia (si no existe, se crea).
        seq = Sequence.search([
            ('code', '=', 'inventory_dashboard_simple.lab_pool_in'),
            ('company_id', '=', company.id),
        ], limit=1)
        if not seq:
            seq = Sequence.create({
                'name': 'Secuencia ingreso laboratorio (pool)',
                'code': 'inventory_dashboard_simple.lab_pool_in',
                'prefix': 'SUPP/LAB-IN/',
                'padding': 5,
                'implementation': 'no_gap',
                'company_id': company.id,
            })

        warehouse = self.env['stock.warehouse'].search([
            ('company_id', '=', company.id),
        ], limit=1)

        vals = {
            'name': 'Laboratorio: Ingreso Pool',
            'code': 'internal',
            'sequence_code': 'LABIN',
            'sequence_id': seq.id,
            'default_location_src_id': source.id,
            'default_location_dest_id': dest.id,
            'company_id': company.id,
        }
        if warehouse:
            vals['warehouse_id'] = warehouse.id

        return PickingType.create(vals)

    def _get_or_create_lab_return_picking_type(self, source, dest):
        """Tipo interno PROPIO para devolución Lab. -> Existencias."""
        self.ensure_one()
        PickingType = self.env['stock.picking.type']
        Sequence = self.env['ir.sequence']
        company = self.env.company

        picking_type = PickingType.search([
            ('code', '=', 'internal'),
            ('company_id', '=', company.id),
            ('default_location_src_id', '=', source.id),
            ('default_location_dest_id', '=', dest.id),
            ('name', '=', 'Laboratorio: Devolución a Existencias'),
        ], limit=1)
        if picking_type:
            return picking_type

        seq = Sequence.search([
            ('code', '=', 'inventory_dashboard_simple.lab_pool_out'),
            ('company_id', '=', company.id),
        ], limit=1)
        if not seq:
            seq = Sequence.create({
                'name': 'Secuencia devolución laboratorio (existencias)',
                'code': 'inventory_dashboard_simple.lab_pool_out',
                'prefix': 'SUPP/LAB-OUT/',
                'padding': 5,
                'implementation': 'no_gap',
                'company_id': company.id,
            })

        warehouse = self.env['stock.warehouse'].search([
            ('company_id', '=', company.id),
        ], limit=1)

        vals = {
            'name': 'Laboratorio: Devolución a Existencias',
            'code': 'internal',
            'sequence_code': 'LABOUT',
            'sequence_id': seq.id,
            'default_location_src_id': source.id,
            'default_location_dest_id': dest.id,
            'company_id': company.id,
        }
        if warehouse:
            vals['warehouse_id'] = warehouse.id

        return PickingType.create(vals)

    def action_process_transfer(self):
        self.ensure_one()
        source = self.source_location_id
        dest = self.destination_location_id
        if self.operation_type == 'exist_to_lab':
            if not self.responsible_user_id:
                raise UserError(_('Debe seleccionar un Responsable para el traslado Existencias -> Supp/Laboratorio.'))
        if self.operation_type == 'lab_to_exist' and self.loan_source_picking_id:
            p = self.loan_source_picking_id
            involved = {p.lab_responsible_user_id.id, p.lab_technician_user_id.id}
            involved.discard(False)
            if self.env.user.id not in involved:
                raise UserError(_(
                    'El préstamo %(picking)s no está asociado a su usuario como responsable ni técnico de laboratorio.'
                ) % {'picking': p.display_name})
        if not source or not dest:
            raise UserError(_(
                'No se encontraron las ubicaciones configuradas para el traslado.\n'
                'Se requiere localizar "Supp/Existencias", "Supp/Alistamiento" y "Supp/Laboratorio".'
            ))
        if not self.line_ids:
            raise UserError(_('Debe agregar al menos un serial para trasladar.'))

        Quant = self.env['stock.quant']
        seen_lot_ids = set()
        for line in self.line_ids:
            if not line.product_id:
                raise UserError(_('Todas las líneas deben tener producto seleccionado.'))
            if not line.lot_id:
                raise UserError(_('Todas las líneas deben tener serial seleccionado.'))
            if line.lot_id.product_id.id != line.product_id.id:
                raise UserError(_(
                    'El serial %(lot)s no corresponde al producto seleccionado %(prod)s.'
                ) % {
                    'lot': line.lot_id.name,
                    'prod': line.product_id.display_name,
                })
            if line.lot_id.id in seen_lot_ids:
                raise UserError(_('No puede repetir el mismo serial en varias líneas.'))
            seen_lot_ids.add(line.lot_id.id)
            if line.quantity <= 0:
                raise UserError(_('La cantidad debe ser mayor a cero.'))

            available_qty = sum(Quant.search([
                ('location_id', 'child_of', source.id),
                ('product_id', '=', line.product_id.id),
                ('lot_id', '=', line.lot_id.id),
                ('quantity', '>', 0),
            ]).mapped('quantity'))
            if line.quantity > available_qty:
                raise UserError(_(
                    'El serial %(lot)s no tiene cantidad suficiente en %(src)s.\n'
                    'Disponible: %(available)s / Solicitado: %(requested)s'
                ) % {
                    'lot': line.lot_id.name,
                    'src': source.display_name,
                    'available': available_qty,
                    'requested': line.quantity,
                })

        if self.operation_type == 'exist_to_lab':
            picking_type = self._get_or_create_lab_pool_picking_type(source, dest)
        elif self.operation_type == 'lab_to_exist':
            picking_type = self._get_or_create_lab_return_picking_type(source, dest)
        else:
            picking_type = self._get_internal_picking_type(source, dest)
        origin = _('Traslado componente')
        if self.operation_type == 'exist_to_lab':
            origin = _('Traslado lab.: Existencias → Laboratorio')
        elif self.operation_type == 'lab_to_exist':
            origin = _('Devolución lab.: Supp/Laboratorio → Existencias')
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': source.id,
            'location_dest_id': dest.id,
            'origin': origin,
            'note': self.note or '',
        })

        Move = self.env['stock.move']
        MoveLine = self.env['stock.move.line']
        for line in self.line_ids:
            move = Move.create({
                'description_picking': _('Traslado componente: %s') % (line.product_id.display_name or line.product_id.name),
                'picking_id': picking.id,
                'product_id': line.product_id.id,
                'product_uom': line.product_uom_id.id,
                'product_uom_qty': line.quantity,
                'location_id': source.id,
                'location_dest_id': dest.id,
            })
            MoveLine.create({
                'move_id': move.id,
                'picking_id': picking.id,
                'product_id': line.product_id.id,
                'product_uom_id': line.product_uom_id.id,
                'location_id': source.id,
                'location_dest_id': dest.id,
                'lot_id': line.lot_id.id,
                'qty_done': line.quantity,
            })

        picking.action_confirm()
        picking.action_assign()

        if self.operation_type == 'lab_to_exist' and self.loan_source_picking_id:
            loan_src = self.loan_source_picking_id
            picking.write({'component_lab_source_loan_picking_id': loan_src.id})
            loan_src.write({'component_lab_return_picking_id': picking.id})

        if self.operation_type == 'exist_to_lab':
            extra_note = _(
                'Responsable (lab.): %(resp)s\n'
                'Flujo pool: las filas en «Asignaciones laboratorio» se crean al validar este ingreso (validación inmediata).\n'
                'El material se asigna a técnicos desde el menú del laboratorio; la devolución del técnico no mueve Existencias; '
                'solo el responsable devuelve a Existencias con el wizard correspondiente.\n'
                'Seguimiento legado de préstamos: menú «Seguimiento préstamos lab.».'
            ) % {
                'resp': self.responsible_user_id.display_name,
            }
            full_note = '\n\n'.join([p for p in [picking.note, extra_note] if p])
            picking.write({
                'note': full_note,
                'component_lab_temp_out': True,
                'component_lab_pool_intake': True,
                'lab_responsible_user_id': self.responsible_user_id.id,
            })

        validate_res = picking.button_validate()
        if isinstance(validate_res, dict) and validate_res.get('type'):
            return validate_res

        msg = _('Se procesó el traslado de %s serial(es).') % len(self.line_ids)
        if self.operation_type == 'exist_to_lab':
            msg = _(
                'Ingreso a laboratorio validado (%(picking)s). %(n)s serial(es) ya figuran en el pool.'
            ) % {'picking': picking.name, 'n': len(self.line_ids)}
        if self.operation_type == 'lab_to_exist' and self.loan_source_picking_id:
            resp = self.loan_source_picking_id.lab_responsible_user_id
            msg += '\n' + _(
                'El préstamo quedará en fase «Devuelto (pendiente aprobación responsable)» hasta que %(name)s '
                'abra el albarán de salida y pulse «Aprobar cierre de préstamo (responsable)».'
            ) % {'name': resp.display_name if resp else _('el responsable de laboratorio')}
        if self.operation_type == 'lab_to_exist' and not self.loan_source_picking_id:
            msg += '\n' + _(
                'No enlazó un préstamo: el seguimiento de préstamos activos no se cerrará automáticamente. '
                'En la próxima devolución use el campo "Préstamo a cerrar".'
            )

        title = _('Traslado realizado')
        if self.operation_type == 'exist_to_lab':
            title = _('Ingreso a laboratorio validado')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': msg,
                'type': 'success',
                'sticky': bool(self.operation_type == 'lab_to_exist'),
            }
        }


class ComponentTransferWizardLine(models.TransientModel):
    _name = 'component.transfer.wizard.line'
    _description = 'Línea de traslado de componente'

    wizard_id = fields.Many2one(
        'component.transfer.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        required=True,
        domain="[('id', 'in', available_product_ids)]",
        help='Primero seleccione el producto disponible en la ubicación origen.',
    )
    lot_id = fields.Many2one(
        'stock.lot',
        string='Serial',
        required=True,
        domain="[('id', 'in', available_lot_ids), ('product_id', '=', product_id)]",
        help='Seleccione el serial del producto elegido.',
    )
    available_lot_ids = fields.Many2many(
        'stock.lot',
        related='wizard_id.available_lot_ids',
        readonly=True,
        store=False,
    )
    available_product_ids = fields.Many2many(
        'product.product',
        related='wizard_id.available_product_ids',
        readonly=True,
        store=False,
    )
    product_uom_id = fields.Many2one(
        'uom.uom',
        string='Unidad',
        related='product_id.uom_id',
        readonly=True,
    )
    available_qty = fields.Float(
        string='Disponible en origen',
        compute='_compute_available_qty',
        store=False,
        readonly=True,
    )
    quantity = fields.Float(
        string='Cantidad a trasladar',
        default=1.0,
        required=True,
    )

    @api.depends('lot_id', 'product_id', 'wizard_id.source_location_id')
    def _compute_available_qty(self):
        Quant = self.env['stock.quant']
        for rec in self:
            rec.available_qty = 0.0
            if not rec.lot_id or not rec.product_id or not rec.wizard_id.source_location_id:
                continue
            quants = Quant.search([
                ('location_id', 'child_of', rec.wizard_id.source_location_id.id),
                ('product_id', '=', rec.product_id.id),
                ('lot_id', '=', rec.lot_id.id),
                ('quantity', '>', 0),
            ])
            rec.available_qty = sum(quants.mapped('quantity'))

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for rec in self:
            rec.lot_id = False
            rec.quantity = 1.0

    @api.onchange('lot_id')
    def _onchange_lot_id(self):
        for rec in self:
            if not rec.lot_id:
                continue
            rec.product_id = rec.lot_id.product_id
            rec.quantity = rec.available_qty or 1.0

    @api.constrains('quantity')
    def _check_quantity_positive(self):
        for rec in self:
            if rec.quantity <= 0:
                raise ValidationError(_('La cantidad debe ser mayor a cero.'))

