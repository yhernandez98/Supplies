# -*- coding: utf-8 -*-
import logging
import re
from urllib.request import Request, urlopen
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class TRM(models.Model):
    _name = 'license.trm'
    _description = 'Tasa Representativa del Mercado (TRM)'
    _order = 'year desc, month desc, cutoff_day desc'
    _rec_name = 'display_name'

    year = fields.Integer(string='Año', required=True, default=lambda self: fields.Date.today().year)
    month = fields.Selection([
        ('1', 'Enero'),
        ('2', 'Febrero'),
        ('3', 'Marzo'),
        ('4', 'Abril'),
        ('5', 'Mayo'),
        ('6', 'Junio'),
        ('7', 'Julio'),
        ('8', 'Agosto'),
        ('9', 'Septiembre'),
        ('10', 'Octubre'),
        ('11', 'Noviembre'),
        ('12', 'Diciembre'),
    ], string='Mes', required=True, default=lambda self: str(fields.Date.today().month))
    cutoff_day = fields.Integer(
        string='Día de corte',
        required=True,
        default=6,
        help='Día del mes al que aplica esta TRM para el corte (ej: 6, 10, 15).'
    )
    rate = fields.Float(
        string='TRM (Tasa USD a COP)',
        required=True,
        digits=(16, 2),
        help='Tasa de cambio de dólares a pesos colombianos para este mes/año'
    )
    display_name = fields.Char(string='Nombre', compute='_compute_display_name', store=True)
    active = fields.Boolean(string='Activo', default=True)
    company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.company)

    _unique_year_month_cutoff = models.Constraint(
        'unique(year, month, cutoff_day, company_id)',
        'Ya existe una TRM para este mes, día de corte y compañía.',
    )

    @api.depends('year', 'month', 'cutoff_day')
    def _compute_display_name(self):
        month_names = {
            '1': 'Enero', '2': 'Febrero', '3': 'Marzo', '4': 'Abril',
            '5': 'Mayo', '6': 'Junio', '7': 'Julio', '8': 'Agosto',
            '9': 'Septiembre', '10': 'Octubre', '11': 'Noviembre', '12': 'Diciembre'
        }
        for rec in self:
            month_name = month_names.get(rec.month, rec.month)
            rec.display_name = f"{month_name} {rec.year} (corte día {rec.cutoff_day}) - TRM: {rec.rate:,.2f}"

    @api.constrains('rate', 'cutoff_day')
    def _check_rate_positive(self):
        for rec in self:
            if rec.rate <= 0:
                raise ValidationError(_('La TRM debe ser mayor a cero.'))
            if rec.cutoff_day < 1 or rec.cutoff_day > 31:
                raise ValidationError(_('El día de corte debe estar entre 1 y 31.'))

    @api.model
    def get_trm_for_date(self, date=None, cutoff_day=None):
        """Obtiene la TRM para una fecha y corte específico.
        - Si llega cutoff_day: busca exacto; si no existe, usa el corte activo más cercano (<=) del mes.
        - Si no llega cutoff_day: usa el corte por defecto día 6.
        Atención: el fallback (último corte <= día pedido) puede devolver otra TRM del mismo mes
        (p. ej. pide corte 30 y solo existe corte 6 en mayo → devuelve la del 6). Para mostrar
        “pendiente” en categorías con corte fijo, usar búsqueda exacta (ver subscription _get_trm_exact_rate_month).
        """
        if not date:
            date = fields.Date.today()
        
        year = date.year
        month = str(date.month)
        target_day = int(cutoff_day or 6)
        
        trm = self.search([
            ('year', '=', year),
            ('month', '=', month),
            ('cutoff_day', '=', target_day),
            ('company_id', '=', self.env.company.id),
            ('active', '=', True)
        ], limit=1)

        if not trm:
            # Fallback: tomar el último corte activo <= target_day en el mes.
            trm = self.search([
                ('year', '=', year),
                ('month', '=', month),
                ('cutoff_day', '<=', target_day),
                ('company_id', '=', self.env.company.id),
                ('active', '=', True)
            ], order='cutoff_day desc', limit=1)
        if not trm:
            # Fallback final: primer corte activo del mes.
            trm = self.search([
                ('year', '=', year),
                ('month', '=', month),
                ('company_id', '=', self.env.company.id),
                ('active', '=', True)
            ], order='cutoff_day asc', limit=1)
        
        if not trm:
            _logger.warning(
                'No hay TRM configurada para %s (corte día %s). Se usará 0 para cálculos hasta configurar TRM.',
                date.strftime('%B %Y'), target_day
            )
            return 0.0
        
        return trm.rate

    @api.model
    def _parse_trm_rate_from_html(self, html_text):
        """Extrae la TRM del texto HTML de dolar-colombia.com."""
        if not html_text:
            return 0.0
        patterns = [
            r'1\s*USD\s*=\s*([0-9\.,]+)\s*COP',
            r'TRM[^0-9]*([0-9\.,]+)\s*COP',
        ]
        for pattern in patterns:
            match = re.search(pattern, html_text, flags=re.IGNORECASE)
            if not match:
                continue
            raw = (match.group(1) or '').strip()
            # Formato esperado: 3,621.86
            normalized = raw.replace(',', '')
            try:
                value = float(normalized)
                if value > 0:
                    return value
            except Exception:
                continue
        return 0.0

    @api.model
    def _fetch_trm_rate_from_web(self, target_date=None):
        """Consulta TRM desde dolar-colombia.com y devuelve tasa."""
        target_date = target_date or fields.Date.today()
        date_str = target_date.strftime('%Y-%m-%d')
        urls = [
            f'https://www.dolar-colombia.com/{date_str}',
            'https://www.dolar-colombia.com/',
        ]
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; Odoo TRM Bot/1.0)',
            'Accept-Language': 'es-CO,es;q=0.9,en;q=0.8',
        }
        for url in urls:
            try:
                req = Request(url, headers=headers)
                with urlopen(req, timeout=20) as resp:
                    html = resp.read().decode('utf-8', errors='ignore')
                rate = self._parse_trm_rate_from_html(html)
                if rate > 0:
                    _logger.info('TRM web obtenida desde %s: %s', url, rate)
                    return rate
            except Exception as exc:
                _logger.warning('Error consultando TRM web (%s): %s', url, exc)
        return 0.0

    @api.model
    def _upsert_trm_for_cutoff(self, date_obj, cutoff_day, rate, overwrite_existing=True):
        """Crea/actualiza TRM para año-mes-corte en la compañía actual."""
        year = int(date_obj.year)
        month = str(int(date_obj.month))
        cutoff = int(cutoff_day or date_obj.day or 6)
        existing = self.search([
            ('year', '=', year),
            ('month', '=', month),
            ('cutoff_day', '=', cutoff),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        vals = {
            'year': year,
            'month': month,
            'cutoff_day': cutoff,
            'rate': rate,
            'active': True,
            'company_id': self.env.company.id,
        }
        if existing:
            if not overwrite_existing:
                return existing
            existing.write(vals)
            return existing
        return self.create(vals)

    @api.model
    def _get_required_cutoff_days(self):
        """Retorna todos los días de corte necesarios según categorías activas."""
        days = {6}
        Category = self.env['license.category']
        if Category:
            categories = Category.search([('active', '=', True)])
            for category in categories:
                try:
                    if hasattr(category, 'get_trm_cutoff_day'):
                        days.add(int(category.get_trm_cutoff_day() or 6))
                    else:
                        days.add(6)
                except Exception:
                    days.add(6)
        # Sanitizar rango
        return sorted(d for d in days if 1 <= int(d) <= 31)

    def action_fetch_trm_from_web_today(self):
        """Acción manual: consulta TRM web del día y la guarda."""
        # Botón de formulario llama con recordset.
        self.ensure_one()
        today = fields.Date.today()
        rate = self._fetch_trm_rate_from_web(today)
        if not rate or rate <= 0:
            raise ValidationError(_('No se pudo obtener la TRM desde la web. Intente nuevamente.'))
        cutoff_days = self._get_required_cutoff_days()
        created_only = []
        skipped_existing = []
        for cutoff_day in cutoff_days:
            existed = self.search([
                ('year', '=', int(today.year)),
                ('month', '=', str(int(today.month))),
                ('cutoff_day', '=', int(cutoff_day)),
                ('company_id', '=', self.env.company.id),
            ], limit=1)
            rec = self._upsert_trm_for_cutoff(today, cutoff_day, rate, overwrite_existing=False)
            if existed:
                skipped_existing.append(rec)
            else:
                created_only.append(rec)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('TRM actualizada'),
                'message': _('TRM %s procesada para %s/%s. Creadas: %s | Conservadas (sin cambio): %s') % (
                    rate,
                    today.month,
                    today.year,
                    len(created_only),
                    len(skipped_existing),
                ),
                'type': 'success',
                'sticky': False,
            },
        }

    @api.model
    def cron_fetch_trm_from_web_daily(self):
        """Cron diario: consulta TRM web y la guarda para todos los cortes configurados."""
        today = fields.Date.today()
        rate = self._fetch_trm_rate_from_web(today)
        if not rate or rate <= 0:
            _logger.warning('Cron TRM web: no fue posible obtener tasa para %s', today)
            return
        cutoff_days = self._get_required_cutoff_days()
        created_count = 0
        preserved_count = 0
        for cutoff_day in cutoff_days:
            existed = self.search([
                ('year', '=', int(today.year)),
                ('month', '=', str(int(today.month))),
                ('cutoff_day', '=', int(cutoff_day)),
                ('company_id', '=', self.env.company.id),
            ], limit=1)
            self._upsert_trm_for_cutoff(today, cutoff_day, rate, overwrite_existing=False)
            if existed:
                preserved_count += 1
            else:
                created_count += 1
        _logger.info(
            'Cron TRM web: TRM=%s para %s/%s. Creadas=%s, conservadas=%s',
            rate, today.month, today.year, created_count, preserved_count
        )

