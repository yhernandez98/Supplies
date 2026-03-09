# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class QuantEditorWizard(models.TransientModel):
    """Wizard para actualizar cantidades de inventario por producto y serial/lote."""
    
    _name = 'quant.editor.wizard'
    _description = 'Editor de Cantidades de Inventario'

    location_id = fields.Many2one(
        'stock.location',
        string='Ubicación',
        required=True,
        domain=['|', ('usage', '=', 'internal'), ('complete_name', 'ilike', 'Supp/Alistamiento')],
        help='Ubicación donde se actualizará el inventario'
    )
    
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        required=True,
        domain=[('product_tmpl_id.tipo_producto', '=', 'consu')],
        help='Producto a actualizar (solo bienes)'
    )
    
    lot_id = fields.Many2one(
        'stock.lot',
        string='Número de Serie / Lote',
        help='Número de serie o lote. Si tiene producto, se cargará automáticamente.'
    )
    
    lot_serial_number = fields.Char(
        string='Número de Serie',
        help='Ingrese el número de serie. Si no existe, se creará automáticamente.'
    )
    
    owner_id = fields.Many2one(
        'res.partner',
        string='Propietario',
        help='Propietario del quant (opcional)'
    )
    
    quantity = fields.Float(
        string='Cantidad',
        required=True,
        default=1.0,
        help='Cantidad a establecer en el inventario'
    )
    
    current_quantity = fields.Float(
        string='Cantidad Actual',
        compute='_compute_current_quantity',
        store=False,
        help='Cantidad actual en el inventario'
    )
    
    inventory_plate = fields.Char(
        string='Placa de Inventario',
        help='Placa de inventario del lote'
    )
    
    security_plate = fields.Char(
        string='Placa de Seguridad',
        help='Placa de seguridad del lote'
    )
    
    internal_ref = fields.Many2one(
        'internal.reference',
        string='Referencia Interna',
        help='Referencia interna del lote (se puede crear nueva si no existe, única por producto)',
        domain="[('product_id', '=', product_id)]"
    )
    
    modelo = fields.Char(
        string='Modelo',
        help='Modelo del producto (se llena automáticamente desde el nombre del producto)'
    )

    def _get_modelo_from_product(self, product):
        """Extraer modelo del nombre del producto (omitir primera palabra)."""
        if not product or not product.name:
            return ''
        name_parts = product.name.strip().split()
        if len(name_parts) > 1:
            return ' '.join(name_parts[1:])
        return ''

    @api.model
    def default_get(self, fields_list):
        """Cargar valores por defecto desde el contexto."""
        res = super(QuantEditorWizard, self).default_get(fields_list)
        
        # Obtener lot_id del contexto
        lot_id = self.env.context.get('default_lot_id') or \
                 (self.env.context.get('active_id') if self.env.context.get('active_model') == 'stock.lot' else None) or \
                 self.env.context.get('lot_id')
        
        if lot_id:
            lot = self.env['stock.lot'].browse(lot_id)
            if lot.exists():
                res['lot_id'] = lot.id
                res['lot_serial_number'] = lot.name or ''
                res['inventory_plate'] = lot.inventory_plate or ''
                res['security_plate'] = lot.security_plate or ''
                
                if lot.product_id:
                    res['product_id'] = lot.product_id.id
                    # Cargar modelo desde el producto
                    res['modelo'] = self._get_modelo_from_product(lot.product_id)
                
                # Cargar modelo desde el lote si existe (prioridad sobre el del producto)
                if hasattr(lot, 'model_name') and getattr(lot, 'model_name', ''):
                    res['modelo'] = getattr(lot, 'model_name', '') or ''
                
                # Cargar referencia interna
                lot_ref = getattr(lot, 'ref', '') or ''
                if lot_ref and lot.product_id:
                    internal_ref = self.env['internal.reference'].search([
                        ('name', '=', lot_ref),
                        ('product_id', '=', lot.product_id.id)
                    ], limit=1)
                    if internal_ref:
                        res['internal_ref'] = internal_ref.id
                    else:
                        ref_vals = {
                            'name': lot_ref,
                            'product_id': lot.product_id.id
                        }
                        internal_ref = self.env['internal.reference'].create(ref_vals)
                        res['internal_ref'] = internal_ref.id
                else:
                    res['internal_ref'] = False
        
        # Cargar producto del contexto si existe
        product_id = self.env.context.get('default_product_id')
        if product_id:
            res['product_id'] = product_id
            # Cargar modelo desde el producto
            product = self.env['product.product'].browse(product_id)
            if product.exists():
                res['modelo'] = self._get_modelo_from_product(product)
        
        # Cargar ubicación
        location_id = self.env.context.get('default_location_id')
        if location_id:
            res['location_id'] = location_id
        else:
            supplies_location = self.env['stock.location'].search([
                ('complete_name', 'ilike', 'Supp/Existencias'),
                ('usage', '=', 'internal'),
            ], limit=1)
            if supplies_location:
                res['location_id'] = supplies_location.id
        
        return res

    @api.depends('location_id', 'product_id', 'lot_id', 'owner_id')
    def _compute_current_quantity(self):
        """Calcular la cantidad actual del quant."""
        for wizard in self:
            if not wizard.location_id or not wizard.product_id:
                wizard.current_quantity = 0.0
                continue
            
            domain = [
                ('location_id', '=', wizard.location_id.id),
                ('product_id', '=', wizard.product_id.id),
            ]
            
            if wizard.lot_id:
                domain.append(('lot_id', '=', wizard.lot_id.id))
            else:
                domain.append(('lot_id', '=', False))
            
            if wizard.owner_id:
                domain.append(('owner_id', '=', wizard.owner_id.id))
            else:
                domain.append(('owner_id', '=', False))
            
            quant = self.env['stock.quant'].search(domain, limit=1)
            wizard.current_quantity = quant.quantity if quant else 0.0

    @api.onchange('lot_id')
    def _onchange_lot_id(self):
        """Cargar información del lote cuando se selecciona."""
        if self.lot_id:
            if self.lot_id.product_id:
                self.product_id = self.lot_id.product_id
                # Cargar modelo desde el producto
                self.modelo = self._get_modelo_from_product(self.lot_id.product_id)
            
            # Cargar modelo desde el lote si existe (prioridad sobre el del producto)
            if hasattr(self.lot_id, 'model_name') and getattr(self.lot_id, 'model_name', ''):
                self.modelo = getattr(self.lot_id, 'model_name', '') or ''
            
            self.lot_serial_number = self.lot_id.name or ''
            self.inventory_plate = self.lot_id.inventory_plate or ''
            self.security_plate = self.lot_id.security_plate or ''
            
            lot_ref = getattr(self.lot_id, 'ref', '') or ''
            if lot_ref and self.lot_id.product_id:
                internal_ref = self.env['internal.reference'].search([
                    ('name', '=', lot_ref),
                    ('product_id', '=', self.lot_id.product_id.id)
                ], limit=1)
                if internal_ref:
                    self.internal_ref = internal_ref.id
                else:
                    ref_vals = {
                        'name': lot_ref,
                        'product_id': self.lot_id.product_id.id
                    }
                    internal_ref = self.env['internal.reference'].create(ref_vals)
                    self.internal_ref = internal_ref.id
            else:
                self.internal_ref = False
            
            self._compute_current_quantity()

    @api.onchange('lot_serial_number')
    def _onchange_lot_serial_number(self):
        """Buscar lote cuando se ingresa un número de serie."""
        if self.lot_serial_number and self.lot_serial_number.strip():
            serial_number = self.lot_serial_number.strip()
            
            # Si hay producto seleccionado, buscar lote por nombre Y producto
            # Si no hay producto, buscar solo por nombre (pero luego validar)
            domain = [('name', '=', serial_number)]
            if self.product_id:
                domain.append(('product_id', '=', self.product_id.id))
            
            lot = self.env['stock.lot'].search(domain, limit=1)
            
            # Si hay producto seleccionado y se encontró un lote de otro producto, mostrar advertencia
            if lot and self.product_id and lot.product_id.id != self.product_id.id:
                # El serial existe pero para otro producto - esto está permitido, no cargar ese lote
                lot = False
                self.lot_id = False
                self.inventory_plate = ''
                self.security_plate = ''
                self.internal_ref = False
                return {
                    'warning': {
                        'title': _('Serial Existe en Otro Producto'),
                        'message': _('El número de serie "%s" ya existe para el producto "%s". '
                                    'Se creará un nuevo lote para el producto "%s".') % 
                                    (serial_number, lot.product_id.name, self.product_id.name)
                    }
                }
            
            if lot:
                # Lote encontrado para el mismo producto (o sin producto seleccionado)
                self.lot_id = lot.id
                if lot.product_id:
                    self.product_id = lot.product_id
                    # Cargar modelo desde el producto
                    self.modelo = self._get_modelo_from_product(lot.product_id)
                
                # Cargar modelo desde el lote si existe (prioridad sobre el del producto)
                if hasattr(lot, 'model_name') and getattr(lot, 'model_name', ''):
                    self.modelo = getattr(lot, 'model_name', '') or ''
                
                self.inventory_plate = lot.inventory_plate or ''
                self.security_plate = lot.security_plate or ''
                
                lot_ref = getattr(lot, 'ref', '') or ''
                if lot_ref and lot.product_id:
                    internal_ref = self.env['internal.reference'].search([
                        ('name', '=', lot_ref),
                        ('product_id', '=', lot.product_id.id)
                    ], limit=1)
                    if internal_ref:
                        self.internal_ref = internal_ref.id
                    else:
                        ref_vals = {
                            'name': lot_ref,
                            'product_id': lot.product_id.id
                        }
                        internal_ref = self.env['internal.reference'].create(ref_vals)
                        self.internal_ref = internal_ref.id
                else:
                    self.internal_ref = False

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Limpiar lote si no coincide con el producto y cargar modelo."""
        if self.product_id and self.lot_id:
            if self.lot_id.product_id and self.lot_id.product_id.id != self.product_id.id:
                self.lot_id = False
                self.inventory_plate = ''
                self.security_plate = ''
                self.internal_ref = False
                self.lot_serial_number = ''
        
        if self.product_id and self.internal_ref:
            if self.internal_ref.product_id != self.product_id:
                self.internal_ref = False
        
        # Cargar modelo desde el producto cuando cambia
        if self.product_id:
            self.modelo = self._get_modelo_from_product(self.product_id)
        else:
            self.modelo = ''

    def action_update_quantity(self):
        """Actualizar la cantidad del quant y la información del lote."""
        self.ensure_one()
        
        if not self.location_id:
            raise UserError(_('Debe seleccionar una ubicación.'))
        
        if not self.product_id:
            raise UserError(_('Debe seleccionar un producto.'))
        
        # Crear o actualizar el lote si hay número de serie
        lot = None
        if self.lot_serial_number and self.lot_serial_number.strip():
            serial_number = self.lot_serial_number.strip()
            
            # SIEMPRE buscar si existe un lote con este serial para este producto
            # Esto previene duplicados incluso si self.lot_id ya está asignado
            existing_lot = self.env['stock.lot'].search([
                ('name', '=', serial_number),
                ('product_id', '=', self.product_id.id)
            ], limit=1)
            
            if existing_lot:
                # El lote ya existe para este producto
                # Validar: Si el usuario está intentando crear uno nuevo (self.lot_id es diferente o None)
                # y el lote existente ya tiene stock, no permitir duplicar
                if not self.lot_id or self.lot_id.id != existing_lot.id:
                    # El usuario está intentando usar un serial que ya existe
                    # Verificar si hay stock en alguna ubicación
                    existing_quants = self.env['stock.quant'].search([
                        ('lot_id', '=', existing_lot.id),
                        ('quantity', '>', 0)
                    ])
                    
                    if existing_quants:
                        raise ValidationError(_(
                            'El número de serie o lote "%s" ya está registrado para el producto "%s" '
                            'y tiene stock en el inventario. No se puede crear un duplicado.\n\n'
                            'Si desea actualizar la cantidad, seleccione el lote existente desde el campo "Número de Serie / Lote".'
                        ) % (serial_number, self.product_id.name))
                    else:
                        # El lote existe pero no tiene stock - usar ese lote
                        lot = existing_lot
                        self.lot_id = lot.id
                else:
                    # El lote ya está asignado correctamente - usarlo
                    lot = existing_lot
            else:
                # No existe lote con este serial para este producto
                # Verificar si self.lot_id está asignado pero es de otro producto
                if self.lot_id and self.lot_id.product_id and self.lot_id.product_id.id != self.product_id.id:
                    # El lote asignado es de otro producto - crear uno nuevo para este producto
                    lot_vals = {
                        'name': serial_number,
                        'product_id': self.product_id.id,
                    }
                    lot = self.env['stock.lot'].create(lot_vals)
                    self.lot_id = lot.id
                elif self.lot_id and self.lot_id.name == serial_number and self.lot_id.product_id.id == self.product_id.id:
                    # El lote asignado es correcto - usarlo
                    lot = self.lot_id
                else:
                    # Crear nuevo lote con el producto correcto
                    lot_vals = {
                        'name': serial_number,
                        'product_id': self.product_id.id,
                    }
                    lot = self.env['stock.lot'].create(lot_vals)
                    self.lot_id = lot.id
        else:
            # No hay número de serie - usar el lote asignado si existe
            lot = self.lot_id
        
        # IMPORTANTE: Actualizar información del lote SIEMPRE (tanto si hay serial como si no)
        # Esto asegura que los campos se guarden correctamente
        if lot:
            lot_vals = {}
            if self.inventory_plate:
                lot_vals['inventory_plate'] = self.inventory_plate.strip()
            elif self.inventory_plate == '':
                # Si el campo está vacío explícitamente, limpiarlo
                lot_vals['inventory_plate'] = False
            
            if self.security_plate:
                lot_vals['security_plate'] = self.security_plate.strip()
            elif self.security_plate == '':
                # Si el campo está vacío explícitamente, limpiarlo
                lot_vals['security_plate'] = False
            
            if hasattr(lot, 'ref'):
                if self.internal_ref:
                    lot_vals['ref'] = self.internal_ref.name
                else:
                    lot_vals['ref'] = False
            
            # Actualizar modelo - usar 'model_name' (campo estándar de Odoo)
            if hasattr(lot, 'model_name'):
                if self.modelo and self.modelo.strip():
                    lot_vals['model_name'] = self.modelo.strip()
                else:
                    lot_vals['model_name'] = False
            
            if lot_vals:
                lot.sudo().write(lot_vals)
            
            self.lot_id = lot.id
        
        # Actualizar cantidad usando el método estándar de Odoo
        self.env['stock.quant']._update_available_quantity(
            self.product_id,
            self.location_id,
            self.quantity,
            lot_id=self.lot_id,
            owner_id=self.owner_id,
            in_date=False
        )
        
        return {
            'type': 'ir.actions.act_window_close',
        }

    def action_update_and_create_new(self):
        """Actualizar la cantidad y abrir un nuevo wizard con el producto precargado."""
        self.ensure_one()
        
        product_id = self.product_id.id if self.product_id else False
        location_id = self.location_id.id if self.location_id else False
        
        # Ejecutar la actualización normal
        self.action_update_quantity()
        
        # Buscar ubicación por defecto si no hay
        if not location_id:
            supplies_location = self.env['stock.location'].search([
                ('complete_name', 'ilike', 'Supp/Existencias'),
                ('usage', '=', 'internal'),
            ], limit=1)
            if supplies_location:
                location_id = supplies_location.id
        
        # Abrir nuevo wizard
        return {
            'type': 'ir.actions.act_window',
            'name': _('Actualizar Cantidad de Inventario'),
            'res_model': 'quant.editor.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_product_id': product_id,
                'default_location_id': location_id,
                'default_quantity': 1.0,
            },
        }
