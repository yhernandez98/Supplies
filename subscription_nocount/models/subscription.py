import calendar
import datetime
import logging
import re
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_round
from odoo.tools.misc import format_date, formatLang, get_lang

_logger = logging.getLogger(__name__)


class SubscriptionSubscription(models.Model):
    _name = 'subscription.subscription'
    _description = 'Non accounting subscription'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Referencia', required=True, default=lambda self: _('Nueva suscripción'), tracking=True)
    partner_id = fields.Many2one('res.partner', string='Cliente', required=True, tracking=True)
    location_id = fields.Many2one('stock.location', string='Ubicación del cliente', tracking=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', required=True, default=lambda self: self.env.company.currency_id.id, tracking=True)
    line_ids = fields.One2many('subscription.subscription.line', 'subscription_id', string='Líneas')
    service_line_ids = fields.One2many(
        'subscription.subscription.line',
        'subscription_id',
        string='Líneas de servicio',
        domain=[('is_active', '=', True), ('display_in_lines', '=', True), ('component_item_type', '=', False)],
    )
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('active', 'Activa'),
        ('cancelled', 'Cancelada'),
    ], default='draft', tracking=True)
    start_date = fields.Date(string='Inicio', tracking=True)
    end_date = fields.Date(string='Fin', tracking=True)
    pricelist_id = fields.Many2one(
        'product.pricelist',
        string='Lista de precios',
        related='partner_id.property_product_pricelist',
        readonly=True,
        help='Lista de precios configurada para el cliente'
    )
    plan_id = fields.Many2one(
        'sale.subscription.plan',
        string='Plan recurrente',
        help='Plan recurrente que define la periodicidad de facturación. Al cambiar el plan, se actualizarán los precios según la lista de precios del cliente.',
        tracking=True,
        domain=[],
    )
    reference_year = fields.Integer(string='Año consulta', help='Para consultar o guardar el facturable de un mes concreto (ej. facturación mes vencido).')
    reference_month = fields.Integer(string='Mes consulta', help='Mes (1-12) para consultar o guardar el facturable.')
    monthly_amount = fields.Monetary(string='Total Mensual', compute='_compute_monthly_amount', store=True, currency_field='currency_id', digits=(16, 0))
    monthly_amount_usd = fields.Float(
        string='Total Mensual USD',
        compute='_compute_monthly_amount',
        store=True,
        digits=(16, 2),
        help='Suma de los costos en USD del facturable en vivo (licencias sin TRM del mes siguiente).',
    )
    monthly_amount_usd_display = fields.Char(
        string='Total Mensual USD',
        compute='_compute_monthly_amount_usd_display',
        help='Total Mensual USD con signo $ (solo visual).',
    )
    total_esperado = fields.Monetary(
        string='Total Esperado',
        compute='_compute_total_esperado_y_mes_anterior',
        store=False,
        currency_field='currency_id',
        digits=(16, 2),
        help='Total como si fueran los días completos del mes (cuánto esperas recibir en el mes).',
    )
    total_mes_anterior = fields.Monetary(
        string='Total Mes Anterior',
        compute='_compute_total_esperado_y_mes_anterior',
        store=False,
        currency_field='currency_id',
        digits=(16, 2),
        help='Total del facturable guardado del mes anterior (si existe).',
    )
    generate_accounting = fields.Boolean(string='Generar contabilidad', default=False, tracking=True)
    proforma_move_ids = fields.One2many('account.move', 'subscription_id', string='Proformas')
    usage_ids = fields.One2many('subscription.subscription.usage', 'subscription_id', string='Usos', copy=False)
    usage_active_count = fields.Integer(string='Activos', compute='_compute_usage_summary', readonly=True)
    # Campos temporales para evitar errores de validación - se eliminarán en _auto_init
    # Estos campos existen solo para que las vistas no fallen durante la actualización
    usage_closed_count = fields.Integer(
        compute='_compute_usage_summary_fake', 
        readonly=True, 
        store=False,
        string='Retirados (deprecated)',
        help='Campo deprecado - será eliminado'
    )
    equipment_change_count = fields.Integer(
        compute='_compute_equipment_change_count_fake', 
        readonly=True, 
        store=False,
        string='Número de Cambios (deprecated)',
        help='Campo deprecado - será eliminado'
    )
    equipment_change_history_ids = fields.One2many(
        'subscription.equipment.change.history',
        'subscription_id',
        string='Historial de Cambios de Equipo',
        copy=False,
        readonly=True,
    )
    proforma_sequence = fields.Integer(string='Consecutivo Proforma', default=0, readonly=True)
    component_quant_ids = fields.Many2many(
        'stock.quant',
        compute='_compute_location_classified_quants',
        string='Quants Componentes',
        compute_sudo=True,
        help='Quants en la ubicación del cliente clasificados como Componentes.',
    )
    peripheral_quant_ids = fields.Many2many(
        'stock.quant',
        compute='_compute_location_classified_quants',
        string='Quants Periféricos',
        compute_sudo=True,
        help='Quants en la ubicación del cliente clasificados como Periféricos.',
    )
    complement_quant_ids = fields.Many2many(
        'stock.quant',
        compute='_compute_location_classified_quants',
        string='Quants Complementos',
        compute_sudo=True,
        help='Quants en la ubicación del cliente clasificados como Complementos.',
    )
    other_quant_ids = fields.Many2many(
        'stock.quant',
        compute='_compute_location_classified_quants',
        string='Quants sin clasificación',
        compute_sudo=True,
        help='Quants en la ubicación del cliente sin clasificación específica.',
    )
    lot_date_override_ids = fields.One2many(
        'subscription.lot.date.override',
        'subscription_id',
        string='Ajustes de fechas por serial',
        help='Fechas de activación/finalización que se muestran en esta suscripción para seriales que ya salieron (sustituyen las del lote).',
    )
    grouped_product_ids = fields.One2many(
        'subscription.product.grouped',
        'subscription_id',
        string='Productos Agrupados',
        compute='_compute_grouped_products',
        store=False,
        help='Productos agrupados por cantidad de seriales.',
    )
    location_quant_ids = fields.Many2many(
        'stock.quant',
        compute='_compute_location_classified_quants',
        string='Quants en ubicación',
        compute_sudo=True,
        help='Todos los quants con inventario en la ubicación del cliente.',
    )
    component_line_ids = fields.One2many(
        'subscription.subscription.line',
        'subscription_id',
        string='Líneas Componentes',
        domain="[('component_item_type', '=', 'component')]",
    )
    peripheral_line_ids = fields.One2many(
        'subscription.subscription.line',
        'subscription_id',
        string='Líneas Periféricos',
        domain="[('component_item_type', '=', 'peripheral')]",
    )
    complement_line_ids = fields.One2many(
        'subscription.subscription.line',
        'subscription_id',
        string='Líneas Complementos',
        domain="[('component_item_type', '=', 'complement')]",
    )
    general_usage_ids = fields.One2many(
        'subscription.subscription.usage',
        'subscription_id',
        string='Usos generales',
        domain="[('component_item_type', '=', False)]",
        readonly=True,
    )

    @api.model
    def _build_subscription_name(self, partner, exclude_id=None):
        """Construye un nombre único para la suscripción con formato: Cliente + Número secuencial (001) + Fecha (DD/MM/AAAA).
        
        :param partner: Cliente (res.partner)
        :param exclude_id: ID de suscripción a excluir de la búsqueda (útil al editar)
        :return: Nombre único para la suscripción
        """
        partner = partner or self.env['res.partner']
        if not partner:
            return _('Nueva suscripción')
        
        # Obtener la fecha actual en formato DD/MM/AAAA
        today = fields.Date.today()
        date_str = today.strftime('%d/%m/%Y')
        
        # Buscar todas las suscripciones del cliente para determinar el siguiente número secuencial
        domain = [
            ('partner_id', '=', partner.id),
        ]
        if exclude_id:
            domain.append(('id', '!=', exclude_id))
        
        existing_subscriptions = self.search(domain)
        
        # Buscar el número más alto usado (formato: "Cliente 001 DD/MM/AAAA")
        max_number = 0
        partner_name = partner.display_name
        
        for sub in existing_subscriptions:
            name = sub.name
            # Buscar patrones como "Cliente 001 DD/MM/AAAA" o "Cliente 001"
            # El formato esperado es: "NOMBRE_CLIENTE NNN DD/MM/AAAA"
            # Patrón: nombre del cliente seguido de espacio, número de 3 dígitos, espacio opcional, fecha opcional
            pattern = r'^' + re.escape(partner_name) + r'\s+(\d{3})(?:\s+\d{2}/\d{2}/\d{4})?$'
            match = re.match(pattern, name)
            if match:
                try:
                    number = int(match.group(1))
                    max_number = max(max_number, number)
                except (ValueError, IndexError):
                    pass
        
        # Generar el siguiente número secuencial (001, 002, 003, etc.)
        next_number = max_number + 1
        sequence_str = str(next_number).zfill(3)  # Formato con 3 dígitos: 001, 002, etc.
        
        # Construir el nombre: "Cliente 001 DD/MM/AAAA"
        return _('%s %s %s') % (partner_name, sequence_str, date_str)

    def _get_proforma_title(self, sequence=None):
        self.ensure_one()
        seq = sequence or (self.proforma_sequence or 1)
        return _('Proforma %s - %s') % (str(seq).zfill(3), self.name)

    def _next_proforma_sequence(self):
        self.ensure_one()
        seq = (self.proforma_sequence or 0) + 1
        self.write({'proforma_sequence': seq})
        return seq

    @api.model
    def create(self, vals):
        partner_id = vals.get('partner_id')
        if partner_id and (not vals.get('name') or vals.get('name') == _('Nueva suscripción')):
            partner = self.env['res.partner'].browse(partner_id)
            vals['name'] = self._build_subscription_name(partner)
        return super().create(vals)
    
    @api.constrains('name', 'partner_id')
    def _check_unique_name_per_partner(self):
        """Valida que el nombre de la suscripción sea único por cliente."""
        for subscription in self:
            if subscription.name and subscription.partner_id:
                duplicate = self.search([
                    ('name', '=', subscription.name),
                    ('partner_id', '=', subscription.partner_id.id),
                    ('id', '!=', subscription.id),
                ], limit=1)
                if duplicate:
                    raise UserError(_(
                        'Ya existe una suscripción con el nombre "%s" para el cliente "%s". '
                        'Por favor, use un nombre diferente o el sistema generará uno único automáticamente.'
                    ) % (subscription.name, subscription.partner_id.display_name))

    def write(self, vals):
        need_update = 'partner_id' in vals and 'name' not in vals
        res = super().write(vals)
        if need_update:
            for subscription in self:
                if subscription.partner_id and (
                    not subscription.name
                    or subscription.name == _('Nueva suscripción')
                    or not self._is_name_in_new_format(subscription.name, subscription.partner_id)
                ):
                    subscription.name = self._build_subscription_name(
                        subscription.partner_id,
                        exclude_id=subscription.id
                    )
        return res

    def _is_name_in_new_format(self, name, partner):
        """Verifica si el nombre está en el nuevo formato: Cliente NNN DD/MM/AAAA"""
        if not name or not partner:
            return False
        partner_name = partner.display_name
        pattern = r'^' + re.escape(partner_name) + r'\s+\d{3}\s+\d{2}/\d{2}/\d{4}$'
        return bool(re.match(pattern, name))

    def _auto_init(self):
        """Eliminar columnas de campos eliminados si existen en la base de datos."""
        res = super()._auto_init()
        if self._auto:
            cr = self.env.cr
            table = 'subscription_subscription'
            # Verificar y eliminar usage_closed_count si existe
            cr.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = %s AND column_name = 'usage_closed_count'
            """, (table,))
            if cr.fetchone():
                try:
                    cr.execute('ALTER TABLE %s DROP COLUMN usage_closed_count' % table)
                    _logger.info('✅ Columna usage_closed_count eliminada de %s', table)
                except Exception as e:
                    _logger.warning('⚠️ Error eliminando columna usage_closed_count: %s', str(e))
            # Verificar y eliminar equipment_change_count si existe
            cr.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = %s AND column_name = 'equipment_change_count'
            """, (table,))
            if cr.fetchone():
                try:
                    cr.execute('ALTER TABLE %s DROP COLUMN equipment_change_count' % table)
                    _logger.info('✅ Columna equipment_change_count eliminada de %s', table)
                except Exception as e:
                    _logger.warning('⚠️ Error eliminando columna equipment_change_count: %s', str(e))
        return res

    @api.depends('line_ids', 'line_ids.subtotal_monthly', 'location_id', 'grouped_product_ids', 'grouped_product_ids.cost', 'grouped_product_ids.cost_currency_id', 'grouped_product_ids.quantity')
    def _compute_monthly_amount(self):
        """Calcula el total mensual sumando solo los costos en COP (facturable en vivo).
        Se excluyen costos en USD (ej. licencias sin TRM del mes siguiente) para no sumar dólares como pesos."""
        for subscription in self:
            try:
                grouped = subscription.grouped_product_ids
            except ValueError:
                grouped = self.env['subscription.product.grouped'].browse([])
            if grouped:
                sub_currency = subscription.currency_id
                total = sum(
                    g.cost for g in grouped
                    if g.cost_currency_id and g.cost_currency_id == sub_currency
                )
                # USD: suma "normal" por los que estén marcados como USD
                def _is_usd(currency):
                    if not currency:
                        return False
                    return (getattr(currency, 'name', '') or '').upper() == 'USD' or (getattr(currency, 'code', '') or '').upper() == 'USD'
                total_usd = sum(g.cost for g in grouped if g.cost_currency_id and _is_usd(g.cost_currency_id))
                subscription.monthly_amount_usd = total_usd
                _logger.debug('💰 Total mensual (solo COP) desde productos agrupados: %s; USD: %s', total, total_usd)
            else:
                total = sum(subscription.line_ids.mapped('subtotal_monthly'))
                subscription.monthly_amount_usd = 0.0
                _logger.debug('💰 Total mensual calculado desde líneas de suscripción: %s', total)
            subscription.monthly_amount = total

    @api.depends('monthly_amount_usd')
    def _compute_monthly_amount_usd_display(self):
        """Muestra Total Mensual USD con $ delante (sin usar Monetary)."""
        for rec in self:
            val = rec.monthly_amount_usd or 0.0
            rec.monthly_amount_usd_display = '$ %s' % formatLang(self.env, val, digits=2)

    @api.depends('grouped_product_ids', 'grouped_product_ids.product_id', 'grouped_product_ids.quantity', 'grouped_product_ids.proyectado')
    def _compute_total_esperado_y_mes_anterior(self):
        """Total esperado = suma de la columna Proyectado de Productos Agrupados. Total mes anterior = del facturable guardado."""
        for subscription in self:
            subscription.total_esperado = 0.0
            subscription.total_mes_anterior = 0.0
            try:
                grouped = subscription.grouped_product_ids
            except ValueError:
                grouped = self.env['subscription.product.grouped'].browse([])
            if grouped:
                subscription.total_esperado = sum(grouped.mapped('proyectado')) or 0.0
            # Total mes anterior: del facturable guardado del mes pasado
            try:
                today = fields.Date.today()
                if today.month == 1:
                    prev_year, prev_month = today.year - 1, 12
                else:
                    prev_year, prev_month = today.year, today.month - 1
                billable = self.env['subscription.monthly.billable'].search([
                    ('subscription_id', '=', subscription.id),
                    ('reference_year', '=', prev_year),
                    ('reference_month', '=', prev_month),
                ], limit=1)
                if billable:
                    subscription.total_mes_anterior = billable.total_amount or 0.0
            except Exception:
                pass

    @api.depends('location_id')
    def _compute_location_classified_quants(self):
        Quant = self.env['stock.quant'].sudo()
        for subscription in self:
            if not subscription.location_id:
                subscription.location_quant_ids = Quant.browse([])
                subscription.component_quant_ids = Quant.browse([])
                subscription.peripheral_quant_ids = Quant.browse([])
                subscription.complement_quant_ids = Quant.browse([])
                subscription.other_quant_ids = Quant.browse([])
                continue

            base_domain = [
                ('location_id', 'child_of', subscription.location_id.id),
                ('quantity', '>', 0),
            ]
            quants = Quant.search(base_domain)
            
            # Filtrar por suscripción: solo seriales asignados a esta suscripción
            filtered_quant_ids = []
            for quant in quants:
                lot = quant.lot_id
                # Si no tiene serial, excluirlo (solo mostrar seriales asignados)
                if not lot:
                    continue
                # Solo incluir si el serial está asignado a esta suscripción
                if lot.active_subscription_id and lot.active_subscription_id.id == subscription.id:
                    filtered_quant_ids.append(quant.id)
                # Si no tiene suscripción asignada o está asignado a otra, excluirlo
            
            # Convertir la lista de IDs de vuelta a un recordset
            if filtered_quant_ids:
                quants = Quant.browse(filtered_quant_ids)
            else:
                quants = Quant.browse([])  # Recordset vacío, no el modelo
            subscription.location_quant_ids = quants
            
            # Obtener los seriales principales asignados a esta suscripción
            principal_lot_ids = quants.filtered(lambda q: q.lot_id).mapped('lot_id').ids
            
            # Buscar componentes/periféricos/complementos asociados a los productos principales
            # a través de stock.lot.supply.line donde lot_id es el principal y related_lot_id es el componente
            SupplyLine = self.env['stock.lot.supply.line']
            associated_component_quant_ids = []
            associated_peripheral_quant_ids = []
            associated_complement_quant_ids = []
            
            if principal_lot_ids:
                # Buscar supply_lines donde el producto principal está en la suscripción
                supply_lines = SupplyLine.search([
                    ('lot_id', 'in', principal_lot_ids),
                    ('related_lot_id', '!=', False),
                ])
                
                for supply_line in supply_lines:
                    related_lot = supply_line.related_lot_id
                    if not related_lot:
                        continue
                    
                    # Obtener el quant del componente en la ubicación
                    component_quants = Quant.search([
                        ('location_id', 'child_of', subscription.location_id.id),
                        ('lot_id', '=', related_lot.id),
                        ('quantity', '>', 0),
                    ])
                    
                    # Usar el item_type de la supply_line para clasificar
                    item_type = supply_line.item_type or 'component'
                    
                    # Agregar los quants a la lista correspondiente según item_type
                    for quant in component_quants:
                        if item_type == 'component':
                            if quant.id not in associated_component_quant_ids:
                                associated_component_quant_ids.append(quant.id)
                        elif item_type == 'peripheral':
                            if quant.id not in associated_peripheral_quant_ids:
                                associated_peripheral_quant_ids.append(quant.id)
                        elif item_type == 'complement':
                            if quant.id not in associated_complement_quant_ids:
                                associated_complement_quant_ids.append(quant.id)
            
            # Crear recordsets con los componentes asociados (no incluir los principales en estas listas)
            subscription.component_quant_ids = Quant.browse(associated_component_quant_ids) if associated_component_quant_ids else Quant.browse([])
            subscription.peripheral_quant_ids = Quant.browse(associated_peripheral_quant_ids) if associated_peripheral_quant_ids else Quant.browse([])
            subscription.complement_quant_ids = Quant.browse(associated_complement_quant_ids) if associated_complement_quant_ids else Quant.browse([])
            subscription.other_quant_ids = quants.filtered(
                lambda q: q.product_id.product_tmpl_id.classification not in ('component', 'peripheral', 'complement') if hasattr(q.product_id.product_tmpl_id, 'classification') else True
            ) if quants else Quant.browse([])

    @api.depends('location_id', 'other_quant_ids', 'usage_ids', 'usage_ids.lot_id', 'reference_year', 'reference_month',
                 'partner_id', 'partner_id.property_product_pricelist', 'plan_id')
    def _compute_grouped_products(self):
        """Agrupa los quants sin clasificación por producto o servicio de suscripción.
        Los seriales con suscripción asignada se agrupan por servicio de suscripción.
        Los seriales sin suscripción se agrupan por producto físico.
        También incluye las licencias activas de la suscripción (si el módulo subscription_licenses está instalado)."""
        # Si no hay registros, retornar
        if not self:
            return
        
        GroupedModel = self.env['subscription.product.grouped'].sudo()
        empty_recordset = GroupedModel.browse([])
        
        # Filtrar solo registros que ya tienen ID (ya guardados en la base de datos)
        # Los registros nuevos (NewId) no pueden tener productos agrupados aún
        saved_subscriptions = self.filtered(lambda s: s.id and isinstance(s.id, int))
        
        # Para los registros nuevos, asignar recordset vacío
        new_subscriptions = self - saved_subscriptions
        for subscription in new_subscriptions:
            subscription.grouped_product_ids = empty_recordset
        
        # Procesar solo los registros guardados (si falla una suscripción, se deja vacío y se registra)
        for subscription in saved_subscriptions:
            subscription.grouped_product_ids = empty_recordset
            try:
                if not subscription.location_id:
                    continue

                # Obtener quants sin clasificación (ya filtrados por suscripción en _compute_location_quants)
                other_quants = subscription.other_quant_ids.filtered(lambda q: q.lot_id and q.quantity > 0)

                # Separar seriales con y sin suscripción asignada
                quants_with_subscription = []
                quants_without_subscription = []

                for quant in other_quants:
                    lot = quant.lot_id
                    if lot and lot.subscription_service_product_id:
                        # Serial con suscripción asignada
                        quants_with_subscription.append(quant)
                    else:
                        # Serial sin suscripción
                        quants_without_subscription.append(quant)

                # Agrupar seriales CON suscripción por servicio de suscripción
                subscription_services_dict = {}
                for quant in quants_with_subscription:
                    lot = quant.lot_id
                    service = lot.subscription_service_product_id
                    if service.id not in subscription_services_dict:
                        subscription_services_dict[service.id] = {
                            'service_id': service.id,
                            'quantity': 0,
                            'lot_ids': [],
                        }
                    subscription_services_dict[service.id]['quantity'] += 1
                    subscription_services_dict[service.id]['lot_ids'].append(lot.id)

                # Incluir también lotes que SALIERON en el mes (ya no están en ubicación).
                # Misma lógica que al guardar: si hay reference_year/reference_month los usamos;
                # si no (facturable en vivo), usamos año/mes actual EN ZONA HORARIA DEL USUARIO para que coincida con lo que vería al guardar.
                if subscription.reference_year and subscription.reference_month and 1 <= subscription.reference_month <= 12:
                    year = subscription.reference_year
                    month = subscription.reference_month
                    months_to_include = [(year, month)]
                else:
                    # Facturable en vivo: mismo criterio que do_save_monthly_billable pero con "hoy" en zona del usuario
                    year = self.env.context.get('reference_year')
                    month = self.env.context.get('reference_month')
                    if not (year and month and 1 <= month <= 12):
                        try:
                            # Fecha/hora actual en zona horaria del usuario (mismo criterio que al guardar)
                            now_utc = fields.Datetime.now()
                            now_user = fields.Datetime.context_timestamp(subscription, now_utc)
                            if now_user:
                                today_user = now_user.date() if hasattr(now_user, 'date') else now_user
                                year = today_user.year
                                month = today_user.month
                        except Exception:
                            today = fields.Date.today()
                            year = today.year if today else None
                            month = today.month if today else None
                    months_to_include = [(year, month)] if year and month else []
                if months_to_include:
                    Lot = self.env['stock.lot']
                    exited_lots = Lot.browse([])
                    for (y, m) in months_to_include:
                        if not (y and m and 1 <= m <= 12):
                            continue
                        days_in_month = calendar.monthrange(y, m)[1]
                        first_day = datetime.date(y, m, 1)
                        last_day = datetime.date(y, m, days_in_month)
                        # 1) Lotes que salieron en este mes y siguen con active_subscription_id = esta suscripción
                        exited_in_month = Lot.search([
                            ('active_subscription_id', '=', subscription.id),
                            ('subscription_service_product_id', '!=', False),
                            ('exit_date', '>=', first_day),
                            ('exit_date', '<=', last_day),
                        ])
                        exited_lots = (exited_lots | exited_in_month)
                    # Rango de fechas para fallbacks (2) y (3): todos los meses considerados
                    first_day = min(datetime.date(y, m, 1) for (y, m) in months_to_include if 1 <= m <= 12)
                    last_day = max(datetime.date(y, m, calendar.monthrange(y, m)[1]) for (y, m) in months_to_include if 1 <= m <= 12)
                    # 2) Fallback: lotes que salieron en el mes y aparecen en usage de esta suscripción
                    Usage = self.env['subscription.subscription.usage']
                    usage_recs = Usage.search([('subscription_id', '=', subscription.id)])
                    usage_lot_ids = usage_recs.mapped('lot_id').filtered(lambda l: l).ids
                    if usage_lot_ids:
                        exited_by_usage = Lot.search([
                            ('id', 'in', usage_lot_ids),
                            ('subscription_service_product_id', '!=', False),
                            ('exit_date', '>=', first_day),
                            ('exit_date', '<=', last_day),
                        ])
                        exited_lots = (exited_lots | exited_by_usage)
                    # 3) Fallback adicional: lotes con exit_date en el mes y servicio en líneas de esta suscripción
                    if not exited_lots:
                        service_product_ids = subscription.service_line_ids.mapped('product_id').ids if subscription.service_line_ids else []
                        if service_product_ids:
                            candidate = Lot.search([
                                ('subscription_service_product_id', 'in', service_product_ids),
                                ('exit_date', '>=', first_day),
                                ('exit_date', '<=', last_day),
                            ])
                            for lot in candidate:
                                if lot.active_subscription_id and lot.active_subscription_id.id == subscription.id:
                                    exited_lots |= lot
                                elif lot.id in usage_lot_ids:
                                    exited_lots |= lot
                    # 4) Fallback por movimientos: lotes que SALIERON de la ubicación del cliente este mes
                    if subscription.location_id:
                        loc_child_ids = self.env['stock.location'].search([
                            ('id', 'child_of', subscription.location_id.id),
                        ]).ids
                        if loc_child_ids:
                            last_day_end = datetime.datetime(year, month, calendar.monthrange(year, month)[1], 23, 59, 59)
                            first_day_start = datetime.datetime(year, month, 1, 0, 0, 0)
                            MoveLine = self.env['stock.move.line'].sudo()
                            move_lines = MoveLine.search([
                                ('location_id', 'in', loc_child_ids),
                                ('location_dest_id', 'not in', loc_child_ids),
                                ('lot_id', '!=', False),
                                ('move_id.state', '=', 'done'),
                                ('move_id.date', '>=', first_day_start),
                                ('move_id.date', '<=', last_day_end),
                            ])
                            moved_out_lot_ids = move_lines.mapped('lot_id').ids
                            if moved_out_lot_ids:
                                lots_moved_out = Lot.browse(moved_out_lot_ids).filtered(
                                    lambda l: l.subscription_service_product_id
                                )
                                exited_lots = (exited_lots | lots_moved_out)
                    for lot in exited_lots:
                        service = lot.subscription_service_product_id
                        if service.id not in subscription_services_dict:
                            subscription_services_dict[service.id] = {
                                'service_id': service.id,
                                'quantity': 0,
                                'lot_ids': [],
                            }
                        if lot.id not in subscription_services_dict[service.id]['lot_ids']:
                            subscription_services_dict[service.id]['lot_ids'].append(lot.id)
                            subscription_services_dict[service.id]['quantity'] += 1

                # Incluir lotes que salieron a otro cliente pero siguen visibles hasta el día 1 del mes siguiente
                today_sub = fields.Date.context_today(subscription)
                if hasattr(Lot, 'last_subscription_id') and hasattr(Lot, 'pending_removal_date'):
                    pending_lots = Lot.search([
                        ('last_subscription_id', '=', subscription.id),
                        ('pending_removal_date', '>', today_sub),
                    ])
                    for lot in pending_lots:
                        service = (lot.last_subscription_service_id if hasattr(lot, 'last_subscription_service_id') and lot.last_subscription_service_id
                                   else lot.subscription_service_product_id)
                        if not service:
                            continue
                        if service.id not in subscription_services_dict:
                            subscription_services_dict[service.id] = {
                                'service_id': service.id,
                                'quantity': 0,
                                'lot_ids': [],
                            }
                        if lot.id not in subscription_services_dict[service.id]['lot_ids']:
                            subscription_services_dict[service.id]['lot_ids'].append(lot.id)
                            subscription_services_dict[service.id]['quantity'] += 1

                # Agrupar seriales SIN suscripción por producto físico
                products_dict = {}
                for quant in quants_without_subscription:
                    product = quant.product_id
                    if product.id not in products_dict:
                        products_dict[product.id] = {
                            'product_id': product.id,
                            'quantity': 0,
                        }
                    products_dict[product.id]['quantity'] += 1  # Contar seriales

                # Limpiar registros anteriores de esta suscripción
                GroupedModel.search([('subscription_id', '=', subscription.id)]).unlink()

                # Inicializar lista de IDs para los registros agrupados
                grouped_record_ids = []

                # Crear una línea agrupada por servicio CON suscripción (lot_ids para prorrateo por fecha ingreso/salida)
                for service_id, data in subscription_services_dict.items():
                    record = GroupedModel.create({
                        'subscription_id': subscription.id,
                        'product_id': service_id,
                        'lot_id': False,
                        'lot_ids': [(6, 0, data['lot_ids'])],
                        'quantity': len(data['lot_ids']),
                        'has_subscription': True,
                        'subscription_service': service_id,
                        'location_id': subscription.location_id.id,
                        'is_license': False,
                    })
                    grouped_record_ids.append(record.id)

                # Crear líneas agrupadas para seriales SIN suscripción (agrupados por producto físico)
                for product_id, data in products_dict.items():
                    record = GroupedModel.create({
                        'subscription_id': subscription.id,
                        'product_id': data['product_id'],
                        'lot_id': False,  # No es un serial individual
                        'quantity': data['quantity'],
                        'has_subscription': False,
                        'subscription_service': False,
                        'location_id': subscription.location_id.id,
                        'is_license': False,
                    })
                    grouped_record_ids.append(record.id)

                # Agregar licencias activas de la suscripción (si el módulo subscription_licenses está instalado)
                # PRIORIDAD 1: Buscar desde license.assignment (modelo principal de asignación de licencias)
                if 'license.assignment' in self.env:
                    try:
                        # Buscar licencias activas que coincidan con partner_id y location_id de la suscripción
                        license_domain = [
                            ('partner_id', '=', subscription.partner_id.id),
                            ('state', '=', 'active'),
                        ]
                        if subscription.location_id:
                            license_domain.append(('location_id', '=', subscription.location_id.id))

                        active_licenses = self.env['license.assignment'].search(license_domain)
                        _logger.info('📋 Licencias encontradas desde license.assignment: %s (Partner: %s, Location: %s)',
                                     len(active_licenses), subscription.partner_id.name, subscription.location_id.name if subscription.location_id else 'Sin ubicación')

                        licenses_by_category = {}
                        for license_assignment in active_licenses:
                            if not license_assignment.license_id:
                                continue
                            license_category_name = 'Sin Categoría'
                            license_category_id = False
                            if license_assignment.license_id and license_assignment.license_id.name:
                                license_category_name = license_assignment.license_id.name.name
                                license_category_id = license_assignment.license_id.name.id
                            product_id = False
                            if license_assignment.license_id.product_id:
                                product_id = license_assignment.license_id.product_id.id
                            category_key = license_category_id or license_category_name
                            if category_key not in licenses_by_category:
                                licenses_by_category[category_key] = {
                                    'quantity': 0,
                                    'assignments': [],
                                    'category_name': license_category_name,
                                    'category_id': license_category_id,
                                }
                            licenses_by_category[category_key]['quantity'] += license_assignment.quantity
                            licenses_by_category[category_key]['assignments'].append(license_assignment)

                        for category_key, data in licenses_by_category.items():
                            product_id = False
                            if data['assignments'] and data['assignments'][0].license_id.product_id:
                                product_id = data['assignments'][0].license_id.product_id.id
                            record = GroupedModel.create({
                                'subscription_id': subscription.id,
                                'product_id': product_id,
                                'lot_id': False,
                                'quantity': data['quantity'],
                                'has_subscription': False,
                                'subscription_service': False,
                                'location_id': subscription.location_id.id if subscription.location_id else False,
                                'is_license': True,
                                'license_name': data['category_name'],
                                'license_category': data['category_name'],
                                'license_type_id': False,
                                'cost': 0.0,
                            })
                            grouped_record_ids.append(record.id)
                            _logger.info('✅ Licencia agrupada por categoría: %s (Cantidad total: %s, Asignaciones: %s)',
                                         data['category_name'], data['quantity'], len(data['assignments']))
                    except Exception as e:
                        _logger.error('❌ Error al incluir licencias desde license.assignment: %s', str(e), exc_info=True)

                # PRIORIDAD 2: Buscar desde subscription.license.assignment (si existe, para compatibilidad)
                if 'subscription.license.assignment' in self.env:
                    try:
                        if hasattr(subscription, 'license_ids'):
                            active_licenses = subscription.license_ids.filtered(lambda l: l.active)
                            _logger.info('📋 Licencias encontradas usando license_ids: %s', len(active_licenses))
                        else:
                            active_licenses = self.env['subscription.license.assignment'].search([
                                ('subscription_id', '=', subscription.id),
                                ('active', '=', True),
                            ])
                            _logger.info('📋 Licencias encontradas usando búsqueda directa: %s', len(active_licenses))

                        if not active_licenses:
                            _logger.debug('ℹ️ No hay licencias activas en subscription.license.assignment para la suscripción %s', subscription.id)
                        else:
                            for license in active_licenses:
                                _logger.info('🔍 Procesando licencia subscription.license.assignment: %s (Cantidad: %s, Costo: %s)',
                                             license.license_type_id.name if license.license_type_id else 'Sin nombre',
                                             license.quantity, license.amount_local)
                                product_id = False
                                if license.license_type_id:
                                    product = self.env['product.product'].search([
                                        ('type', '=', 'service'),
                                        ('name', 'ilike', license.license_type_id.name),
                                    ], limit=1)
                                    if product:
                                        product_id = product.id
                                record = GroupedModel.create({
                                    'subscription_id': subscription.id,
                                    'product_id': product_id,
                                    'lot_id': False,
                                    'quantity': license.quantity,
                                    'has_subscription': False,
                                    'subscription_service': False,
                                    'location_id': subscription.location_id.id if subscription.location_id else False,
                                    'is_license': True,
                                    'license_name': license.license_type_id.name if license.license_type_id else '',
                                    'license_type_id': license.license_type_id.id if license.license_type_id else False,
                                    'cost': license.amount_local or 0.0,
                                })
                                grouped_record_ids.append(record.id)
                                _logger.info('✅ Licencia subscription.license.assignment agregada: %s (ID: %s)',
                                             license.license_type_id.name if license.license_type_id else 'Sin nombre', record.id)
                    except Exception as e:
                        _logger.error('❌ Error al incluir licencias desde subscription.license.assignment: %s', str(e), exc_info=True)

                # Servicios de MESA DE SERVICIOS y ADMINISTRACION Y SEGURIDAD INFORMATICA desde la lista de precios del cliente
                _SERVICES_BL_NAMES = ('MESA DE SERVICIOS', 'ADMINISTRACION Y SEGURIDAD INFORMATICA')
                try:
                    pricelist = subscription.partner_id.property_product_pricelist if subscription.partner_id else False
                    if pricelist and 'product.business.line' in self.env:
                        names_upper = {n.strip().upper() for n in _SERVICES_BL_NAMES}
                        existing_product_ids = set(GroupedModel.browse(grouped_record_ids).mapped('product_id').ids) if grouped_record_ids else set()
                        products_to_add = self.env['product.product']
                        if 'sale.subscription.pricing' in self.env:
                            PricingModel = self.env['sale.subscription.pricing']
                            for pricing in PricingModel.search([('pricelist_id', '=', pricelist.id)]):
                                product = False
                                if getattr(pricing, 'product_id', None):
                                    product = pricing.product_id
                                elif getattr(pricing, 'product_tmpl_id', None):
                                    tmpl = pricing.product_tmpl_id
                                    product = (tmpl.product_variant_ids[:1] if getattr(tmpl, 'product_variant_ids', None) else self.env['product.product']) or False
                                elif getattr(pricing, 'product_template_id', None):
                                    tmpl = pricing.product_template_id
                                    product = (tmpl.product_variant_ids[:1] if getattr(tmpl, 'product_variant_ids', None) else self.env['product.product']) or False
                                if not product or product.id in existing_product_ids:
                                    continue
                                bl = getattr(product, 'business_line_id', None) or (getattr(product.product_tmpl_id, 'business_line_id', None) if product.product_tmpl_id else None)
                                if not bl or (bl.name or '').strip().upper() not in names_upper:
                                    continue
                                products_to_add |= product
                        if getattr(pricelist, 'item_ids', None):
                            for item in pricelist.item_ids:
                                product = False
                                if getattr(item, 'product_id', None):
                                    product = item.product_id
                                elif getattr(item, 'product_tmpl_id', None):
                                    variants = getattr(item.product_tmpl_id, 'product_variant_ids', None)
                                    product = variants[:1] if variants else False
                                if not product or product.id in existing_product_ids or product in products_to_add:
                                    continue
                                bl = getattr(product, 'business_line_id', None) or (getattr(product.product_tmpl_id, 'business_line_id', None) if product.product_tmpl_id else None)
                                if not bl or (bl.name or '').strip().upper() not in names_upper:
                                    continue
                                products_to_add |= product
                        for product in products_to_add:
                            if product.id in existing_product_ids:
                                continue
                            record = GroupedModel.create({
                                'subscription_id': subscription.id,
                                'product_id': product.id,
                                'lot_id': False,
                                'lot_ids': [(5, 0, 0)],
                                'quantity': 1,
                                'has_subscription': False,
                                'subscription_service': False,
                                'location_id': subscription.location_id.id if subscription.location_id else False,
                                'is_license': False,
                            })
                            grouped_record_ids.append(record.id)
                            existing_product_ids.add(product.id)
                            _logger.info('✅ Servicio (lista de precios) agregado a Facturable: %s', product.display_name)
                except Exception as e:
                    _logger.warning('⚠️ No se pudieron agregar servicios desde lista de precios: %s', str(e))

                # Asignar los registros agrupados ordenados alfabéticamente por línea de negocio
                if grouped_record_ids:
                    records = GroupedModel.browse(grouped_record_ids)
                    def _sort_key(r):
                        bl = (r.business_line_id.name if r.business_line_id else '') or (r.business_line_name or '')
                        return (
                            r.is_license,
                            not (r.has_subscription or False),
                            (bl or '').upper(),
                            r.product_id.id or 0,
                        )
                    sorted_records = records.sorted(key=_sort_key)
                    subscription.grouped_product_ids = GroupedModel.browse(sorted_records.ids)
                else:
                    subscription.grouped_product_ids = empty_recordset
            except Exception as e:
                _logger.warning(
                    'Error en _compute_grouped_products para suscripción %s (id=%s): %s. Se asigna recordset vacío.',
                    subscription.display_name or subscription.id, subscription.id, str(e),
                    exc_info=True
                )
                subscription.grouped_product_ids = empty_recordset

    @api.depends('line_ids', 'line_ids.component_item_type', 'line_ids.product_id', 'line_ids.location_id', 'location_id')
    def _compute_classified_lines(self):
        Location = self.env['stock.location']
        for subscription in self:
            component_lines = self.env['subscription.subscription.line']
            peripheral_lines = self.env['subscription.subscription.line']
            complement_lines = self.env['subscription.subscription.line']

            lines = subscription.line_ids
            if subscription.location_id:
                child_locations = Location.search([('id', 'child_of', subscription.location_id.id)])
                lines = lines.filtered(lambda l: not l.location_id or l.location_id in child_locations)

            for line in lines:
                classification = getattr(line.product_id.product_tmpl_id, 'classification', False)
                if not line.is_component_line and classification not in ('component', 'peripheral', 'complement'):
                    continue
                kind = line.component_item_type or classification
                if kind == 'component':
                    component_lines |= line
                elif kind == 'peripheral':
                    peripheral_lines |= line
                elif kind == 'complement':
                    complement_lines |= line

            subscription.component_line_ids = component_lines
            subscription.peripheral_line_ids = peripheral_lines
            subscription.complement_line_ids = complement_lines

    def _get_price_for_product(self, product, quantity=1.0):
        """Obtiene el precio de un producto. Usa el método mejorado que considera el plan recurrente."""
        self.ensure_one()
        # Usar el método mejorado que considera el plan recurrente si está configurado
        return self._get_price_for_product_with_plan(product, quantity, self.plan_id if self.plan_id else None)

    def _get_license_unit_price_cop(self, product, trm_rate):
        """Devuelve el precio unitario en COP para un producto de licencia, usando la TRM dada.
        Usado por el facturable guardado al aplicar TRM del mes."""
        self.ensure_one()
        if not product or trm_rate is None:
            return 0.0
        pricelist = self.pricelist_id or (self.partner_id.property_product_pricelist if self.partner_id else False)
        if not pricelist:
            return 0.0
        unit_price = self._get_price_for_product(product, 1.0) or 0.0
        if unit_price <= 0:
            return 0.0
        price_currency = None
        if 'sale.subscription.pricing' in self.env and self.plan_id:
            try:
                PricingModel = self.env['sale.subscription.pricing']
                pricing_domain = [
                    ('pricelist_id', '=', pricelist.id),
                    ('plan_id', '=', self.plan_id.id),
                ]
                if 'product_template_id' in PricingModel._fields:
                    pricing_domain.append(('product_template_id', '=', product.product_tmpl_id.id))
                    pricing_rec = PricingModel.search(pricing_domain, limit=1)
                elif 'product_tmpl_id' in PricingModel._fields:
                    pricing_domain.append(('product_tmpl_id', '=', product.product_tmpl_id.id))
                    pricing_rec = PricingModel.search(pricing_domain, limit=1)
                else:
                    pricing_rec = self.env['sale.subscription.pricing']
                if not pricing_rec and 'product_id' in PricingModel._fields:
                    pricing_domain = [
                        ('pricelist_id', '=', pricelist.id),
                        ('plan_id', '=', self.plan_id.id),
                        ('product_id', '=', product.id),
                    ]
                    pricing_rec = PricingModel.search(pricing_domain, limit=1)
                if pricing_rec and len(pricing_rec) > 0 and hasattr(pricing_rec[0], 'currency_id') and pricing_rec[0].currency_id:
                    price_currency = pricing_rec[0].currency_id
            except Exception:
                pass
        if not price_currency:
            price_currency = pricelist.currency_id
        if price_currency and price_currency.name == 'USD' and trm_rate and trm_rate > 0:
            return unit_price * trm_rate
        return unit_price

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        for subscription in self:
            if subscription.partner_id and subscription.partner_id.currency_id:
                subscription.currency_id = subscription.partner_id.currency_id.id
            if subscription.partner_id:
                if not subscription.name or subscription.name == _('Nueva suscripción') or not subscription._is_name_in_new_format(subscription.name, subscription.partner_id):
                    subscription.name = subscription._build_subscription_name(
                        subscription.partner_id,
                        exclude_id=subscription.id
                    )
                default_location = subscription.partner_id.property_stock_customer
                if default_location:
                    subscription.location_id = default_location
    

    @api.onchange('plan_id', 'pricelist_id')
    def _onchange_plan_pricelist(self):
        """Actualiza los precios de las líneas cuando cambia el plan recurrente o la lista de precios."""
        if not self.pricelist_id:
            return
        
        # Verificar si el modelo sale.subscription.plan existe
        if 'sale.subscription.plan' not in self.env:
            _logger.warning('El modelo sale.subscription.plan no está disponible')
            return
        
        # Actualizar precios de todas las líneas activas
        plan = self.plan_id if self.plan_id else None
        for line in self.line_ids.filtered(lambda l: l.is_active and l.product_id):
            # Buscar precio recurrente en la lista de precios para este producto y plan
            price = self._get_price_for_product_with_plan(line.product_id, line.quantity, plan)
            if price and price > 0:
                line.price_monthly = price
                plan_name = plan.name if plan else 'Sin plan'
                _logger.info('✅ Precio actualizado para línea %s: %s (Plan: %s)', line.product_id.display_name, price, plan_name)

    def _get_price_for_product_with_plan(self, product, quantity=1.0, plan=None):
        """Obtiene el precio de un producto considerando el plan recurrente y la lista de precios.
        
        Prioridad:
        1. Precio recurrente específico para el plan seleccionado
        2. Precio de reglas de precio estándar de la lista
        3. Precio de lista del producto
        """
        self.ensure_one()
        partner = self.partner_id
        pricelist = partner.property_product_pricelist if partner else False
        qty = quantity or 1.0
        
        if not pricelist:
            _logger.debug('No hay lista de precios para el cliente, usando precio de lista del producto')
            return product.lst_price
        
        # PRIORIDAD 1: Si hay plan recurrente, buscar precio recurrente específico en sale.subscription.pricing
        if plan:
            _logger.info('🔍 Buscando precio recurrente para producto %s con plan %s en pricelist %s', 
                        product.display_name, plan.name, pricelist.display_name)
            
            recurring_price = False
            
            # Buscar en sale.subscription.pricing (modelo estándar de Odoo para precios recurrentes)
            if 'sale.subscription.pricing' in self.env:
                try:
                    PricingModel = self.env['sale.subscription.pricing']
                    
                    # Verificar qué campos tiene el modelo
                    has_product_id = 'product_id' in PricingModel._fields
                    has_product_tmpl_id = 'product_template_id' in PricingModel._fields or 'product_tmpl_id' in PricingModel._fields
                    
                    # Obtener el nombre correcto del campo
                    product_tmpl_field = 'product_template_id' if 'product_template_id' in PricingModel._fields else 'product_tmpl_id'
                    
                    _logger.info('🔍 Campos disponibles en sale.subscription.pricing: product_id=%s, product_template_id=%s (campo: %s)', 
                               has_product_id, has_product_tmpl_id, product_tmpl_field)
                    
                    # Construir dominio base: pricelist y plan
                    domain_base = [
                        ('pricelist_id', '=', pricelist.id),
                        ('plan_id', '=', plan.id),
                    ]
                    
                    pricing_records = False
                    
                    # PRIORIDAD 1: Buscar por product_template_id (según las imágenes, este es el campo correcto)
                    if has_product_tmpl_id:
                        domain_template = domain_base + [(product_tmpl_field, '=', product.product_tmpl_id.id)]
                        pricing_records = PricingModel.search(domain_template, limit=1)
                        if pricing_records:
                            _logger.info('✅ Encontrado por %s: %s (producto: %s)', 
                                       product_tmpl_field, product.product_tmpl_id.id, product.display_name)
                    
                    # PRIORIDAD 2: Si no se encuentra, buscar por product_id
                    if not pricing_records and has_product_id:
                        domain_product = domain_base + [('product_id', '=', product.id)]
                        pricing_records = PricingModel.search(domain_product, limit=1)
                        if pricing_records:
                            _logger.info('✅ Encontrado por product_id: %s', product.id)
                    
                    # NO usar Estrategia 3 (precio global sin filtro) porque puede devolver precio de otro producto
                    # Si no se encuentra precio específico, se usará el precio estándar de la lista de precios
                    
                    if pricing_records:
                        # El campo de precio se llama 'price' según el tooltip
                        if hasattr(pricing_records[0], 'price'):
                            price_value = pricing_records[0].price
                            # IMPORTANTE: Si el precio es 0, también debemos retornarlo (no buscar en otros lugares)
                            if price_value is not None:
                                # Verificar si tiene moneda personalizada
                                pricing_currency = False
                                if hasattr(pricing_records[0], 'currency_id') and pricing_records[0].currency_id:
                                    pricing_currency = pricing_records[0].currency_id
                                
                                if price_value > 0:
                                    _logger.info('✅ Precio recurrente encontrado: %s %s para producto %s (ID: %s) con plan %s (ID: %s) y pricelist %s (ID: %s)', 
                                               price_value, pricing_currency.name if pricing_currency else 'N/A', product.display_name, product.id, plan.name, plan.id, pricelist.display_name, pricelist.id)
                                elif price_value == 0:
                                    _logger.info('✅ Precio recurrente encontrado: 0 %s para producto %s (ID: %s) - El costo será 0', 
                                               pricing_currency.name if pricing_currency else 'N/A', product.display_name, product.id)
                                
                                # Si el precio tiene moneda diferente a la de la pricelist, convertir
                                if pricing_currency and pricing_currency.id != pricelist.currency_id.id and price_value > 0:
                                    try:
                                        # Convertir el precio a la moneda de la pricelist
                                        converted_price = pricing_currency._convert(
                                            price_value, 
                                            pricelist.currency_id, 
                                            self.env.company, 
                                            fields.Date.today()
                                        )
                                        _logger.info('💰 Precio convertido: %s %s -> %s %s', 
                                                   price_value, pricing_currency.name, 
                                                   converted_price, pricelist.currency_id.name)
                                        return converted_price
                                    except Exception as e:
                                        _logger.warning('⚠️ Error convirtiendo moneda: %s, usando precio original', str(e))
                                        return price_value
                                
                                # Retornar el precio (incluso si es 0)
                                return price_value
                            else:
                                _logger.warning('⚠️ Precio recurrente encontrado pero es None')
                        else:
                            _logger.warning('⚠️ Campo "price" no existe en sale.subscription.pricing. Campos disponibles: %s', 
                                          list(pricing_records[0]._fields.keys()))
                    else:
                        _logger.info('⚠️ No se encontró registro en sale.subscription.pricing para producto %s (ID: %s), plan %s (ID: %s), pricelist %s (ID: %s)', 
                                   product.display_name, product.id, plan.name, plan.id, pricelist.display_name, pricelist.id)
                        # Log adicional: mostrar qué registros existen para debugging
                        all_pricing = PricingModel.search([('pricelist_id', '=', pricelist.id), ('plan_id', '=', plan.id)], limit=10)
                        if all_pricing:
                            _logger.info('📋 Registros encontrados en sale.subscription.pricing con mismo pricelist y plan: %s', 
                                       [(p.id, p.product_id.name if hasattr(p, 'product_id') and p.product_id else 'Sin producto', 
                                         p.product_tmpl_id.name if hasattr(p, 'product_tmpl_id') and p.product_tmpl_id else 'Sin plantilla') 
                                        for p in all_pricing])
                except Exception as e:
                    _logger.error('❌ Error buscando en sale.subscription.pricing: %s', str(e))
                    import traceback
                    _logger.error(traceback.format_exc())
            
            # Si no se encuentra en sale.subscription.pricing, buscar directamente en la pricelist
            # NOTA: Los precios recurrentes están en sale.subscription.pricing, no en pricelist.item_ids
            # Pero por si acaso, también buscamos en item_ids
            if not recurring_price:
                # Buscar en precios recurrentes de la pricelist (campo item_ids o similar)
                try:
                    # Intentar acceder a item_ids que contiene los precios recurrentes
                    if hasattr(pricelist, 'item_ids'):
                        recurring_items = pricelist.item_ids.filtered(
                            lambda item: (
                                (hasattr(item, 'product_id') and item.product_id and item.product_id.id == product.id) or
                                (hasattr(item, 'product_template_id') and item.product_template_id and item.product_template_id.id == product.product_tmpl_id.id) or
                                (hasattr(item, 'product_tmpl_id') and item.product_tmpl_id and item.product_tmpl_id.id == product.product_tmpl_id.id)
                            ) and hasattr(item, 'recurring_plan_id') and item.recurring_plan_id and item.recurring_plan_id.id == plan.id
                        )
                        if recurring_items:
                            for item in recurring_items:
                                # Buscar el campo de precio recurrente
                                for price_field in ['recurring_price', 'price', 'fixed_price']:
                                    if hasattr(item, price_field):
                                        price_value = getattr(item, price_field)
                                        if price_value and price_value > 0:
                                            _logger.info('✅ Precio recurrente encontrado en pricelist.item_ids.%s: %s para producto %s', 
                                                       price_field, price_value, product.display_name)
                                            return price_value
                except Exception as e:
                    _logger.debug('Error buscando en pricelist.item_ids: %s', str(e))
                
                # También buscar en otros campos One2many de precios recurrentes
                try:
                    pricelist_fields = pricelist._fields
                    for field_name, field in pricelist_fields.items():
                        if field.type == 'one2many' and ('recurring' in field_name.lower() or 'recurrence' in field_name.lower()):
                            try:
                                recurring_field = getattr(pricelist, field_name)
                                if recurring_field:
                                    recurring_items = recurring_field.filtered(
                                        lambda rp: (
                                            (hasattr(rp, 'product_id') and rp.product_id and rp.product_id.id == product.id) or
                                            (hasattr(rp, 'product_tmpl_id') and rp.product_tmpl_id and rp.product_tmpl_id.id == product.product_tmpl_id.id)
                                        ) and hasattr(rp, 'plan_id') and rp.plan_id and rp.plan_id.id == plan.id
                                    )
                                    if recurring_items:
                                        for price_field in ['price', 'recurring_price', 'fixed_price']:
                                            if hasattr(recurring_items[0], price_field):
                                                price_value = getattr(recurring_items[0], price_field)
                                                if price_value and price_value > 0:
                                                    _logger.info('✅ Precio recurrente encontrado en campo %s.%s: %s', 
                                                               field_name, price_field, price_value)
                                                    return price_value
                            except Exception as e:
                                _logger.debug('Error accediendo a campo %s: %s', field_name, str(e))
                                continue
                except Exception as e:
                    _logger.debug('Error buscando en campos One2many: %s', str(e))
            
            # Si se encontró un precio recurrente, ya se retornó arriba
            # Si llegamos aquí, no se encontró precio recurrente
            if not recurring_price:
                _logger.info('⚠️ No se encontró precio recurrente para producto %s con plan %s, usando precio estándar', 
                           product.display_name, plan.name)
        
        # PRIORIDAD 2: Usar el método estándar de la pricelist (busca en reglas de precio)
        price = pricelist._get_product_price(product, qty, partner=partner)
        if price and price > 0:
            _logger.debug('💰 Usando precio de reglas de precio: %s para producto %s', price, product.display_name)
            return price
        
        # PRIORIDAD 3: Usar precio de lista del producto
        _logger.debug('💰 Usando precio de lista del producto: %s', product.lst_price)
        return product.lst_price

    def _sync_subscription_lines(self, products, remove_missing=False, track_usage=False, sync_datetime=None):
        """Update or create lines based on provided products data."""
        self.ensure_one()
        sync_datetime = sync_datetime or fields.Datetime.now()
        line_model = self.env['subscription.subscription.line']
        main_lines = self.line_ids.filtered(lambda l: not l.is_component_line)
        def _line_key(line):
            return line.stock_product_id.id if line.stock_product_id else line.product_id.id

        existing_map = {_line_key(line): line for line in main_lines}
        processed = set()
        partner_active_keys = set()
        if self.partner_id:
            partner_active_lines = line_model.search([
                ('subscription_id.partner_id', '=', self.partner_id.id),
                ('subscription_id', '!=', self.id),
                ('subscription_id.state', '=', 'active'),
                ('is_active', '=', True),
                ('is_component_line', '=', False),
            ])
            for line in partner_active_lines:
                location = line.location_id or line.subscription_id.location_id
                partner_active_keys.add((
                    _line_key(line),
                    location.id if location else False,
                ))
        # IMPORTANTE: Agrupar por (stock_product.id, service_product.id) para que:
        # - Seriales del mismo producto físico con diferentes servicios creen líneas separadas
        # - Seriales del mismo producto físico con el mismo servicio se agrupen
        # Esto replica la lógica de _get_location_products
        products_by_key = {}
        for item in products:
            product = item.get('product')  # Este es el service_product
            stock_product = item.get('stock_product') or product
            if not product:
                continue
            # Usar (stock_product.id, service_product.id) como clave de agrupación
            grouping_key = (stock_product.id, product.id)
            if grouping_key not in products_by_key:
                products_by_key[grouping_key] = {
                    'product': product,  # service_product
                    'quantity': 0.0,
                    'lots': [],
                    'location': item.get('location') or self.location_id,
                    'stock_product': stock_product,  # producto físico
                }
            # Sumar cantidades
            products_by_key[grouping_key]['quantity'] += item.get('quantity', 1.0)
            # Agregar lotes
            if item.get('lots'):
                products_by_key[grouping_key]['lots'].extend(item.get('lots', []))
        
        # Procesar productos agrupados
        _logger.info('🔄 Procesando %s productos agrupados para suscripción %s', len(products_by_key), self.display_name)
        for grouping_key, grouped_item in products_by_key.items():
            product = grouped_item['product']  # service_product
            item_location = grouped_item['location']
            stock_product = grouped_item['stock_product']
            qty = grouped_item['quantity']
            lots = grouped_item['lots']
            product_id = product.id  # service_product.id para búsqueda de línea existente
            
            lot_ids = [lot.get('lot_id') for lot in lots if lot.get('lot_id')] if lots else []
            _logger.info('📦 Procesando: Stock=%s, Servicio=%s, Cantidad=%s, Seriales=%s', 
                        stock_product.display_name, product.display_name, qty, lot_ids)
            
            conflict_key = (stock_product.id, item_location.id if item_location else False)
            if conflict_key in partner_active_keys and stock_product.id not in existing_map:
                _logger.warning(
                    '⚠️ Producto %s (Stock: %s) omitido para la suscripción %s porque ya está asociado a otra suscripción activa del mismo cliente.',
                    product.display_name,
                    stock_product.display_name,
                    self.display_name,
                )
                continue
            
            # Usar el método que considera el plan recurrente si está configurado
            price = self._get_price_for_product_with_plan(product, qty, self.plan_id if self.plan_id else None)
            values = {
                'product_id': product.id,  # service_product
                'quantity': qty,
                'price_monthly': price,
                'is_active': True,
                'stock_product_id': stock_product.id if stock_product and stock_product != product else False,
                'display_in_lines': True,
                'is_component_line': False,
            }
            if item_location:
                values['location_id'] = item_location.id
            
            # Buscar línea existente por (stock_product_id, product_id) para mantener consistencia
            line = None
            for existing_line in main_lines:
                existing_stock = existing_line.stock_product_id.id if existing_line.stock_product_id else existing_line.product_id.id
                if (existing_stock == stock_product.id and 
                    existing_line.product_id.id == product_id and 
                    not existing_line.is_component_line):
                    line = existing_line
                    _logger.info('✅ Línea existente encontrada: ID=%s, Stock=%s, Servicio=%s', 
                               line.id, stock_product.display_name, product.display_name)
                    break
            
            if line:
                previous_qty = line.quantity
                values.setdefault('display_in_lines', True)
                _logger.info('✏️ Actualizando línea existente ID=%s: Cantidad %s → %s', line.id, previous_qty, qty)
                # Usar contexto para evitar cierre de registros durante la sincronización
                line.with_context(skip_usage_update=False).write(values)
                if track_usage:
                    line._update_usage(previous_qty, qty, sync_datetime, lot_quantities=lots if lots else None)
            else:
                values.update({
                    'subscription_id': self.id,
                    'product_id': product.id,
                    'is_active': True,
                    'stock_product_id': stock_product.id if stock_product and stock_product != product else False,
                    'display_in_lines': True,
                    'is_component_line': False,
                })
                _logger.info('🆕 Creando nueva línea: Stock=%s, Servicio=%s, Cantidad=%s, display_in_lines=True', 
                           stock_product.display_name, product.display_name, qty)
                new_line = line_model.create(values)
                if track_usage:
                    new_line._update_usage(0.0, qty, sync_datetime, lot_quantities=lots if lots else None)
                _logger.info('✅ Línea creada exitosamente: ID=%s', new_line.id)
            processed.add(product_id)  # product_id es el service_product
        if remove_missing:
            # Filtrar líneas que no están en processed (usando product_id que es el service_product)
            lines_to_remove = main_lines.filtered(lambda l: l.product_id.id not in processed)
            if lines_to_remove:
                if track_usage:
                    for line in lines_to_remove:
                        line._update_usage(line.quantity, 0.0, sync_datetime, lot_quantities=[])
                lines_to_remove.write({
                    'quantity': 0.0,
                    'is_active': False,
                })
    def _sync_component_lines(self, component_items, remove_missing=False, track_usage=False, sync_datetime=None):
        self.ensure_one()
        sync_datetime = sync_datetime or fields.Datetime.now()
        line_model = self.env['subscription.subscription.line']
        component_lines = self.line_ids.filtered('is_component_line')
        existing_map = {(line.product_id.id, line.component_item_type or 'component'): line for line in component_lines}
        if component_lines:
            component_lines.write({
                'display_in_lines': False,
                'price_monthly': 0.0,
            })
        processed = set()

        for item in component_items or []:
            product = item.get('product')
            if not product:
                continue
            qty = item.get('quantity', 0.0)
            template_classification = getattr(product.product_tmpl_id, 'classification', False)
            item_type = template_classification or item.get('component_type') or 'component'
            key = (product.id, item_type)
            values = {
                'product_id': product.id,
                'quantity': qty,
                'price_monthly': 0.0,
                'is_active': bool(qty),
                'display_in_lines': False,
                'is_component_line': True,
                'stock_product_id': product.id,
                'component_item_type': item_type,
            }
            if item.get('location'):
                values['location_id'] = item['location'].id
            line = existing_map.get(key)
            if line:
                prev_qty = line.quantity
                line.write(values)
            else:
                fallback = self.line_ids.filtered(lambda l: not l.is_component_line and l.product_id.id == product.id)
                if fallback:
                    line = fallback[0]
                    prev_qty = line.quantity
                    line.write(values)
                else:
                    values.update({
                        'subscription_id': self.id,
                        'display_in_lines': False,
                    })
                    line = line_model.create(values)
                    prev_qty = 0.0
            if not line.is_component_line:
                line.is_component_line = True
            if line.display_in_lines:
                line.display_in_lines = False
            if track_usage:
                lot_quantities = item.get('lots') or []
                line._update_usage(prev_qty, qty, sync_datetime, lot_quantities=lot_quantities)
            lots_info = item.get('lots') or []
            if lots_info:
                lot_data = lots_info[0]
                line.component_lot_id = lot_data.get('lot_id')
                in_date = lot_data.get('in_date')
                line.component_date_start = in_date
                if in_date:
                    delta = sync_datetime - fields.Datetime.to_datetime(in_date)
                    line.component_days_active = max(delta.days + 1, 1)
                    daily_rate = float_round((line.price_monthly or 0.0) / 30, precision_digits=2)
                    line.component_daily_rate = daily_rate
                    line.component_amount = float_round(daily_rate * line.component_days_active * (line.quantity or 1.0), precision_digits=2)
                else:
                    line.component_days_active = 0
                    line.component_daily_rate = 0.0
                    line.component_amount = 0.0
            else:
                line.component_lot_id = False
                line.component_date_start = False
                line.component_date_end = False
                line.component_days_active = 0
                line.component_daily_rate = 0.0
                line.component_amount = 0.0
            processed.add((line.product_id.id, line.component_item_type or item_type))

        if remove_missing:
            to_remove = component_lines.filtered(lambda l: (l.product_id.id, l.component_item_type or 'component') not in processed)
            if to_remove:
                if track_usage:
                    for line in to_remove:
                        line._update_usage(line.quantity, 0.0, sync_datetime, lot_quantities=[])
                to_remove.write({
                    'quantity': 0.0,
                    'is_active': False,
                })

    def _get_location_products(self):
        self.ensure_one()
        result = {
            'main_products': [],
            'component_items': [],
        }
        if not self.location_id:
            return result

        Quant = self.env['stock.quant']
        SuppliesComposite = self.env['product.composite.line']
        SuppliesPeripheral = self.env['product.peripheral.line']
        SuppliesComplement = self.env['product.complement.line']

        related_product_ids = set()
        related_product_ids.update(SuppliesComposite.search([]).mapped('component_product_id').ids)
        related_product_ids.update(SuppliesPeripheral.search([]).mapped('peripheral_product_id').ids)
        related_product_ids.update(SuppliesComplement.search([]).mapped('complement_product_id').ids)

        # Filtrar quants: solo incluir seriales asignados a esta suscripción
        quant_domain = [
            ('location_id', 'child_of', self.location_id.id),
            ('quantity', '>', 0),
        ]
        quants = Quant.search(quant_domain)
        
        # Filtrar por suscripción: solo seriales asignados a esta suscripción
        filtered_quants = []
        for quant in quants:
            lot = quant.lot_id
            # Si no tiene serial, excluirlo (solo mostrar seriales asignados)
            if not lot:
                continue
            # Solo incluir si el serial está asignado a esta suscripción
            if lot.active_subscription_id and lot.active_subscription_id.id == self.id:
                filtered_quants.append(quant)
            # Si no tiene suscripción asignada o está asignado a otra, excluirlo
        
        quants = filtered_quants
        product_data = {}
        component_data = {}
        for quant in quants:
            product = quant.product_id
            classification = product.product_tmpl_id.classification if hasattr(product.product_tmpl_id, "classification") else False
            lot = quant.lot_id
            
            # Determinar si es componente/periférico/complemento
            is_component = (
                classification in ("component", "peripheral", "complement") or 
                product.id in related_product_ids or
                (lot and lot.principal_lot_id)
            )
            
            # Si es componente, agregarlo a component_data
            if is_component:
                item_type = classification or 'component'
                comp_entry = component_data.setdefault((product.id, item_type), {
                    'product': product,
                    'location': self.location_id,
                    'untracked_quantity': 0.0,
                    'lots_map': {},
                    'component_type': item_type,
                })
                if lot:
                    lot_key = lot.id
                    lot_info = comp_entry['lots_map'].setdefault(lot_key, {
                        'lot_id': lot.id,
                        'quantity': 0.0,
                        'in_date': False,
                    })
                    lot_info['quantity'] += quant.quantity
                    entry_date = self._get_lot_entry_date(
                        lot,
                        self.location_id,
                        product=product,
                        default_dt=(quant.in_date or quant.write_date or quant.create_date),
                    )
                    lot_info['in_date'] = fields.Datetime.to_string(entry_date) if entry_date else lot_info['in_date']
                else:
                    comp_entry['untracked_quantity'] += quant.quantity
                continue
            
            # Si no es componente, agregarlo a product_data
            # Usar el servicio del lote si existe, sino usar el producto directamente
            if lot:
                # Verificar si el lote tiene servicio asignado
                lot_service = lot.subscription_service_product_id
                if lot_service:
                    service_product = lot_service
                    _logger.info('✅ Serial %s (Producto físico: %s) → Servicio: %s', lot.name, product.display_name, service_product.display_name)
                    # Logging especial para serial 1515
                    if lot.name == '1515':
                        _logger.info('🔍 SERIAL 1515 DETECTADO: Producto físico=%s, Servicio=%s, Ubicación=%s', 
                                   product.display_name, service_product.display_name, self.location_id.display_name)
                else:
                    service_product = product
                    _logger.info('⚠️ Serial %s (Producto: %s) NO tiene servicio asignado, usando producto físico como servicio', lot.name, product.display_name)
                    # Logging especial para serial 1515
                    if lot.name == '1515':
                        _logger.warning('⚠️ SERIAL 1515 SIN SERVICIO: Usando producto físico como servicio')
            else:
                service_product = product
                _logger.info('⚠️ Quant sin serial (Producto: %s), usando producto físico como servicio', product.display_name)
            
            # IMPORTANTE: Agrupar por (stock_product.id, service_product.id) para que:
            # - Seriales del mismo producto físico con diferentes servicios creen líneas separadas
            # - Seriales del mismo producto físico con el mismo servicio se agrupen
            # Esto es similar a como funcionaba antes, pero ahora el servicio viene del serial
            service_key = (product.id, service_product.id)
            data = product_data.setdefault(service_key, {
                'service_product': service_product,
                'stock_product': product,
                'quantity': 0.0,
                'location': self.location_id,
                'lots': [],
                'untracked_quantity': 0.0,
            })
            data['quantity'] += quant.quantity
            if lot:
                entry_date = self._get_lot_entry_date(
                    lot,
                    self.location_id,
                    product=product,
                    default_dt=(quant.in_date or quant.write_date or quant.create_date),
                )
                data['lots'].append({
                    'lot_id': lot.id,
                    'quantity': quant.quantity,
                    'in_date': fields.Datetime.to_string(entry_date) if entry_date else False,
                })
                for supply_line in lot.lot_supply_line_ids:
                    comp = supply_line.product_id
                    item_type = supply_line.item_type or 'component'
                    comp_entry = component_data.setdefault((comp.id, item_type), {
                        'product': comp,
                        'location': self.location_id,
                        'untracked_quantity': 0.0,
                        'lots_map': {},
                        'component_type': item_type,
                    })
                    qty = (supply_line.quantity or 0.0) * (quant.quantity or 1.0)
                    lot_key = supply_line.related_lot_id.id if supply_line.related_lot_id else False
                    if lot_key:
                        # Si tiene lote relacionado, agregarlo a lots_map
                        lot_info = comp_entry['lots_map'].setdefault(lot_key, {
                            'lot_id': supply_line.related_lot_id.id,
                            'quantity': 0.0,
                            'in_date': False,
                        })
                        lot_info['quantity'] += qty
                        entry_comp = self._get_lot_entry_date(
                            supply_line.related_lot_id,
                            self.location_id,
                            product=comp,
                            default_dt=fields.Datetime.now(),
                        )
                        lot_info['in_date'] = fields.Datetime.to_string(entry_comp) if entry_comp else lot_info['in_date']
                    else:
                        # Si no tiene lote relacionado, agregarlo a untracked_quantity
                        comp_entry['untracked_quantity'] += qty
            else:
                data['untracked_quantity'] += quant.quantity

        component_product_ids = set(pid for pid, _type in component_data.keys())

        for service_key, info in product_data.items():
            stock_product = info['stock_product']
            service_product = info['service_product']
            
            if not info['quantity']:
                _logger.warning('⚠️ Producto %s (servicio: %s) tiene cantidad 0, omitiendo', stock_product.display_name, service_product.display_name)
                continue
            
            if stock_product.id in component_product_ids:
                _logger.warning('⚠️ Producto %s está en component_product_ids, omitiendo de main_products', stock_product.display_name)
                continue
            
            lots = info['lots'] or None
            value = {
                'product': service_product,
                'quantity': info['quantity'],
                'location': info['location'],
                'stock_product': stock_product,
            }
            if lots:
                value['lots'] = lots
                lot_names = [lot.get('lot_id') for lot in lots if lot.get('lot_id')]
                _logger.info('✅ Agregando a main_products: Stock=%s, Servicio=%s, Cantidad=%s, Seriales=%s', 
                           stock_product.display_name, service_product.display_name, info['quantity'], lot_names)
            else:
                _logger.info('✅ Agregando a main_products: Stock=%s, Servicio=%s, Cantidad=%s (sin seriales)', 
                           stock_product.display_name, service_product.display_name, info['quantity'])
            result['main_products'].append(value)

        for (prod_id, item_type), entry in component_data.items():
            lots = []
            total_qty = entry.get('untracked_quantity', 0.0)
            for lot_info in entry['lots_map'].values():
                if lot_info['lot_id']:
                    lots.append({
                        'lot_id': lot_info['lot_id'],
                        'quantity': lot_info['quantity'],
                        'in_date': lot_info['in_date'],
                    })
                    total_qty += lot_info['quantity']
            
            # skip if quantity zero
            if not total_qty:
                continue
                
            result['component_items'].append({
                'product': entry['product'],
                'quantity': total_qty,
                'location': entry['location'],
                'lots': lots if lots else None,
                'component_type': entry.get('component_type') or item_type,
            })

        return result

    def _normalize_component_lines(self, component_items):
        """Ensure existing lines for component products are hidden and marked appropriately."""
        self.ensure_one()
        component_keys = {}
        for item in component_items or []:
            product = item.get('product')
            component_type = item.get('component_type') or 'component'
            if product:
                component_keys[product.id] = component_type
        extra_lines = self.line_ids.filtered(lambda l: not l.is_component_line and (
            (l.product_id and l.product_id.product_tmpl_id and
             getattr(l.product_id.product_tmpl_id, 'classification', False) in ('component', 'peripheral', 'complement'))
            or (l.product_id and l.product_id.id in component_keys)
        ))
        if extra_lines:
            for line in extra_lines:
                updates = {
                    'display_in_lines': False,
                    'is_component_line': True,
                    'price_monthly': 0.0,
                }
                tmpl_class = getattr(line.product_id.product_tmpl_id, 'classification', False) if line.product_id else False
                if tmpl_class in ('component', 'peripheral', 'complement'):
                    updates['component_item_type'] = tmpl_class
                elif line.component_item_type:
                    updates['component_item_type'] = line.component_item_type
                elif line.product_id and line.product_id.id in component_keys:
                    updates['component_item_type'] = component_keys[line.product_id.id]
                else:
                    updates['component_item_type'] = 'component'
                line.write(updates)

    def _get_lot_entry_date(self, lot, location, product=None, default_dt=None):
        MoveLine = self.env['stock.move.line'].sudo()
        domain = [
            ('state', '=', 'done'),
            ('lot_id', '=', lot.id),
            ('product_id', '=', (product.id if product else lot.product_id.id)),
            ('qty_done', '>', 0),
        ]
        child_ids = set()
        if location:
            child_ids = set(self.env['stock.location'].sudo().search([('id', 'child_of', location.id)]).ids)
            domain.append(('location_dest_id', 'in', list(child_ids)))
        candidates = MoveLine.search(domain, order='date desc', limit=10)
        for move_line in candidates:
            if location and move_line.location_id.id in child_ids:
                continue
            return move_line.date or move_line.write_date or move_line.create_date
        return default_dt

    def _assign_lots_to_subscription(self, main_products, component_items):
        """Asigna automáticamente los seriales a esta suscripción cuando se sincronizan."""
        self.ensure_one()
        Lot = self.env['stock.lot']
        lot_ids_to_assign = set()
        
        # Recopilar todos los lot_ids de productos principales
        for item in main_products:
            lots = item.get('lots', [])
            for lot_data in lots:
                if isinstance(lot_data, dict):
                    lot_id = lot_data.get('lot_id')
                else:
                    lot_id = lot_data[0] if lot_data else None
                if lot_id:
                    if hasattr(lot_id, 'id'):
                        lot_id = lot_id.id
                    elif isinstance(lot_id, int):
                        pass  # Ya es un ID
                    else:
                        continue
                    lot_ids_to_assign.add(lot_id)
        
        # Recopilar todos los lot_ids de componentes/periféricos/complementos
        # En component_items, los lots están en 'lots_map' con estructura {'lot_id': id, ...}
        for item in component_items:
            lots_map = item.get('lots_map', {})
            for lot_key, lot_info in lots_map.items():
                if isinstance(lot_info, dict):
                    lot_id = lot_info.get('lot_id')
                else:
                    lot_id = lot_key
                if lot_id:
                    if hasattr(lot_id, 'id'):
                        lot_id = lot_id.id
                    elif isinstance(lot_id, int):
                        pass  # Ya es un ID
                    else:
                        continue
                    lot_ids_to_assign.add(lot_id)
        
        # Asignar todos los seriales a esta suscripción
        if lot_ids_to_assign:
            lots_to_assign = Lot.browse(list(lot_ids_to_assign))
            # Solo asignar seriales que no tienen suscripción o que ya están asignados a esta
            lots_to_update = lots_to_assign.filtered(
                lambda l: not l.active_subscription_id or l.active_subscription_id.id == self.id
            )
            if lots_to_update:
                lots_to_update.write({'active_subscription_id': self.id})
                _logger.info('✅ Asignados %s seriales a la suscripción %s', len(lots_to_update), self.display_name)

    def action_sync_from_location(self):
        for subscription in self:
            if subscription.state == 'cancelled':
                raise UserError(_('No puede sincronizar una suscripción cancelada.'))
            if not subscription.location_id:
                raise UserError(_('Debe establecer una ubicación para sincronizar productos.'))
            products_info = subscription._get_location_products()
            main_products = products_info.get('main_products', [])
            component_items = products_info.get('component_items', [])
            subscription._normalize_component_lines(component_items)
            sync_dt = fields.Datetime.now()
            
            # Asignar automáticamente los seriales a esta suscripción
            subscription._assign_lots_to_subscription(main_products, component_items)
            
            subscription._sync_subscription_lines(
                main_products,
                remove_missing=False,
                track_usage=True,
                sync_datetime=sync_dt
            )
            subscription._sync_component_lines(
                component_items,
                remove_missing=False,
                track_usage=True,
                sync_datetime=sync_dt,
            )
            # Corregir líneas existentes que deberían estar ocultas
            subscription._fix_existing_lines_visibility()
            # Consolidar líneas duplicadas por producto (por si acaso quedan duplicados de sincronizaciones anteriores)
            subscription._consolidate_duplicate_lines()
            subscription.message_post(
                body=_('Productos actualizados desde la ubicación %s.') % (subscription.location_id.display_name or ''),
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )

    @api.model
    def cron_sync_from_locations(self):
        subscriptions = self.search([
            ('state', 'in', ['draft', 'active']),
            ('location_id', '!=', False),
        ])
        for subscription in subscriptions:
            try:
                subscription.with_context(from_cron=True).action_sync_from_location()
            except UserError as err:
                _logger.info('Suscripción %s omitida durante la sincronización automática: %s', subscription.display_name, err)
            except Exception as exc:
                _logger.exception('Error al sincronizar suscripción %s: %s', subscription.display_name, exc)

    @api.model
    def cron_sync_last_day_of_month(self):
        """Último día del mes: actualizar productos (mismo efecto que botón Actualizar Productos)."""
        today = fields.Date.context_today(self)
        last_day = calendar.monthrange(today.year, today.month)[1]
        if today.day != last_day:
            return
        _logger.info('Cron: último día del mes, sincronizando productos de todas las suscripciones.')
        self.cron_sync_from_locations()

    @api.model
    def cron_save_monthly_billable_all(self):
        """Último día del mes: guardar facturable del mes en curso para cada suscripción activa."""
        today = fields.Date.context_today(self)
        last_day = calendar.monthrange(today.year, today.month)[1]
        if today.day != last_day:
            return
        year, month = today.year, today.month
        subscriptions = self.search([
            ('state', '=', 'active'),
            ('location_id', '!=', False),
        ])
        _logger.info('Cron: último día del mes, guardando facturable %s-%s para %s suscripciones.', year, month, len(subscriptions))
        for subscription in subscriptions:
            try:
                subscription.do_save_monthly_billable(year, month)
            except UserError as err:
                _logger.info('Suscripción %s omitida al guardar facturable: %s', subscription.display_name, err)
            except Exception as exc:
                _logger.exception('Error al guardar facturable para %s: %s', subscription.display_name, exc)

    @api.model
    def cron_sync_first_day_of_month(self):
        """Día 1 del mes: actualizar productos para que el facturable en vivo refleje la ubicación del cliente.
        Además: limpiar en lotes los last_subscription_id / pending_removal_date / last_subscription_service_id
        cuya pending_removal_date ya llegó, para que dejen de mostrarse en la suscripción."""
        today = fields.Date.context_today(self)
        if today.day != 1:
            return
        _logger.info('Cron: día 1, sincronizando productos (facturable en vivo).')
        self.cron_sync_from_locations()
        # Quitar de los seriales la “baja pendiente”: ya es día 1, el registro no debe seguir en la suscripción
        Lot = self.env['stock.lot'].sudo()
        if hasattr(Lot, 'pending_removal_date'):
            to_clear = Lot.search([('pending_removal_date', '<=', today)])
            if to_clear:
                clear_vals = {
                    'last_subscription_id': False,
                    'last_subscription_service_id': False,
                    'pending_removal_date': False,
                }
                if hasattr(Lot, 'last_exit_date_display'):
                    clear_vals['last_exit_date_display'] = False
                if hasattr(Lot, 'last_entry_date_display'):
                    clear_vals['last_entry_date_display'] = False
                if hasattr(Lot, 'last_subscription_entry_date'):
                    clear_vals['last_subscription_entry_date'] = False
                if hasattr(Lot, 'last_subscription_exit_date'):
                    clear_vals['last_subscription_exit_date'] = False
                to_clear.write(clear_vals)
                _logger.info('Cron día 1: limpiados last_subscription / pending_removal en %s lote(s).', len(to_clear))

    @api.model
    def cron_apply_trm_saved_billables(self):
        """Día 7 del mes: aplicar TRM del mes a facturar a cada facturable guardado del mes anterior."""
        today = fields.Date.context_today(self)
        if today.day != 7:
            return
        prev = today - relativedelta(months=1)
        year, month = prev.year, prev.month
        Billable = self.env['subscription.monthly.billable']
        billables = Billable.search([
            ('reference_year', '=', year),
            ('reference_month', '=', month),
        ])
        _logger.info('Cron: día 7, aplicando TRM a %s facturables guardados (%s-%s).', len(billables), year, month)
        for billable in billables:
            try:
                billable.action_apply_trm()
            except UserError as err:
                _logger.info('Facturable %s omitido al aplicar TRM: %s', billable.display_name, err)
            except Exception as exc:
                _logger.exception('Error al aplicar TRM en %s: %s', billable.display_name, exc)

    @api.model
    def cron_generate_proformas_from_saved(self):
        """Día 7 del mes: generar proformas a partir del facturable guardado del mes anterior."""
        today = fields.Date.context_today(self)
        if today.day != 7:
            return
        prev = today - relativedelta(months=1)
        year, month = prev.year, prev.month
        Billable = self.env['subscription.monthly.billable']
        billables = Billable.search([
            ('reference_year', '=', year),
            ('reference_month', '=', month),
        ])
        _logger.info('Cron: día 7, generando proformas desde facturable guardado para %s suscripciones.', len(billables))
        Move = self.env['account.move']
        month_end = prev.replace(day=calendar.monthrange(prev.year, prev.month)[1])
        month_start = prev.replace(day=1)
        for billable in billables:
            sub = billable.subscription_id
            if sub.state != 'active':
                continue
            # Reemplazar proforma existente del mes: borrar las en borrador de este mes y crear la nueva
            existing = Move.search([
                ('subscription_id', '=', sub.id),
                ('x_is_proforma', '=', True),
                ('invoice_date', '>=', month_start),
                ('invoice_date', '<=', month_end),
            ])
            draft = existing.filtered(lambda m: m.state == 'draft')
            if draft:
                draft.unlink()
                _logger.info('Suscripción %s: proforma(s) en borrador de %s-%s eliminada(s); se crea la nueva.', sub.display_name, year, month)
            try:
                sub._create_proforma_move_from_billable(billable)
            except UserError as err:
                _logger.info('Suscripción %s omitida al generar proforma: %s', sub.display_name, err)
            except Exception as exc:
                _logger.exception('Error al generar proforma para %s: %s', sub.display_name, exc)

    @api.model
    def ensure_subscription(self, partner, location=False, products=None, remove_missing=False, track_usage=False):
        """Find or create a subscription for a partner/location and sync lines.

        :param partner: recordset res.partner (mandatory)
        :param location: recordset stock.location (optional)
        :param products: iterable of dicts {'product': product.product, 'quantity': float,
                           'price': float (optional), 'location': stock.location (optional)}
        :param remove_missing: if True, lines not present in products will be removed.
        :param track_usage: if True, actualizará registros de uso al sincronizar.
        :return: subscription.subscription record
        """
        if not partner:
            raise UserError(_('Debe indicar un cliente para crear la suscripción.'))
        domain = [
            ('partner_id', '=', partner.id),
        ]
        if location:
            domain.append(('location_id', '=', location.id))
        subscription = self.search(domain, limit=1)
        if not subscription:
            name = partner.display_name
            if location:
                name = '%s - %s' % (partner.display_name, location.display_name)
            subscription = self.create({
                'name': name,
                'partner_id': partner.id,
                'location_id': location.id if location else False,
                'currency_id': partner.currency_id.id or self.env.company.currency_id.id,
                'state': 'draft',
            })
        elif location and subscription.location_id != location:
            subscription.location_id = location.id
        component_items = []
        if products is None and location:
            products_info = subscription._get_location_products()
            products = products_info.get('main_products', [])
            component_items = products_info.get('component_items', [])
            subscription._normalize_component_lines(component_items)
            remove_missing = True
            track_usage = True
        if products:
            subscription._sync_subscription_lines(products, remove_missing=remove_missing, track_usage=track_usage)
        if component_items:
            subscription._sync_component_lines(component_items, remove_missing=remove_missing, track_usage=track_usage)
        return subscription


    def action_activate(self):
        for subscription in self:
            if subscription.state != 'draft':
                raise UserError(_('Solo puede activar suscripciones en borrador.'))
            if not subscription.plan_id:
                raise UserError(_('Debe seleccionar el Plan recurrente antes de activar la suscripción.'))
            # Permitir activar sin productos asignados; se pueden agregar después.
            subscription.state = 'active'

    def action_cancel(self):
        for subscription in self:
            if subscription.state not in ('draft', 'active'):
                raise UserError(_('Solo puede cancelar suscripciones en borrador o activas.'))
            subscription.state = 'cancelled'

    def action_open_cancel_wizard(self):
        """Abre el asistente de cancelación con advertencia."""
        self.ensure_one()
        if self.state not in ('draft', 'active'):
            raise UserError(_('Solo puede cancelar suscripciones en borrador o activas.'))
        wizard = self.env['subscription.cancel.wizard'].create({
            'subscription_id': self.id,
        })
        return {
            'name': _('Confirmar cancelación'),
            'type': 'ir.actions.act_window',
            'res_model': 'subscription.cancel.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_generate_proforma(self):
        """Genera proforma en vivo (mantenido para compatibilidad / cron)."""
        self.ensure_one()
        if self.state != 'active':
            raise UserError(_('Solo puede generar proformas desde suscripciones activas.'))
        move = self._create_proforma_move()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': move.id,
            'context': {'hide_account_column': True},
        }

    def action_save_monthly_billable(self):
        """Abre el asistente para guardar el facturable del mes (para facturación mes vencido)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Guardar Facturable'),
            'res_model': 'subscription.monthly.billable.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_subscription_id': self.id},
        }

    def action_open_monthly_billable(self):
        """Abre la lista de facturables mensuales guardados de esta suscripción."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Consultar Facturable'),
            'res_model': 'subscription.monthly.billable',
            'view_mode': 'list,form',
            'domain': [('subscription_id', '=', self.id)],
            'context': {'default_subscription_id': self.id},
        }

    def do_save_monthly_billable(self, year, month):
        """Guarda el facturable del mes (total + líneas + detalles por serial del mes)."""
        self.ensure_one()
        if not (year and month and 1 <= month <= 12):
            raise UserError(_('Indique un año y mes válidos (1-12).'))
        Billable = self.env['subscription.monthly.billable']
        Line = self.env['subscription.monthly.billable.line']
        Detail = self.env['subscription.monthly.billable.line.detail']
        existing = Billable.search([
            ('subscription_id', '=', self.id),
            ('reference_year', '=', year),
            ('reference_month', '=', month),
        ])
        existing.unlink()
        self.reference_year = year
        self.reference_month = month
        self.invalidate_recordset(['grouped_product_ids'])
        grouped = self.grouped_product_ids
        total = sum(grouped.mapped('cost'))
        billable = Billable.create({
            'subscription_id': self.id,
            'reference_year': year,
            'reference_month': month,
            'total_amount': total,
        })
        days_in_month = calendar.monthrange(year, month)[1]
        first_day = datetime.date(year, month, 1)
        last_day = datetime.date(year, month, days_in_month)
        ctx = {'reference_year': year, 'reference_month': month}
        Quant = self.env['stock.quant'].with_context(**ctx)
        for g in grouped:
            line = Line.create({
                'billable_id': billable.id,
                'product_id': g.product_id.id if g.product_id else False,
                'product_display_name': g.product_display_name or (g.product_id.display_name if g.product_id else ''),
                'business_line_id': g.business_line_id.id if g.business_line_id else False,
                'quantity': g.quantity or 0,
                'cost': g.cost or 0.0,
                'is_license': bool(g.is_license),
            })
            if g.is_license:
                self._save_monthly_billable_license_details(line, g, Detail)
            else:
                lots_for_month = self._lots_with_activity_in_month(g, first_day, last_day)
                if not lots_for_month:
                    continue
                quants = Quant.search([
                    ('location_id', 'child_of', self.location_id.id),
                    ('lot_id', 'in', lots_for_month.ids),
                    ('quantity', '>', 0),
                ])
                lot_sel = self.env['stock.lot']._fields.get('reining_plazo')
                sel_dict = dict(lot_sel.selection) if lot_sel and getattr(lot_sel, 'selection', None) else {}
                for q in quants:
                    lot = q.lot_id
                    entry_display, lot_exit_display = self._lot_entry_exit_for_display(lot) if lot else (None, None)
                    plazo_label = (sel_dict.get(lot.reining_plazo) or lot.reining_plazo or '') if lot else ''
                    Detail.create({
                        'billable_line_id': line.id,
                        'location_id': q.location_id.id if q.location_id else self.location_id.id,
                        'lot_id': lot.id if lot else False,
                        'lot_name': lot.name if lot else '',
                        'product_name': q.product_id.display_name if q.product_id else '',
                        'inventory_plate': getattr(lot, 'inventory_plate', None) or '',
                        'cost_renting': getattr(q, 'lot_cost_renting_month', 0) or 0,
                        'days_total_month': getattr(q, 'lot_days_total_month', 0) or 0,
                        'current_day_of_month': getattr(q, 'lot_current_day_of_month_display', 0) or 0,
                        'entry_date': entry_display,
                        'exit_date': lot_exit_display,
                        'reining_plazo': plazo_label,
                        'days_total_on_site': getattr(q, 'lot_days_total_on_site', 0) or 0,
                        'days_in_service': getattr(q, 'lot_days_used_in_month', 0) or 0,
                        'cost_daily': getattr(q, 'lot_cost_daily', 0) or 0,
                        'cost_to_date': getattr(q, 'lot_cost_to_date_current', 0) or 0,
                    })
                # Lotes que salieron en el mes y ya no tienen quant en la ubicación: crear detalle desde el lote
                lots_with_quant = quants.mapped('lot_id')
                lots_without_quant = lots_for_month - lots_with_quant
                current_day = min(last_day.day, days_in_month) if (year, month) == (datetime.date.today().year, datetime.date.today().month) else days_in_month
                for lot in lots_without_quant:
                    self._create_billable_detail_for_exited_lot(
                        Detail, line, lot, g, first_day, last_day, days_in_month,
                        year, month, current_day, sel_dict
                    )
        self.reference_year = False
        self.reference_month = False
        month_name = _(datetime.date(year, month, 1).strftime('%B'))
        self.message_post(
            body=_('Facturable guardado: %s %s. Total: %s') % (
                month_name, year,
                formatLang(self.env, total, currency_obj=self.currency_id, digits=0),
            ),
            message_type='notification',
            subtype_xmlid='mail.mt_note',
        )
        return billable

    def _lots_with_activity_in_month(self, grouped_product, first_day, last_day):
        """Lots que estuvieron en el mes: todo el mes, ingreso en el mes, o salida en el mes."""
        lots = grouped_product.lot_ids or self.env['stock.lot']
        if not lots:
            return self.env['stock.lot']
        res = self.env['stock.lot']
        for lot in lots:
            entry_raw, lot_exit_raw = self._lot_entry_exit_for_display(lot)
            entry = self._lot_date_for_billable(entry_raw)
            exit_ = self._lot_date_for_billable(lot_exit_raw)
            if entry is None and exit_ is None:
                res |= lot
                continue
            if entry and entry > last_day:
                continue
            if exit_ and exit_ < first_day:
                continue
            res |= lot
        return res

    def _create_billable_detail_for_exited_lot(
        self, Detail, line, lot, grouped_product,
        first_day, last_day, days_in_month, year, month, current_day, sel_dict
    ):
        """Crea un registro de detalle para un lote que salió en el mes y ya no tiene quant en la ubicación."""
        entry_raw, lot_exit_raw = self._lot_entry_exit_for_display(lot)
        entry = self._lot_date_for_billable(entry_raw)
        exit_ = self._lot_date_for_billable(lot_exit_raw)
        if entry is None and exit_ is None:
            days_used = current_day
        elif entry and exit_ and entry.year == year and entry.month == month and exit_.year == year and exit_.month == month:
            days_used = max(0, exit_.day - entry.day + 1)
        elif entry and entry.year == year and entry.month == month:
            days_used = max(0, current_day - entry.day + 1)
        elif exit_ and exit_.year == year and exit_.month == month:
            days_used = max(0, exit_.day)
        else:
            days_used = days_in_month
        price_monthly = self._get_price_for_product(grouped_product.product_id, 1.0) or 0.0
        cost_daily = round(price_monthly / days_in_month, 2) if days_in_month else 0.0
        cost_to_date = round(cost_daily * days_used, 2)
        # Días totales en sitio = desde activación hasta hoy (o hasta fecha salida si ya salió), no el total del contrato
        days_total_on_site = 0
        if entry:
            today_d = fields.Date.context_today(self)
            today_d = today_d if isinstance(today_d, datetime.date) else datetime.date(today_d.year, today_d.month, today_d.day)
            end = (exit_ if exit_ and exit_ < today_d else today_d)
            if end >= entry:
                days_total_on_site = max(0, (end - entry).days + 1)
        product_name = grouped_product.product_display_name or (grouped_product.product_id.display_name if grouped_product.product_id else '')
        if lot.product_id:
            product_name = lot.product_id.display_name or product_name
        plazo_label = (sel_dict.get(lot.reining_plazo) or lot.reining_plazo or '') if sel_dict and getattr(lot, 'reining_plazo', None) else ''
        Detail.create({
            'billable_line_id': line.id,
            'location_id': self.location_id.id if self.location_id else False,
            'lot_id': lot.id,
            'lot_name': lot.name or '',
            'product_name': product_name,
            'inventory_plate': getattr(lot, 'inventory_plate', None) or '',
            'cost_renting': price_monthly,
            'days_total_month': days_in_month,
            'current_day_of_month': current_day,
            'entry_date': entry_raw,
            'exit_date': lot_exit_raw,
            'reining_plazo': plazo_label,
            'days_total_on_site': days_total_on_site,
            'days_in_service': days_used,
            'cost_daily': cost_daily,
            'cost_to_date': cost_to_date,
        })

    def _lot_date_for_billable(self, value):
        """Convierte fecha a datetime.date para comparación en filtro de mes."""
        if value is None:
            return None
        if isinstance(value, datetime.date) and not isinstance(value, datetime.datetime):
            return value
        if isinstance(value, datetime.datetime):
            return value.date()
        if hasattr(value, 'year') and hasattr(value, 'month') and hasattr(value, 'day'):
            try:
                return datetime.date(int(value.year), int(value.month), int(value.day))
            except (TypeError, ValueError):
                return None
        if isinstance(value, str):
            try:
                d = fields.Date.from_string(value)
                if d:
                    return datetime.date(d.year, d.month, d.day)
            except Exception:
                pass
        return None

    def _lot_entry_exit_for_display(self, lot):
        """Devuelve (entry_date, exit_date) para mostrar en esta suscripción.
        Si el lote salió de esta suscripción (last_subscription_id == self), usa las fechas congeladas
        para que cambios manuales en el lote (cliente nuevo) no afecten lo que ve esta suscripción."""
        if not lot:
            return (None, None)
        if getattr(lot, 'last_subscription_id', None) and lot.last_subscription_id.id == self.id:
            # Override opcional por suscripción (ajustes de fechas para la suscripción de la que salió)
            Override = self.env.get('subscription.lot.date.override')
            if Override:
                override = Override.search([
                    ('subscription_id', '=', self.id),
                    ('lot_id', '=', lot.id),
                ], limit=1)
                if override:
                    entry = override.entry_date or getattr(lot, 'last_subscription_entry_date', None)
                    exit_ = override.exit_date or getattr(lot, 'last_subscription_exit_date', None)
                    return (entry, exit_)
            entry = getattr(lot, 'last_subscription_entry_date', None)
            exit_ = getattr(lot, 'last_subscription_exit_date', None)
            return (entry, exit_)
        if getattr(lot, 'active_subscription_id', None) and lot.active_subscription_id.id == self.id:
            entry = getattr(lot, 'entry_date', None) or getattr(lot, 'last_entry_date_display', None)
            return (entry, None)
        entry = getattr(lot, 'entry_date', None) or getattr(lot, 'last_entry_date_display', None)
        exit_ = getattr(lot, 'exit_date', None) or getattr(lot, 'last_exit_date_display', None)
        return (entry, exit_)

    def _save_monthly_billable_license_details(self, billable_line, grouped_product, Detail):
        """Guarda detalles por licencia: asignados + filas vacías (igual que Ver Detalles)."""
        category_name = grouped_product.license_category or ''
        total_qty = max(1, int(grouped_product.quantity or 0))
        cost_per_unit = (grouped_product.cost or 0) / float(total_qty) if total_qty else 0
        location_id = self.location_id.id if self.location_id else False
        if 'license.assignment' not in self.env:
            for _dummy in range(total_qty):
                Detail.create({
                    'billable_line_id': billable_line.id,
                    'location_id': location_id,
                    'license_service_name': category_name,
                    'cost_renting': cost_per_unit,
                })
            return
        license_domain = [
            ('partner_id', '=', self.partner_id.id),
            ('state', '=', 'active'),
        ]
        if self.location_id:
            license_domain.append(('location_id', '=', self.location_id.id))
        active_licenses = self.env['license.assignment'].search(license_domain)
        lot_ids = []
        for la in active_licenses:
            if not la.license_id:
                continue
            lic_cat = (la.license_id.name.name if la.license_id.name else 'Sin Categoría')
            if lic_cat != category_name:
                continue
            if 'license.equipment' in self.env:
                for eq in self.env['license.equipment'].search([
                    ('assignment_id', '=', la.id),
                    ('state', '=', 'assigned'),
                    ('lot_id', '!=', False),
                ]):
                    if eq.lot_id and eq.lot_id.id not in lot_ids:
                        lot_ids.append(eq.lot_id.id)
        service_line_name = category_name
        for la in active_licenses:
            if not la.license_id or (la.license_id.name.name if la.license_id.name else '') != category_name:
                continue
            if la.license_id.product_id:
                service_line_name = la.license_id.product_id.display_name or la.license_id.product_id.name
                break
        Quant = self.env['stock.quant']
        assigned_count = 0
        if lot_ids:
            quants = Quant.search([
                ('location_id', 'child_of', self.location_id.id),
                ('lot_id', 'in', lot_ids),
                ('quantity', '>', 0),
            ])
            for q in quants:
                svc = getattr(q, 'license_service_name', None) or category_name
                if svc and service_line_name == category_name:
                    service_line_name = svc
                lot = q.lot_id
                hardware_name = q.product_id.display_name if q.product_id else ''
                Detail.create({
                    'billable_line_id': billable_line.id,
                    'location_id': q.location_id.id if q.location_id else self.location_id.id,
                    'lot_id': lot.id if lot else False,
                    'lot_name': lot.name if lot else '',
                    'product_name': hardware_name,
                    'license_service_name': svc,
                    'inventory_plate': getattr(lot, 'inventory_plate', None) or '',
                    'cost_renting': cost_per_unit,
                })
                assigned_count += 1
            if not quants and active_licenses:
                for la in active_licenses:
                    if not la.license_id or (la.license_id.name.name if la.license_id.name else '') != category_name:
                        continue
                    if la.license_id.product_id:
                        service_line_name = la.license_id.product_id.display_name or la.license_id.product_id.name
                        break
        location_id = self.location_id.id if self.location_id else False
        for _dummy in range(total_qty - assigned_count):
            Detail.create({
                'billable_line_id': billable_line.id,
                'location_id': location_id,
                'license_service_name': service_line_name,
                'cost_renting': cost_per_unit,
            })

    def _create_proforma_move(self):
        self.ensure_one()
        # Usar grouped_product_ids (pestaña "Producto Principal Copia") en lugar de line_ids
        if not self.grouped_product_ids:
            raise UserError(_('No hay productos agrupados para generar la proforma. Por favor, actualiza los productos primero.'))
        journal = self.env.ref('subscription_nocount.journal_proforma', raise_if_not_found=False)
        if not journal:
            raise UserError(_('No se encontró el diario de proformas.'))
        move_vals = {
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'currency_id': self.currency_id.id or self.env.company.currency_id.id,
            'invoice_origin': self.name,
            'invoice_line_ids': [],
            'journal_id': journal.id,
            'subscription_id': self.id,
            'x_is_proforma': True,
            'invoice_date': fields.Date.context_today(self),
        }
        seq = self._next_proforma_sequence()
        move_vals['name'] = self._get_proforma_title(seq)
        
        # Agrupar productos agrupados por business_line_id
        grouped_by_business = {}
        for grouped_product in self.grouped_product_ids:
            business_line = grouped_product.business_line_id
            if business_line:
                if business_line.id not in grouped_by_business:
                    grouped_by_business[business_line.id] = {
                        'business_line': business_line,
                        'products': []
                    }
                grouped_by_business[business_line.id]['products'].append(grouped_product)
            else:
                # Productos sin business_line van al final
                if 'no_business' not in grouped_by_business:
                    grouped_by_business['no_business'] = {
                        'business_line': False,
                        'products': []
                    }
                grouped_by_business['no_business']['products'].append(grouped_product)
        
        # Crear líneas agrupadas por business_line
        for business_id, group_data in grouped_by_business.items():
            business_line = group_data['business_line']
            products = group_data['products']
            
            # No pasar subscription_id en líneas: account.move.line.subscription_id apunta a sale_order
            if business_line:
                move_vals['invoice_line_ids'].append((0, 0, {
                    'display_type': 'line_section',
                    'name': business_line.name,
                }))
            for grouped_product in products:
                line_vals = grouped_product._prepare_invoice_line_values(self)
                move_vals['invoice_line_ids'].append((0, 0, line_vals))
        
        move = self.env['account.move'].create(move_vals)
        return move

    def _create_proforma_move_from_billable(self, billable):
        """Crea una proforma a partir del facturable mensual guardado (no del facturable en vivo)."""
        self.ensure_one()
        if not billable or billable.subscription_id.id != self.id:
            raise UserError(_('El facturable no pertenece a esta suscripción.'))
        if not billable.line_ids:
            raise UserError(_('El facturable guardado no tiene líneas para generar la proforma.'))
        journal = self.env.ref('subscription_nocount.journal_proforma', raise_if_not_found=False)
        if not journal:
            raise UserError(_('No se encontró el diario de proformas.'))
        # Crear primero solo la cabecera del move (sin líneas) para evitar que el contexto
        # del formulario del billable inyecte default_subscription_id = billable.id en las líneas
        move_vals = {
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'currency_id': self.currency_id.id or self.env.company.currency_id.id,
            'invoice_origin': self.name,
            'journal_id': journal.id,
            'subscription_id': self.id,
            'x_is_proforma': True,
            'invoice_date': fields.Date.context_today(self),
        }
        seq = self._next_proforma_sequence()
        move_vals['name'] = self._get_proforma_title(seq)
        move = self.env['account.move'].with_context(
            default_subscription_id=self.id,
            active_model='subscription.subscription',
            active_id=self.id,
            active_ids=[self.id],
        ).create(move_vals)
        # Añadir líneas con contexto explícito de suscripción (las líneas heredan subscription_id del move)
        grouped_by_business = {}
        for line in billable.line_ids:
            bl = line.business_line_id
            key = bl.id if bl else 'no_business'
            if key not in grouped_by_business:
                grouped_by_business[key] = {'business_line': bl, 'lines': []}
            grouped_by_business[key]['lines'].append(line)
        # Crear líneas sin subscription_id: la FK en account.move.line apunta a sale_order, no a subscription.subscription
        MoveLine = self.env['account.move.line'].with_context(
            active_model='account.move',
            active_id=move.id,
            active_ids=[move.id],
        )
        for key, g in grouped_by_business.items():
            if g['business_line']:
                MoveLine.create({
                    'move_id': move.id,
                    'display_type': 'line_section',
                    'name': g['business_line'].name,
                })
            for line in g['lines']:
                if line.product_id:
                    line_vals = line._prepare_invoice_line_values(self)
                    line_vals['move_id'] = move.id
                    MoveLine.create(line_vals)
        return move

    def _create_proforma_with_usages(self, wizard_lines):
        self.ensure_one()
        journal = self.env.ref('subscription_nocount.journal_proforma', raise_if_not_found=False)
        if not journal:
            raise UserError(_('No se encontró el diario de proformas.'))
        move_vals = {
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'currency_id': self.currency_id.id or self.env.company.currency_id.id,
            'invoice_origin': _('Uso %s') % self.name,
            'journal_id': journal.id,
            'subscription_id': self.id,
            'x_is_proforma': True,
            'invoice_line_ids': [],
            'invoice_date': fields.Date.context_today(self),
        }
        seq = self._next_proforma_sequence()
        move_vals['name'] = self._get_proforma_title(seq)
        # No pasar subscription_id en líneas: account.move.line.subscription_id apunta a sale_order
        active_lines = self.line_ids.filtered(lambda l: l.is_active and not l.is_component_line)
        for line in active_lines:
            line_vals = line._prepare_invoice_line_values(self)
            move_vals['invoice_line_ids'].append((0, 0, line_vals))
        for wizard_line in wizard_lines:
            line_vals = wizard_line._prepare_invoice_line_vals()
            move_vals['invoice_line_ids'].append((0, 0, line_vals))
        return self.env['account.move'].create(move_vals)

    @api.model
    def cron_generate_monthly_proformas(self):
        today = fields.Date.context_today(self)
        last_day = calendar.monthrange(today.year, today.month)[1]
        trigger_days = {last_day}
        if last_day >= 30:
            trigger_days.add(30)
        force_param = self.env['ir.config_parameter'].sudo().get_param('subscription_nocount.force_generate_proforma', '0')
        force_run = force_param == '1'
        if force_run:
            self.env['ir.config_parameter'].sudo().set_param('subscription_nocount.force_generate_proforma', '0')
        if not (self.env.context.get('force_generate_proforma') or force_run) and today.day not in trigger_days:
            return
        self.cron_sync_from_locations()
        domain = [
            ('state', '=', 'active'),
            ('start_date', '!=', False),
            ('start_date', '<=', today),
        ]
        subscriptions = self.search(domain)
        for subscription in subscriptions:
            if subscription.end_date and subscription.end_date < today:
                continue
            try:
                subscription.with_context(from_cron=True).action_generate_proforma()
            except UserError as err:
                _logger.info('Suscripción %s omitida durante la generación automática: %s', subscription.display_name, err)
            except Exception as exc:
                _logger.exception('Error al generar proforma automática para la suscripción %s: %s', subscription.display_name, exc)

    all_location_history_ids = fields.Many2many(
        'stock.move.line',
        compute='_compute_all_location_history',
        string='Historial completo de ubicación',
        readonly=True,
    )

    all_location_products_ids = fields.Many2many(
        'stock.quant',
        compute='_compute_all_location_products',
        string='Todos los productos en ubicación',
        readonly=True,
    )

    @api.depends('location_id')
    def _compute_all_location_products(self):
        for subscription in self:
            if not subscription.location_id:
                subscription.all_location_products_ids = False
                continue
            location_ids = self.env['stock.location'].search([('id', 'child_of', subscription.location_id.id)]).ids
            quants = self.env['stock.quant'].search([
                ('location_id', 'in', location_ids),
                ('quantity', '>', 0),
            ])
            subscription.all_location_products_ids = quants

    @api.depends('location_id')
    def _compute_all_location_history(self):
        for subscription in self:
            if not subscription.location_id:
                subscription.all_location_history_ids = False
                continue
            location_ids = self.env['stock.location'].search([('id', 'child_of', subscription.location_id.id)]).ids
            move_lines = self.env['stock.move.line'].search([
                ('state', '=', 'done'),
                '|',
                ('location_dest_id', 'in', location_ids),
                ('location_id', 'in', location_ids),
            ], order='date desc')
            subscription.all_location_history_ids = move_lines

    def _consolidate_duplicate_lines(self):
        """Consolida líneas duplicadas del mismo producto sumando las cantidades."""
        self.ensure_one()
        line_model = self.env['subscription.subscription.line']
        
        # Obtener todas las líneas de servicio visibles
        service_lines = self.service_line_ids.filtered(
            lambda l: l.is_active and l.display_in_lines and not l.is_component_line
        )
        
        # Agrupar por producto (usando product_id como clave)
        lines_by_product = {}
        for line in service_lines:
            product_key = line.product_id.id
            if product_key not in lines_by_product:
                lines_by_product[product_key] = []
            lines_by_product[product_key].append(line)
        
        # Consolidar líneas duplicadas
        for product_id, lines in lines_by_product.items():
            if len(lines) <= 1:
                continue  # No hay duplicados
            
            # Convertir a recordset y ordenar por ID para mantener la primera línea
            lines_recordset = line_model.browse([l.id for l in lines]).sorted('id')
            main_line = lines_recordset[0]
            duplicate_lines = lines_recordset[1:]
            
            # Sumar cantidades
            total_quantity = sum(l.quantity for l in lines_recordset)
            
            # Transferir registros de uso de las líneas duplicadas a la línea principal
            # ANTES de actualizar la cantidad para evitar que se cierren registros
            for dup_line in duplicate_lines:
                # Transferir usage_ids a la línea principal
                dup_line.usage_ids.write({'line_id': main_line.id})
            
            # Recalcular precio mensual basado en la cantidad total
            if main_line.subscription_id:
                new_price = main_line.subscription_id._get_price_for_product(main_line.product_id, total_quantity)
            else:
                new_price = main_line.product_id.lst_price
            
            # Actualizar la línea principal usando write() con contexto para evitar cierre de registros
            # El contexto 'skip_usage_update' evitará que se ejecuten métodos que cierren registros
            main_line.with_context(skip_usage_update=True, consolidating_lines=True).write({
                'quantity': total_quantity,
                'price_monthly': new_price,
            })
            # El subtotal se recalculará automáticamente por el compute
            
            # Eliminar las líneas duplicadas (los usage_ids ya fueron transferidos)
            if duplicate_lines:
                duplicate_lines.unlink()

    def _fix_existing_lines_visibility(self):
        """Corrige la visibilidad de las líneas existentes según su clasificación."""
        self.ensure_one()
        
        SuppliesComposite = self.env['product.composite.line']
        SuppliesPeripheral = self.env['product.peripheral.line']
        SuppliesComplement = self.env['product.complement.line']
        
        # Obtener productos relacionados como componentes/periféricos/complementos
        related_product_ids = set()
        related_product_ids.update(SuppliesComposite.search([]).mapped('component_product_id').ids)
        related_product_ids.update(SuppliesPeripheral.search([]).mapped('peripheral_product_id').ids)
        related_product_ids.update(SuppliesComplement.search([]).mapped('complement_product_id').ids)
        
        for line in self.line_ids:
            product = line.stock_product_id or line.product_id
            if not product:
                continue
            
            # Determinar si es componente/periférico/complemento
            classification = getattr(product.product_tmpl_id, 'classification', False) if hasattr(product.product_tmpl_id, 'classification') else False
            is_component_related = (
                classification in ('component', 'peripheral', 'complement') or
                product.id in related_product_ids
            )
            
            # Si es componente pero está visible, ocultarlo
            if is_component_related and line.display_in_lines:
                component_item_type = classification or 'component'
                line.write({
                    'display_in_lines': False,
                    'is_component_line': True,
                    'component_item_type': component_item_type,
                    'price_monthly': 0.0,
                })
            # Si NO es componente pero está oculto, mostrarlo
            elif not is_component_related and not line.display_in_lines and not line.is_component_line:
                line.write({
                    'display_in_lines': True,
                    'is_component_line': False,
                    'component_item_type': False,
                })

    def _ensure_all_products_have_usage(self):
        """Asegura que todos los productos en la ubicación tengan registros de uso."""
        self.ensure_one()
        if not self.location_id:
            return
        
        Quant = self.env['stock.quant']
        location_ids = self.env['stock.location'].search([('id', 'child_of', self.location_id.id)]).ids
        
        # Obtener TODOS los quants en la ubicación (sin filtros)
        quants = Quant.search([
            ('location_id', 'in', location_ids),
            ('quantity', '>', 0),
        ])
        
        line_model = self.env['subscription.subscription.line']
        usage_model = self.env['subscription.subscription.usage']
        SuppliesComposite = self.env['product.composite.line']
        SuppliesPeripheral = self.env['product.peripheral.line']
        SuppliesComplement = self.env['product.complement.line']
        
        # Obtener productos relacionados como componentes/periféricos/complementos
        related_product_ids = set()
        related_product_ids.update(SuppliesComposite.search([]).mapped('component_product_id').ids)
        related_product_ids.update(SuppliesPeripheral.search([]).mapped('peripheral_product_id').ids)
        related_product_ids.update(SuppliesComplement.search([]).mapped('complement_product_id').ids)
        
        # Agrupar quants por producto y lote
        quant_groups = {}
        for quant in quants:
            product = quant.product_id
            lot_id = quant.lot_id.id if quant.lot_id else False
            key = (product.id, lot_id)
            if key not in quant_groups:
                quant_groups[key] = {
                    'product': product,
                    'lot': quant.lot_id,
                    'quantity': 0.0,
                    'in_date': quant.in_date or quant.write_date or quant.create_date,
                }
            quant_groups[key]['quantity'] += quant.quantity
        
        for (product_id, lot_id), group_data in quant_groups.items():
            product = group_data['product']
            lot = group_data['lot']
            qty = group_data['quantity']
            in_date = group_data['in_date']
            
            # Determinar si es componente/periférico/complemento
            classification = getattr(product.product_tmpl_id, 'classification', False) if hasattr(product.product_tmpl_id, 'classification') else False
            is_component_related = (
                classification in ('component', 'peripheral', 'complement') or
                product.id in related_product_ids or
                (lot and lot.principal_lot_id)
            )
            
            # Buscar línea de suscripción existente
            line = line_model.search([
                ('subscription_id', '=', self.id),
                '|',
                ('product_id', '=', product.id),
                ('stock_product_id', '=', product.id),
            ], limit=1)
            
            # Si no existe línea, crearla
            if not line:
                # Usar el servicio del lote si existe, sino usar el producto directamente
                service_product = (lot.subscription_service_product_id if lot else False) or product
                display_in_lines = not is_component_related
                is_component_line = is_component_related
                component_item_type = False
                if is_component_related:
                    component_item_type = classification or 'component'
                
                line = line_model.create({
                    'subscription_id': self.id,
                    'product_id': service_product.id,
                    'stock_product_id': product.id,
                    'quantity': qty,
                    'price_monthly': self._get_price_for_product(service_product, qty) if not is_component_related else 0.0,
                    'is_active': True,
                    'display_in_lines': display_in_lines,
                    'is_component_line': is_component_line,
                    'component_item_type': component_item_type,
                })
            
            # Verificar si existe registro de uso activo (sin date_end) para este producto/lote
            domain_active = [
                ('line_id', '=', line.id),
                ('date_end', '=', False),
            ]
            if lot:
                domain_active.append(('lot_id', '=', lot.id))
            else:
                domain_active.append(('lot_id', '=', False))
            
            usage_active = usage_model.search(domain_active, limit=1)
            
            # Solo crear registro si NO existe uno activo
            # Si ya existe un registro activo, no hacer nada (evitar duplicados)
            if not usage_active:
                # Verificar si existe algún registro (activo o histórico) para este producto/lote
                # Si existe uno histórico cerrado, no crear uno nuevo a menos que el producto esté actualmente en stock
                domain_any = [
                    ('line_id', '=', line.id),
                ]
                if lot:
                    domain_any.append(('lot_id', '=', lot.id))
                else:
                    domain_any.append(('lot_id', '=', False))
                
                existing_usage = usage_model.search(domain_any, order='date_start desc', limit=1)
                
                # Solo crear si:
                # 1. No existe ningún registro (ni activo ni histórico)
                # 2. O existe uno histórico cerrado Y el producto está actualmente en stock (necesita uno activo nuevo)
                should_create = False
                if not existing_usage:
                    # No existe ningún registro, crear uno nuevo
                    should_create = True
                elif existing_usage.date_end and qty > 0:
                    # Existe un registro histórico cerrado pero el producto está actualmente en stock
                    # Esto significa que el producto volvió a la ubicación, crear un nuevo registro activo
                    should_create = True
                
                if should_create:
                    entry_date = in_date
                    if lot:
                        entry_date = self._get_lot_entry_date(
                            lot,
                            self.location_id,
                            product=product,
                            default_dt=in_date,
                        ) or in_date
                    
                    usage_model.create({
                        'line_id': line.id,
                        'lot_id': lot.id if lot else False,
                        'date_start': entry_date or fields.Datetime.now(),
                        'quantity': qty,
                        'price_monthly_snapshot': line.price_monthly or 0.0,
                    })

    def _ensure_usage_for_missing_products(self):
        """Crea registros de uso solo para productos que no tienen líneas de suscripción pero están en la ubicación."""
        self.ensure_one()
        if not self.location_id:
            return
        
        Quant = self.env['stock.quant']
        location_ids = self.env['stock.location'].search([('id', 'child_of', self.location_id.id)]).ids
        quants = Quant.search([
            ('location_id', 'in', location_ids),
            ('quantity', '>', 0),
        ])
        
        line_model = self.env['subscription.subscription.line']
        usage_model = self.env['subscription.subscription.usage']
        
        # Obtener productos que ya tienen líneas de suscripción
        existing_product_ids = set(line_model.search([
            ('subscription_id', '=', self.id)
        ]).mapped(lambda l: l.stock_product_id.id if l.stock_product_id else l.product_id.id))
        
        # Agrupar quants por producto y lote
        quant_groups = {}
        for quant in quants:
            product = quant.product_id
            # Solo procesar productos que NO tienen línea de suscripción
            if product.id in existing_product_ids:
                continue
                
            lot_id = quant.lot_id.id if quant.lot_id else False
            key = (product.id, lot_id)
            if key not in quant_groups:
                quant_groups[key] = {
                    'product': product,
                    'lot': quant.lot_id,
                    'quantity': 0.0,
                    'in_date': quant.in_date or quant.write_date or quant.create_date,
                }
            quant_groups[key]['quantity'] += quant.quantity
        
        # Solo crear registros para productos que realmente no tienen línea
        for (product_id, lot_id), group_data in quant_groups.items():
            product = group_data['product']
            lot = group_data['lot']
            qty = group_data['quantity']
            in_date = group_data['in_date']
            
            # Crear línea de suscripción para este producto
            # Usar el servicio del lote si existe, sino usar el producto directamente
            service_product = (lot.subscription_service_product_id if lot else False) or product
            line = line_model.create({
                'subscription_id': self.id,
                'product_id': service_product.id,
                'stock_product_id': product.id,
                'quantity': qty,
                'price_monthly': self._get_price_for_product(service_product, qty),
                'is_active': True,
                'display_in_lines': True,
                'is_component_line': False,
            })
            
            # Crear registro de uso
            entry_date = in_date
            if lot:
                entry_date = self._get_lot_entry_date(
                    lot,
                    self.location_id,
                    product=product,
                    default_dt=in_date,
                ) or in_date
            
            usage_model.create({
                'line_id': line.id,
                'lot_id': lot.id if lot else False,
                'date_start': entry_date or fields.Datetime.now(),
                'quantity': qty,
                'price_monthly_snapshot': line.price_monthly or 0.0,
            })

    def _ensure_usage_for_all_location_products(self):
        """Crea registros de uso para todos los productos en la ubicación."""
        self.ensure_one()
        if not self.location_id:
            return
        
        Quant = self.env['stock.quant']
        SuppliesComposite = self.env['product.composite.line']
        SuppliesPeripheral = self.env['product.peripheral.line']
        SuppliesComplement = self.env['product.complement.line']
        
        # Obtener productos relacionados como componentes/periféricos/complementos
        related_product_ids = set()
        related_product_ids.update(SuppliesComposite.search([]).mapped('component_product_id').ids)
        related_product_ids.update(SuppliesPeripheral.search([]).mapped('peripheral_product_id').ids)
        related_product_ids.update(SuppliesComplement.search([]).mapped('complement_product_id').ids)
        
        location_ids = self.env['stock.location'].search([('id', 'child_of', self.location_id.id)]).ids
        quants = Quant.search([
            ('location_id', 'in', location_ids),
            ('quantity', '>', 0),
        ])
        
        line_model = self.env['subscription.subscription.line']
        usage_model = self.env['subscription.subscription.usage']
        
        # Agrupar quants por producto y lote
        quant_groups = {}
        for quant in quants:
            product = quant.product_id
            lot_id = quant.lot_id.id if quant.lot_id else False
            key = (product.id, lot_id)
            if key not in quant_groups:
                quant_groups[key] = {
                    'product': product,
                    'lot': quant.lot_id,
                    'quantity': 0.0,
                    'in_date': quant.in_date or quant.write_date or quant.create_date,
                }
            quant_groups[key]['quantity'] += quant.quantity
        
        for (product_id, lot_id), group_data in quant_groups.items():
            product = group_data['product']
            lot = group_data['lot']
            qty = group_data['quantity']
            in_date = group_data['in_date']
            
            # Determinar si es componente/periférico/complemento
            classification = getattr(product.product_tmpl_id, 'classification', False) if hasattr(product.product_tmpl_id, 'classification') else False
            is_component_related = (
                classification in ('component', 'peripheral', 'complement') or
                product.id in related_product_ids or
                (lot and lot.principal_lot_id)  # Si el lote tiene un lote principal, es componente
            )
            
            # Buscar o crear línea de suscripción para este producto
            line = line_model.search([
                ('subscription_id', '=', self.id),
                '|',
                ('product_id', '=', product.id),
                ('stock_product_id', '=', product.id),
            ], limit=1)
            
            if not line:
                # Usar el servicio del lote si existe, sino usar el producto directamente
                service_product = (lot.subscription_service_product_id if lot else False) or product
                display_in_lines = not is_component_related
                is_component_line = is_component_related
                
                # Determinar el tipo de componente si aplica
                component_item_type = False
                if is_component_related:
                    if classification:
                        component_item_type = classification
                    else:
                        component_item_type = 'component'  # Por defecto
                
                line = line_model.create({
                    'subscription_id': self.id,
                    'product_id': service_product.id,
                    'stock_product_id': product.id,
                    'quantity': qty,
                    'price_monthly': self._get_price_for_product(service_product, qty) if not is_component_related else 0.0,
                    'is_active': True,
                    'display_in_lines': display_in_lines,
                    'is_component_line': is_component_line,
                    'component_item_type': component_item_type,
                })
            else:
                # Actualizar línea existente si es necesario
                if is_component_related and line.display_in_lines:
                    line.write({
                        'display_in_lines': False,
                        'is_component_line': True,
                        'component_item_type': classification or 'component',
                        'price_monthly': 0.0,
                    })
            
            # Buscar registro de uso activo (sin date_end) para este producto/lote
            domain_active = [
                ('line_id', '=', line.id),
                ('date_end', '=', False),
            ]
            if lot:
                domain_active.append(('lot_id', '=', lot.id))
            else:
                domain_active.append(('lot_id', '=', False))
            
            usage_active = usage_model.search(domain_active, limit=1)
            
            # SOLO crear nuevo registro si:
            # 1. NO existe un registro activo (sin date_end)
            # 2. El producto está actualmente en stock (qty > 0)
            # Esto evita crear registros duplicados cuando se actualiza sin cambios
            if not usage_active and qty > 0:
                # Verificar si existe un registro histórico (con date_end) para evitar duplicados
                domain_historical = [
                    ('line_id', '=', line.id),
                ]
                if lot:
                    domain_historical.append(('lot_id', '=', lot.id))
                else:
                    domain_historical.append(('lot_id', '=', False))
                
                # Buscar el registro histórico más reciente
                existing_usage = usage_model.search(domain_historical, order='date_start desc', limit=1)
                
                # Solo crear si:
                # 1. No existe ningún registro histórico, O
                # 2. Existe un registro histórico pero tiene date_end (producto fue retirado y ahora volvió)
                should_create = False
                if not existing_usage:
                    # No existe ningún registro, crear uno nuevo
                    should_create = True
                elif existing_usage.date_end and qty > 0:
                    # Existe un registro histórico cerrado pero el producto está actualmente en stock
                    # Esto significa que el producto volvió a la ubicación, crear un nuevo registro activo
                    should_create = True
                
                if should_create:
                    entry_date = in_date
                    if lot:
                        entry_date = self._get_lot_entry_date(
                            lot,
                            self.location_id,
                            product=product,
                            default_dt=in_date,
                        ) or in_date
                    
                    usage_model.create({
                        'line_id': line.id,
                        'lot_id': lot.id if lot else False,
                        'date_start': entry_date or fields.Datetime.now(),
                        'quantity': qty,
                        'price_monthly_snapshot': line.price_monthly or 0.0,
                    })

    def _compute_usage_summary_fake(self):
        """Método temporal para evitar errores de validación."""
        for subscription in self:
            subscription.usage_closed_count = 0
    
    def _compute_equipment_change_count_fake(self):
        """Método temporal para evitar errores de validación."""
        for subscription in self:
            subscription.equipment_change_count = 0

    @api.depends('usage_ids.date_end', 'location_id', 'location_quant_ids')
    def _compute_usage_summary(self):
        """Calcula el número de activos basándose en los seriales únicos en la ubicación.
        Esto evita contar registros duplicados de uso."""
        for subscription in self:
            if not subscription.location_id:
                subscription.usage_active_count = 0
                continue
            
            # Contar seriales únicos en la ubicación (como en inventario)
            # Esto es más preciso que contar registros de uso que pueden tener duplicados
            Quant = self.env['stock.quant']
            location_ids = self.env['stock.location'].search([('id', 'child_of', subscription.location_id.id)]).ids
            quants = Quant.search([
                ('location_id', 'in', location_ids),
                ('lot_id', '!=', False),
                ('quantity', '>', 0),
            ])
            # Contar seriales únicos (por lot_id)
            unique_lots = quants.mapped('lot_id')
            subscription.usage_active_count = len(unique_lots)

    def action_equipment_change(self):
        """Abre el wizard para cambio de equipo."""
        self.ensure_one()
        if self.state != 'active':
            raise UserError(_('Solo puede realizar cambios de equipo en suscripciones activas.'))
        if not self.location_id:
            raise UserError(_('Debe establecer una ubicación para realizar cambios de equipo.'))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cambio de Equipo'),
            'res_model': 'subscription.equipment.change.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_subscription_id': self.id,
                'equipment_change_wizard': True,
                'search_by_inventory_plate_only': True,
                'active_model': 'subscription.equipment.change.wizard',  # Asegurar que active_model esté presente
            },
        }


