# -*- coding: utf-8 -*-
import calendar
import datetime
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class StockLot(models.Model):
    _inherit = "stock.lot"
    
    subscription_service_product_id = fields.Many2one(
        'product.product',
        string='Servicio',
        domain="[('type', '=', 'service')]",
        help='Servicio que se utilizará en las líneas de suscripción cuando este serial se sincronice desde inventario. Si no se especifica, se usará el servicio del producto.',
    )
    
    available_subscription_ids = fields.Many2many(
        'subscription.subscription',
        string='Suscripciones Disponibles',
        compute='_compute_available_subscription_ids',
        store=False,
        help='Suscripciones disponibles según el cliente de la ubicación del lote'
    )
    
    active_subscription_id = fields.Many2one(
        'subscription.subscription',
        string='Suscripción Activa',
        domain="[('id', 'in', available_subscription_ids)]",
        help='Suscripción a la que está asignado este serial. Solo se mostrará en la suscripción asignada.',
        index=True,
    )
    # Mantener registro en suscripción hasta el día 1 del mes siguiente (producto salió a otro cliente)
    last_subscription_id = fields.Many2one(
        'subscription.subscription',
        string='Última suscripción (hasta día 1)',
        readonly=True,
        index=True,
        help='Suscripción de la que salió el serial; el registro sigue visible en esa suscripción hasta pending_removal_date.',
    )
    last_subscription_service_id = fields.Many2one(
        'product.product',
        string='Último servicio (hasta día 1)',
        readonly=True,
        help='Servicio con el que se mostraba en la suscripción; se usa hasta que el día 1 actualice.',
    )
    pending_removal_date = fields.Date(
        string='Baja en suscripción el',
        readonly=True,
        help='Día 1 del mes siguiente: ese día el cron quita el serial de la suscripción y limpia last_*.',
    )
    # Fechas que tenía cuando salió de esa suscripción; así si editas el lote en el nuevo cliente, la suscripción de origen no cambia
    last_subscription_entry_date = fields.Date(
        string='Fecha activación (en suscripción de la que salió)',
        readonly=True,
        help='Fecha de activación que se muestra en la suscripción de la que salió; no se actualiza al editar el lote en el nuevo cliente.',
    )
    last_subscription_exit_date = fields.Date(
        string='Fecha finalización (en suscripción de la que salió)',
        readonly=True,
        help='Fecha de finalización que se muestra en la suscripción de la que salió; no se actualiza al editar el lote en el nuevo cliente.',
    )

    def write(self, vals):
        # Al quitar la suscripción del serial (producto sale a otro cliente): mantener registro hasta día 1 del mes siguiente.
        # Solo guardar last_subscription_id si aún no hay uno (A→B→C mismo día: no sobrescribir con B, así A sigue viendo salida y B no aparece).
        if 'active_subscription_id' in vals and vals.get('active_subscription_id') is False:
            today = fields.Date.context_today(self)
            next_month = today + relativedelta(months=1)
            first_next = datetime.date(next_month.year, next_month.month, 1)
            for lot in self:
                if lot.active_subscription_id and not lot.last_subscription_id:
                    vals = dict(vals, last_subscription_id=lot.active_subscription_id.id)
                    vals = dict(vals, pending_removal_date=first_next)
                    # Guardar fechas que tenía en esa suscripción para que no cambien si editan el lote en el nuevo cliente
                    entry_saved = getattr(lot, 'entry_date', None) or getattr(lot, 'last_entry_date_display', None)
                    exit_saved = getattr(lot, 'exit_date', None) or getattr(lot, 'last_exit_date_display', None)
                    vals = dict(vals, last_subscription_entry_date=entry_saved, last_subscription_exit_date=exit_saved)
                    if 'subscription_service_product_id' in vals and vals.get('subscription_service_product_id') is False:
                        vals = dict(vals, last_subscription_service_id=lot.subscription_service_product_id.id if lot.subscription_service_product_id else False)
                    elif lot.subscription_service_product_id:
                        vals = dict(vals, last_subscription_service_id=lot.subscription_service_product_id.id)
                    break  # un solo lote actualizado por write; mismo criterio para todos
            # No borrar last_exit_date_display ni last_entry_date_display aquí: la suscripción debe seguir
            # mostrando las fechas hasta el día 1 (el cron las limpia entonces).
        # Si también quitan el servicio, guardar para mostrar hasta el día 1
        if 'subscription_service_product_id' in vals and vals.get('subscription_service_product_id') is False:
            for lot in self:
                if lot.subscription_service_product_id and not vals.get('last_subscription_service_id'):
                    vals = dict(vals, last_subscription_service_id=lot.subscription_service_product_id.id)
        res = super().write(vals)
        # Reentrega al mismo cliente: si el serial quedó asignado a la suscripción de la que "salió", limpiar last_* (solo en esos lotes)
        if 'active_subscription_id' in vals and vals.get('active_subscription_id'):
            to_clear = self.filtered(
                lambda l: l.last_subscription_id and l.active_subscription_id and l.active_subscription_id.id == l.last_subscription_id.id
            )
            if to_clear:
                clear_vals = {
                    'last_subscription_id': False,
                    'pending_removal_date': False,
                    'last_subscription_entry_date': False,
                    'last_subscription_exit_date': False,
                    'last_subscription_service_id': False,
                }
                to_clear.write(clear_vals)
        # Para que la suscripción actualice productos agrupados (incluir/quitar hasta día 1)
        if 'last_subscription_id' in vals or 'pending_removal_date' in vals:
            for lot in self:
                if lot.last_subscription_id:
                    lot.last_subscription_id.invalidate_recordset(['grouped_product_ids'])
        return res

    # Visualización: día del mes en curso y costo acumulado al día (para vista de series)
    current_day_of_month = fields.Integer(
        string='Día del mes',
        compute='_compute_cost_to_date_display',
        store=False,
        help='Día del mes en curso (1-31), para referencia en listados.'
    )
    cost_to_date_currency_id = fields.Many2one(
        'res.currency',
        compute='_compute_cost_to_date_display',
        store=False,
    )
    cost_to_date_current = fields.Monetary(
        string='Costo al día',
        compute='_compute_cost_to_date_display',
        currency_field='cost_to_date_currency_id',
        store=False,
        help='Costo prorrateado acumulado hasta el día de hoy en el mes en curso (solo productos con servicio y fechas).'
    )

    @api.depends('active_subscription_id', 'subscription_service_product_id', 'entry_date', 'last_entry_date_display', 'exit_date', 'last_exit_date_display')
    def _compute_cost_to_date_display(self):
        """Día del mes: días activos en el mes (según entry/exit). Costo acumulado prorrateado por esos días."""
        today = fields.Date.today()
        year, month = today.year, today.month
        days_in_month = calendar.monthrange(year, month)[1]
        first_day = datetime.date(year, month, 1)
        today_date = datetime.date(today.year, today.month, today.day) if hasattr(today, 'year') else today
        day_of_month_elapsed = min(today.day, days_in_month)  # días transcurridos si no hay fechas
        for lot in self:
            lot.cost_to_date_currency_id = False
            lot.cost_to_date_current = 0.0
            entry_date = getattr(lot, 'entry_date', None) or getattr(lot, 'last_entry_date_display', None)
            exit_date = getattr(lot, 'exit_date', None) or getattr(lot, 'last_exit_date_display', None)
            if entry_date and hasattr(entry_date, 'year'):
                entry_date = datetime.date(entry_date.year, entry_date.month, entry_date.day)
            if exit_date and hasattr(exit_date, 'year'):
                exit_date = datetime.date(exit_date.year, exit_date.month, exit_date.day)
            # Días activos en el mes: desde entry (o inicio mes) hasta exit (o hoy)
            end = min(exit_date or today_date, today_date)
            start = max(entry_date or first_day, first_day)
            days_used = max(0, (end - start).days + 1)
            # Día del mes: con fechas = días activos; sin fechas = días transcurridos en el mes
            if entry_date is not None or exit_date is not None:
                lot.current_day_of_month = days_used
            else:
                lot.current_day_of_month = day_of_month_elapsed
            if not lot.active_subscription_id or not lot.subscription_service_product_id:
                continue
            try:
                lot.cost_to_date_currency_id = lot.active_subscription_id.currency_id or lot.env.company.currency_id
                price_monthly = lot.active_subscription_id._get_price_for_product(
                    lot.subscription_service_product_id, 1.0
                ) or 0.0
                if days_in_month > 0:
                    lot.cost_to_date_current = round(
                        (price_monthly / float(days_in_month)) * float(days_used), 2
                    )
            except Exception:
                lot.cost_to_date_current = 0.0

