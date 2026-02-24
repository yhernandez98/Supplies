# -*- coding: utf-8 -*-
import calendar
import datetime
from odoo import api, fields, models


class StockQuant(models.Model):
    _inherit = 'stock.quant'
    
    principal_lot_id = fields.Many2one(
        'stock.lot',
        string='Serial/Producto Principal (suscripción)',
        compute='_compute_principal_lot_info',
        store=False,
        help='Producto principal al que está asociado este componente/periférico/complemento'
    )
    
    principal_product_id = fields.Many2one(
        'product.product',
        string='Producto Principal (suscripción)',
        compute='_compute_principal_lot_info',
        store=False,
        help='Producto principal al que está asociado este componente/periférico/complemento'
    )
    
    inventory_plate = fields.Char(
        string='Placa Inventario (quant)',
        related='lot_id.inventory_plate',
        readonly=True,
        store=False,
        help='Placa de inventario del serial'
    )
    
    principal_lot_name = fields.Char(
        string='Serial Producto Asociado',
        compute='_compute_principal_lot_info',
        store=False,
        help='Número de serie/lote del producto principal asociado'
    )
    
    principal_lot_inventory_plate = fields.Char(
        string='Placa Producto Asociado',
        compute='_compute_principal_lot_info',
        store=False,
        help='Placa de inventario del producto principal asociado'
    )
    
    license_service_name = fields.Char(
        string='Licencia/Servicio Asignado',
        compute='_compute_license_service_name',
        store=False,
        help='Tipo de licencia o servicio asignado a este serial'
    )

    # Fechas de cobro por días (stock.lot: entry_date / exit_date — "para cobro por días").
    # Solo equipos/servicios; la lógica de licencias no se modifica.
    lot_entry_date = fields.Date(
        string='Fecha Activacion Renting',
        compute='_compute_lot_entry_date',
        readonly=True,
        help='Fecha de activación (entry_date o last_entry_date_display para coincidir con lo que ve la suscripción).',
    )

    @api.depends('lot_id', 'lot_id.entry_date', 'lot_id.last_entry_date_display',
                 'lot_id.last_subscription_id', 'lot_id.last_subscription_entry_date')
    def _compute_lot_entry_date(self):
        """Mostrar entry_date o last_entry_date_display; si la vista es de la suscripción de la que salió, usar last_subscription_entry_date."""
        subscription_id = self.env.context.get('subscription_id') or self.env.context.get('default_subscription_id')
        for q in self:
            lot = q.lot_id
            if not lot:
                q.lot_entry_date = False
                continue
            if subscription_id and getattr(lot, 'last_subscription_id', None) and lot.last_subscription_id.id == subscription_id:
                Override = self.env.get('subscription.lot.date.override')
                entry_display = getattr(lot, 'last_subscription_entry_date', None)
                if Override:
                    override = Override.search([
                        ('subscription_id', '=', subscription_id),
                        ('lot_id', '=', lot.id),
                    ], limit=1)
                    if override and override.entry_date:
                        entry_display = override.entry_date
                q.lot_entry_date = entry_display
                continue
            ent = getattr(lot, 'entry_date', None) and lot.entry_date
            last_ent = getattr(lot, 'last_entry_date_display', None) and lot.last_entry_date_display
            q.lot_entry_date = ent or last_ent
    lot_exit_date = fields.Date(
        string='Fecha Finalizacion Renting',
        compute='_compute_lot_exit_date',
        readonly=True,
        help='Fecha de salida del cliente (exit_date o last_exit_date_display para coincidir con lo que ve la suscripción).',
    )

    @api.depends('lot_id', 'lot_id.exit_date', 'lot_id.last_exit_date_display', 'lot_id.active_subscription_id',
                 'lot_id.last_subscription_id', 'lot_id.last_subscription_exit_date')
    def _compute_lot_exit_date(self):
        """Mostrar exit_date o last_exit_date_display. Si el lote está en ESTA suscripción (context), no mostrar.
        Si el lote salió de ESTA suscripción (last_subscription_id), usar last_subscription_exit_date."""
        subscription_id = self.env.context.get('subscription_id') or self.env.context.get('default_subscription_id')
        for q in self:
            lot = q.lot_id
            if not lot:
                q.lot_exit_date = False
                continue
            if subscription_id and getattr(lot, 'active_subscription_id', None) and lot.active_subscription_id.id == subscription_id:
                q.lot_exit_date = False
                continue
            if subscription_id and getattr(lot, 'last_subscription_id', None) and lot.last_subscription_id.id == subscription_id:
                Override = self.env.get('subscription.lot.date.override')
                exit_display = getattr(lot, 'last_subscription_exit_date', None)
                if Override:
                    override = Override.search([
                        ('subscription_id', '=', subscription_id),
                        ('lot_id', '=', lot.id),
                    ], limit=1)
                    if override and override.exit_date:
                        exit_display = override.exit_date
                q.lot_exit_date = exit_display
                continue
            ex = getattr(lot, 'exit_date', None) and lot.exit_date
            last_ex = getattr(lot, 'last_exit_date_display', None) and lot.last_exit_date_display
            q.lot_exit_date = ex or last_ex
    lot_reining_plazo = fields.Selection(
        related='lot_id.reining_plazo',
        readonly=True,
        string='Plazo Renting',
    )
    lot_days_total_on_site = fields.Integer(
        string='Días totales en sitio',
        compute='_compute_lot_days_total_on_site',
        help='Días totales desde Fecha Activación Renting hasta hoy (o hasta Fecha Finalización si ya salió).',
    )
    # Columnas para "Ver Detalles" en suscripción — según borrador Excel (Quants).
    lot_month_name = fields.Char(
        string='Mes',
        compute='_compute_lot_days_and_cost_to_date',
        help='Nombre del mes en curso (ej. enero).',
    )
    lot_days_total_month = fields.Integer(
        string='Días total del mes',
        compute='_compute_lot_days_and_cost_to_date',
        help='Días totales del mes actual (28, 29, 30 o 31).',
    )
    lot_current_day_of_month_display = fields.Integer(
        string='Día del mes en curso',
        compute='_compute_lot_days_and_cost_to_date',
        help='Día actual del mes (1-31).',
    )
    lot_days_used_in_month = fields.Integer(
        string='Días en servicio',
        compute='_compute_lot_days_and_cost_to_date',
        help='Días facturables en el mes (si el cliente cancela, se cobra solo hasta este número de días).',
    )
    lot_cost_renting_month = fields.Monetary(
        string='Costo renting',
        compute='_compute_lot_days_and_cost_to_date',
        currency_field='lot_cost_to_date_currency_id',
        help='Costo renting mes total.',
    )
    lot_cost_daily = fields.Monetary(
        string='Costo diario',
        compute='_compute_lot_days_and_cost_to_date',
        currency_field='lot_cost_to_date_currency_id',
        help='Costo renting del mes / días total del mes; base para prorratear si el cliente cancela.',
    )
    lot_cost_to_date_currency_id = fields.Many2one(
        'res.currency',
        compute='_compute_lot_days_and_cost_to_date',
    )
    lot_cost_to_date_current = fields.Monetary(
        string='Costo días en servicio',
        compute='_compute_lot_days_and_cost_to_date',
        currency_field='lot_cost_to_date_currency_id',
        help='Días en servicio × costo diario; es el monto a cobrar si el cliente cancela a mitad de mes.',
    )
    lot_current_day_of_month = fields.Integer(
        string='Día del mes (lot)',
        related='lot_id.current_day_of_month',
        readonly=True,
    )

    _MONTH_NAMES = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
                    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre')

    @api.depends('lot_id', 'lot_id.entry_date', 'lot_id.last_entry_date_display', 'lot_id.exit_date', 'lot_id.last_exit_date_display', 'lot_id.active_subscription_id', 'lot_id.subscription_service_product_id')
    def _compute_lot_days_and_cost_to_date(self):
        """
        Cobro por días (equipos/servicios). Siempre muestra desglose diario aunque haya
        fechas y plazo, para que si el cliente cancela a mitad de mes se vea claro
        cuánto cobrar (días en servicio × costo diario).
        Usa mes/año del contexto o mes actual. Días en servicio según fechas de ingreso/salida.
        """
        today = fields.Date.today()
        year = self.env.context.get('reference_year')
        month = self.env.context.get('reference_month')
        if not year or not (1 <= (month or 0) <= 12):
            year = today.year
            month = today.month
        month = month or today.month
        year = year or today.year
        days_in_month = calendar.monthrange(year, month)[1]
        if (year, month) == (today.year, today.month):
            current_day = min(today.day, days_in_month)
        else:
            current_day = days_in_month
        month_name = self._MONTH_NAMES[month - 1] if 1 <= month <= 12 else ''

        for quant in self:
            quant.lot_month_name = month_name
            quant.lot_days_total_month = days_in_month
            quant.lot_current_day_of_month_display = current_day
            quant.lot_days_used_in_month = days_in_month
            quant.lot_cost_renting_month = 0.0
            quant.lot_cost_daily = 0.0
            quant.lot_cost_to_date_currency_id = False
            quant.lot_cost_to_date_current = 0.0

            lot = quant.lot_id
            if not lot:
                continue

            entry = self._lot_date_to_python(
                getattr(lot, 'entry_date', None) or getattr(lot, 'last_entry_date_display', None)
            )
            exit_ = self._lot_date_to_python(
                getattr(lot, 'exit_date', None) or getattr(lot, 'last_exit_date_display', None)
            )

            if entry is None and exit_ is None:
                days_used = current_day
            elif (
                entry is not None and exit_ is not None
                and entry.year == year and entry.month == month
                and exit_.year == year and exit_.month == month
            ):
                days_used = max(0, exit_.day - entry.day + 1)
            elif entry is not None and entry.year == year and entry.month == month:
                days_used = max(0, current_day - entry.day + 1)
            elif exit_ is not None and exit_.year == year and exit_.month == month:
                days_used = max(0, exit_.day)
            else:
                # Activación en mes/año anterior o salida en otro mes: en el mes actual cobrar solo hasta hoy
                if (year, month) == (today.year, today.month):
                    days_used = current_day
                else:
                    days_used = days_in_month

            quant.lot_days_used_in_month = days_used

            if not lot.active_subscription_id or not lot.subscription_service_product_id:
                continue
            try:
                quant.lot_cost_to_date_currency_id = (
                    lot.active_subscription_id.currency_id or quant.env.company.currency_id
                )
                price_monthly = lot.active_subscription_id._get_price_for_product(
                    lot.subscription_service_product_id, 1.0
                ) or 0.0
                quant.lot_cost_renting_month = price_monthly
                if days_in_month > 0:
                    quant.lot_cost_daily = round(price_monthly / days_in_month, 2)
                    if days_used == days_in_month:
                        quant.lot_cost_to_date_current = price_monthly
                    else:
                        quant.lot_cost_to_date_current = round(quant.lot_cost_daily * days_used, 2)
            except Exception:
                pass

    @api.depends('lot_id', 'lot_id.entry_date', 'lot_id.last_entry_date_display', 'lot_id.exit_date', 'lot_id.last_exit_date_display')
    def _compute_lot_days_total_on_site(self):
        """Días totales desde Fecha Activación Renting hasta hoy (o hasta Fecha Finalización si ya salió)."""
        today = fields.Date.today()
        today_py = today if isinstance(today, datetime.date) else datetime.date(today.year, today.month, today.day)
        for quant in self:
            quant.lot_days_total_on_site = 0
            lot = quant.lot_id
            if not lot:
                continue
            entry = self._lot_date_to_python(
                getattr(lot, 'entry_date', None) or getattr(lot, 'last_entry_date_display', None)
            )
            if not entry:
                continue
            exit_ = self._lot_date_to_python(
                getattr(lot, 'exit_date', None) or getattr(lot, 'last_exit_date_display', None)
            )
            end = exit_ if exit_ and exit_ < today_py else today_py
            if end < entry:
                continue
            quant.lot_days_total_on_site = (end - entry).days + 1

    def _lot_date_to_python(self, value):
        """Convierte entry_date/exit_date de Odoo a datetime.date. None si no hay valor."""
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

    @api.depends('lot_id')
    def _compute_license_service_name(self):
        """Calcula el tipo de licencia o servicio asignado a este serial."""
        for quant in self:
            if not quant.lot_id:
                quant.license_service_name = ''
                continue
            
            # Buscar en license.equipment los registros donde este lot_id está asignado
            license_names = []
            if 'license.equipment' in self.env:
                equipment_records = self.env['license.equipment'].search([
                    ('lot_id', '=', quant.lot_id.id),
                    ('state', '=', 'assigned'),
                ])
                
                for equipment in equipment_records:
                    if equipment.license_id:
                        # Obtener el nombre del servicio/producto de la licencia
                        if equipment.license_id.product_id:
                            service_name = equipment.license_id.product_id.display_name or equipment.license_id.product_id.name
                            if service_name and service_name not in license_names:
                                license_names.append(service_name)
                        # Si no hay producto, usar el código de la licencia
                        elif equipment.license_id.code:
                            if equipment.license_id.code not in license_names:
                                license_names.append(equipment.license_id.code)
            
            quant.license_service_name = ', '.join(license_names) if license_names else ''
    
    @api.depends('lot_id', 'lot_id.principal_lot_id')
    def _compute_principal_lot_info(self):
        """Calcula el producto principal asociado desde lot_id.principal_lot_id."""
        for quant in self:
            if quant.lot_id and quant.lot_id.principal_lot_id:
                principal_lot = quant.lot_id.principal_lot_id
                quant.principal_lot_id = principal_lot
                quant.principal_product_id = principal_lot.product_id
                quant.principal_lot_name = principal_lot.name or ''
                quant.principal_lot_inventory_plate = principal_lot.inventory_plate or ''
            else:
                # Si no hay principal_lot_id directo, buscar en supply_line
                if quant.lot_id:
                    supply_line = self.env['stock.lot.supply.line'].search([
                        ('related_lot_id', '=', quant.lot_id.id)
                    ], limit=1)
                    if supply_line and supply_line.lot_id:
                        principal_lot = supply_line.lot_id
                        quant.principal_lot_id = principal_lot
                        quant.principal_product_id = principal_lot.product_id
                        quant.principal_lot_name = principal_lot.name or ''
                        quant.principal_lot_inventory_plate = principal_lot.inventory_plate or ''
                    else:
                        quant.principal_lot_id = False
                        quant.principal_product_id = False
                        quant.principal_lot_name = ''
                        quant.principal_lot_inventory_plate = ''
                else:
                    quant.principal_lot_id = False
                    quant.principal_product_id = False
                    quant.principal_lot_name = ''
                    quant.principal_lot_inventory_plate = ''