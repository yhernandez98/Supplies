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
    name = fields.Char(
        string='Referencia',
        compute='_compute_name',
        store=True,
        readonly=True,
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
        """Recalcula los importes de las líneas de licencia usando la TRM del mes SIGUIENTE al facturable.
        Mes vencido: la TRM vigente es la que aplica desde el día 6 del mes siguiente (ej. facturable febrero → TRM de marzo)."""
        self.ensure_one()
        if not (self.reference_year and self.reference_month and 1 <= self.reference_month <= 12):
            raise UserError(_('El facturable debe tener un año y mes válidos (1-12).'))
        # TRM del mes siguiente (mes vencido: se usa la TRM que rige desde el 6 del mes siguiente)
        trm_month = self.reference_month + 1
        trm_year = self.reference_year
        if trm_month > 12:
            trm_month = 1
            trm_year += 1
        trm_date = datetime.date(trm_year, trm_month, 1)
        trm_rate = 0.0
        if 'license.trm' in self.env:
            trm_rate = self.env['license.trm'].get_trm_for_date(trm_date)
        if not trm_rate or trm_rate <= 0:
            raise UserError(
                _('No hay TRM configurada para %s (mes siguiente al facturable). Configure la TRM de ese mes antes de aplicar.')
                % trm_date.strftime('%B %Y')
            )
        subscription = self.subscription_id
        license_lines = self.line_ids.filtered(lambda l: l.is_license)
        if not license_lines and self.line_ids:
            return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
                'title': _('Sin licencias'),
                'message': _('No hay líneas de licencia en este facturable. Los importes de equipos no se modifican.'),
                'type': 'info',
                'sticky': False,
            }}
        if 'license.assignment' not in self.env:
            raise UserError(_('El módulo de licencias no está disponible.'))
        for line in license_lines:
            category_name = (line.product_display_name or '').strip() or 'Sin Categoría'
            license_domain = [
                ('partner_id', '=', subscription.partner_id.id),
                ('state', '=', 'active'),
                ('license_id', '!=', False),
            ]
            if subscription.location_id:
                license_domain.append(('location_id', '=', subscription.location_id.id))
            assignments = self.env['license.assignment'].search(license_domain)
            total_cost = 0.0
            for assignment in assignments:
                if not assignment.license_id or not assignment.license_id.product_id:
                    continue
                cat = (assignment.license_id.name.name if assignment.license_id.name else 'Sin Categoría') or 'Sin Categoría'
                if cat != category_name:
                    continue
                product = assignment.license_id.product_id
                unit_cop = subscription._get_license_unit_price_cop(product, trm_rate)
                qty = float(assignment.quantity or 0)
                total_cost += unit_cop * qty
            line.write({'cost': float_round(total_cost, precision_digits=2)})
        new_total = sum(self.line_ids.mapped('cost'))
        self.write({'total_amount': float_round(new_total, precision_digits=2)})
        _months = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre')
        trm_month_name = _months[trm_date.month - 1] if 1 <= trm_date.month <= 12 else trm_date.strftime('%B')
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('TRM aplicada'),
            'message': _('Se recalculó el costo de las licencias con la TRM de %s %s (mes siguiente al facturable). Total actualizado: %s.')
                % (trm_month_name, trm_date.year, self.currency_id.format(new_total)),
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

    def _prepare_invoice_line_values(self, subscription):
        """Prepara los valores para una línea de factura desde una línea del facturable guardado."""
        self.ensure_one()
        price_unit = (self.cost / float(self.quantity)) if self.quantity and self.quantity > 0 else 0.0
        name = self.product_display_name or (self.product_id.display_name if self.product_id else _('Línea'))
        if self.quantity and self.quantity > 1:
            name = '%s (%s %s)' % (name, _('Cantidad:'), self.quantity)
        tax_ids = []
        if self.product_id and self.product_id.taxes_id:
            tax_ids = [(6, 0, self.product_id.taxes_id.ids)]
        return {
            'product_id': self.product_id.id if self.product_id else False,
            'name': name,
            'quantity': float_round(float(self.quantity or 0), precision_digits=2),
            'price_unit': float_round(price_unit, precision_digits=2),
            'tax_ids': tax_ids,
        }

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
            'context': {'create': False, 'edit': False, 'delete': False},
        }


class SubscriptionMonthlyBillableLineDetail(models.Model):
    _name = 'subscription.monthly.billable.line.detail'
    _description = 'Detalle por serial del facturable mensual (solo actividad del mes)'
    _order = 'product_name, inventory_plate, lot_name'

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
    license_service_name = fields.Char(
        string='Licencia/Servicio Asignado',
        readonly=True,
        help='Nombre del servicio o licencia asignada (solo para líneas de licencia).',
    )
    inventory_plate = fields.Char(string='Placa de Inventario', readonly=True)
    cost_renting = fields.Monetary(
        string='Costo Renting',
        currency_field='currency_id',
        digits=(16, 2),
        readonly=True,
    )
    cost_additional = fields.Monetary(
        string='Costo Adicional',
        currency_field='currency_id',
        digits=(16, 2),
        readonly=True,
        compute='_compute_cost_additional',
        help='Suma de los costos de los elementos asociados con costo (pestaña Elementos Con Costo del serial).',
    )
    cost_renting_total = fields.Monetary(
        string='Costo Renting (total)',
        currency_field='currency_id',
        digits=(16, 2),
        readonly=True,
        compute='_compute_cost_additional',
        help='Costo Renting base + Costo adicional (elementos con costo).',
    )
    days_total_month = fields.Integer(string='Días total del mes', readonly=True)
    current_day_of_month = fields.Integer(string='Día del mes en curso', readonly=True)
    entry_date = fields.Date(string='Fecha Activación Renting', readonly=True)
    exit_date = fields.Date(string='Fecha Finalización Renting', readonly=True)
    reining_plazo = fields.Char(string='Plazo Renting', readonly=True)
    days_total_on_site = fields.Integer(string='Días totales en sitio', readonly=True)
    days_in_service = fields.Integer(string='Días En Servicio', readonly=True)
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
    )
    cost_to_date = fields.Monetary(
        string='Costo Días En Servicio',
        currency_field='currency_id',
        digits=(16, 2),
        readonly=True,
        compute='_compute_cost_daily_from_total',
        help='Costo días en servicio = Costo diario × Días en servicio.',
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

    @api.depends('billable_line_id', 'billable_line_id.billable_id', 'billable_line_id.billable_id.reference_year', 'billable_line_id.billable_id.reference_month')
    def _compute_month_display(self):
        months = (
            'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
            'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
        )
        for rec in self:
            billable = rec.billable_line_id.billable_id if rec.billable_line_id else None
            if billable and billable.reference_year and billable.reference_month and 1 <= billable.reference_month <= 12:
                rec.month_display = f'{months[billable.reference_month - 1]} {billable.reference_year}'
            else:
                rec.month_display = ''

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
            if not rec.entry_date:
                rec.tiempo_en_sitio_display = '0 días'
            else:
                end_site = today
                if rec.exit_date:
                    exit_d = rec.exit_date
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

    @api.depends('cost_renting_total', 'days_total_month', 'days_in_service')
    def _compute_cost_daily_from_total(self):
        """Costo diario y costo días en servicio a partir del Costo Renting total."""
        for rec in self:
            total = rec.cost_renting_total or 0.0
            days_month = rec.days_total_month or 0
            days_used = rec.days_in_service or 0
            rec.cost_daily = round(total / float(days_month), 2) if days_month else 0.0
            rec.cost_to_date = round((rec.cost_daily or 0.0) * float(days_used), 2)