class SubscriptionLotDateOverride(models.Model):
    _name = 'subscription.lot.date.override'
    _description = 'Override fechas por suscripción (serial que ya salió)'
    _rec_name = 'lot_id'

    subscription_id = fields.Many2one(
        'subscription.subscription',
        string='Suscripción',
        required=True,
        ondelete='cascade',
    )
    lot_id = fields.Many2one(
        'stock.lot',
        string='Serial',
        required=True,
        ondelete='cascade',
    )
    entry_date = fields.Date(
        string='Fecha activación (ajuste)',
        help='Fecha de activación que se mostrará en esta suscripción para este serial (sustituye la guardada al salir).',
    )
    exit_date = fields.Date(
        string='Fecha finalización (ajuste)',
        help='Fecha de finalización que se mostrará en esta suscripción para este serial (sustituye la guardada al salir).',
    )

    def _lot_display_for_message(self):
        return (self.lot_id.display_name or self.lot_id.name or _('Serial')) if self.lot_id else _('Serial')

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            if rec.subscription_id:
                rec.subscription_id.message_post(
                    body=_('Ajuste de fechas añadido: %s.') % rec._lot_display_for_message(),
                    message_type='notification',
                    subtype_xmlid='mail.mt_note',
                )
        return recs

    def write(self, vals):
        res = super().write(vals)
        if vals:
            to_log = {}
            for rec in self:
                if rec.subscription_id:
                    sid = rec.subscription_id.id
                    if sid not in to_log:
                        to_log[sid] = []
                    to_log[sid].append(rec._lot_display_for_message())
            for sub_id, names in to_log.items():
                sub = self.env['subscription.subscription'].browse(sub_id)
                if sub.exists() and names:
                    sub.message_post(
                        body=_('Ajuste de fechas modificado: %s.') % ', '.join(names),
                        message_type='notification',
                        subtype_xmlid='mail.mt_note',
                    )
        return res

    def unlink(self):
        to_log = {}  # subscription_id -> list of lot display names
        for rec in self:
            if rec.subscription_id:
                sid = rec.subscription_id.id
                if sid not in to_log:
                    to_log[sid] = []
                to_log[sid].append(rec._lot_display_for_message())
        res = super().unlink()
        for sub_id, names in to_log.items():
            sub = self.env['subscription.subscription'].browse(sub_id)
            if sub.exists() and names:
                sub.message_post(
                    body=_('Ajuste de fechas eliminado: %s.') % ', '.join(names),
                    message_type='notification',
                    subtype_xmlid='mail.mt_note',
                )
        return res

    _sql_constraints = [
        ('unique_sub_lot', 'unique(subscription_id, lot_id)', 'Ya existe un ajuste de fechas para este serial en esta suscripción.'),
    ]


