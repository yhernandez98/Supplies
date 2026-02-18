# -*- coding: utf-8 -*-

from odoo import models, fields, api
from decimal import Decimal, getcontext

getcontext().prec = 10


class CalculadoraEquipo(models.Model):
    _name = 'calculadora.equipo'
    _description = 'Calculadora de Costos de Equipos'
    _order = 'create_date desc'

    name = fields.Char(
        string='Nombre del Equipo',
        required=True,
        help='Nombre o descripción del equipo'
    )
    
    # Costos del Equipo
    valor_usd = fields.Float(
        string='Valor en USD',
        required=True,
        default=0.0,
        help='Valor del equipo en dólares estadounidenses'
    )
    
    valor_garantia_usd = fields.Float(
        string='Valor Garantía Extendida (USD)',
        default=0.0,
        help='Costo adicional de garantía extendida en USD'
    )
    
    porcentaje_utilidad = fields.Float(
        string='Porcentaje de Utilidad (%)',
        default=10.0,
        required=True,
        help='Porcentaje de utilidad aplicado sobre el costo (ej: 10 = 10%, 20 = 20%)'
    )
    
    trm = fields.Float(
        string='TRM (COP/USD)',
        required=True,
        default=4000.0,
        help='Tasa Representativa del Mercado para conversión'
    )
    
    costo_total_usd = fields.Float(
        string='Costo Total USD',
        compute='_compute_costo_total_usd',
        store=True,
        help='Costo total en USD (equipo + garantía)'
    )
    
    costo_con_utilidad_usd = fields.Float(
        string='Costo con Utilidad (USD)',
        compute='_compute_costo_con_utilidad',
        store=True,
        help='Costo aplicando factor de utilidad'
    )
    
    costo_total_cop = fields.Float(
        string='Costo Total (COP)',
        compute='_compute_costo_total_cop',
        store=True,
        help='Costo total en pesos colombianos'
    )
    
    # Costos de Servicios
    costo_servicios_completos = fields.Float(
        string='Costo Servicios Completos',
        default=0.0,
        help='Costo base de servicios técnicos completos'
    )
    
    margen_servicio = fields.Float(
        string='Margen de Servicio (%)',
        default=15.0,
        help='Porcentaje de margen aplicado a servicios (ej: 15 = 15%)'
    )
    
    servicio_con_margen = fields.Float(
        string='Servicio con Margen',
        compute='_compute_servicio_con_margen',
        store=True,
        help='Costo de servicios con margen aplicado'
    )
    
    # Parámetros Financieros
    tasa_nominal = fields.Float(
        string='Tasa Nominal (%)',
        default=21.0,
        required=True,
        help='Tasa de interés nominal anual en porcentaje'
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
        help='Porcentaje del valor del equipo para opción de compra'
    )
    
    valor_opcion_compra = fields.Float(
        string='Valor Opción de Compra (COP)',
        compute='_compute_valor_opcion_compra',
        store=True,
        help='Valor calculado de la opción de compra'
    )
    
    # Pago Mensual
    pago_mensual = fields.Float(
        string='Pago Mensual (COP)',
        compute='_compute_pago_mensual',
        store=True,
        help='Pago mensual calculado incluyendo servicios'
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
    
    currency_usd_id = fields.Many2one(
        'res.currency',
        string='Moneda USD',
        default=lambda self: self.env.ref('base.USD', raise_if_not_found=False),
        required=True
    )
    
    total_pagar = fields.Float(
        string='Total a Pagar',
        compute='_compute_total_pagar',
        store=True,
        help='Total a pagar durante todo el plazo'
    )
    
    @api.depends('pago_mensual', 'plazo_meses', 'valor_opcion_compra')
    def _compute_total_pagar(self):
        """Calcula el total a pagar durante todo el plazo"""
        for record in self:
            plazo = int(record.plazo_meses or 0) if record.plazo_meses else 0
            total_cuotas = record.pago_mensual * plazo
            record.total_pagar = total_cuotas + record.valor_opcion_compra
    
    # Métodos de cálculo
    @api.depends('valor_usd', 'valor_garantia_usd')
    def _compute_costo_total_usd(self):
        """Calcula el costo total en USD"""
        for record in self:
            record.costo_total_usd = record.valor_usd + record.valor_garantia_usd
    
    @api.depends('costo_total_usd', 'porcentaje_utilidad')
    def _compute_costo_con_utilidad(self):
        """Calcula el costo aplicando porcentaje de utilidad"""
        for record in self:
            # Aplicar utilidad: Precio = Costo × (1 + Utilidad/100)
            factor_utilidad = 1 + (record.porcentaje_utilidad / 100.0)
            record.costo_con_utilidad_usd = record.costo_total_usd * factor_utilidad
    
    @api.depends('costo_con_utilidad_usd', 'trm')
    def _compute_costo_total_cop(self):
        """Calcula el costo total en pesos colombianos"""
        for record in self:
            record.costo_total_cop = record.costo_con_utilidad_usd * record.trm
    
    @api.depends('costo_servicios_completos', 'margen_servicio')
    def _compute_servicio_con_margen(self):
        """Calcula el servicio con margen aplicado"""
        for record in self:
            margen = 1 + (record.margen_servicio / 100.0)
            record.servicio_con_margen = record.costo_servicios_completos * margen
    
    @api.depends('tasa_nominal')
    def _compute_tasa_mensual(self):
        """Calcula la tasa mensual"""
        for record in self:
            record.tasa_mensual = record.tasa_nominal / 12.0
    
    @api.depends('tasa_nominal', 'plazo_meses')
    def _compute_tasa_efectiva_anual(self):
        """Calcula la tasa efectiva anual usando la fórmula EFFECT"""
        for record in self:
            plazo = int(record.plazo_meses or 0) if record.plazo_meses else 0
            if plazo > 0:
                tasa_mensual_decimal = (record.tasa_nominal / 100.0) / 12.0
                # Fórmula: (1 + tasa_mensual)^12 - 1
                tasa_efectiva = ((1 + tasa_mensual_decimal) ** 12) - 1
                record.tasa_efectiva_anual = tasa_efectiva * 100.0
            else:
                record.tasa_efectiva_anual = 0.0
    
    @api.depends('costo_total_cop', 'porcentaje_opcion_compra')
    def _compute_valor_opcion_compra(self):
        """Calcula el valor de la opción de compra"""
        for record in self:
            porcentaje = record.porcentaje_opcion_compra / 100.0
            record.valor_opcion_compra = record.costo_total_cop * porcentaje
    
    @api.depends('costo_total_cop', 'tasa_nominal', 'plazo_meses', 
                 'valor_opcion_compra', 'servicio_con_margen')
    def _compute_pago_mensual(self):
        """Calcula el pago mensual usando la función PMT"""
        for record in self:
            plazo = int(record.plazo_meses or 0) if record.plazo_meses else 0
            if plazo > 0:
                # Convertir tasa nominal a decimal mensual
                tasa_mensual_decimal = (record.tasa_nominal / 100.0) / 12.0
                
                # Calcular PMT (equivalente a función PMT de Excel)
                if tasa_mensual_decimal > 0:
                    factor = (1 + tasa_mensual_decimal) ** plazo
                    pago_base = (record.costo_total_cop * tasa_mensual_decimal * factor) / (factor - 1)
                    
                    # Ajustar por opción de compra (valor futuro)
                    if record.valor_opcion_compra > 0:
                        ajuste_opcion = (record.valor_opcion_compra * tasa_mensual_decimal) / (factor - 1)
                        pago_base = pago_base - ajuste_opcion
                else:
                    # Si tasa es 0, pago simple
                    pago_base = record.costo_total_cop / plazo
                
                # Sumar servicio con margen
                record.pago_mensual = pago_base + record.servicio_con_margen
            else:
                record.pago_mensual = 0.0
    
    @api.model
    def create(self, vals):
        """Sobrescribir create para cargar valores por defecto"""
        # Cargar parámetros por defecto si no se especifican
        parametros = self.env['calculadora.parametros.financieros'].search([], limit=1)
        if parametros:
            if 'trm' not in vals or not vals.get('trm'):
                vals['trm'] = parametros.trm_actual
            if 'porcentaje_utilidad' not in vals:
                vals['porcentaje_utilidad'] = parametros.porcentaje_utilidad_default
            if 'tasa_nominal' not in vals:
                vals['tasa_nominal'] = parametros.tasa_nominal_default
            if 'margen_servicio' not in vals:
                vals['margen_servicio'] = parametros.margen_servicio_default
        return super(CalculadoraEquipo, self).create(vals)
