# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


def _safe_get(obj, key, default=None):
    """Evita 'list' object has no attribute 'get' (Odoo 19 compat)."""
    return obj.get(key, default) if isinstance(obj, dict) else default


class ProductTransferWizard(models.TransientModel):
    _name = 'product.transfer.wizard'
    _description = 'Wizard para transferir unidades y seriales entre productos'

    source_product_id = fields.Many2one(
        'product.product',
        string='Producto Origen',
        required=True,
        domain="[('id', 'in', available_product_ids)]",
        help='Producto del cual se transferirán las unidades/seriales',
    )

    destination_product_id = fields.Many2one(
        'product.product',
        string='Producto Destino',
        required=True,
        help='Producto al cual se transferirán las unidades/seriales',
    )

    location_id = fields.Many2one(
        'stock.location',
        string='Ubicación',
        required=True,
        domain=lambda self: self._get_location_domain(),
        help='Ubicación de la cual se transferirán las unidades',
    )

    operation_mode = fields.Selection(
        [
            ('conversion', 'Conversión Genérico → Específico'),
        ],
        string='Modo de Operación',
        required=True,
        default='conversion',
        help='Conversión: Elimina producto genérico y crea específico.',
    )


    # Campo computed para productos disponibles en la ubicación
    available_product_ids = fields.Many2many(
        'product.product',
        string='Productos Disponibles',
        compute='_compute_available_products',
        help='Productos con stock disponible en la ubicación seleccionada',
    )

    lot_ids = fields.Many2many(
        'stock.lot',
        string='Serial Genérico a Convertir',
        domain="[('id', 'in', available_lot_ids)]",
        help='Seleccione el serial del producto genérico a convertir (solo uno)',
    )

    product_uom_id = fields.Many2one(
        'uom.uom',
        string='Unidad de Medida',
        related='source_product_id.uom_id',
        readonly=True,
    )

    available_lot_ids = fields.Many2many(
        'stock.lot',
        string='Seriales Disponibles',
        compute='_compute_available_lot_ids',
        help='Seriales disponibles en la ubicación seleccionada',
    )

    note = fields.Text(
        string='Nota',
        help='Nota adicional sobre la transferencia',
    )

    @api.depends('location_id')
    def _compute_available_products(self):
        """Calcula los productos disponibles en la ubicación seleccionada"""
        for record in self:
            if not record.location_id:
                record.available_product_ids = False
                continue

            # Buscar quants con stock disponible en la ubicación
            quant_domain = [
                ('location_id', '=', record.location_id.id),
                ('quantity', '>', 0),
            ]
            quants = self.env['stock.quant'].search(quant_domain)
            product_ids = quants.mapped('product_id').ids

            if product_ids:
                products = self.env['product.product'].browse(product_ids)
                record.available_product_ids = products.ids
            else:
                record.available_product_ids = False

    @api.model
    def _get_location_domain(self):
        """Retorna el dominio para filtrar ubicaciones internas y en tránsito"""
        # Retornar todas las ubicaciones de tipo internal o transit
        # Incluye ubicaciones con y sin stock
        return [('usage', 'in', ['internal', 'transit'])]

    @api.depends('source_product_id', 'location_id')
    def _compute_available_lot_ids(self):
        """Calcula los seriales disponibles en la ubicación seleccionada para el producto origen"""
        for record in self:
            if not record.source_product_id or not record.location_id:
                record.available_lot_ids = False
                continue

            # Buscar quants con stock disponible en la ubicación para el producto origen
            quants = self.env['stock.quant'].search([
                ('product_id', '=', record.source_product_id.id),
                ('location_id', '=', record.location_id.id),
                ('quantity', '>', 0),
                ('lot_id', '!=', False),
            ])

            record.available_lot_ids = quants.mapped('lot_id')

    @api.onchange('location_id')
    def _onchange_filters(self):
        """Limpia los productos seleccionados cuando cambia la ubicación"""
        if self.source_product_id:
            # Verificar si el producto origen sigue siendo válido
            if self.available_product_ids and self.source_product_id.id not in self.available_product_ids.ids:
                self.source_product_id = False
                self.lot_ids = False
        if self.destination_product_id:
            # Verificar si el producto destino sigue siendo válido
            if self.available_product_ids and self.destination_product_id.id not in self.available_product_ids.ids:
                self.destination_product_id = False

    @api.onchange('source_product_id')
    def _onchange_source_product(self):
        """Limpia los lotes seleccionados cuando cambia el producto origen"""
        if self.source_product_id:
            self.lot_ids = False
            # Si el producto destino es igual al origen, limpiarlo
            if self.destination_product_id and self.destination_product_id.id == self.source_product_id.id:
                self.destination_product_id = False
    
    @api.onchange('destination_product_id')
    def _onchange_destination_product(self):
        """Valida que el producto destino sea diferente al origen"""
        if self.source_product_id and self.destination_product_id:
            if self.source_product_id.id == self.destination_product_id.id:
                return {
                    'warning': {
                        'title': _('Productos iguales'),
                        'message': _('El producto origen y destino no pueden ser el mismo. Por favor, seleccione un producto destino diferente.'),
                    }
                }

    @api.constrains('source_product_id', 'destination_product_id')
    def _check_different_products(self):
        """Valida que los productos origen y destino sean diferentes"""
        for record in self:
            if record.source_product_id and record.destination_product_id:
                if record.source_product_id.id == record.destination_product_id.id:
                    raise ValidationError(_('El producto origen y destino no pueden ser el mismo.'))

    @api.constrains('lot_ids', 'operation_mode')
    def _check_conversion_data(self):
        """Valida que se haya proporcionado la información necesaria para la conversión"""
        for record in self:
            if not record.lot_ids or len(record.lot_ids) != 1:
                raise ValidationError(_('Debe seleccionar exactamente un serial/lote del producto genérico para convertir.'))

    def action_transfer(self):
        """Ejecuta la conversión de producto genérico a específico"""
        self.ensure_one()

        # IMPORTANTE: En modo conversión, las relaciones se eliminan en _convert_generic_to_specific()

        # Validaciones adicionales
        if not self.source_product_id or not self.destination_product_id:
            raise UserError(_('Debe seleccionar producto origen y destino.'))

        if not self.location_id:
            raise UserError(_('Debe seleccionar una ubicación.'))

        if self.source_product_id.id == self.destination_product_id.id:
            raise UserError(_('El producto origen y destino no pueden ser el mismo. Por favor, seleccione productos diferentes.'))

        # Verificar que los productos tengan seguimiento por seriales/lotes
        source_tracking = self.source_product_id.tracking
        dest_tracking = self.destination_product_id.tracking

        if source_tracking == 'none' or dest_tracking == 'none':
            raise UserError(_('Ambos productos deben tener seguimiento por seriales/lotes para realizar la conversión.'))

        if not self.lot_ids or len(self.lot_ids) != 1:
            raise UserError(_('Debe seleccionar exactamente un serial/lote del producto genérico para convertir.'))

        # Ejecutar la conversión
        try:
            result = self._convert_generic_to_specific()

            # Mostrar mensaje de éxito
            message = _('✅ Conversión completada exitosamente.')
            message += _('\nProducto genérico eliminado: %s (Serial: %s)') % (
                self.source_product_id.display_name,
                self.lot_ids[0].name if self.lot_ids else 'N/A'
            )
            message += _('\nProducto específico creado: %s') % self.destination_product_id.display_name
            new_lot_name = _safe_get(result, 'new_lot_name')
            if new_lot_name:
                message += _('\nNuevo serial: %s') % new_lot_name

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Éxito'),
                    'message': message,
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            _logger.error('Error al convertir producto: %s', str(e), exc_info=True)
            
            # Si hay un error, limpiar las líneas dummy de bloqueo y lotes temporales
            # IMPORTANTE: No intentar eliminar los lotes temporales si tienen referencias para evitar errores de clave foránea
            if 'stock.lot.supply.line' in self.env:
                try:
                    # Buscar lotes temporales
                    self.env.cr.execute("""
                        SELECT id FROM stock_lot 
                        WHERE name LIKE 'TEMP-BLOCK-%%'
                    """)
                    temp_lot_ids = [row[0] for row in self.env.cr.fetchall()]
                    
                    if temp_lot_ids:
                        # Limpiar líneas de supply_line que referencian lotes temporales
                        # En lugar de eliminar, establecer related_lot_id a NULL
                        self.env.cr.execute("""
                            UPDATE stock_lot_supply_line 
                            SET related_lot_id = NULL 
                            WHERE related_lot_id IN %s
                        """, (tuple(temp_lot_ids),))
                        
                        # Eliminar líneas donde el lote temporal es el lot_id principal
                        self.env.cr.execute("""
                            DELETE FROM stock_lot_supply_line 
                            WHERE lot_id IN %s
                        """, (tuple(temp_lot_ids),))
                        
                        self.env.cr.commit()
                        _logger.info('🧹 Limpieza de líneas de supply_line de lotes temporales después del error. Los lotes temporales permanecerán en el sistema.')
                except Exception as cleanup_error:
                    _logger.error('Error al limpiar líneas de supply_line de lotes temporales: %s', str(cleanup_error))
            
            raise UserError(_('Error al convertir producto: %s') % str(e))

    def action_show_debug_info(self):
        """Muestra información de debug sobre los lotes y líneas de supply_line"""
        self.ensure_one()
        
        debug_info = []
        debug_info.append("=" * 80)
        debug_info.append("INFORMACIÓN DE DEBUG - CONVERSIÓN DE PRODUCTOS")
        debug_info.append("=" * 80)
        debug_info.append("")
        
        if not self.lot_ids:
            debug_info.append("⚠️ No hay lotes seleccionados para convertir")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Debug Info',
                    'message': '\n'.join(debug_info),
                    'type': 'warning',
                    'sticky': True,
                }
            }
        
        # Información de los lotes a transferir
        debug_info.append("📦 LOTES A TRANSFERIR:")
        debug_info.append("-" * 80)
        for lot in self.lot_ids:
            debug_info.append(f"  Lote: {lot.name} (ID: {lot.id})")
            debug_info.append(f"    Producto: {lot.product_id.name} (ID: {lot.product_id.id})")
            debug_info.append(f"    Ubicación actual: {lot.location_id.name if lot.location_id else 'N/A'}")
            debug_info.append(f"    Stock disponible: {lot.product_qty}")
            
            # Buscar quants
            quants = self.env['stock.quant'].search([
                ('lot_id', '=', lot.id),
                ('location_id', '=', self.location_id.id),
                ('quantity', '>', 0),
            ])
            debug_info.append(f"    Quants en ubicación {self.location_id.name}: {len(quants)}")
            for quant in quants:
                debug_info.append(f"      - Quant ID {quant.id}: {quant.quantity} unidades")
            debug_info.append("")
        
        # Información de líneas de supply_line relacionadas
        if 'stock.lot.supply.line' in self.env:
            debug_info.append("🔗 LÍNEAS DE SUPPLY_LINE RELACIONADAS:")
            debug_info.append("-" * 80)
            
            lot_ids_to_transfer = self.lot_ids.ids
            product_ids_to_transfer = self.lot_ids.mapped('product_id').ids
            
            # 1. Líneas donde el lote es related_lot_id (componente)
            supply_lines_as_component = self.env['stock.lot.supply.line'].sudo().search([
                ('related_lot_id', 'in', lot_ids_to_transfer)
            ])
            debug_info.append(f"  Líneas donde el lote es COMPONENTE (related_lot_id): {len(supply_lines_as_component)}")
            for sl in supply_lines_as_component[:10]:  # Limitar a 10 para no saturar
                debug_info.append(f"    - ID {sl.id}: lot_id={sl.lot_id.name} (ID: {sl.lot_id.id}), related_lot_id={sl.related_lot_id.name} (ID: {sl.related_lot_id.id})")
                debug_info.append(f"      Producto: {sl.product_id.name}, Ubicación lot_id: {sl.lot_id.location_id.name if sl.lot_id.location_id else 'N/A'}")
                debug_info.append(f"      Ubicación related_lot_id: {sl.related_lot_id.location_id.name if sl.related_lot_id.location_id else 'N/A'}")
            if len(supply_lines_as_component) > 10:
                debug_info.append(f"    ... y {len(supply_lines_as_component) - 10} más")
            debug_info.append("")
            
            # 2. Líneas donde el lote es lot_id principal
            supply_lines_as_principal = self.env['stock.lot.supply.line'].sudo().search([
                ('lot_id', 'in', lot_ids_to_transfer),
                ('related_lot_id', '!=', False)
            ])
            debug_info.append(f"  Líneas donde el lote es PRINCIPAL (lot_id): {len(supply_lines_as_principal)}")
            for sl in supply_lines_as_principal[:10]:
                debug_info.append(f"    - ID {sl.id}: lot_id={sl.lot_id.name} (ID: {sl.lot_id.id}), related_lot_id={sl.related_lot_id.name} (ID: {sl.related_lot_id.id})")
                debug_info.append(f"      Producto: {sl.product_id.name}")
            if len(supply_lines_as_principal) > 10:
                debug_info.append(f"    ... y {len(supply_lines_as_principal) - 10} más")
            debug_info.append("")
            
            # 3. Líneas que podrían intentar auto-asignar estos lotes
            potential_lines = self.env['stock.lot.supply.line'].sudo().search([
                ('related_lot_id', '=', False),
                ('product_id', 'in', product_ids_to_transfer)
            ])
            debug_info.append(f"  Líneas que PODRÍAN auto-asignar estos lotes (related_lot_id=NULL, product_id en productos a transferir): {len(potential_lines)}")
            for sl in potential_lines[:10]:
                debug_info.append(f"    - ID {sl.id}: lot_id={sl.lot_id.name} (ID: {sl.lot_id.id}), product_id={sl.product_id.name}")
                debug_info.append(f"      Ubicación lot_id: {sl.lot_id.location_id.name if sl.lot_id.location_id else 'N/A'}")
            if len(potential_lines) > 10:
                debug_info.append(f"    ... y {len(potential_lines) - 10} más")
            debug_info.append("")
            
            # 4. Verificar líneas bloqueadas (con related_lot_id = -1)
            self.env.cr.execute("""
                SELECT COUNT(*) FROM stock_lot_supply_line 
                WHERE related_lot_id = -1 AND product_id IN %s
            """, (tuple(product_ids_to_transfer),))
            blocked_count = self.env.cr.fetchone()[0] if self.env.cr.rowcount > 0 else 0
            debug_info.append(f"  Líneas BLOQUEADAS (related_lot_id=-1): {blocked_count}")
            debug_info.append("")
        
        # Información del producto destino
        debug_info.append("🎯 PRODUCTO DESTINO:")
        debug_info.append("-" * 80)
        if self.destination_product_id:
            debug_info.append(f"  Producto: {self.destination_product_id.name} (ID: {self.destination_product_id.id})")
            
            # Verificar si el producto destino tiene componentes definidos
            if hasattr(self.destination_product_id.product_tmpl_id, 'composite_line_ids'):
                composite_lines = self.destination_product_id.product_tmpl_id.composite_line_ids
                debug_info.append(f"  Componentes definidos: {len(composite_lines)}")
                for comp in composite_lines[:5]:
                    debug_info.append(f"    - {comp.component_product_id.name} (cantidad: {comp.component_qty})")
                if len(composite_lines) > 5:
                    debug_info.append(f"    ... y {len(composite_lines) - 5} más")
        debug_info.append("")
        
        debug_info.append("=" * 80)
        debug_info.append("FIN DE INFORMACIÓN DE DEBUG")
        debug_info.append("=" * 80)
        
        # Mostrar en una ventana de diálogo
        message = '\n'.join(debug_info)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': '🔍 Información de Debug',
                'message': message,
                'type': 'info',
                'sticky': True,
            }
        }

    def _transfer_by_lots(self, supply_lines_to_update=None):
        """Transfiere seriales específicos de un producto a otro"""
        self.ensure_one()
        
        if supply_lines_to_update is None:
            supply_lines_to_update = []
        
        # Limpiar relaciones de supply_line antes de la transferencia

        # Obtener el tipo de operación de ajuste interno
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('warehouse_id', '=', self.location_id.warehouse_id.id),
        ], limit=1)

        if not picking_type:
            # Buscar cualquier tipo de operación interno
            picking_type = self.env['stock.picking.type'].search([
                ('code', '=', 'internal'),
            ], limit=1)

        if not picking_type:
            raise UserError(_('No se encontró un tipo de operación interno. Por favor, configure uno en Configuración > Inventario.'))

        # Obtener ubicación de inventario para ajustes
        inventory_location = self.env['stock.location'].search([
            ('usage', '=', 'inventory'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)

        if not inventory_location:
            # Si no hay ubicación de inventario, usar la ubicación de origen
            inventory_location = self.location_id

        # Las relaciones ya fueron limpiadas en action_transfer antes de llegar aquí
        # supply_lines_to_update ya viene como parámetro desde action_transfer

        # Crear el picking de transferencia (ajuste interno)
        picking_vals = {
            'picking_type_id': picking_type.id,
            'location_id': self.location_id.id,
            'location_dest_id': inventory_location.id,  # Ubicación de inventario para ajuste
            'origin': _('Transferencia de Producto: %s -> %s') % (
                self.source_product_id.display_name,
                self.destination_product_id.display_name
            ),
            'note': self.note or '',
        }

        picking = self.env['stock.picking'].create(picking_vals)

        # Agrupar lotes por cantidad disponible en la ubicación
        lot_quantities = {}
        
        for lot in self.lot_ids:
            quant = self.env['stock.quant'].search([
                ('product_id', '=', self.source_product_id.id),
                ('location_id', '=', self.location_id.id),
                ('lot_id', '=', lot.id),
                ('quantity', '>', 0),
            ], limit=1)

            if not quant:
                raise UserError(_('El serial/lote %s no tiene stock disponible en la ubicación %s.') % (
                    lot.name, self.location_id.display_name
                ))

            lot_quantities[lot.id] = quant.quantity

        # Crear movimiento de salida (producto origen) (Odoo 19: stock.move usa description_picking, no name)
        move_out_vals = {
            'description_picking': _('Transferencia: %s -> %s') % (
                self.source_product_id.display_name,
                self.destination_product_id.display_name
            ),
            'product_id': self.source_product_id.id,
            'product_uom': self.source_product_id.uom_id.id,
            'product_uom_qty': sum(lot_quantities.values()),
            'picking_id': picking.id,
            'location_id': self.location_id.id,
            'location_dest_id': inventory_location.id,
        }

        move_out = self.env['stock.move'].create(move_out_vals)

        # Crear líneas de movimiento para cada lote (salida)
        move_line_env = self.env['stock.move.line']
        for lot_id, qty in lot_quantities.items():
            move_line_env.create({
                'move_id': move_out.id,
                'product_id': self.source_product_id.id,
                'product_uom_id': self.source_product_id.uom_id.id,
                'location_id': self.location_id.id,
                'location_dest_id': inventory_location.id,
                'lot_id': lot_id,
                'qty_done': qty,
            })

        # Crear picking de entrada (producto destino) desde inventario a ubicación
        picking_in_vals = {
            'picking_type_id': picking_type.id,
            'location_id': inventory_location.id,
            'location_dest_id': self.location_id.id,
            'origin': _('Transferencia de Producto: %s -> %s') % (
                self.source_product_id.display_name,
                self.destination_product_id.display_name
            ),
            'note': self.note or '',
        }

        picking_in = self.env['stock.picking'].create(picking_in_vals)

        # Crear movimiento de entrada (producto destino) (Odoo 19: stock.move usa description_picking, no name)
        move_in_vals = {
            'description_picking': _('Transferencia: %s -> %s') % (
                self.source_product_id.display_name,
                self.destination_product_id.display_name
            ),
            'product_id': self.destination_product_id.id,
            'product_uom': self.destination_product_id.uom_id.id,
            'product_uom_qty': sum(lot_quantities.values()),
            'picking_id': picking_in.id,
            'location_id': inventory_location.id,
            'location_dest_id': self.location_id.id,
        }

        move_in = self.env['stock.move'].create(move_in_vals)

        # Crear líneas de movimiento para cada lote (entrada)
        # Transferir los seriales al nuevo producto copiando toda la información
        move_line_env = self.env['stock.move.line']
        old_lots_transferred = []  # Guardar los lotes originales transferidos (para referencia, no para eliminar)
        lot_mapping = {}  # Mapeo de old_lot_id -> new_lot_id para transferencia de movimientos históricos
        
        for lot_id, qty in lot_quantities.items():
            old_lot = self.env['stock.lot'].browse(lot_id)
            
            # Verificar si ya existe un lote con el mismo nombre en el producto destino
            new_lot = self.env['stock.lot'].search([
                ('product_id', '=', self.destination_product_id.id),
                ('name', '=', old_lot.name),
            ], limit=1)

            if not new_lot:
                # Preparar valores para copiar toda la información del lote original
                lot_vals = {
                    'name': old_lot.name,
                    'product_id': self.destination_product_id.id,
                    'company_id': old_lot.company_id.id,
                }
                
                # Copiar campos estándar de stock.lot
                if hasattr(old_lot, 'ref'):
                    lot_vals['ref'] = old_lot.ref
                if hasattr(old_lot, 'note'):
                    lot_vals['note'] = old_lot.note
                
                # Copiar campos personalizados de product_suppiles si existen
                if hasattr(old_lot, 'inventory_plate'):
                    lot_vals['inventory_plate'] = old_lot.inventory_plate
                if hasattr(old_lot, 'security_plate'):
                    lot_vals['security_plate'] = old_lot.security_plate
                if hasattr(old_lot, 'billing_code'):
                    lot_vals['billing_code'] = old_lot.billing_code
                if hasattr(old_lot, 'model_name'):
                    lot_vals['model_name'] = old_lot.model_name
                if hasattr(old_lot, 'purchase_tracking_ref'):
                    lot_vals['purchase_tracking_ref'] = old_lot.purchase_tracking_ref
                if hasattr(old_lot, 'is_principal'):
                    lot_vals['is_principal'] = old_lot.is_principal
                # No copiar principal_product_id ni principal_lot_id porque son del producto origen
                
                # Copiar campos de product_suppiles_partner si existen
                if hasattr(old_lot, 'related_partner_id') and old_lot.related_partner_id:
                    lot_vals['related_partner_id'] = old_lot.related_partner_id.id
                
                # IMPORTANTE: El módulo auto_link_components crea automáticamente líneas de supply_line
                # cuando se crea un nuevo lote, y estas líneas intentan auto-asignar related_lot_id,
                # lo cual activa la validación DURANTE el create. El problema es que la validación se
                # ejecuta antes de que podamos limpiar las líneas.
                #
                # SOLUCIÓN: Bloquear TODAS las líneas de supply_line que podrían intentar auto-asignar
                # el lote que estamos transfiriendo ANTES de crear el nuevo lote. Esto evita que el
                # método create de stock.lot.supply.line intente asignar el lote problemático.
                
                # Eliminar temporalmente líneas que podrían intentar auto-asignar el lote que estamos transfiriendo
                # ANTES de crear el nuevo lote
                if 'stock.lot.supply.line' in self.env:
                    # IMPORTANTE: El problema es que cuando se crea el nuevo lote, el módulo auto_link_components
                    # crea líneas de supply_line automáticamente, y estas líneas intentan auto-asignar related_lot_id
                    # usando la ubicación del nuevo lote (rec.lot_id.location_id.id). Si el nuevo lote tiene una
                    # ubicación diferente, puede intentar asignar lotes que están en ubicaciones diferentes, lo cual
                    # causa el error de validación.
                    #
                    # SOLUCIÓN: Eliminar temporalmente las líneas problemáticas que podrían auto-asignar el lote
                    # que estamos transfiriendo. Estas líneas se restaurarán después de la transferencia.
                    
                    # Buscar y eliminar temporalmente líneas con related_lot_id NULL para el producto del lote a transferir
                    self.env.cr.execute("""
                        SELECT id, lot_id, item_type, product_id, quantity, uom_id, related_lot_id, create_uid, create_date
                        FROM stock_lot_supply_line 
                        WHERE related_lot_id IS NULL 
                        AND product_id = %s
                    """, (old_lot.product_id.id,))
                    
                    lines_to_restore_per_lot = []
                    for row in self.env.cr.fetchall():
                        line_id, lot_id, item_type, product_id, quantity, uom_id, related_lot_id, create_uid, create_date = row
                        lines_to_restore_per_lot.append({
                            'id': line_id,
                            'lot_id': lot_id,
                            'item_type': item_type,
                            'product_id': product_id,
                            'quantity': quantity,
                            'uom_id': uom_id,
                            'related_lot_id': related_lot_id,
                            'create_uid': create_uid,
                            'create_date': create_date,
                        })
                    
                    # Eliminar temporalmente las líneas problemáticas
                    if lines_to_restore_per_lot:
                        line_ids_to_delete = [line['id'] for line in lines_to_restore_per_lot]
                        self.env.cr.execute("""
                            DELETE FROM stock_lot_supply_line 
                            WHERE id IN %s
                        """, (tuple(line_ids_to_delete),))
                        self.env.cr.commit()
                        _logger.info('🔒 Eliminadas temporalmente %s líneas con related_lot_id NULL para producto %s (ID: %s). Se restaurarán después.', 
                                    len(lines_to_restore_per_lot), old_lot.product_id.name, old_lot.product_id.id)
                        
                        # Agregar estas líneas a la lista de restauración global
                        supply_lines_to_update.extend(lines_to_restore_per_lot)
                    
                    _logger.info('🔒 Preparación de lote %s (ID: %s) completada. Líneas problemáticas eliminadas temporalmente.', 
                                old_lot.name, old_lot.id)
                
                # Crear nuevo lote para el producto destino con toda la información
                # IMPORTANTE: Usar un contexto especial para evitar que el módulo auto_link_components
                # (si todavía está activo) intente crear relaciones automáticamente
                _logger.info('📦 Creando nuevo lote para producto destino %s (ID: %s) con nombre %s', 
                            self.destination_product_id.name, self.destination_product_id.id, _safe_get(lot_vals, 'name'))
                
                try:
                    # IMPORTANTE: Verificar una última vez que todas las líneas problemáticas estén eliminadas
                    # antes de crear el nuevo lote. Esto es crítico para evitar que auto_link_components
                    # intente auto-asignar el lote que estamos transfiriendo
                    self.env.cr.execute("""
                        SELECT COUNT(*) FROM stock_lot_supply_line 
                        WHERE related_lot_id IS NULL 
                        AND product_id = %s
                    """, (old_lot.product_id.id,))
                    remaining_count = self.env.cr.fetchone()[0]
                    if remaining_count > 0:
                        _logger.warning('⚠️ Aún hay %s líneas sin eliminar para producto %s (ID: %s). Eliminándolas ahora...', 
                                      remaining_count, old_lot.product_id.name, old_lot.product_id.id)
                        # Guardar información de líneas adicionales antes de eliminarlas
                        self.env.cr.execute("""
                            SELECT id, lot_id, item_type, product_id, quantity, uom_id, related_lot_id, create_uid, create_date
                            FROM stock_lot_supply_line 
                            WHERE related_lot_id IS NULL 
                            AND product_id = %s
                        """, (old_lot.product_id.id,))
                        
                        additional_lines = []
                        for row in self.env.cr.fetchall():
                            line_id, lot_id, item_type, product_id, quantity, uom_id, related_lot_id, create_uid, create_date = row
                            additional_lines.append({
                                'id': line_id,
                                'lot_id': lot_id,
                                'item_type': item_type,
                                'product_id': product_id,
                                'quantity': quantity,
                                'uom_id': uom_id,
                                'related_lot_id': related_lot_id,
                                'create_uid': create_uid,
                                'create_date': create_date,
                            })
                        
                        # Eliminar las líneas adicionales
                        if additional_lines:
                            line_ids_to_delete = [line['id'] for line in additional_lines]
                            self.env.cr.execute("""
                                DELETE FROM stock_lot_supply_line 
                                WHERE id IN %s
                            """, (tuple(line_ids_to_delete),))
                            self.env.cr.commit()
                            _logger.info('🔒 Eliminadas %s líneas adicionales antes de crear el nuevo lote', len(additional_lines))
                            supply_lines_to_update.extend(additional_lines)
                    
                    # IMPORTANTE: Crear el nuevo lote y limpiar INMEDIATAMENTE cualquier relación que se cree automáticamente
                    # El módulo auto_link_components puede crear relaciones automáticamente, pero las limpiaremos de inmediato
                    # para evitar que intenten auto-asignar el lote que estamos transfiriendo
                    try:
                        # Crear el lote
                        new_lot = self.env['stock.lot'].with_context(
                            skip_auto_link=True,
                            no_auto_link=True,
                            skip_supply_line_creation=True
                        ).create(lot_vals)
                        _logger.info('✅ Nuevo lote creado exitosamente: %s (ID: %s)', new_lot.name, new_lot.id)
                        
                        # IMPORTANTE: Limpiar INMEDIATAMENTE cualquier relación que se haya creado automáticamente
                        # Esto debe hacerse ANTES de que cualquier validación se ejecute
                        if 'stock.lot.supply.line' in self.env:
                            # Limpiar TODAS las líneas del nuevo lote que se hayan creado automáticamente
                            self.env.cr.execute("""
                                DELETE FROM stock_lot_supply_line 
                                WHERE lot_id = %s
                            """, (new_lot.id,))
                            
                            # También limpiar cualquier línea que tenga related_lot_id apuntando al nuevo lote
                            self.env.cr.execute("""
                                UPDATE stock_lot_supply_line 
                                SET related_lot_id = NULL 
                                WHERE related_lot_id = %s
                            """, (new_lot.id,))
                            
                            # IMPORTANTE: NO limpiar líneas que referencian old_lot.id porque esto podría causar
                            # errores de clave foránea si se intenta eliminar algo. Solo mantenerlas bloqueadas.
                            # Las líneas que referencian old_lot.id se mantendrán bloqueadas (related_lot_id = -1)
                            # y no se modificarán durante la transferencia
                            
                            self.env.cr.commit()
                            _logger.info('🧹 Limpieza inmediata de relaciones automáticas completada para nuevo lote %s', new_lot.name)
                            
                    except Exception as create_error:
                        # Si falla con el contexto, intentar sin contexto pero con el bloqueo aplicado
                        _logger.warning('⚠️ Error al crear lote con contexto especial: %s. Intentando sin contexto...', str(create_error))
                        new_lot = self.env['stock.lot'].create(lot_vals)
                        _logger.info('✅ Nuevo lote creado exitosamente (sin contexto): %s (ID: %s)', new_lot.name, new_lot.id)
                        
                        # Limpiar relaciones incluso si se creó sin contexto
                        # IMPORTANTE: Solo limpiar líneas del nuevo lote, NO tocar líneas que referencian old_lot.id
                        if 'stock.lot.supply.line' in self.env:
                            self.env.cr.execute("""
                                DELETE FROM stock_lot_supply_line 
                                WHERE lot_id = %s
                            """, (new_lot.id,))
                            # Solo limpiar líneas que referencian el nuevo lote, NO las que referencian old_lot.id
                            self.env.cr.execute("""
                                UPDATE stock_lot_supply_line 
                                SET related_lot_id = NULL 
                                WHERE related_lot_id = %s
                            """, (new_lot.id,))
                            self.env.cr.commit()
                            _logger.info('🧹 Limpieza inmediata de relaciones automáticas completada (fallback) - Solo nuevo lote')
                except Exception as create_error:
                    _logger.error('❌ Error al crear nuevo lote: %s', str(create_error), exc_info=True)
                    # Si hay un error, verificar qué líneas se crearon
                    if 'stock.lot.supply.line' in self.env:
                        self.env.cr.execute("""
                            SELECT id, lot_id, product_id, related_lot_id, create_date 
                            FROM stock_lot_supply_line 
                            WHERE create_date > NOW() - INTERVAL '5 seconds'
                            ORDER BY create_date DESC
                            LIMIT 20
                        """)
                        recent_lines = self.env.cr.fetchall()
                        if recent_lines:
                            _logger.error('📋 Líneas de supply_line creadas recientemente (últimos 5 segundos):')
                            for line_id, lot_id, product_id, related_lot_id, create_date in recent_lines:
                                _logger.error('  - ID: %s, lot_id: %s, product_id: %s, related_lot_id: %s, create_date: %s', 
                                            line_id, lot_id, product_id, related_lot_id, create_date)
                    raise
                
                # NOTA: La limpieza de relaciones ya se hizo inmediatamente después de crear el lote
                # (ver código arriba). Esta sección ya no es necesaria, pero la mantenemos por compatibilidad
                # si hay algún caso donde no se ejecutó la limpieza inmediata
                if 'stock.lot.supply.line' in self.env:
                    # Verificar si quedan líneas del nuevo lote que no se limpiaron
                    self.env.cr.execute(
                        "SELECT COUNT(*) FROM stock_lot_supply_line WHERE lot_id = %s",
                        (new_lot.id,)
                    )
                    line_count = self.env.cr.fetchone()[0]
                    if line_count > 0:
                        _logger.warning('⚠️ Aún hay %s líneas de supply_line para el nuevo lote. Limpiándolas...', line_count)
                        self.env.cr.execute(
                            "DELETE FROM stock_lot_supply_line WHERE lot_id = %s",
                            (new_lot.id,)
                        )
                        self.env.cr.commit()
                        _logger.info('🧹 Limpieza adicional de líneas auto-creadas para nuevo lote %s (ID: %s): %s líneas eliminadas', new_lot.name, new_lot.id, line_count)
                
                # Copiar las líneas de supply_line si existen en el lote original
                if hasattr(old_lot, 'lot_supply_line_ids') and old_lot.lot_supply_line_ids:
                    for supply_line in old_lot.lot_supply_line_ids:
                        # Crear la línea usando SQL directo para evitar que el método create intente auto-asignar related_lot_id
                        # Primero obtener el ID de uom_id si existe
                        uom_id = supply_line.uom_id.id if supply_line.uom_id else None
                        self.env.cr.execute("""
                            INSERT INTO stock_lot_supply_line 
                            (lot_id, item_type, product_id, quantity, uom_id, related_lot_id, create_uid, create_date, write_uid, write_date)
                            VALUES (%s, %s, %s, %s, %s, NULL, %s, NOW(), %s, NOW())
                            RETURNING id
                        """, (
                            new_lot.id,
                            supply_line.item_type,
                            supply_line.product_id.id,
                            supply_line.quantity,
                            uom_id,
                            self.env.user.id,
                            self.env.user.id,
                        ))
                        created_id = self.env.cr.fetchone()[0]
                        self.env.cr.commit()
                        _logger.debug('Línea de supply_line creada usando SQL directo: ID %s', created_id)
            else:
                # Si el lote ya existe, actualizar sus campos con la información del lote original
                update_vals = {}
                if hasattr(old_lot, 'inventory_plate') and old_lot.inventory_plate and not new_lot.inventory_plate:
                    update_vals['inventory_plate'] = old_lot.inventory_plate
                if hasattr(old_lot, 'security_plate') and old_lot.security_plate and not new_lot.security_plate:
                    update_vals['security_plate'] = old_lot.security_plate
                if hasattr(old_lot, 'billing_code') and old_lot.billing_code and not new_lot.billing_code:
                    update_vals['billing_code'] = old_lot.billing_code
                if hasattr(old_lot, 'model_name') and old_lot.model_name and not new_lot.model_name:
                    update_vals['model_name'] = old_lot.model_name
                if hasattr(old_lot, 'related_partner_id') and old_lot.related_partner_id and not new_lot.related_partner_id:
                    update_vals['related_partner_id'] = old_lot.related_partner_id.id
                
                if update_vals:
                    new_lot.write(update_vals)

            # Guardar el lote original para referencia (no lo eliminamos para evitar conflictos)
            old_lots_transferred.append(old_lot.id)
            
            # Guardar el mapeo de lotes para transferencia de movimientos históricos
            lot_mapping[lot_id] = new_lot.id

            move_line_env.create({
                'move_id': move_in.id,
                'product_id': self.destination_product_id.id,
                'product_uom_id': self.destination_product_id.uom_id.id,
                'location_id': inventory_location.id,
                'location_dest_id': self.location_id.id,
                'lot_id': new_lot.id,
                'qty_done': qty,
            })

        # Confirmar y validar ambos pickings
        picking.action_confirm()
        picking.action_assign()
        # Odoo 19: move_line_ids_without_package fue eliminado; usar move_line_ids
        pick_lines = getattr(picking, 'move_line_ids_without_package', picking.move_line_ids)
        for move_line in pick_lines:
            if move_line.qty_done <= 0:
                move_line.qty_done = move_line.reserved_uom_qty
        picking.button_validate()

        picking_in.action_confirm()
        picking_in.action_assign()
        pick_in_lines = getattr(picking_in, 'move_line_ids_without_package', picking_in.move_line_ids)
        for move_line in pick_in_lines:
            if move_line.qty_done <= 0:
                move_line.qty_done = move_line.reserved_uom_qty
        picking_in.button_validate()
        
        # Transferir movimientos históricos relacionados con los lotes transferidos
        # Esto actualiza las referencias en stock.move y stock.move.line para que apunten al nuevo producto/lote
        # El mapeo de lotes ya se construyó durante la creación de los lotes nuevos
        if lot_mapping:
            _logger.info('🔄 Iniciando transferencia de movimientos históricos para %s lotes', len(lot_mapping))
            self._transfer_historical_moves(lot_mapping)
        else:
            _logger.warning('⚠️ No se encontró mapeo de lotes para transferir movimientos históricos')
        
        # Nota: No eliminamos los lotes originales para evitar conflictos con restricciones de clave foránea
        # Los lotes quedarán en el sistema pero sin stock después de la transferencia

        # IMPORTANTE: En lugar de eliminar los lotes originales, los dejamos sin stock
        # Esto evita conflictos con restricciones de clave foránea de stock.lot.supply.line
        # Los lotes quedarán en el sistema pero sin stock, lo cual es más seguro y evita errores
        
        # Limpiar lotes temporales de bloqueo si existen
        # IMPORTANTE: En lugar de eliminar los lotes temporales (que puede causar errores de clave foránea),
        # simplemente limpiaremos las líneas de supply_line que los referencian y dejaremos los lotes en el sistema
        # Los lotes temporales no afectarán la funcionalidad y pueden ser limpiados manualmente después si es necesario
        if 'stock.lot.supply.line' in self.env:
            # Buscar los IDs de los lotes temporales
            self.env.cr.execute("""
                SELECT id FROM stock_lot 
                WHERE name LIKE 'TEMP-BLOCK-%%'
            """)
            temp_lot_ids = [row[0] for row in self.env.cr.fetchall()]
            
            if temp_lot_ids:
                # Limpiar las líneas de supply_line que referencian estos lotes
                # Hacerlo en un bucle para asegurarnos de que no queden referencias
                max_iterations = 5
                iteration = 0
                while iteration < max_iterations:
                    self.env.cr.execute("""
                        SELECT COUNT(*) FROM stock_lot_supply_line 
                        WHERE lot_id IN %s OR related_lot_id IN %s
                    """, (tuple(temp_lot_ids), tuple(temp_lot_ids)))
                    remaining_count = self.env.cr.fetchone()[0]
                    
                    if remaining_count == 0:
                        break  # No hay más líneas que limpiar
                    
                    # Limpiar las líneas estableciendo related_lot_id a NULL en lugar de eliminarlas
                    # Esto evita problemas de clave foránea
                    self.env.cr.execute("""
                        UPDATE stock_lot_supply_line 
                        SET related_lot_id = NULL 
                        WHERE related_lot_id IN %s
                    """, (tuple(temp_lot_ids),))
                    
                    # Eliminar líneas donde el lote temporal es el lot_id principal
                    self.env.cr.execute("""
                        DELETE FROM stock_lot_supply_line 
                        WHERE lot_id IN %s
                    """, (tuple(temp_lot_ids),))
                    
                    self.env.cr.commit()
                    iteration += 1
                    _logger.info('🧹 Iteración %s: Limpiadas líneas de supply_line de lotes temporales (restantes: %s)', iteration, remaining_count)
                
                _logger.info('✅ Limpieza de líneas de supply_line de lotes temporales completada. Los lotes temporales permanecerán en el sistema pero no afectarán la funcionalidad.')
        
        # Eliminar automáticamente los lotes originales después de la transferencia
        if old_lots_transferred:
            old_lots = self.env['stock.lot'].browse(old_lots_transferred)
            for old_lot in old_lots:
                if not old_lot.exists():
                    continue
                
                # Verificar que no tenga stock en ninguna ubicación
                quants = self.env['stock.quant'].search([
                    ('lot_id', '=', old_lot.id),
                    ('quantity', '!=', 0),
                ])
                if quants:
                    # Si aún tiene stock, registrar advertencia y no eliminar
                    _logger.warning('⚠️ El lote %s (ID: %s) aún tiene stock después de la transferencia. No se eliminará.', old_lot.name, old_lot.id)
                else:
                    # El lote ya no tiene stock, proceder a eliminarlo automáticamente
                    _logger.info('🗑️ Eliminando automáticamente lote original %s (ID: %s) después de la transferencia', 
                                old_lot.name, old_lot.id)
                    self._delete_lot_safely(old_lot)

        # Restaurar las relaciones de supply_line si existían
        # Actualizar la ubicación en las relaciones si el módulo product_suppiles está instalado
        if supply_lines_to_update and 'stock.lot.supply.line' in self.env:
            _logger.info('Restaurando %s relaciones de supply_line', len(supply_lines_to_update))
            for supply_line_data in supply_lines_to_update:
                if not isinstance(supply_line_data, dict):
                    _logger.warning('Saltando supply_line_data no-dict: %s', type(supply_line_data))
                    continue
                # Verificar si es una línea eliminada temporalmente (tiene item_type) o una línea existente
                if 'item_type' in supply_line_data:
                    # Es una línea eliminada temporalmente, restaurarla
                    try:
                        self.env.cr.execute("""
                            INSERT INTO stock_lot_supply_line 
                            (lot_id, item_type, product_id, quantity, uom_id, related_lot_id, create_uid, create_date, write_uid, write_date)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                            RETURNING id
                        """, (
                            supply_line_data['lot_id'],
                            supply_line_data['item_type'],
                            supply_line_data['product_id'],
                            supply_line_data['quantity'],
                            supply_line_data['uom_id'],
                            supply_line_data['related_lot_id'],
                            supply_line_data['create_uid'],
                            supply_line_data['create_date'],
                            self.env.user.id,
                        ))
                        restored_id = self.env.cr.fetchone()[0]
                        self.env.cr.commit()
                        _logger.debug('Línea restaurada: ID %s (originalmente %s)', restored_id, _safe_get(supply_line_data, 'id'))
                    except Exception as restore_error:
                        _logger.warning('No se pudo restaurar línea eliminada temporalmente (ID original: %s): %s', 
                                      _safe_get(supply_line_data, 'id'), str(restore_error))
                else:
                    # Es una línea existente que necesita actualización
                    supply_line = self.env['stock.lot.supply.line'].browse(supply_line_data['id'])
                    if not supply_line.exists():
                        continue
                    
                    original_related_lot_id = _safe_get(supply_line_data, 'related_lot_id')
                    
                    # Buscar el nuevo lote creado para el producto destino con el mismo nombre
                    new_lot = self.env['stock.lot'].search([
                        ('product_id', '=', self.destination_product_id.id),
                        ('name', '=', supply_line_data['lot_name']),
                    ], limit=1)
                    
                    if new_lot and original_related_lot_id:
                        # Si tenía un related_lot_id original, intentar restaurarlo con el nuevo lote
                        # Verificar que el nuevo lote esté en la misma ubicación que el lote principal
                        lot_principal = self.env['stock.lot'].browse(_safe_get(supply_line_data, 'lot_principal_id'))
                        if lot_principal and lot_principal.exists() and lot_principal.current_location_id:
                            # Verificar que el nuevo lote tenga stock en la ubicación del lote principal
                            quant_check = self.env['stock.quant'].search_count([
                                ('lot_id', '=', new_lot.id),
                                ('location_id', '=', lot_principal.current_location_id.id),
                                ('quantity', '>', 0),
                            ])
                            if quant_check > 0:
                                # Actualizar la relación usando SQL directo para evitar validaciones
                                self.env.cr.execute(
                                    "UPDATE stock_lot_supply_line SET related_lot_id = %s WHERE id = %s",
                                    (new_lot.id, supply_line.id)
                                )
                                self.env.cr.commit()
                                _logger.debug('Relación restaurada: supply_line %s -> new_lot %s', supply_line.id, new_lot.id)
                            else:
                                # Si no está en la misma ubicación, limpiar la relación
                                self.env.cr.execute(
                                    "UPDATE stock_lot_supply_line SET related_lot_id = NULL WHERE id = %s",
                                    (supply_line.id,)
                                )
                                self.env.cr.commit()
                        else:
                            # Si no hay lote principal válido, limpiar la relación
                            self.env.cr.execute(
                                "UPDATE stock_lot_supply_line SET related_lot_id = NULL WHERE id = %s",
                                (supply_line.id,)
                            )
                            self.env.cr.commit()
                    else:
                        # Si originalmente no tenía related_lot_id, mantenerlo así
                        _logger.debug('Relación mantenida sin cambios: supply_line %s (originalmente %s)', 
                                    supply_line.id, original_related_lot_id)

        return {
            'picking_name': _('%s y %s') % (picking.name, picking_in.name),
            'picking_id': picking.id,
        }

    def _delete_lot_safely(self, lot):
        """
        Elimina un lote de forma segura, limpiando todas sus referencias.
        
        Args:
            lot: Recordset de stock.lot a eliminar
        """
        self.ensure_one()
        
        if not lot.exists():
            return
        
        lot_name = lot.name
        lot_id = lot.id
        
        _logger.info('🗑️ Iniciando eliminación segura del lote %s (ID: %s)', lot_name, lot_id)
        
        # PASO 1: Eliminar relaciones de supply_line donde el lote es componente (related_lot_id)
        # Usar contexto para permitir eliminación desde el wizard
        if 'stock.lot.supply.line' in self.env:
            supply_lines_as_component = self.env['stock.lot.supply.line'].with_context(
                allow_delete_supply_relations=True
            ).search([
                ('related_lot_id', '=', lot_id),
            ])
            if supply_lines_as_component:
                _logger.info('🗑️ Eliminando %s relaciones donde el lote es componente', len(supply_lines_as_component))
                supply_lines_as_component.with_context(allow_delete_supply_relations=True).unlink()
        
        # PASO 2: Eliminar relaciones donde el lote es principal (lot_id)
        if 'stock.lot.supply.line' in self.env:
            supply_lines_as_principal = self.env['stock.lot.supply.line'].with_context(
                allow_delete_supply_relations=True
            ).search([
                ('lot_id', '=', lot_id),
            ])
            if supply_lines_as_principal:
                _logger.info('🗑️ Eliminando %s relaciones donde el lote es principal', len(supply_lines_as_principal))
                supply_lines_as_principal.with_context(allow_delete_supply_relations=True).unlink()
        
        # PASO 3: Eliminar o actualizar todos los quants que referencian el lote
        # IMPORTANTE: Antes de eliminar el lote, debemos eliminar o actualizar TODOS los quants que lo referencian
        # (incluso los que tienen cantidad 0), porque PostgreSQL no permite eliminar el lote si hay quants que lo referencian
        
        all_quants = self.env['stock.quant'].search([
            ('lot_id', '=', lot_id),
        ])
        
        if all_quants:
            _logger.info('🔍 Encontrados %s quants para el lote (incluyendo cantidad 0)', len(all_quants))
            
            # Intentar eliminar los quants usando el ORM (requiere permisos)
            try:
                all_quants.unlink()
                _logger.info('✅ Eliminados %s quants del lote', len(all_quants))
            except Exception as e:
                _logger.warning('⚠️ No se pudieron eliminar quants usando ORM: %s. Intentando con SQL...', str(e))
                # Si falla por permisos, usar SQL directo para actualizar lot_id a NULL
                try:
                    self.env.cr.execute("""
                        UPDATE stock_quant 
                        SET lot_id = NULL 
                        WHERE lot_id = %s
                    """, (lot_id,))
                    self.env.cr.commit()
                    _logger.info('✅ Actualizados %s quants del lote (lot_id = NULL)', len(all_quants))
                except Exception as sql_error:
                    _logger.error('❌ Error al actualizar quants con SQL: %s', str(sql_error))
                    # Si también falla SQL, intentar eliminar directamente con SQL (más agresivo)
                    try:
                        self.env.cr.execute("""
                            DELETE FROM stock_quant 
                            WHERE lot_id = %s
                        """, (lot_id,))
                        self.env.cr.commit()
                        _logger.info('✅ Eliminados %s quants del lote usando SQL directo', len(all_quants))
                    except Exception as delete_error:
                        _logger.error('❌ Error crítico: No se pudieron eliminar/actualizar quants: %s', str(delete_error))
                        raise UserError(_(
                            'No se pudo eliminar el lote %s porque aún tiene quants asociados. '
                            'Por favor, contacte al administrador. Error: %s'
                        ) % (lot_name, str(delete_error)))
        
        # Verificar una vez más que no queden quants
        remaining_quants_check = self.env['stock.quant'].search_count([
            ('lot_id', '=', lot_id),
        ])
        
        if remaining_quants_check > 0:
            _logger.warning('⚠️ Aún quedan %s quants después de la limpieza. Intentando limpieza adicional...', remaining_quants_check)
            # Último intento con SQL directo
            self.env.cr.execute("""
                UPDATE stock_quant 
                SET lot_id = NULL 
                WHERE lot_id = %s
            """, (lot_id,))
            self.env.cr.commit()
            _logger.info('✅ Limpieza adicional de quants completada')
        
        # PASO 4: Eliminar el lote (debería ser seguro ahora)
        try:
            lot.unlink()
            _logger.info('✅ Lote eliminado exitosamente: %s (ID: %s)', lot_name, lot_id)
        except Exception as unlink_error:
            _logger.error('❌ Error al eliminar lote: %s', str(unlink_error))
            # Si aún falla, intentar con SQL directo (último recurso)
            try:
                # Primero verificar que no haya más referencias
                self.env.cr.execute("""
                    SELECT COUNT(*) FROM stock_quant WHERE lot_id = %s
                """, (lot_id,))
                quant_count = self.env.cr.fetchone()[0]
                
                if quant_count > 0:
                    # Aún hay quants, actualizarlos
                    self.env.cr.execute("""
                        UPDATE stock_quant SET lot_id = NULL WHERE lot_id = %s
                    """, (lot_id,))
                    self.env.cr.commit()
                    _logger.info('✅ Actualizados %s quants restantes antes de eliminar lote', quant_count)
                
                # Ahora intentar eliminar el lote con SQL
                self.env.cr.execute("""
                    DELETE FROM stock_lot WHERE id = %s
                """, (lot_id,))
                self.env.cr.commit()
                _logger.info('✅ Lote eliminado usando SQL directo: %s (ID: %s)', lot_name, lot_id)
            except Exception as sql_unlink_error:
                _logger.error('❌ Error crítico al eliminar lote con SQL: %s', str(sql_unlink_error))
                raise UserError(_(
                    'No se pudo eliminar el lote %s. '
                    'Puede que aún tenga referencias en otras tablas. '
                    'Por favor, verifique manualmente. Error: %s'
                ) % (lot_name, str(sql_unlink_error)))

    def _transfer_historical_moves(self, lot_mapping):
        """
        Transfiere los movimientos históricos relacionados con los lotes transferidos.
        
        Args:
            lot_mapping: Diccionario que mapea old_lot_id -> new_lot_id
        """
        self.ensure_one()
        
        if not lot_mapping:
            return
        
        old_lot_ids = list(lot_mapping.keys())
        new_lot_ids = list(lot_mapping.values())
        
        _logger.info('🔄 Iniciando transferencia de movimientos históricos para %s lotes', len(lot_mapping))
        
        # 1. Actualizar stock.move.line que referencian los lotes originales
        # Buscar todas las líneas de movimiento que referencian los lotes originales
        # IMPORTANTE: Solo actualizar movimientos históricos (completados o cancelados) para evitar
        # problemas con movimientos en curso
        move_lines = self.env['stock.move.line'].search([
            ('lot_id', 'in', old_lot_ids),
            ('state', 'in', ['done', 'cancel']),  # Solo movimientos históricos (completados o cancelados)
        ])
        
        updated_move_lines = 0
        skipped_move_lines = 0
        for move_line in move_lines:
            old_lot_id = move_line.lot_id.id
            if old_lot_id not in lot_mapping:
                continue
                
            new_lot_id = lot_mapping[old_lot_id]
            # Verificar que el nuevo lote existe
            new_lot = self.env['stock.lot'].browse(new_lot_id)
            if not new_lot.exists():
                _logger.warning('⚠️ El nuevo lote %s no existe, saltando move_line %s', new_lot_id, move_line.id)
                skipped_move_lines += 1
                continue
            
            # IMPORTANTE: Solo actualizar si el producto de la línea coincide con el producto origen o destino
            # y el movimiento está en estado 'done' o 'cancel' (histórico)
            if move_line.product_id.id == self.source_product_id.id:
                # Si el movimiento es del producto origen, actualizar el producto y el lote
                # pero solo si el movimiento está en estado 'done' o 'cancel'
                try:
                    move_line.write({
                        'lot_id': new_lot_id,
                        'product_id': self.destination_product_id.id,
                    })
                    updated_move_lines += 1
                    _logger.debug('✅ Actualizada move_line %s: old_lot %s -> new_lot %s, producto %s -> %s', 
                                 move_line.id, old_lot_id, new_lot_id,
                                 self.source_product_id.id, self.destination_product_id.id)
                except Exception as e:
                    _logger.warning('⚠️ No se pudo actualizar move_line %s: %s', move_line.id, str(e))
                    skipped_move_lines += 1
            elif move_line.product_id.id == self.destination_product_id.id:
                # Si ya es del producto destino, solo actualizar el lote
                try:
                    move_line.write({'lot_id': new_lot_id})
                    updated_move_lines += 1
                    _logger.debug('✅ Actualizada move_line %s: old_lot %s -> new_lot %s', 
                                 move_line.id, old_lot_id, new_lot_id)
                except Exception as e:
                    _logger.warning('⚠️ No se pudo actualizar move_line %s: %s', move_line.id, str(e))
                    skipped_move_lines += 1
            else:
                # El movimiento es de otro producto, no actualizar
                skipped_move_lines += 1
                _logger.debug('⏭️ Saltando move_line %s: producto diferente (%s)', 
                            move_line.id, move_line.product_id.id)
        
        _logger.info('✅ Actualizadas %s líneas de movimiento (stock.move.line), %s omitidas', 
                    updated_move_lines, skipped_move_lines)
        
        # 2. Actualizar stock.move que referencian el producto origen
        # Buscar movimientos completados o cancelados del producto origen
        # IMPORTANTE: Solo actualizar movimientos donde TODAS las líneas están relacionadas con lotes transferidos
        moves = self.env['stock.move'].search([
            ('product_id', '=', self.source_product_id.id),
            ('state', 'in', ['done', 'cancel']),
        ])
        
        # Filtrar movimientos que tienen líneas con los lotes que estamos transfiriendo
        moves_to_update = moves.filtered(
            lambda m: any(ml.lot_id and ml.lot_id.id in old_lot_ids for ml in m.move_line_ids)
        )
        
        updated_moves = 0
        skipped_moves = 0
        for move in moves_to_update:
            # Verificar si todas las líneas de movimiento de este move están relacionadas con lotes transferidos
            lines_with_lots = move.move_line_ids.filtered('lot_id')
            related_lines = lines_with_lots.filtered(
                lambda ml: ml.lot_id.id in old_lot_ids
            )
            
            # Solo actualizar si TODAS las líneas con lotes están relacionadas con lotes transferidos
            # y si todas las líneas ya fueron actualizadas en el paso anterior
            if lines_with_lots and len(related_lines) == len(lines_with_lots):
                # Verificar que todas las líneas relacionadas ya tienen el producto destino
                all_updated = all(
                    ml.product_id.id == self.destination_product_id.id 
                    for ml in related_lines
                )
                
                if all_updated:
                    try:
                        move.write({'product_id': self.destination_product_id.id})
                        updated_moves += 1
                        _logger.debug('✅ Actualizado move %s: producto %s -> %s', 
                                     move.id, self.source_product_id.id, self.destination_product_id.id)
                    except Exception as e:
                        _logger.warning('⚠️ No se pudo actualizar move %s: %s', move.id, str(e))
                        skipped_moves += 1
                else:
                    skipped_moves += 1
                    _logger.debug('⏭️ Saltando move %s: no todas las líneas están actualizadas', move.id)
            else:
                skipped_moves += 1
                _logger.debug('⏭️ Saltando move %s: no todas las líneas están relacionadas con lotes transferidos', move.id)
        
        _logger.info('✅ Actualizados %s movimientos (stock.move), %s omitidos', updated_moves, skipped_moves)
        
        # 3. Actualizar quants históricos si es necesario
        # Los quants se actualizan automáticamente cuando se validan los pickings,
        # pero podemos verificar si hay quants huérfanos que referencian los lotes originales
        quants = self.env['stock.quant'].search([
            ('lot_id', 'in', old_lot_ids),
            ('quantity', '!=', 0),
        ])
        
        if quants:
            _logger.warning('⚠️ Se encontraron %s quants que aún referencian los lotes originales. Esto es normal si hay stock residual.', len(quants))
        
        # 4. Actualizar referencias en módulos personalizados si existen
        # Actualizar supply_parent_product_id en stock.move si el módulo product_suppiles está instalado
        if hasattr(self.env['stock.move'], 'supply_parent_product_id'):
            moves_with_supply = self.env['stock.move'].search([
                ('supply_parent_product_id', '=', self.source_product_id.id),
                ('state', 'in', ['done', 'cancel']),
            ])
            
            if moves_with_supply:
                # Actualizar el campo computed recalculándolo
                # Como es un campo computed, necesitamos forzar su recálculo
                moves_with_supply._compute_supply_parent_product_id()
                _logger.info('✅ Recalculado supply_parent_product_id para %s movimientos', len(moves_with_supply))
        
        _logger.info('✅ Transferencia de movimientos históricos completada')

    def _transfer_by_quantity(self):
        """Transfiere una cantidad específica de un producto a otro"""
        self.ensure_one()

        if self.quantity <= 0:
            raise UserError(_('La cantidad a transferir debe ser mayor a cero.'))

        # Obtener el tipo de operación de ajuste interno
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('warehouse_id', '=', self.location_id.warehouse_id.id),
        ], limit=1)

        if not picking_type:
            picking_type = self.env['stock.picking.type'].search([
                ('code', '=', 'internal'),
            ], limit=1)

        if not picking_type:
            raise UserError(_('No se encontró un tipo de operación interno. Por favor, configure uno en Configuración > Inventario.'))

        # Verificar stock disponible
        available_qty = self.env['stock.quant']._get_available_quantity(
            self.source_product_id,
            self.location_id,
        )

        if available_qty < self.quantity:
            raise UserError(_('Stock insuficiente. Disponible: %s %s, Solicitado: %s %s') % (
                available_qty,
                self.source_product_id.uom_id.name,
                self.quantity,
                self.source_product_id.uom_id.name,
            ))

        # Obtener ubicación de inventario para ajustes
        inventory_location = self.env['stock.location'].search([
            ('usage', '=', 'inventory'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)

        if not inventory_location:
            # Si no hay ubicación de inventario, usar la ubicación de origen
            inventory_location = self.location_id

        # Crear el picking de transferencia (salida del producto origen)
        picking_vals = {
            'picking_type_id': picking_type.id,
            'location_id': self.location_id.id,
            'location_dest_id': inventory_location.id,
            'origin': _('Transferencia de Producto: %s -> %s') % (
                self.source_product_id.display_name,
                self.destination_product_id.display_name
            ),
            'note': self.note or '',
        }

        picking = self.env['stock.picking'].create(picking_vals)

        # Crear movimiento de salida (producto origen) (Odoo 19: stock.move usa description_picking, no name)
        move_out_vals = {
            'description_picking': _('Transferencia: %s -> %s') % (
                self.source_product_id.display_name,
                self.destination_product_id.display_name
            ),
            'product_id': self.source_product_id.id,
            'product_uom': self.source_product_id.uom_id.id,
            'product_uom_qty': self.quantity,
            'picking_id': picking.id,
            'location_id': self.location_id.id,
            'location_dest_id': picking_type.default_location_dest_id.id or self.location_id.id,
        }

        move_out = self.env['stock.move'].create(move_out_vals)

        # Crear picking de entrada (producto destino) desde inventario a ubicación
        picking_in_vals = {
            'picking_type_id': picking_type.id,
            'location_id': inventory_location.id,
            'location_dest_id': self.location_id.id,
            'origin': _('Transferencia de Producto: %s -> %s') % (
                self.source_product_id.display_name,
                self.destination_product_id.display_name
            ),
            'note': self.note or '',
        }

        picking_in = self.env['stock.picking'].create(picking_in_vals)

        # Crear movimiento de entrada (producto destino) (Odoo 19: stock.move usa description_picking, no name)
        move_in_vals = {
            'description_picking': _('Transferencia: %s -> %s') % (
                self.source_product_id.display_name,
                self.destination_product_id.display_name
            ),
            'product_id': self.destination_product_id.id,
            'product_uom': self.destination_product_id.uom_id.id,
            'product_uom_qty': self.quantity,
            'picking_id': picking_in.id,
            'location_id': inventory_location.id,
            'location_dest_id': self.location_id.id,
        }

        move_in = self.env['stock.move'].create(move_in_vals)

        # Confirmar y validar ambos pickings (Odoo 19: move_line_ids_without_package -> move_line_ids)
        picking.action_confirm()
        picking.action_assign()
        pick_lines = getattr(picking, 'move_line_ids_without_package', picking.move_line_ids)
        for move_line in pick_lines:
            if move_line.qty_done <= 0:
                move_line.qty_done = move_line.reserved_uom_qty
        picking.button_validate()

        picking_in.action_confirm()
        picking_in.action_assign()
        pick_in_lines = getattr(picking_in, 'move_line_ids_without_package', picking_in.move_line_ids)
        for move_line in pick_in_lines:
            move_line.qty_done = self.quantity
            # Si el producto destino tiene seguimiento, crear un lote nuevo
            if self.destination_product_id.tracking != 'none':
                # Crear un lote automático
                lot = self.env['stock.lot'].create({
                    'name': self.env['ir.sequence'].next_by_code('stock.lot.serial') or _('TRANS-%s') % fields.Datetime.now(),
                    'product_id': self.destination_product_id.id,
                    'company_id': self.env.company.id,
                })
                move_line.lot_id = lot.id
        picking_in.button_validate()

        return {
            'picking_name': _('%s y %s') % (picking.name, picking_in.name),
            'picking_id': picking.id,
        }

    def _convert_generic_to_specific(self):
        """
        Convierte un producto genérico recibido en un producto específico.
        Elimina completamente el serial e información del genérico y crea una unidad del específico.
        """
        self.ensure_one()
        
        # Validaciones específicas para conversión
        if not self.lot_ids or len(self.lot_ids) != 1:
            raise UserError(_('En modo conversión debe seleccionar exactamente un serial/lote del producto genérico.'))
        
        generic_lot = self.lot_ids[0]
        
        # Validar que el lote pertenece al producto origen
        if generic_lot.product_id.id != self.source_product_id.id:
            raise UserError(_('El serial seleccionado no pertenece al producto origen seleccionado.'))
        
        # Validar que hay stock disponible
        quant = self.env['stock.quant'].search([
            ('product_id', '=', self.source_product_id.id),
            ('location_id', '=', self.location_id.id),
            ('lot_id', '=', generic_lot.id),
            ('quantity', '>', 0),
        ], limit=1)
        
        if not quant:
            raise UserError(_('El serial %s no tiene stock disponible en la ubicación %s.') % (
                generic_lot.name, self.location_id.display_name
            ))
        
        quantity_to_convert = quant.quantity
        
        # Validar que el producto destino tiene seguimiento si el origen lo tiene
        if self.source_product_id.tracking != 'none' and self.destination_product_id.tracking == 'none':
            raise UserError(_('El producto destino debe tener seguimiento por seriales/lotes si el origen lo tiene.'))
        
        _logger.info('🔄 Iniciando conversión: Producto genérico %s (Serial: %s) → Producto específico %s',
                    self.source_product_id.name, generic_lot.name, self.destination_product_id.name)
        
        # PASO 1: Guardar información del lote genérico antes de eliminarlo
        # IMPORTANTE: Extraer IDs de objetos Many2one para evitar error "can't adapt type"
        principal_product = getattr(generic_lot, 'principal_product_id', False)
        principal_lot = getattr(generic_lot, 'principal_lot_id', False)
        related_partner = getattr(generic_lot, 'related_partner_id', False)
        
        generic_info = {
            'name': generic_lot.name,
            'purchase_tracking_ref': getattr(generic_lot, 'purchase_tracking_ref', False),
            'principal_product_id': principal_product.id if principal_product else False,
            'principal_lot_id': principal_lot.id if principal_lot else False,
            'inventory_plate': getattr(generic_lot, 'inventory_plate', False),
            'security_plate': getattr(generic_lot, 'security_plate', False),
            'billing_code': getattr(generic_lot, 'billing_code', False),
            'model_name': getattr(generic_lot, 'model_name', False),
            'related_partner_id': related_partner.id if related_partner else False,
            'is_principal': getattr(generic_lot, 'is_principal', False),
        }
        
        # Guardar relaciones de supply_line del genérico
        generic_supply_lines = []
        if hasattr(generic_lot, 'lot_supply_line_ids') and generic_lot.lot_supply_line_ids:
            for sl in generic_lot.lot_supply_line_ids:
                generic_supply_lines.append({
                    'item_type': sl.item_type,
                    'product_id': sl.product_id.id,
                    'quantity': sl.quantity,
                    'uom_id': sl.uom_id.id if sl.uom_id else False,
                    'related_lot_id': sl.related_lot_id.id if sl.related_lot_id else False,
                })
        
        # PASO 2: Guardar y eliminar relaciones donde el lote genérico está asociado (related_lot_id)
        # IMPORTANTE: Guardar TODAS las relaciones (sin importar el tipo: componente, periférico, complemento, etc.)
        # para recrearlas después con el nuevo lote
        relations_to_restore = []
        if 'stock.lot.supply.line' in self.env:
            supply_lines_as_related = self.env['stock.lot.supply.line'].search([
                ('related_lot_id', '=', generic_lot.id),
            ])
            if supply_lines_as_related:
                # Guardar información de TODAS las relaciones antes de eliminarlas
                for sl in supply_lines_as_related:
                    relations_to_restore.append({
                        'lot_id': sl.lot_id.id,  # Serial del producto principal
                        'item_type': sl.item_type,  # Tipo: componente, periférico, complemento, etc.
                        'product_id': sl.product_id.id,
                        'quantity': sl.quantity,
                        'uom_id': sl.uom_id.id if sl.uom_id else False,
                    })
                _logger.info('💾 Guardadas %s relaciones donde el lote genérico está asociado (cualquier tipo). Se restaurarán con el nuevo lote.', len(relations_to_restore))
                _logger.info('🗑️ Eliminando %s relaciones donde el lote genérico está asociado', len(supply_lines_as_related))
                supply_lines_as_related.with_context(allow_delete_supply_relations=True).unlink()
        
        # PASO 3: Eliminar relaciones donde el lote genérico es principal (lot_id)
        if 'stock.lot.supply.line' in self.env:
            supply_lines_as_principal = self.env['stock.lot.supply.line'].search([
                ('lot_id', '=', generic_lot.id),
            ])
            if supply_lines_as_principal:
                _logger.info('🗑️ Eliminando %s relaciones donde el lote genérico es principal', len(supply_lines_as_principal))
                supply_lines_as_principal.with_context(allow_delete_supply_relations=True).unlink()
        
        # PASO 4: Reducir stock del producto genérico a cero usando picking de salida
        # En lugar de eliminar quants directamente (requiere permisos), creamos un picking de salida
        # que mueva el stock a ubicación de inventario/scrap, reduciéndolo a cero
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('warehouse_id', '=', self.location_id.warehouse_id.id),
        ], limit=1)
        
        if not picking_type:
            picking_type = self.env['stock.picking.type'].search([
                ('code', '=', 'internal'),
            ], limit=1)
        
        if not picking_type:
            raise UserError(_('No se encontró un tipo de operación interno. Por favor, configure uno en Configuración > Inventario.'))
        
        # Obtener ubicación de inventario o scrap para reducir stock
        inventory_location = self.env['stock.location'].search([
            ('usage', '=', 'inventory'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        
        if not inventory_location:
            # Si no hay ubicación de inventario, buscar scrap
            inventory_location = self.env['stock.location'].search([
                ('usage', '=', 'inventory'),
            ], limit=1)
        
        if not inventory_location:
            # Como último recurso, usar la ubicación actual (no es ideal pero funciona)
            inventory_location = self.location_id
        
        # Crear picking de salida para reducir stock a cero
        picking_out_vals = {
            'picking_type_id': picking_type.id,
            'location_id': self.location_id.id,
            'location_dest_id': inventory_location.id,
            'origin': _('Conversión: Reducción de stock - %s (Serial: %s)') % (
                self.source_product_id.display_name,
                generic_info['name']
            ),
            'note': _('Reducción de stock para conversión a producto específico'),
        }
        
        picking_out = self.env['stock.picking'].create(picking_out_vals)
        
        # Crear movimiento de salida (Odoo 19: stock.move usa description_picking, no name)
        move_out_vals = {
            'description_picking': _('Reducción de stock: %s') % self.source_product_id.display_name,
            'product_id': self.source_product_id.id,
            'product_uom': self.source_product_id.uom_id.id,
            'product_uom_qty': quantity_to_convert,
            'picking_id': picking_out.id,
            'location_id': self.location_id.id,
            'location_dest_id': inventory_location.id,
        }
        
        move_out = self.env['stock.move'].create(move_out_vals)
        
        # Crear línea de movimiento con el lote genérico
        move_line_out_vals = {
            'move_id': move_out.id,
            'product_id': self.source_product_id.id,
            'product_uom_id': self.source_product_id.uom_id.id,
            'location_id': self.location_id.id,
            'location_dest_id': inventory_location.id,
            'lot_id': generic_lot.id,
            'qty_done': quantity_to_convert,
        }
        
        self.env['stock.move.line'].create(move_line_out_vals)
        
        # Validar el picking de salida para reducir el stock (Odoo 19: move_line_ids_without_package -> move_line_ids)
        picking_out.action_confirm()
        picking_out.action_assign()
        pick_out_lines = getattr(picking_out, 'move_line_ids_without_package', picking_out.move_line_ids)
        for move_line in pick_out_lines:
            if move_line.qty_done <= 0:
                move_line.qty_done = move_line.reserved_uom_qty
        picking_out.button_validate()
        
        _logger.info('✅ Stock del producto genérico reducido a cero mediante picking: %s', picking_out.name)
        
        # PASO 5: Crear nuevo lote para el producto específico
        # Verificar si ya existe un lote con el mismo nombre
        existing_lot = self.env['stock.lot'].search([
            ('product_id', '=', self.destination_product_id.id),
            ('name', '=', generic_info['name']),
        ], limit=1)
        
        if existing_lot:
            new_lot = existing_lot
            _logger.info('✅ Usando lote existente para producto específico: %s', new_lot.name)
        else:
            # Crear nuevo lote copiando información relevante
            lot_vals = {
                'name': generic_info['name'],
                'product_id': self.destination_product_id.id,
                'company_id': generic_lot.company_id.id,
            }
            
            # Copiar campos estándar
            if hasattr(generic_lot, 'ref') and generic_lot.ref:
                lot_vals['ref'] = generic_lot.ref
            if hasattr(generic_lot, 'note') and generic_lot.note:
                lot_vals['note'] = generic_lot.note
            
            # Copiar campos personalizados
            if generic_info['inventory_plate']:
                lot_vals['inventory_plate'] = generic_info['inventory_plate']
            if generic_info['security_plate']:
                lot_vals['security_plate'] = generic_info['security_plate']
            if generic_info['billing_code']:
                lot_vals['billing_code'] = generic_info['billing_code']
            if generic_info['model_name']:
                lot_vals['model_name'] = generic_info['model_name']
            if generic_info['purchase_tracking_ref']:
                lot_vals['purchase_tracking_ref'] = generic_info['purchase_tracking_ref']
            if generic_info['is_principal']:
                lot_vals['is_principal'] = generic_info['is_principal']
            if generic_info['related_partner_id']:
                lot_vals['related_partner_id'] = generic_info['related_partner_id']
            
            # Mantener relación con producto principal si existe
            if generic_info['principal_product_id']:
                lot_vals['principal_product_id'] = generic_info['principal_product_id']
            # Nota: principal_lot_id se actualizará después si es necesario
            
            new_lot = self.env['stock.lot'].with_context(
                skip_auto_link=True,
                no_auto_link=True,
                skip_supply_line_creation=True
            ).create(lot_vals)
            _logger.info('✅ Creado nuevo lote para producto específico: %s (ID: %s)', new_lot.name, new_lot.id)
            
            # Limpiar relaciones automáticas si se crearon
            if 'stock.lot.supply.line' in self.env:
                self.env.cr.execute("""
                    DELETE FROM stock_lot_supply_line 
                    WHERE lot_id = %s
                """, (new_lot.id,))
                self.env.cr.commit()
        
        # PASO 7: Restaurar relaciones de supply_line para el nuevo lote
        if generic_supply_lines and 'stock.lot.supply.line' in self.env:
            for sl_data in generic_supply_lines:
                # Crear línea usando SQL directo para evitar auto-asignación
                self.env.cr.execute("""
                    INSERT INTO stock_lot_supply_line 
                    (lot_id, item_type, product_id, quantity, uom_id, related_lot_id, create_uid, create_date, write_uid, write_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), %s, NOW())
                    RETURNING id
                """, (
                    new_lot.id,
                    sl_data['item_type'],
                    sl_data['product_id'],
                    sl_data['quantity'],
                    sl_data['uom_id'] if sl_data['uom_id'] else None,
                    sl_data['related_lot_id'] if sl_data['related_lot_id'] else None,
                    self.env.user.id,
                    self.env.user.id,
                ))
                self.env.cr.commit()
            _logger.info('✅ Restauradas %s relaciones de supply_line para el nuevo lote', len(generic_supply_lines))
        
        # PASO 7b: Restaurar asociaciones donde el genérico era COMPONENTE de otro producto (evitar doble trabajo al técnico)
        if relations_to_restore and 'stock.lot.supply.line' in self.env:
            for rel in relations_to_restore:
                if not isinstance(rel, dict):
                    _logger.warning('Saltando relación no-dict en relations_to_restore: %s', type(rel))
                    continue
                uom_id = _safe_get(rel, 'uom_id')
                self.env.cr.execute("""
                    INSERT INTO stock_lot_supply_line 
                    (lot_id, item_type, product_id, quantity, uom_id, related_lot_id, create_uid, create_date, write_uid, write_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), %s, NOW())
                """, (
                    rel['lot_id'],
                    rel['item_type'],
                    rel['product_id'],
                    rel['quantity'],
                    uom_id if uom_id else None,
                    new_lot.id,
                    self.env.user.id,
                    self.env.user.id,
                ))
            self.env.cr.commit()
            _logger.info('✅ Restauradas %s asociaciones donde el serial era componente (sigue vinculado al mismo principal)', len(relations_to_restore))
        
        # PASO 8: Crear el quant directamente en la ubicación destino
        # En lugar de usar un picking que requiera reserva, creamos el stock directamente
        # Esto evita el error "no tiene stock disponible en la ubicación"
        
        _logger.info('📦 Creando quant directamente en ubicación %s para producto %s (lote: %s)',
                    self.location_id.display_name, self.destination_product_id.display_name, new_lot.name)
        
        # Usar _update_available_quantity para crear el quant directamente
        # Este método maneja automáticamente la creación/actualización del quant
        try:
            self.env['stock.quant']._update_available_quantity(
                self.destination_product_id,
                self.location_id,
                quantity_to_convert,
                lot_id=new_lot,
                in_date=fields.Datetime.now()
            )
            _logger.info('✅ Quant creado directamente: %s unidades de %s en %s',
                        quantity_to_convert, self.destination_product_id.display_name, self.location_id.display_name)
        except Exception as quant_error:
            _logger.error('❌ Error al crear quant directamente: %s. Intentando método alternativo...', str(quant_error))
            # Método alternativo: crear el quant manualmente
            quant_vals = {
                'product_id': self.destination_product_id.id,
                'location_id': self.location_id.id,
                'lot_id': new_lot.id,
                'quantity': quantity_to_convert,
                'in_date': fields.Datetime.now(),
            }
            # Buscar si ya existe un quant para este producto/lote/ubicación
            existing_quant = self.env['stock.quant'].search([
                ('product_id', '=', self.destination_product_id.id),
                ('location_id', '=', self.location_id.id),
                ('lot_id', '=', new_lot.id),
            ], limit=1)
            
            if existing_quant:
                # Actualizar cantidad existente
                existing_quant.quantity += quantity_to_convert
                _logger.info('✅ Quant existente actualizado: %s unidades agregadas', quantity_to_convert)
            else:
                # Crear nuevo quant
                self.env['stock.quant'].create(quant_vals)
                _logger.info('✅ Quant creado manualmente: %s unidades', quantity_to_convert)
        
        # Crear un picking de tipo "inventory" para registrar el movimiento en el historial
        # Esto es opcional pero ayuda a mantener el historial de movimientos
        picking = None
        try:
            # Buscar tipo de operación de inventario
            inventory_picking_type = self.env['stock.picking.type'].search([
                ('code', '=', 'inventory'),
                ('warehouse_id', '=', self.location_id.warehouse_id.id if self.location_id.warehouse_id else False),
            ], limit=1)
            
            if not inventory_picking_type:
                # Si no hay tipo de inventario, buscar cualquier tipo interno
                inventory_picking_type = self.env['stock.picking.type'].search([
                    ('code', '=', 'internal'),
                ], limit=1)
            
            if inventory_picking_type:
                picking_vals = {
                    'picking_type_id': inventory_picking_type.id,
                    'location_id': inventory_picking_type.default_location_src_id.id or self.location_id.id,
                    'location_dest_id': self.location_id.id,
                    'origin': _('Conversión: %s (Serial: %s) → %s') % (
                        self.source_product_id.display_name,
                        generic_info['name'],
                        self.destination_product_id.display_name
                    ),
                    'note': self.note or _('Conversión de producto genérico a específico'),
                    'state': 'done',  # Marcar como hecho directamente
                }
                
                picking = self.env['stock.picking'].create(picking_vals)
                
                # Crear movimiento ya completado (Odoo 19: stock.move usa description_picking, no name)
                move_vals = {
                    'description_picking': _('Conversión: %s → %s') % (
                        self.source_product_id.display_name,
                        self.destination_product_id.display_name
                    ),
                    'product_id': self.destination_product_id.id,
                    'product_uom': self.destination_product_id.uom_id.id,
                    'product_uom_qty': quantity_to_convert,
                    'picking_id': picking.id,
                    'location_id': picking.location_id.id,
                    'location_dest_id': self.location_id.id,
                    'state': 'done',
                }
                
                move = self.env['stock.move'].create(move_vals)
                
                # Crear línea de movimiento con el nuevo lote
                move_line_vals = {
                    'move_id': move.id,
                    'product_id': self.destination_product_id.id,
                    'product_uom_id': self.destination_product_id.uom_id.id,
                    'location_id': picking.location_id.id,
                    'location_dest_id': self.location_id.id,
                    'lot_id': new_lot.id,
                    'qty_done': quantity_to_convert,
                    'state': 'done',
                }
                
                self.env['stock.move.line'].create(move_line_vals)
                
                _logger.info('✅ Picking de historial creado: %s', picking.name)
        except Exception as picking_error:
            _logger.warning('⚠️ No se pudo crear picking de historial (no crítico): %s', str(picking_error))
            # No es crítico si falla, el quant ya está creado
        
        # PASO 9: Verificar que el quant se creó correctamente
        created_quant = self.env['stock.quant'].search([
            ('product_id', '=', self.destination_product_id.id),
            ('location_id', '=', self.location_id.id),
            ('lot_id', '=', new_lot.id),
        ])
        
        if created_quant and created_quant.quantity >= quantity_to_convert:
            _logger.info('✅ Verificación: Quant creado correctamente con %s unidades', created_quant.quantity)
        else:
            _logger.warning('⚠️ Advertencia: El quant puede no haberse creado correctamente')
        
        # PASO 10: Recrear relaciones donde el nuevo lote está asociado a productos principales
        # Esto mantiene TODAS las relaciones (sin importar el tipo) con productos principales 
        # cuando el serial convertido estaba asociado
        if relations_to_restore and 'stock.lot.supply.line' in self.env:
            _logger.info('🔗 Recreando %s relaciones donde el nuevo lote está asociado a productos principales (cualquier tipo)', len(relations_to_restore))
            
            for rel_data in relations_to_restore:
                if not isinstance(rel_data, dict):
                    _logger.warning('Saltando rel_data no-dict: %s', type(rel_data))
                    continue
                # Verificar que el lote principal aún existe
                principal_lot = self.env['stock.lot'].browse(rel_data['lot_id'])
                if not principal_lot.exists():
                    _logger.warning('⚠️ El lote principal (ID: %s) ya no existe. Saltando relación.', rel_data['lot_id'])
                    continue
                
                # Verificar que el nuevo lote tiene stock en la ubicación del lote principal
                # Esto es importante para que la validación de supply_line no falle
                principal_location = principal_lot.location_id if hasattr(principal_lot, 'location_id') and principal_lot.location_id else None
                if principal_location:
                    # Buscar quant del nuevo lote en la ubicación del principal
                    quant_check = self.env['stock.quant'].search_count([
                        ('lot_id', '=', new_lot.id),
                        ('location_id', '=', principal_location.id),
                        ('quantity', '>', 0),
                    ])
                    
                    if quant_check == 0:
                        # Si no está en la misma ubicación, verificar si podemos moverlo o crear la relación de todas formas
                        # La relación puede existir aunque el componente esté en otra ubicación temporalmente
                        _logger.info('ℹ️ El nuevo lote no está en la ubicación del principal (%s), pero se creará la relación de todas formas', principal_location.display_name)
                
                # Crear la relación usando SQL directo para evitar validaciones que puedan fallar
                # IMPORTANTE: Usar el producto destino (específico) en lugar del producto origen (genérico)
                try:
                    self.env.cr.execute("""
                        INSERT INTO stock_lot_supply_line 
                        (lot_id, item_type, product_id, quantity, uom_id, related_lot_id, create_uid, create_date, write_uid, write_date)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), %s, NOW())
                        RETURNING id
                    """, (
                        rel_data['lot_id'],  # lot_id del producto principal
                        rel_data['item_type'],
                        self.destination_product_id.id,  # product_id = producto destino (específico), NO el genérico
                        rel_data['quantity'],
                        rel_data['uom_id'] if rel_data['uom_id'] else None,
                        new_lot.id,  # related_lot_id = nuevo lote creado
                        self.env.user.id,
                        self.env.user.id,
                    ))
                    restored_id = self.env.cr.fetchone()[0]
                    self.env.cr.commit()
                    _logger.info('✅ Relación restaurada: Principal (ID: %s, Tipo: %s) → Nuevo serial asociado (ID: %s, Serial: %s)', 
                                rel_data['lot_id'], rel_data['item_type'], new_lot.id, new_lot.name)
                except Exception as rel_error:
                    _logger.error('❌ Error al recrear relación con principal (ID: %s): %s', rel_data['lot_id'], str(rel_error))
                    # Continuar con las demás relaciones aunque una falle
                    continue
        
        # PASO 11: Eliminar el lote genérico completamente usando el método auxiliar
        # Nota: Ya eliminamos las relaciones de supply_line en PASOS 2 y 3
        # El método _delete_lot_safely se encargará de limpiar quants y eliminar el lote
        generic_lot_id = generic_lot.id
        self._delete_lot_safely(generic_lot)
        
        _logger.info('✅ Conversión completada: Producto genérico eliminado, producto específico creado en ubicación %s',
                    self.location_id.display_name)
        
        # Preparar información de retorno
        picking_name = picking_out.name
        if picking:
            picking_name = _('%s y %s') % (picking_out.name, picking.name)
        
        return {
            'picking_name': picking_name,
            'picking_id': picking.id if picking else False,
            'picking_out_id': picking_out.id,
            'new_lot_id': new_lot.id,
            'new_lot_name': new_lot.name,
        }

