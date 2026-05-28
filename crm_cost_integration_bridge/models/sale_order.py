# -*- coding: utf-8 -*-
from odoo import _, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    integration_case_ids = fields.One2many(
        'commercial.integration.case',
        'sale_order_id',
        string='Casos integración',
        readonly=True,
    )
    integration_case_count = fields.Integer(
        compute='_compute_integration_case_count',
        string='Casos integración',
    )
    calculator_projection_case_id = fields.Many2one(
        'commercial.integration.case',
        string='Caso calculadora',
        readonly=True,
        copy=False,
    )
    calculator_projection_currency_id = fields.Many2one(
        'res.currency',
        string='Moneda propuesta cliente',
        readonly=True,
        copy=False,
    )
    calculator_projection_total = fields.Monetary(
        string='Total propuesta cliente',
        currency_field='calculator_projection_currency_id',
        readonly=True,
        copy=False,
    )
    calculator_projection_24 = fields.Monetary(
        string='Escenario 24 meses',
        currency_field='calculator_projection_currency_id',
        readonly=True,
        copy=False,
    )
    calculator_projection_36 = fields.Monetary(
        string='Escenario 36 meses',
        currency_field='calculator_projection_currency_id',
        readonly=True,
        copy=False,
    )
    calculator_projection_48 = fields.Monetary(
        string='Escenario 48 meses',
        currency_field='calculator_projection_currency_id',
        readonly=True,
        copy=False,
    )
    calculator_projection_ready = fields.Boolean(
        string='Proyección calculadora lista',
        readonly=True,
        copy=False,
    )

    def _compute_integration_case_count(self):
        for order in self:
            order.integration_case_count = len(order.integration_case_ids)

    def action_view_integration_cases(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Casos integración'),
            'res_model': 'commercial.integration.case',
            'view_mode': 'list,form',
            'domain': [('sale_order_id', '=', self.id)],
            'context': {
                'default_sale_order_id': self.id,
                'default_partner_id': self.partner_id.id if self.partner_id else False,
                'default_lead_id': self.opportunity_id.id if self.opportunity_id else False,
            },
        }
