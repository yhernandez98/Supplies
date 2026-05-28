# -*- coding: utf-8 -*-
import datetime
import logging
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_round

_logger = logging.getLogger(__name__)

_logger = logging.getLogger(__name__)


class SubscriptionMonthlyBillable(models.Model):
    _name = 'subscription.monthly.billable'
    _description = 'Facturable mensual guardado (para facturación mes vencido)'
    _order = 'reference_year desc, reference_month desc'

    subscription_id = fields.Many2one(
        'subscription.subscription',
        string='Suscripción',
        required=True,
        ondelete='cascade',
        index=True,
    )
    reference_year = fields.Integer(string='Año', required=True)
    reference_month = fields.Integer(string='Mes', required=True)
    total_amount = fields.Monetary(
        string='Total Mensual',
        currency_field='currency_id',
        digits=(16, 2),
        readonly=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        related='subscription_id.currency_id',
        readonly=True,
    )
    line_ids = fields.One2many(
        'subscription.monthly.billable.line',
        'billable_id',
        string='Líneas',
        readonly=True,
    )
    line_trm_usd_ids = fields.Many2many(
        'subscription.monthly.billable.line',
        string='Líneas licencia USD (TRM)',
        compute='_compute_line_trm_usd_ids',
        readonly=True,
        help='Solo líneas de licencia guardadas con costo en USD (pestaña TRM aplicadas).',
    )
    name = fields.Char(
        string='Referencia',
        compute='_compute_name',
        store=True,
        readonly=True,
    )

    @api.depends('line_ids', 'line_ids.is_license', 'line_ids.is_cost_usd')
    def _compute_line_trm_usd_ids(self):
        for billable in self:
            billable.line_trm_usd_ids = billable.line_ids.filtered(
                lambda l: l.is_license and l.is_cost_usd
            )

    @api.depends('reference_year', 'reference_month', 'subscription_id.name')
    def _compute_name(self):
        months = (
            'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
            'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
        )
        for rec in self:
            if rec.reference_year and rec.reference_month and 1 <= rec.reference_month <= 12:
                month_name = months[rec.reference_month - 1]
                sub_name = rec.subscription_id.name or _('Suscripción')
                rec.name = f'{sub_name} - {month_name} {rec.reference_year}'
            else:
                rec.name = rec.subscription_id.name or _('Facturable mensual')

    def action_apply_trm(self):
        """Recalcula TRM en facturable guardado para líneas de licencia en USD.
        Usa el mes del facturable como base:
        - categorías default (día 6): TRM del mes siguiente,
        - categorías personalizadas: TRM del mes del facturable.
        """
        self.ensure_one()
        if not (self.reference_year and self.reference_month and 1 <= self.reference_month <= 12):
            raise UserError(_('El facturable debe tener un año y mes válidos (1-12).'))
        if 'license.trm' not in self.env:
            raise UserError(_('El módulo de TRM no está disponible.'))
        subscription = self.subscription_id
        usd_categories = set()
        category_by_name = {}
        if 'license.assignment' in self.env and subscription and subscription.partner_id:
            license_domain = [
                ('partner_id', '=', subscription.partner_id.id),
                ('state', '=', 'active'),
            ]
            if subscription.location_id:
                license_domain.append(('location_id', '=', subscription.location_id.id))
            assignments = self.env['license.assignment'].search(license_domain)
            for la in assignments:
                if not la.license_id:
                    continue
                if not subscription._license_assignment_matches_subscription_plan(la):
                    continue
                category_name = (la.license_id.name and la.license_id.name.name) or 'Sin Categoría'
                category_key = (category_name or '').strip().upper()
                if category_key and category_key not in category_by_name:
                    category_by_name[category_key] = la.license_id.name
                product = la.license_id.product_id
                if not product:
                    continue
                price_currency = subscription._get_currency_for_product_price(product, subscription.plan_id)
                if not price_currency:
                    pricelist = subscription.pricelist_id or (subscription.partner_id.property_product_pricelist if subscription.partner_id else False)
                    price_currency = pricelist.currency_id if pricelist else False
                if price_currency and (price_currency.name or '').upper() == 'USD':
                    usd_categories.add(category_key)

        license_lines = self.line_ids.filtered(
            lambda l: l.is_license and (
                l.is_cost_usd
                or ((l.product_display_name or '').strip().upper() in usd_categories)
            )
        )
        if not license_lines and self.line_ids:
            return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
                'title': _('Sin licencias'),
                'message': _('No hay líneas de licencia en USD para recalcular TRM en este facturable.'),
                'type': 'info',
                'sticky': False,
            }}
        trm_model = self.env['license.trm']
        Category = self.env['license.category'] if 'license.category' in self.env else False

        # Mes base = SIEMPRE el del facturable guardado (no el de la suscripción al abrir otro mes).
        billable_base = datetime.date(int(self.reference_year), int(self.reference_month), 1)

        def _trm_lookup_date_for_saved_line(category_rec):
            use_default_cutoff = True
            if category_rec and hasattr(category_rec, 'use_default_trm_cutoff'):
                use_default_cutoff = bool(category_rec.use_default_trm_cutoff)
            return billable_base + relativedelta(months=1) if use_default_cutoff else billable_base

        applied_count = 0
        for line in license_lines:
            category_name = (line.product_display_name or '').strip()
            category_key = category_name.upper()
            category_rec = category_by_name.get(category_key)
            if Category and category_name:
                if not category_rec:
                    category_rec = Category.search([('name', '=', category_name)], limit=1)
                if not category_rec:
                    category_rec = Category.search([('name', 'ilike', category_name)], limit=1)
            trm_date = _trm_lookup_date_for_saved_line(category_rec)
            cutoff_day = subscription._get_license_category_cutoff_day(category_rec)
            trm_rate = trm_model.get_trm_for_date(trm_date, cutoff_day=cutoff_day) or 0.0
            if not trm_rate or trm_rate <= 0:
                continue

            # Evitar sobreaplicar: si ya había TRM aplicada, recuperar base USD aproximada.
            base_usd = float(line.cost or 0.0)
            if line.trm_rate_applied and line.trm_rate_applied > 0:
                base_usd = base_usd / float(line.trm_rate_applied)
            new_cost_cop = float_round(base_usd * trm_rate, precision_digits=2)

            line.write({
                'cost': new_cost_cop,
                'trm_rate_applied': trm_rate,
                'trm_cutoff_day_applied': cutoff_day or 6,
                'trm_date_applied': trm_date,
                'is_cost_usd': True,
            })
            applied_count += 1

        if applied_count <= 0:
            raise UserError(_('No se pudo aplicar TRM: valide que existan TRM configuradas para los cortes requeridos de este facturable.'))

        new_total = sum(self.line_ids.mapped('cost'))
        self.write({'total_amount': float_round(new_total, precision_digits=2)})
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('TRM aplicada'),
            'message': _('Se recalcularon %s líneas de licencia en USD con su TRM por corte. Total actualizado: %s.')
                % (applied_count, self.currency_id.format(new_total)),
            'type': 'success',
            'sticky': False,
        }}

    def action_generate_proforma(self):
        """Genera una proforma a partir de este facturable guardado y abre el movimiento."""
        self.ensure_one()
        if not self.subscription_id:
            raise UserError(_('Este facturable no tiene suscripción asociada.'))
        if not self.line_ids:
            raise UserError(_('El facturable guardado no tiene líneas para generar la proforma.'))
        sub = self.subscription_id
        # Quitar del contexto active_id/default_subscription_id del billable para que las líneas
        # no reciban subscription_id = self.id (facturable); la creación usa solo la suscripción
        ctx = dict(self.env.context)
        ctx.pop('active_id', None)
        ctx.pop('active_ids', None)
        ctx.pop('active_model', None)
        ctx.pop('default_subscription_id', None)
        move = sub.with_context(**ctx)._create_proforma_move_from_billable(self)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': move.id,
            'context': {'hide_account_column': True},
        }

    def _get_export_saved_license_details(self):
        """Datos guardados para exportar (licencias) desde el facturable mensual."""
        self.ensure_one()
        subscription = self.subscription_id
        license_lines = self.line_ids.filtered(lambda l: l.is_license)
        if not subscription or not license_lines:
            return license_lines.mapped('detail_ids')

        # Importante: algunos facturables guardados pueden existir antes de los últimos fixes.
        # Para que el Excel/PDF salga consistente con "en vivo", recalculamos EN MEMORIA
        # los detalles de licencias por serial (sin modificar el facturable guardado).
        export_rows = []
        Detail = self.env['subscription.monthly.billable.line.detail']
        for line in license_lines:
            category_name = (line.product_display_name or '').strip() or 'Sin Categoría'
            stub = type(
                'GroupedProductStub',
                (),
                {
                    'license_category': category_name,
                    'quantity': line.quantity or 0,
                    'cost': line.cost or 0.0,
                },
            )()
            rows = subscription._save_monthly_billable_license_details(
                line, stub, Detail, persist=False
            )
            if rows:
                export_rows.extend(rows)

        return export_rows

    def _get_export_saved_equipment_details(self):
        """Datos guardados para exportar (equipos) desde el facturable mensual."""
        self.ensure_one()
        equipment_lines = self.line_ids.filtered(lambda l: not l.is_license)
        return equipment_lines.mapped('detail_ids')

    def action_view_licencias_unificadas_guardadas(self):
        """Abre una vista unificada de las licencias guardadas en este facturable."""
        self.ensure_one()
        license_line_ids = self.line_ids.filtered(lambda l: l.is_license).ids
        if not license_line_ids:
            return {'type': 'ir.actions.act_window_close'}

        view_id = self.env.ref('subscription_nocount.view_subscription_monthly_billable_line_detail_list').id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Ver Licencias'),
            'res_model': 'subscription.monthly.billable.line.detail',
            'view_mode': 'list',
            'views': [(view_id, 'list')],
            'domain': [('billable_line_id', 'in', license_line_ids)],
            'context': {
                'create': False,
                'edit': False,
                'delete': False,
                'group_by': ['business_line_name'],
            },
        }

    def action_view_equipos_unificados_guardados(self):
        """Abre una vista unificada de los equipos guardados en este facturable."""
        self.ensure_one()
        equipment_line_ids = self.line_ids.filtered(lambda l: not l.is_license).ids
        if not equipment_line_ids:
            return {'type': 'ir.actions.act_window_close'}

        view_id = self.env.ref('subscription_nocount.view_subscription_monthly_billable_line_detail_equipment_list').id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Ver Equipos'),
            'res_model': 'subscription.monthly.billable.line.detail',
            'view_mode': 'list',
            'views': [(view_id, 'list')],
            'domain': [('billable_line_id', 'in', equipment_line_ids)],
            'context': {
                'create': False,
                'edit': False,
                'delete': False,
                'group_by': ['business_line_name'],
            },
        }

    def action_open_export_licenses_equipos_wizard_monthly(self):
        """Abre el wizard de exportación (Excel/PDF) usando este facturable guardado."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Exportar Licencias y Equipos'),
            'res_model': 'subscription.export.licenses.equipos.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_subscription_id': self.subscription_id.id if self.subscription_id else False,
                'default_billable_id': self.id,
            },
        }


class SubscriptionMonthlyBillableLine(models.Model):
    _name = 'subscription.monthly.billable.line'
    _description = 'Línea del facturable mensual guardado'

    billable_id = fields.Many2one(
        'subscription.monthly.billable',
        string='Facturable mensual',
        required=True,
        ondelete='cascade',
        index=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        readonly=True,
    )
    product_display_name = fields.Char(string='Producto', readonly=True)
    business_line_id = fields.Many2one(
        'product.business.line',
        string='Línea de negocio',
        readonly=True,
    )
    quantity = fields.Integer(string='Cantidad', readonly=True)
    cost = fields.Monetary(
        string='Costo',
        currency_field='currency_id',
        digits=(16, 2),
        readonly=True,
    )
    is_license = fields.Boolean(string='Es licencia', readonly=True, help='True si esta línea es de licencias (Ver Detalles usa vista de 4 columnas).')
    is_cost_usd = fields.Boolean(
        string='Costo en USD',
        readonly=True,
        help='True cuando la línea se guardó con moneda base USD.',
    )
    usd_currency_id = fields.Many2one(
        'res.currency',
        string='USD',
        compute='_compute_usd_cost_reference_fields',
        readonly=True,
    )
    cost_usd_reference = fields.Monetary(
        string='Costo USD',
        currency_field='usd_currency_id',
        digits=(16, 2),
        compute='_compute_usd_cost_reference_fields',
        readonly=True,
        help='Referencia en USD: costo COP entre TRM aplicada, o monto USD si aún no hay TRM.',
    )
    trm_rate_applied = fields.Float(
        string='TRM aplicada',
        digits=(16, 4),
        readonly=True,
        help='TRM aplicada a esta línea de licencia al guardar/recalcular facturable.'
    )
    trm_cutoff_day_applied = fields.Integer(
        string='Corte TRM',
        readonly=True,
        help='Día de corte TRM usado para esta línea de licencia.'
    )
    trm_date_applied = fields.Date(
        string='Fecha base TRM',
        readonly=True,
        help='Primer día del mes en el que se consultó la TRM (uso interno).'
    )
    trm_month_label = fields.Char(
        string='Mes TRM',
        compute='_compute_trm_month_label',
        readonly=True,
        help='Nombre del mes de la TRM (solo mes, sin día; el corte va en Resumen).',
    )
    trm_applied_display = fields.Char(
        string='TRM aplicada',
        compute='_compute_trm_applied_display',
        readonly=True,
        help='Resumen legible de TRM aplicada para esta línea.'
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='billable_id.currency_id',
        readonly=True,
    )
    detail_ids = fields.One2many(
        'subscription.monthly.billable.line.detail',
        'billable_line_id',
        string='Detalles por serial',
        readonly=True,
    )

    @api.depends('cost', 'trm_rate_applied', 'is_cost_usd', 'is_license')
    def _compute_usd_cost_reference_fields(self):
        """Un solo compute: la moneda USD debe existir antes del Monetary (evita 500 por orden de cómputo)."""
        usd = self.env.ref('base.USD', raise_if_not_found=False) or self.env['res.currency'].search(
            [('name', '=', 'USD')], limit=1
        )
        usd_id = usd.id if usd else False
        for rec in self:
            rec.usd_currency_id = usd_id
            if not usd_id or not rec.is_license or not rec.is_cost_usd:
                rec.cost_usd_reference = 0.0
                continue
            if rec.trm_rate_applied and rec.trm_rate_applied > 0:
                rec.cost_usd_reference = float_round(
                    float(rec.cost or 0.0) / float(rec.trm_rate_applied),
                    precision_digits=2,
                )
            else:
                rec.cost_usd_reference = float_round(float(rec.cost or 0.0), precision_digits=2)

    @api.depends('trm_date_applied')
    def _compute_trm_month_label(self):
        months = (
            'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
            'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
        )
        for rec in self:
            d = rec.trm_date_applied
            if not d or not hasattr(d, 'month') or not (1 <= d.month <= 12):
                rec.trm_month_label = ''
                continue
            rec.trm_month_label = months[d.month - 1]

    @api.depends('is_license', 'trm_rate_applied', 'trm_cutoff_day_applied', 'trm_date_applied')
    def _compute_trm_applied_display(self):
        for rec in self:
            if not rec.is_license or not rec.trm_rate_applied:
                rec.trm_applied_display = ''
                continue
            month_label = rec.trm_date_applied.strftime('%Y-%m') if rec.trm_date_applied else ''
            rec.trm_applied_display = _('TRM %s | Corte %s | Mes %s') % (
                rec.trm_rate_applied,
                rec.trm_cutoff_day_applied or 6,
                month_label,
            )

    def _prepare_invoice_line_values(self, subscription):
        """Prepara los valores para una línea de factura desde una línea del facturable guardado (misma columna que el facturable: producto, línea de negocio, cantidad, costo)."""
        self.ensure_one()
        price_unit = (self.cost / float(self.quantity)) if self.quantity and self.quantity > 0 else 0.0
        # Dejamos name vacío para que la columna Etiqueta no repita lo de Producto (evitar duplicación que no gusta al jefe)
        tax_ids = []
        if self.product_id and self.product_id.taxes_id:
            tax_ids = [(6, 0, self.product_id.taxes_id.ids)]
        vals = {
            'product_id': self.product_id.id if self.product_id else False,
            'name': '',
            'quantity': float_round(float(self.quantity or 0), precision_digits=2),
            'price_unit': float_round(price_unit, precision_digits=2),
            'tax_ids': tax_ids,
            'subscription_billable_line_id': self.id,
            'subscription_business_line_id': self.business_line_id.id if self.business_line_id else False,
        }
        return vals

    def action_view_details(self):
        """Abre la lista de seriales guardados. Licencias: 4 columnas. Equipos: columnas completas (imagen)."""
        self.ensure_one()
        if self.is_license:
            view_id = self.env.ref('subscription_nocount.view_subscription_monthly_billable_line_detail_list').id
        else:
            view_id = self.env.ref('subscription_nocount.view_subscription_monthly_billable_line_detail_equipment_list').id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Detalles - %s') % (self.product_display_name or _('Línea')),
            'res_model': 'subscription.monthly.billable.line.detail',
            'view_mode': 'list',
            'views': [(view_id, 'list')],
            'domain': [('billable_line_id', '=', self.id)],
            'context': {'create': False, 'edit': False, 'delete': True},
        }


class SubscriptionMonthlyBillableLineDetail(models.Model):
    _name = 'subscription.monthly.billable.line.detail'
    _description = 'Detalle por serial del facturable mensual (solo actividad del mes)'
    _order = 'business_line_name, product_name, inventory_plate, lot_name'

    billable_line_id = fields.Many2one(
        'subscription.monthly.billable.line',
        string='Línea facturable',
        required=True,
        ondelete='cascade',
        index=True,
    )
    location_id = fields.Many2one(
        'stock.location',
        string='Ubicación',
        readonly=True,
        help='Ubicación del equipo (igual que en Series con licencias).',
    )
    lot_id = fields.Many2one('stock.lot', string='Serial/Lote', readonly=True)
    lot_name = fields.Char(string='Número de serie/lote', readonly=True)
    product_name = fields.Char(string='Producto', readonly=True, help='Equipo/hardware (licencias) o producto (equipos renting).')
    business_line_name = fields.Char(
        string='Agrupamiento',
        readonly=True,
        compute='_compute_business_line_name',
        store=True,
        help='Agrupamiento para organizar licencias/equipos (viene del facturable guardado).',
    )
    license_service_name = fields.Char(
        string='Licencia/Servicio Asignado',
        readonly=True,
        help='Nombre del servicio o licencia asignada (solo para líneas de licencia).',
    )
    inventory_plate = fields.Char(string='Placa de Inventario', readonly=True)
    assigned_user_id = fields.Many2one(
        'res.partner',
        string='Usuario Asignado',
        readonly=True,
        group_operator=False,
        help='Contacto usuario del serial (stock.lot.related_partner_id) al guardar el facturable.',
    )
    assigned_user_display_name = fields.Char(
        string='Usuario Asignado',
        compute='_compute_assigned_user_display_name',
        store=False,
        help='Nombre del contacto sin prefijo de compañía (solo para listas e informes).',
    )
    cost_renting = fields.Monetary(
        string='Costo Renting',
        currency_field='currency_id',
        digits=(16, 2),
        readonly=True,
        group_operator=False,
    )
    cost_additional = fields.Monetary(
        string='Costo Adicional',
        currency_field='currency_id',
        digits=(16, 2),
        readonly=True,
        compute='_compute_cost_additional',
        help='Suma de los costos de los elementos asociados con costo (pestaña Elementos Con Costo del serial).',
        group_operator=False,
    )
    cost_renting_total = fields.Monetary(
        string='Costo Renting (total)',
        currency_field='currency_id',
        digits=(16, 2),
        readonly=True,
        compute='_compute_cost_additional',
        help='Costo Renting base + Costo adicional (elementos con costo).',
        group_operator=False,
    )
    days_total_month = fields.Integer(string='Días total del mes', readonly=True, group_operator=False)
    current_day_of_month = fields.Integer(string='Día del mes en curso', readonly=True, group_operator=False)
    entry_date = fields.Date(string='Fecha Activación Renting', readonly=True)
    exit_date = fields.Date(string='Fecha Finalización Renting', readonly=True)
    reining_plazo = fields.Char(string='Plazo Renting', readonly=True)
    days_total_on_site = fields.Integer(string='Días totales en sitio', readonly=True, group_operator=False)
    days_in_service = fields.Integer(string='Días En Servicio', readonly=True, group_operator=False)
    tiempo_en_sitio_display = fields.Char(
        string='Tiempo En Sitio',
        compute='_compute_tiempo_displays',
        help='Tiempo en sitio en formato "X meses y Y días".',
    )
    tiempo_restante_display = fields.Char(
        string='Tiempo Restante',
        compute='_compute_tiempo_displays',
        help='Tiempo restante hasta fecha finalización.',
    )
    cost_daily = fields.Monetary(
        string='Costo Diario',
        currency_field='currency_id',
        digits=(16, 2),
        readonly=True,
        compute='_compute_cost_daily_from_total',
        help='Costo diario calculado a partir del Costo Renting total (base + adicional).',
        group_operator=False,
    )
    cost_to_date = fields.Monetary(
        string='Costo Días En Servicio',
        currency_field='currency_id',
        digits=(16, 2),
        readonly=True,
        compute='_compute_cost_daily_from_total',
        help='Costo días en servicio = Costo diario × Días en servicio.',
        group_operator=False,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='billable_line_id.currency_id',
        readonly=True,
    )
    month_display = fields.Char(
        string='Mes',
        compute='_compute_month_display',
        help='Mes y año del facturable (ej. febrero 2026).',
    )

    @api.depends('billable_line_id', 'billable_line_id.product_display_name')
    def _compute_business_line_name(self):
        for rec in self:
            rec.business_line_name = rec.billable_line_id.product_display_name or ''

    @api.depends('assigned_user_id', 'assigned_user_id.name')
    def _comput