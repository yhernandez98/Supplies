# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
import time

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    """Extender Sale Order para verificar stock y crear alertas por cotización."""
    _inherit = 'sale.order'

    purchase_alert_ids = fields.One2many(
        'purchase.alert',
        'sale_order_id',
        string='Alertas Por Cotización',
        readonly=True,
    )
    purchase_alert_count = fields.Integer(
        string='Número de Alertas',
        compute='_compute_purchase_alert_count',
        readonly=True,
    )
    has_stock_issues = fields.Boolean(
        string='Tiene Problemas de Stock',
        compute='_compute_stock_availability',
        readonly=True,
        store=False,
    )
    stock_availability_summary = fields.Text(
        string='Resumen de Disponibilidad',
        compute='_compute_stock_availability',
        readonly=True,
        store=False,
    )
    has_physical_products = fields.Boolean(
        string='Tiene Productos Físicos',
        compute='_compute_stock_availability',
        readonly=True,
        store=False,
    )
    stock_status_message = fields.Char(
        string='Estado de Stock',
        compute='_compute_stock_availability',
        readonly=True,
        store=False,
    )
    generate_accounting = fields.Boolean(
        string='Generar Contabilidad',
        default=False,
    )
    order_type_display = fields.Char(
        string='Tipo de Orden',
        compute='_compute_order_type_display',
        readonly=True,
        store=False,
        help='Indica si la orden está en cotización o ya está confirmada como compra',
    )

    @api.depends('purchase_alert_ids')
    def _compute_purchase_alert_count(self):
        """Calcular número de alertas por cotización."""
        for order in self:
            order.purchase_alert_count = len(order.purchase_alert_ids.filtered(lambda a: a.state == 'pending'))
    
    @api.depends('state')
    def _compute_order_type_display(self):
        """Calcular tipo de orden (Cotización o Compra confirmada)."""
        for order in self:
            if order.state in ('draft', 'sent'):
                order.order_type_display = _('Cotización')
            elif order.state in ('sale', 'done'):
                order.order_type_display = _('Compra Confirmada')
            elif order.state == 'cancel':
                order.order_type_display = _('Cancelada')
            else:
                order.order_type_display = _('Desconocido')

    @api.depends('order_line.product_id', 'order_line.product_uom_qty', 'warehouse_id')
    def _compute_stock_availability(self):
        """Verificar disponibilidad de stock para cada línea."""
        for order in self:
            order.has_stock_issues = False
            order.stock_availability_summary = ''
            order.has_physical_products = False
            order.stock_status_message = ''
            
            # Obtener líneas con productos
            lines = order.order_line.filtered(lambda l: l.product_id)
            if not lines:
                _logger.info("=== Orden %s no tiene líneas con productos ===", order.name)
                continue
            
            _logger.info("=== INICIANDO VERIFICACIÓN DE STOCK PARA ORDEN %s ===", order.name)
            _logger.info("Orden %s tiene %s líneas con productos", order.name, len(lines))
            
            # Separar por tipo de producto - SIMPLIFICADO
            product_lines = []
            consu_lines = []
            service_lines = []
            
            for line in lines:
                if not line.product_id:
                    continue
                
                # Leer tipo de producto - LEER DESDE TEMPLATE QUE ES MÁS CONFIABLE
                ptype = None
                try:
                    product_id = line.product_id.id
                    product_name = line.product_id.display_name
                    
                    # Leer desde product_tmpl_id que es más confiable en Odoo
                    if line.product_id.product_tmpl_id:
                        ptype = line.product_id.product_tmpl_id.type
                        _logger.info(">>> Línea %s - Producto: %s (ID: %s) - Tipo DESDE TEMPLATE: %s", 
                                    line.id, product_name, product_id, ptype)
                    else:
                        # Fallback: leer desde product_id directamente
                        ptype = line.product_id.type
                        _logger.info(">>> Línea %s - Producto: %s (ID: %s) - Tipo DESDE PRODUCT: %s (NO HAY TEMPLATE)", 
                                    line.id, product_name, product_id, ptype)
                    
                    # Validación adicional: verificar que el tipo sea válido
                    if ptype and ptype not in ('product', 'consu', 'service'):
                        _logger.warning(">>> Línea %s - Producto %s tiene tipo inválido: %s", 
                                      line.id, product_name, ptype)
                except Exception as e:
                    _logger.error(">>> ERROR leyendo tipo de producto para línea %s: %s", line.id, str(e), exc_info=True)
                    continue
                
                if not ptype:
                    _logger.warning(">>> Línea %s - No se pudo obtener tipo de producto", line.id)
                    continue
                
                # Clasificar por tipo - TRATAR 'consu' COMO 'product' PARA VERIFICAR STOCK
                if ptype == 'product':
                    product_lines.append(line)
                    _logger.info(">>> ✓ Línea %s clasificada como PRODUCTO ALMACENABLE (type='product')", line.id)
                elif ptype == 'consu':
                    # IMPORTANTE: Tratar consumibles como productos almacenables para verificar stock
                    product_lines.append(line)
                    consu_lines.append(line)  # También guardar en consu_lines para referencia
                    _logger.info(">>> ✓ Línea %s tratada como PRODUCTO ALMACENABLE (type='consu' pero se verifica stock)", line.id)
                elif ptype == 'service':
                    service_lines.append(line)
                    _logger.info(">>> ✓ Línea %s clasificada como SERVICIO (type='service')", line.id)
            
            _logger.info("=== RESUMEN ORDEN %s ===", order.name)
            _logger.info(">>> Productos tipo 'product' (almacenables): %s", len(product_lines))
            _logger.info(">>> Productos tipo 'consu' (consumibles): %s", len(consu_lines))
            _logger.info(">>> Productos tipo 'service' (servicios): %s", len(service_lines))
            
            # Si hay productos tipo 'product', verificar stock
            if product_lines:
                order.has_physical_products = True
                
                if not order.warehouse_id:
                    order.stock_status_message = _('⚠️ Sin almacén')
                    continue
                
                location = order.warehouse_id.lot_stock_id
                issues = []
                stock_info = []
                
                for line in product_lines:
                    try:
                        # Usar sudo() para _gather y luego filtrar solo los accesibles
                        all_quants = self.env['stock.quant'].sudo()._gather(line.product_id, location)
                        # Filtrar solo los quants que el usuario actual puede leer
                        accessible_quants = self.env['stock.quant']
                        for quant in all_quants:
                            try:
                                quant_check = self.env['stock.quant'].browse(quant.id)
                                if quant_check.exists():
                                    accessible_quants |= quant_check
                            except Exception:
                                continue
                        qty_available = sum(accessible_quants.mapped('quantity'))
                        qty_needed = line.product_uom_qty
                        
                        if qty_available < qty_needed:
                            missing = qty_needed - qty_available
                            issues.append(line)
                            stock_info.append(
                                _('%s: Faltan %s unidades') % (
                                    line.product_id.display_name,
                                    int(missing),
                                )
                            )
                        else:
                            stock_info.append(
                                _('%s: OK (disponible: %s)') % (
                                    line.product_id.display_name,
                                    int(qty_available),
                                )
                            )
                    except Exception as e:
                        _logger.error("Error verificando stock para línea %s: %s", line.id, str(e))
                        issues.append(line)
                        stock_info.append(_('%s: Error verificando') % line.product_id.display_name)
                
                order.has_stock_issues = len(issues) > 0
                order.stock_availability_summary = '\n'.join(stock_info)
                
                if order.has_stock_issues:
                    order.stock_status_message = _('⚠️ %s producto(s) sin stock') % len(issues)
                    _logger.info(">>> MENSAJE FINAL: ⚠️ %s producto(s) sin stock", len(issues))
                else:
                    order.stock_status_message = _('✓ Stock disponible')
                    _logger.info(">>> MENSAJE FINAL: ✓ Stock disponible")
            elif service_lines and not product_lines and not consu_lines:
                # Solo servicios
                order.has_physical_products = False
                order.stock_status_message = _('✓ Solo servicios')
                _logger.info(">>> MENSAJE FINAL: ✓ Solo servicios")
            else:
                # Si hay product_lines (que ahora incluye consu_lines tratados como product)
                # ya se manejó arriba
                if not product_lines:
                    _logger.warning(">>> CASO NO MANEJADO - product_lines: %s, consu_lines: %s, service_lines: %s", 
                                  len(product_lines), len(consu_lines), len(service_lines))

    @api.model_create_multi
    def create(self, vals_list):
        """Sobrescribir creación para verificar stock automáticamente cuando se crea desde CRM Lead."""
        orders = super().create(vals_list)
        
        # Ejecutar automáticamente después de crear
        for i, order in enumerate(orders):
            # Verificar si tiene opportunity_id
            has_opportunity = False
            if order.opportunity_id:
                has_opportunity = True
            elif i < len(vals_list) and vals_list[i].get('opportunity_id'):
                has_opportunity = True
            
            if has_opportunity:
                _logger.info("Orden %s creada desde Lead %s - Ejecutando verificación automática", 
                           order.name, order.opportunity_id.name if order.opportunity_id else 'N/A')
                
                try:
                    # Forzar flush y recálculo
                    order.flush_recordset()
                    order._compute_stock_availability()
                    order.flush_recordset()
                    
                    # Crear alertas automáticamente
                    order.sudo()._create_purchase_alerts_automatically()
                except Exception as e:
                    _logger.error("Error en creación automática de alertas para orden %s: %s", 
                                order.name, str(e), exc_info=True)
        
        return orders
    
    def write(self, vals):
        """Sobrescribir escritura para verificar stock cuando se agregan productos."""
        result = super().write(vals)
        
        # Si se modificaron las líneas y hay opportunity_id, verificar
        if 'order_line' in vals:
            for order in self:
                if order.opportunity_id and order.state == 'draft':
                    try:
                        order._compute_stock_availability()
                        order.flush_recordset()
                        order.sudo()._create_purchase_alerts_automatically()
                    except Exception as e:
                        _logger.error("Error en verificación automática para orden %s: %s", 
                                    order.name, str(e))
        
        return result
    
    def _create_purchase_alerts_automatically(self):
        """Crear alertas por cotización automáticamente cuando se crea orden desde Lead."""
        self.ensure_one()
        
        # Si se está creando una alerta manualmente desde el wizard (sin productos), no crear alertas automáticas
        if self.env.context.get('skip_auto_create_alerts'):
            _logger.debug("Orden %s - Saltando creación automática (skip_auto_create_alerts=True)", self.name)
            return
        
        if not self.opportunity_id or not self.warehouse_id:
            _logger.debug("Orden %s no tiene Lead o almacén - Saltando creación automática", self.name)
            return
        
        # Si viene del wizard con productos, verificar duplicados antes de crear
        if self.env.context.get('from_wizard'):
            # Verificar si ya existe una alerta pendiente para esta orden
            existing_alert = self.env['purchase.alert'].search([
                ('sale_order_id', '=', self.id),
                ('state', '=', 'pending'),
            ], limit=1)
            
            if existing_alert:
                _logger.debug("Orden %s - Ya existe alerta pendiente (ID: %s), saltando creación automática", 
                             self.name, existing_alert.id)
                return
        
        # Verificar si ya existe una alerta manual (sin productos) para esta orden
        # Si existe y NO viene del wizard, no crear alertas automáticas para evitar duplicados
        if not self.env.context.get('from_wizard'):
            existing_manual_alert = self.env['purchase.alert'].search([
                ('sale_order_id', '=', self.id),
                ('state', '=', 'pending'),
                ('product_id', '=', False),  # Alerta manual sin producto específico
                ('alert_line_ids', '=', False),  # Sin líneas de productos
            ], limit=1)
            
            if existing_manual_alert:
                _logger.debug("Orden %s - Ya existe alerta manual (ID: %s), saltando creación automática", 
                             self.name, existing_manual_alert.id)
                return
        
        _logger.info("Creando alertas automáticas para orden %s (Lead: %s)", 
                    self.name, self.opportunity_id.name)
        
        location = self.warehouse_id.lot_stock_id
        
        # Inicializar lista de alertas creadas
        alerts_created = []
        
        # Agrupar todas las líneas que necesitan stock en una sola alerta
        lines_needing_stock = []
        
        # Verificar cada línea de producto tipo 'product'
        for line in self.order_line:
            if not line.product_id:
                continue
            
            # Verificar tipo de producto - LEER DESDE TEMPLATE
            ptype = None
            if line.product_id.product_tmpl_id:
                ptype = line.product_id.product_tmpl_id.type
            else:
                ptype = line.product_id.type
            
            _logger.debug("Verificando línea %s - Producto %s (ID: %s) - Tipo desde template: %s", 
                         line.id, line.product_id.display_name, line.product_id.id, ptype)
            
            # Verificar stock para productos tipo 'product' o 'consu' (tratamos consu como product)
            if ptype not in ('product', 'consu'):
                _logger.debug("Línea %s saltada - No es tipo 'product' o 'consu' (tipo: %s)", line.id, ptype)
                continue
            
            try:
                # Verificar stock
                # Usar sudo() para _gather y luego filtrar solo los accesibles
                all_quants = self.env['stock.quant'].sudo()._gather(line.product_id, location)
                # Filtrar solo los quants que el usuario actual puede leer
                accessible_quants = self.env['stock.quant']
                for quant in all_quants:
                    try:
                        quant_check = self.env['stock.quant'].browse(quant.id)
                        if quant_check.exists():
                            accessible_quants |= quant_check
                    except Exception:
                        continue
                qty_available = sum(accessible_quants.mapped('quantity'))
                qty_needed = line.product_uom_qty
                
                _logger.debug("Línea %s - Stock disponible: %s, Necesita: %s", 
                             line.id, qty_available, qty_needed)
                
                # Si falta stock, agregar a la lista
                if qty_available < qty_needed:
                    # Verificar si ya existe una alerta para esta línea
                    existing = self.env['purchase.alert'].search([
                        ('sale_order_id', '=', self.id),
                        ('alert_line_ids.sale_order_line_id', '=', line.id),
                        ('state', '=', 'pending'),
                    ], limit=1)
                    
                    if not existing:
                        lines_needing_stock.append({
                            'sale_order_line_id': line.id,
                            'product_id': line.product_id.id,
                            'quantity_requested': qty_needed,
                        })
            except Exception as e:
                _logger.error("Error verificando stock para línea %s: %s", line.id, str(e))
                continue
        
        # Crear una sola alerta con todas las líneas que necesitan stock
        if lines_needing_stock:
            # Verificar si ya existe una alerta pendiente para esta orden
            existing_alert = self.env['purchase.alert'].search([
                ('sale_order_id', '=', self.id),
                ('state', '=', 'pending'),
            ], limit=1)
            
            if existing_alert:
                # Agregar líneas nuevas a la alerta existente
                for line_data in lines_needing_stock:
                    # Verificar si la línea ya existe
                    existing_line = existing_alert.alert_line_ids.filtered(
                        lambda l: l.sale_order_line_id.id == line_data['sale_order_line_id']
                    )
                    if not existing_line:
                        self.env['purchase.alert.line'].create({
                            'alert_id': existing_alert.id,
                            'sale_order_line_id': line_data['sale_order_line_id'],
                            'product_id': line_data['product_id'],
                            'quantity_requested': line_data['quantity_requested'],
                        })
                
                # Forzar actualización de componentes, periféricos y complementos después de agregar líneas
                existing_alert.invalidate_recordset(['alert_line_ids'])
                if len(existing_alert.alert_line_ids) > 1:
                    _logger.info("Alerta existente %s ahora tiene %s productos, actualizando componentes/periféricos/complementos", 
                               existing_alert.name, len(existing_alert.alert_line_ids))
                    existing_alert._update_component_lines()
            else:
                # Crear nueva alerta con todas las líneas
                alert_vals = {
                    'sale_order_id': self.id,
                    'product_id': lines_needing_stock[0]['product_id'] if len(lines_needing_stock) == 1 else False,
                    'state': 'pending',
                    'warehouse_id': self.warehouse_id.id,
                    'lead_id': self.opportunity_id.id,
                }
                
                # Agregar partner_id si existe
                if self.partner_id:
                    alert_vals['partner_id'] = self.partner_id.id
                elif self.opportunity_id and self.opportunity_id.partner_id:
                    alert_vals['partner_id'] = self.opportunity_id.partner_id.id
                
                alert = self.env['purchase.alert'].create(alert_vals)
                
                # Crear las líneas de la alerta
                for line_data in lines_needing_stock:
                    self.env['purchase.alert.line'].create({
                        'alert_id': alert.id,
                        'sale_order_line_id': line_data['sale_order_line_id'],
                        'product_id': line_data['product_id'],
                        'quantity_requested': line_data['quantity_requested'],
                    })
                
                # Forzar actualización de componentes, periféricos y complementos después de crear todas las líneas
                # Esto es necesario porque cuando hay múltiples productos, las líneas se crean después de la alerta
                alert.invalidate_recordset(['alert_line_ids'])
                if len(alert.alert_line_ids) > 1:
                    _logger.info("Alerta %s tiene %s productos, actualizando componentes/periféricos/complementos", 
                               alert.name, len(alert.alert_line_ids))
                    alert._update_component_lines()
                
                alerts_created.append(alert.id)
                _logger.info("Alerta %s creada con %s líneas de productos", alert.name, len(lines_needing_stock))
        
        # Si se creó una alerta con múltiples líneas, agregar nota
        if alerts_created:
            alert_count = len(alerts_created)
            if alert_count == 1:
                alert = self.env['purchase.alert'].browse(alerts_created[0])
                if len(alert.alert_line_ids) > 1:
                    alert.write({
                        'notes': _('Creado automáticamente desde CRM Lead: %s\n\nEsta alerta contiene %s productos que necesitan ser cotizados.') % (
                            self.opportunity_id.name, len(alert.alert_line_ids)
                        )
                    })
                else:
                    alert.write({
                        'notes': _('Creado automáticamente desde CRM Lead: %s') % self.opportunity_id.name
                    })
            
            self.message_post(
                body=_('✅ Se creó automáticamente %s alerta(s) de compra desde el CRM Lead.') % alert_count,
            )
            _logger.info("Total de alertas creadas automáticamente para orden %s: %s", 
                        self.name, alert_count)
    

    def action_confirm(self):
        """Sobrescribir confirmación para verificar stock y crear suscripción automáticamente si aplica."""
        _logger.info("=== INICIANDO action_confirm para orden(es) %s ===", self.mapped('name'))
        
        for order in self:
            _logger.info(">>> Procesando orden: %s (ID: %s)", order.name, order.id)
            _logger.info(">>> Estado actual: %s", order.state)
            _logger.info(">>> Partner: %s (ID: %s)", order.partner_id.name if order.partner_id else 'N/A', order.partner_id.id if order.partner_id else 'N/A')
            _logger.info(">>> Opportunity: %s (ID: %s)", order.opportunity_id.name if order.opportunity_id else 'N/A', order.opportunity_id.id if order.opportunity_id else 'N/A')
            _logger.info(">>> Picking IDs antes de confirmar: %s", order.picking_ids.mapped('name'))
        
        if self.has_stock_issues:
            _logger.warning(">>> Orden(es) %s tiene(n) problemas de stock", self.mapped('name'))
            self.message_post(
                body=_('⚠️ ADVERTENCIA: Esta orden tiene productos sin stock suficiente. '
                      'Considera crear alertas por cotización antes de confirmar.'),
                subject=_('Verificación de Stock'),
            )
        
        # Guardar si viene de un Lead con suscripción antes de confirmar
        lead = self.opportunity_id
        should_create_subscription = (
            lead and 
            lead.is_subscription_opportunity and 
            lead.auto_generate_subscription
        )
        
        if should_create_subscription:
            _logger.info(">>> Se creará suscripción automáticamente para orden %s", self.name)
        else:
            _logger.info(">>> NO se creará suscripción automáticamente para orden %s", self.name)
        
        # Intentar confirmar la orden - capturar cualquier error
        _logger.info(">>> Llamando a super().action_confirm() para orden(es) %s", self.mapped('name'))
        try:
            result = super().action_confirm()
            _logger.info(">>> super().action_confirm() completado exitosamente para orden(es) %s", self.mapped('name'))
        except Exception as e:
            _logger.error(">>> ERROR en super().action_confirm() para orden(es) %s: %s", 
                         self.mapped('name'), str(e), exc_info=True)
            _logger.error(">>> Tipo de error: %s", type(e).__name__)
            # Re-lanzar el error para que Odoo lo maneje
            raise
        
        _logger.info(">>> Estado después de super().action_confirm(): %s", self.mapped('state'))
        _logger.info(">>> Picking IDs después de confirmar: %s", self.mapped('picking_ids.name'))
        
        if not self.generate_accounting:
            pass
        
        # Crear suscripción automáticamente después de confirmar la orden
        if should_create_subscription:
            _logger.info(">>> Iniciando creación de suscripción para orden %s", self.name)
            try:
                self._create_subscription_from_sale_order()
                _logger.info(">>> Suscripción creada exitosamente para orden %s", self.name)
            except Exception as e:
                _logger.error(">>> ERROR creando suscripción automáticamente desde orden %s: %s", 
                            self.name, str(e), exc_info=True)
                _logger.error(">>> Tipo de error: %s", type(e).__name__)
                # Capturar el error específico de restricción única
                error_msg = str(e)
                if 'única' in error_msg or 'unique' in error_msg.lower() or 'duplicate key' in error_msg.lower():
                    _logger.error(">>> ERROR DE RESTRICCIÓN ÚNICA detectado: %s", error_msg)
                    # Intentar obtener más detalles del error
                    import traceback
                    _logger.error(">>> Traceback completo:\n%s", traceback.format_exc())
                
                self.message_post(
                    body=_('⚠️ Advertencia: No se pudo crear la suscripción automáticamente: %s') % str(e),
                    subject=_('Creación de Suscripción'),
                )
        
        _logger.info("=== FINALIZANDO action_confirm para orden(es) %s ===", self.mapped('name'))
        return result
    
    def _create_subscription_from_sale_order(self):
        """Crear suscripción automáticamente desde una orden de venta confirmada."""
        self.ensure_one()
        
        if not self.opportunity_id:
            _logger.warning("Orden %s no tiene Lead asociado - No se creará suscripción", self.name)
            return
        
        lead = self.opportunity_id
        
        if not lead.is_subscription_opportunity:
            _logger.debug("Lead %s no está marcado como suscripción - No se creará suscripción", lead.name)
            return
        
        if not self.partner_id:
            raise UserError(_('La orden debe tener un cliente para crear la suscripción.'))
        
        _logger.info("Creando suscripción automáticamente desde orden %s (Lead: %s)", self.name, lead.name)
        
        # Obtener ubicación del cliente (del Lead o del partner)
        location = lead.location_id
        if not location and self.partner_id:
            location = self.partner_id.property_stock_customer
        
        # Preparar productos tipo 'service' desde la orden de venta
        products = []
        for line in self.order_line:
            if not line.product_id:
                continue
            
            # Verificar tipo de producto
            ptype = None
            if line.product_id.product_tmpl_id:
                ptype = line.product_id.product_tmpl_id.type
            else:
                ptype = line.product_id.type
            
            # Solo agregar productos tipo 'service' para la suscripción
            if ptype == 'service':
                products.append({
                    'product': line.product_id,
                    'quantity': int(line.product_uom_qty) or 1,  # Cantidad entera
                    'price': int(line.price_unit) or line.product_id.list_price,  # Precio entero
                })
                _logger.info("Producto agregado a suscripción: %s (cantidad: %s, precio: %s)", 
                           line.product_id.display_name, int(line.product_uom_qty) or 1, 
                           int(line.price_unit) or line.product_id.list_price)
        
        if not products:
            _logger.warning("Orden %s no tiene productos tipo 'service' - No se creará suscripción", self.name)
            self.message_post(
                body=_('ℹ️ Información: La orden no tiene productos tipo servicio, por lo que no se creó suscripción.'),
                subject=_('Creación de Suscripción'),
            )
            return
        
        # Crear o actualizar suscripción usando ensure_subscription
        Subscription = self.env['subscription.subscription']
        
        _logger.info(">>> Buscando suscripción existente para partner %s (ID: %s) y location %s (ID: %s)", 
                    self.partner_id.display_name, self.partner_id.id, 
                    location.display_name if location else 'N/A', location.id if location else 'N/A')
        
        # Primero buscar si ya existe una suscripción para este partner y location
        domain = [('partner_id', '=', self.partner_id.id)]
        if location:
            domain.append(('location_id', '=', location.id))
        
        _logger.info(">>> Dominio de búsqueda: %s", domain)
        existing_subscription = Subscription.search(domain, limit=1)
        
        if existing_subscription:
            _logger.info(">>> Suscripción existente encontrada: %s (ID: %s)", 
                       existing_subscription.name, existing_subscription.id)
            # Si ya existe, usar esa suscripción y sincronizar productos
            subscription = existing_subscription
            if products:
                _logger.info(">>> Sincronizando productos en suscripción existente")
                subscription._sync_subscription_lines(products, remove_missing=False, track_usage=True)
        else:
            _logger.info(">>> No se encontró suscripción existente, creando nueva")
            # Si no existe, crear una nueva con nombre único
            base_name = self.partner_id.display_name
            if location:
                base_name = '%s - %s' % (self.partner_id.display_name, location.display_name)
            
            _logger.info(">>> Nombre base para suscripción: %s", base_name)
            
            # Generar nombre único verificando que no exista
            # El error "La referencia debe ser única por empresa" sugiere un constraint SQL
            # Usar timestamp desde el inicio para garantizar unicidad
            timestamp = int(time.time())
            name = f"{base_name} - {timestamp}"
            
            _logger.info(">>> Verificando unicidad del nombre: %s", name)
            
            # Verificar que no exista (por si acaso hay colisión de timestamps)
            # IMPORTANTE: Verificar también por company_id ya que el error menciona "única por empresa"
            counter = 1
            while Subscription.search([
                ('name', '=', name),
                ('company_id', '=', self.env.company.id)
            ], limit=1):
                _logger.warning(">>> Colisión de nombre detectada (intento %s): %s", counter, name)
                name = f"{base_name} - {timestamp} ({counter})"
                counter += 1
                if counter > 100:
                    # Si hay más de 100 colisiones, algo está mal
                    _logger.error(">>> Demasiadas colisiones de nombres de suscripción")
                    raise UserError(_('Error generando nombre único para la suscripción. Por favor, contacte al administrador.'))
            
            _logger.info(">>> Nombre único generado: %s", name)
            
            # Preparar valores para crear la suscripción
            subscription_vals = {
                'name': name,  # Nombre explícito con timestamp para garantizar unicidad
                'partner_id': self.partner_id.id,
                'location_id': location.id if location else False,
                'currency_id': self.partner_id.currency_id.id or self.env.company.currency_id.id,
                'state': 'draft',
                'company_id': self.env.company.id,  # Asegurar que se establezca la compañía
            }
            
            _logger.info(">>> Valores para crear suscripción: %s", subscription_vals)
            _logger.info(">>> Intentando crear suscripción con nombre: %s", name)
            
            try:
                # Crear la suscripción con el nombre único
                subscription = Subscription.create(subscription_vals)
                _logger.info(">>> Suscripción creada exitosamente: %s (ID: %s)", subscription.name, subscription.id)
            except Exception as create_error:
                _logger.error(">>> ERROR al crear suscripción: %s", str(create_error), exc_info=True)
                _logger.error(">>> Tipo de error: %s", type(create_error).__name__)
                # Re-lanzar el error para que se maneje arriba
                raise
            
            # Sincronizar líneas de productos
            if products:
                _logger.info(">>> Sincronizando productos en nueva suscripción")
                subscription._sync_subscription_lines(products, remove_missing=False, track_usage=True)
        
        # Activar la suscripción si está en borrador
        if subscription.state == 'draft':
            subscription.action_activate()
            _logger.info("Suscripción %s activada automáticamente", subscription.name)
        
        # Agregar mensaje en la orden
        self.message_post(
            body=_('✅ Suscripción %s creada automáticamente desde esta orden de venta.') % subscription.name,
            subject=_('Suscripción Creada'),
        )
        
        # Agregar mensaje en el Lead
        lead.message_post(
            body=_('✅ Suscripción %s creada automáticamente desde la orden de venta %s.') % (
                subscription.name, self.name
            ),
            subject=_('Suscripción Creada'),
        )
        
        _logger.info("✅ Suscripción %s creada exitosamente desde orden %s", subscription.name, self.name)
        
        return subscription

    def action_view_purchase_alerts(self):
        """Ver alertas por cotización relacionadas con esta orden."""
        self.ensure_one()
        action = {
            'name': _('Alertas Por Cotización'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.alert',
            'view_mode': 'list,form',
            'domain': [('sale_order_id', '=', self.id)],
            'context': {'default_sale_order_id': self.id},
        }
        if len(self.purchase_alert_ids) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': self.purchase_alert_ids.id,
            })
        return action
    
    def action_request_purchase_quotation(self):
        """Solicitar cotización de compra para productos sin stock o sin productos específicos."""
        self.ensure_one()
        
        # Si no hay productos físicos, abrir wizard para crear alerta manual
        if not self.has_physical_products:
            # Verificar si hay productos en las líneas
            has_any_product = any(
                line.product_id and line.product_id.type in ('product', 'consu') 
                for line in self.order_line
            )
            
            if not has_any_product:
                # No hay productos físicos, abrir wizard para crear alerta manual
                return {
                    'type': 'ir.actions.act_window',
                    'name': _('Solicitar Cotización de Compra'),
                    'res_model': 'sale.order.request.quotation.wizard',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_sale_order_id': self.id,
                        'active_id': self.id,
                        'active_model': 'sale.order',
                    },
                }
        
        # Si hay productos físicos pero no hay problemas de stock
        if not self.has_stock_issues:
            # Ofrecer opción de crear alerta manual de todas formas
            return {
                'type': 'ir.actions.act_window',
                'name': _('Solicitar Cotización de Compra'),
                'res_model': 'sale.order.request.quotation.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_sale_order_id': self.id,
                    'active_id': self.id,
                    'active_model': 'sale.order',
                },
            }
        
        # Si hay problemas de stock, las alertas ya se crean automáticamente
        # Pero también ofrecer opción de crear alerta manual si el usuario lo desea
        return {
            'type': 'ir.actions.act_window',
            'name': _('Solicitar Cotización de Compra'),
            'res_model': 'sale.order.request.quotation.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_order_id': self.id,
                'active_id': self.id,
                'active_model': 'sale.order',
            },
        }
    
    def action_view_all_purchase_alerts(self):
        """Ver todas las alertas por cotización."""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Alertas Por Cotización'),
            'res_model': 'purchase.alert',
            'view_mode': 'list,form',
            'domain': [],
            'context': {'create': False},
        }