class SubscriptionSubscriptionLine(models.Model):
    _name = 'subscription.subscription.line'
    _description = 'Subscription product line'
    _rec_name = 'display_name'
    
    def _auto_init(self):
        # Eliminar columnas de campos eliminados si existen en la base de datos
        cr = self._cr
        table = self._table
        # Verificar y eliminar usage_closed_count si existe
        cr.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = %s AND column_name = 'usage_closed_count'
        """, (table,))
        if cr.fetchone():
            cr.execute('ALTER TABLE %s DROP COLUMN IF EXISTS usage_closed_count' % table)
        # Verificar y eliminar equipment_change_count si existe
        cr.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = %s AND column_name = 'equipment_change_count'
        """, (table,))
        if cr.fetchone():
            cr.execute('ALTER TABLE %s DROP COLUMN IF EXISTS equipment_change_count' % table)
        
        return super()._auto_init()
    
    def _auto_init_old(self):
        """Crear columna business_line_id si no existe."""
        res = super()._auto_init()
        if self._auto:
            # Verificar si la columna existe
            self.env.cr.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='subscription_subscription_line' 
                AND column_name='business_line_id'
            """)
            if not self.env.cr.fetchone():
                # Verificar si la tabla product_business_line existe
                self.env.cr.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_name='product_business_line'
                """)
                if self.env.cr.fetchone():
                    # Crear la columna con foreign key
                    self.env.cr.execute("""
                        ALTER TABLE subscription_subscription_line 
                        ADD COLUMN business_line_id INTEGER
                    """)
                    self.env.cr.execute("""
                        CREATE INDEX IF NOT EXISTS subscription_subscription_line_business_line_id_index 
                        ON subscription_subscription_line(business_line_id)
                    """)
                    # Agregar foreign key constraint si es posible
                    try:
                        self.env.cr.execute("""
                            ALTER TABLE subscription_subscription_line 
                            ADD CONSTRAINT subscription_subscription_line_business_line_id_fkey 
                            FOREIGN KEY (business_line_id) 
                            REFERENCES product_business_line(id) 
                            ON DELETE RESTRICT
                        """)
                    except Exception:
                        # Si falla, continuar sin foreign key
                        pass
                    # Recalcular business_line_id para todas las líneas existentes
                    self.env.cr.execute("""
                        UPDATE subscription_subscription_line ssl
                        SET business_line_id = (
                            SELECT pt.business_line_id 
                            FROM product_product pp 
                            JOIN product_template pt ON pt.id = pp.product_tmpl_id
                            WHERE pp.id = ssl.product_id
                        )
                        WHERE EXISTS (
                            SELECT 1 FROM product_product pp 
                            JOIN product_template pt ON pt.id = pp.product_tmpl_id
                            WHERE pp.id = ssl.product_id 
                            AND pt.business_line_id IS NOT NULL
                        )
                    """)
        return res

    subscription_id = fields.Many2one('subscription.subscription', string='Suscripción', required=True, ondelete='cascade', index=True)
    product_id = fields.Many2one('product.product', string='Producto', required=True)
    stock_product_id = fields.Many2one('product.product', string='Producto físico')
    business_line_id = fields.Many2one(
        'product.business.line',
        string='Línea de negocio',
        compute='_compute_business_line_id',
        store=True,
        readonly=True,
    )
    product_code = fields.Char(
        string='Código',
        related='product_id.default_code',
        store=True,
        readonly=True,
    )
    
    @api.depends('product_id', 'product_id.business_line_id', 'product_id.product_tmpl_id.business_line_id')
    def _compute_business_line_id(self):
        for line in self:
            if not line.product_id:
                line.business_line_id = False
                continue
            # Verificar si el modelo product.business.line existe
            if 'product.business.line' in self.env:
                # Intentar obtener desde product_id directamente
                if hasattr(line.product_id, 'business_line_id') and line.product_id.business_line_id:
                    line.business_line_id = line.product_id.business_line_id
                # Si no, intentar desde product_tmpl_id
                elif hasattr(line.product_id, 'product_tmpl_id') and hasattr(line.product_id.product_tmpl_id, 'business_line_id'):
                    line.business_line_id = line.product_id.product_tmpl_id.business_line_id
                else:
                    line.business_line_id = False
            else:
                line.business_line_id = False
    quantity = fields.Float(string='Cantidad', default=1.0)
    price_monthly = fields.Monetary(string='Precio mensual', currency_field='currency_id', digits=(16, 0))
    subtotal_monthly = fields.Monetary(string='Subtotal Mensual', compute='_compute_subtotal_monthly', store=True, currency_field='currency_id', digits=(16, 0))
    currency_id = fields.Many2one(related='subscription_id.currency_id', store=True, readonly=True)
    location_id = fields.Many2one('stock.location', string='Ubicación específica')
    usage_ids = fields.One2many('subscription.subscription.usage', 'line_id', string='Usos')
    active_usage_count = fields.Integer(string='Usos en curso', compute='_compute_usage_counts')
    closed_usage_count = fields.Integer(string='Usos finalizados', compute='_compute_usage_counts')
    display_name = fields.Char(string='Descripción', compute='_compute_display_name', store=True)
    lot_serials_display = fields.Char(string='Series', compute='_compute_lot_serials', compute_sudo=True)
    is_active = fields.Boolean(string='Activo', default=True)
    display_in_lines = fields.Boolean(string='Mostrar en pestaña líneas', default=True)
    is_component_line = fields.Boolean(string='Línea de componente', default=False)
    component_item_type = fields.Selection(
        selection=[
            ('component', 'Componente'),
            ('peripheral', 'Periférico'),
            ('complement', 'Complemento'),
            ('monitor', 'Monitores'),
            ('ups', 'UPS'),
        ],
        string='Tipo componente',
        readonly=True,
    )
    component_lot_id = fields.Many2one('stock.lot', string='Serie componente', readonly=True)
    component_date_start = fields.Datetime(string='Fecha inicio componente', readonly=True)
    component_date_end = fields.Datetime(string='Fecha fin componente', readonly=True)
    component_days_active = fields.Integer(string='Días activos comp.', readonly=True)
    component_daily_rate = fields.Monetary(string='Tarifa diaria comp.', currency_field='currency_id', readonly=True, digits=(16, 0))
    component_amount = fields.Monetary(string='Importe comp.', currency_field='currency_id', readonly=True, digits=(16, 0))

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for line in self:
            if not line.product_id:
                continue
            subscription = line.subscription_id
            if subscription:
                line.price_monthly = subscription._get_price_for_product(line.product_id, line.quantity or 1.0)
            else:
                line.price_monthly = line.product_id.lst_price

    @api.depends('quantity', 'price_monthly')
    def _compute_subtotal_monthly(self):
        for line in self:
            line.subtotal_monthly = line.quantity * line.price_monthly

    @api.onchange('quantity')
    def _onchange_quantity(self):
        for line in self:
            if not line.subscription_id or not line.product_id:
                continue
            line.price_monthly = line.subscription_id._get_price_for_product(line.product_id, line.quantity or 1.0)

    def action_view_serials(self):
        self.ensure_one()
        # Obtener el producto físico (stock_product_id) - este es el que está en stock
        stock_product = self.stock_product_id or self.product_id
        service_product = self.product_id  # Este es el servicio de la línea
        
        if not stock_product:
            raise UserError(_('La línea no tiene un producto definido.'))
        
        location = self.location_id or self.subscription_id.location_id
        if not location:
            raise UserError(_('No hay ubicación definida para mostrar las series.'))
        
        Quant = self.env['stock.quant']
        
        # PRIORIDAD 1: Usar usage_ids si existen (estos son los seriales realmente asociados a esta línea)
        open_usages = self.usage_ids.filtered(lambda u: not u.date_end)
        usage_lot_ids = open_usages.mapped('lot_id').filtered(lambda l: l).ids if open_usages else []
        
        if usage_lot_ids:
            # Si hay usage_ids, mostrar SOLO esos seriales
            domain = [
                ('location_id', 'child_of', location.id),
                ('lot_id', 'in', usage_lot_ids),
                ('quantity', '>', 0),
            ]
        else:
            # PRIORIDAD 2: Si no hay usage_ids, buscar seriales por producto físico y servicio
            # Buscar todos los quants del producto físico en la ubicación
            quant_domain = [
                ('location_id', 'child_of', location.id),
                ('product_id', '=', stock_product.id),
                ('lot_id', '!=', False),
                ('quantity', '>', 0),
            ]
            all_quants = Quant.search(quant_domain)
            
            # Filtrar por servicio del lote
            matching_lot_ids = []
            for quant in all_quants:
                lot = quant.lot_id
                if not lot:
                    continue
                
                # Obtener el servicio del lote
                lot_service = lot.subscription_service_product_id
                if lot_service:
                    quant_service_product = lot_service
                else:
                    quant_service_product = stock_product  # Usar producto físico si no hay servicio
                
                # Solo incluir si el servicio coincide con el servicio de la línea
                if quant_service_product.id == service_product.id:
                    if lot.id not in matching_lot_ids:
                        matching_lot_ids.append(lot.id)
            
            # Limitar a la cantidad de la línea (si hay cantidad definida)
            if matching_lot_ids and self.quantity > 0:
                # Tomar solo los primeros N lotes según la cantidad de la línea
                matching_lot_ids = matching_lot_ids[:int(self.quantity)]
            
            if matching_lot_ids:
                domain = [
                    ('location_id', 'child_of', location.id),
                    ('lot_id', 'in', matching_lot_ids),
                    ('quantity', '>', 0),
                ]
            else:
                # Si no encontramos nada, mostrar mensaje vacío
                domain = [
                    ('location_id', 'child_of', location.id),
                    ('id', '=', False),  # Dominio que no devuelve resultados
                ]
        
        # Obtener quants finales para contar
        matching_quants = Quant.search(domain)
        total_quants = len(matching_quants) if matching_quants else 0
        quants_with_lot = matching_quants.filtered(lambda q: q.lot_id)
        unique_lots = len(quants_with_lot.mapped('lot_id')) if quants_with_lot else 0
        total_quantity = sum(matching_quants.mapped('quantity')) if matching_quants else 0.0

        return {
            'type': 'ir.actions.act_window',
            'name': _('Series de %s (Cantidad línea: %s, Series: %s)') % (
                stock_product.display_name,
                self.quantity,
                unique_lots
            ),
            'res_model': 'stock.quant',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {
                'default_product_id': stock_product.id,
                'search_default_location_id': location.id,
                'subscription_id': self.subscription_id.id if self.subscription_id else False,
            },
            'limit': 10000,
        }

    @api.depends('product_id', 'subscription_id')
    def _compute_display_name(self):
        for line in self:
            parts = []
            if line.subscription_id:
                parts.append(line.subscription_id.name)
            if line.product_id:
                parts.append(line.product_id.display_name)
            line.display_name = ' - '.join(parts) if parts else _('Línea de suscripción')

    @api.depends('product_id', 'stock_product_id', 'subscription_id.location_id', 'location_id', 'quantity')
    def _compute_lot_serials(self):
        Quant = self.env['stock.quant'].sudo()
        for line in self:
            target_product = line.stock_product_id or line.product_id
            if not target_product:
                line.lot_serials_display = False
                continue
            location = line.location_id or line.subscription_id.location_id
            domain = [
                ('product_id', '=', target_product.id),
                ('lot_id', '!=', False),
                ('quantity', '>', 0),
            ]
            if location:
                domain.append(('location_id', 'child_of', location.id))
            quants = Quant.search(domain)
            lots = quants.mapped('lot_id')
            line.lot_serials_display = ', '.join(lots.mapped('name')) if lots else False

    def _update_usage(self, previous_qty, new_qty, sync_datetime=None, lot_quantities=None):
        self.ensure_one()
        # Si estamos consolidando líneas, no actualizar registros de uso
        if self.env.context.get('skip_usage_update') or self.env.context.get('consolidating_lines'):
            return
        if not sync_datetime:
            sync_datetime = fields.Datetime.now()
        if lot_quantities is not None:
            self._sync_usage_lots(lot_quantities, sync_datetime)
            return
        delta = new_qty - previous_qty
        if not delta:
            return
        if delta > 0:
            self._create_usage_entries(delta, sync_datetime)
        else:
            self._close_usage_entries(abs(delta), sync_datetime)

    def _get_usage_price(self, quantity=None):
        self.ensure_one()
        if self.is_component_line:
            return 0.0
        qty = quantity or self.quantity or 1.0
        return self.subscription_id._get_price_for_product(self.product_id, qty)

    def _sync_usage_lots(self, lot_quantities, sync_datetime):
        self.ensure_one()
        # Si estamos consolidando líneas, no actualizar registros de uso
        if self.env.context.get('skip_usage_update') or self.env.context.get('consolidating_lines'):
            return
        lot_map = {}
        for lot_data in lot_quantities or []:
            if not lot_data:
                continue
            if isinstance(lot_data, dict):
                lot_id = lot_data.get('lot_id')
                qty = lot_data.get('quantity', 0.0)
                in_date = lot_data.get('in_date')
            else:
                lot_id, qty = lot_data
                if hasattr(lot_id, 'id'):
                    lot_id = lot_id.id
                in_date = None
            if not qty:
                continue
            entry = lot_map.setdefault(lot_id or False, {'quantity': 0.0, 'dates': []})
            entry['quantity'] += qty
            if in_date:
                try:
                    entry['dates'].append(fields.Datetime.to_datetime(in_date))
                except Exception:
                    pass
        current_price = self._get_usage_price()
        if not float_round(current_price, precision_digits=2) == float_round(self.price_monthly, precision_digits=2):
            self.price_monthly = current_price
        open_usages = self.usage_ids.filtered(lambda u: not u.date_end)
        open_map = {}
        for usage in open_usages:
            key = usage.lot_id.id if usage.lot_id else False
            open_map.setdefault(key, [])
            open_map[key].append(usage)
        for usage_list in open_map.values():
            usage_list.sort(key=lambda u: u.date_start or fields.Datetime.from_string('1970-01-01 00:00:00'))
        processed = set()
        for lot_key, info in lot_map.items():
            target_qty = info['quantity']
            current_qty = sum(u.quantity for u in open_map.get(lot_key, []))
            processed.add(lot_key)
            lot_dates = info['dates']
            custom_date = min(lot_dates) if lot_dates else None
            
            # SOLO crear o cerrar registros si hay un cambio real en la cantidad
            # Si target_qty == current_qty, no hacer nada (evitar duplicados)
            if target_qty > current_qty:
                # Hay más cantidad, crear nuevos registros
                # PERO primero verificar que realmente no exista un registro activo
                # (doble verificación para evitar duplicados)
                Usage = self.env['subscription.subscription.usage'].sudo()
                domain_check = [
                    ('line_id', '=', self.id),
                    ('date_end', '=', False),
                ]
                if lot_key:
                    domain_check.append(('lot_id', '=', lot_key))
                else:
                    domain_check.append(('lot_id', '=', False))
                
                existing_check = Usage.search(domain_check, limit=1)
                if not existing_check:
                    # Solo crear si realmente no existe un registro activo
                    self._create_usage_entries(
                        target_qty - current_qty,
                        sync_datetime,
                        lot_id=lot_key,
                        current_price=current_price,
                        date_start=custom_date,
                    )
                else:
                    _logger.debug('⚠️ No se creó registro de uso para lote %s (línea %s): ya existe uno activo', 
                                 lot_key or 'sin lote', self.id)
            elif target_qty < current_qty:
                # Hay menos cantidad, cerrar registros existentes
                removal_date = self._get_removal_date(lot_key, sync_datetime, prefer_dates=lot_dates)
                self._close_usage_entries(
                    current_qty - target_qty,
                    sync_datetime,
                    usages=open_map.get(lot_key, []),
                    current_price=current_price,
                    date_end=removal_date,
                )
            # Si target_qty == current_qty, no hacer nada (ya está sincronizado)
        
        # Cerrar registros de lotes que ya no están en la lista
        for lot_key, usage_list in open_map.items():
            if lot_key in processed:
                continue
            qty_to_close = sum(u.quantity for u in usage_list)
            if qty_to_close:
                removal_date = self._get_removal_date(lot_key, sync_datetime)
                self._close_usage_entries(
                    qty_to_close,
                    sync_datetime,
                    usages=usage_list,
                    current_price=current_price,
                    date_end=removal_date,
                )

    def _get_removal_date(self, lot_id, sync_datetime, prefer_dates=None):
        location = self.location_id or self.subscription_id.location_id
        domain = [
            ('state', '=', 'done'),
            ('product_id', '=', (self.stock_product_id.id if self.stock_product_id else self.product_id.id)),
            ('qty_done', '>', 0),
            ('date', '<=', sync_datetime),
        ]
        child_ids = set()
        if location:
            child_ids = set(self.env['stock.location'].sudo().search([('id', 'child_of', location.id)]).ids)
            if child_ids:
                domain.append(('location_id', 'in', list(child_ids)))
        if lot_id:
            domain.append(('lot_id', '=', lot_id))
        else:
            domain.append(('lot_id', '=', False))
        candidates = self.env['stock.move.line'].sudo().search(domain, order='date desc', limit=10)
        for move_line in candidates:
            if location and move_line.location_dest_id.id in child_ids:
                continue
            return move_line.date or move_line.write_date or move_line.create_date or sync_datetime
        if prefer_dates:
            try:
                latest = max(prefer_dates)
                if latest:
                    return latest
            except Exception:
                pass
        return sync_datetime

    def _create_usage_entries(self, quantity, sync_datetime, lot_id=False, current_price=None, date_start=None):
        """Crea registros de uso solo si no existe uno activo para el mismo lote."""
        Usage = self.env['subscription.subscription.usage'].sudo()
        current_price = current_price if current_price is not None else self._get_usage_price(quantity)
        if not float_round(current_price, precision_digits=2) == float_round(self.price_monthly, precision_digits=2):
            self.price_monthly = current_price
        start_date = date_start if date_start else sync_datetime
        
        # Verificar si ya existe un registro activo para este lote y línea
        # Esto evita crear duplicados cuando se actualiza sin cambios
        domain = [
            ('line_id', '=', self.id),
            ('date_end', '=', False),  # Solo registros activos
        ]
        if lot_id:
            domain.append(('lot_id', '=', lot_id))
        else:
            domain.append(('lot_id', '=', False))
        
        existing_active = Usage.search(domain, limit=1)
        
        # SOLO crear si NO existe un registro activo
        # Si ya existe uno activo, no crear duplicado
        if not existing_active:
            Usage.create({
                'line_id': self.id,
                'date_start': start_date,
                'quantity': quantity,
                'price_monthly_snapshot': current_price,
                'lot_id': lot_id,
            })
        else:
            # Si ya existe un registro activo, solo actualizar la cantidad si es necesario
            # pero NO crear un nuevo registro
            _logger.debug('⚠️ No se creó registro de uso duplicado para línea %s, lote %s (ya existe uno activo)', 
                         self.id, lot_id or 'sin lote')

    def _close_usage_entries(self, quantity, sync_datetime, usages=None, current_price=None, date_end=None):
        Usage = self.env['subscription.subscription.usage'].sudo()
        remaining = quantity
        open_usages = usages or self.usage_ids.filtered(lambda u: not u.date_end).sorted('date_start')
        current_price = current_price if current_price is not None else self._get_usage_price()
        if not float_round(current_price, precision_digits=2) == float_round(self.price_monthly, precision_digits=2):
            self.price_monthly = current_price
        for usage in open_usages:
            if remaining <= 0:
                break
            usage_price = usage.price_monthly_snapshot or current_price
            if usage.quantity > remaining:
                # split usage: close portion and reduce remaining open quantity
                Usage.create({
                    'line_id': self.id,
                    'date_start': usage.date_start,
                    'date_end': date_end or sync_datetime,
                    'quantity': remaining,
                    'price_monthly_snapshot': usage_price,
                    'lot_id': usage.lot_id.id if usage.lot_id else False,
                })
                usage.write({
                    'quantity': usage.quantity - remaining,
                    'price_monthly_snapshot': usage_price,
                })
                remaining = 0
            else:
                usage.write({
                    'date_end': date_end or sync_datetime,
                    'price_monthly_snapshot': usage_price,
                })
                remaining -= usage.quantity
        if remaining > 0:
            start_dt = sync_datetime
            if self.subscription_id.start_date:
                start_dt = datetime.datetime.combine(self.subscription_id.start_date, datetime.time.min)
            Usage.create({
                'line_id': self.id,
                'date_start': start_dt,
                'date_end': date_end or sync_datetime,
                'quantity': remaining,
                'price_monthly_snapshot': current_price,
                'lot_id': False,
            })

    @api.depends('usage_ids.date_end')
    def _compute_usage_counts(self):
        for line in self:
            active = line.usage_ids.filtered(lambda u: not u.date_end)
            closed = line.usage_ids.filtered(lambda u: u.date_end)
            line.active_usage_count = len(active)
            line.closed_usage_count = len(closed)
    def _prepare_invoice_line_values(self, subscription):
        self.ensure_one()
        # Usar directamente el precio mensual sin ajustes por período
        price_unit = self.price_monthly
        return {
            'product_id': self.product_id.id,
            'name': self.display_name,
            'quantity': float_round(self.quantity, precision_digits=2),
            'price_unit': price_unit,
            'tax_ids': [(6, 0, self.product_id.taxes_id.ids)],
        }


