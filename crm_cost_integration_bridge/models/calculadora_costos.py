# -*- coding: utf-8 -*-
from odoo import api, fields, models


class CalculadoraCostos(models.Model):
    _inherit = 'calculadora.costos'

    integration_case_id = fields.Many2one(
        'commercial.integration.case',
        string='Caso integración',
        ondelete='set null',
        index=True,
        copy=False,
    )
    source_purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Cotización proveedor origen',
        ondelete='set null',
        readonly=True,
        copy=False,
    )
    bridge_manual_insurance_cop = fields.Float(
        string='Seguro manual base compañía',
        default=0.0,
        help='Valor manual adicional expresado en la moneda base de la compañía.',
    )
    bridge_apply_tax = fields.Boolean(
        string='Aplicar IVA',
        default=False,
        help='Si está activo, se aplica el porcentaje de IVA sobre la base indicada.',
    )
    bridge_tax_percent = fields.Float(
        string='IVA (%)',
        default=19.0,
        help='Porcentaje de IVA sobre la base (ej. 19).',
    )
    bridge_amount_before_tax_cop = fields.Monetary(
        string='Base antes de IVA (moneda base)',
        compute='_compute_bridge_pricing',
        store=True,
        currency_field='company_currency_id',
        help='Costo equipo más servicio del plazo en moneda base de la compañía.',
    )
    bridge_tax_amount_cop = fields.Monetary(
        string='Monto IVA (moneda base)',
        compute='_compute_bridge_pricing',
        store=True,
        currency_field='company_currency_id',
    )
    bridge_precio_final_cliente_cop = fields.Monetary(
        string='Precio final cliente (moneda base)',
        compute='_compute_bridge_pricing',
        store=True,
        currency_field='company_currency_id',
        help='Base + IVA (si aplica) + seguro manual en moneda base.',
    )
    bridge_amount_before_tax = fields.Monetary(
        string='Base antes de IVA',
        compute='_compute_bridge_pricing',
        store=True,
        currency_field='currency_id',
        help='Base antes de IVA expresada en la moneda de la cotización.',
    )
    bridge_tax_amount = fields.Monetary(
        string='Monto IVA',
        compute='_compute_bridge_pricing',
        store=True,
        currency_field='currency_id',
    )
    bridge_precio_final_cliente = fields.Monetary(
        string='Precio final cliente',
        compute='_compute_bridge_pricing',
        store=True,
        currency_field='currency_id',
    )

    @api.depends(
        'costo_total_cop',
        'currency_id',
        'company_currency_id',
        'calculation_type',
        'total_servicio_tecnico_plazo_cop',
        'bridge_apply_tax',
        'bridge_tax_percent',
        'bridge_manual_insurance_cop',
        'rate_date',
    )
    def _compute_bridge_pricing(self):
        for rec in self:
            base = rec.costo_total_cop or 0.0
            if rec.calculation_type == 'subscription':
                base += rec.total_servicio_tecnico_plazo_cop or 0.0
            rec.bridge_amount_before_tax_cop = base
            if rec.bridge_apply_tax and (rec.bridge_tax_percent or 0.0):
                rec.bridge_tax_amount_cop = base * (rec.bridge_tax_percent / 100.0)
            else:
                rec.bridge_tax_amount_cop = 0.0
            rec.bridge_precio_final_cliente_cop = (
                base + rec.bridge_tax_amount_cop + (rec.bridge_manual_insurance_cop or 0.0)
            )
            rec.bridge_amount_before_tax = rec._convert_from_company_currency(rec.bridge_amount_before_tax_cop)
            rec.bridge_tax_amount = rec._convert_from_company_currency(rec.bridge_tax_amount_cop)
            rec.bridge_precio_final_cliente = rec._convert_from_company_currency(rec.bridge_precio_final_cliente_cop)
