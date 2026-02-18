# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)


class MaintenanceComponentChange(models.Model):
    """Registro de cambios de componentes durante mantenimientos."""
    _name = 'maintenance.component.change'
    _description = 'Cambio de Componente en Mantenimiento'
    _order = 'change_date desc, id desc'
    
    maintenance_id = fields.Many2one(
        'stock.lot.maintenance',
        string='Mantenimiento',
        required=True,
        ondelete='cascade',
        index=True,
    )
    
    lot_id = fields.Many2one(
        'stock.lot',
        related='maintenance_id.lot_id',
        string='Equipo',
        store=True,
        readonly=True,
    )
    
    change_date = fields.Datetime(
        string='Fecha del Cambio',
        default=fields.Datetime.now,
        required=True,
    )
    
    # Campo computed para obtener los productos asociados al equipo
    available_component_product_ids = fields.Many2many(
        'product.product',
        string='Componentes Disponibles',
        compute='_compute_available_component_products',
        help='Componentes que están asociados a este equipo'
    )
    
    product_id = fields.Many2one(
        'product.product',
        string='Tipo de Componente',
        required=True,
        domain="[('id', 'in', available_component_product_ids), ('classification', 'in', ('component', 'peripheral', 'complement'))]",
        help='Tipo de componente cambiado. Solo se muestran los componentes asociados a este equipo.',
    )
    
    @api.depends('lot_id', 'lot_id.lot_supply_line_ids', 'lot_id.lot_supply_line_ids.product_id')
    def _compute_available_component_products(self):
        """Calcular los productos de componentes disponibles para este equipo."""
        for record in self:
            if record.lot_id and record.lot_id.lot_supply_line_ids:
                # Obtener todos los productos únicos de las líneas de suministro
                products = record.lot_id.lot_supply_line_ids.mapped('product_id').filtered(lambda p: p)
                record.available_component_product_ids = products.ids if products else []
            else:
                record.available_component_product_ids = []
    
    @api.onchange('product_id', 'lot_id')
    def _onchange_product_id(self):
        """Limpiar los campos de componentes cuando cambia el tipo de componente y actualizar dominios."""
        result = {}
        
        # Limpiar los valores seleccionados
        self.old_component_lot_id = False
        self.new_component_lot_id = False
        
        if not self.product_id:
            # Si no hay producto, restringir a ningún lote
            result['domain'] = {
                'old_component_lot_id': [('id', '=', False)],
                'new_component_lot_id': [('id', '=', False)],
            }
            return result
        
        # Forzar actualización de los campos computed
        self._compute_old_component_lot_ids()
        self._compute_new_component_lot_ids()
        
        # Obtener la categoría del producto para filtrar
        product_category_id = False
        if self.product_id and self.product_id.categ_id:
            product_category_id = self.product_id.categ_id.id
        
        # Obtener la ubicación
        location_id = False
        if self.lot_id:
            if hasattr(self.lot_id, 'customer_location_id') and self.lot_id.customer_location_id:
                location_id = self.lot_id.customer_location_id.id
            elif self.lot_id.current_location_id:
                location_id = self.lot_id.current_location_id.id
        
        # Construir dominios
        domain_old = [('id', '=', False)]
        domain_new = [('id', '=', False)]
        
        # Dominio para componente retirado (producto específico)
        if self.product_id:
            domain_old = [
                ('product_id', '=', self.product_id.id),
                ('id', 'in', self.old_component_lot_ids.ids if self.old_component_lot_ids else []),
            ]
        
        # Dominio para componente instalado (misma categoría + ubicación)
        # Filtrar directamente por categoría del producto en el dominio
        if product_category_id:
            domain_new = [
                ('product_id.categ_id', '=', product_category_id),
            ]
            
            # Si hay ubicación, también filtrar por ubicación (a través del quant)
            if location_id:
                # Buscar productos de la misma categoría para el filtro
                Product = self.env['product.product']
                products_with_same_category = Product.search([
                    ('categ_id', '=', product_category_id),
                ])
                
                if products_with_same_category:
                    product_ids = products_with_same_category.ids
                    # Obtener los lotes que tienen stock en esa ubicación
                    Quant = self.env['stock.quant']
                    Location = self.env['stock.location']
                    location_ids = [location_id]
                    try:
                        child_locations = Location.search([('id', 'child_of', location_id)])
                        location_ids = child_locations.ids
                    except Exception:
                        pass
                    
                    quants = Quant.sudo().search([
                        ('product_id', 'in', product_ids),
                        ('location_id', 'in', location_ids),
                        ('lot_id', '!=', False),
                        ('quantity', '>', 0),
                    ])
                    
                    lot_ids = list(set(quants.mapped('lot_id').ids))
                    if lot_ids:
                        # Dominio restrictivo: solo los lotes específicos que tienen stock en la ubicación
                        domain_new = [('id', 'in', lot_ids)]
                    else:
                        domain_new = [('id', '=', False)]
        
        result['domain'] = {
            'old_component_lot_id': domain_old,
            'new_component_lot_id': domain_new,
        }
        
        return result
    
    # Campos computed para filtrar los lotes disponibles
    old_component_lot_ids = fields.Many2many(
        'stock.lot',
        string='Componentes Retirados Disponibles',
        compute='_compute_old_component_lot_ids',
        help='Lotes de componentes actualmente asociados al equipo del tipo seleccionado'
    )
    
    new_component_lot_ids = fields.Many2many(
        'stock.lot',
        string='Componentes Instalados Disponibles',
        compute='_compute_new_component_lot_ids',
        help='Lotes de componentes disponibles en la ubicación del cliente'
    )
    
    old_component_lot_id = fields.Many2one(
        'stock.lot',
        string='Componente Retirado',
        domain="[('id', 'in', old_component_lot_ids)]",
        help='Número de serie del componente que se retiró. Solo muestra componentes actualmente asociados al equipo.',
    )
    
    new_component_lot_id = fields.Many2one(
        'stock.lot',
        string='Componente Instalado',
        domain="[('id', 'in', new_component_lot_ids)]",
        help='Número de serie del componente que se instaló. Solo muestra componentes disponibles en la ubicación del cliente de la misma categoría.',
    )
    
    @api.depends('lot_id', 'lot_id.lot_supply_line_ids', 'lot_id.lot_supply_line_ids.related_lot_id', 'product_id')
    def _compute_old_component_lot_ids(self):
        """Calcular los lotes de componentes actualmente asociados al equipo del producto específico seleccionado.
        
        Muestra SOLO los componentes del producto específico que está seleccionado en "Tipo de Componente".
        Por ejemplo, si selecciona RAM 16GB, solo mostrará las RAM 16GB asociadas al equipo.
        """
        for record in self:
            if record.lot_id and record.product_id and record.lot_id.lot_supply_line_ids:
                # Buscar las líneas de suministro que coincidan EXACTAMENTE con el producto seleccionado
                supply_lines = record.lot_id.lot_supply_line_ids.filtered(
                    lambda l: l.product_id.id == record.product_id.id and l.related_lot_id
                )
                
                # Obtener los lotes asociados (solo del producto específico)
                lots = supply_lines.mapped('related_lot_id').filtered(lambda l: l)
                record.old_component_lot_ids = lots.ids if lots else []
            else:
                record.old_component_lot_ids = []
    
    @api.depends('lot_id', 'lot_id.current_location_id', 'lot_id.customer_location_id', 'maintenance_id', 'maintenance_id.customer_id', 'product_id', 'product_id.categ_id', 'old_component_lot_id')
    def _compute_new_component_lot_ids(self):
        """Calcular los lotes de componentes disponibles en la ubicación del cliente.
        
        Muestra todos los productos de la misma clasificación (classification) que el producto seleccionado,
        no solo el mismo producto específico. Ejemplo: Si selecciona RAM 16GB, mostrará todas las RAMs
        disponibles (8GB, 16GB, 32GB, etc.) en la ubicación del cliente.
        """
        for record in self:
            if not record.product_id:
                record.new_component_lot_ids = []
                continue
            
            # Obtener la categoría del producto seleccionado para agrupar productos similares
            # Ejemplo: todas las RAMs están en la misma categoría
            product_category_id = False
            if record.product_id and record.product_id.categ_id:
                product_category_id = record.product_id.categ_id.id
            
            # Obtener la ubicación del cliente desde el equipo principal
            location_id = False
            if record.lot_id:
                # Prioridad 1: Ubicación del cliente desde el equipo
                if hasattr(record.lot_id, 'customer_location_id') and record.lot_id.customer_location_id:
                    location_id = record.lot_id.customer_location_id.id
                # Prioridad 2: Ubicación actual del equipo
                elif record.lot_id.current_location_id:
                    location_id = record.lot_id.current_location_id.id
            
            if not location_id:
                record.new_component_lot_ids = []
                continue
            
            # Buscar todos los productos de la misma categoría (para agrupar productos similares)
            Product = self.env['product.product']
            try:
                if not product_category_id:
                    record.new_component_lot_ids = []
                    continue
                
                # Buscar productos de la misma categoría
                # Esto agrupa productos similares (ej: todas las RAMs están en la misma categoría)
                products_with_same_category = Product.search([
                    ('categ_id', '=', product_category_id),
                ])
                
                if not products_with_same_category:
                    record.new_component_lot_ids = []
                    continue
                
                product_ids = products_with_same_category.ids
                
                # Obtener todas las ubicaciones hijas para buscar en toda la estructura
                Location = self.env['stock.location']
                location_ids = [location_id]
                try:
                    child_locations = Location.search([('id', 'child_of', location_id)])
                    location_ids = child_locations.ids
                except Exception:
                    pass
                
                # Buscar quants disponibles de TODOS los productos de la misma categoría en esa ubicación
                Quant = self.env['stock.quant']
                all_quants = Quant.sudo().search([
                    ('product_id', 'in', product_ids),
                    ('location_id', 'in', location_ids),
                    ('lot_id', '!=', False),
                    ('quantity', '>', 0),
                ])
                
                # Filtrar solo los quants accesibles
                accessible_quants = self.env['stock.quant']
                for quant in all_quants:
                    try:
                        quant_check = self.env['stock.quant'].browse(quant.id)
                        if quant_check.exists():
                            accessible_quants |= quant_check
                    except Exception:
                        continue
                
                # Obtener los lotes únicos
                all_lots = accessible_quants.mapped('lot_id').filtered(lambda l: l)
                
                # Filtrar lotes que sean de productos de la misma categoría
                filtered_lots = self.env['stock.lot']
                for lot in all_lots:
                    try:
                        if not lot.product_id or not lot.product_id.categ_id:
                            continue
                        
                        # Solo incluir si la categoría coincide
                        if lot.product_id.categ_id.id == product_category_id:
                            filtered_lots |= lot
                    except Exception:
                        continue
                
                # Excluir el componente que se está retirando (si existe)
                if record.old_component_lot_id:
                    filtered_lots = filtered_lots.filtered(lambda l: l.id != record.old_component_lot_id.id)
                
                record.new_component_lot_ids = filtered_lots.ids if filtered_lots else []
            except Exception as e:
                _logger.warning('Error al calcular componentes instalados disponibles: %s', str(e))
                record.new_component_lot_ids = []
    
    reason = fields.Text(
        string='Motivo del Cambio',
        required=True,
        help='Razón por la cual se cambió el componente',
    )
    
    technician_id = fields.Many2one(
        'res.users',
        related='maintenance_id.technician_id',
        string='Técnico',
        store=True,
        readonly=True,
    )
    
    ticket_id = fields.Many2one(
        'helpdesk.ticket',
        string='Ticket',
        readonly=True,
        help='Ticket creado automáticamente para este cambio de componente'
    )
    
    @api.model
    def create(self, vals):
        """Crear registro de cambio y actualizar elementos asociados."""
        change = super().create(vals)
        change._update_supply_lines()
        # Crear ticket automático para cambio de componentes
        change._create_automatic_ticket()
        return change
    
    def write(self, vals):
        """Actualizar elementos asociados si cambia el componente."""
        result = super().write(vals)
        if 'new_component_lot_id' in vals or 'old_component_lot_id' in vals:
            for record in self:
                record._update_supply_lines()
                # Si el cambio está completo (hay componente instalado), cerrar el ticket
                if record.ticket_id and record.new_component_lot_id:
                    record._close_ticket_when_complete()
        return result
    
    def _update_supply_lines(self):
        """Actualizar automáticamente lot_supply_line_ids en el inventario."""
        self.ensure_one()
        if not self.lot_id or not self.product_id:
            return
        
        # Buscar la línea de suministro correspondiente al producto y lote principal
        SupplyLine = self.env['stock.lot.supply.line']
        supply_line = SupplyLine.search([
            ('lot_id', '=', self.lot_id.id),
            ('product_id', '=', self.product_id.id),
        ], limit=1)
        
        # Si hay un componente nuevo instalado, actualizar o crear la línea
        if self.new_component_lot_id:
            if supply_line:
                # Actualizar la línea existente con el nuevo componente
                supply_line.write({
                    'related_lot_id': self.new_component_lot_id.id,
                })
            else:
                # Crear nueva línea si no existe
                # Determinar el tipo de item según la clasificación del producto
                classification = self.product_id.classification if hasattr(self.product_id, 'classification') else 'component'
                item_type_map = {
                    'component': 'component',
                    'peripheral': 'peripheral',
                    'complement': 'complement',
                }
                item_type = item_type_map.get(classification, 'component')
                
                SupplyLine.create({
                    'lot_id': self.lot_id.id,
                    'product_id': self.product_id.id,
                    'item_type': item_type,
                    'related_lot_id': self.new_component_lot_id.id,
                    'quantity': 1.0,
                    'uom_id': self.product_id.uom_id.id if self.product_id.uom_id else False,
                })
        
        # Si se retiró un componente, eliminar o desasociar la línea correspondiente
        if self.old_component_lot_id:
            old_supply_line = SupplyLine.search([
                ('lot_id', '=', self.lot_id.id),
                ('product_id', '=', self.product_id.id),
                ('related_lot_id', '=', self.old_component_lot_id.id),
            ], limit=1)
            
            if old_supply_line:
                # Si hay un nuevo componente, actualizar; si no, eliminar la línea
                if not self.new_component_lot_id:
                    old_supply_line.unlink()
                elif old_supply_line.related_lot_id.id != self.new_component_lot_id.id:
                    old_supply_line.write({
                        'related_lot_id': self.new_component_lot_id.id,
                    })
    
    def _create_automatic_ticket(self):
        """Crear ticket automático para cambio de componentes."""
        self.ensure_one()
        
        # Si ya tiene ticket, no crear otro
        if self.ticket_id:
            return self.ticket_id
        
        # Obtener información del mantenimiento y equipo
        maintenance = self.maintenance_id
        if not maintenance:
            return False
        
        lot = self.lot_id
        customer = maintenance.customer_id if maintenance.customer_id else (lot.customer_id if hasattr(lot, 'customer_id') and lot.customer_id else False)
        
        if not customer:
            # No crear ticket si no hay cliente
            _logger.warning("No se puede crear ticket para cambio de componente %s: no hay cliente asociado", self.id)
            return False
        
        # Determinar si hay ticket padre (de la orden de mantenimiento)
        parent_ticket = None
        if maintenance.maintenance_order_id and maintenance.maintenance_order_id.ticket_id:
            parent_ticket = maintenance.maintenance_order_id.ticket_id
        
        # Preparar descripción del ticket con formato HTML organizado
        plate = lot.inventory_plate if (lot and hasattr(lot, 'inventory_plate') and lot.inventory_plate) else _('Sin placa')
        serial = lot.name if lot else _('N/A')
        product_name = self.product_id.display_name if self.product_id else _('N/A')
        old_component = self.old_component_lot_id.name if self.old_component_lot_id else _('N/A')
        new_component = self.new_component_lot_id.name if self.new_component_lot_id else _('Pendiente')
        maintenance_name = maintenance.name if maintenance and maintenance.name else _('N/A')
        
        ticket_description = f'''
<div style="padding: 15px; background-color: #fff3cd; border-left: 4px solid #ffc107; border-radius: 4px; margin-bottom: 15px;">
<h3 style="color: #856404; margin-top: 0;">🔧 Cambio de Componente</h3>
<div style="line-height: 1.8;">
<p style="margin: 5px 0;"><strong>Equipo:</strong> {serial}</p>
<p style="margin: 5px 0;"><strong>Placa de Inventario:</strong> {plate}</p>
<p style="margin: 5px 0;"><strong>Tipo de Componente:</strong> {product_name}</p>
</div>
</div>

<div style="padding: 15px; background-color: #f8f9fa; border-left: 4px solid #6c757d; border-radius: 4px; margin-bottom: 15px;">
<h4 style="color: #495057; margin-top: 0; margin-bottom: 10px;">📤 Componente Retirado</h4>
<p style="margin: 5px 0; font-size: 16px;"><strong>{old_component}</strong></p>
</div>

<div style="padding: 15px; background-color: #d1ecf1; border-left: 4px solid #0c5460; border-radius: 4px; margin-bottom: 15px;">
<h4 style="color: #0c5460; margin-top: 0; margin-bottom: 10px;">📥 Componente Instalado</h4>
<p style="margin: 5px 0; font-size: 16px;"><strong>{new_component}</strong></p>
</div>
'''
        
        if self.reason:
            ticket_description += f'''
<div style="margin-top: 15px; padding: 15px; background-color: #e7f3ff; border-left: 4px solid #0066cc; border-radius: 4px;">
<h4 style="color: #0066cc; margin-top: 0; margin-bottom: 10px;">📝 Motivo del Cambio</h4>
<p style="margin: 0; white-space: pre-wrap;">{self.reason}</p>
</div>
'''
        
        if maintenance_name:
            ticket_description += f'''
<div style="margin-top: 15px; padding: 10px; background-color: #f8f9fa; border-radius: 4px;">
<p style="margin: 5px 0;"><strong>Mantenimiento:</strong> {maintenance_name}</p>
</div>
'''
        
        # Preparar nombre del ticket con tipo de componente y placa de inventario
        ticket_name_parts = [_('Cambio de Componente')]
        
        # Agregar tipo de componente si existe
        if self.product_id:
            ticket_name_parts.append(self.product_id.display_name)
        
        # Agregar número de serie del equipo
        if lot:
            ticket_name_parts.append(lot.name)
        else:
            ticket_name_parts.append('Equipo')
        
        # Agregar placa de inventario si existe
        if lot and hasattr(lot, 'inventory_plate') and lot.inventory_plate:
            ticket_name_parts.append('(%s)' % lot.inventory_plate)
        
        ticket_name = ' - '.join(ticket_name_parts)
        
        # Crear el ticket
        ticket_vals = {
            'name': ticket_name,
            'partner_id': customer.id,
            'description': ticket_description,
            'lot_id': lot.id if lot else False,
            'maintenance_id': maintenance.id,
            'maintenance_category': 'maintenance',
            'user_id': self.technician_id.id if self.technician_id else self.env.user.id,
        }
        
        ticket = self.env['helpdesk.ticket'].create(ticket_vals)
        
        # Si hay ticket padre, vincularlos mediante mensajes
        if parent_ticket:
            parent_ticket.message_post(
                body=_('Se creó un ticket hijo para cambio de componente: <a href="#" data-oe-model="helpdesk.ticket" data-oe-id="%s">%s</a>') % (
                    ticket.id, ticket.name
                ),
                subject=_('Ticket hijo creado')
            )
            ticket.message_post(
                body=_('Este ticket está relacionado con el ticket padre: <a href="#" data-oe-model="helpdesk.ticket" data-oe-id="%s">%s</a>') % (
                    parent_ticket.id, parent_ticket.name
                ),
                subject=_('Relación con ticket padre')
            )
        
        # Vincular el ticket al cambio de componente
        self.ticket_id = ticket.id
        
        # Notificar en el chatter del mantenimiento
        if maintenance:
            maintenance.message_post(
                body=_('Se creó un ticket automático para el cambio de componente: <a href="#" data-oe-model="helpdesk.ticket" data-oe-id="%s">%s</a>') % (
                    ticket.id, ticket.name
                ),
                subject=_('Ticket Creado')
            )
        
        # NO cerrar el ticket automáticamente al crear - se cerrará cuando se guarde el cambio completo
        
        return ticket
    
    def _close_ticket_when_complete(self):
        """Cerrar el ticket cuando el cambio de componente está completo."""
        self.ensure_one()
        
        if not self.ticket_id:
            return
        
        # Verificar que el cambio está completo (tiene componente instalado)
        if not self.new_component_lot_id:
            return
        
        # Verificar que el ticket no esté ya cerrado
        try:
            if hasattr(self.ticket_id, 'stage_id') and self.ticket_id.stage_id:
                # Verificar si ya está en un stage cerrado
                stage_name = self.ticket_id.stage_id.name.lower()
                if 'cerrado' in stage_name or 'resuelto' in stage_name or 'done' in stage_name:
                    return
        except Exception:
            pass
        
        # Cerrar el ticket automáticamente
        try:
            # Buscar stage "Cerrado" o "Resuelto"
            closed_stages = self.env['helpdesk.ticket.stage'].search([
                '|',
                ('name', 'ilike', 'cerrado'),
                ('name', 'ilike', 'resuelto'),
            ], limit=1)
            if closed_stages:
                self.ticket_id.stage_id = closed_stages[0].id
                
                # Notificar en el chatter del ticket
                self.ticket_id.message_post(
                    body=_('✅ Ticket cerrado automáticamente: El cambio de componente ha sido completado y guardado.'),
                    subject=_('Cambio Completado')
                )
            else:
                # Si no hay stage cerrado, al menos actualizar la descripción
                self.ticket_id.description = (self.ticket_id.description or '') + _('\n\n✅ Cambio de componente completado y guardado.')
        except Exception as e:
            _logger.warning("No se pudo cerrar automáticamente el ticket %s: %s", self.ticket_id.name, str(e))
