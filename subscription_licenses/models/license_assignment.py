# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import float_round


class LicenseAssignment(models.Model):
    _name = 'license.assignment'
    _description = 'Asignación de Licencia a Cliente'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'partner_id, license_id'
    _rec_name = 'license_display_name_stored'

    # Campo para seleccionar el servicio/producto primero
    selected_product_id = fields.Many2one(
        'product.product',
        string='Producto/Servicio',
        required=True,
        domain=lambda self: self._get_product_domain(),
        tracking=True,
        help='Seleccione el producto/servicio. La licencia y categoría se cargarán automáticamente.'
    )
    
    @api.model
    def _get_product_domain(self):
        """Obtiene el dominio para filtrar productos por línea de negocio"""
        domain = [('type', '=', 'service')]
        
        # Buscar la línea de negocio "RENTING SOFTWARE Y LICENCIAMIENTO"
        if 'product.business.line' in self.env:
            business_line = self.env['product.business.line'].search([
                ('name', '=', 'RENTING SOFTWARE Y LICENCIAMIENTO')
            ], limit=1)
            
            if business_line:
                domain.append(('business_line_id', '=', business_line.id))
        
        return domain
    
    license_id = fields.Many2one(
        'license.template',
        string='Licencia',
        required=True,
        ondelete='cascade',
        tracking=True
    )
    license_product_id = fields.Many2one(
        'product.product',
        related='license_id.product_id',
        string='Producto/Servicio (Relacionado)',
        store=True,
        readonly=True,
        help='Producto/servicio asociado a esta licencia'
    )
    license_applies_to_equipment = fields.Boolean(
        related='license_id.applies_to_equipment',
        string='Licencia aplica a equipo',
        readonly=True,
        store=True,
    )
    license_applies_to_user = fields.Boolean(
        related='license_id.applies_to_user',
        string='Licencia aplica a usuario',
        readonly=True,
        store=True,
    )
    
    # Campo computed para mostrar mejor información en la vista
    license_display_name = fields.Char(
        string='Licencia (Completo)',
        compute='_compute_license_display_name',
        store=False,
        help='Muestra el código y nombre de la licencia para fácil identificación'
    )
    # Almacenado para poder agrupar por "Tipo de Licencia" (categoría - producto)
    license_display_name_stored = fields.Char(
        string='Tipo de Licencia (agrupar)',
        compute='_compute_license_display_name',
        store=True,
        index=True,
        help='Mismo valor que Tipo de Licencia; almacenado para agrupar por tipo real, no por categoría.',
    )

    @api.depends('license_id', 'license_id.name', 'license_id.product_id', 'license_id.product_id.name')
    def _compute_license_display_name(self):
        """Calcula el nombre completo de la licencia para mostrar (categoría - producto)."""
        for rec in self:
            if rec.license_id:
                category_name = rec.license_id.name.name if rec.license_id.name else 'Sin Categoría'
                product_name = rec.license_id.product_id.name if rec.license_id.product_id else ''
                if product_name:
                    val = f"{category_name} - {product_name}"
                else:
                    val = category_name
            else:
                val = ''
            rec.license_display_name = val
            rec.license_display_name_stored = val
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        required=True,
        tracking=True,
        domain=[('is_company', '=', True)]
    )
    license_provider_choice_ids = fields.Many2many(
        'res.partner',
        compute='_compute_license_provider_choice_ids',
        string='Proveedores para esta licencia',
        store=False,
        help='Proveedores que ofrecen esta licencia (configurados en Cantidad por proveedor).'
    )
    license_provider_id = fields.Many2one(
        'res.partner',
        string='Proveedor de la licencia',
        tracking=True,
        domain="[('id', 'in', license_provider_choice_ids)]",
        help='Proveedor del cual se obtuvieron estas licencias. Solo se listan los que ofrecen esta licencia.'
    )

    @api.depends('license_id', 'license_id.product_id')
    def _compute_license_provider_choice_ids(self):
        """Restringe a proveedores que tengan esta licencia (producto) en Cantidad por proveedor."""
        for rec in self:
            if rec.license_id and rec.license_id.product_id:
                stocks = self.env['license.provider.stock'].search([
                    ('license_product_id', '=', rec.license_id.product_id.id)
                ])
                rec.license_provider_choice_ids = stocks.mapped('provider_id')
            else:
                rec.license_provider_choice_ids = self.env['res.partner']
    location_id = fields.Many2one(
        'stock.location',
        string='Ubicación del Cliente',
        tracking=True,
        help='Ubicación donde se encuentran los equipos del cliente'
    )
    quantity = fields.Integer(
        string='Cantidad',
        required=True,
        default=1,
        tracking=True,
        help='Cantidad de licencias asignadas a este cliente'
    )
    start_date = fields.Date(string='Fecha de Inicio', tracking=True)
    end_date = fields.Date(string='Fecha de Fin', tracking=True)
    contracting_type = fields.Selection([
        ('monthly_monthly', 'Mensual Mensual'),
        ('annual_monthly_commitment', 'Anual Compromiso Mensual'),
        ('annual', 'Anual'),
    ], string='Tipo de Contratación', required=True, tracking=True, help='Tipo de contratación de la licencia')
    contracting_type_description = fields.Html(
        string='Descripción del Tipo de Contratación',
        compute='_compute_contracting_type_description',
        store=False,
        readonly=True,
        help='Descripción del tipo de contratación seleccionado'
    )
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('active', 'Activa'),
        ('expired', 'Vencida'),
        ('cancelled', 'Cancelada'),
    ], string='Estado', default='draft', tracking=True)
    auto_renewal = fields.Boolean(
        string='Renovación automática',
        default=False,
        tracking=True,
        help='Si está marcado, la licencia se considera de renovación automática (Sí). Visible también en Licencias contratadas del proveedor.',
    )

    # Relación con equipos
    equipment_ids = fields.One2many('license.equipment', 'assignment_id', string='Equipos Asignados')
    unassignment_history_ids = fields.One2many(
        'license.equipment.unassignment.history',
        'assignment_id',
        string='Historial de desasignaciones',
        readonly=True,
    )
    equipment_count = fields.Integer(string='Equipos Asignados', compute='_compute_equipment_count')
    
    # Relación con usuarios (contactos)
    user_count = fields.Integer(string='Usuarios Asignados', compute='_compute_user_count')
    
    # Información de costos (eliminado - los costos ahora vienen de la lista de precios)
    price_usd = fields.Float(
        string='Precio Unitario USD',
        digits=(16, 2),
        help='Precio unitario en USD para este cliente. Si está vacío, se usará el precio de la lista de precios del cliente o el costo de la plantilla.'
    )
    use_custom_price = fields.Boolean(
        string='Usar Precio Personalizado',
        default=False,
        help='Si está activo, se usará el precio personalizado. Si no, se calculará desde la lista de precios del cliente.'
    )
    total_cost_usd = fields.Float(
        string='Costo Total USD',
        compute='_compute_total_cost',
        store=False,
        help='Precio a cliente en USD (siempre desde lista de precios del cliente al mostrar).'
    )
    trm_rate = fields.Float(
        string='TRM Aplicada',
        compute='_compute_trm_rate',
        store=True,
        help='TRM utilizada para el cálculo en COP'
    )
    total_cost_cop = fields.Float(
        string='Costo Total COP',
        compute='_compute_total_cost',
        store=False,
        digits=(16, 2)
    )
    provider_cost_usd = fields.Float(
        string='Costo Proveedor (USD)',
        compute='_compute_provider_cost_usd',
        store=False,
        digits=(16, 2),
        help='Valor por defecto desde Costos por licencia del proveedor; el costo real se edita en Reporte del proveedor → Ver licencias contratadas.',
    )
    profit_usd = fields.Float(
        string='Ganancia (USD)',
        compute='_compute_profit_usd',
        store=False,
        digits=(16, 2),
        help='Costo a cliente - Costo proveedor.',
    )
    cut_off_display = fields.Char(
        string='Fecha de corte',
        compute='_compute_cut_off_display',
        help='Fechas/condiciones del cliente (inicio–fin).',
    )
    assignment_period_display = fields.Char(
        string='Período',
        compute='_compute_assignment_period_display',
        store=False,
        help='Desde / hasta y cantidad, para distinguir varias asignaciones del mismo licenciamiento.',
    )

    @api.depends('start_date', 'end_date', 'quantity')
    def _compute_assignment_period_display(self):
        for rec in self:
            parts = []
            if rec.start_date:
                parts.append(_('Desde %s') % rec.start_date)
            if rec.end_date:
                parts.append(_('hasta %s') % rec.end_date)
            q = rec.quantity or 0
            parts.append(_('%s lic') % q)
            rec.assignment_period_display = ' · '.join(parts) if parts else ''

    @api.depends('license_provider_id', 'license_id', 'license_id.product_id')
    def _compute_provider_cost_usd(self):
        """Valor por defecto desde Costos por licencia; el usuario edita el costo en Licencias contratadas del proveedor."""
        Stock = self.env['license.provider.stock']
        for rec in self:
            if not rec.license_provider_id or not rec.license_id or not rec.license_id.product_id:
                rec.provider_cost_usd = 0.0
                continue
            stock = Stock.search([
                ('provider_id', '=', rec.license_provider_id.id),
                ('license_product_id', '=', rec.license_id.product_id.id),
            ], limit=1)
            rec.provider_cost_usd = stock.cost_per_unit_usd if stock and stock.cost_per_unit_usd else 0.0

    @api.depends('total_cost_usd', 'provider_cost_usd', 'quantity', 'price_usd', 'license_provider_id', 'license_id')
    def _compute_profit_usd(self):
        for rec in self:
            cost_to_client = rec.total_cost_usd or 0.0
            cost_provider = rec.provider_cost_usd if rec.provider_cost_usd else 0.0
            rec.profit_usd = cost_to_client - cost_provider

    @api.depends('start_date', 'end_date')
    def _compute_cut_off_display(self):
        for rec in self:
            if rec.start_date and rec.end_date:
                rec.cut_off_display = '%s — %s' % (rec.start_date, rec.end_date)
            elif rec.start_date:
                rec.cut_off_display = str(rec.start_date)
            elif rec.end_date:
                rec.cut_off_display = str(rec.end_date)
            else:
                rec.cut_off_display = ''

    # Campos relacionados
    company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.company)
    currency_cop_id = fields.Many2one(
        'res.currency',
        string='Moneda COP',
        default=lambda self: self.env.ref('base.COP', raise_if_not_found=False),
        readonly=True
    )
    
    # Campos computed para mostrar en la vista de suscripción
    license_business_line_id = fields.Many2one(
        'product.business.line',
        string='Línea de Negocio (Licencia)',
        compute='_compute_license_display_fields',
        store=False,
        readonly=True,
        help='Línea de negocio del producto asociado a la licencia',
    )
    license_code_display = fields.Char(
        string='Código Licencia',
        compute='_compute_license_display_fields',
        store=False,
        readonly=True,
    )
    license_name_display = fields.Char(
        string='Tipo de Servicio (Licencia)',
        compute='_compute_license_display_fields',
        store=False,
        readonly=True,
    )
    license_total_cost_cop = fields.Float(
        string='Valor Total COP (Licencia)',
        related='total_cost_cop',
        readonly=True,
    )
    
    @api.depends('license_id', 'license_id.product_id', 'license_id.code', 'license_id.name')
    def _compute_license_display_fields(self):
        """Calcula campos para mostrar las licencias en la vista de suscripción."""
        for rec in self:
            if rec.license_id:
                rec.license_code_display = rec.license_id.code or ''
                rec.license_name_display = rec.license_id.name or ''
                
                # Obtener business_line_id del producto
                if rec.license_id.product_id:
                    product = rec.license_id.product_id
                    if hasattr(product, 'business_line_id') and product.business_line_id:
                        rec.license_business_line_id = product.business_line_id.id
                    elif hasattr(product.product_tmpl_id, 'business_line_id') and product.product_tmpl_id.business_line_id:
                        rec.license_business_line_id = product.product_tmpl_id.business_line_id.id
                    else:
                        rec.license_business_line_id = False
                else:
                    rec.license_business_line_id = False
            else:
                rec.license_code_display = ''
                rec.license_name_display = ''
                rec.license_business_line_id = False

    @api.depends('equipment_ids', 'equipment_ids.contact_id', 'equipment_ids.lot_id')
    def _compute_equipment_count(self):
        """Cuenta solo equipos que NO tienen contacto asignado (equipos sin usuario)"""
        for rec in self:
            # Solo contar equipos que tienen lot_id pero NO tienen contact_id
            equipment_without_user = rec.equipment_ids.filtered(
                lambda e: e.lot_id and not e.contact_id
            )
            rec.equipment_count = len(equipment_without_user)
    
    @api.depends('equipment_ids', 'equipment_ids.contact_id')
    def _compute_user_count(self):
        """Cuenta usuarios únicos asignados. Si un equipo tiene contacto, se cuenta como usuario"""
        for rec in self:
            # Obtener todos los contactos únicos de los equipos
            contacts = rec.equipment_ids.mapped('contact_id')
            # Filtrar para eliminar duplicados y valores False
            unique_contacts = contacts.filtered(lambda c: c)
            rec.user_count = len(unique_contacts)
    
    @api.depends('contracting_type')
    def _compute_contracting_type_description(self):
        """Calcula la descripción según el tipo de contratación seleccionado."""
        for rec in self:
            if rec.contracting_type == 'monthly_monthly':
                rec.contracting_type_description = _(
                    '<div style="margin-top: 8px; padding: 12px; background-color: #e7f3ff; border-radius: 4px; border-left: 4px solid #2196F3;">'
                    '<strong style="font-size: 14px; color: #1976D2;">Mensual Mensual</strong><br/><br/>'
                    '• Se paga mes a mes.<br/>'
                    '• Sin compromiso a largo plazo.<br/>'
                    '• <strong>Puedes agregar o quitar licencias, equipos y usuarios en cualquier momento.</strong>'
                    '</div>'
                )
            elif rec.contracting_type == 'annual_monthly_commitment':
                rec.contracting_type_description = _(
                    '<div style="margin-top: 8px; padding: 12px; background-color: #fff3cd; border-radius: 4px; border: 2px solid #ff9800; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">'
                    '<strong style="font-size: 14px; color: #e65100;">⚠️ ADVERTENCIA IMPORTANTE</strong><br/><br/>'
                    '<div style="background-color: #ffebee; padding: 10px; border-radius: 4px; margin-top: 8px; border-left: 4px solid #f44336;">'
                    '<strong style="color: #c62828; font-size: 13px;">🚫 RESTRICCIÓN DE ELIMINACIÓN</strong><br/>'
                    '<span style="color: #d32f2f;">Una vez que asignes licencias, equipos o usuarios, <strong>NO PODRÁS QUITARLOS</strong> durante los 12 meses del contrato.</span><br/>'
                    '<span style="color: #d32f2f;">Solo podrás <strong>AGREGAR</strong> más elementos durante el período.</span>'
                    '</div><br/>'
                    '<strong>Anual – Compromiso Mensual</strong><br/>'
                    '• Contrato por 12 meses.<br/>'
                    '• El pago se hace mensualmente.<br/>'
                    '• Las licencias adicionales se facturan hasta completar el año.'
                    '</div>'
                )
            elif rec.contracting_type == 'annual':
                rec.contracting_type_description = _(
                    '<div style="margin-top: 8px; padding: 12px; background-color: #fff3cd; border-radius: 4px; border: 2px solid #ff9800; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">'
                    '<strong style="font-size: 14px; color: #e65100;">⚠️ ADVERTENCIA IMPORTANTE</strong><br/><br/>'
                    '<div style="background-color: #ffebee; padding: 10px; border-radius: 4px; margin-top: 8px; border-left: 4px solid #f44336;">'
                    '<strong style="color: #c62828; font-size: 13px;">🚫 RESTRICCIÓN DE ELIMINACIÓN</strong><br/>'
                    '<span style="color: #d32f2f;">Una vez que asignes licencias, equipos o usuarios, <strong>NO PODRÁS QUITARLOS</strong> durante los 12 meses del contrato.</span><br/>'
                    '<span style="color: #d32f2f;">Solo podrás <strong>AGREGAR</strong> más elementos durante el período.</span>'
                    '</div><br/>'
                    '<strong>Anual</strong><br/>'
                    '• Contrato por 12 meses.<br/>'
                    '• El pago es una sola vez al año.<br/>'
                    '• Las licencias agregadas se cobran por el tiempo restante del período anual.'
                    '</div>'
                )
            else:
                rec.contracting_type_description = ''

    @api.depends('quantity', 'price_usd', 'use_custom_price', 'partner_id', 'license_id', 'license_id.product_id', 'trm_rate')
    def _compute_total_cost(self):
        for rec in self:
            unit_price = rec._get_unit_price_usd()
            rec.total_cost_usd = rec.quantity * unit_price
            # COP siempre = TRM * USD (incluso cuando USD es 0)
            rec.total_cost_cop = rec.total_cost_usd * (rec.trm_rate or 0.0)

    def _get_unit_price_usd(self):
        """Obtiene el precio unitario en USD para esta asignación.
        Prioridad: usar siempre el precio que el usuario configuró en la lista de precios del cliente.
        1. Precio personalizado (si use_custom_price está activo)
        2. Precios recurrentes de la lista del cliente (sale.subscription.pricing: pricelist + producto)
        3. Precio vía suscripción del cliente (_get_price_for_product)
        4. Reglas de la lista de precios (pricelist._get_product_price)
        5. Cero
        """
        self.ensure_one()
        
        # Si hay precio personalizado y está activado, usarlo.
        # Pero para el reporte del proveedor (Consolidado / Ver licencias contratadas),
        # a veces el precio personalizado se queda "congelado" aunque la lista cambie.
        # Por eso permitimos saltar el precio personalizado por contexto.
        if not self.env.context.get('ignore_custom_price', False):
            if self.use_custom_price and self.price_usd:
                return self.price_usd
        
        product = self.license_id and self.license_id.product_id
        if not self.partner_id or not product:
            return 0.0

        pricelist = self.partner_id.property_product_pricelist
        usd_currency = self.env.ref('base.USD', raise_if_not_found=False)
        cutoff_day = 6
        if self.license_id and self.license_id.name and hasattr(self.license_id.name, 'get_trm_cutoff_day'):
            cutoff_day = self.license_id.name.get_trm_cutoff_day()
        trm_rate = self.trm_rate or (
            self.env['license.trm'].get_trm_for_date(cutoff_day=cutoff_day) if 'license.trm' in self.env else 0.0
        )

        # 1) (Odoo 18 legacy) Precios recurrentes: sale.subscription.pricing
        # En Odoo 19 los recurrentes deberían venir desde la lista de precios (product.pricelist.item / suscripción),
        # pero durante el upgrade a veces queda el modelo heredado y puede devolver valores viejos.
        # Por eso, lo dejamos desactivado por defecto y solo lo usamos si se fuerza con contexto.
        if (
            pricelist
            and 'sale.subscription.pricing' in self.env
            and self.env.context.get('use_sale_subscription_pricing', False)
        ):
            try:
                Pricing = self.env['sale.subscription.pricing']
                product_tmpl_field = 'product_template_id' if 'product_template_id' in Pricing._fields else 'product_tmpl_id'
                domain_tmpl = [
                    ('pricelist_id', '=', pricelist.id),
                    (product_tmpl_field, '=', product.product_tmpl_id.id),
                ]
                pricing = Pricing.search(domain_tmpl, limit=1)
                if not pricing and 'product_id' in Pricing._fields:
                    pricing = Pricing.search([
                        ('pricelist_id', '=', pricelist.id),
                        ('product_id', '=', product.id),
                    ], limit=1)
                if pricing and hasattr(pricing, 'price') and pricing.price is not None:
                    price_val = float(pricing.price)
                    curr = getattr(pricing, 'currency_id', None) and pricing.currency_id or pricelist.currency_id
                    if curr and curr.name == 'USD':
                        return price_val
                    if curr and curr.name == 'COP' and trm_rate and trm_rate > 0:
                        return price_val / trm_rate
                    if curr and usd_currency:
                        try:
                            return curr._convert(price_val, usd_currency, self.env.company, fields.Date.today())
                        except Exception:
                            pass
                    return price_val
            except Exception:
                pass

        # 1.5) Prioridad: precio desde la lista de precios del cliente
        # OJO: muchas veces las reglas recurrentes viven con plan_id y
        # `pricelist._get_product_price()` puede devolver 0.0 (cuando "no encuentra").
        # En ese caso NO debemos retornar 0.0: debemos dejar que el cálculo
        # siga hacia el bloque recurrente por plan.
        if pricelist:
            try:
                direct_price = pricelist._get_product_price(
                    product,
                    quantity=self.quantity or 1.0,
                    partner=self.partner_id,
                    date=fields.Date.today(),
                    uom_id=product.uom_id.id,
                )
                if direct_price is not None:
                    try:
                        direct_price = float(direct_price)
                    except (TypeError, ValueError):
                        direct_price = None

                # Si el precio "estándar" es 0, puede significar que no hay regla
                # (en reglas recurrentes). Dejamos seguir hacia el bloque por plan.
                if direct_price is not None and direct_price != 0.0:
                    if pricelist.currency_id and pricelist.currency_id.name == 'USD':
                        return direct_price
                    if pricelist.currency_id and pricelist.currency_id.name == 'COP':
                        return (direct_price / trm_rate) if trm_rate and trm_rate > 0 else 0.0
                    if pricelist.currency_id and usd_currency:
                        try:
                            return pricelist.currency_id._convert(
                                direct_price,
                                usd_currency,
                                self.env.company,
                                fields.Date.today(),
                            ) or 0.0
                        except Exception:
                            pass
            except Exception:
                pass

        # 1.6) Fallback (fiable): leer la regla recurrente directamente en product.pricelist.item
        # (evita depender de APIs cuando el plan_id no se resuelve bien).
        try:
            if pricelist and product:
                plan_model = self.env['sale.subscription.plan']
                expected_plan_ids = []
                if self.contracting_type == 'monthly_monthly':
                    expected_plan_ids = plan_model.search([
                        ('billing_period_unit', '=', 'month'),
                        ('billing_period_value', '=', 1),
                    ], limit=10).ids
                elif self.contracting_type in ('annual_monthly_commitment', 'annual'):
                    # anual: 12 meses o 1 año
                    expected_plan_ids = plan_model.search([
                        '|',
                        '&',
                        ('billing_period_unit', '=', 'month'),
                        ('billing_period_value', '=', 12),
                        '&',
                        ('billing_period_unit', '=', 'year'),
                        ('billing_period_value', '=', 1),
                    ], limit=10).ids
                if not expected_plan_ids:
                    expected_plan_ids = plan_model.search([
                        ('billing_period_unit', 'in', ('month', 'year')),
                    ], limit=10).ids

                if expected_plan_ids:
                    PricelistItem = self.env['product.pricelist.item']
                    item = PricelistItem.search([
                        ('pricelist_id', '=', pricelist.id),
                        ('plan_id', 'in', expected_plan_ids),
                        '|',
                        ('product_tmpl_id', '=', product.product_tmpl_id.id),
                        ('product_id', '=', product.id),
                    ], limit=1)
                    if item:
                        qty = self.quantity or 1.0
                        # _compute_price usa la moneda del pricelist y considera plan/cantidad.
                        price_value = item._compute_price(
                            product,
                            qty,
                            uom=product.uom_id,
                            date=fields.Datetime.now(),
                            currency=pricelist.currency_id,
                            plan_id=item.plan_id.id if item.plan_id else None,
                        )
                        if price_value is not None:
                            price_value = float(price_value)
                            if pricelist.currency_id and pricelist.currency_id.name == 'USD':
                                return price_value
                            if pricelist.currency_id and pricelist.currency_id.name == 'COP':
                                return (price_value / trm_rate) if trm_rate and trm_rate > 0 else 0.0
                            if pricelist.currency_id and usd_currency:
                                try:
                                    return pricelist.currency_id._convert(
                                        price_value, usd_currency, self.env.company, fields.Date.today()
                                    ) or 0.0
                                except Exception:
                                    pass
        except Exception:
            pass

        # 2) Precio recurrente desde Plan del cliente (sale.subscription.plan)
        # En Odoo 19, los "precios recurrentes" suelen vivir en product.pricelist.item con plan_id.
        # Si no pasamos ese plan_id, pricelist._get_product_price puede caer a una regla genérica
        # (por eso en el Consolidado se ve un valor viejo tipo 12 aunque en la lista pongas 150).
        try:
            if 'sale.subscription.plan' in self.env and product and pricelist:
                plan_model = self.env['sale.subscription.plan']
                plans = self.env['sale.subscription.plan']
                # Odoo 19 Enterprise: sale.subscription.plan usa campos de billing period en vez de nombres
                # (y en producción normalmente está en inglés: Monthly/Yearly).
                if self.contracting_type == 'monthly_monthly':
                    # Plan mensual: 1 mes
                    plans = plan_model.search([
                        ('billing_period_unit', '=', 'month'),
                        ('billing_period_value', '=', 1),
                    ], limit=1)
                elif self.contracting_type in ('annual_monthly_commitment', 'annual'):
                    # Plan anual: 12 meses o 1 año
                    plans = plan_model.search([
                        '|',
                        '&',
                        ('billing_period_unit', '=', 'month'),
                        ('billing_period_value', '=', 12),
                        '&',
                        ('billing_period_unit', '=', 'year'),
                        ('billing_period_value', '=', 1),
                    ], limit=1)

                # Fallback por si no existe exactamente el plan.
                # Preferimos probar múltiples planes para evitar quedarnos con uno incorrecto.
                if not plans:
                    if self.contracting_type == 'monthly_monthly':
                        plans = plan_model.search([('billing_period_unit', '=', 'month')], limit=10)
                    else:
                        plans = plan_model.search([('billing_period_unit', 'in', ('month', 'year'))], limit=10)

                if plans and hasattr(product.product_tmpl_id, '_get_recurring_pricing'):
                    qty = self.quantity or 1.0
                    for plan in plans:
                        pricing_item = product.product_tmpl_id._get_recurring_pricing(
                            pricelist=pricelist,
                            variant=product,
                            plan_id=plan.id if plan else None,
                            quantity=qty,
                        )
                        if not pricing_item or not hasattr(pricing_item, '_compute_price'):
                            continue

                        price_value = pricing_item._compute_price(
                            product,
                            qty,
                            uom=product.uom_id,
                            date=fields.Datetime.now(),
                            currency=pricelist.currency_id,
                            plan_id=plan.id if plan else None,
                        )
                        if price_value is None:
                            continue

                        try:
                            price_value = float(price_value)
                        except (TypeError, ValueError):
                            continue

                        # Convertir a USD según la moneda de la lista
                        if pricelist.currency_id and pricelist.currency_id.name == 'USD':
                            return price_value
                        if pricelist.currency_id and pricelist.currency_id.name == 'COP':
                            return (price_value / trm_rate) if trm_rate and trm_rate > 0 else 0.0
                        if pricelist.currency_id and usd_currency:
                            try:
                                return pricelist.currency_id._convert(
                                    price_value, usd_currency, self.env.company, fields.Date.today()
                                ) or 0.0
                            except Exception:
                                pass
        except Exception:
            pass

        # 2.5) Odoo 19 nativo sin plan explícito:
        # si no se pudo resolver plan en assignment, pedir a Odoo la primera regla recurrente aplicable
        # para la lista del cliente (any_plan=True internamente en _get_recurring_pricing cuando plan_id=None).
        try:
            if pricelist and product and hasattr(product.product_tmpl_id, '_get_recurring_pricing'):
                qty = self.quantity or 1.0
                pricing_item = product.product_tmpl_id._get_recurring_pricing(
                    pricelist=pricelist,
                    variant=product,
                    plan_id=None,
                    quantity=qty,
                )
                if pricing_item and hasattr(pricing_item, '_compute_price'):
                    price_value = pricing_item._compute_price(
                        product,
                        qty,
                        uom=product.uom_id,
                        date=fields.Datetime.now(),
                        currency=pricelist.currency_id,
                        plan_id=None,
                    )
                    if price_value is not None:
                        try:
                            price_value = float(price_value)
                        except (TypeError, ValueError):
                            price_value = None

                    if price_value is not None:
                        if pricelist.currency_id and pricelist.currency_id.name == 'USD':
                            return price_value
                        if pricelist.currency_id and pricelist.currency_id.name == 'COP':
                            return (price_value / trm_rate) if trm_rate and trm_rate > 0 else 0.0
                        if pricelist.currency_id and usd_currency:
                            try:
                                return pricelist.currency_id._convert(
                                    price_value, usd_currency, self.env.company, fields.Date.today()
                                ) or 0.0
                            except Exception:
                                pass
        except Exception:
            pass

        # 3) Suscripción del cliente (por si no hay fila en Precios recurrentes pero sí en la suscripción)
        if 'subscription.subscription' in self.env and hasattr(self.env['subscription.subscription'], '_get_price_for_product'):
            try:
                sub_domain = [('partner_id', '=', self.partner_id.id)]
                if self.location_id:
                    sub_domain.append(('location_id', '=', self.location_id.id))
                subscription = self.env['subscription.subscription'].search(sub_domain, limit=1)
                if not subscription and self.partner_id:
                    subscription = self.env['subscription.subscription'].search(
                        [('partner_id', '=', self.partner_id.id)], limit=1
                    )
                if subscription:
                    price = subscription._get_price_for_product(product, 1.0)
                    if price is not None:
                        sub_pricelist = subscription.partner_id.property_product_pricelist if subscription.partner_id else None
                        curr = sub_pricelist.currency_id if sub_pricelist and sub_pricelist.currency_id else None
                        if curr and curr.name == 'USD':
                            return float(price)
                        if curr and curr.name == 'COP' and trm_rate and trm_rate > 0:
                            return float(price) / trm_rate
                        if curr and usd_currency:
                            try:
                                return curr._convert(float(price), usd_currency, self.env.company, fields.Date.today())
                            except Exception:
                                pass
                        return float(price)
            except Exception:
                pass

        # 4) Reglas de la lista de precios (pricelist._get_product_price)
        if pricelist:
            try:
                price = pricelist._get_product_price(
                    product,
                    quantity=self.quantity or 1.0,
                    partner=self.partner_id,
                    date=fields.Date.today(),
                    uom_id=product.uom_id.id
                )
                if price is not None:
                    # Incluir precio 0: siempre hacer la operación (COP = TRM * USD)
                    if pricelist.currency_id.name == 'USD':
                        return float(price)
                    if pricelist.currency_id.name == 'COP':
                        return (float(price) / trm_rate) if trm_rate and trm_rate > 0 else 0.0
                    if pricelist.currency_id and usd_currency:
                        try:
                            converted = pricelist.currency_id._convert(
                                float(price), usd_currency, self.env.company, fields.Date.today()
                            )
                            return converted if converted is not None else 0.0
                        except Exception:
                            pass
            except Exception:
                pass

        return 0.0

    @api.onchange('selected_product_id')
    def _onchange_selected_product_id(self):
        """Carga automáticamente la licencia y categoría cuando se selecciona un producto/servicio"""
        for rec in self:
            if rec.selected_product_id:
                # Buscar la licencia que tiene este producto asociado
                license_template = self.env['license.template'].search([
                    ('product_id', '=', rec.selected_product_id.id)
                ], limit=1)
                
                if license_template:
                    rec.license_id = license_template
                    # La categoría se carga automáticamente a través del campo relacionado license_id.name
                else:
                    # Si no se encuentra una licencia, limpiar el campo
                    rec.license_id = False
                    return {
                        'warning': {
                            'title': _('Licencia no encontrada'),
                            'message': _('No se encontró una licencia asociada al producto "%s". '
                                        'Por favor, cree primero la licencia para este producto.')
                                        % rec.selected_product_id.name
                        }
                    }
            else:
                # Si se limpia el producto, limpiar también la licencia
                rec.license_id = False

    @api.onchange('partner_id', 'license_id', 'license_provider_id')
    def _onchange_duplicate_assignment_warning(self):
        """Avisar si ya existe otra asignación activa del mismo cliente + licencia + proveedor."""
        for rec in self:
            if not rec.partner_id or not rec.license_id or not rec.license_provider_id:
                continue
            domain = [
                ('partner_id', '=', rec.partner_id.id),
                ('license_id', '=', rec.license_id.id),
                ('license_provider_id', '=', rec.license_provider_id.id),
                ('state', '=', 'active'),
            ]
            if rec.id:
                domain.append(('id', '!=', rec.id))
            existing = self.search(domain, limit=1)
            if existing:
                return {
                    'warning': {
                        'title': _('Otra asignación activa del mismo tipo'),
                        'message': _(
                            'Ya existe una asignación activa de "%s" con el mismo proveedor para este cliente. '
                            'Si son períodos o contratos distintos, use la columna "Período" en la lista para diferenciarlas.'
                        ) % (rec.license_display_name or _('esta licencia')),
                    }
                }

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """Actualiza la ubicación cuando se selecciona el cliente"""
        for rec in self:
            if rec.partner_id:
                # Buscar la ubicación del cliente (property_stock_customer)
                customer_location = rec.partner_id.property_stock_customer
                if customer_location:
                    rec.location_id = customer_location
                else:
                    # Si no tiene ubicación de cliente, buscar ubicaciones internas relacionadas
                    # Buscar si hay alguna asignación previa con ubicación para este cliente
                    prev_assignment = self.search([
                        ('partner_id', '=', rec.partner_id.id),
                        ('location_id', '!=', False)
                    ], limit=1, order='id desc')
                    if prev_assignment:
                        rec.location_id = prev_assignment.location_id

    @api.onchange('start_date', 'contracting_type')
    def _onchange_start_date(self):
        """Calcula automáticamente la fecha de fin cuando se establece fecha de inicio en contratos anuales."""
        for rec in self:
            if rec.start_date and rec.contracting_type in ('annual_monthly_commitment', 'annual'):
                from dateutil.relativedelta import relativedelta
                # Calcular fecha de fin: 12 meses después de la fecha de inicio
                end_date = rec.start_date + relativedelta(months=12) - relativedelta(days=1)
                rec.end_date = end_date

    @api.onchange('partner_id', 'license_id', 'quantity')
    def _onchange_partner_or_license(self):
        """Actualiza el precio cuando cambia el cliente o la licencia"""
        for rec in self:
            if not rec.use_custom_price:
                # Recalcular el precio desde la lista de precios o costo de plantilla
                rec.price_usd = rec._get_unit_price_usd()
                # Forzar recálculo de totales
                rec._compute_total_cost()

    @api.depends('start_date')
    def _compute_trm_rate(self):
        trm_model = self.env['license.trm']
        for rec in self:
            cutoff_day = 6
            if rec.license_id and rec.license_id.name and hasattr(rec.license_id.name, 'get_trm_cutoff_day'):
                cutoff_day = rec.license_id.name.get_trm_cutoff_day()
            if rec.start_date:
                try:
                    rec.trm_rate = trm_model.get_trm_for_date(rec.start_date, cutoff_day=cutoff_day)
                except ValidationError:
                    rec.trm_rate = 0.0
            else:
                # Si no hay fecha, usar TRM actual
                try:
                    rec.trm_rate = trm_model.get_trm_for_date(cutoff_day=cutoff_day)
                except ValidationError:
                    rec.trm_rate = 0.0



    @api.model_create_multi
    def create(self, vals_list):
        """Sobrescribe create para cargar automáticamente la licencia si hay producto seleccionado."""
        for vals in vals_list:
            if vals.get('selected_product_id') and not vals.get('license_id'):
                license_template = self.env['license.template'].search([
                    ('product_id', '=', vals['selected_product_id'])
                ], limit=1)
                if license_template:
                    vals['license_id'] = license_template.id
        records = super().create(vals_list)
        records._sync_to_provider_report()
        return records

    @api.constrains('selected_product_id', 'license_id')
    def _check_license_from_product(self):
        """Valida que si hay producto seleccionado, debe haber licencia asociada"""
        for rec in self:
            if rec.selected_product_id and not rec.license_id:
                # Intentar cargar la licencia automáticamente una vez más
                license_template = self.env['license.template'].search([
                    ('product_id', '=', rec.selected_product_id.id)
                ], limit=1)
                
                if license_template:
                    rec.license_id = license_template
                else:
                    raise ValidationError(
                        _('No se encontró una licencia asociada al producto "%s".\n\n'
                          'Por favor, cree primero la licencia para este producto en la configuración de licencias.')
                        % rec.selected_product_id.name
                    )

    @api.constrains('license_id', 'quantity', 'state')
    def _check_stock_availability(self):
        """Valida que no se exceda el stock disponible de licencias"""
        for rec in self:
            if not rec.license_id:
                continue
            
            # Solo validar si la asignación está activa o se va a activar
            if rec.state != 'active':
                continue
            
            license_template = rec.license_id
            
            # Si el stock es 0, no hay límite (stock ilimitado)
            if license_template.stock <= 0:
                continue
            
            # Calcular cuántas licencias están en uso (excluyendo esta asignación si es nueva o se está editando)
            other_active_assignments = self.search([
                ('license_id', '=', license_template.id),
                ('state', '=', 'active'),
                ('id', '!=', rec.id)
            ])
            used_quantity = sum(other_active_assignments.mapped('quantity'))
            
            # Calcular cuántas licencias quedarían disponibles después de esta asignación
            total_used_after = used_quantity + rec.quantity
            available_after = license_template.stock - total_used_after
            
            if available_after < 0:
                raise ValidationError(
                    _('No hay suficientes licencias disponibles.\n\n'
                      'Stock disponible: %s\n'
                      'Licencias en uso: %s\n'
                      'Cantidad a asignar: %s\n'
                      'Disponibles después: %s\n\n'
                      'Por favor, reduzca la cantidad o aumente el stock de la licencia.')
                    % (license_template.stock, used_quantity, rec.quantity, available_after)
                )

    @api.constrains('quantity')
    def _check_quantity_positive(self):
        for rec in self:
            if rec.quantity <= 0:
                raise ValidationError(_('La cantidad debe ser mayor a cero.'))

    def _sync_to_provider_report(self):
        """Crea o actualiza la línea de reporte del proveedor para cada asignación (sin tocar Costo proveedor)."""
        ProviderPartner = self.env['license.provider.partner']
        for rec in self:
            if not rec.license_provider_id:
                continue
            partner = ProviderPartner.search([
                ('partner_id', '=', rec.license_provider_id.id),
            ], limit=1)
            if partner:
                partner._sync_report_line_for_assignment(rec)

    def unlink(self):
        """Elimina las líneas de reporte asociadas antes de borrar la asignación."""
        ReportLine = self.env['license.provider.report.line']
        lines = ReportLine.search([('assignment_id', 'in', self.ids)])
        providers = lines.mapped('provider_partner_id')
        lines.unlink()
        for partner in providers:
            partner._sync_report_groups()
        return super().unlink()

    def write(self, vals):
        """Sobrescribe write para validar que no se reduzca la cantidad en contratos anuales y calcular fecha de fin."""
        # Validar reducción de cantidad antes de escribir
        if 'quantity' in vals:
            for rec in self:
                # Solo validar si la asignación está activa y el tipo es anual
                if rec.state == 'active' and rec.contracting_type in ('annual_monthly_commitment', 'annual'):
                    old_quantity = rec.quantity
                    new_quantity = vals['quantity']
                    if new_quantity < old_quantity:
                        contracting_type_name = dict(rec._fields['contracting_type'].selection).get(rec.contracting_type, rec.contracting_type)
                        raise ValidationError(
                            _('No se puede reducir la cantidad de licencias en un contrato de tipo "%s".\n\n'
                              'Cantidad actual: %d\n'
                              'Cantidad intentada: %d\n\n'
                              'En contratos anuales solo se pueden agregar licencias, no quitar.')
                            % (contracting_type_name, old_quantity, new_quantity)
                        )
        
        # Calcular automáticamente fecha de fin cuando se establece fecha de inicio en contratos anuales
        if 'start_date' in vals and vals['start_date']:
            from dateutil.relativedelta import relativedelta
            for rec in self:
                contracting_type = vals.get('contracting_type', rec.contracting_type)
                if contracting_type in ('annual_monthly_commitment', 'annual'):
                    start_date = vals['start_date']
                    # Convertir string a date si es necesario
                    if isinstance(start_date, str):
                        start_date = fields.Date.from_string(start_date)
                    # Calcular fecha de fin: 12 meses después de la fecha de inicio
                    end_date = start_date + relativedelta(months=12) - relativedelta(days=1)
                    vals['end_date'] = fields.Date.to_string(end_date)

        res = super().write(vals)

        # Ajustar estado automáticamente cuando cambian fechas:
        # - Si estaba vencida y ahora la vigencia cubre hoy, volver a activa.
        # - Si estaba activa y ahora quedó fuera de vigencia, marcar vencida.
        if 'start_date' in vals or 'end_date' in vals:
            today = fields.Date.today()
            for rec in self:
                if rec.state == 'cancelled':
                    continue
                is_started = (not rec.start_date) or (rec.start_date <= today)
                is_not_ended = (not rec.end_date) or (rec.end_date >= today)
                if rec.state == 'expired' and is_started and is_not_ended:
                    rec.state = 'active'
                elif rec.state == 'active' and (not is_started or not is_not_ended):
                    rec.state = 'expired'

        if not self.env.context.get('skip_sync_provider_report'):
            self._sync_to_provider_report()
        return res

    @api.constrains('start_date', 'end_date', 'contracting_type')
    def _check_dates(self):
        for rec in self:
            # Validar que las fechas sean obligatorias en contratos anuales
            if rec.contracting_type in ('annual_monthly_commitment', 'annual'):
                if not rec.start_date:
                    contracting_type_name = dict(self._fields['contracting_type'].selection).get(rec.contracting_type, rec.contracting_type)
                    raise ValidationError(
                        _('La fecha de inicio es obligatoria para contratos de tipo "%s".')
                        % contracting_type_name
                    )
                if not rec.end_date:
                    contracting_type_name = dict(self._fields['contracting_type'].selection).get(rec.contracting_type, rec.contracting_type)
                    raise ValidationError(
                        _('La fecha de fin es obligatoria para contratos de tipo "%s".')
                        % contracting_type_name
                    )
            # Validar que la fecha de inicio no sea posterior a la fecha de fin
            if rec.start_date and rec.end_date and rec.start_date > rec.end_date:
                raise ValidationError(_('La fecha de inicio no puede ser posterior a la fecha de fin.'))

    # Nota: Se permite varias asignaciones activas del mismo cliente + misma licencia con distinta
    # cantidad, precio y fechas, para alinear con los reportes del proveedor (múltiples líneas por cliente/producto).
    # Ya no se aplica _check_duplicate_active_assignment.
    
    @api.constrains('quantity', 'equipment_ids')
    def _check_equipment_quantity(self):
        """Valida que no haya más asignaciones (equipos sin usuario + usuarios únicos) que la cantidad de licencias"""
        for rec in self:
            # Contar total de asignaciones: equipos sin usuario + usuarios únicos
            total_assignments = rec.equipment_count + rec.user_count
            if total_assignments > rec.quantity:
                raise ValidationError(
                    _('No puede tener más asignaciones (%d equipos sin usuario + %d usuarios = %d total) '
                      'que la cantidad de licencias (%d).')
                    % (rec.equipment_count, rec.user_count, total_assignments, rec.quantity)
                )

    def action_activate(self):
        """Activa la asignación de licencia"""
        for rec in self:
            if rec.state != 'draft':
                raise ValidationError(_('Solo se pueden activar asignaciones en estado Borrador.'))
            if not rec.start_date:
                rec.start_date = fields.Date.today()
            rec.state = 'active'

    def _apply_cancel_state(self):
        """Pasa la asignación a cancelada (usado tras confirmar en el wizard de advertencia)."""
        for rec in self:
            if rec.state == 'cancelled':
                continue
            rec.state = 'cancelled'

    def action_cancel(self):
        """Abre el wizard de advertencia antes de cancelar la asignación."""
        self.ensure_one()
        if self.state in ('cancelled', 'draft'):
            return True
        return {
            'name': _('Advertencia - Cancelar asignación'),
            'type': 'ir.actions.act_window',
            'res_model': 'license.assignment.cancel.warning.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_assignment_id': self.id},
        }

    def action_open_add_multiple_equipment(self):
        """Abre wizard de añadir varios equipos. Si el contrato es anual, muestra antes la advertencia."""
        self.ensure_one()
        if self.contracting_type in ('annual_monthly_commitment', 'annual'):
            return {
                'name': _('Advertencia - Añadir equipos'),
                'type': 'ir.actions.act_window',
                'res_model': 'license.add.multiple.warning.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_assignment_id': self.id,
                    'default_add_type': 'equipment',
                },
            }
        return {
            'name': _('Añadir varios equipos'),
            'type': 'ir.actions.act_window',
            'res_model': 'license.equipment.add.multiple.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_assignment_id': self.id,
                'default_add_type': 'equipment',
            },
        }

    def action_open_add_multiple_contact(self):
        """Abre wizard de añadir varios contactos. Si el contrato es anual, muestra antes la advertencia."""
        self.ensure_one()
        if self.contracting_type in ('annual_monthly_commitment', 'annual'):
            return {
                'name': _('Advertencia - Añadir contactos'),
                'type': 'ir.actions.act_window',
                'res_model': 'license.add.multiple.warning.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_assignment_id': self.id,
                    'default_add_type': 'contact',
                },
            }
        return {
            'name': _('Añadir varios contactos'),
            'type': 'ir.actions.act_window',
            'res_model': 'license.equipment.add.multiple.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_assignment_id': self.id,
                'default_add_type': 'contact',
            },
        }

    def action_open_quantity_warning_wizard(self):
        """Abre el wizard de advertencia para modificar cantidad (contratos anuales)."""
        self.ensure_one()
        return {
            'name': _('Modificar cantidad de licencias'),
            'type': 'ir.actions.act_window',
            'res_model': 'license.quantity.warning.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_assignment_id': self.id,
            },
        }

    def action_expire(self):
        """Marca la asignación como vencida"""
        for rec in self:
            if rec.state == 'active':
                rec.state = 'expired'

    @api.model
    def _cron_check_expired_licenses(self):
        """Cron job para renovar automáticamente y luego marcar licencias vencidas."""
        today = fields.Date.today()
        # 1) Renovar primero las activas/vencidas con auto-renovación habilitada.
        renewable = self.search([
            ('state', 'in', ['active', 'expired']),
            ('auto_renewal', '=', True),
            ('end_date', '<', today),
            ('end_date', '!=', False),
        ])
        for rec in renewable:
            if rec.contracting_type == 'monthly_monthly':
                step_months = 1
            else:
                # annual y annual_monthly_commitment
                step_months = 12
            if step_months <= 0:
                continue

            # Avanzar tantos períodos como sea necesario para dejarla vigente hoy.
            while rec.end_date and rec.end_date < today:
                next_start = rec.end_date + relativedelta(days=1)
                next_end = next_start + relativedelta(months=step_months) - relativedelta(days=1)
                # Escribir ambas fechas en un solo write para no disparar validación intermedia
                # start_date > end_date cuando se cambia campo por campo.
                rec.with_context(skip_sync_provider_report=True).write({
                    'start_date': next_start,
                    'end_date': next_end,
                })

            # Blindaje de estado por si venía desalineado.
            if rec.state != 'active':
                rec.state = 'active'

        # 2) Las que no aplican a renovación o siguen fuera de vigencia quedan vencidas.
        expired = self.search([
            ('state', '=', 'active'),
            ('end_date', '<', today),
            ('end_date', '!=', False),
        ])
        expired.action_expire()

    def name_get(self):
        result = []
        for rec in self:
            name = f"{rec.license_id.code} - {rec.partner_id.name}"
            if rec.quantity > 1:
                name += f" (x{rec.quantity})"
            result.append((rec.id, name))
        return result

    def get_price_for_subscription(self):
        """Método para obtener el precio de esta asignación para usar en subscription_nocount.
        Retorna un diccionario con la información de precio.
        """
        self.ensure_one()
        unit_price_usd = self._get_unit_price_usd()
        unit_price_cop = unit_price_usd * self.trm_rate if self.trm_rate > 0 else 0.0
        
        return {
            'unit_price_usd': unit_price_usd,
            'unit_price_cop': unit_price_cop,
            'total_price_usd': unit_price_usd * self.quantity,
            'total_price_cop': unit_price_cop * self.quantity,
            'trm_rate': self.trm_rate,
            'quantity': self.quantity,
            'product_id': self.license_id.product_id.id,
            'license_code': self.license_id.code,
        }

    @api.model
    def get_license_price_for_partner(self, partner_id, license_code, quantity=1, date=None):
        """Método estático para obtener el precio de una licencia para un cliente específico.
        Útil para ser llamado desde subscription_nocount.
        
        :param partner_id: ID del cliente
        :param license_code: Código de la licencia (ej: 'LIANT')
        :param quantity: Cantidad (default: 1)
        :param date: Fecha para calcular TRM (default: hoy)
        :return: Diccionario con información de precio
        """
        LicenseTemplate = self.env['license.template']
        LicenseAssignment = self.env['license.assignment']
        TRM = self.env['license.trm']
        
        # Buscar la licencia
        license_template = LicenseTemplate.search([('code', '=', license_code)], limit=1)
        if not license_template:
            return {
                'unit_price_usd': 0.0,
                'unit_price_cop': 0.0,
                'total_price_usd': 0.0,
                'total_price_cop': 0.0,
                'trm_rate': 0.0,
                'error': f'Licencia con código {license_code} no encontrada'
            }
        
        # Buscar si hay una asignación existente para este cliente
        assignment = LicenseAssignment.search([
            ('partner_id', '=', partner_id),
            ('license_id', '=', license_template.id),
            ('state', '=', 'active')
        ], limit=1)
        
        if assignment:
            # Usar el precio de la asignación existente
            unit_price_usd = assignment._get_unit_price_usd()
        else:
            # Calcular precio desde lista de precios o plantilla
            partner = self.env['res.partner'].browse(partner_id)
            if partner and license_template.product_id:
                pricelist = partner.property_product_pricelist
                if pricelist:
                    try:
                        price = pricelist._get_product_price(
                            license_template.product_id,
                            quantity=quantity,
                            partner=partner,
                            date=date or fields.Date.today(),
                            uom_id=license_template.product_id.uom_id.id
                        )
                        if pricelist.currency_id.name == 'USD':
                            unit_price_usd = price
                        elif pricelist.currency_id.name == 'COP':
                            cutoff_day = 6
                            if license_template.name and hasattr(license_template.name, 'get_trm_cutoff_day'):
                                cutoff_day = license_template.name.get_trm_cutoff_day()
                            trm_rate = TRM.get_trm_for_date(date, cutoff_day=cutoff_day) if date else TRM.get_trm_for_date(cutoff_day=cutoff_day)
                            unit_price_usd = price / trm_rate if trm_rate > 0 else 0.0
                        else:
                            usd_currency = self.env.ref('base.USD', raise_if_not_found=False)
                            if usd_currency and pricelist.currency_id:
                                unit_price_usd = pricelist.currency_id._convert(
                                    price, usd_currency, self.env.company, date or fields.Date.today()
                                )
                            else:
                                unit_price_usd = 0.0  # Los costos ahora vienen de la lista de precios
                    except Exception:
                        unit_price_usd = license_template.cost_usd or 0.0
                else:
                    unit_price_usd = license_template.cost_usd or 0.0
            else:
                unit_price_usd = license_template.cost_usd or 0.0
        
        # Calcular TRM y precio en COP
        cutoff_day = 6
        if license_template.name and hasattr(license_template.name, 'get_trm_cutoff_day'):
            cutoff_day = license_template.name.get_trm_cutoff_day()
        trm_rate = TRM.get_trm_for_date(date, cutoff_day=cutoff_day) if date else TRM.get_trm_for_date(cutoff_day=cutoff_day)
        unit_price_cop = unit_price_usd * trm_rate
        
        return {
            'unit_price_usd': unit_price_usd,
            'unit_price_cop': unit_price_cop,
            'total_price_usd': unit_price_usd * quantity,
            'total_price_cop': unit_price_cop * quantity,
            'trm_rate': trm_rate,
            'quantity': quantity,
            'product_id': license_template.product_id.id,
            'license_code': license_code,
        }
    
    def action_view_license_details(self):
        """Abre la vista de detalles de esta asignación de licencia."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Detalles de Licencia'),
            'res_model': 'license.assignment',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_view_license_details_by_product(self):
        """Abre la vista de detalles de licencias para el producto de esta asignaci