class SubscriptionSubscriptionUsage(models.Model):
    _name = 'subscription.subscription.usage'
    _description = 'Registro de uso por ubicación'

    line_id = fields.Many2one('subscription.subscription.line', string='Línea de suscripción', required=True, ondelete='cascade')
    line_stock_display_name = fields.Char(string='Línea de suscripción', compute='_compute_line_stock_display_name', store=False)
    subscription_id = fields.Many2one(related='line_id.subscription_id', store=True, readonly=True)
    lot_id = fields.Many2one('stock.lot', string='Número de serie', readonly=True)
    date_start = fields.Datetime(string='Fecha de entrada', required=True)
    date_end = fields.Datetime(string='Fecha de salida')
    quantity = fields.Float(string='Cantidad', default=1.0)
    invoiced = fields.Boolean(string='Facturado', default=False)
    days_open = fields.Integer(string='Días activos', compute='_compute_usage_metrics', store=True)
    amount = fields.Monetary(string='Importe calculado', currency_field='currency_id', digits=(16, 0))
    price_monthly_snapshot = fields.Monetary(string='Precio mensual usado', currency_field='currency_id', digits=(16, 0))
    currency_id = fields.Many2one(related='line_id.currency_id', store=True, readonly=True)
    daily_rate = fields.Monetary(string='Tarifa diaria', currency_field='currency_id', compute='_compute_usage_metrics', store=False, digits=(16, 0))
    component_item_type = fields.Selection(
        related='line_id.component_item_type',
        string='Tipo componente',
        readonly=True,
        store=True,
    )
    component_line_product_id = fields.Many2one(
        related='line_id.product_id',
        string='Producto componente',
        readonly=True,
        store=True,
    )
    component_is_component_line = fields.Boolean(
        related='line_id.is_component_line',
        string='Es línea componente',
        readonly=True,
        store=True,
    )
    component_line_id = fields.Many2one(
        'subscription.subscription.line',
        related='line_id',
        string='Línea origen',
        readonly=True,
        store=True,
    )

    @api.onchange('date_start', 'date_end', 'line_id')
    def _onchange_dates(self):
        for usage in self:
            usage._compute_amount()

    @api.depends('date_start', 'date_end', 'quantity', 'line_id.price_monthly', 'price_monthly_snapshot')
    def _compute_usage_metrics(self):
        for usage in self:
            amount = 0.0
            days_open = 0
            daily_rate = 0.0
            if usage.date_start:
                end_dt = usage.date_end or fields.Datetime.now()
                if end_dt >= usage.date_start:
                    days_open = max((end_dt.date() - usage.date_start.date()).days + 1, 1)
                    monthly_price = usage.price_monthly_snapshot or usage.line_id.price_monthly
                    daily_rate = float_round((monthly_price or 0.0) / 30, precision_digits=2)
                    if usage.date_end:
                        amount = float_round(daily_rate * days_open * usage.quantity, precision_digits=2)
            usage.days_open = days_open
            usage.daily_rate = daily_rate
            usage.amount = amount

    def action_mark_invoiced(self):
        self.write({'invoiced': True})

    def _prepare_usage_invoice_line(self):
        self.ensure_one()
        return {
            'product_id': self.line_id.product_id.id,
            'name': self._get_description(),
            'quantity': 1.0,
            'price_unit': self.amount,
            'tax_ids': [(6, 0, self.line_id.product_id.taxes_id.ids)],
        }

    def _get_description(self):
        self.ensure_one()
        date_start = fields.Date.to_string(self.date_start.date()) if self.date_start else _('sin entrada')
        date_end = fields.Date.to_string(self.date_end.date()) if self.date_end else _('sin salida')
        return _('%s (%s - %s)') % (
            self.line_id.product_id.display_name,
            date_start,
            date_end,
        )

    @api.depends('line_id.subscription_id', 'line_id.product_id', 'line_id.stock_product_id')
    def _compute_line_stock_display_name(self):
        for usage in self:
            line = usage.line_id
            if not line:
                usage.line_stock_display_name = False
                continue
            parts = []
            if line.subscription_id:
                parts.append(line.subscription_id.name)
            product = line.stock_product_id or line.product_id
            if product:
                parts.append(product.display_name)
            usage.line_stock_display_name = ' - '.join(parts) if parts else line.display_name


