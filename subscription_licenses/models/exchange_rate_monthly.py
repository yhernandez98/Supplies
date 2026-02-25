# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ExchangeRateMonthly(models.Model):
    """Modelo para almacenar la TRM (Tasa Representativa del Mercado) por mes."""
    _name = 'exchange.rate.monthly'
    _description = 'TRM Mensual'
    _order = 'year desc, month desc'
    _rec_name = 'display_name'

    year = fields.Integer(string='Año', required=True, default=lambda self: fields.Date.today().year, index=True)
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
    ], string='Mes', required=True, default=lambda self: str(fields.Date.today().month), index=True)
    rate = fields.Float(string='TRM (USD a COP)', required=True, digits=(16, 2), help='Tasa de cambio de USD a moneda local')
    company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.company, required=True, index=True)
    active = fields.Boolean(string='Activo', default=True, index=True)
    display_name = fields.Char(string='Nombre', compute='_compute_display_name', store=True, index=True)

    _unique_year_month_company = models.Constraint(
        'unique(year, month, company_id)',
        'Ya existe un TRM para este mes y año en esta compañía.',
    )

    @api.depends('year', 'month', 'rate')
    def _compute_display_name(self):
        for rec in self:
            month_names = {
                '1': 'Enero', '2': 'Febrero', '3': 'Marzo', '4': 'Abril',
                '5': 'Mayo', '6': 'Junio', '7': 'Julio', '8': 'Agosto',
                '9': 'Septiembre', '10': 'Octubre', '11': 'Noviembre', '12': 'Diciembre'
            }
            month_name = month_names.get(rec.month, '')
            rate_str = '{:,.2f}'.format(rec.rate) if rec.rate else '0.00'
            rec.display_name = f"{month_name} {rec.year} - TRM: {rate_str}"

    @api.model
    def get_rate_for_date(self, date=None, company_id=None):
        """Obtiene el TRM para una fecha específica."""
        if not date:
            date = fields.Date.today()
        if not company_id:
            company_id = self.env.company.id
        
        year = date.year
        month = str(date.month)
        
        rate_rec = self.search([
            ('year', '=', year),
            ('month', '=', month),
            ('company_id', '=', company_id),
            ('active', '=', True),
        ], limit=1)
        
        return rate_rec.rate if rate_rec else 0.0

