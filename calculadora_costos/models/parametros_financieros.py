# -*- coding: utf-8 -*-

from odoo import models, fields, api
from decimal import Decimal, getcontext

# Configurar precisión para cálculos financieros
getcontext().prec = 10


class ParametrosFinancieros(models.Model):
    _name = 'calculadora.parametros.financieros'
    _description = 'Parámetros Financieros Globales'
    _rec_name = 'name'

    name = fields.Char(
        string='Nombre',
        default='Parámetros Financieros',
        required=True
    )
    
    # Parámetros de Moneda
    trm_actual = fields.Float(
        string='TRM Actual (COP/USD)',
        default=4000.0,
        required=True,
        digits=(16, 0),
        help='Tasa Representativa del Mercado actual'
    )
    
    # Parámetros de Utilidad
    porcentaje_utilidad_default = fields.Float(
        string='Porcentaje de Utilidad por Defecto (%)',
        default=10.0,
        required=True,
        digits=(16, 0),
        help='Porcentaje de utilidad aplicado sobre el costo (ej: 10 = 10%, 20 = 20%)'
    )
    
    # Parámetros de Interés
    tasa_nominal_default = fields.Float(
        string='Tasa Nominal por Defecto (%)',
        default=21.0,
        required=True,
        digits=(16, 0),
        help='Tasa de interés nominal anual en porcentaje (ej: 21 = 21%)'
    )
    
    # Parámetros de Servicios
    margen_servicio_default = fields.Float(
        string='Margen de Servicio por Defecto (%)',
        default=15.0,
        required=True,
        digits=(16, 0),
        help='Margen aplicado a servicios técnicos en porcentaje'
    )
    
    # Parámetros de Trabajo
    horas_trabajo_mes_default = fields.Integer(
        string='Horas de Trabajo por Mes',
        default=240,
        required=True,
        help='Número de horas de trabajo por mes'
    )
    
    dias_trabajo_mes_default = fields.Integer(
        string='Días de Trabajo por Mes',
        default=30,
        required=True,
        help='Número de días de trabajo por mes'
    )
    
    horas_trabajo_dia_default = fields.Integer(
        string='Horas de Trabajo por Día',
        default=8,
        required=True,
        help='Número de horas de trabajo por día'
    )
    
    # Parámetros de Depreciación
    anos_depreciacion_vehiculo = fields.Integer(
        string='Años de Depreciación',
        default=7,
        required=True,
        help='Años de vida útil para depreciación'
    )
    
    # Métodos de cálculo
    @api.model
    def get_trm_actual(self):
        """Obtiene la TRM actual"""
        parametros = self.search([], limit=1)
        if parametros:
            return parametros.trm_actual
        return 4000.0
    
    @api.model
    def get_tasa_nominal_default(self):
        """Obtiene la tasa nominal por defecto"""
        parametros = self.search([], limit=1)
        if parametros:
            return parametros.tasa_nominal_default / 100.0
        return 0.21
    
    @api.model
    def get_porcentaje_utilidad_default(self):
        """Obtiene el porcentaje de utilidad por defecto"""
        parametros = self.search([], limit=1)
        if parametros:
            return parametros.porcentaje_utilidad_default
        return 10.0
    
    @api.model
    def get_margen_servicio_default(self):
        """Obtiene el margen de servicio por defecto"""
        parametros = self.search([], limit=1)
        if parametros:
            return parametros.margen_servicio_default / 100.0
        return 0.15
    
    _sql_constraints = [
        ('unique_parametros', 'UNIQUE(name)',
         'Solo puede existir un registro de parámetros financieros'),
    ]
