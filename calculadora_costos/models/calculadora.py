# -*- coding: utf-8 -*-

import base64
from odoo import models, fields, api
from odoo.exceptions import UserError
from decimal import Decimal, getcontext

getcontext().prec = 10


class Calculadora(models.Model):
    _name = 'calculadora.costos'
    _description = 'Calculadora de Costos y Renting'
    _order = 'create_date desc'

    name = fields.Char(
        string='Nombre',
        required=True,
        help='Nombre o descripción del cálculo'
    )
    
    # Tipo de cálculo
    tipo_calculo = fields.Selection([
        ('renting', 'Renting')
    ], string='Tipo de Cálculo', default='renting', required=True,
       help='Tipo de cálculo a realizar')
    
    # Relación con Cliente
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        domain=[
            ('is_company', '=', True),
            ('tipo_contacto', 'in', ['cliente', 'ambos']),
        ],
        help='Cliente asociado a este cálculo (solo empresas con tipo Cliente o Proveedor y Cliente)'
    )
    
    subscription_count = fields.Integer(
        string='Suscripciones Activas',
        compute='_compute_subscription_count',
        store=False,
        help='Cantidad de suscripciones no contables activas del cliente'
    )

    # Estado del flujo: borrador, enviada por correo, aprobada (y cargada a lista de precios si es renting)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('sent', 'Enviada'),
        ('approved', 'Aprobada'),
    ], string='Estado', default='draft', required=True, copy=False,
       help='Borrador: en edición. Enviada: cotización enviada por correo. Aprobada: cliente aprobó y (si es renting) se cargó a lista de precios.')

    # Tipo de operación: Venta (solo valor con utilidad) o Renting (con servicios, financiación, plazos)
    tipo_operacion = fields.Selection([
        ('venta', 'Venta'),
        ('renting', 'Renting'),
    ], string='Tipo de operación', default='renting', required=True,
       help='Venta: cotización con valor del producto con utilidad. Renting: incluye servicios técnicos, parámetros financieros y opciones por plazo.')

    # Moneda de cotización (el total siempre se muestra en COP)
    moneda_cotizacion = fields.Selection([
        ('usd', 'USD'),
        ('cop', 'COP (Pesos)'),
    ], string='Cotizar en', default='usd', required=True,
       help='Moneda en la que ingresarás los valores del equipo. El total siempre se mostrará en pesos (COP).')

    # Tipo: Bien o Servicio (solo estas dos opciones; si es Bien se muestra categoría de activo)
    tipo_producto = fields.Selection([
        ('consu', 'Bien'),
        ('service', 'Servicio'),
    ], string='Tipo', default='consu', required=True,
       help='Seleccione si cotiza un bien (activo) o un servicio. Si es bien, podrá elegir la categoría de activo.')
    asset_category_id = fields.Many2one(
        'product.asset.category',
        string='Categoría de activo',
        help='Categoría del activo a cotizar (visible cuando el tipo es Bien).'
    )
    asset_class_id = fields.Many2one(
        'product.asset.class',
        string='Clase de activo',
        domain="[('category_id', '=', asset_category_id)]",
        help='Clase del activo a cotizar (visible cuando el tipo es Bien). Filtra por la categoría seleccionada.'
    )

    # Cantidad de equipos a cotizar (1 o más)
    cantidad_equipos = fields.Integer(
        string='Cantidad de equipos',
        default=1,
        required=True,
        help='Número de equipos a cotizar (1 a 20). Guarde para actualizar la lista de equipos.'
    )
    _cantidad_equipos_range = models.Constraint(
        'CHECK(cantidad_equipos >= 1 AND cantidad_equipos <= 20)',
        'La cantidad de equipos debe estar entre 1 y 20.',
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

    # Costos del Equipo (se mantienen para compatibilidad cuando hay 1 solo equipo)
    valor_usd = fields.Float(
        string='Valor en USD',
        default=0.0,
        digits=(16, 0),
        help='Valor del equipo en dólares estadounidenses'
    )
    
    valor_garantia_usd = fields.Float(
        string='Valor Garantía Extendida (USD)',
        default=0.0,
        digits=(16, 0),
        help='Costo adicional de garantía extendida en USD'
    )
    
    valor_cop = fields.Float(
        string='Valor en COP',
        default=0.0,
        digits=(16, 0),
        help='Valor del equipo en pesos colombianos (visible cuando cotizas en COP)'
    )
    
    valor_garantia_cop = fields.Float(
        string='Valor Garantía Extendida (COP)',
        default=0.0,
        digits=(16, 0),
        help='Costo adicional de garantía extendida en pesos (visible cuando cotizas en COP)'
    )
    
    porcentaje_utilidad = fields.Float(
        string='Porcentaje de Utilidad (%)',
        default=10.0,
        required=True,
        digits=(16, 0),
        help='Porcentaje de utilidad aplicado sobre el costo (ej: 10 = 10%, 20 = 20%)'
    )
    
    trm = fields.Float(
        string='TRM (COP/USD)',
        required=True,
        default=4000.0,
        digits=(16, 0),
        help='Tasa Representativa del Mercado para conversión'
    )
    
    costo_total_usd = fields.Float(
        string='Costo Total USD',
        compute='_compute_costo_total_usd',
        store=True,
        digits=(16, 0),
        help='Costo total en USD (equipo + garantía)'
    )
    
    costo_con_utilidad_usd = fields.Float(
        string='Costo con Utilidad (USD)',
        compute='_compute_costo_con_utilidad',
        store=True,
        digits=(16, 0),
        help='Costo aplicando porcentaje de utilidad'
    )
    
    costo_total_cop = fields.Float(
        string='Costo Total (COP)',
        compute='_compute_costo_total_cop',
        store=True,
        digits='Calculadora COP (Entero)',
        help='Conversión a pesos del costo con utilidad (costo_con_utilidad_usd × TRM)'
    )
    
    # Costos de Servicios
    costo_servicios_completos = fields.Float(
        string='Costo Servicios Completos (Anual)',
        default=0.0,
        digits=(16, 0),
        help='Costo base anual de servicios técnicos. En reportes se divide por 12 para obtener el valor mensual.'
    )
    
    porcentaje_margen_servicio = fields.Float(
        string='Porcentaje Margen Servicio (%)',
        default=15.0,
        digits=(16, 0),
        help='Porcentaje de margen aplicado a servicios (ej: 15 = 15%, 25 = 25%)'
    )
    
    servicio_con_margen = fields.Float(
        string='Servicio con Margen',
        compute='_compute_servicio_con_margen',
        store=True,
        digits=(16, 0),
        help='Costo de servicios con margen aplicado (en USD si carga el costo en USD)'
    )
    
    servicio_con_margen_cop = fields.Float(
        string='Servicio con Margen (COP/anual)',
        compute='_compute_servicio_con_margen_cop',
        store=True,
        digits='Calculadora COP (Entero)',
        help='Costo anual de servicios con margen en COP. En reportes se divide por 12 para el valor mensual.'
    )
    
    # Parámetros Financieros
    tasa_nominal = fields.Float(
        string='Tasa Nominal (%)',
        default=21.0,
        required=True,
        digits=(16, 0),
        help='Tasa de interés nominal anual en porcentaje'
    )
    
    tasa_mensual = fields.Float(
        string='Tasa Mensual (%)',
        compute='_compute_tasa_mensual',
        store=True,
        digits=(16, 0),
        help='Tasa de interés mensual calculada'
    )
    
    tasa_efectiva_anual = fields.Float(
        string='Tasa Efectiva Anual (%)',
        compute='_compute_tasa_efectiva_anual',
        store=True,
        digits=(16, 0),
        help='Tasa efectiva anual calculada'
    )
    
    PLAZOS_MESES = [
        ('12', '12 meses'),
        ('24', '24 meses'),
        ('36', '36 meses'),
        ('48', '48 meses'),
        ('60', '60 meses'),
    ]
    plazo_meses = fields.Selection(
        PLAZOS_MESES,
        string='Plazo (Meses)',
        default='24',
        required=True,
        help='Plazo del financiamiento en meses (12, 24, 36, 48, 60)'
    )
    
    # Opción de Compra
    porcentaje_opcion_compra = fields.Float(
        string='Porcentaje Opción de Compra (%)',
        default=20.0,
        digits=(16, 0),
        help='Porcentaje del valor del equipo para opción de compra'
    )
    
    valor_opcion_compra = fields.Float(
        string='Valor Opción de Compra (COP)',
        compute='_compute_valor_opcion_compra',
        store=True,
        digits='Calculadora COP (Entero)',
        help='Valor calculado de la opción de compra'
    )
    
    # Pago Mensual
    pago_mensual = fields.Float(
        string='Pago Mensual (COP)',
        compute='_compute_pago_mensual',
        store=True,
        digits='Calculadora COP (Entero)',
        help='Pago mensual calculado incluyendo servicios'
    )
    
    # Campo auxiliar para mostrar el costo del equipo sin servicios
    costo_equipo_cop = fields.Float(
        string='Costo Equipo (COP)',
        compute='_compute_costo_equipo_cop',
        store=True,
        digits=(16, 0),
        help='Costo del equipo sin incluir servicios'
    )
    
    # Valores por plazo: costo_total_cop / meses (cuota fija sin interés)
    valor_12_meses = fields.Float(
        string='Valor 12 Meses',
        compute='_compute_valores_plazos',
        store=True,
        digits='Calculadora COP (Entero)',
        help='Cuota mensual para 12 meses (costo_total_cop / 12)'
    )
    valor_24_meses = fields.Float(
        string='Valor 24 Meses',
        compute='_compute_valores_plazos',
        store=True,
        digits='Calculadora COP (Entero)',
        help='Cuota mensual para 24 meses (costo_total_cop / 24)'
    )
    
    valor_36_meses = fields.Float(
        string='Valor 36 Meses',
        compute='_compute_valores_plazos',
        store=True,
        digits='Calculadora COP (Entero)',
        help='Cuota mensual para 36 meses (costo_total_cop / 36)'
    )
    
    valor_48_meses = fields.Float(
        string='Valor 48 Meses',
        compute='_compute_valores_plazos',
        store=True,
        digits='Calculadora COP (Entero)',
        help='Cuota mensual para 48 meses (costo_total_cop / 48)'
    )
    
    valor_60_meses = fields.Float(
        string='Valor 60 Meses',
        compute='_compute_valores_plazos',
        store=True,
        digits='Calculadora COP (Entero)',
        help='Cuota mensual para 60 meses (costo_total_cop / 60)'
    )
    
    # Total a Pagar
    total_pagar = fields.Float(
        string='Total a Pagar',
        compute='_compute_total_pagar',
        store=True,
        digits=(16, 0),
        help='Total a pagar durante todo el plazo'
    )
    
    # Aprobación (solo renting): plazo y escenario elegidos por el cliente para cargar a lista de precios
    approved_plazo_meses = fields.Integer(
        string='Plazo aprobado (meses)',
        help='Plazo en meses con el que el cliente aprobó la cotización (12, 24, 36, 48 o 60).'
    )
    approved_escenario_key = fields.Selection([
        ('escenario_1', 'Escenario 1: Con Seguro y Servicios'),
        ('escenario_2', 'Escenario 2: Sin Seguro, con Servicios'),
        ('escenario_3', 'Escenario 3: Con Seguro, sin Servicios'),
        ('escenario_4', 'Escenario 4: Sin Seguro ni Servicios'),
    ], string='Escenario aprobado',
       help='Escenario elegido por el cliente al aprobar.')

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
    
    currency_usd_id = fields.Many2one(
        'res.currency',
        string='Moneda USD',
        default=lambda self: self.env.ref('base.USD', raise_if_not_found=False),
        required=True
    )
    
    # Métodos de cálculo
    @api.depends('valor_usd', 'valor_garantia_usd', 'valor_cop', 'valor_garantia_cop', 'moneda_cotizacion', 'trm')
    def _compute_costo_total_usd(self):
        """Calcula el costo total en USD (para referencia cuando se cotiza en COP)"""
        for record in self:
            if record.moneda_cotizacion == 'usd':
                record.costo_total_usd = round(record.valor_usd + record.valor_garantia_usd, 0)
            else:
                # Cuando se cotiza en COP, convertir a USD para referencia
                total_cop = record.valor_cop + record.valor_garantia_cop
                record.costo_total_usd = round(total_cop / record.trm, 0) if record.trm else 0.0
    
    @api.depends('valor_usd', 'valor_garantia_usd', 'valor_cop', 'valor_garantia_cop', 'moneda_cotizacion', 'porcentaje_utilidad')
    def _compute_costo_con_utilidad(self):
        """Calcula el costo aplicando porcentaje de utilidad"""
        for record in self:
            factor_utilidad = 1 + (record.porcentaje_utilidad / 100.0)
            if record.moneda_cotizacion == 'usd':
                record.costo_con_utilidad_usd = round((record.valor_usd + record.valor_garantia_usd) * factor_utilidad, 0)
            else:
                # En modo COP, costo_con_utilidad_usd = (valor_cop + valor_garantia_cop) / TRM * factor (para consistencia)
                total_cop = record.valor_cop + record.valor_garantia_cop
                record.costo_con_utilidad_usd = round((total_cop * factor_utilidad) / record.trm, 0) if record.trm else 0.0
    
    @api.depends('valor_usd', 'valor_garantia_usd', 'valor_cop', 'valor_garantia_cop', 'moneda_cotizacion', 'porcentaje_utilidad', 'trm')
    def _compute_costo_equipo_cop(self):
        """Calcula el costo del equipo en pesos colombianos (sin servicios). Total siempre en COP."""
        for record in self:
            factor_utilidad = 1 + (record.porcentaje_utilidad / 100.0)
            if record.moneda_cotizacion == 'usd':
                record.costo_equipo_cop = round((record.valor_usd + record.valor_garantia_usd) * factor_utilidad * record.trm, 0)
            else:
                record.costo_equipo_cop = round((record.valor_cop + record.valor_garantia_cop) * factor_utilidad, 0)
    
    @api.depends('valor_usd', 'valor_garantia_usd', 'valor_cop', 'valor_garantia_cop', 'moneda_cotizacion', 'porcentaje_utilidad', 'trm', 'line_ids.costo_total_cop')
    def _compute_costo_total_cop(self):
        """Costo total en pesos. Si hay líneas de equipos, suma de todas; si no, valor del registro."""
        for record in self:
            if record.line_ids:
                record.costo_total_cop = int(round(sum(record.line_ids.mapped('costo_total_cop')), 0))
            else:
                factor_utilidad = 1 + (record.porcentaje_utilidad / 100.0)
                if record.moneda_cotizacion == 'usd':
                    record.costo_total_cop = int(round((record.valor_usd + record.valor_garantia_usd) * factor_utilidad * record.trm, 0))
                else:
                    record.costo_total_cop = int(round((record.valor_cop + record.valor_garantia_cop) * factor_utilidad, 0))
    
    @api.depends('costo_servicios_completos', 'porcentaje_margen_servicio')
    def _compute_servicio_con_margen(self):
        """Calcula el servicio con margen aplicado (misma unidad que costo_servicios_completos según moneda_cotizacion)"""
        for record in self:
            margen = 1 + (record.porcentaje_margen_servicio / 100.0)
            record.servicio_con_margen = int(round(record.costo_servicios_completos * margen, 0))
    
    @api.depends('servicio_con_margen', 'trm', 'moneda_cotizacion')
    def _compute_servicio_con_margen_cop(self):
        """Convierte servicio con margen a COP según moneda de cotización.
        - Si cotiza en USD: costo_servicios_completos está en USD → multiplicar por TRM
        - Si cotiza en COP: costo_servicios_completos está en COP → usar directamente"""
        for record in self:
            if record.moneda_cotizacion == 'usd':
                record.servicio_con_margen_cop = int(round(record.servicio_con_margen * record.trm, 0))
            else:
                record.servicio_con_margen_cop = int(round(record.servicio_con_margen, 0))
    
    @api.depends('tasa_nominal')
    def _compute_tasa_mensual(self):
        """Calcula la tasa mensual"""
        for record in self:
            record.tasa_mensual = round(record.tasa_nominal / 12.0, 0)
    
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
            plazo = int(record.plazo_meses or 0) if record.plazo_meses else 0
            if plazo > 0:
                # Calcular con mayor precisión usando Decimal
                tasa_nominal_decimal = Decimal(str(record.tasa_nominal)) / Decimal('100')
                tasa_mensual_decimal = tasa_nominal_decimal / Decimal('12')
                uno_mas_tasa = Decimal('1') + tasa_mensual_decimal
                factor = uno_mas_tasa ** 12
                tasa_efectiva_decimal = factor - Decimal('1')
                record.tasa_efectiva_anual = round(float(tasa_efectiva_decimal * Decimal('100')), 0)
            else:
                record.tasa_efectiva_anual = 0.0
    
    @api.depends('costo_equipo_cop', 'porcentaje_opcion_compra')
    def _compute_valor_opcion_compra(self):
        """Calcula el valor de la opción de compra (solo sobre el costo del equipo, no servicios)"""
        for record in self:
            porcentaje = record.porcentaje_opcion_compra / 100.0
            record.valor_opcion_compra = int(round(record.costo_equipo_cop * porcentaje, 0))
    
    @api.depends('costo_total_cop', 'plazo_meses')
    def _compute_pago_mensual(self):
        """Pago mensual = costo_total_cop / plazo_meses (cuota fija según plazo seleccionado)."""
        for record in self:
            plazo = int(record.plazo_meses or 0) if record.plazo_meses else 0
            if plazo > 0:
                record.pago_mensual = int(round(record.costo_total_cop / plazo, 0))
            else:
                record.pago_mensual = 0
    
    @api.depends('costo_total_cop')
    def _compute_valores_plazos(self):
        """Cuota mensual por plazo: costo_total_cop dividido en 12, 24, 36, 48 y 60 meses."""
        for record in self:
            total = record.costo_total_cop or 0
            record.valor_12_meses = int(round(total / 12.0, 0)) if total else 0
            record.valor_24_meses = int(round(total / 24.0, 0)) if total else 0
            record.valor_36_meses = int(round(total / 36.0, 0)) if total else 0
            record.valor_48_meses = int(round(total / 48.0, 0)) if total else 0
            record.valor_60_meses = int(round(total / 60.0, 0)) if total else 0
    
    @api.depends('pago_mensual', 'plazo_meses')
    def _compute_total_pagar(self):
        """Calcula el total a pagar durante todo el plazo (solo cuotas mensuales)"""
        for record in self:
            plazo = int(record.plazo_meses or 0) if record.plazo_meses else 0
            record.total_pagar = round(record.pago_mensual * plazo, 0)
    
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
    
    def _ajustar_lineas_equipos(self):
        """Crea o elimina líneas para que haya exactamente cantidad_equipos."""
        for rec in self:
            n = max(1, rec.cantidad_equipos or 1)
            lines = rec.line_ids.sorted(key=lambda l: l.sequence)
            if len(lines) < n:
                for i in range(len(lines), n):
                    self.env['calculadora.costos.line'].create({
                        'calculadora_id': rec.id,
                        'sequence': i + 1,
                        'name': 'Equipo %s' % (i + 1),
                    })
            elif len(lines) > n:
                to_unlink = lines[n:]
                to_unlink.unlink()
            # Si no hay líneas pero hay valores en el registro principal, crear una línea con esos valores
            if not rec.line_ids and (rec.valor_usd or rec.valor_cop or rec.valor_garantia_usd or rec.valor_garantia_cop):
                self.env['calculadora.costos.line'].create({
                    'calculadora_id': rec.id,
                    'sequence': 1,
                    'name': 'Equipo 1',
                    'valor_usd': rec.valor_usd,
                    'valor_garantia_usd': rec.valor_garantia_usd,
                    'valor_cop': rec.valor_cop,
                    'valor_garantia_cop': rec.valor_garantia_cop,
                })
                rec.cantidad_equipos = 1

    def get_lineas_para_reporte(self):
        """Devuelve las líneas de equipos para el reporte. Si no hay líneas, usa el registro actual como una línea virtual."""
        self.ensure_one()
        if self.line_ids:
            return self.line_ids.sorted(key=lambda l: l.sequence)
        return self

    def get_report_equipos(self):
        """Lista de dicts con nombre_equipo y escenarios para el reporte (4 escenarios por equipo)."""
        self.ensure_one()
        lineas = self.get_lineas_para_reporte()
        resultado = []
        for idx, linea in enumerate(lineas):
            if linea._name == 'calculadora.costos.line':
                nombre = linea.name or ('Equipo %s' % (idx + 1))
            else:
                nombre = 'Equipo 1'
            resultado.append({
                'nombre': nombre,
                'linea': linea,
                'escenarios': self.get_escenarios_resumen_linea(linea),
            })
        return resultado

    def _calcular_escenario_linea(self, line, incluir_seguro=True, incluir_servicios=True, plazo=None):
        """Calcula un escenario para una línea de equipo. line puede ser calculadora.costos.line o self (registro único)."""
        self.ensure_one()
        plazo_calc = plazo if plazo is not None else (int(self.plazo_meses or 0) if self.plazo_meses else 0)
        factor_utilidad = 1 + (self.porcentaje_utilidad / 100.0)
        # Determinar si line es una línea o el propio registro
        if line._name == 'calculadora.costos.line':
            valor_usd = line.valor_usd
            valor_garantia_usd = line.valor_garantia_usd
            valor_cop = line.valor_cop
            valor_garantia_cop = line.valor_garantia_cop
            costo_equipo_cop_line = line.costo_equipo_cop
        else:
            valor_usd = self.valor_usd
            valor_garantia_usd = self.valor_garantia_usd
            valor_cop = self.valor_cop
            valor_garantia_cop = self.valor_garantia_cop
            costo_equipo_cop_line = self.costo_equipo_cop
        if self.moneda_cotizacion == 'usd':
            costo_equipo_base_usd = valor_usd
            if incluir_seguro:
                costo_equipo_base_usd += valor_garantia_usd
            costo_con_utilidad_usd = costo_equipo_base_usd * factor_utilidad
            costo_equipo_cop = costo_con_utilidad_usd * self.trm
        else:
            costo_base_cop = valor_cop
            if incluir_seguro:
                costo_base_cop += valor_garantia_cop
            costo_equipo_cop = costo_base_cop * factor_utilidad
            costo_equipo_base_usd = costo_equipo_cop / self.trm if self.trm else 0.0
        servicio_mensual = 0.0
        if incluir_servicios:
            servicio_mensual = self.servicio_con_margen_cop / 12.0
        tasa_mensual_decimal = (self.tasa_nominal / 100.0) / 12.0
        pago_base_equipo = 0.0
        if plazo_calc > 0:
            if tasa_mensual_decimal > 0:
                factor = (1 + tasa_mensual_decimal) ** plazo_calc
                pago_base_equipo = (costo_equipo_cop * tasa_mensual_decimal * factor) / (factor - 1)
                if self.porcentaje_opcion_compra > 0:
                    porcentaje_opcion = self.porcentaje_opcion_compra / 100.0
                    valor_opcion = costo_equipo_cop * porcentaje_opcion
                    ajuste_opcion = (valor_opcion * tasa_mensual_decimal) / (factor - 1)
                    pago_base_equipo = pago_base_equipo - ajuste_opcion
            else:
                pago_base_equipo = costo_equipo_cop / plazo_calc
        pago_mensual_total = pago_base_equipo + servicio_mensual
        if self.moneda_cotizacion == 'usd':
            valor_equipo_sin_garantia_cop = valor_usd * factor_utilidad * self.trm
        else:
            valor_equipo_sin_garantia_cop = valor_cop * factor_utilidad
        garantia_cop = 0.0
        if incluir_seguro:
            if self.moneda_cotizacion == 'usd' and valor_garantia_usd > 0:
                garantia_cop = valor_garantia_usd * factor_utilidad * self.trm
            elif self.moneda_cotizacion == 'cop' and valor_garantia_cop > 0:
                garantia_cop = valor_garantia_cop * factor_utilidad
        valor_equipo_por_mes = 0.0
        garantia_por_mes = 0.0
        servicio_por_mes = servicio_mensual if servicio_mensual > 0 else 0.0
        if plazo_calc > 0:
            valor_equipo_por_mes = costo_equipo_cop / plazo_calc
            garantia_por_mes = garantia_cop / plazo_calc if garantia_cop > 0 else 0.0
        pago_mensual_total = valor_equipo_por_mes + garantia_por_mes + servicio_por_mes
        return {
            'costo_equipo_usd': costo_equipo_base_usd if self.moneda_cotizacion == 'usd' else 0.0,
            'costo_equipo_cop': costo_equipo_cop,
            'valor_equipo_sin_garantia_cop': valor_equipo_sin_garantia_cop,
            'garantia_cop': garantia_cop,
            'servicio_mensual': servicio_mensual,
            'pago_base_equipo': pago_base_equipo,
            'pago_mensual_total': pago_mensual_total,
            'total_pagar': pago_mensual_total * plazo_calc,
            'plazo': plazo_calc,
            'valor_equipo_por_mes': valor_equipo_por_mes,
            'garantia_por_mes': garantia_por_mes,
            'servicio_por_mes': servicio_por_mes,
        }

    def get_escenarios_resumen_linea(self, line):
        """Obtiene los 4 escenarios para una línea de equipo (o para el registro si es modo único)."""
        self.ensure_one()
        escenarios = {
            'escenario_1': {'nombre': 'Con Seguro y Servicios Técnicos', 'incluir_seguro': True, 'incluir_servicios': True, 'plazos': {}},
            'escenario_2': {'nombre': 'Sin Seguro pero con Servicios Técnicos', 'incluir_seguro': False, 'incluir_servicios': True, 'plazos': {}},
            'escenario_3': {'nombre': 'Con Seguro pero sin Servicios Técnicos', 'incluir_seguro': True, 'incluir_servicios': False, 'plazos': {}},
            'escenario_4': {'nombre': 'Sin Seguro ni Servicios Técnicos', 'incluir_seguro': False, 'incluir_servicios': False, 'plazos': {}},
        }
        for esc_key, esc_data in escenarios.items():
            for plazo in [12, 24, 36, 48, 60]:
                valores = self._calcular_escenario_linea(
                    line,
                    incluir_seguro=esc_data['incluir_seguro'],
                    incluir_servicios=esc_data['incluir_servicios'],
                    plazo=plazo
                )
                esc_data['plazos'][plazo] = valores
        return escenarios

    @api.model
    def create(self, vals):
        """Sobrescribir create para cargar valores por defecto"""
        parametros = self.env['calculadora.parametros.financieros'].search([], limit=1)
        if parametros:
            if 'trm' not in vals or not vals.get('trm'):
                vals['trm'] = parametros.trm_actual
            if 'porcentaje_utilidad' not in vals:
                vals['porcentaje_utilidad'] = parametros.porcentaje_utilidad_default
            # Renting: por defecto 0% interés para que cuotas = costo equipo / plazo (ej. 2.760.000/24 = 115.000)
            if 'tasa_nominal' not in vals:
                vals['tasa_nominal'] = 0.0
            if 'porcentaje_margen_servicio' not in vals:
                # Usar margen_servicio_default si existe, sino 15% por defecto
                if hasattr(parametros, 'margen_servicio_default'):
                    vals['porcentaje_margen_servicio'] = parametros.margen_servicio_default
                else:
                    vals['porcentaje_margen_servicio'] = 15.0
            # Ajustar valores por defecto para renting
            if 'tipo_calculo' not in vals:
                vals['tipo_calculo'] = 'renting'
            # Siempre usar valores por defecto de renting
            if 'plazo_meses' not in vals:
                vals['plazo_meses'] = '48'
            if 'porcentaje_opcion_compra' not in vals:
                vals['porcentaje_opcion_compra'] = 0.0
            if 'porcentaje_margen_servicio' not in vals:
                vals['porcentaje_margen_servicio'] = 25.0
        record = super(Calculadora, self).create(vals)
        record._ajustar_lineas_equipos()
        return record

    def write(self, vals):
        res = super(Calculadora, self).write(vals)
        if 'cantidad_equipos' in vals:
            self._ajustar_lineas_equipos()
        return res

    @api.depends('line_ids', 'line_ids.name', 'line_ids.product_id', 'line_ids.valor_usd', 'line_ids.valor_garantia_usd',
                 'line_ids.valor_cop', 'line_ids.valor_garantia_cop', 'line_ids.costo_total_cop')
    def _compute_equipo_campos(self):
        """Rellena todos los campos equipo_N_* desde line_ids."""
        for rec in self:
            lines = rec.line_ids.sorted(key=lambda l: l.sequence)
            for n in range(1, 21):
                line = lines[n - 1] if n <= len(lines) else None
                setattr(rec, 'equipo_%d_nombre' % n, line.name if line else '')
                setattr(rec, 'equipo_%d_product_id' % n, line.product_id if line else False)
                setattr(rec, 'equipo_%d_valor_usd' % n, line.valor_usd if line else 0.0)
                setattr(rec, 'equipo_%d_garantia_usd' % n, line.valor_garantia_usd if line else 0.0)
                setattr(rec, 'equipo_%d_valor_cop' % n, line.valor_cop if line else 0.0)
                setattr(rec, 'equipo_%d_garantia_cop' % n, line.valor_garantia_cop if line else 0.0)
                setattr(rec, 'equipo_%d_costo_total_cop' % n, line.costo_total_cop if line else 0.0)

    def _inverse_equipo_campos(self):
        """Escribe en line_ids los valores de los campos equipo_N_*. Conserva siempre los valores
        existentes de la línea cuando el formulario envía vacío/0 (evita que se borren al guardar)."""
        for rec in self:
            lines = rec.line_ids.sorted(key=lambda l: l.sequence)
            if not lines:
                continue
            line_commands = []
            for n in range(1, 21):
                if n > len(lines):
                    break
                line = lines[n - 1]
                nombre_nuevo = getattr(rec, 'equipo_%d_nombre' % n)
                prod = getattr(rec, 'equipo_%d_product_id' % n)
                v_usd = getattr(rec, 'equipo_%d_valor_usd' % n)
                g_usd = getattr(rec, 'equipo_%d_garantia_usd' % n)
                v_cop = getattr(rec, 'equipo_%d_valor_cop' % n)
                g_cop = getattr(rec, 'equipo_%d_garantia_cop' % n)
                # Conservar valores de la línea cuando lo que llega está vacío o es 0 (actualización parcial)
                name_final = nombre_nuevo or line.name or ''
                product_final = prod or line.product_id
                valor_usd_final = v_usd if (v_usd != 0 or line.valor_usd == 0) else line.valor_usd
                garantia_usd_final = g_usd if (g_usd != 0 or line.valor_garantia_usd == 0) else line.valor_garantia_usd
                valor_cop_final = v_cop if (v_cop != 0 or line.valor_cop == 0) else line.valor_cop
                garantia_cop_final = g_cop if (g_cop != 0 or line.valor_garantia_cop == 0) else line.valor_garantia_cop
                line_commands.append((1, line.id, {
                    'name': name_final or '',
                    'product_id': product_final.id if product_final else False,
                    'valor_usd': valor_usd_final,
                    'valor_garantia_usd': garantia_usd_final,
                    'valor_cop': valor_cop_final,
                    'valor_garantia_cop': garantia_cop_final,
                }))
            if line_commands:
                rec.write({'line_ids': line_commands})

    def _calcular_escenario(self, incluir_seguro=True, incluir_servicios=True, plazo=None):
        """
        Calcula los valores para un escenario específico
        
        :param incluir_seguro: Si True, incluye la garantía extendida (seguro)
        :param incluir_servicios: Si True, incluye los servicios técnicos
        :param plazo: Plazo en meses (si None, usa el plazo_meses del registro)
        :return: Diccionario con los valores calculados
        """
        self.ensure_one()
        plazo_calc = plazo if plazo is not None else (int(self.plazo_meses or 0) if self.plazo_meses else 0)
        
        factor_utilidad = 1 + (self.porcentaje_utilidad / 100.0)
        
        # Calcular costo del equipo según moneda de cotización
        if self.moneda_cotizacion == 'usd':
            costo_equipo_base_usd = self.valor_usd
            if incluir_seguro:
                costo_equipo_base_usd += self.valor_garantia_usd
            costo_con_utilidad_usd = costo_equipo_base_usd * factor_utilidad
            costo_equipo_cop = costo_con_utilidad_usd * self.trm
        else:
            # Cotización en COP
            costo_base_cop = self.valor_cop
            if incluir_seguro:
                costo_base_cop += self.valor_garantia_cop
            costo_equipo_cop = costo_base_cop * factor_utilidad
            costo_equipo_base_usd = costo_equipo_cop / self.trm if self.trm else 0.0
        
        # Calcular servicios (valor anual dividido por 12 meses para reportes)
        servicio_mensual = 0.0
        if incluir_servicios:
            servicio_mensual = self.servicio_con_margen_cop / 12.0
        
        # Calcular pago mensual del equipo (usando PMT)
        # Usar la misma lógica que _calcular_pago_plazo para consistencia
        tasa_mensual_decimal = (self.tasa_nominal / 100.0) / 12.0
        pago_base_equipo = 0.0
        
        if plazo_calc > 0:
            if tasa_mensual_decimal > 0:
                factor = (1 + tasa_mensual_decimal) ** plazo_calc
                pago_base_equipo = (costo_equipo_cop * tasa_mensual_decimal * factor) / (factor - 1)
                
                # Ajustar por opción de compra si aplica (misma lógica que _calcular_pago_plazo)
                # La opción de compra se calcula sobre el costo_equipo_cop del escenario
                if self.porcentaje_opcion_compra > 0:
                    porcentaje_opcion = self.porcentaje_opcion_compra / 100.0
                    valor_opcion = costo_equipo_cop * porcentaje_opcion
                    ajuste_opcion = (valor_opcion * tasa_mensual_decimal) / (factor - 1)
                    pago_base_equipo = pago_base_equipo - ajuste_opcion
            else:
                pago_base_equipo = costo_equipo_cop / plazo_calc
        
        # Pago mensual total (equipo + servicios)
        pago_mensual_total = pago_base_equipo + servicio_mensual
        
        # Total a pagar
        total_pagar = pago_mensual_total * plazo_calc
        
        # Calcular valor del equipo sin garantía (siempre en COP)
        if self.moneda_cotizacion == 'usd':
            valor_equipo_sin_garantia_cop = self.valor_usd * factor_utilidad * self.trm
        else:
            valor_equipo_sin_garantia_cop = self.valor_cop * factor_utilidad
        
        # Calcular valor de garantía en COP si está incluida
        garantia_cop = 0.0
        if incluir_seguro:
            if self.moneda_cotizacion == 'usd' and self.valor_garantia_usd > 0:
                garantia_cop = self.valor_garantia_usd * factor_utilidad * self.trm
            elif self.moneda_cotizacion == 'cop' and self.valor_garantia_cop > 0:
                garantia_cop = self.valor_garantia_cop * factor_utilidad
        
        # Calcular valores por mes (dividir por plazo)
        valor_equipo_por_mes = 0.0
        garantia_por_mes = 0.0
        servicio_por_mes = 0.0
        
        if plazo_calc > 0:
            # Valor del equipo por mes: usar costo_total_cop / plazo según solicitud del usuario
            # costo_total_cop incluye equipo + garantía con utilidad aplicada
            valor_equipo_por_mes = self.costo_total_cop / plazo_calc
            
            # Garantía por mes (solo si está incluida en el escenario, para desglose)
            garantia_por_mes = garantia_cop / plazo_calc if garantia_cop > 0 else 0.0
            
            # Servicio por mes (valor anual/12, mismo para todos los plazos)
            servicio_por_mes = servicio_mensual if servicio_mensual > 0 else 0.0
        
        # Pago mensual total = suma de los tres valores por mes
        # Según solicitud del usuario: sumar valor_equipo_por_mes + garantia_por_mes + servicio_por_mes
        pago_mensual_total = valor_equipo_por_mes + garantia_por_mes + servicio_por_mes
        
        return {
            'costo_equipo_usd': costo_equipo_base_usd,
            'costo_equipo_cop': costo_equipo_cop,
            'valor_equipo_sin_garantia_cop': valor_equipo_sin_garantia_cop,
            'garantia_cop': garantia_cop,
            'servicio_mensual': servicio_mensual,
            'pago_base_equipo': pago_base_equipo,
            'pago_mensual_total': pago_mensual_total,
            'total_pagar': pago_mensual_total * plazo_calc,
            'plazo': plazo_calc,
            # Valores por mes para el reporte
            'valor_equipo_por_mes': valor_equipo_por_mes,
            'garantia_por_mes': garantia_por_mes,
            'servicio_por_mes': servicio_por_mes,
        }
    
    def get_escenarios_resumen(self):
        """
        Obtiene los 4 escenarios para el reporte.
        Los escenarios muestran el desglose de los valores calculados.
        
        IMPORTANTE: El Escenario 1 (con seguro y servicios) debería coincidir con
        los valores valor_12_meses, valor_24_meses, valor_36_meses, valor_48_meses, valor_60_meses mostrados en
        la interfaz web cuando el equipo tiene garantía configurada.
        
        :return: Diccionario con los 4 escenarios y sus valores para 12, 24, 36, 48 y 60 meses
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
            for plazo in [12, 24, 36, 48, 60]:
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
        if self.plazo_meses in ('12', '24', '36', '48', '60'):
            plazo_int = int(self.plazo_meses)
            escenario_1 = self.get_escenarios_resumen()['escenario_1']
            valor_plazo_escenario = escenario_1['plazos'][plazo_int]['pago_mensual_total']
            diferencia = abs(self.pago_mensual - valor_plazo_escenario)
            
            if diferencia > 1.0:
                resultados['valido'] = False
                resultados['errores'].append(
                    f"pago_mensual ({self.pago_mensual:,.2f}) no coincide con "
                    f"Escenario 1 a {plazo_int} meses ({valor_plazo_escenario:,.2f}). "
                    f"Diferencia: {diferencia:,.2f} COP"
                )
        
        return resultados
    
    def action_print_report(self):
        """Acción para imprimir el reporte PDF completo"""
        self.ensure_one()
        return {
            'type': 'ir.actions.report',
            'report_name': 'calculadora_costos.report_calculadora',
            'report_type': 'qweb-pdf',
            'res_model': 'calculadora.costos',
            'res_id': self.id,
            'context': self.env.context,
        }

    def action_generar_cotizacion(self):
        """Genera el reporte PDF de cotización simplificado (solo meses y valor a pagar)"""
        self.ensure_one()
        return {
            'type': 'ir.actions.report',
            'report_name': 'calculadora_costos.report_cotizacion',
            'report_type': 'qweb-pdf',
            'res_model': 'calculadora.costos',
            'res_id': self.id,
            'context': self.env.context,
        }

    def action_send_quote_email(self):
        """Abre el asistente para enviar la cotización por correo al cliente."""
        self.ensure_one()
        if not self.partner_id or not self.partner_id.email:
            raise UserError('El cliente debe tener un correo electrónico para enviar la cotización.')
        report = self.env.ref('calculadora_costos.action_report_cotizacion', raise_if_not_found=False)
        if not report:
            raise UserError('No se encontró el reporte de cotización.')
        pdf_content, _ = report._render_qweb_pdf(report.report_name, self.ids)
        filename = 'Cotización - %s.pdf' % (self.name or 'Sin Nombre')
        datas = base64.b64encode(pdf_content) if isinstance(pdf_content, bytes) else base64.b64encode(pdf_content.encode() if pdf_content else b'')
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': datas,
            'res_model': self._name,
            'res_id': self.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Enviar cotización por correo',
            'res_model': 'mail.compose.message',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_model': self._name,
                'default_res_id': self.id,
                'default_res_ids': [self.id],
                'default_attachment_ids': [(6, 0, [attachment.id])],
                'default_subject': 'Cotización: %s' % (self.name or ''),
                'default_body': 'Adjunto encontrará la cotización solicitada.',
                'default_partner_ids': [(6, 0, self.partner_id.ids)],
                'default_composition_mode': 'comment',
            },
        }

    def _get_escenario_params(self, escenario_key):
        """Devuelve incluir_seguro e incluir_servicios según la clave del escenario."""
        map_escenario = {
            'escenario_1': (True, True),
            'escenario_2': (False, True),
            'escenario_3': (True, False),
            'escenario_4': (False, False),
        }
        return map_escenario.get(escenario_key, (True, True))

    def action_approve_and_load_pricelist(self, plazo_meses, escenario_key):
        """
        Aprobación de cotización renting: guarda plazo y escenario, y carga cada equipo
        a la lista de precios del cliente con el valor mensual (COP) del escenario/plazo elegido.
        """
        self.ensure_one()
        if self.tipo_operacion != 'renting':
            raise UserError('Solo se puede aprobar y cargar a lista de precios una cotización de tipo Renting.')
        if self.state == 'approved':
            raise UserError('Esta cotización ya está aprobada.')
        if not self.partner_id:
            raise UserError('Debe indicar un cliente para cargar la cotización a su lista de precios.')
        if plazo_meses not in (12, 24, 36, 48, 60):
            raise UserError('El plazo debe ser 12, 24, 36, 48 o 60 meses.')
        if escenario_key not in ('escenario_1', 'escenario_2', 'escenario_3', 'escenario_4'):
            raise UserError('Debe seleccionar un escenario válido.')
        incluir_seguro, incluir_servicios = self._get_escenario_params(escenario_key)
        # Obtener o crear lista de precios del cliente
        pricelist = self.partner_id.property_product_pricelist
        if not pricelist:
            pricelist = self.env['product.pricelist'].create({
                'name': 'Lista - %s' % self.partner_id.name,
                'currency_id': self.env.ref('base.COP', raise_if_not_found=False).id or self.currency_id.id,
            })
            self.partner_id.property_product_pricelist = pricelist
        lineas = self.get_lineas_para_reporte()
        created_items = []
        for linea in lineas:
            if linea._name == 'calculadora.costos.line':
                product = linea.product_id
                nombre_equipo = linea.name or (product.display_name if product else 'Equipo')
            else:
                product = False
                nombre_equipo = 'Equipo 1'
            if not product:
                raise UserError(
                    'Para cargar a la lista de precios, cada equipo debe tener un producto asociado. '
                    'Falta producto en: %s.' % nombre_equipo
                )
            valores = self._calcular_escenario_linea(
                linea,
                incluir_seguro=incluir_seguro,
                incluir_servicios=incluir_servicios,
                plazo=plazo_meses,
            )
            pago_mensual_cop = valores.get('pago_mensual_total', 0)
            if pago_mensual_cop <= 0:
                continue
            item_vals = {
                'pricelist_id': pricelist.id,
                'applied_on': '0_product_variant',
                'product_id': product.id,
                'compute_price': 'fixed',
                'fixed_price': pago_mensual_cop,
            }
            # La moneda de la lista de precios se usa automáticamente; si la lista no tiene COP, se creó con COP arriba
            item = self.env['product.pricelist.item'].create(item_vals)
            created_items.append(item)
        self.write({
            'state': 'approved',
            'approved_plazo_meses': plazo_meses,
            'approved_escenario_key': escenario_key,
        })
        return created_items

    def action_confirm_sent(self):
        """Marca la cotización como enviada por correo (puede llamarse desde el wizard de envío o al cerrar el composer)."""
        self.ensure_one()
        if self.state == 'draft':
            self.write({'state': 'sent'})

    def action_open_approve_wizard(self):
        """Abre el asistente para aprobar la cotización (plazo + escenario) y cargar a lista de precios del cliente."""
        self.ensure_one()
        if self.tipo_operacion != 'renting':
            raise UserError('Solo las cotizaciones de tipo Renting se pueden aprobar y cargar a lista de precios.')
        if self.state == 'approved':
            raise UserError('Esta cotización ya está aprobada.')
        if not self.partner_id:
            raise UserError('Seleccione un cliente para poder aprobar y cargar a su lista de precios.')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Aprobar cotización y cargar a lista de precios',
            'res_model': 'calculadora.approve.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_calculadora_id': self.id},
        }