<<<<<<< HEAD
    @api.depends('quant_ids', 'quant_ids.location_id', 'quant_ids.quantity', 'location_partner_id', 'customer_id', 'customer_location_id')
=======
    @api.depends('quant_ids', 'quant_ids.location_id', 'quant_ids.quantity', 'location_partner_id')
>>>>>>> fb2d0eddb44261c7833d37e32b0869ec9bdb22c2
    def _compute_available_subscription_ids(self):
        """Calcular suscripciones disponibles según el cliente de la ubicación del lote."""
        for lot in self:
            # Inicializar como lista vacía
            lot.available_subscription_ids = []
            
            if not lot.id:
                continue
            
            # Obtener el cliente de la ubicación
            customer_partner_id = False
            customer_location_id = False
            
            # Intentar obtener desde location_partner_id (product_suppiles_partner)
            if hasattr(lot, 'location_partner_id') and lot.location_partner_id:
                customer_partner_id = lot.location_partner_id.id
            
            # Intentar obtener desde customer_id (mesa_ayuda_inventario)
            if not customer_partner_id and hasattr(lot, 'customer_id') and lot.customer_id:
                customer_partner_id = lot.customer_id.id
            
            # Intentar obtener desde customer_location_id (mesa_ayuda_inventario)
            if hasattr(lot, 'customer_location_id') and lot.customer_location_id:
                customer_location_id = lot.customer_location_id.id
            
            # Si no hay customer_location_id, intentar obtener desde quants
            if not customer_location_id and lot.quant_ids:
                quant = lot.quant_ids.filtered(lambda q: q.quantity > 0 and q.location_id.usage == 'internal')
                if quant:
                    location = quant[0].location_id
                    customer_location_id = location.id
                    
                    # Si no hay customer_partner_id, intentar obtenerlo desde la ubicación
                    if not customer_partner_id:
                        partner = lot.env['res.partner'].search([
                            ('property_stock_customer', '=', location.id)
                        ], limit=1)
                        if partner:
                            customer_partner_id = partner.id
            
            # Buscar suscripciones según el cliente y ubicación
            domain = [('state', 'in', ('draft', 'active'))]
            
            if customer_partner_id:
                domain.append(('partner_id', '=', customer_partner_id))
            
            if customer_location_id:
                domain.append(('location_id', '=', customer_location_id))
            
            # Si tenemos al menos cliente o ubicación, buscar suscripciones
            if customer_partner_id or customer_location_id:
                subscriptions = lot.env['subscription.subscription'].search(domain)
                lot.available_subscription_ids = subscriptions.ids
            else:
                # Si no hay cliente ni ubicación, no mostrar ninguna suscripción
                lot.available_subscription_ids = []
    
    @api.onchange('quant_ids')
    def _onchange_quant_ids_update_subscriptions(self):
        """Forzar recálculo de suscripciones disponibles cuando cambian los quants."""
        self._compute_available_subscription_ids()
        return {
            'domain': {
                'active_subscription_id': [('id', 'in', self.available_subscription_ids.ids), ('state', 'in', ('draft', 'active'))]
            }
        }

    def name_get(self):
        """Personaliza el nombre mostrado para mostrar solo la placa de inventario cuando se usa desde el wizard."""
        context = self.env.context or {}
        
        # LOGGING DETALLADO: Registrar todo el contexto para depuración
        _logger.info("=" * 80)
        _logger.info("name_get llamado para stock.lot")
        _logger.info("Contexto completo: %s", context)
        _logger.info("IDs de lotes: %s", self.ids)
        
        # ESTRATEGIA SIMPLIFICADA: Verificar si estamos en el contexto del wizard
        # El contexto puede venir de varias formas cuando se llama desde un Many2one:
        # 1. Directamente desde el campo Many2one (equipment_change_wizard, search_by_inventory_plate_only)
        # 2. Desde la acción que abre el wizard (active_model)
        # 3. Desde la vista de lista cuando se abre el dropdown (list_view_ref)
        
        # Verificar todas las formas posibles de detectar el contexto del wizard
        equipment_change_wizard = context.get('equipment_change_wizard')
        search_by_inventory_plate_only = context.get('search_by_inventory_plate_only')
        active_model = context.get('active_model')
        default_model = context.get('default_model')
        list_view_ref = context.get('list_view_ref')
        active_id = context.get('active_id')
        
        _logger.info("Valores del contexto:")
        _logger.info("  - equipment_change_wizard: %s", equipment_change_wizard)
        _logger.info("  - search_by_inventory_plate_only: %s", search_by_inventory_plate_only)
        _logger.info("  - active_model: %s", active_model)
        _logger.info("  - default_model: %s", default_model)
        _logger.info("  - list_view_ref: %s", list_view_ref)
        _logger.info("  - active_id: %s", active_id)
        
        is_wizard_context = (
            equipment_change_wizard or 
            search_by_inventory_plate_only or
            active_model == 'subscription.equipment.change.wizard' or
            default_model == 'subscription.equipment.change.wizard' or
            'equipment_change' in str(list_view_ref) or
            'view_stock_lot_equipment_change_tree' in str(list_view_ref)
        )
        
        _logger.info("is_wizard_context (después de verificación inicial): %s", is_wizard_context)
        
        # SOLUCIÓN ALTERNATIVA: Si el contexto no está disponible, verificar si hay un registro
        # del wizard activo en el entorno. Esto es útil cuando el contexto no se propaga correctamente.
        # ESTRATEGIA: Verificar active_id primero, ya que es más confiable que active_model en llamadas RPC
        if not is_wizard_context:
            # Intentar verificar si hay un wizard activo usando active_id
            if active_id:
                try:
                    wizard_model = self.env.get('subscription.equipment.change.wizard')
                    if wizard_model:
                        _logger.info("Intentando verificar wizard activo. active_id: %s", active_id)
                        # Verificar si hay un wizard activo (esto puede ayudar a detectar el contexto)
                        active_wizard = wizard_model.browse(active_id)
                        if active_wizard.exists():
                            _logger.info("Wizard activo encontrado por active_id: %s", active_wizard.ids)
                            # Si hay un wizard activo, asumir que estamos en el contexto del wizard
                            is_wizard_context = True
                except Exception as e:
                    # Si falla, continuar con el método normal
                    _logger.warning("Error al verificar wizard activo: %s", str(e))
            
            # Si aún no se detectó, intentar verificar usando active_model
            if not is_wizard_context and active_model:
                if active_model == 'subscription.equipment.change.wizard':
                    _logger.info("Wizard detectado por active_model: %s", active_model)
                    is_wizard_context = True
        
        _logger.info("is_wizard_context (final): %s", is_wizard_context)
        
        # Si el contexto indica que es desde el wizard, mostrar SOLO la placa de inventario
        if is_wizard_context:
            _logger.info("Usando modo wizard: mostrar solo placa de inventario")
            result = []
            for lot in self:
                # Mostrar SOLO la placa de inventario si existe
                if lot.inventory_plate:
                    display_name = lot.inventory_plate
                # Si no hay placa, usar el número de serie como fallback
                elif lot.name:
                    display_name = lot.name
                # Si no hay nada, usar el ID
                else:
                    display_name = "Lote #%s" % lot.id
                
                _logger.info("  Lote ID %s: display_name = %s (inventory_plate=%s, name=%s)", 
                           lot.id, display_name, lot.inventory_plate, lot.name)
                result.append((lot.id, display_name))
            _logger.info("=" * 80)
            return result
        
        # Si no es desde el wizard, usar el método original del módulo product_suppiles
        # que muestra: "PLACA - Serie: SERIAL - PRODUCTO"
        _logger.info("Usando método original (no es wizard)")
        _logger.info("=" * 80)
        return super(StockLot, self).name_get()

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, order=None):
        """Sobrescribe la búsqueda para buscar SOLO por inventory_plate cuando se usa desde el wizard de cambio de equipo."""
        try:
            # Asegurar que args sea siempre una lista válida
            if args is None:
                args = []
            elif not isinstance(args, list):
                # Si args no es una lista, intentar convertirlo
                try:
                    args = list(args) if args else []
                except (TypeError, ValueError):
                    args = []
            
            context = self.env.context or {}
            
            # DETECCIÓN CRÍTICA: Verificar el dominio PRIMERO (más confiable)
            # Si el dominio incluye available_old_equipment_ids o available_new_equipment_ids,
            # es DEFINITIVAMENTE desde el wizard de cambio de equipo
            try:
                domain_str = str(args)
                is_wizard_context = (
                    "available_old_equipment_ids" in domain_str or 
                    "available_new_equipment_ids" in domain_str
                )
            except Exception:
                is_wizard_context = False
            
            # Si no se detectó por dominio, verificar el contexto
            if not is_wizard_context:
                is_wizard_context = (
                    context.get('search_by_inventory_plate_only') or 
                    context.get('equipment_change_wizard') or
                    context.get('active_model') == 'subscription.equipment.change.wizard'
                )
            
            # Si el contexto indica que se busca por placa de inventario, buscar SOLO por inventory_plate
            # NO buscar por serial number ni por nombre de producto
            if is_wizard_context:
                # Construir el dominio de búsqueda SOLO con inventory_plate
                domain = list(args) if args else []
                
                if name:
                    # CRÍTICO: Buscar SOLO por placa de inventario (inventory_plate)
                    # NO buscar por 'name' (serial) ni por 'product_id.name'
                    # Usar 'ilike' para búsqueda parcial
                    search_domain = [
                        ('inventory_plate', 'ilike', name),
                    ]
                    # Combinar con los args existentes usando AND
                    if domain:
                        domain = ['&'] + search_domain + domain
                    else:
                        domain = search_domain
                
                # IMPORTANTE: Buscar directamente usando _search del modelo base de Odoo
                # Esto evita completamente el método _name_search de product_suppiles
                # que busca por serial y producto
                lot_ids = self.env['stock.lot']._search(domain, limit=limit, order=order or 'inventory_plate, name')
                
                # Convertir los IDs a tuplas (id, display_name) usando name_get
                # con el contexto del wizard para obtener solo la placa
                if lot_ids:
                    lots = self.env['stock.lot'].browse(lot_ids)
                    # Forzar el contexto del wizard para que name_get muestre solo la placa
                    wizard_context = {
                        'equipment_change_wizard': True,
                        'search_by_inventory_plate_only': True,
                        'active_model': 'subscription.equipment.change.wizard',
                    }
                    # Actualizar con el contexto existente
                    wizard_context.update(context)
                    result = lots.with_context(wizard_context).name_get()
                else:
                    result = []
                
                return result
            
            # Si no es desde el wizard, usar el método original del módulo product_suppiles
            # Asegurar que args sea una lista válida antes de pasarlo
            return super(StockLot, self)._name_search(name=name, args=args, operator=operator, limit=limit, order=order)
        except Exception as e:
            # Si hay algún error, intentar usar el método original como fallback
            _logger.error("Error en _name_search de stock.lot: %s", str(e))
            try:
                return super(StockLot, self)._name_search(name=name, args=args or [], operator=operator, limit=limit, order=order)
            except Exception:
                # Si incluso el fallback falla, retornar lista vacía
                _logger.error("Error crítico en _name_search, retornando lista vacía")
                return []

    def action_open_subscription_equipment_changes(self):
        """Abrir el wizard de cambios de equipo con el lote actual como equipo anterior."""
        self.ensure_one()
        
        # Buscar la suscripción relacionada con este lot a través de usage activo
        usage = self.env['subscription.subscription.usage'].search([
            ('lot_id', '=', self.id),
            ('date_end', '=', False),  # Solo usage activo
        ], limit=1, order='date_start desc')
        
        if not usage or not usage.subscription_id:
            raise UserError(_(
                'No se encontró una suscripción activa asociada a este equipo.\n'
                'El equipo debe estar en uso en una suscripción activa para realizar cambios.'
            ))
        
        subscription_id = usage.subscription_id.id
        
        # Abrir el wizard directamente con los valores por defecto
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cambio de Equipo'),
            'res_model': 'subscription.equipment.change.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_subscription_id': subscription_id,
                'default_old_equipment_inventory_plate_search': self.id,  # Prellenar con el lote actual
                'default_old_equipment_lot_id': self.id,  # Prellenar con el lote actual
                'equipment_change_wizard': True,
                'search_by_inventory_plate_only': True,
                'active_model': 'subscription.equipment.change.wizard',
            },
        }