class SubscriptionProductGrouped(models.Model):
    """Modelo para agrupar quants por producto en la vista de suscripción."""
    _name = 'subscription.product.grouped'
    _description = 'Productos agrupados por cantidad de seriales'
    _order = 'business_line_name asc, is_license asc, has_subscription desc, product_id, lot_id'

    subscription_id = fields.Many2one('subscription.subscription', string='Suscripción', required=True, ondelete='cascade', index=True)
    product_id = fields.Many2one('product.product', string='Producto', required=False, readonly=True, index=True, help='Producto físico o servicio. Si es una licencia, puede estar vacío.')
    lot_id = fields.Many2one('stock.lot', string='Serial', readonly=True, help='Serial individual (legado; usar lot_ids para agrupados)')
    lot_ids = fields.Many2many('stock.lot', 'subscription_product_grouped_lot_rel', 'grouped_id', 'lot_id', string='Seriales', readonly=True, help='Seriales de este servicio (para prorrateo por fecha ingreso/salida)')
    quantity = fields.Integer(string='Cantidad', readonly=True, help='Cantidad de seriales de este producto (solo para agrupados)')
    has_subscription = fields.Boolean(string='Tiene Suscripción', readonly=True, help='Indica si este serial tiene una suscripción asignada')
    subscription_service = fields.Many2one('product.product', string='Servicio de Suscripción', readonly=True, help='Servicio asignado al serial')
    # Campos para licencias
    is_license = fields.Boolean(string='Es Licencia', readonly=True, default=False, help='Indica si este registro representa una licencia')
    license_name = fields.Char(string='Nombre de Licencia', readonly=True, help='Nombre de la licencia cuando is_license=True')
    license_category = fields.Char(string='Categoría de Licencia', readonly=True, help='Categoría para agrupar licencias (ej: Office 365, Google Workspace)')
    license_type_id = fields.Many2one('product.license.type', string='Tipo de Licencia', readonly=True, help='Tipo de licencia asociado')
    # Campo computed para mostrar el nombre correcto (producto o licencia)
    product_display_name = fields.Char(string='Producto', compute='_compute_product_display_name', store=False, help='Nombre del producto o licencia para mostrar')
    
    @api.depends('product_id', 'is_license', 'license_name', 'license_category')
    def _compute_product_display_name(self):
        """Calcula el nombre a mostrar: producto si existe, o categoría de licencia si es licencia."""
        for record in self:
            try:
                if record.is_license:
                    # Para licencias, mostrar la categoría (ej: "Office 365") en lugar del nombre individual
                    if record.license_category:
                        record.product_display_name = str(record.license_category)
                    elif record.license_name:
                        record.product_display_name = str(record.license_name)
                    else:
                        record.product_display_name = 'Licencia'
                elif record.product_id:
                    # Asegurar que product_id es un registro válido y tiene display_name
                    try:
                        if hasattr(record.product_id, 'display_name') and record.product_id.display_name:
                            record.product_display_name = str(record.product_id.display_name)
                        elif hasattr(record.product_id, 'name') and record.product_id.name:
                            record.product_display_name = str(record.product_id.name)
                        else:
                            record.product_display_name = str(record.product_id) if record.product_id else ''
                    except Exception:
                        record.product_display_name = str(record.product_id) if record.product_id else ''
                else:
                    record.product_display_name = ''
            except Exception as e:
                # Si hay cualquier error, usar un valor por defecto
                record.product_display_name = 'Sin nombre'
    
    business_line_id = fields.Many2one(
        'product.business.line',
        string='Línea de negocio',
        compute='_compute_business_line_id',
        store=True,
        readonly=True,
        help='Línea de negocio del servicio de suscripción o del producto físico'
    )
    business_line_name = fields.Char(
        related='business_line_id.name',
        string='Nombre línea de negocio',
        store=True,
        readonly=True,
        help='Para ordenar alfabéticamente por línea de negocio.'
    )
    show_view_details = fields.Boolean(
        string='Mostrar Ver Detalles',
        compute='_compute_show_view_details',
        store=False,
        help='False para líneas de negocio que son solo servicios (MESA DE SERVICIOS, ADMINISTRACION Y SEGURIDAD INFORMATICA) que no agrupan equipos.'
    )

    @api.depends('business_line_id', 'business_line_id.name')
    def _compute_show_view_details(self):
        """Oculta "Ver Detalles" para servicios que no agrupan equipos/seriales."""
        _SERVICES_NO_DETAILS = ('MESA DE SERVICIOS', 'ADMINISTRACION Y SEGURIDAD INFORMATICA')
        names_upper = {n.strip().upper() for n in _SERVICES_NO_DETAILS}
        for record in self:
            if not record.business_line_id or not record.business_line_id.name:
                record.show_view_details = True
                continue
            bl_name = (record.business_line_id.name or '').strip().upper()
            record.show_view_details = bl_name not in names_upper

    def read(self, fields=None, load='_classic_read'):
        """Evita error al hacer clic en la línea cuando algún Many2one apunta a registro eliminado (_unknown)."""
        fnames = fields
        try:
            try:
                return super().read(fields=fnames, load=load)
            except TypeError:
                return super().read(fields=fnames)
        except AttributeError as e:
            if "'id'" not in str(e) and "'_unknown'" not in str(e):
                raise
            # Algún Many2one tiene referencia rota; leer campo a campo y sustituir valores inválidos.
            # Con load=None (web_read) el cliente espera Many2one como id (entero), no (id, nombre).
            use_classic = (load == '_classic_read')
            result = []
            fnames = fnames or list(self._fields.keys())
            for record in self:
                row = {}
                for fname in fnames:
                    if fname not in self._fields:
                        continue
                    try:
                        val = record[fname]
                        f = self._fields[fname]
                        if f.type == 'many2one':
                            if val and getattr(val, 'id', None) is not None:
                                row[fname] = (val.id, val.display_name or '') if use_classic else val.id
                            else:
                                row[fname] = (False, False) if use_classic else False
                        elif f.type in ('one2many', 'many2many'):
                            row[fname] = val.ids if val else []
                        else:
                            row[fname] = val
                    except (AttributeError, TypeError):
                        f = self._fields.get(fname)
                        if f and f.type == 'many2one':
                            row[fname] = (False, False) if use_classic else False
                        elif f and f.type in ('one2many', 'many2many'):
                            row[fname] = []
                        else:
                            row[fname] = False
                result.append(row)
            return result

    cost = fields.Monetary(
        string='Costo',
        compute='_compute_cost',
        store=True,
        readonly=True,
        currency_field='cost_currency_id',
        digits=(16, 2),
        help='Costo total (en COP o USD según corresponda; solo COP se suma en Total Mensual)'
    )
    cost_currency_id = fields.Many2one(
        'res.currency',
        string='Moneda del costo',
        compute='_compute_cost',
        store=True,
        readonly=True,
        help='Moneda en que está expresado el Costo (COP o USD). Solo los costos en COP entran en Total Mensual.',
    )
    proyectado = fields.Monetary(
        string='Proyectado',
        compute='_compute_proyectado',
        store=False,
        readonly=True,
        currency_field='currency_id',
        digits=(16, 2),
        help='Total proyectado por línea: licencias con TRM del mes en curso; servicios/equipos igual al Costo.'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        related='subscription_id.currency_id',
        readonly=True,
        store=True
    )
    location_id = fields.Many2one('stock.location', string='Ubicación', readonly=True)

    @api.depends('product_id', 'product_id.business_line_id', 'product_id.product_tmpl_id.business_line_id', 'is_license', 'license_type_id')
    def _compute_business_line_id(self):
        """Calcula la línea de negocio desde el product_id (servicio o producto físico) o desde la licencia."""
        for record in self:
            # Si es una licencia, intentar obtener la línea de negocio
            if record.is_license and record.license_type_id:
                # Si la licencia tiene un product_id asociado (buscado por nombre), usar su línea de negocio
                if record.product_id:
                    if 'product.business.line' in self.env:
                        if hasattr(record.product_id, 'business_line_id') and record.product_id.business_line_id:
                            record.business_line_id = record.product_id.business_line_id
                        elif hasattr(record.product_id, 'product_tmpl_id') and hasattr(record.product_id.product_tmpl_id, 'business_line_id'):
                            record.business_line_id = record.product_id.product_tmpl_id.business_line_id
                        else:
                            record.business_line_id = False
                    else:
                        record.business_line_id = False
                else:
                    # Si no hay producto asociado, buscar un producto de servicio con el nombre de la licencia
                    # para obtener su línea de negocio
                    if 'product.business.line' in self.env and record.license_name:
                        product = self.env['product.product'].search([
                            ('type', '=', 'service'),
                            ('name', 'ilike', record.license_name),
                        ], limit=1)
                        if product:
                            if hasattr(product, 'business_line_id') and product.business_line_id:
                                record.business_line_id = product.business_line_id
                            elif hasattr(product, 'product_tmpl_id') and hasattr(product.product_tmpl_id, 'business_line_id'):
                                record.business_line_id = product.product_tmpl_id.business_line_id
                            else:
                                record.business_line_id = False
                        else:
                            record.business_line_id = False
                    else:
                        record.business_line_id = False
                continue
            
            if not record.product_id:
                record.business_line_id = False
                continue
            # Verificar si el modelo product.business.line existe
            if 'product.business.line' in self.env:
                # Intentar obtener desde product_id directamente
                if hasattr(record.product_id, 'business_line_id') and record.product_id.business_line_id:
                    record.business_line_id = record.product_id.business_line_id
                # Si no, intentar desde product_tmpl_id
                elif hasattr(record.product_id, 'product_tmpl_id') and hasattr(record.product_id.product_tmpl_id, 'business_line_id'):
                    record.business_line_id = record.product_id.product_tmpl_id.business_line_id
                else:
                    record.business_line_id = False
            else:
                record.business_line_id = False

    pricelist_id = fields.Many2one(
        'product.pricelist',
        string='Lista de precios',
        compute='_compute_pricelist_id',
        store=True,
        readonly=True,
        help='Lista de precios del cliente usada para calcular el costo'
    )

    @api.depends('subscription_id', 'subscription_id.partner_id', 'subscription_id.partner_id.property_product_pricelist')
    def _compute_pricelist_id(self):
        """Obtiene la lista de precios del cliente."""
        for record in self:
            if record.subscription_id and record.subscription_id.partner_id:
                record.pricelist_id = record.subscription_id.partner_id.property_product_pricelist
            else:
                record.pricelist_id = False

    @api.depends('subscription_id', 'product_id', 'quantity', 'lot_id', 'lot_id.entry_date', 'lot_id.exit_date', 'lot_id.lot_supply_line_ids', 'lot_id.lot_supply_line_ids.has_cost', 'lot_id.lot_supply_line_ids.cost', 'lot_ids', 'lot_ids.entry_date', 'lot_ids.exit_date', 'lot_ids.lot_supply_line_ids', 'lot_ids.lot_supply_line_ids.has_cost', 'lot_ids.lot_supply_line_ids.cost', 'subscription_id.partner_id', 'subscription_id.partner_id.property_product_pricelist', 'subscription_id.plan_id', 'pricelist_id', 'has_subscription', 'is_license', 'license_type_id', 'license_category', 'subscription_id.location_id', 'subscription_id.reference_year', 'subscription_id.reference_month')
    def _compute_cost(self):
        """Calcula el costo basado en la lista de precios del cliente y la cantidad.
        Solo busca precios recurrentes si el producto tiene una suscripción asignada (has_subscription=True).
        Los productos sin suscripción usan el precio estándar de la lista de precios.
        Las licencias usan el costo directamente de amount_local."""
        for record in self:
            # Inicializar por defecto (cost_currency_id: solo COP se suma en Total Mensual)
            record.cost = 0.0
            record.cost_currency_id = record.subscription_id.currency_id.id if record.subscription_id else False
            
            # Si es una licencia: costo = precio unitario (TRM mes vencido) × cantidad de la línea (record.quantity)
            if record.is_license:
                if not record.subscription_id or not record.license_category:
                    continue
                if not record.quantity:
                    record.cost = 0.0
                    record.cost_currency_id = record.subscription_id.currency_id.id if record.subscription_id else False
                    continue
                try:
                    pricelist = record.pricelist_id
                    if not pricelist and record.subscription_id.partner_id:
                        pricelist = record.subscription_id.partner_id.property_product_pricelist
                    if not pricelist:
                        _logger.warning('⚠️ No hay lista de precios para calcular costo de licencia: %s', record.license_category)
                        continue
                    if 'license.assignment' not in self.env or 'license.trm' not in self.env:
                        continue
                    license_domain = [
                        ('partner_id', '=', record.subscription_id.partner_id.id),
                        ('state', '=', 'active'),
                    ]
                    if record.subscription_id.location_id:
                        license_domain.append(('location_id', '=', record.subscription_id.location_id.id))
                    active_licenses = self.env['license.assignment'].search(license_domain)
                    total_cost = 0.0
                    trm_rate = 0.0
                    license_cost_in_usd = False  # True si hay precios en USD sin TRM (no sumar en Total Mensual)
                    if 'license.trm' in self.env:
                        trm_model = self.env['license.trm']
                        sub = record.subscription_id
                        if sub.reference_year and sub.reference_month and 1 <= sub.reference_month <= 12:
                            _m = int(sub.reference_month) + 1
                            _y = int(sub.reference_year)
                            if _m > 12:
                                _m = 1
                                _y += 1
                            trm_date = datetime.date(_y, _m, 1)
                        else:
                            now_user = fields.Datetime.context_timestamp(sub, fields.Datetime.now())
                            today_user = (now_user.date() if hasattr(now_user, 'date') else fields.Date.today())
                            first_current = datetime.date(today_user.year, today_user.month, 1)
                            trm_date = first_current + relativedelta(months=1)
                        trm_rate = trm_model.get_trm_for_date(trm_date) or 0.0
                    for license_assignment in active_licenses:
                        if not license_assignment.license_id or not license_assignment.license_id.product_id:
                            continue
                        license_category_name = (license_assignment.license_id.name and license_assignment.license_id.name.name) or 'Sin Categoría'
                        if license_category_name != record.license_category:
                            continue
                        product = license_assignment.license_id.product_id
                        try:
                            unit_price = record.subscription_id._get_price_for_product(product, 1.0) or 0.0
                            if unit_price <= 0.0:
                                continue
                            price_currency = None
                            if 'sale.subscription.pricing' in self.env and record.subscription_id.plan_id:
                                try:
                                    PricingModel = self.env['sale.subscription.pricing']
                                    pricing_domain = [
                                        ('pricelist_id', '=', pricelist.id),
                                        ('plan_id', '=', record.subscription_id.plan_id.id),
                                    ]
                                    if 'product_template_id' in PricingModel._fields:
                                        pricing_domain.append(('product_template_id', '=', product.product_tmpl_id.id))
                                        pricing_rec = PricingModel.search(pricing_domain, limit=1)
                                    elif 'product_tmpl_id' in PricingModel._fields:
                                        pricing_domain.append(('product_tmpl_id', '=', product.product_tmpl_id.id))
                                        pricing_rec = PricingModel.search(pricing_domain, limit=1)
                                    else:
                                        pricing_rec = self.env['sale.subscription.pricing'].browse([])
                                    if not pricing_rec and 'product_id' in PricingModel._fields:
                                        pricing_domain = [
                                            ('pricelist_id', '=', pricelist.id),
                                            ('plan_id', '=', record.subscription_id.plan_id.id),
                                            ('product_id', '=', product.id),
                                        ]
                                        pricing_rec = PricingModel.search(pricing_domain, limit=1)
                                    if pricing_rec and len(pricing_rec) > 0 and hasattr(pricing_rec[0], 'currency_id') and pricing_rec[0].currency_id:
                                        price_currency = pricing_rec[0].currency_id
                                except Exception:
                                    pass
                            if not price_currency:
                                price_currency = pricelist.currency_id
                            unit_price_cop = unit_price
                            if price_currency and price_currency.name == 'USD':
                                if trm_rate and trm_rate > 0:
                                    unit_price_cop = unit_price * trm_rate
                                else:
                                    license_cost_in_usd = True
                            assignment_qty = float(license_assignment.quantity or 0.0)
                            total_cost += unit_price_cop * assignment_qty
                        except Exception as e:
                            _logger.error('❌ Error obteniendo precio para producto %s: %s', product.display_name, str(e))
                            continue
                    record.cost = float_round(total_cost, precision_digits=2) if total_cost > 0 else 0.0
                    if license_cost_in_usd and total_cost > 0:
                        usd_curr = self.env.ref('base.USD', raise_if_not_found=False) or self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
                        record.cost_currency_id = usd_curr.id if usd_curr else record.subscription_id.currency_id.id
                    else:
                        record.cost_currency_id = record.subscription_id.currency_id.id
                    if total_cost > 0:
                        _logger.info('✅ Costo licencia %s: suma por asignación = %s %s',
                                     record.license_category, record.cost, 'USD' if license_cost_in_usd else 'COP')
                except Exception as e:
                    _logger.error('❌ Error calculando costo de licencia %s: %s', record.license_category, str(e))
                    record.cost = 0.0
                    record.cost_currency_id = record.subscription_id.currency_id.id if record.subscription_id else False
                continue
            
            # Validaciones básicas para productos
            if not record.subscription_id or not record.product_id:
                continue
            
            # Si quantity es 0 o None, costo es 0
            if not record.quantity or record.quantity <= 0:
                continue
            
            try:
                # Validar que subscription_id existe
                if not record.subscription_id.exists():
                    continue
                
                # Obtener la lista de precios
                pricelist = record.pricelist_id
                if not pricelist and record.subscription_id.partner_id:
                    pricelist = record.subscription_id.partner_id.property_product_pricelist
                
                # Precio mensual unitario (para 1 unidad)
                try:
                    price_monthly = record.subscription_id._get_price_for_product(
                        record.product_id,
                        1.0
                    ) or 0.0
                except Exception as e:
                    _logger.error('❌ Error obteniendo precio para producto %s (ID: %s): %s',
                                  record.product_id.display_name, record.product_id.id, str(e), exc_info=True)
                    price_monthly = record.product_id.lst_price or 0.0
                
                # Prorrateo por días: productos (no licencias) con lot_ids/lot_id.
                # Misma fórmula que "Ver Detalles" (Costo Días En Sitio): costo = suma de (costo_diario × días_servicio) por serial,
                # con costo_diario = (costo_renting_base + costo_adicional) / días_mes, para que el total coincida con el detalle.
                lots_for_prorate = record.lot_ids or (record.lot_id if record.lot_id else self.env['stock.lot'])
                use_prorated = (
                    record.has_subscription
                    and not record.is_license
                    and lots_for_prorate
                )
                if use_prorated and lots_for_prorate:
                    now_utc = fields.Datetime.now()
                    now_user = fields.Datetime.context_timestamp(record.subscription_id, now_utc)
                    today_user = (now_user.date() if hasattr(now_user, 'date') else fields.Date.today())
                    ref_year = record.subscription_id.reference_year if record.subscription_id else None
                    ref_month = record.subscription_id.reference_month if record.subscription_id else None
                    if ref_year and ref_month and 1 <= ref_month <= 12:
                        year, month = int(ref_year), int(ref_month)
                    else:
                        year, month = today_user.year, today_user.month
                    days_in_month = calendar.monthrange(year, month)[1]
                    current_day = min(int(today_user.day), days_in_month) if (year, month) == (today_user.year, today_user.month) else days_in_month

                    def _lot_additional_cost(lot):
                        if not lot or not hasattr(lot, 'lot_supply_line_ids'):
                            return 0.0
                        lines_with_cost = lot.lot_supply_line_ids.filtered(lambda l: l.has_cost)
                        return sum(lines_with_cost.mapped('cost')) or 0.0

                    total_cost = 0.0
                    for lot in lots_for_prorate:
                        entry_display, lot_exit_display = record.subscription_id._lot_entry_exit_for_display(lot)
                        entry = record.subscription_id._lot_date_for_billable(entry_display)
                        exit_ = record.subscription_id._lot_date_for_billable(lot_exit_display)
                        if entry is None and exit_ is None:
                            days_used = current_day
                        elif entry and exit_ and entry.year == year and entry.month == month and exit_.year == year and exit_.month == month:
                            days_used = max(0, exit_.day - entry.day + 1)
                        elif entry and entry.year == year and entry.month == month:
                            days_used = max(0, current_day - entry.day + 1)
                        elif exit_ and exit_.year == year and exit_.month == month:
                            days_used = max(0, exit_.day)
                        else:
                            days_used = current_day if (year, month) == (today_user.year, today_user.month) else days_in_month
                        additional = _lot_additional_cost(lot)
                        total_monthly_lot = (price_monthly or 0.0) + additional
                        cost_daily_lot = (total_monthly_lot / float(days_in_month)) if days_in_month else 0.0
                        cost_to_date_lot = cost_daily_lot * float(days_used)
                        total_cost += cost_to_date_lot
                    record.cost = float_round(total_cost, precision_digits=2)
                    record.cost_currency_id = record.subscription_id.currency_id.id
                    _logger.info('💰 Prorrateo producto %s: %s seriales, mes %s/%s, costo total=%s (suma Costo Días En Sitio)',
                                 record.product_id.display_name, len(lots_for_prorate), month, year, record.cost)
                else:
                    # Sin prorrateo: costo = precio mensual * cantidad
                    price = record.subscription_id._get_price_for_product(
                        record.product_id,
                        float(record.quantity)
                    ) or price_monthly * float(record.quantity)
                    record.cost = float_round(price * float(record.quantity), precision_digits=2)
                    record.cost_currency_id = record.subscription_id.currency_id.id
                    _logger.info('💰 Costo producto %s: %s (precio: %s, cantidad: %s)',
                                record.product_id.display_name, record.cost, price, record.quantity)
            except Exception:
                # Si hay cualquier error, dejar en 0
                record.cost = 0.0
                record.cost_currency_id = record.subscription_id.currency_id.id if record.subscription_id else False

    @api.depends('subscription_id', 'product_id', 'quantity', 'is_license', 'license_category', 'subscription_id.location_id', 'cost',
                 'lot_ids', 'lot_id', 'has_subscription')
    def _compute_proyectado(self):
        """Proyectado por línea: licencias = precio unitario (TRM mes en curso) × cantidad de la línea; equipos/servicios = total mes completo (precio unitario × cantidad)."""
        today = fields.Date.context_today(self)
        trm_date_current_month = datetime.date(today.year, today.month, 1)

        for record in self:
            if record.is_license:
                record.proyectado = record._compute_proyectado_license(trm_date_current_month)
            else:
                record.proyectado = record._compute_proyectado_equipment_service()

    def _compute_proyectado_license(self, trm_date):
        """Proyectado para licencias: precio unitario en COP (TRM mes en curso) × cantidad de la línea (record.quantity)."""
        self.ensure_one()
        if not self.subscription_id or not self.license_category or not self.quantity:
            return 0.0
        try:
            pricelist = self.pricelist_id
            if not pricelist and self.subscription_id.partner_id:
                pricelist = self.subscription_id.partner_id.property_product_pricelist
            if not pricelist:
                return 0.0
            if 'license.assignment' not in self.env or 'license.trm' not in self.env:
                return self.cost or 0.0
            trm_model = self.env['license.trm']
            trm_rate = trm_model.get_trm_for_date(trm_date) or 0.0
            if not trm_rate or trm_rate <= 0:
                return self.cost or 0.0
            license_domain = [
                ('partner_id', '=', self.subscription_id.partner_id.id),
                ('state', '=', 'active'),
            ]
            if self.subscription_id.location_id:
                license_domain.append(('location_id', '=', self.subscription_id.location_id.id))
            active_licenses = self.env['license.assignment'].search(license_domain)
            # Proyectado = suma por cada asignación de la categoría: (precio unit. COP con TRM mes curso × cantidad asignación)
            total_proyectado = 0.0
            for license_assignment in active_licenses:
                if not license_assignment.license_id or not license_assignment.license_id.product_id:
                    continue
                license_category_name = (license_assignment.license_id.name and license_assignment.license_id.name.name) or 'Sin Categoría'
                if license_category_name != self.license_category:
                    continue
                product = license_assignment.license_id.product_id
                try:
                    unit_price = self.subscription_id._get_price_for_product(product, 1.0) or 0.0
                    if unit_price <= 0.0:
                        continue
                    price_currency = None
                    if 'sale.subscription.pricing' in self.env and self.subscription_id.plan_id:
                        try:
                            PricingModel = self.env['sale.subscription.pricing']
                            pricing_domain = [
                                ('pricelist_id', '=', pricelist.id),
                                ('plan_id', '=', self.subscription_id.plan_id.id),
                            ]
                            if 'product_template_id' in PricingModel._fields:
                                pricing_domain.append(('product_template_id', '=', product.product_tmpl_id.id))
                                pricing_rec = PricingModel.search(pricing_domain, limit=1)
                            elif 'product_tmpl_id' in PricingModel._fields:
                                pricing_domain.append(('product_tmpl_id', '=', product.product_tmpl_id.id))
                                pricing_rec = PricingModel.search(pricing_domain, limit=1)
                            else:
                                pricing_rec = self.env['sale.subscription.pricing'].browse([])
                            if not pricing_rec and 'product_id' in PricingModel._fields:
                                pricing_domain = [
                                    ('pricelist_id', '=', pricelist.id),
                                    ('plan_id', '=', self.subscription_id.plan_id.id),
                                    ('product_id', '=', product.id),
                                ]
                                pricing_rec = PricingModel.search(pricing_domain, limit=1)
                            if pricing_rec and len(pricing_rec) > 0 and hasattr(pricing_rec[0], 'currency_id') and pricing_rec[0].currency_id:
                                price_currency = pricing_rec[0].currency_id
                        except Exception:
                            pass
                    if not price_currency:
                        price_currency = pricelist.currency_id
                    unit_price_cop = unit_price
                    if price_currency and price_currency.name == 'USD':
                        unit_price_cop = unit_price * trm_rate
                    assignment_qty = float(license_assignment.quantity or 0.0)
                    total_proyectado += unit_price_cop * assignment_qty
                except Exception:
                    continue
            return float_round(total_proyectado, precision_digits=2) if total_proyectado > 0 else (self.cost or 0.0)
        except Exception:
            return self.cost or 0.0

    def _compute_proyectado_equipment_service(self):
        """Proyectado para equipos/servicios = suma de la columna 'Costo Renting' (y costo adicional por serial) de cada serial del grupo; es decir, total mes completo por serial."""
        self.ensure_one()
        if not self.subscription_id:
            return 0.0
        try:
            lots = self.lot_ids or (self.env['stock.lot'].browse([self.lot_id.id]) if self.lot_id else self.env['stock.lot'])
            if lots:
                total = 0.0
                for lot in lots:
                    service_product = getattr(lot, 'subscription_service_product_id', None) or self.product_id
                    if not service_product:
                        continue
                    monthly = self.subscription_id._get_price_for_product(service_product, 1.0) or 0.0
                    additional = 0.0
                    if getattr(lot, 'lot_supply_line_ids', None):
                        lines_with_cost = lot.lot_supply_line_ids.filtered(lambda l: getattr(l, 'has_cost', False))
                        additional = sum(lines_with_cost.mapped('cost')) or 0.0
                    total += monthly + additional
                return float_round(total, precision_digits=2)
            # Sin seriales (ej. servicio sin equipos): precio unitario × cantidad
            if self.product_id and self.quantity:
                price_monthly = self.subscription_id._get_price_for_product(self.product_id, 1.0) or 0.0
                return float_round(price_monthly * float(self.quantity), precision_digits=2)
            return 0.0
        except Exception:
            return self.cost or 0.0

    def action_view_serials(self):
        """Abre una vista con los seriales de este producto o servicio de suscripción.
        También funciona para licencias, mostrando los seriales que tienen asignadas esas licencias."""
        self.ensure_one()
        if not self.subscription_id or not self.subscription_id.location_id:
            raise UserError(_('No hay ubicación definida para mostrar las series.'))
        
        Quant = self.env['stock.quant']
        
        # Si es una licencia, mostrar los seriales que tienen asignadas esas licencias
        if self.is_license:
            if not self.license_category:
                raise UserError(_('No hay categoría de licencia para mostrar las series.'))
            
            # Buscar todas las asignaciones de licencias activas para este cliente y ubicación
            license_domain = [
                ('partner_id', '=', self.subscription_id.partner_id.id),
                ('state', '=', 'active'),
            ]
            if self.subscription_id.location_id:
                license_domain.append(('location_id', '=', self.subscription_id.location_id.id))
            
            if 'license.assignment' not in self.env:
                raise UserError(_('El módulo de licencias no está disponible.'))
            
            active_licenses = self.env['license.assignment'].search(license_domain)
            
            # Filtrar por categoría y construir una fila por unidad, con el nombre del tipo de licencia (producto) en cada fila
            # Así si ANTIVIRUS tiene GravityZone Enterprise (27) y GravityZone Enterprise Server (1), se ve cada tipo en su fila.
            Line = self.env['subscription.license.serial.line']
            location_id = self.subscription_id.location_id.id if self.subscription_id.location_id else False
            category_name = self.license_category or ''
            line_vals = []
            for license_assignment in active_licenses:
                if not license_assignment.license_id:
                    continue
                license_category_name = (license_assignment.license_id.name and license_assignment.license_id.name.name) or 'Sin Categoría'
                if license_category_name != category_name:
                    continue
                product = license_assignment.license_id.product_id
                service_name = (product.display_name or product.name or category_name) if product else category_name
                qty = int(license_assignment.quantity or 0)
                if qty <= 0:
                    continue
                # Equipos asignados a esta asignación (esta licencia concreta)
                equipment_lots = []
                if 'license.equipment' in self.env:
                    equipment_records = self.env['license.equipment'].search([
                        ('assignment_id', '=', license_assignment.id),
                        ('state', '=', 'assigned'),
                        ('lot_id', '!=', False),
                    ])
                    equipment_lots = [e.lot_id for e in equipment_records if e.lot_id]
                # Filas con serial asignado: una por cada equipo (lote) asignado a esta licencia
                if equipment_lots:
                    quants = Quant.search([
                        ('location_id', 'child_of', self.subscription_id.location_id.id),
                        ('lot_id', 'in', [l.id for l in equipment_lots]),
                        ('quantity', '>', 0),
                    ])
                    # Un registro por lote (evitar duplicar si el mismo lote tiene varios quants)
                    seen_lot_ids = set()
                    for q in quants:
                        if not q.lot_id or q.lot_id.id in seen_lot_ids:
                            continue
                        seen_lot_ids.add(q.lot_id.id)
                        line_vals.append({
                            'location_id': q.location_id.id if q.location_id else location_id,
                            'product_id': q.product_id.id if q.product_id else (product.id if product else False),
                            'lot_id': q.lot_id.id,
                            'inventory_plate': getattr(q, 'inventory_plate', None) or (q.lot_id.inventory_plate if q.lot_id else ''),
                            'license_service_name': service_name,
                            'assignment_group': 'assigned',
                        })
                # Filas no asignadas para esta licencia: cantidad - equipos ya listados
                num_assigned = len(equipment_lots) if equipment_lots else 0
                missing = qty - num_assigned
                for _dummy in range(missing):
                    line_vals.append({
                        'location_id': location_id,
                        'product_id': product.id if product else False,
                        'license_service_name': service_name,
                        'assignment_group': 'unassigned',
                    })
            if not line_vals:
                line_vals.append({
                    'location_id': location_id,
                    'license_service_name': category_name,
                    'assignment_group': 'unassigned',
                })
            lines = Line.create(line_vals)
            return {
                'type': 'ir.actions.act_window',
                'name': _('Series con licencias %s') % self.license_category,
                'res_model': 'subscription.license.serial.line',
                'view_mode': 'list',
                'domain': [('id', 'in', lines.ids)],
                'context': {'create': False, 'edit': False, 'delete': False},
            }

        # EQUIPOS / SERVICIOS (no licencias)
        # Importante: el facturable en vivo puede incluir lotes que ya salieron del cliente (sin stock.quant en ubicación).
        # Por eso "Ver Detalles" NO debe depender solo de stock.quant; generamos una lista (transiente) desde los lotes.
        lots = (self.lot_ids or self.env['stock.lot'])
        if self.quantity and lots and len(lots) > int(self.quantity):
            lots = lots[:int(self.quantity)]

        # Determinar mes/año igual que el facturable: reference_* si existe; si no, mes actual (zona usuario)
        now_utc = fields.Datetime.now()
        now_user = fields.Datetime.context_timestamp(self.subscription_id, now_utc)
        today_user = (now_user.date() if hasattr(now_user, 'date') else fields.Date.today())

        if self.subscription_id.reference_year and self.subscription_id.reference_month and 1 <= self.subscription_id.reference_month <= 12:
            year = int(self.subscription_id.reference_year)
            month = int(self.subscription_id.reference_month)
        else:
            year = int(today_user.year)
            month = int(today_user.month)

        days_in_month = calendar.monthrange(year, month)[1]
        first_day = datetime.date(year, month, 1)
        last_day = datetime.date(year, month, days_in_month)
        if (year, month) == (today_user.year, today_user.month):
            current_day = min(int(today_user.day), int(days_in_month))
        else:
            current_day = int(days_in_month)
        _month_names = (
            'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
            'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
        )
        month_display = f'{_month_names[month - 1]} {year}' if 1 <= month <= 12 else ''

        lot_sel = self.env['stock.lot']._fields.get('reining_plazo')
        sel_dict = dict(lot_sel.selection) if lot_sel and getattr(lot_sel, 'selection', None) else {}

        price_monthly = self.subscription_id._get_price_for_product(self.product_id, 1.0) if self.product_id else 0.0

        def _lot_additional_cost(lot):
            if not lot or not hasattr(lot, 'lot_supply_line_ids'):
                return 0.0
            lines_with_cost = lot.lot_supply_line_ids.filtered(lambda l: l.has_cost)
            return sum(lines_with_cost.mapped('cost')) or 0.0

        Line = self.env['subscription.equipment.serial.line']
        line_vals = []
        for lot in lots:
            # Usar fechas "para esta suscripción": si el lote salió de esta suscripción usamos las congeladas
            entry_display, lot_exit_display = self.subscription_id._lot_entry_exit_for_display(lot)
            entry = self.subscription_id._lot_date_for_billable(entry_display)
            exit_ = self.subscription_id._lot_date_for_billable(lot_exit_display)
            if entry is None and exit_ is None:
                days_used = current_day
            elif entry and exit_ and entry.year == year and entry.month == month and exit_.year == year and exit_.month == month:
                days_used = max(0, exit_.day - entry.day + 1)
            elif entry and entry.year == year and entry.month == month:
                days_used = max(0, current_day - entry.day + 1)
            elif exit_ and exit_.year == year and exit_.month == month:
                days_used = max(0, exit_.day)
            else:
                days_used = current_day if (year, month) == (today_user.year, today_user.month) else days_in_month

            additional = _lot_additional_cost(lot)
            total_monthly = (price_monthly or 0.0) + additional
            cost_daily_lot = round((total_monthly / float(days_in_month)), 2) if days_in_month else 0.0
            cost_to_date = round(cost_daily_lot * float(days_used), 2)
            # Días totales en sitio = desde activación hasta hoy (o hasta fecha salida si ya salió), no el total del contrato
            days_total_on_site = 0
            if entry:
                today_d = today_user if isinstance(today_user, datetime.date) else datetime.date(today_user.year, today_user.month, today_user.day)
                end = (exit_ if exit_ and exit_ < today_d else today_d)
                if end >= entry:
                    days_total_on_site = max(0, (end - entry).days + 1)

            plazo_label = (sel_dict.get(lot.reining_plazo) or lot.reining_plazo or '') if lot else ''
            product_name = lot.product_id.display_name if getattr(lot, 'product_id', None) else (self.product_id.display_name if self.product_id else '')

            line_vals.append({
                'subscription_id': self.subscription_id.id,
                'location_id': self.subscription_id.location_id.id,
                'lot_id': lot.id if lot else False,
                'product_name': product_name or '',
                'inventory_plate': getattr(lot, 'inventory_plate', None) or '',
                'lot_name': lot.name or '',
                'cost_renting': price_monthly or 0.0,
                'entry_date': entry_display,
                'exit_date': lot_exit_display,
                'reining_plazo': plazo_label,
                'days_total_on_site': days_total_on_site,
                'days_total_month': days_in_month,
                'current_day_of_month': current_day,
                'month_display': month_display,
                'days_in_service': int(days_used),
                'cost_daily': cost_daily_lot or 0.0,
                'cost_to_date': cost_to_date or 0.0,
                'currency_id': self.subscription_id.currency_id.id if self.subscription_id.currency_id else self.env.company.currency_id.id,
            })

        lines = Line.create(line_vals) if line_vals else Line.browse([])
        return {
            'type': 'ir.actions.act_window',
            'name': _('Detalles - %s') % (self.product_display_name or self.product_id.display_name),
            'res_model': 'subscription.equipment.serial.line',
            'view_mode': 'list',
            'views': [(self.env.ref('subscription_nocount.view_subscription_equipment_serial_line_tree').id, 'list')],
            'domain': [('id', 'in', lines.ids)],
            'context': {'create': False, 'edit': False, 'delete': False},
        }

    def _prepare_invoice_line_values(self, subscription):
        """Prepara los valores para crear una línea de factura desde un producto agrupado."""
        self.ensure_one()
        # Usar el costo total calculado, dividido por la cantidad para obtener el precio unitario
        # O usar el precio unitario directamente si está disponible
        price_unit = self.cost / float(self.quantity) if self.quantity > 0 else 0.0
        
        # Construir el nombre de la línea
        name_parts = []
        if self.has_subscription:
            name_parts.append(_('Suscripción: %s') % self.product_id.display_name)
        else:
            name_parts.append(self.product_id.display_name)
        
        if self.quantity > 1:
            name_parts.append(_('(Cantidad: %s)') % self.quantity)
        
        name = ' - '.join(name_parts) if name_parts else self.product_id.display_name
        
        return {
            'product_id': self.product_id.id,
            'name': name,
            'quantity': float_round(float(self.quantity), precision_digits=2),
            'price_unit': float_round(price_unit, precision_digits=2),
            'tax_ids': [(6, 0, self.product_id.taxes_id.ids)],
        }


