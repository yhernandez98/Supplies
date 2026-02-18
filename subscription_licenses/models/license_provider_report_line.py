# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.tools import float_round


class LicenseProviderReportLine(models.Model):
    _name = 'license.provider.report.line'
    _description = 'Línea de reporte / facturación del proveedor'
    _order = 'client_name asc, product_name asc, start_date desc, id desc'

    provider_partner_id = fields.Many2one(
        'license.provider.partner',
        string='Proveedor',
        required=True,
        ondelete='cascade',
    )
    report_period = fields.Date(
        string='Periodo facturación',
        help='Periodo del reporte (ej. 2026-01-12 para reporte de enero 2026).',
    )
    # Cliente: nombre libre o enlace a contacto
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        ondelete='set null',
        help='Cliente en Odoo si ya está identificado.',
    )
    client_name = fields.Char(
        string='Cliente',
        help='Nombre del cliente tal como viene en el reporte (Cliente Final / Customer).',
    )
    # Producto / oferta
    product_id = fields.Many2one(
        'product.product',
        string='Producto (Odoo)',
        ondelete='set null',
        domain=[('type', '=', 'service')],
    )
    product_name = fields.Char(
        string='Producto / Oferta',
        help='Nombre del producto u oferta tal como viene en el reporte (Producto / Offer Name).',
    )
    quantity = fields.Integer(string='Cantidad', default=1)
    start_date = fields.Date(
        string='Fecha inicio',
        help='Fecha de inicio del periodo (misma que la asignación al cliente).',
    )
    end_date = fields.Date(
        string='Fecha fin',
        help='Fecha de fin del periodo (misma que la asignación al cliente).',
    )
    cut_off_date = fields.Date(
        string='Fecha de corte / aniversario',
        help='Fecha de corte o de aniversario (por defecto se toma la fecha fin de la asignación).',
    )
    contract_type = fields.Selection(
        [
            ('monthly_monthly', 'Mensual'),
            ('annual_monthly_commitment', 'Anual Compromiso Mensual'),
            ('annual', 'Anual'),
        ],
        string='Contrato',
    )
    billing_cycle = fields.Char(
        string='Ciclo facturación',
        help='Ej. MONTHLY, ANNUAL, Mensual.',
    )
    movement_type = fields.Char(
        string='Movimiento',
        help='Ej. renew, new, cycleCharge, addQuantity, cancelImmediate.',
    )
    unit_price_usd = fields.Float(string='Precio unitario', digits=(16, 2))
    total_price_usd = fields.Float(string='Precio total', digits=(16, 2))
    provider_cost_usd = fields.Float(
        string='Costo Proveedor',
        digits=(16, 2),
        help='Costo que paga al proveedor (se rellena desde la asignación al usar Rellenar desde asignaciones).',
    )
    # Precio a cliente desde lista de precios (misma lógica que suscripción/asignación)
    unit_price_pricelist_usd = fields.Float(
        string='Precio al Cliente',
        compute='_compute_price_from_pricelist',
        digits=(16, 2),
        help='Precio unitario en USD obtenido de la lista de precios del cliente (igual que en suscripción).',
    )
    total_price_pricelist_usd = fields.Float(
        string='Total Precio Cliente',
        compute='_compute_price_from_pricelist',
        digits=(16, 2),
        help='Precio total en USD desde la lista de precios del cliente (cantidad × precio unit. lista).',
    )
    # Costo total proveedor = Cantidad × Costo proveedor
    total_provider_cost_usd = fields.Float(
        string='Costo Total Proveedor',
        compute='_compute_totals_and_profit',
        digits=(16, 2),
        help='Cantidad × Costo proveedor.',
    )
    # Ganancia unitaria = Precio a cliente (unit.) − Costo proveedor (unit.)
    profit_unit_usd = fields.Float(
        string='Ganancia',
        compute='_compute_totals_and_profit',
        digits=(16, 2),
        help='Precio unit. a cliente − Costo proveedor (ganancia por unidad).',
    )
    # Ganancia total = Ganancia × Cantidad
    profit_total_usd = fields.Float(
        string='Ganancia Total',
        compute='_compute_totals_and_profit',
        digits=(16, 2),
        help='Ganancia unitaria × Cantidad.',
    )

    @api.depends('quantity', 'provider_cost_usd', 'unit_price_pricelist_usd', 'total_price_pricelist_usd',
                 'partner_id', 'product_id', 'assignment_id')
    def _compute_totals_and_profit(self):
        for rec in self:
            qty = rec.quantity or 0
            rec.total_provider_cost_usd = float_round((rec.provider_cost_usd or 0.0) * qty, precision_digits=2)
            unit_profit = (rec.unit_price_pricelist_usd or 0.0) - (rec.provider_cost_usd or 0.0)
            rec.profit_unit_usd = float_round(unit_profit, precision_digits=2)
            rec.profit_total_usd = float_round(unit_profit * qty, precision_digits=2)

    @api.depends('partner_id', 'product_id', 'quantity', 'assignment_id')
    def _compute_price_from_pricelist(self):
        """Obtiene el precio a cliente desde la lista de precios (misma fuente que suscripción)."""
        for rec in self:
            unit = 0.0
            if rec.assignment_id:
                unit = rec.assignment_id._get_unit_price_usd()
            elif rec.partner_id and rec.product_id:
                unit = rec._get_unit_price_from_pricelist_usd()
            rec.unit_price_pricelist_usd = unit
            rec.total_price_pricelist_usd = float_round(unit * (rec.quantity or 0), precision_digits=2)

    def _get_unit_price_from_pricelist_usd(self):
        """Precio unitario en USD desde lista de precios del cliente (igual que en asignación/suscripción)."""
        self.ensure_one()
        if not self.partner_id or not self.product_id:
            return 0.0
        product = self.product_id
        pricelist = self.partner_id.property_product_pricelist
        usd_currency = self.env.ref('base.USD', raise_if_not_found=False)
        trm_rate = 0.0
        if 'license.trm' in self.env:
            trm_rate = self.env['license.trm'].get_trm_for_date() or 0.0
        # 1) Suscripción del cliente -> _get_price_for_product
        if 'subscription.subscription' in self.env and hasattr(self.env['subscription.subscription'], '_get_price_for_product'):
            try:
                sub = self.env['subscription.subscription'].search([('partner_id', '=', self.partner_id.id)], limit=1)
                if sub:
                    price = sub._get_price_for_product(product, 1.0)
                    if price is not None:
                        curr = sub.partner_id.property_product_pricelist.currency_id if sub.partner_id and sub.partner_id.property_product_pricelist else None
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
        # 2) Precios recurrentes (sale.subscription.pricing) — pestaña "Precios recurrentes" de la lista
        if pricelist and 'sale.subscription.pricing' in self.env:
            try:
                Pricing = self.env['sale.subscription.pricing']
                product_tmpl_field = 'product_template_id' if 'product_template_id' in Pricing._fields else 'product_tmpl_id'
                domain = [
                    ('pricelist_id', '=', pricelist.id),
                    (product_tmpl_field, '=', product.product_tmpl_id.id),
                ]
                pricing = Pricing.search(domain, limit=1)
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
        # 3) Lista de precios directa (reglas de precio)
        if pricelist:
            try:
                price = pricelist._get_product_price(
                    product,
                    quantity=self.quantity or 1.0,
                    partner=self.partner_id,
                    date=fields.Date.today(),
                    uom_id=product.uom_id.id,
                )
                if price is not None:
                    if pricelist.currency_id.name == 'USD':
                        return float(price)
                    if pricelist.currency_id.name == 'COP' and trm_rate and trm_rate > 0:
                        return float(price) / trm_rate
                    if pricelist.currency_id and usd_currency:
                        try:
                            return pricelist.currency_id._convert(float(price), usd_currency, self.env.company, fields.Date.today())
                        except Exception:
                            pass
            except Exception:
                pass
        return 0.0
    external_order_id = fields.Char(string='Order ID / MPN', help='ID externo del pedido o MPN.')
    subscription_id = fields.Char(string='Suscripción ID', help='ID de suscripción en el reporte.')
    assignment_id = fields.Many2one(
        'license.assignment',
        string='Asignación (Odoo)',
        ondelete='set null',
        help='Vínculo opcional con la asignación en Odoo para conciliar.',
    )
    auto_renewal = fields.Boolean(
        string='Renovación automática',
        default=False,
        help='Sí/No. Se rellena desde la asignación al usar Rellenar desde asignaciones. Si lo edita aquí, se actualiza también en la asignación.',
    )
    notes = fields.Char(string='Notas')

    def write(self, vals):
        res = super().write(vals)
        if 'auto_renewal' in vals and vals.get('auto_renewal') is not None:
            for rec in self:
                if rec.assignment_id:
                    rec.assignment_id.auto_renewal = rec.auto_renewal
        return res

    def name_get(self):
        result = []
        for rec in self:
            name = rec.client_name or (rec.partner_id.name if rec.partner_id else '')
            product = rec.product_name or (rec.product_id.name if rec.product_id else '')
            if product:
                name = '%s - %s' % (name or 'Sin cliente', product)
            result.append((rec.id, name or _('Línea de reporte')))
        return result
