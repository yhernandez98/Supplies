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
        help='Costo que paga al proveedor. Defínalo aquí o en Ver licencias contratadas; no se sobrescribe con cero.',
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
        """Obtiene el precio a cliente directamente desde la lista de precios del cliente."""
        for rec in self:
            unit = rec._get_unit_price_from_pricelist_usd() if (rec.partner_id and rec.product_id) else 0.0
            rec.unit_price_pricelist_usd = unit
            rec.total_price_pricelist_usd = float_round(unit * (rec.quantity or 0), precision_digits=2)

    def _get_unit_price_from_pricelist_usd(self):
        """Precio unitario en USD desde la lista de precios del cliente (directo por producto)."""
        self.ensure_one()
        if not self.partner_id or not self.product_id:
            return 0.0
        product = self.product_id
        pricelist = self.partner_id.property_product_pricelist
        if not pricelist:
            return 0.0
        usd_currency = self.env.ref('base.USD', raise_if_not_found=False)
        trm_rate = 0.0
        if 'license.trm' in self.env:
            trm_rate = self.env['license.trm'].get_trm_for_date() or 0.0

        # 1) Buscar regla explícita en product.pricelist.item (la misma que editas en UI).
        try:
            Item = self.env['product.pricelist.item']
            item = Item.search([
                ('pricelist_id', '=', pricelist.id),
                '|',
                ('product_id', '=', product.id),
                ('product_tmpl_id', '=', product.product_tmpl_id.id),
            ], order='applied_on desc, min_quantity desc, id desc', limit=1)
            if item:
                qty = self.quantity or 1.0
                price_val = None
                # Precio fijo de la regla
                if item.compute_price == 'fixed' and hasattr(item, 'fixed_price'):
                    price_val = float(item.fixed_price or 0.0)
                # Fórmula/descuento u otros: usar motor nativo
                if price_val is None and hasattr(item, '_compute_price'):
                    price_val = item._compute_price(
                        product,
                        qty,
                        uom=product.uom_id,
                        date=fields.Datetime.now(),
                        currency=pricelist.currency_id,
                        plan_id=getattr(item, 'plan_id', False) and item.plan_id.id or None,
                    )
                    price_val = float(price_val or 0.0)

                curr = getattr(item, 'currency_id', False) or pricelist.currency_id
                if curr and curr.name == 'USD':
                    return price_val
                if curr and curr.name == 'COP':
                    return (price_val / trm_rate) if trm_rate and trm_rate > 0 else 0.0
                if curr and usd_currency:
                    try:
                        return curr._convert(price_val, usd_currency, self.env.company, fields.Date.today())
                    except Exception:
                        pass
                return price_val
        except Exception:
            pass

        # 2) Fallback estándar del pricelist.
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
        help='Si lo edita aquí, se actualiza también en la asignación.',
    )
    notes = fields.Char(string='Notas')

    def write(self, vals):
        # Nunca sobrescribir el Costo proveedor con 0: si en vals viene 0 (o vacío), no escribir este campo.
        if 'provider_cost_usd' in vals:
            incoming = vals.get('provider_cost_usd')
            is_zero = False
            if incoming is None or incoming is False:
                is_zero = True
            else:
                try:
                    is_zero = float(incoming) == 0.0
                except (TypeError, ValueError):
                    if isinstance(incoming, str) and not (incoming or '').strip():
                        is_zero = True
                    else:
                        is_zero = True  # valor no numérico: no sobrescribir con esto
            if is_zero:
                vals = dict(vals)
                vals.pop('provider_cost_usd', None)
                if not vals:
                    return True
        res = super().write(vals)
        if 'auto_renewal' in vals and vals.get('auto_renewal') is not None:
            for rec in self:
                if rec.assignment_id:
                    rec.assignment_id.with_context(skip_sync_provider_report=True).write({
                        'auto_renewal': rec.auto_renewal,
                    })
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
