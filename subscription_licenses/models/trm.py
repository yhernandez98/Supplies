# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class TRM(models.Model):
    _name = 'license.trm'
    _description = 'Tasa Representativa del Mercado (TRM)'
    _order = 'year desc, month desc'
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
    rate = fields.Float(
        string='TRM (Tasa USD a COP)',
        required=True,
        digits=(16, 2),
        help='Tasa de cambio de dólares a pesos colombianos para este mes/año'
    )
    display_name = fields.Char(string='Nombre', compute='_compute_display_name', store=True)
    active = fields.Boolean(string='Activo', default=True)
    company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.company)

    unique_year_month = models.Constraint(
        'unique(year, month, company_id)',
        'Ya existe una TRM para este mes y año en esta compañía.',
    )

    @api.depends('year', 'month')
    def _compute_display_name(self):
        month_names = {
            '1': 'Enero', '2': 'Febrero', '3': 'Marzo', '4': 'Abril',
            '5': 'Mayo', '6': 'Junio', '7': 'Julio', '8': 'Agosto',
            '9': 'Septiembre', '10': 'Octubre', '11': 'Noviembre', '12': 'Diciembre'
        }
        for rec in self:
            month_name = month_names.get(rec.month, rec.month)
            rec.display_name = f"{month_name} {rec.year} - TRM: {rec.rate:,.2f}"

    @api.constrains('rate')
    def _check_rate_positive(self):
        for rec in self:
            if rec.rate <= 0:
                raise ValidationError(_('La TRM debe ser mayor a cero.'))

    @api.model
    def get_trm_for_date(self, date=None):
        """Obtiene la TRM para una fecha específica. Si no se proporciona fecha, usa la actual."""
        if not date:
            date = fields.Date.today()
        
        year = date.year
        month = str(date.month)
        
        trm = self.search([
            ('year', '=', year),
            ('month', '=', month),
            ('company_id', '=', self.env.company.id),
            ('active', '=', True)
        ], limit=1)
        
        if not trm:
            _logger.warning(
                'No hay TRM configurada para %s. Se usará 0 para cálculos hasta que configure la TRM.',
                date.strftime('%B %Y')
            )
            return 0.0
        
        return trm.rate

