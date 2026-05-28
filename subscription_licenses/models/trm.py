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
        - Si no llega cutoff_day: usa el corte por