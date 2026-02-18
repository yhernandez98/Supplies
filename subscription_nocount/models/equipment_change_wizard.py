# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime


class EquipmentChangeWizard(models.TransientModel):
    _name = 'subscription.equipment.change.wizard'
    _description = 'Wizard para cambio de equipo en suscripción'
    
    # Forzar contexto en todos los Many2one de stock.lot cuando se usan desde este wizard
    @api.model
    def _get_default_context(self):
        """Retorna el contexto por defecto para los campos Many2one de stock.lot."""
        return {
            'equipment_change_wizard': True,
            'search_by_inventory_plate_only': True,
        }
    
    @api.model
    def read(self, fields=None, load='_classic_read'):
        """Sobrescribe read para forzar el contexto en los campos Many2one de stock.lot."""
        # Forzar el contexto antes de leer
        self = self.with_context(
            equipment_change_wizard=True,
            search_by_inventory_plate_only=True,
            active_model='subscription.equipment.change.wizard',
        )
        return super(EquipmentChangeWizard, self).read(fields=fields, load=load)
    
    @api.model
    def fields_get(self, allfields=None, attributes=None):
        """Sobrescribe fields_get para forzar el contexto en los campos Many2one de stock.lot."""
        result = super(EquipmentChangeWizard, self).fields_get(allfields=allfields, attributes=attributes)
        
        # Forzar el contexto en los campos Many2one de stock.lot
        for field_name in ['old_equipment_lot_id', 'new_equipment_lot_id', 'old_equipment_inventory_plate_search', 'new_equipment_inventory_plate_search']:
            if field_name in result:
                # Asegurar que el contexto esté presente en la definición del campo
                if 'context' not in result[field_name]:
                    result[field_name]['context'] = {}
                elif not isinstance(result[field_name]['context'], dict):
                    result[field_name]['context'] = {}
                
                # Forzar los valores del contexto
                result[field_name]['context'].update({
                    'equipment_change_wizard': True,
                    'search_by_inventory_plate_only': True,
                    'active_model': 'subscription.equipment.change.wizard',
                })
        
        return result

    subscription_id = fields.Many2one(
        'subscription.subscription',
        string='Suscripción',
        required=True,
        readonly=True,
    )
    
    partner_id = fields.Many2one(
        related='subscription_id.partner_id',
        string='Cliente',
        readonly=True,
    )
    
    customer_location_id = fields.Many2one(
        related='subscription_id.location_id',
        string='Ubicación del Cliente',
        readonly=True,
    )
    
    old_equipment_inventory_plate_search = fields.Many2one(
        'stock.lot',
        string='Placa de Inventario',
        domain="[('id', 'in', available_old_equipment_ids), ('inventory_plate', '!=', False)]",
        help='Busque y seleccione la placa de inventario del equipo que desea cambiar. La búsqueda se realiza por el campo inventory_plate. Solo se muestran equipos en la ubicación del cliente que tienen placa de inventario.',
        context="{'equipment_change_wizard': True, 'search_by_inventory_plate_only': True, 'active_model': 'subscription.equipment.change.wizard'}",
    )
    
    old_equipment_lot_id = fields.Many2one(
        'stock.lot',
        string='Serial Seleccionado',
        required=True,
        domain="[('id', 'in', available_old_equipment_ids), ('inventory_plate', '!=', False)]",
        help='Serial del equipo seleccionado.',
        readonly=True,
        invisible="not old_equipment_inventory_plate_search",
    )
    
    old_equipment_inventory_plate = fields.Char(
        related='old_equipment_lot_id.inventory_plate',
        string='Placa del Equipo Viejo',
        readonly=True,
    )
    
    old_equipment_name = fields.Char(
        related='old_equipment_lot_id.name',
        string='Número de Serie del Equipo Viejo',
        readonly=True,
    )
    
    old_equipment_product_id = fields.Many2one(
        related='old_equipment_lot_id.product_id',
        string='Producto del Equipo Viejo',
        readonly=True,
    )
    
    old_equipment_supply_line_ids = fields.One2many(
        related='old_equipment_lot_id.lot_supply_line_ids',
        string='Elementos Asociados del Equipo Viejo',
        readonly=True,
    )
    
    available_old_equipment_ids = fields.Many2many(
        'stock.lot',
        compute='_compute_available_equipment',
        string='Equipos Disponibles en Ubicación del Cliente',
    )
    
    new_equipment_inventory_plate_search = fields.Many2one(
        'stock.lot',
        string='Buscar por Placa de Inventario',
        domain="[('id', 'in', available_new_equipment_ids), ('inventory_plate', '!=', False)]",
        help='Busque y seleccione la placa de inventario del equipo nuevo. La búsqueda se realiza por el campo inventory_plate. Solo se muestran equipos disponibles en Supp/Existencias que tienen placa de inventario.',
        context="{'equipment_change_wizard': True, 'search_by_inventory_plate_only': True, 'active_model': 'subscription.equipment.change.wizard'}",
    )
    
    new_equipment_lot_id = fields.Many2one(
        'stock.lot',
        string='Equipo Nuevo Seleccionado',
        required=True,
        domain="[('id', 'in', available_new_equipment_ids), ('inventory_plate', '!=', False)]",
        help='Equipo nuevo seleccionado. Use el campo de búsqueda por placa de inventario para seleccionar el equipo.',
        readonly=True,
        invisible="not new_equipment_inventory_plate_search",
    )
    
    new_equipment_inventory_plate = fields.Char(
        related='new_equipment_lot_id.inventory_plate',
        string='Placa del Equipo Nuevo',
        readonly=True,
    )
    
    new_equipment_name = fields.Char(
        related='new_equipment_lot_id.name',
        string='Número de Serie del Equipo Nuevo',
        readonly=True,
    )
    
    new_equipment_product_id = fields.Many2one(
        related='new_equipment_lot_id.product_id',
        string='Producto del Equipo Nuevo',
        readonly=True,
    )
    
    new_equipment_supply_line_ids = fields.One2many(
        related='new_equipment_lot_id.lot_supply_line_ids',
        string='Elementos Asociados del Equipo Nuevo',
        readonly=True,
    )
    
    available_new_equipment_ids = fields.Many2many(
        'stock.lot',
        compute='_compute_available_equipment',
        string='Equipos Disponibles en Supp/Existencias',
    )
    
    change_date = fields.Datetime(
        string='Fecha del Cambio',
        default=fields.Datetime.now,
        required=True,
        help='Fecha y hora en que se realiza el cambio de equipo',
    )
    
    notes = fields.Text(
        string='Notas',
        help='Notas adicionales sobre el cambio de equipo',
    )

    @api.depends('subscription_id', 'customer_location_id', 'old_equipment_lot_id')
    def _compute_available_equipment(self):
        """Calcula los equipos disponibles en ambas ubicaciones."""
        for wizard in self:
            wizard.available_old_equipment_ids = False
            wizard.available_new_equipment_ids = False
            
            if not wizard.subscription_id or not wizard.customer_location_id:
                continue
            
            # Ubicación del cliente (equipos a cambiar)
            customer_location_ids = self.env['stock.location'].search([
                ('id', 'child_of', wizard.customer_location_id.id)
            ]).ids
            
            # Obtener productos de las líneas de suscripción activas (NO componentes)
            subscription_lines = wizard.subscription_id.line_ids.filtered(
                lambda l: l.is_active 
                and not l.is_component_line 
                and l.display_in_lines
            )
            
            # Obtener IDs de productos únicos (stock_product_id o product_id)
            subscription_product_ids = []
            for line in subscription_lines:
                product_id = line.stock_product_id.id if line.stock_product_id else (line.product_id.id if line.product_id else False)
                if product_id and product_id not in subscription_product_ids:
                    subscription_product_ids.append(product_id)
            
            if not subscription_product_ids:
                # Si no hay productos en la suscripción, no hay equipos disponibles
                wizard.available_old_equipment_ids = False
                wizard.available_new_equipment_ids = False
                continue
            
            # Buscar TODOS los quants en ubicación del cliente con lotes que tengan placa de inventario
            # y que pertenezcan a productos de la suscripción
            customer_quants = self.env['stock.quant'].search([
                ('location_id', 'in', customer_location_ids),
                ('quantity', '>', 0),
                ('lot_id', '!=', False),
                ('lot_id.inventory_plate', '!=', False),
                ('product_id', 'in', subscription_product_ids),
            ])
            
            # Obtener todos los lotes únicos que tienen stock en la ubicación del cliente
            available_old_lots = customer_quants.mapped('lot_id')
            
            # Filtrar para asegurar que tienen placa de inventario
            available_old_lots = available_old_lots.filtered(lambda l: l.inventory_plate)
            
            wizard.available_old_equipment_ids = available_old_lots
            
            # Ubicación Supp/Existencias (equipos nuevos)
            supplies_location = self.env['stock.location'].search([
                ('complete_name', 'ilike', 'Supp/Existencias'),
                ('usage', '=', 'internal'),
            ], limit=1)
            
            if supplies_location:
                supplies_location_ids = self.env['stock.location'].search([
                    ('id', 'child_of', supplies_location.id)
                ]).ids
                
                # Buscar quants en Supp/Existencias con lotes que tengan placa de inventario
                supplies_quants = self.env['stock.quant'].search([
                    ('location_id', 'in', supplies_location_ids),
                    ('quantity', '>', 0),
                    ('lot_id', '!=', False),
                    ('lot_id.inventory_plate', '!=', False),
                ])
                
                # Filtrar por el mismo producto del equipo viejo (si está seleccionado)
                # Si no hay equipo viejo seleccionado, mostrar todos los productos de la suscripción
                if wizard.old_equipment_lot_id and wizard.old_equipment_lot_id.product_id:
                    # Filtrar por el mismo producto del equipo viejo
                    supplies_quants = supplies_quants.filtered(
                        lambda q: q.lot_id.product_id.id == wizard.old_equipment_lot_id.product_id.id
                    )
                elif subscription_product_ids:
                    # Si no hay equipo viejo seleccionado, mostrar todos los productos de la suscripción
                    supplies_quants = supplies_quants.filtered(
                        lambda q: q.lot_id.product_id.id in subscription_product_ids
                    )
                
                # Obtener todos los lotes únicos
                available_new_lots = supplies_quants.mapped('lot_id')
                
                # Filtrar para asegurar que tienen placa de inventario
                available_new_lots = available_new_lots.filtered(lambda l: l.inventory_plate)
                
                # Excluir lotes que ya están en uso en otras suscripciones activas
                if available_new_lots:
                    Usage = self.env['subscription.subscription.usage']
                    active_usages = Usage.search([
                        ('lot_id', 'in', available_new_lots.ids),
                        ('date_end', '=', False),
                        ('subscription_id.state', '=', 'active'),
                    ])
                    used_lot_ids = active_usages.mapped('lot_id').ids
                    available_new_lots = available_new_lots.filtered(
                        lambda l: l.id not in used_lot_ids
                    )
                
                wizard.available_new_equipment_ids = available_new_lots
            else:
                wizard.available_new_equipment_ids = False

    def _get_lots_from_line(self, line):
        """Obtiene los IDs de lotes asociados a una línea de suscripción."""
        lot_ids = []
        
        # Buscar quants en la ubicación de la suscripción para este producto
        location = line.location_id or line.subscription_id.location_id
        if not location:
            return lot_ids
        
        location_ids = self.env['stock.location'].search([
            ('id', 'child_of', location.id)
        ]).ids
        
        product = line.stock_product_id or line.product_id
        if not product:
            return lot_ids
        
        quants = self.env['stock.quant'].search([
            ('location_id', 'in', location_ids),
            ('product_id', '=', product.id),
            ('quantity', '>', 0),
            ('lot_id', '!=', False),
        ])
        
        return quants.mapped('lot_id').ids

    @api.onchange('old_equipment_inventory_plate_search')
    def _onchange_old_equipment_inventory_plate_search(self):
        """Actualiza el equipo seleccionado cuando se selecciona una placa de inventario."""
        if self.old_equipment_inventory_plate_search:
            # Cuando se selecciona una placa, actualizar el equipo seleccionado
            self.old_equipment_lot_id = self.old_equipment_inventory_plate_search
        else:
            # Si se limpia la placa, limpiar también el equipo seleccionado
            self.old_equipment_lot_id = False
    
    @api.onchange('new_equipment_inventory_plate_search')
    def _onchange_new_equipment_inventory_plate_search(self):
        """Actualiza el equipo nuevo seleccionado cuando se selecciona una placa de inventario."""
        if self.new_equipment_inventory_plate_search:
            # Cuando se selecciona una placa, actualizar el equipo seleccionado
            self.new_equipment_lot_id = self.new_equipment_inventory_plate_search
        else:
            # Si se limpia la placa, limpiar también el equipo seleccionado
            self.new_equipment_lot_id = False
    
    @api.onchange('old_equipment_lot_id')
    def _onchange_old_equipment(self):
        """Actualiza el dominio del equipo nuevo cuando se selecciona el viejo."""
        if self.old_equipment_lot_id:
            # Forzar recálculo del dominio del equipo nuevo
            self._compute_available_equipment()
            # Limpiar selección del equipo nuevo si no es compatible
            if self.new_equipment_lot_id:
                if (self.new_equipment_lot_id.product_id.id != 
                    self.old_equipment_lot_id.product_id.id):
                    self.new_equipment_lot_id = False

    @api.constrains('old_equipment_lot_id', 'new_equipment_lot_id')
    def _check_equipment_different(self):
        """Valida que los equipos sean diferentes."""
        for wizard in self:
            if (wizard.old_equipment_lot_id and wizard.new_equipment_lot_id and
                wizard.old_equipment_lot_id.id == wizard.new_equipment_lot_id.id):
                raise ValidationError(_('El equipo nuevo debe ser diferente al equipo a cambiar.'))

    @api.constrains('old_equipment_lot_id', 'new_equipment_lot_id')
    def _check_same_product(self):
        """Valida que ambos equipos sean del mismo producto."""
        for wizard in self:
            if (wizard.old_equipment_lot_id and wizard.new_equipment_lot_id):
                if (wizard.old_equipment_lot_id.product_id.id != 
                    wizard.new_equipment_lot_id.product_id.id):
                    raise ValidationError(_(
                        'El equipo nuevo debe ser del mismo producto que el equipo a cambiar.\n'
                        'Equipo viejo: %s\n'
                        'Equipo nuevo: %s'
                    ) % (
                        wizard.old_equipment_lot_id.product_id.display_name,
                        wizard.new_equipment_lot_id.product_id.display_name,
                    ))

    def action_confirm_change(self):
        """Confirma el cambio de equipo."""
        self.ensure_one()
        
        # Si se seleccionó la placa pero no el equipo, actualizar el equipo desde la placa
        if self.old_equipment_inventory_plate_search and not self.old_equipment_lot_id:
            self.old_equipment_lot_id = self.old_equipment_inventory_plate_search
        
        # Si se seleccionó la placa pero no el equipo, actualizar el equipo desde la placa
        if self.new_equipment_inventory_plate_search and not self.new_equipment_lot_id:
            self.new_equipment_lot_id = self.new_equipment_inventory_plate_search
        
        if not self.old_equipment_lot_id or not self.new_equipment_lot_id:
            raise UserError(_('Debe seleccionar ambos equipos para realizar el cambio.'))
        
        # Validar que ambos equipos tengan placa de inventario
        if not self.old_equipment_lot_id.inventory_plate:
            raise UserError(_('El equipo seleccionado no tiene placa de inventario.'))
        
        if not self.new_equipment_lot_id.inventory_plate:
            raise UserError(_('El equipo nuevo seleccionado no tiene placa de inventario.'))
        
        if self.old_equipment_lot_id.id == self.new_equipment_lot_id.id:
            raise UserError(_('El equipo nuevo debe ser diferente al equipo a cambiar.'))
        
        # Validar que el equipo viejo esté en la ubicación del cliente
        old_quant = self.env['stock.quant'].search([
            ('lot_id', '=', self.old_equipment_lot_id.id),
            ('location_id', 'child_of', self.customer_location_id.id),
            ('quantity', '>', 0),
        ], limit=1)
        
        if not old_quant:
            raise UserError(_(
                'El equipo seleccionado no se encuentra en la ubicación del cliente: %s'
            ) % self.customer_location_id.display_name)
        
        # Validar que el equipo nuevo esté en Supp/Existencias
        supplies_location = self.env['stock.location'].search([
            ('complete_name', 'ilike', 'Supp/Existencias'),
            ('usage', '=', 'internal'),
        ], limit=1)
        
        if not supplies_location:
            raise UserError(_('No se encontró la ubicación Supp/Existencias.'))
        
        new_quant = self.env['stock.quant'].search([
            ('lot_id', '=', self.new_equipment_lot_id.id),
            ('location_id', 'child_of', supplies_location.id),
            ('quantity', '>', 0),
        ], limit=1)
        
        if not new_quant:
            raise UserError(_(
                'El equipo nuevo no se encuentra en la ubicación Supp/Existencias.'
            ))
        
        # Realizar el cambio
        subscription_line = self._find_subscription_line_for_lot(self.old_equipment_lot_id)
        preserved_price = subscription_line.price_monthly if subscription_line else 0.0
        currency_symbol = self.subscription_id.currency_id.symbol if self.subscription_id.currency_id else ''
        
        self._perform_equipment_change()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Cambio de Equipo Exitoso'),
                'message': _(
                    'El equipo ha sido cambiado exitosamente.\n'
                    'Equipo viejo: %s (Placa: %s)\n'
                    'Equipo nuevo: %s (Placa: %s)\n'
                    'Precio preservado: %s %s'
                ) % (
                    self.old_equipment_lot_id.display_name,
                    self.old_equipment_inventory_plate or 'N/A',
                    self.new_equipment_lot_id.display_name,
                    self.new_equipment_inventory_plate or 'N/A',
                    preserved_price,
                    currency_symbol,
                ),
                'type': 'success',
                'sticky': False,
            }
        }

    def _perform_equipment_change(self):
        """Realiza el cambio físico y lógico de los equipos."""
        self.ensure_one()
        
        # Obtener ubicación Supp/Existencias
        supplies_location = self.env['stock.location'].search([
            ('complete_name', 'ilike', 'Supp/Existencias'),
            ('usage', '=', 'internal'),
        ], limit=1)
        
        if not supplies_location:
            raise UserError(_('No se encontró la ubicación Supp/Existencias.'))
        
        # Buscar la línea de suscripción correspondiente al equipo viejo
        subscription_line = self._find_subscription_line_for_lot(self.old_equipment_lot_id)
        
        if not subscription_line:
            raise UserError(_(
                'No se encontró una línea de suscripción para el equipo seleccionado.'
            ))
        
        # Validar que los productos coincidan
        self._validate_product_match(subscription_line, self.old_equipment_lot_id, self.new_equipment_lot_id)
        
        # Validar que el equipo nuevo no esté en otra suscripción activa
        self._validate_new_equipment_available(self.new_equipment_lot_id)
        
        # PRESERVAR EL PRECIO: Guardar el precio actual antes de cualquier cambio
        original_price = subscription_line.price_monthly or 0.0
        original_subtotal = subscription_line.subtotal_monthly or 0.0
        
        # 1. Cerrar registro de uso del equipo viejo
        self._close_usage_for_lot(subscription_line, self.old_equipment_lot_id)
        
        # 2. Crear registro de uso del equipo nuevo (con el precio preservado)
        self._create_usage_for_lot(subscription_line, self.new_equipment_lot_id, original_price)
        
        # 3. Mover el equipo viejo a Supp/Existencias
        self._move_lot_to_location(self.old_equipment_lot_id, supplies_location)
        
        # 4. Mover el equipo nuevo a la ubicación del cliente
        self._move_lot_to_location(self.new_equipment_lot_id, self.customer_location_id)
        
        # 5. GARANTIZAR que el precio NO cambie después del cambio
        # Forzar que el precio_monthly se mantenga igual
        if subscription_line.price_monthly != original_price:
            subscription_line.price_monthly = original_price
            # Recalcular subtotal si es necesario
            if subscription_line.subtotal_monthly != original_subtotal:
                subscription_line.subtotal_monthly = subscription_line.quantity * original_price
        
        # 6. Crear registro en el historial de cambios de equipo
        history_vals = {
            'subscription_id': self.subscription_id.id,
            'subscription_line_id': subscription_line.id,
            'change_date': self.change_date,
            'user_id': self.env.user.id,
            'old_equipment_lot_id': self.old_equipment_lot_id.id,
            'old_equipment_name': self.old_equipment_lot_id.name,
            'old_equipment_inventory_plate': self.old_equipment_inventory_plate,
            'old_equipment_product_id': self.old_equipment_lot_id.product_id.id,
            'new_equipment_lot_id': self.new_equipment_lot_id.id,
            'new_equipment_name': self.new_equipment_lot_id.name,
            'new_equipment_inventory_plate': self.new_equipment_inventory_plate,
            'new_equipment_product_id': self.new_equipment_lot_id.product_id.id,
            'price_preserved': original_price,
            'notes': self.notes,
            'old_location_id': supplies_location.id,
            'new_location_id': self.customer_location_id.id,
        }
        
        history_record = self.env['subscription.equipment.change.history'].create(history_vals)
        
        # 7. Registrar en el historial de mensajes de la suscripción (compatibilidad)
        if self.notes:
            self.subscription_id.message_post(
                body=_(
                    'Cambio de Equipo. Equipo viejo: %s (Placa: %s). Equipo nuevo: %s (Placa: %s). Fecha: %s. Precio preservado: %s %s. Notas: %s.'
                ) % (
                    self.old_equipment_lot_id.display_name,
                    self.old_equipment_inventory_plate or 'N/A',
                    self.new_equipment_lot_id.display_name,
                    self.new_equipment_inventory_plate or 'N/A',
                    self.change_date,
                    original_price,
                    self.subscription_id.currency_id.symbol or '',
                    self.notes,
                )
            )
        else:
            self.subscription_id.message_post(
                body=_(
                    'Cambio de Equipo. Equipo viejo: %s (Placa: %s). Equipo nuevo: %s (Placa: %s). Fecha: %s. Precio preservado: %s %s.'
                ) % (
                    self.old_equipment_lot_id.display_name,
                    self.old_equipment_inventory_plate or 'N/A',
                    self.new_equipment_lot_id.display_name,
                    self.new_equipment_inventory_plate or 'N/A',
                    self.change_date,
                    original_price,
                    self.subscription_id.currency_id.symbol or '',
                )
            )

    def _validate_product_match(self, line, old_lot, new_lot):
        """Valida que los productos del equipo viejo y nuevo coincidan con la línea de suscripción."""
        if line.stock_product_id.id != old_lot.product_id.id:
            raise UserError(_(
                'El producto del equipo viejo (%s) no coincide con la línea de suscripción (%s).'
            ) % (
                old_lot.product_id.display_name,
                line.stock_product_id.display_name,
            ))
        if line.stock_product_id.id != new_lot.product_id.id:
            raise UserError(_(
                'El producto del equipo nuevo (%s) no coincide con la línea de suscripción (%s).'
            ) % (
                new_lot.product_id.display_name,
                line.stock_product_id.display_name,
            ))
        if old_lot.product_id.id != new_lot.product_id.id:
            raise UserError(_(
                'El producto del equipo nuevo (%s) no coincide con el producto del equipo viejo (%s).'
            ) % (
                new_lot.product_id.display_name,
                old_lot.product_id.display_name,
            ))

    def _validate_new_equipment_available(self, new_lot):
        """Valida que el equipo nuevo no esté en otra suscripción activa."""
        # Buscar suscripciones activas que tengan este lote
        Usage = self.env['subscription.subscription.usage']
        active_usages = Usage.search([
            ('lot_id', '=', new_lot.id),
            ('date_end', '=', False),
            ('subscription_id', '!=', self.subscription_id.id),
            ('subscription_id.state', '=', 'active'),
        ])
        
        if active_usages:
            conflicting_subs = active_usages.mapped('subscription_id')
            raise UserError(_(
                'El equipo nuevo (%s) está actualmente en uso en otra suscripción activa:\n%s'
            ) % (
                new_lot.display_name,
                '\n'.join(['- %s' % sub.name for sub in conflicting_subs]),
            ))

    def _find_subscription_line_for_lot(self, lot):
        """Encuentra la línea de suscripción correspondiente a un lote."""
        # Buscar líneas activas con el mismo producto que NO sean líneas de componente
        lines = self.subscription_id.line_ids.filtered(
            lambda l: l.stock_product_id.id == lot.product_id.id 
            and l.is_active 
            and not l.is_component_line
            and l.display_in_lines
        )
        
        if not lines:
            # Si no hay líneas activas, buscar cualquier línea con el mismo producto
            lines = self.subscription_id.line_ids.filtered(
                lambda l: l.stock_product_id.id == lot.product_id.id 
                and not l.is_component_line
            )
        
        if not lines:
            return False
        
        # Si hay múltiples líneas, buscar la que tenga el lote activo en uso
        for line in lines:
            active_usage = self.env['subscription.subscription.usage'].search([
                ('line_id', '=', line.id),
                ('lot_id', '=', lot.id),
                ('date_end', '=', False),
            ], limit=1)
            if active_usage:
                return line
        
        # Si no hay línea con uso activo, verificar que el lote esté en la ubicación de alguna línea
        for line in lines:
            location = line.location_id or self.subscription_id.location_id
            if location:
                location_ids = self.env['stock.location'].search([
                    ('id', 'child_of', location.id)
                ]).ids
                
                quant = self.env['stock.quant'].search([
                    ('lot_id', '=', lot.id),
                    ('location_id', 'in', location_ids),
                    ('quantity', '>', 0),
                ], limit=1)
                
                if quant:
                    return line
        
        # Si no se encuentra ninguna línea específica, devolver la primera
        return lines[0] if lines else False

    def _close_usage_for_lot(self, line, lot):
        """Cierra el registro de uso activo para un lote."""
        # Buscar registro de uso activo (sin date_end) para este lote
        active_usage = self.env['subscription.subscription.usage'].search([
            ('line_id', '=', line.id),
            ('lot_id', '=', lot.id),
            ('date_end', '=', False),
        ], order='date_start asc')
        
        # Cerrar todos los registros activos
        if active_usage:
            active_usage.write({
                'date_end': self.change_date,
            })

    def _create_usage_for_lot(self, line, lot, preserved_price=None):
        """Crea un nuevo registro de uso para un lote.
        
        Args:
            line: Línea de suscripción
            lot: Lote del equipo nuevo
            preserved_price: Precio mensual a preservar (si no se proporciona, usa el de la línea)
        """
        # Verificar que no exista ya un registro activo
        existing_usage = self.env['subscription.subscription.usage'].search([
            ('line_id', '=', line.id),
            ('lot_id', '=', lot.id),
            ('date_end', '=', False),
        ], limit=1)
        
        if existing_usage:
            # Ya existe un registro activo, no crear otro
            return
        
        # Obtener fecha de entrada del lote
        entry_date = self._get_lot_entry_date(lot, self.customer_location_id)
        
        # Usar el precio preservado si se proporciona, sino usar el de la línea
        price_to_use = preserved_price if preserved_price is not None else (line.price_monthly or 0.0)
        
        # Crear nuevo registro de uso con el precio preservado
        self.env['subscription.subscription.usage'].create({
            'line_id': line.id,
            'lot_id': lot.id,
            'date_start': entry_date or self.change_date,
            'quantity': 1.0,
            'price_monthly_snapshot': price_to_use,
        })

    def _get_lot_entry_date(self, lot, location):
        """Obtiene la fecha de entrada de un lote a una ubicación."""
        MoveLine = self.env['stock.move.line'].sudo()
        
        location_ids = self.env['stock.location'].search([
            ('id', 'child_of', location.id)
        ]).ids
        
        domain = [
            ('state', '=', 'done'),
            ('lot_id', '=', lot.id),
            ('product_id', '=', lot.product_id.id),
            ('qty_done', '>', 0),
            ('location_dest_id', 'in', location_ids),
        ]
        
        move_line = MoveLine.search(domain, order='date desc', limit=1)
        
        if move_line:
            return move_line.date or move_line.write_date or move_line.create_date
        
        return False

    def _move_lot_to_location(self, lot, destination_location):
        """Mueve un lote de su ubicación actual a una nueva ubicación."""
        # Buscar quant actual del lote
        current_quants = self.env['stock.quant'].search([
            ('lot_id', '=', lot.id),
            ('quantity', '>', 0),
        ])
        
        if not current_quants:
            raise UserError(_(
                'No se encontró inventario para el lote: %s'
            ) % lot.display_name)
        
        # Crear movimiento de stock usando stock.move
        for quant in current_quants:
            if quant.location_id.id == destination_location.id:
                # Ya está en la ubicación destino, no hacer nada
                continue
            
            # Buscar tipo de operación interno
            picking_type = self.env['stock.picking.type'].search([
                ('code', '=', 'internal'),
                ('warehouse_id', '!=', False),
            ], limit=1)
            
            if not picking_type:
                # Si no hay picking type, usar método directo con stock.move
                self._move_quant_direct(quant, destination_location)
                continue
            
            # Crear picking
            picking = self.env['stock.picking'].create({
                'picking_type_id': picking_type.id,
                'location_id': quant.location_id.id,
                'location_dest_id': destination_location.id,
            })
            
            # Crear movimiento
            move = self.env['stock.move'].create({
                'name': _('Cambio de equipo - %s') % lot.display_name,
                'product_id': lot.product_id.id,
                'product_uom': lot.product_id.uom_id.id,
                'location_id': quant.location_id.id,
                'location_dest_id': destination_location.id,
                'product_uom_qty': quant.quantity,
                'picking_id': picking.id,
            })
            
            # Confirmar y asignar
            picking.action_confirm()
            picking.action_assign()
            
            # Actualizar o crear move line y validar
            # Después de action_assign(), los move lines pueden o no existir
            move_lines = move.move_line_ids.filtered(lambda ml: ml.product_id == lot.product_id)
            
            if move_lines:
                # Actualizar move lines existentes
                # Solo actualizar los campos que necesitamos (qty_done y lot_id)
                # No modificar location_id y location_dest_id porque pueden estar bloqueados después de assign
                for move_line in move_lines:
                    move_line.lot_id = lot.id
                    # Usar la cantidad del quant directamente (es lo que queremos mover)
                    move_line.qty_done = quant.quantity
            else:
                # Crear move line manualmente si no existe después de assign
                self.env['stock.move.line'].create({
                    'move_id': move.id,
                    'product_id': lot.product_id.id,
                    'product_uom_id': lot.product_id.uom_id.id,
                    'lot_id': lot.id,
                    'location_id': quant.location_id.id,
                    'location_dest_id': destination_location.id,
                    'qty_done': quant.quantity,
                    'product_uom_qty': quant.quantity,
                })
            
            # Validar el picking
            picking.button_validate()

    def _move_quant_direct(self, quant, destination_location):
        """Mueve un quant directamente usando stock.move (método alternativo)."""
        # Crear movimiento directo
        move = self.env['stock.move'].create({
            'name': _('Cambio de equipo - %s') % quant.lot_id.display_name,
            'product_id': quant.product_id.id,
            'product_uom': quant.product_id.uom_id.id,
            'location_id': quant.location_id.id,
            'location_dest_id': destination_location.id,
            'product_uom_qty': quant.quantity,
        })
        
        move._action_confirm()
        move._action_assign()
        
        # Actualizar o crear move line
        move_lines = move.move_line_ids.filtered(lambda ml: ml.product_id == quant.product_id)
        
        if move_lines:
            # Actualizar move lines existentes
            # Solo actualizar los campos que necesitamos (qty_done y lot_id)
            # No modificar location_id y location_dest_id porque pueden estar bloqueados después de assign
            for move_line in move_lines:
                move_line.lot_id = quant.lot_id.id
                move_line.qty_done = quant.quantity
        else:
            # Crear move line manualmente si no existe después de assign
            self.env['stock.move.line'].create({
                'move_id': move.id,
                'product_id': quant.product_id.id,
                'product_uom_id': quant.product_id.uom_id.id,
                'lot_id': quant.lot_id.id,
                'location_id': quant.location_id.id,
                'location_dest_id': destination_location.id,
                'qty_done': quant.quantity,
                'product_uom_qty': quant.quantity,
            })
        
        move._action_done()

