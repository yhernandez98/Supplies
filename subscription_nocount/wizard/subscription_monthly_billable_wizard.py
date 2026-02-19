# -*- coding: utf-8 -*-
from datetime import date
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_MONTH_SELECTION = [
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
]


class SubscriptionMonthlyBillableWizard(models.TransientModel):
    _name = 'subscription.monthly.billable.wizard'
    _description = 'Guardar facturable del mes (para facturación mes vencido)'

    subscription_id = fields.Many2one(
        'subscription.subscription',
        string='Suscripción',
        required=True,
        readonly=True,
    )
    reference_year = fields.Selection(
        selection='_get_year_selection',
        string='Año',
        required=True,
    )
    reference_month = fields.Selection(
        _MONTH_SELECTION,
        string='Mes',
        required=True,
    )

    @api.model
    def _get_year_selection(self):
        today = date.today()
        years = []
        for y in range(today.year - 2, today.year + 2):
            years.append((str(y), str(y)))
        return years

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        today = date.today()
        last_month = today - relativedelta(months=1)
        if 'reference_year' not in res or not res.get('reference_year'):
            res['reference_year'] = str(last_month.year)
        if 'reference_month' not in res or not res.get('reference_month'):
            res['reference_month'] = str(last_month.month)
        return res

    def action_confirm(self):
        self.ensure_one()
        if not self.subscription_id:
            raise UserError(_('Falta la suscripción.'))
        year = int(self.reference_year) if self.reference_year else date.today().year
        month = int(self.reference_month) if self.reference_month else date.today().month
        billable = self.subscription_id.do_save_monthly_billable(
            year,
            month,
        )
        return {
            'type': 'ir.actions.act_window',
            'name': _('Facturable guardado'),
            'res_model': 'subscription.monthly.billable',
            'view_mode': 'form',
            'res_id': billable.id,
            'target': 'current',
        }