class SubscriptionLicenseSerialLine(models.TransientModel):
    """Líneas de la vista «Series con licencias» cuando no hay seriales asignados.
    Muestra tantas filas como cantidad (ej. 50 para KASEYA) con la misma estructura que stock.quant."""
    _name = 'subscription.license.serial.line'
    _description = 'Línea de serie/licencia (vista placeholder)'

    location_id = fields.Many2one('stock.location', string='Ubicación')
    product_id = fields.Many2one('product.product', string='Producto')
    lot_id = fields.Many2one('stock.lot', string='Número de serie/lote')
    inventory_plate = fields.Char(string='Placa de Inventario')
    license_service_name = fields.Char(string='Licencia/Servicio Asignado')
    assignment_group = fields.Selection(
        [
            ('assigned', 'Asignada'),
            ('unassigned', 'No asignada'),
        ],
        string='Estado asignación',
        help='Para agrupar por licencias asignadas y no asignadas',
    )


class SubscriptionEquipmentSerialLine(models.TransientModel):
    """Detalle de equipos/servicios para "Ver Detalles" en facturable en vivo.
    Se genera desde lotes (incluye los que ya salieron del cliente y no tienen stock.quant en ubicación)."""
    _name = 'subscription.equipment.serial.line'
    _description = 'Detalle equipo (vista transiente)'
    _order = 'product_name, inventory_plate, lot_name'

    subscription_id = fields.Many2one('subscription.subscription', string='Suscripción', readonly=True)
    location_id = fields.Many2one('stock.location', string='Ubicación', readonly=True)
    lot_id = fields.Many2one('stock.lot', string='Serial/Lote', readonly=True)
    product_name = fields.Char(string='Producto', readonly=True)
    inventory_plate = fields.Char(string='Placa de Inventario', readonly=True)
    lot_name = fields.Char(string='Número de serie/lote', readonly=True)
    cost_renting = fields.Monetary(string='Costo Renting', currency_field='currency_id', readonly=True, digits=(16, 2))
    cost_additional = fields.Monetary(
        string='Costo Adicional',
        currency_field='currency_id',
        digits=(16, 2),
        readonly=True,
        compute='_compute_cost_additional',
        help='Suma de los costos de los elementos asociados con costo (Elementos Con Costo del serial).',
    )
    cost_renting_total = fields.Monetary(
        string='Costo Renting (total)',
        currency_field='currency_id',
        digits=(16, 2),
        readonly=True,
        compute='_compute_cost_additional',
        help='Costo Renting base + Costo adicional.',
    )
    entry_date = fields.Date(string='Fecha Activación Renting', readonly=True)
    exit_date = fields.Date(string='Fecha Finalización Renting', readonly=True)
    reining_plazo = fields.Char(string='Plazo Renting', readonly=True)
    days_total_on_site = fields.Integer(string='Días totales en sitio', readonly=True)
    days_total_month = fields.Integer(string='Días total del mes', readonly=True)
    current_day_of_month = fields.Integer(string='Día del mes en curso', readonly=True)
    month_display = fields.Char(string='Mes', readonly=True)
    days_in_service = fields.Integer(string='Días En Servicio', readonly=True)
    tiempo_en_sitio_display = fields.Char(
        string='Tiempo En Sitio',
        compute='_compute_tiempo_displays',
        help='Tiempo en sitio en formato "X meses y Y días".',
    )
    tiempo_restante_display = fields.Char(
        string='Tiempo Restante',
        compute='_compute_tiempo_displays',
        help='Tiempo restante hasta fecha finalización en "X meses y Y días".',
    )
    cost_daily = fields.Monetary(string='Costo Diario', currency_field='currency_id', readonly=True, digits=(16, 2))
    cost_to_date = fields.Monetary(string='Costo Días En Servicio', currency_field='currency_id', readonly=True, digits=(16, 2))
    currency_id = fields.Many2one('res.currency', string='Moneda', readonly=True)

    @api.depends('lot_id', 'lot_id.lot_supply_line_ids', 'lot_id.lot_supply_line_ids.has_cost', 'lot_id.lot_supply_line_ids.cost')
    def _compute_cost_additional(self):
        """Suma de costos de elementos asociados con costo (Elementos Con Costo del serial)."""
        for rec in self:
            additional = 0.0
            if rec.lot_id and hasattr(rec.lot_id, 'lot_supply_line_ids'):
                lines_with_cost = rec.lot_id.lot_supply_line_ids.filtered(lambda l: l.has_cost)
                additional = sum(lines_with_cost.mapped('cost')) or 0.0
            rec.cost_additional = additional
            rec.cost_renting_total = (rec.cost_renting or 0.0) + additional

    def _months_and_days_calendar(self, start_date, end_date):
        """Meses completos de calendario y días restantes entre dos fechas. Devuelve (meses, días)."""
        if not start_date or not end_date:
            return (0, 0)
        try:
            start = start_date.date() if isinstance(start_date, datetime.datetime) else start_date
            end = end_date.date() if isinstance(end_date, datetime.datetime) else end_date
            if not hasattr(start, 'year'):
                start = fields.Date.from_string(start) if start else None
            if not hasattr(end, 'year'):
                end = fields.Date.from_string(end) if end else None
            if not start or not end or end < start:
                return (0, 0)
            months = 0
            d = start
            while True:
                next_d = d + relativedelta(months=1)
                if next_d <= end:
                    months += 1
                    d = next_d
                else:
                    break
            remaining = (end - d).days
            return (months, remaining)
        except Exception:
            return (0, 0)

    @api.depends('entry_date', 'exit_date', 'days_total_on_site')
    def _compute_tiempo_displays(self):
        """Tiempo En Sitio y Tiempo Restante en formato 'X meses y Y días' (meses de calendario reales)."""
        today = fields.Date.context_today(self)
        for rec in self:
            # Tiempo En Sitio: desde entry_date hasta (exit_date si ya salió, si no hoy)
            if not rec.entry_date:
                rec.tiempo_en_sitio_display = '0 días'
            else:
                end_site = today
                if rec.exit_date:
                    exit_d = rec.exit_date if hasattr(rec.exit_date, 'year') else getattr(rec.exit_date, 'date', lambda: rec.exit_date)()
                    if hasattr(exit_d, 'date'):
                        exit_d = exit_d.date()
                    if exit_d < today:
                        end_site = exit_d
                meses, dias = rec._months_and_days_calendar(rec.entry_date, end_site)
                if meses and dias:
                    rec.tiempo_en_sitio_display = '%d meses y %d días' % (meses, dias)
                elif meses:
                    rec.tiempo_en_sitio_display = '%d meses' % meses
                elif dias:
                    rec.tiempo_en_sitio_display = '%d días' % dias
                else:
                    rec.tiempo_en_sitio_display = '0 días'
            # Tiempo Restante: desde hoy hasta exit_date
            if not rec.exit_date:
                rec.tiempo_restante_display = ''
            else:
                try:
                    exit_d = rec.exit_date
                    if hasattr(exit_d, 'date'):
                        exit_d = exit_d.date()
                    if exit_d < today:
                        rec.tiempo_restante_display = _('Finalizado')
                    else:
                        meses, dias = rec._months_and_days_calendar(today, exit_d)
                        if meses and dias:
                            rec.tiempo_restante_display = '%d meses y %d días' % (meses, dias)
                        elif meses:
                            rec.tiempo_restante_display = '%d meses' % meses
                        elif dias:
                            rec.tiempo_restante_display = '%d días' % dias
                        else:
                            rec.tiempo_restante_display = '0 días'
                except Exception:
                    rec.tiempo_restante_display = ''

    def action_ver_detalles_elementos_costo(self):
        """Abre wizard con los elementos con costo de este serial (solo visible si cost_additional > 0)."""
        self.ensure_one()
        if not self.lot_id:
            return {'type': 'ir.actions.act_window_close'}
        Wizard = self.env['subscription.equipment.cost.detail.wizard']
        wizard = Wizard.create({'lot_id': self.lot_id.id})
        return {
            'type': 'ir.actions.act_window',
            'name': _('Elementos Con Costo - %s') % (self.lot_name or self.product_name or _('Serial')),
            'res_model': 'subscription.equipment.cost.detail.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }
