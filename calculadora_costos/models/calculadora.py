# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from decimal import Decimal, getcontext

getcontext().prec = 10

# Plazos permitidos para financiación y comparativas (meses)
PLAZOS_MESES_SELECTION = [
    ('12', '12 meses'),
    ('24', '24 meses'),
    ('36', '36 meses'),
    ('48', '48 meses'),
    ('60', '60 meses'),
]
PLAZOS_COMPARACION_MESES = (12, 24, 36, 48, 60)
CALCULATION_TYPE_SELECTION = [
    ('sale', 'Venta'),
    ('subscription', 'Suscripción'),
]


class Calculadora(models.Model):
    _name = 'calculadora.costos'
    _description = 'Calculadora de Costos y Renting'
    _order = 'create_date desc'

    name = fields.Char(
        string='Nombre',
        required=True,
        help='Nombre o descripción del cálculo'
    )
    
    # Relación con Cliente
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        domain="[('is_company', '=', True)]",
        help='Cliente asociado a este cálculo'
    )
    
    subscription_count = fields.Integer(
        string='Suscripciones Activas',
        compute='_compute_subscription_count',
        store=False,
        help='Cantidad de suscripciones no contables activas del cliente'
    )

    # Estado del flujo: borrador, enviada por correo, aprobada
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('sent', 'Enviada'),
        ('approved', 'Aprobada'),
    ], string='Estado', default='draft', required=True, copy=False,
       help='Borrador: en edición. Enviada: cotización enviada por correo. Aprobada: cliente aprobó el cálculo.')

    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    calculation_type = fields.Selection(
        CALCULATION_TYPE_SELECTION,
        string='Tipo de cálculo',
        compute='_compute_calculation_type',
        inverse='_inverse_calculation_type',
        store=False,
        required=True,
        help='Fuente de verdad funcional del cálculo: venta o suscripción.',
    )

    # Tipo de operación: venta directa vs. esquema tipo suscripción (servicios, financiación, plazos)
    tipo_operacion = fields.Selection([
        ('venta', 'Venta'),
        ('suscripcion', 'Suscripción'),
    ], string='Tipo de operación', default='venta', required=True,
       help='Venta: costeo del equipo con utilidad. Suscripción: incluye servicios, parámetros financieros y plazos.')

    # Moneda de cotización global (legado; la moneda por equipo está en cada línea)
    moneda_cotizacion = fields.Selection([
        ('usd', 'USD'),
        ('cop', 'COP (Pesos)'),
    ], string='Cotizar en', compute='_compute_moneda_cotizacion', store=False, readonly=False,
       help='Referencia legacy. Los importes por equipo usan el campo «Moneda» en cada línea de equipos.')

    rate_date = fields.Date(
        string='Fecha de tasa',
        default=fields.Date.context_today,
        required=True,
        help='Fecha usada para resolver la tasa de conversión de la cotización.',
    )

    # Tipo: Bien o Servicio (producto consumible vs servicio; sin vínculo a activos fijos:
    # los modelos product.asset.* solo existen con módulos Enterprise / contabilidad avanzada)
    tipo_producto = fields.Selection([
        ('consu', 'Bien'),
        ('service', 'Servicio'),
    ], string='Tipo', default='consu', required=True,
       help='Indica si la cotización corresponde a un bien o a un servicio.')

    # Cantidad de equipos a cotizar (1 o más)
    cantidad_equipos = fields.Integer(
        string='Cantidad de equipos',
        default=1,
        required=True,
        help='Número de equipos a cotizar (1 a 20). Guarde para actualizar la lista de equipos.'
    )
    _cantidad_equipos_range = models.Constraint(
        'CHECK(cantidad_equipos >= 1 AND cantidad_equipos <= 100)',
        'La cantidad de equipos debe estar entre 1 y 100.',
    )
    line_ids = fields.One2many(
        'calculadora.costos.line',
        'calculadora_id',
        string='Equipos',
        copy=True,
        help='Una línea por cada equipo a cotizar'
    )

    # Campos por equipo 1..20 para formulario (sincronizados con line_ids)
    equipo_1_nombre = fields.Char(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Nombre')
    equipo_1_product_id = fields.Many2one('product.product', compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Producto')
    equipo_1_valor_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (USD)', digits=(16, 0))
    equipo_1_garantia_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (USD)', digits=(16, 0))
    equipo_1_valor_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (COP)', digits=(16, 0))
    equipo_1_garantia_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (COP)', digits=(16, 0))
    equipo_1_costo_total_cop = fields.Float(compute='_compute_equipo_campos', string='Costo total (COP)', digits=(16, 0))
    equipo_2_nombre = fields.Char(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Nombre')
    equipo_2_product_id = fields.Many2one('product.product', compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Producto')
    equipo_2_valor_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (USD)', digits=(16, 0))
    equipo_2_garantia_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (USD)', digits=(16, 0))
    equipo_2_valor_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (COP)', digits=(16, 0))
    equipo_2_garantia_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (COP)', digits=(16, 0))
    equipo_2_costo_total_cop = fields.Float(compute='_compute_equipo_campos', string='Costo total (COP)', digits=(16, 0))
    equipo_3_nombre = fields.Char(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Nombre')
    equipo_3_product_id = fields.Many2one('product.product', compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Producto')
    equipo_3_valor_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (USD)', digits=(16, 0))
    equipo_3_garantia_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (USD)', digits=(16, 0))
    equipo_3_valor_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (COP)', digits=(16, 0))
    equipo_3_garantia_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (COP)', digits=(16, 0))
    equipo_3_costo_total_cop = fields.Float(compute='_compute_equipo_campos', string='Costo total (COP)', digits=(16, 0))
    equipo_4_nombre = fields.Char(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Nombre')
    equipo_4_product_id = fields.Many2one('product.product', compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Producto')
    equipo_4_valor_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (USD)', digits=(16, 0))
    equipo_4_garantia_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (USD)', digits=(16, 0))
    equipo_4_valor_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (COP)', digits=(16, 0))
    equipo_4_garantia_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (COP)', digits=(16, 0))
    equipo_4_costo_total_cop = fields.Float(compute='_compute_equipo_campos', string='Costo total (COP)', digits=(16, 0))
    equipo_5_nombre = fields.Char(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Nombre')
    equipo_5_product_id = fields.Many2one('product.product', compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Producto')
    equipo_5_valor_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (USD)', digits=(16, 0))
    equipo_5_garantia_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (USD)', digits=(16, 0))
    equipo_5_valor_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (COP)', digits=(16, 0))
    equipo_5_garantia_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (COP)', digits=(16, 0))
    equipo_5_costo_total_cop = fields.Float(compute='_compute_equipo_campos', string='Costo total (COP)', digits=(16, 0))
    equipo_6_nombre = fields.Char(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Nombre')
    equipo_6_product_id = fields.Many2one('product.product', compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Producto')
    equipo_6_valor_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (USD)', digits=(16, 0))
    equipo_6_garantia_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (USD)', digits=(16, 0))
    equipo_6_valor_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (COP)', digits=(16, 0))
    equipo_6_garantia_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (COP)', digits=(16, 0))
    equipo_6_costo_total_cop = fields.Float(compute='_compute_equipo_campos', string='Costo total (COP)', digits=(16, 0))
    equipo_7_nombre = fields.Char(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Nombre')
    equipo_7_product_id = fields.Many2one('product.product', compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Producto')
    equipo_7_valor_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (USD)', digits=(16, 0))
    equipo_7_garantia_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (USD)', digits=(16, 0))
    equipo_7_valor_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (COP)', digits=(16, 0))
    equipo_7_garantia_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (COP)', digits=(16, 0))
    equipo_7_costo_total_cop = fields.Float(compute='_compute_equipo_campos', string='Costo total (COP)', digits=(16, 0))
    equipo_8_nombre = fields.Char(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Nombre')
    equipo_8_product_id = fields.Many2one('product.product', compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Producto')
    equipo_8_valor_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (USD)', digits=(16, 0))
    equipo_8_garantia_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (USD)', digits=(16, 0))
    equipo_8_valor_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (COP)', digits=(16, 0))
    equipo_8_garantia_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (COP)', digits=(16, 0))
    equipo_8_costo_total_cop = fields.Float(compute='_compute_equipo_campos', string='Costo total (COP)', digits=(16, 0))
    equipo_9_nombre = fields.Char(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Nombre')
    equipo_9_product_id = fields.Many2one('product.product', compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Producto')
    equipo_9_valor_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (USD)', digits=(16, 0))
    equipo_9_garantia_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (USD)', digits=(16, 0))
    equipo_9_valor_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (COP)', digits=(16, 0))
    equipo_9_garantia_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (COP)', digits=(16, 0))
    equipo_9_costo_total_cop = fields.Float(compute='_compute_equipo_campos', string='Costo total (COP)', digits=(16, 0))
    equipo_10_nombre = fields.Char(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Nombre')
    equipo_10_product_id = fields.Many2one('product.product', compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Producto')
    equipo_10_valor_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (USD)', digits=(16, 0))
    equipo_10_garantia_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (USD)', digits=(16, 0))
    equipo_10_valor_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (COP)', digits=(16, 0))
    equipo_10_garantia_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (COP)', digits=(16, 0))
    equipo_10_costo_total_cop = fields.Float(compute='_compute_equipo_campos', string='Costo total (COP)', digits=(16, 0))
    equipo_11_nombre = fields.Char(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Nombre')
    equipo_11_product_id = fields.Many2one('product.product', compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Producto')
    equipo_11_valor_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (USD)', digits=(16, 0))
    equipo_11_garantia_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (USD)', digits=(16, 0))
    equipo_11_valor_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (COP)', digits=(16, 0))
    equipo_11_garantia_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (COP)', digits=(16, 0))
    equipo_11_costo_total_cop = fields.Float(compute='_compute_equipo_campos', string='Costo total (COP)', digits=(16, 0))
    equipo_12_nombre = fields.Char(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Nombre')
    equipo_12_product_id = fields.Many2one('product.product', compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Producto')
    equipo_12_valor_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (USD)', digits=(16, 0))
    equipo_12_garantia_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (USD)', digits=(16, 0))
    equipo_12_valor_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (COP)', digits=(16, 0))
    equipo_12_garantia_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (COP)', digits=(16, 0))
    equipo_12_costo_total_cop = fields.Float(compute='_compute_equipo_campos', string='Costo total (COP)', digits=(16, 0))
    equipo_13_nombre = fields.Char(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Nombre')
    equipo_13_product_id = fields.Many2one('product.product', compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Producto')
    equipo_13_valor_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (USD)', digits=(16, 0))
    equipo_13_garantia_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (USD)', digits=(16, 0))
    equipo_13_valor_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (COP)', digits=(16, 0))
    equipo_13_garantia_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (COP)', digits=(16, 0))
    equipo_13_costo_total_cop = fields.Float(compute='_compute_equipo_campos', string='Costo total (COP)', digits=(16, 0))
    equipo_14_nombre = fields.Char(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Nombre')
    equipo_14_product_id = fields.Many2one('product.product', compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Producto')
    equipo_14_valor_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (USD)', digits=(16, 0))
    equipo_14_garantia_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (USD)', digits=(16, 0))
    equipo_14_valor_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (COP)', digits=(16, 0))
    equipo_14_garantia_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (COP)', digits=(16, 0))
    equipo_14_costo_total_cop = fields.Float(compute='_compute_equipo_campos', string='Costo total (COP)', digits=(16, 0))
    equipo_15_nombre = fields.Char(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Nombre')
    equipo_15_product_id = fields.Many2one('product.product', compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Producto')
    equipo_15_valor_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (USD)', digits=(16, 0))
    equipo_15_garantia_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (USD)', digits=(16, 0))
    equipo_15_valor_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (COP)', digits=(16, 0))
    equipo_15_garantia_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (COP)', digits=(16, 0))
    equipo_15_costo_total_cop = fields.Float(compute='_compute_equipo_campos', string='Costo total (COP)', digits=(16, 0))
    equipo_16_nombre = fields.Char(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Nombre')
    equipo_16_product_id = fields.Many2one('product.product', compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Producto')
    equipo_16_valor_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (USD)', digits=(16, 0))
    equipo_16_garantia_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (USD)', digits=(16, 0))
    equipo_16_valor_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (COP)', digits=(16, 0))
    equipo_16_garantia_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (COP)', digits=(16, 0))
    equipo_16_costo_total_cop = fields.Float(compute='_compute_equipo_campos', string='Costo total (COP)', digits=(16, 0))
    equipo_17_nombre = fields.Char(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Nombre')
    equipo_17_product_id = fields.Many2one('product.product', compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Producto')
    equipo_17_valor_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (USD)', digits=(16, 0))
    equipo_17_garantia_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (USD)', digits=(16, 0))
    equipo_17_valor_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (COP)', digits=(16, 0))
    equipo_17_garantia_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (COP)', digits=(16, 0))
    equipo_17_costo_total_cop = fields.Float(compute='_compute_equipo_campos', string='Costo total (COP)', digits=(16, 0))
    equipo_18_nombre = fields.Char(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Nombre')
    equipo_18_product_id = fields.Many2one('product.product', compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Producto')
    equipo_18_valor_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (USD)', digits=(16, 0))
    equipo_18_garantia_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (USD)', digits=(16, 0))
    equipo_18_valor_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (COP)', digits=(16, 0))
    equipo_18_garantia_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (COP)', digits=(16, 0))
    equipo_18_costo_total_cop = fields.Float(compute='_compute_equipo_campos', string='Costo total (COP)', digits=(16, 0))
    equipo_19_nombre = fields.Char(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Nombre')
    equipo_19_product_id = fields.Many2one('product.product', compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Producto')
    equipo_19_valor_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (USD)', digits=(16, 0))
    equipo_19_garantia_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (USD)', digits=(16, 0))
    equipo_19_valor_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (COP)', digits=(16, 0))
    equipo_19_garantia_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (COP)', digits=(16, 0))
    equipo_19_costo_total_cop = fields.Float(compute='_compute_equipo_campos', string='Costo total (COP)', digits=(16, 0))
    equipo_20_nombre = fields.Char(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Nombre')
    equipo_20_product_id = fields.Many2one('product.product', compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Producto')
    equipo_20_valor_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (USD)', digits=(16, 0))
    equipo_20_garantia_usd = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (USD)', digits=(16, 0))
    equipo_20_valor_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Valor (COP)', digits=(16, 0))
    equipo_20_garantia_cop = fields.Float(compute='_compute_equipo_campos', inverse='_inverse_equipo_campos', string='Garantía (COP)', digits=(16, 0))
    equipo_20_costo_total_cop = fields.Float(compute='_compute_equipo_campos', string='Costo total (COP)', digits=(16, 0))

    # Agregados desde line_ids (equivalentes USD para utilidad y reportes; no editables)
    valor_usd = fields.Float(
        string='Valor equipo (equiv. USD)',
        compute='_compute_agregados_desde_lineas',
        store=True,
        help='Suma de valores de equipo en equivalente USD según moneda de cada línea y TRM.'
    )
    
    valor_garantia_usd = fields.Float(
        string='Valor garantía (equiv. USD)',
        compute='_compute_agregados_desde_lineas',
        store=True,
        help='Suma de garantías en equivalente USD según moneda de cada línea y TRM.'
    )
    
    porcentaje_utilidad = fields.Float(
        string='Porcentaje de Utilidad (%)',
        default=10.0,
        required=True,
        help='Porcentaje de utilidad aplicado sobre el costo (ej: 10 = 10%, 20 = 20%)'
    )
    
    trm = fields.Float(
        string='TRM (COP/USD)',
        compute='_compute_trm',
        store=False,
        readonly=True,
        help='Tasa representativa aplicada desde las tasas de moneda de Odoo.'
    )

    applied_currency_rate = fields.Float(
        string='Tasa aplicada',
        compute='_compute_applied_currency_rate',
        store=True,
        readonly=True,
        help='Snapshot de la tasa usada para convertir la moneda de cotización a la moneda base de la compañía.',
    )
    
    costo_total_usd = fields.Float(
        string='Costo Total USD (base)',
        compute='_compute_agregados_desde_lineas',
        store=True,
        help='Equiv. USD del costo base (equipo + garantía) antes de utilidad, sumando líneas.'
    )
    
    costo_con_utilidad_usd = fields.Float(
        string='Costo con Utilidad (USD)',
        compute='_compute_costo_con_utilidad',
        store=True,
        help='Costo aplicando porcentaje de utilidad'
    )
    
    costo_total_cop = fields.Float(
        string='Costo Total Equipo (COP)',
        compute='_compute_costo_total_cop',
        store=True,
        help='Costo del equipo en pesos (USD + garantía, utilidad y TRM). No incluye servicio técnico.'
    )
    
    # Servicio técnico (independiente del costo total del equipo)
    costo_servicio_tecnico_mensual_cop = fields.Float(
        string='Costo Servicio Técnico Mensual COP',
        default=0.0,
        help='Costo base mensual del servicio técnico en COP, antes del margen.'
    )
    
    porcentaje_margen_servicio = fields.Float(
        string='Margen Servicio Técnico (%)',
        default=15.0,
        help='Margen sobre el costo mensual del servicio técnico (ej: 15 = 15%).'
    )
    
    servicio_con_margen = fields.Float(
        string='Servicio Técnico Mensual con Margen (COP)',
        compute='_compute_servicio_con_margen',
        store=True,
        help='Valor mensual del servicio técnico con margen aplicado (COP).'
    )
    
    total_servicio_tecnico_plazo_cop = fields.Float(
        string='Total Servicio Técnico en el Plazo (COP)',
        compute='_compute_total_servicio_tecnico_plazo_cop',
        store=True,
        help='Servicio técnico mensual con margen multiplicado por el plazo en meses.'
    )
    
    # Parámetros Financieros
    financiacion_con_interes = fields.Boolean(
        string='Financiación con interés (PMT)',
        default=False,
        help='Desactivado: la cuota del equipo reparte solo el costo del equipo en el plazo, sin interés; '
             'el pago mensual suma esa cuota más el servicio técnico mensual. '
             'Activado: PMT sobre el costo del equipo; el total a pagar en el plazo incluye intereses '
             'del capital del equipo además del servicio técnico.',
    )

    tasa_nominal = fields.Float(
        string='Tasa Nominal (%)',
        default=21.0,
        required=True,
        help='Tasa de interés nominal anual en porcentaje (solo aplica si «Financiación con interés» está activa)'
    )
    
    tasa_mensual = fields.Float(
        string='Tasa Mensual (%)',
        compute='_compute_tasa_mensual',
        store=True,
        help='Tasa de interés mensual calculada'
    )
    
    tasa_efectiva_anual = fields.Float(
        string='Tasa Efectiva Anual (%)',
        compute='_compute_tasa_efectiva_anual',
        store=True,
        help='Tasa efectiva anual calculada'
    )
    
    plazo_meses = fields.Selection(
        PLAZOS_MESES_SELECTION,
        string='Plazo (meses)',
        default='24',
        required=True,
        help='Plazo del financiamiento: 12, 24, 36, 48 o 60 meses (por defecto 24).'
    )
    
    # Pago Mensual
    pago_mensual = fields.Float(
        string='Pago Mensual (COP)',
        compute='_compute_pago_mensual',
        store=True,
        help='Pago mensual calculado incluyendo servicios'
    )
    
    # Campo auxiliar para mostrar el costo del equipo sin servicios
    costo_equipo_cop = fields.Float(
        string='Costo Equipo (COP)',
        compute='_compute_costo_equipo_cop',
        store=True,
        help='Costo del equipo sin incluir servicios'
    )
    
    # Valores para diferentes plazos (solo aplica en modo suscripción en UI)
    valor_12_meses = fields.Float(
        string='Valor 12 Meses',
        compute='_compute_valores_plazos',
        store=True,
        help='Pago mensual calculado para 12 meses'
    )
    
    valor_24_meses = fields.Float(
        string='Valor 24 Meses',
        compute='_compute_valores_plazos',
        store=True,
        help='Pago mensual calculado para 24 meses'
    )
    
    valor_36_meses = fields.Float(
        string='Valor 36 Meses',
        compute='_compute_valores_plazos',
        store=True,
        help='Pago mensual calculado para 36 meses'
    )
    
    valor_48_meses = fields.Float(
        string='Valor 48 Meses',
        compute='_compute_valores_plazos',
        store=True,
        help='Pago mensual calculado para 48 meses'
    )
    
    valor_60_meses = fields.Float(
        string='Valor 60 Meses',
        compute='_compute_valores_plazos',
        store=True,
        help='Pago mensual calculado para 60 meses'
    )
    
    # Total a Pagar
    total_pagar = fields.Float(
        string='Total Estimado a Pagar (Plazo)',
        compute='_compute_total_pagar',
        store=True,
        help='Suma estimada en el plazo: costo del equipo + total servicio técnico del plazo (sin interés), '
             'o suma de cuotas si hay financiación con interés. Distinto del «Costo Total Equipo».'
    )

    quote_equipment_total = fields.Monetary(
        string='Total equipo cotización',
        currency_field='currency_id',
        compute='_compute_quote_amounts',
        store=True,
        help='Costo total del equipo expresado en la moneda de la cotización.',
    )

    quote_monthly_amount = fields.Monetary(
        string='Cuota cotización',
        currency_field='currency_id',
        compute='_compute_quote_amounts',
        store=True,
        help='Cuota mensual expresada en la moneda de la cotización.',
    )

    quote_contract_total = fields.Monetary(
        string='Total contrato cotización',
        currency_field='currency_id',
        compute='_compute_quote_amounts',
        store=True,
        help='Total estimado del contrato expresado en la moneda de la cotización.',
    )
    
    # Información adicional
    active = fields.Boolean(
        string='Activo',
        default=True
    )
    
    notas = fields.Text(
        string='Notas',
        help='Notas adicionales sobre el cálculo'
    )
    
    # Campos para moneda
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        default=lambda self: self.env.ref('base.COP', raise_if_not_found=False),
        required=True
    )

    company_currency_id = fields.Many2one(
        'res.currency',
        string='Moneda base compañía',
        compute='_compute_company_currency_id',
        store=False,
    )
    
    currency_usd_id = fields.Many2one(
        'res.currency',
        string='Moneda USD',
        default=lambda self: self.env.ref('base.USD', raise_if_not_found=False),
        required=True
    )

    is_quote_currency_usd = fields.Boolean(
        compute='_compute_currency_flags',
        store=False,
    )
    is_quote_currency_cop = fields.Boolean(
        compute='_compute_currency_flags',
        store=False,
    )

    @api.depends('tipo_operacion')
    def _compute_calculation_type(self):
        for record in self:
            record.calculation_type = 'subscription' if record.tipo_operacion == 'suscripcion' else 'sale'

    def _inverse_calculation_type(self):
        for record in self:
            record.tipo_operacion = 'suscripcion' if record.calculation_type == 'subscription' else 'venta'

    @api.depends('currency_id')
    def _compute_moneda_cotizacion(self):
        usd = self.env.ref('base.USD', raise_if_not_found=False)
        for record in self:
            record.moneda_cotizacion = 'usd' if usd and record.currency_id == usd else 'cop'

    @api.depends('company_id')
    def _compute_company_currency_id(self):
        for record in self:
            record.company_currency_id = record.company_id.currency_id or self.env.company.currency_id

    @api.depends('currency_id')
    def _compute_currency_flags(self):
        usd = self.env.ref('base.USD', raise_if_not_found=False)
        cop = self.env.ref('base.COP', raise_if_not_found=False)
        for record in self:
            record.is_quote_currency_usd = bool(usd and record.currency_id == usd)
            record.is_quote_currency_cop = bool(cop and record.currency_id == cop)

    def _get_company_currency(self):
        self.ensure_one()
        return self.company_id.currency_id or self.env.company.currency_id

    def _get_quote_currency(self):
        self.ensure_one()
        return self.currency_id or self._get_company_currency()

    def _get_rate_date(self):
        self.ensure_one()
        return self.rate_date or fields.Date.context_today(self)

    def _get_applied_rate(self, source_currency=None, target_currency=None, date=None):
        self.ensure_one()
        source_currency = source_currency or self._get_quote_currency()
        target_currency = target_currency or self._get_company_currency()
        if not source_currency or not target_currency:
            return 0.0
        if source_currency == target_currency:
            return 1.0
        try:
            return source_currency._convert(
                1.0,
                target_currency,
                self.company_id or self.env.company,
                date or self._get_rate_date(),
                round=False,
            )
        except Exception:
            return 0.0

    def _convert_currency_amount(self, amount, source_currency, target_currency, date=None):
        self.ensure_one()
        if not amount:
            return 0.0
        if not source_currency or not target_currency:
            return 0.0
        if source_currency == target_currency:
            return amount
        return source_currency._convert(
            amount,
            target_currency,
            self.company_id or self.env.company,
            date or self._get_rate_date(),
            round=False,
        )

    def _convert_to_company_currency(self, amount, source_currency):
        self.ensure_one()
        return self._convert_currency_amount(amount, source_currency, self._get_company_currency())

    def _convert_from_company_currency(self, amount, target_currency=None):
        self.ensure_one()
        return self._convert_currency_amount(amount, self._get_company_currency(), target_currency or self._get_quote_currency())

    @api.depends('currency_id', 'rate_date', 'company_id')
    def _compute_applied_currency_rate(self):
        for record in self:
            record.applied_currency_rate = record._get_applied_rate()

    @api.depends('applied_currency_rate', 'currency_id')
    def _compute_trm(self):
        usd = self.env.ref('base.USD', raise_if_not_found=False)
        for record in self:
            record.trm = record.applied_currency_rate if usd and record.currency_id == usd else 0.0

    def _plazo_meses_int(self):
        """Convierte plazo_meses (Selection) a entero para cálculos."""
        self.ensure_one()
        try:
            return int(self.plazo_meses or 0)
        except (TypeError, ValueError):
            return 0

    def _pago_mensual_solo_equipo(self, costo_equipo_cop, plazo_meses):
        """
        Cuota mensual correspondiente solo al capital del equipo (sin servicios recurrentes).

        - Sin financiación con interés (o tasa 0 %): costo_equipo_cop / plazo (capital repartido).
        - Con financiación con interés: fórmula PMT sobre el capital indicado.

        Ejemplo sin interés (validación de negocio): 600 USD × 1,15 × 4.000 COP = 2.760.000 COP;
        plazo 12 meses → cuota 230.000 COP/mes; 12 × 230.000 = 2.760.000 COP.
        """
        if plazo_meses <= 0 or costo_equipo_cop <= 0:
            return 0.0
        usar_pmt = self.financiacion_con_interes and (self.tasa_nominal or 0.0) > 0.0
        if not usar_pmt:
            return costo_equipo_cop / float(plazo_meses)
        tasa_mensual_decimal = (self.tasa_nominal / 100.0) / 12.0
        if tasa_mensual_decimal <= 0:
            return costo_equipo_cop / float(plazo_meses)
        factor = (1 + tasa_mensual_decimal) ** plazo_meses
        return (costo_equipo_cop * tasa_mensual_decimal * factor) / (factor - 1)

    def _line_source_currency(self, line):
        self.ensure_one()
        usd = self.env.ref("base.USD", raise_if_not_found=False)
        cop = self.env.ref("base.COP", raise_if_not_found=False)
        return usd if line.moneda_equipo == "USD" else cop

    # Métodos de cálculo
    def _equivalentes_usd_desde_lineas(self):
        """Suma equivalentes USD por línea: USD directo; COP dividido entre TRM. Sin aplicar utilidad."""
        self.ensure_one()
        usd = self.env.ref("base.USD", raise_if_not_found=False)
        if not usd:
            return 0.0, 0.0
        vu, vg = 0.0, 0.0
        for line in self.line_ids:
            amt = line.amount_equipment()
            source_currency = self._line_source_currency(line)
            if not source_currency:
                continue
            vu += self._convert_currency_amount(amt, source_currency, usd)
            vg += self._convert_currency_amount(line.monto_garantia or 0.0, source_currency, usd)
        return vu, vg

    @api.depends(
        "line_ids",
        "line_ids.product_qty",
        "line_ids.price_unit",
        "line_ids.monto_garantia",
        "line_ids.moneda_equipo",
        "applied_currency_rate",
        "rate_date",
    )
    def _compute_agregados_desde_lineas(self):
        """valor_usd / valor_garantia_usd / costo_total_usd desde líneas (una conversión TRM por línea COP)."""
        for record in self:
            vu, vg = record._equivalentes_usd_desde_lineas()
            record.valor_usd = vu
            record.valor_garantia_usd = vg
            record.costo_total_usd = vu + vg
    
    @api.depends('costo_total_usd', 'porcentaje_utilidad')
    def _compute_costo_con_utilidad(self):
        """Calcula el costo aplicando porcentaje de utilidad"""
        for record in self:
            factor_utilidad = 1 + (record.porcentaje_utilidad / 100.0)
            record.costo_con_utilidad_usd = record.costo_total_usd * factor_utilidad
    
    @api.depends('costo_con_utilidad_usd', 'applied_currency_rate', 'company_id')
    def _compute_costo_equipo_cop(self):
        """Calcula el costo del equipo en pesos colombianos (sin servicios)"""
        usd = self.env.ref("base.USD", raise_if_not_found=False)
        for record in self:
            record.costo_equipo_cop = record._convert_to_company_currency(record.costo_con_utilidad_usd, usd) if usd else 0.0
    
    @api.depends('costo_equipo_cop')
    def _compute_costo_total_cop(self):
        """Costo total del equipo en COP (solo apartado Costos del equipo). El servicio técnico no suma aquí."""
        for record in self:
            record.costo_total_cop = record.costo_equipo_cop
    
    @api.depends('costo_servicio_tecnico_mensual_cop', 'porcentaje_margen_servicio')
    def _compute_servicio_con_margen(self):
        """Servicio técnico mensual con margen (independiente del costo total equipo)."""
        for record in self:
            margen = 1 + (record.porcentaje_margen_servicio / 100.0)
            record.servicio_con_margen = record.costo_servicio_tecnico_mensual_cop * margen
    
    @api.depends('servicio_con_margen', 'plazo_meses', 'calculation_type')
    def _compute_total_servicio_tecnico_plazo_cop(self):
        for record in self:
            pm = record._plazo_meses_int()
            record.total_servicio_tecnico_plazo_cop = (
                record.servicio_con_margen * pm if pm > 0 and record.calculation_type == 'subscription' else 0.0
            )
    
    @api.depends('tasa_nominal')
    def _compute_tasa_mensual(self):
        """Calcula la tasa mensual"""
        for record in self:
            record.tasa_mensual = record.tasa_nominal / 12.0
    
    @api.depends('tasa_nominal', 'plazo_meses')
    def _compute_tasa_efectiva_anual(self):
        """Calcula la tasa efectiva anual usando la fórmula EFFECT de Excel
        
        Fórmula: EFFECT(nominal_rate, npery) = (1 + nominal_rate/npery)^npery - 1
        Donde:
        - nominal_rate: tasa nominal anual (en decimal, ej: 0.21 para 21%)
        - npery: número de períodos de capitalización por año (12 para mensual)
        
        Nota: Excel puede mostrar ligeras diferencias debido a:
        - Precisión numérica interna de Excel
        - Redondeo intermedio en cálculos
        - Configuración de precisión de la celda
        """
        for record in self:
            if record._plazo_meses_int() > 0:
                # Calcular con mayor precisión usando Decimal
                tasa_nominal_decimal = Decimal(str(record.tasa_nominal)) / Decimal('100')
                tasa_mensual_decimal = tasa_nominal_decimal / Decimal('12')
                uno_mas_tasa = Decimal('1') + tasa_mensual_decimal
                factor = uno_mas_tasa ** 12
                tasa_efectiva_decimal = factor - Decimal('1')
                record.tasa_efectiva_anual = float(tasa_efectiva_decimal * Decimal('100'))
            else:
                record.tasa_efectiva_anual = 0.0
    
    @api.depends(
        'costo_equipo_cop',
        'tasa_nominal',
        'plazo_meses',
        'servicio_con_margen',
        'financiacion_con_interes',
    )
    def _compute_pago_mensual(self):
        """
        Pago mensual = cuota del equipo (capital/plazo o PMT) + servicio técnico mensual.
        Si no hay financiación con interés, la suma de cuotas del equipo reparte exactamente costo_equipo_cop.
        """
        for record in self:
            pm = record._plazo_meses_int()
            if record.calculation_type != 'subscription':
                record.pago_mensual = 0.0
            elif pm > 0:
                pago_base = record._pago_mensual_solo_equipo(record.costo_equipo_cop, pm)
                record.pago_mensual = pago_base + record.servicio_con_margen
            else:
                record.pago_mensual = 0.0
    
    @api.depends(
        'costo_equipo_cop',
        'tasa_nominal',
        'servicio_con_margen',
        'financiacion_con_interes',
    )
    def _compute_valores_plazos(self):
        """Calcula valores para comparación de plazos (12 a 60 meses)."""
        for record in self:
            if record.calculation_type != 'subscription':
                record.valor_12_meses = 0.0
                record.valor_24_meses = 0.0
                record.valor_36_meses = 0.0
                record.valor_48_meses = 0.0
                record.valor_60_meses = 0.0
                continue
            record.valor_12_meses = self._calcular_pago_plazo(record, 12)
            record.valor_24_meses = self._calcular_pago_plazo(record, 24)
            record.valor_36_meses = self._calcular_pago_plazo(record, 36)
            record.valor_48_meses = self._calcular_pago_plazo(record, 48)
            record.valor_60_meses = self._calcular_pago_plazo(record, 60)
    
    def _calcular_pago_plazo(self, record, plazo):
        """
        Pago mensual total para un plazo de comparación (mismo criterio que el formulario).
        """
        if plazo > 0:
            pago_base = record._pago_mensual_solo_equipo(record.costo_equipo_cop, plazo)
            return pago_base + record.servicio_con_margen
        return 0.0
    
    @api.depends(
        'pago_mensual',
        'plazo_meses',
        'costo_equipo_cop',
        'servicio_con_margen',
        'financiacion_con_interes',
        'tasa_nominal',
    )
    def _compute_total_pagar(self):
        """Estimado a pagar en el plazo: costo equipo + total servicio técnico del plazo (sin interés);
        con PMT, suma de cuotas mensuales (incluye intereses sobre el equipo)."""
        for record in self:
            if record.calculation_type != 'subscription':
                record.total_pagar = record._compute_sale_totals()
            else:
                record.total_pagar = record._compute_subscription_totals()

    @api.depends('costo_equipo_cop', 'pago_mensual', 'total_pagar', 'currency_id', 'company_id', 'rate_date')
    def _compute_quote_amounts(self):
        for record in self:
            quote_currency = record._get_quote_currency()
            record.quote_equipment_total = record._convert_from_company_currency(record.costo_equipo_cop, quote_currency)
            record.quote_monthly_amount = record._convert_from_company_currency(record.pago_mensual, quote_currency)
            record.quote_contract_total = record._convert_from_company_currency(record.total_pagar, quote_currency)

    def _compute_sale_totals(self):
        self.ensure_one()
        return self.costo_equipo_cop

    def _compute_subscription_totals(self):
        self.ensure_one()
        pm = self._plazo_meses_int()
        if pm <= 0:
            return 0.0
        if not self.financiacion_con_interes or not (self.tasa_nominal or 0.0):
            return self.costo_equipo_cop + self.servicio_con_margen * pm
        return self.pago_mensual * pm
    
    @api.depends('partner_id')
    def _compute_subscription_count(self):
        """Calcula el número de suscripciones activas del cliente"""
        for record in self:
            if record.partner_id:
                try:
                    if 'subscription.subscription' in self.env:
                        count = self.env['subscription.subscription'].search_count([
                            ('partner_id', '=', record.partner_id.id),
                            ('state', '=', 'active')
                        ])
                        record.subscription_count = count
                    else:
                        record.subscription_count = 0
                except Exception:
                    record.subscription_count = 0
            else:
                record.subscription_count = 0
    
    def action_view_subscriptions(self):
        """Abre la vista de suscripciones activas del cliente"""
        self.ensure_one()
        if not self.partner_id:
            raise UserError('Debe seleccionar un cliente para ver las suscripciones.')
        
        try:
            if 'subscription.subscription' not in self.env:
                raise UserError('El módulo de suscripciones no contables no está instalado.')
        except Exception:
            raise UserError('El módulo de suscripciones no contables no está instalado.')
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Suscripciones No Contables Activas',
            'res_model': 'subscription.subscription',
            'view_mode': 'list,form',
            'domain': [
                ('partner_id', '=', self.partner_id.id),
                ('state', '=', 'active')
            ],
            'context': {
                'default_partner_id': self.partner_id.id,
                'search_default_partner_id': self.partner_id.id,
            },
        }

    @api.model_create_multi
    def create(self, vals_list):
        """Valores por defecto locales por cotización (sin parámetros globales)."""
        for vals in vals_list:
            if vals.get('calculation_type') and 'tipo_operacion' not in vals:
                vals['tipo_operacion'] = 'suscripcion' if vals['calculation_type'] == 'subscription' else 'venta'
            if 'tipo_operacion' not in vals:
                vals['tipo_operacion'] = 'venta'
            tipo = vals.get('tipo_operacion')
            if 'company_id' not in vals:
                vals['company_id'] = self.env.company.id
            if 'rate_date' not in vals:
                vals['rate_date'] = fields.Date.context_today(self)
            if 'porcentaje_utilidad' not in vals:
                vals['porcentaje_utilidad'] = 10.0
            if 'tasa_nominal' not in vals:
                vals['tasa_nominal'] = 21.0
            if 'porcentaje_margen_servicio' not in vals:
                vals['porcentaje_margen_servicio'] = 25.0 if tipo == 'suscripcion' else 15.0
            if 'plazo_meses' not in vals:
                vals['plazo_meses'] = '24'
            if vals.get('tipo_operacion') == 'venta':
                vals['financiacion_con_interes'] = False
        records = super(Calculadora, self).create(vals_list)
        Line = self.env["calculadora.costos.line"]
        for rec in records:
            if not rec.line_ids:
                Line.create(
                    {
                        "calculadora_id": rec.id,
                        "sequence": 10,
                        "name": rec.name or "Equipo",
                        "moneda_equipo": "USD",
                        "product_qty": 1.0,
                        "price_unit": 0.0,
                        "monto_garantia": 0.0,
                    }
                )
        return records

    def write(self, vals):
        if vals.get('calculation_type') and 'tipo_operacion' not in vals:
            vals = dict(vals)
            vals['tipo_operacion'] = 'suscripcion' if vals['calculation_type'] == 'subscription' else 'venta'
        if vals.get('tipo_operacion') == 'venta':
            vals = dict(vals)
            vals['financiacion_con_interes'] = False
        return super().write(vals)

    @api.onchange('currency_id', 'rate_date')
    def _onchange_quote_currency(self):
        if self.line_ids and self._origin:
            return {
                'warning': {
                    'title': 'Cambio de moneda de cotización',
                    'message': (
                        'La moneda de cotización o la fecha de tasa cambiaron. '
                        'Se recalcularán equivalencias y totales usando las tasas de Odoo.'
                    ),
                }
            }

    @api.onchange('tipo_operacion')
    def _onchange_tipo_operacion_financiacion(self):
        if self.tipo_operacion == 'venta':
            self.financiacion_con_interes = False
        if self.line_ids and self._origin:
            return {
                'warning': {
                    'title': 'Cambio de tipo de cálculo',
                    'message': (
                        'El flujo de cálculo cambió entre venta y suscripción. '
                        'Revise cuotas, plazos y servicios técnicos antes de continuar.'
                    ),
                }
            }

    @api.constrains('currency_id', 'company_id')
    def _check_quote_currency(self):
        usd = self.env.ref('base.USD', raise_if_not_found=False)
        cop = self.env.ref('base.COP', raise_if_not_found=False)
        allowed_ids = {c.id for c in (usd, cop) if c}
        for record in self:
            if not record.currency_id:
                raise ValidationError('La calculadora debe tener una moneda de cotización definida.')
            if allowed_ids and record.currency_id.id not in allowed_ids:
                raise ValidationError('La calculadora solo admite cotización en COP o USD.')

    @api.constrains('currency_id', 'applied_currency_rate', 'company_id')
    def _check_quote_rate(self):
        for record in self:
            if record.currency_id and record.currency_id != record._get_company_currency() and not record.applied_currency_rate:
                raise ValidationError(
                    'No existe una tasa configurada en Odoo para la moneda de cotización en la fecha seleccionada.'
                )

    @api.constrains('calculation_type', 'plazo_meses')
    def _check_subscription_requirements(self):
        for record in self:
            if record.calculation_type == 'subscription' and record._plazo_meses_int() <= 0:
                raise ValidationError('Las suscripciones requieren un plazo válido.')

    def _calcular_escenario(self, incluir_seguro=True, incluir_servicios=True, plazo=None):
        """
        Calcula los valores para un escenario específico
        
        :param incluir_seguro: Si True, incluye la garantía extendida (seguro)
        :param incluir_servicios: Si True, incluye los servicios técnicos
        :param plazo: Plazo en meses (si None, usa el plazo_meses del registro)
        :return: Diccionario con los valores calculados
        """
        self.ensure_one()
        plazo_calc = plazo if plazo is not None else self._plazo_meses_int()
        
        # Calcular costo del equipo base (sin garantía)
        costo_equipo_base_usd = self.valor_usd
        if incluir_seguro:
            costo_equipo_base_usd += self.valor_garantia_usd
        
        # Aplicar utilidad
        costo_con_utilidad_usd = costo_equipo_base_usd * (1 + self.porcentaje_utilidad / 100.0)
        
        # Convertir a COP
        usd = self.env.ref('base.USD', raise_if_not_found=False)
        costo_equipo_cop = self._convert_to_company_currency(costo_con_utilidad_usd, usd) if usd else 0.0
        
        # Calcular servicios
        servicio_mensual = 0.0
        if incluir_servicios:
            servicio_mensual = self.servicio_con_margen
        
        # Cuota del equipo: reparto lineal del capital o PMT según configuración
        pago_base_equipo = (
            self._pago_mensual_solo_equipo(costo_equipo_cop, plazo_calc) if plazo_calc > 0 else 0.0
        )
        
        # Pago mensual total (equipo + servicios)
        pago_mensual_total = pago_base_equipo + servicio_mensual
        
        # Total a pagar
        total_pagar = pago_mensual_total * plazo_calc
        
        # Calcular valor del equipo sin garantía (siempre)
        valor_equipo_sin_garantia_cop = self._convert_to_company_currency(
            self.valor_usd * (1 + self.porcentaje_utilidad / 100.0),
            usd,
        ) if usd else 0.0
        
        # Calcular valor de garantía en COP si está incluida
        garantia_cop = 0.0
        if incluir_seguro and self.valor_garantia_usd > 0:
            garantia_cop = self._convert_to_company_currency(
                self.valor_garantia_usd * (1 + self.porcentaje_utilidad / 100.0),
                usd,
            ) if usd else 0.0
        
        return {
            'costo_equipo_usd': costo_equipo_base_usd,
            'costo_equipo_cop': costo_equipo_cop,
            'valor_equipo_sin_garantia_cop': valor_equipo_sin_garantia_cop,
            'garantia_cop': garantia_cop,
            'servicio_mensual': servicio_mensual,
            'pago_base_equipo': pago_base_equipo,
            'pago_mensual_total': pago_mensual_total,
            'total_pagar': total_pagar,
            'plazo': plazo_calc,
        }
    
    def get_escenarios_resumen(self):
        """
        Obtiene los 4 escenarios para el reporte.
        Los escenarios muestran el desglose de los valores calculados.
        
        IMPORTANTE: El Escenario 1 (con seguro y servicios) debería coincidir con
        los valores por plazo mostrados en la interfaz cuando el equipo tiene garantía configurada.
        
        :return: Diccionario con los 4 escenarios y sus valores por plazo
        """
        self.ensure_one()
        
        escenarios = {
            'escenario_1': {
                'nombre': 'Con Seguro y Servicios Técnicos',
                'incluir_seguro': True,
                'incluir_servicios': True,
                'plazos': {}
            },
            'escenario_2': {
                'nombre': 'Sin Seguro pero con Servicios Técnicos',
                'incluir_seguro': False,
                'incluir_servicios': True,
                'plazos': {}
            },
            'escenario_3': {
                'nombre': 'Con Seguro pero sin Servicios Técnicos',
                'incluir_seguro': True,
                'incluir_servicios': False,
                'plazos': {}
            },
            'escenario_4': {
                'nombre': 'Sin Seguro ni Servicios Técnicos',
                'incluir_seguro': False,
                'incluir_servicios': False,
                'plazos': {}
            },
        }
        
        # Calcular valores para cada escenario en los diferentes plazos
        # Usa _calcular_escenario que ya tiene toda la lógica de cálculo
        for esc_key, esc_data in escenarios.items():
            for plazo in PLAZOS_COMPARACION_MESES:
                valores = self._calcular_escenario(
                    incluir_seguro=esc_data['incluir_seguro'],
                    incluir_servicios=esc_data['incluir_servicios'],
                    plazo=plazo
                )
                esc_data['plazos'][plazo] = valores
        
        return escenarios
    
    def validar_consistencia_calculos(self):
        """
        Valida que los cálculos de la interfaz web coincidan con los del reporte.
        Retorna un diccionario con los resultados de la validación.
        """
        self.ensure_one()
        resultados = {
            'valido': True,
            'errores': [],
            'advertencias': []
        }
        
        # Validar que valor_24_meses coincida con Escenario 1 a 24 meses
        # (solo si hay garantía configurada)
        if self.valor_garantia_usd > 0:
            escenario_1 = self.get_escenarios_resumen()['escenario_1']
            valor_24_escenario = escenario_1['plazos'][24]['pago_mensual_total']
            diferencia = abs(self.valor_24_meses - valor_24_escenario)
            
            # Permitir pequeñas diferencias por redondeo (menos de 1 COP)
            if diferencia > 1.0:
                resultados['valido'] = False
                resultados['errores'].append(
                    f"valor_24_meses ({self.valor_24_meses:,.2f}) no coincide con "
                    f"Escenario 1 a 24 meses ({valor_24_escenario:,.2f}). "
                    f"Diferencia: {diferencia:,.2f} COP"
                )
            elif diferencia > 0.01:
                resultados['advertencias'].append(
                    f"Pequeña diferencia en valor_24_meses: {diferencia:,.2f} COP"
                )
        
        # Validar que pago_mensual coincida con el escenario correspondiente
        # según el plazo configurado
        pm = self._plazo_meses_int()
        if pm in PLAZOS_COMPARACION_MESES:
            escenario_1 = self.get_escenarios_resumen()['escenario_1']
            valor_plazo_escenario = escenario_1['plazos'][pm]['pago_mensual_total']
            diferencia = abs(self.pago_mensual - valor_plazo_escenario)
            
            if diferencia > 1.0:
                resultados['valido'] = False
                resultados['errores'].append(
                    f"pago_mensual ({self.pago_mensual:,.2f}) no coincide con "
                    f"Escenario 1 a {pm} meses ({valor_plazo_escenario:,.2f}). "
                    f"Diferencia: {diferencia:,.2f} COP"
                )
        
        return resultados

    def _ensure_line_count(self):
        """Mantiene line_ids sincronizado con cantidad_equipos.

        En formularios nuevos (padre sin guardar) no se debe usar create()/unlink()
        sobre las líneas: el cliente web espera ids virtuales (NewId) y mezclar
        enteros reales rompe el diff del onchange (AttributeError: 'int' has no 'origin').
        """
        Line = self.env["calculadora.costos.line"]
        for record in self:
            target = max(1, min(100, record.cantidad_equipos or 1))
            lines = record.line_ids.sorted("sequence")
            current = len(lines)
            if current < target:
                if record._origin:
                    vals_list = []
                    for seq in range(current + 1, target + 1):
                        vals_list.append({
                            "calculadora_id": record.id,
                            "sequence": seq,
                        })
                    Line.create(vals_list)
                else:
                    record.line_ids = [
                        (
                            0,
                            0,
                            {
                                "sequence": seq,
                                "name": record.name or "Equipo",
                                "moneda_equipo": "USD",
                                "product_qty": 1.0,
                                "price_unit": 0.0,
                                "monto_garantia": 0.0,
                            },
                        )
                        for seq in range(current + 1, target + 1)
                    ]
            elif current > target:
                to_remove = lines[target:]
                if record._origin:
                    to_remove.unlink()
                else:
                    record.line_ids = [(2, line.id) for line in to_remove]

    @api.depends(
        "line_ids",
        "line_ids.name",
        "line_ids.product_id",
        "line_ids.product_qty",
        "line_ids.price_unit",
        "line_ids.monto_garantia",
        "line_ids.moneda_equipo",
        "line_ids.subtotal_base_cop",
        "applied_currency_rate",
        "rate_date",
    )
    def _compute_equipo_campos(self):
        usd = self.env.ref("base.USD", raise_if_not_found=False)
        cop = self.env.ref("base.COP", raise_if_not_found=False)
        for record in self:
            lines = record.line_ids.sorted("sequence")
            for idx in range(1, 21):
                line = lines[idx - 1] if len(lines) >= idx else False
                setattr(record, f"equipo_{idx}_nombre", line.name if line else False)
                setattr(record, f"equipo_{idx}_product_id", line.product_id if line else False)
                if line:
                    amt = line.amount_equipment()
                    source_currency = record._line_source_currency(line)
                    evu = record._convert_currency_amount(amt, source_currency, usd) if usd and source_currency else 0.0
                    eg = record._convert_currency_amount(line.monto_garantia or 0.0, source_currency, usd) if usd and source_currency else 0.0
                    evc = record._convert_currency_amount(amt, source_currency, cop) if cop and source_currency else 0.0
                    egc = record._convert_currency_amount(line.monto_garantia or 0.0, source_currency, cop) if cop and source_currency else 0.0
                    st = line.subtotal_base_cop
                else:
                    evu = eg = evc = egc = st = 0.0
                setattr(record, f"equipo_{idx}_valor_usd", evu)
                setattr(record, f"equipo_{idx}_garantia_usd", eg)
                setattr(record, f"equipo_{idx}_valor_cop", evc)
                setattr(record, f"equipo_{idx}_garantia_cop", egc)
                setattr(record, f"equipo_{idx}_costo_total_cop", st)

    def _inverse_equipo_campos(self):
        for record in self:
            record._ensure_line_count()
            lines = record.line_ids.sorted("sequence")
            for idx in range(1, min(record.cantidad_equipos, 20) + 1):
                line = lines[idx - 1]
                vu = getattr(record, f"equipo_{idx}_valor_usd", 0.0) or 0.0
                vg = getattr(record, f"equipo_{idx}_garantia_usd", 0.0) or 0.0
                vc = getattr(record, f"equipo_{idx}_valor_cop", 0.0) or 0.0
                gc = getattr(record, f"equipo_{idx}_garantia_cop", 0.0) or 0.0
                # Prefer COP si el usuario editó esos campos; si no, USD
                if vc or gc:
                    line.write({
                        "name": getattr(record, f"equipo_{idx}_nombre", False) or False,
                        "product_id": getattr(record, f"equipo_{idx}_product_id", False).id
                        if getattr(record, f"equipo_{idx}_product_id", False)
                        else False,
                        "moneda_equipo": "COP",
                        "product_qty": 1.0,
                        "price_unit": vc,
                        "monto_garantia": gc,
                    })
                else:
                    line.write({
                        "name": getattr(record, f"equipo_{idx}_nombre", False) or False,
                        "product_id": getattr(record, f"equipo_{idx}_product_id", False).id
                        if getattr(record, f"equipo_{idx}_product_id", False)
                        else False,
                        "moneda_equipo": "USD",
                        "product_qty": 1.0,
                        "price_unit": vu,
                        "monto_garantia": vg,
                    })

    @api.onchange("cantidad_equipos")
    def _onchange_cantidad_equipos(self):
        self._ensure_line_count()
    
    def action_print_report(self):
        """Acción para imprimir el reporte PDF"""
        self.ensure_one()
        return {
            'type': 'ir.actions.report',
            'report_name': 'calculadora_costos.report_calculadora',
            'report_type': 'qweb-pdf',
            'res_model': 'calculadora.costos',
            'res_id': self.id,
            'context': self.env.context,
        }