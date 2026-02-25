# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class LicenseEquipment(models.Model):
    _name = 'license.equipment'
    _description = 'Asignación de Licencia a Equipo'
    _order = 'assignment_id, lot_id'

    assignment_id = fields.Many2one(
        'license.assignment',
        string='Asignación de Licencia',
        required=True,
        ondelete='cascade',
        index=True
    )
    license_id = fields.Many2one(
        'license.template',
        related='assignment_id.license_id',
        string='Licencia',
        store=True,
        readonly=True
    )
    # Campos para visibilidad en vista (desde configuración de la licencia)
    license_applies_to_equipment = fields.Boolean(
        related='license_id.applies_to_equipment',
        string='Licencia aplica a equipo',
        readonly=True
    )
    license_applies_to_user = fields.Boolean(
        related='license_id.applies_to_user',
        string='Licencia aplica a usuario',
        readonly=True
    )
    partner_id = fields.Many2one(
        'res.partner',
        related='assignment_id.partner_id',
        string='Cliente',
        store=True,
        readonly=True
    )
    contracting_type = fields.Selection(
        related='assignment_id.contracting_type',
        string='Tipo de Contratación',
        store=False,
        readonly=True
    )
    contact_id = fields.Many2one(
        'res.partner',
        string='Contacto',
        required=False,
        domain="[('parent_id', '=', partner_id), ('is_company', '=', False)]",
        help='Contacto relacionado de la empresa al que se asigna la licencia (opcional)'
    )
    location_id = fields.Many2one(
        'stock.location',
        related='assignment_id.location_id',
        string='Ubicación',
        store=True,
        readonly=True
    )
    lot_id = fields.Many2one(
        'stock.lot',
        string='Equipo (Lote/Serie)',
        required=False,
        domain="[('id', 'in', available_lot_ids)]",
        help='Equipo específico al que se asigna la licencia (opcional). Solo muestra equipos con categoría COMPUTO.'
    )
    available_lot_ids = fields.Many2many(
        'stock.lot',
        string='Lotes Disponibles',
        compute='_compute_available_lot_ids',
        store=False,
        help='Lotes disponibles en la ubicación del cliente'
    )
    product_id = fields.Many2one(
        'product.product',
        related='lot_id.product_id',
        string='Producto del Equipo',
        store=True,
        readonly=True
    )
    inventory_plate = fields.Char(
        related='lot_id.inventory_plate',
        string='Placa de Inventario',
        store=True,
        readonly=True,
        help='Placa de inventario del equipo asignado'
    )
    # Usuario asignado: si hay equipo (lot_id), muestra el Usuario del lote (related_partner_id); si no, el contacto de la línea
    assigned_partner_id = fields.Many2one(
        'res.partner',
        string='Asignado',
        compute='_compute_assigned_partner_id',
        store=True,
        readonly=True,
        help='Usuario del equipo (desde el lote) o contacto asignado a la licencia'
    )
    # Equipo a mostrar: si hay lot_id lo muestra; si es fila de usuario (contact_id), muestra el equipo relacionado al usuario (lote con related_partner_id = contact_id)
    display_lot_id = fields.Many2one(
        'stock.lot',
        string='Equipo',
        compute='_compute_display_lot_id',
        store=True,
        readonly=True,
        help='Equipo de la línea o equipo relacionado al usuario asignado'
    )
    service_product_id = fields.Many2one(
        'product.product',
        related='license_id.product_id',
        string='Servicio',
        store=True,
        readonly=True,
        help='Servicio asociado a la licencia (ej: Microsoft 365 Empresa Estándar)'
    )
    assignment_date = fields.Date(
        string='Fecha de Asignación',
        required=True,
        help='Debe coincidir con la fecha de inicio del contrato.'
    )
    unassignment_date = fields.Date(string='Fecha de Desasignación')
    assignment_end_date = fields.Date(
        related='assignment_id.end_date',
        string='Fecha de Fin (contrato)',
        readonly=True,
        help='Fecha de terminación del contrato de la asignación.'
    )
    state = fields.Selection([
        ('assigned', 'Asignado'),
        ('unassigned', 'Desasignado'),
    ], string='Estado', default='assigned', required=True)
    notes = fields.Text(string='Notas')
    
    # Campo computed para indicar el tipo de asignación
    assignment_type = fields.Selection([
        ('user', 'Por Usuario'),
        ('equipment', 'Por Equipo'),
        ('both', 'Por Usuario y Equipo'),
    ], string='Tipo de Asignación',
       compute='_compute_assignment_type',
       store=False,
       help='Indica si la licencia está asignada por usuario, por equipo, o ambos')
    
    @api.depends('contact_id', 'lot_id')
    def _compute_assigned_partner_id(self):
        """Muestra el usuario del equipo (related_partner_id del lote) o el contacto de la línea."""
        for rec in self:
            if rec.lot_id and getattr(rec.lot_id, 'related_partner_id', None):
                rec.assigned_partner_id = rec.lot_id.related_partner_id
            else:
                rec.assigned_partner_id = rec.contact_id

    @api.depends('contact_id', 'lot_id')
    def _compute_display_lot_id(self):
        """Muestra el equipo de la línea (lot_id) o, si es usuario, el primer equipo relacionado a ese usuario (lote con related_partner_id = contact_id)."""
        for rec in self:
            if rec.lot_id:
                rec.display_lot_id = rec.lot_id
            elif rec.contact_id and hasattr(self.env['stock.lot'], 'related_partner_id'):
                lot = self.env['stock.lot'].search(
                    [('related_partner_id', '=', rec.contact_id.id)],
                    limit=1,
                    order='id desc'
                )
                rec.display_lot_id = lot
            else:
                rec.display_lot_id = False

    @api.depends('contact_id', 'lot_id')
    def _compute_assignment_type(self):
        """Calcula el tipo de asignación según si hay usuario, equipo o ambos"""
        for rec in self:
            has_user = bool(rec.contact_id)
            has_equipment = bool(rec.lot_id)
            
            if has_user and has_equipment:
                rec.assignment_type = 'both'
            elif has_user:
                rec.assignment_type = 'user'
            elif has_equipment:
                rec.assignment_type = 'equipment'
            else:
                # Si no hay ni usuario ni equipo, dejar vacío (None)
                rec.assignment_type = None

    unique_lot_assignment = models.Constraint(
        'unique(assignment_id, lot_id, state)',
        'Este equipo ya está asignado a esta licencia. Solo puede haber una asignación activa por equipo.',
    )
    unique_contact_license_assigned = models.Constraint(
        "unique(contact_id, license_id) WHERE state = 'assigned'",
        'Este contacto ya tiene una asignación activa de este tipo de licencia. No se puede duplicar.',
    )

    @api.depends('location_id')
    def _compute_available_lot_ids(self):
        """Calcula los lotes disponibles en la ubicación del cliente con categoría COMPUTO"""
        for rec in self:
            rec.available_lot_ids = [(5, 0, 0)]  # Limpiar
            if rec.location_id:
                # Buscar categoría de activo "COMPUTO"
                computo_category = self.env['product.asset.category'].search([
                    ('name', '=', 'COMPUTO')
                ], limit=1)
                
                # Buscar lotes que tengan quants en la ubicación del cliente
                quants = self.env['stock.quant'].search([
                    ('location_id', 'child_of', rec.location_id.id),
                    ('lot_id', '!=', False),
                    ('quantity', '>', 0)
                ])
                
                # Filtrar lotes que tengan productos con categoría COMPUTO
                lot_ids = []
                for quant in quants:
                    if quant.lot_id and quant.lot_id.product_id:
                        product = quant.lot_id.product_id
                        # Verificar si el producto tiene categoría COMPUTO
                        if computo_category and product.asset_category_id and product.asset_category_id.id == computo_category.id:
                            if quant.lot_id.id not in lot_ids:
                                lot_ids.append(quant.lot_id.id)
                
                if lot_ids:
                    rec.available_lot_ids = [(6, 0, lot_ids)]

    @api.onchange('assignment_id')
    def _onchange_assignment_id(self):
        """Limpia el contacto y recalcula lotes disponibles cuando cambia la asignación"""
        if self.assignment_id:
            # El partner_id y location_id se actualizan automáticamente por ser related
            # Limpiar contact_id para que el usuario seleccione uno nuevo
            self.contact_id = False
            # Recalcular lotes disponibles
            self._compute_available_lot_ids()

    @api.constrains('contact_id', 'lot_id', 'license_id', 'state')
    def _check_license_applies_to(self):
        """Exige Contacto o Equipo según la configuración de la licencia (applies_to_user / applies_to_equipment)."""
        for rec in self:
            if not rec.license_id or rec.state == 'unassigned':
                continue
            applies_eq = rec.license_id.applies_to_equipment
            applies_usr = rec.license_id.applies_to_user
            has_contact = bool(rec.contact_id)
            has_lot = bool(rec.lot_id)
            if applies_eq and not applies_usr:
                if not has_lot:
                    raise ValidationError(
                        _('La licencia "%s" está configurada solo para Equipo. Debe seleccionar un Equipo (Lote/Serie).')
                        % (rec.license_id.display_name or rec.license_id.code)
                    )
            elif applies_usr and not applies_eq:
                if not has_contact:
                    raise ValidationError(
                        _('La licencia "%s" está configurada solo para Usuario. Debe seleccionar un Contacto.')
                        % (rec.license_id.display_name or rec.license_id.code)
                    )
            elif applies_eq and applies_usr:
                if not has_contact and not has_lot:
                    raise ValidationError(
                        _('La licencia "%s" aplica para Equipo y Usuario. Debe indicar al menos un Contacto o un Equipo (Lote/Serie).')
                        % (rec.license_id.display_name or rec.license_id.code)
                    )
            else:
                if not has_contact and not has_lot:
                    raise ValidationError(
                        _('Configure la licencia "%s" en Licenciamientos: marque "Aplica para Equipo" y/o "Aplica para Usuario", e indique al menos un Contacto o un Equipo aquí.')
                        % (rec.license_id.display_name or rec.license_id.code)
                    )

    @api.constrains('contact_id', 'license_id', 'state')
    def _check_unique_contact_license(self):
        """Valida que no haya duplicados: mismo contacto + mismo tipo de licencia en estado assigned"""
        for rec in self:
            if rec.state == 'assigned' and rec.contact_id and rec.license_id:
                existing = self.search([
                    ('contact_id', '=', rec.contact_id.id),
                    ('license_id', '=', rec.license_id.id),
                    ('state', '=', 'assigned'),
                    ('id', '!=', rec.id)
                ], limit=1)
                if existing:
                    raise ValidationError(
                        _('El contacto %s ya tiene una asignación activa de la licencia %s. '
                          'No se puede crear una asignación duplicada.')
                        % (rec.contact_id.name, rec.license_id.name)
                    )

    @api.constrains('lot_id', 'location_id')
    def _check_lot_location(self):
        """Verifica que el lote esté en la ubicación del cliente"""
        for rec in self:
            if rec.lot_id and rec.location_id:
                # Verificar que el lote tenga quants en la ubicación
                quants = self.env['stock.quant'].search([
                    ('lot_id', '=', rec.lot_id.id),
                    ('location_id', 'child_of', rec.location_id.id),
                    ('quantity', '>', 0)
                ])
                if not quants:
                    raise ValidationError(
                        _('El equipo %s no se encuentra en la ubicación %s.')
                        % (rec.lot_id.name, rec.location_id.complete_name)
                    )

    def action_unassign(self):
        """Desasigna el equipo de la licencia"""
        for rec in self:
            if rec.state == 'unassigned':
                continue
            rec.unassignment_date = fields.Date.today()
            rec.state = 'unassigned'
            # Mostrar mensaje informativo si es contrato anual
            if rec.assignment_id and rec.assignment_id.state == 'active':
                if rec.contracting_type in ('annual_monthly_commitment', 'annual'):
                    contracting_type_name = dict(rec.assignment_id._fields['contracting_type'].selection).get(rec.contracting_type, rec.contracting_type)
                    item_name = rec.lot_id.name if rec.lot_id else (rec.contact_id.name if rec.contact_id else _('elemento'))
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Asignación quitada'),
                            'message': _(
                                '✅ Se ha quitado la asignación del %s "%s" del listado.\n\n'
                                '📋 <strong>La cantidad de licencias (%d) se mantiene</strong> por el contrato "%s".\n\n'
                                '💡 Puedes asignar otro equipo o usuario en su lugar, pero la cantidad total de licencias no se reducirá durante el período del contrato.'
                            ) % (
                                _('equipo') if rec.lot_id else _('usuario'),
                                item_name,
                                rec.assignment_id.quantity,
                                contracting_type_name
                            ),
                            'type': 'warning',
                            'sticky': True,
                        }
                    }
    
    def unlink(self):
        """Sobrescribe unlink para mostrar mensaje informativo al eliminar en contratos anuales."""
        # Guardar información antes de eliminar para el mensaje
        items_to_delete = []
        for rec in self:
            if rec.assignment_id and rec.assignment_id.state == 'active':
                if rec.contracting_type in ('annual_monthly_commitment', 'annual'):
                    item_name = rec.lot_id.name if rec.lot_id else (rec.contact_id.name if rec.contact_id else _('elemento'))
                    item_type = _('equipo') if rec.lot_id else _('usuario')
                    items_to_delete.append({
                        'name': item_name,
                        'type': item_type,
                        'assignment': rec.assignment_id,
                        'contracting_type': rec.contracting_type,
                    })
        
        # Eliminar los registros
        result = super().unlink()
        
        # Mostrar mensaje informativo si se eliminaron elementos en contratos anuales
        if items_to_delete:
            # Agrupar por asignación para mostrar un mensaje por asignación
            assignments_info = {}
            for item in items_to_delete:
                assignment_id = item['assignment'].id
                if assignment_id not in assignments_info:
                    assignments_info[assignment_id] = {
                        'assignment': item['assignment'],
                        'contracting_type': item['contracting_type'],
                        'items': []
                    }
                assignments_info[assignment_id]['items'].append(item)
            
            # Mostrar un mensaje por cada asignación afectada
            for assignment_id, info in assignments_info.items():
                contracting_type_name = dict(info['assignment']._fields['contracting_type'].selection).get(info['contracting_type'], info['contracting_type'])
                items_text = ', '.join([f"{item['type']} \"{item['name']}\"" for item in info['items']])
                if len(info['items']) == 1:
                    item_text = info['items'][0]
                    message = _(
                        '✅ Se ha eliminado la asignación del %s "%s" del listado.\n\n'
                        '📋 <strong>La cantidad de licencias (%d) se mantiene</strong> por el contrato "%s".\n\n'
                        '💡 Puedes asignar otro equipo o usuario en su lugar, pero la cantidad total de licencias no se reducirá durante el período del contrato.'
                    ) % (
                        item_text['type'],
                        item_text['name'],
                        info['assignment'].quantity,
                        contracting_type_name
                    )
                else:
                    message = _(
                        '✅ Se han eliminado las asignaciones de: %s del listado.\n\n'
                        '📋 <strong>La cantidad de licencias (%d) se mantiene</strong> por el contrato "%s".\n\n'
                        '💡 Puedes asignar otros equipos o usuarios en su lugar, pero la cantidad total de licencias no se reducirá durante el período del contrato.'
                    ) % (
                        items_text,
                        info['assignment'].quantity,
                        contracting_type_name
                    )
                
                # Mostrar notificación (solo la primera para evitar spam)
                if assignment_id == list(assignments_info.keys())[0]:
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Asignaciones eliminadas'),
                            'message': message,
                            'type': 'warning',
                            'sticky': True,
                        }
                    }
        
        return result

    def action_open_delete_wizard(self):
        """Abre el wizard de confirmación para eliminar el equipo/usuario."""
        self.ensure_one()
        # Validar que el registro existe
        if not self.exists():
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('El registro ya no existe o fue eliminado.'),
                    'type': 'danger',
                    'sticky': True,
                }
            }
        # Guardar el ID antes de crear el wizard para evitar problemas de contexto
        equipment_id = self.id
        return {
            'name': _('Confirmar Eliminación'),
            'type': 'ir.actions.act_window',
            'res_model': 'license.equipment.delete.warning.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_equipment_id': equipment_id,
                'active_id': equipment_id,
            }
        }

    def _default_assignment_date(self, assignment):
        """Fecha de asignación: inicio de contrato, o el día de hoy si se agrega después (ej. contrato en enero, agregó equipo el 27)."""
        today = fields.Date.context_today(self)
        if not assignment or not assignment.start_date:
            return today
        # Si hoy es posterior al inicio del contrato, usar hoy (día en que se asigna); si no, usar inicio del contrato
        return max(assignment.start_date, today)

    @api.model
    def default_get(self, fields_list):
        """Fecha de asignación = fecha de inicio del contrato, o hoy si se agrega después del inicio."""
        res = super().default_get(fields_list)
        assignment_id = self.env.context.get('default_assignment_id') or self.env.context.get('assignment_id')
        if assignment_id and 'assignment_date' in fields_list and 'assignment_date' not in res:
            assignment = self.env['license.assignment'].browse(assignment_id)
            res['assignment_date'] = self._default_assignment_date(assignment)
        elif 'assignment_date' in fields_list and 'assignment_date' not in res:
            res['assignment_date'] = fields.Date.context_today(self)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        """Sobrescribe create para actualizar fecha de inicio de la asignación cuando se asignan equipos/usuarios."""
        for vals in vals_list:
            if 'assignment_date' not in vals and vals.get('assignment_id'):
                assignment = self.env['license.assignment'].browse(vals['assignment_id'])
                vals['assignment_date'] = self._default_assignment_date(assignment)
        records = super().create(vals_list)
        # Actualizar fecha de inicio de la asignación si es necesario
        for rec in records:
            rec._update_assignment_start_date()
        # Validar que equipos/usuarios no superen la cantidad de licencias de la asignación
        for assignment in records.mapped('assignment_id'):
            assignment._check_equipment_quantity()
        return records

    def write(self, vals):
        """Sobrescribe write para actualizar fecha de inicio de la asignación cuando se asignan equipos/usuarios."""
        result = super().write(vals)
        # Si se cambió assignment_date o state a 'assigned', actualizar fecha de inicio
        if 'assignment_date' in vals or (vals.get('state') == 'assigned'):
            for rec in self:
                rec._update_assignment_start_date()
        # Si cambió algo que afecta el conteo (equipos/usuarios), validar que no se exceda la cantidad de licencias
        if any(k in vals for k in ('assignment_id', 'contact_id', 'lot_id', 'state')):
            for assignment in self.mapped('assignment_id'):
                assignment._check_equipment_quantity()
        return result

    def _update_assignment_start_date(self):
        """Actualiza la fecha de inicio de la asignación solo si aún no está definida.

        - Para contratos anuales, si la asignación NO tiene start_date, se toma la fecha
          del día que se asigna el primer equipo/usuario.
        - Si el usuario ya definió manualmente la fecha de inicio, NO se vuelve a tocar.
        """
        for rec in self:
            assignment = rec.assignment_id
            if not assignment:
                continue

            # Solo aplicar a contratos anuales
            if assignment.contracting_type not in ('annual_monthly_commitment', 'annual'):
                continue

            # Si ya hay fecha de inicio definida (por el usuario), no la tocamos
            if assignment.start_date:
                continue

            # Solo actualizar si este es el primer equipo/usuario asignado (no hay otros asignados antes)
            assigned_items = assignment.equipment_ids.filtered(
                lambda e: e.state == 'assigned' and e.assignment_date and e.id != rec.id
            )
            
            # Si este es el primer equipo/usuario asignado (no hay otros), usar su fecha de asignación
            if not assigned_items and rec.state == 'assigned' and rec.assignment_date:
                from dateutil.relativedelta import relativedelta
                assignment.start_date = rec.assignment_date
                # Calcular fecha de fin automáticamente (12 meses desde la fecha de inicio)
                assignment.end_date = rec.assignment_date + relativedelta(months=12) - relativedelta(days=1)

    def action_reassign(self):
        """Reasigna el equipo a la licencia"""
        for rec in self:
            if rec.state == 'assigned':
                continue
            # Validar que no haya duplicados antes de reasignar
            if rec.contact_id and rec.license_id:
                existing = self.search([
                    ('contact_id', '=', rec.contact_id.id),
                    ('license_id', '=', rec.license_id.id),
                    ('state', '=', 'assigned'),
                    ('id', '!=', rec.id)
                ], limit=1)
                if existing:
                    raise ValidationError(
                        _('El contacto %s ya tiene una asignación activa de la licencia %s. '
                          'No se puede reasignar esta asignación.')
                        % (rec.contact_id.name, rec.license_id.name)
                    )
            rec.unassignment_date = False
            rec.state = 'assigned'
            # Misma regla: inicio de contrato, o hoy si se reasigna después
            rec.assignment_date = self._default_assignment_date(rec.assignment_id)
            # Actualizar fecha de inicio de la asignación
            rec._update_assignment_start_date()

    def name_get(self):
        result = []
        for rec in self:
            name = f"{rec.license_id.code if rec.license_id else ''} - {rec.lot_id.name if rec.lot_id else 'Sin equipo'}"
            result.append((rec.id, name))
        return result

