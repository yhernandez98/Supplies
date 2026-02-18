# -*- coding: utf-8 -*-

from odoo import models, fields, api


class APUServicio(models.Model):
    _name = 'apu.servicio'
    _description = 'Análisis de Precios Unitarios - Servicios'
    _order = 'name'

    name = fields.Char(
        string='Nombre del Servicio',
        required=True,
        help='Nombre del servicio o actividad'
    )
    
    # Parámetros de Vehículo
    costo_vehiculo = fields.Float(
        string='Costo del Vehículo',
        default=35000000.0,
        help='Costo inicial del vehículo'
    )
    
    años_depreciacion_vehiculo = fields.Integer(
        string='Años Depreciación Vehículo',
        default=7,
        help='Años de vida útil para depreciación'
    )
    
    costo_mantenimiento_vehiculo = fields.Float(
        string='Costo Mantenimiento Vehículo/Mes',
        default=350000.0,
        help='Costo mensual de mantenimiento del vehículo'
    )
    
    salario_conductor = fields.Float(
        string='Salario Conductor',
        default=1100000.0,
        help='Salario mensual del conductor'
    )
    
    factor_prestaciones_conductor = fields.Float(
        string='Factor Prestaciones Conductor',
        default=1.52,
        help='Factor de prestaciones sociales para conductor'
    )
    
    # Parámetros de Técnico
    salario_tecnico = fields.Float(
        string='Salario Técnico',
        default=1650000.0,
        help='Salario mensual del técnico'
    )
    
    factor_prestaciones_tecnico = fields.Float(
        string='Factor Prestaciones Técnico',
        default=1.55,
        help='Factor de prestaciones sociales para técnico'
    )
    
    # Parámetros de Internet
    costo_internet_claro = fields.Float(
        string='Costo Internet Claro/Mes',
        default=340000.0,
        help='Costo mensual de internet Claro'
    )
    
    costo_internet_etb = fields.Float(
        string='Costo Internet ETB/Mes',
        default=167000.0,
        help='Costo mensual de internet ETB'
    )
    
    # Parámetros de Infraestructura
    costo_infraestructura_total = fields.Float(
        string='Costo Infraestructura Total',
        default=3200000.0,
        help='Costo total de infraestructura (servidores, equipos, etc.)'
    )
    
    # Parámetros de Trabajo
    horas_trabajo_mes = fields.Integer(
        string='Horas de Trabajo por Mes',
        default=240,
        help='Número de horas de trabajo por mes'
    )
    
    dias_trabajo_mes = fields.Integer(
        string='Días de Trabajo por Mes',
        default=30,
        help='Número de días de trabajo por mes'
    )
    
    horas_trabajo_dia = fields.Integer(
        string='Horas de Trabajo por Día',
        default=8,
        help='Número de horas de trabajo por día'
    )
    
    # Costos Calculados por Hora
    costo_hora_vehiculo = fields.Float(
        string='Costo Hora Vehículo',
        compute='_compute_costo_hora_vehiculo',
        store=True,
        help='Costo por hora de uso del vehículo'
    )
    
    costo_hora_tecnico = fields.Float(
        string='Costo Hora Técnico',
        compute='_compute_costo_hora_tecnico',
        store=True,
        help='Costo por hora de trabajo técnico'
    )
    
    costo_hora_internet = fields.Float(
        string='Costo Hora Internet',
        compute='_compute_costo_hora_internet',
        store=True,
        help='Costo por hora de internet'
    )
    
    costo_hora_remoto = fields.Float(
        string='Costo Hora Soporte Remoto',
        compute='_compute_costo_hora_remoto',
        store=True,
        help='Costo por hora de soporte remoto'
    )
    
    # Costos de Actividades
    costo_alistamiento = fields.Float(
        string='Costo Alistamiento',
        compute='_compute_costo_alistamiento',
        store=True,
        help='Costo total de alistamiento'
    )
    
    costo_instalacion = fields.Float(
        string='Costo Instalación',
        compute='_compute_costo_instalacion',
        store=True,
        help='Costo total de instalación'
    )
    
    # Información adicional
    active = fields.Boolean(
        string='Activo',
        default=True
    )
    
    notas = fields.Text(
        string='Notas'
    )
    
    # Campo para moneda
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        default=lambda self: self.env.ref('base.COP', raise_if_not_found=False),
        required=True
    )
    
    # Métodos de cálculo
    @api.depends('costo_vehiculo', 'años_depreciacion_vehiculo', 
                 'costo_mantenimiento_vehiculo', 'salario_conductor',
                 'factor_prestaciones_conductor', 'horas_trabajo_dia',
                 'dias_trabajo_mes', 'horas_trabajo_mes')
    def _compute_costo_hora_vehiculo(self):
        """Calcula el costo por hora de vehículo"""
        for record in self:
            # Depreciación anual del vehículo
            if record.años_depreciacion_vehiculo > 0:
                depreciacion_anual = record.costo_vehiculo / record.años_depreciacion_vehiculo
                depreciacion_diaria = depreciacion_anual / 365
                depreciacion_hora = depreciacion_diaria / record.horas_trabajo_dia
            else:
                depreciacion_hora = 0
            
            # Mantenimiento por hora
            mantenimiento_diario = record.costo_mantenimiento_vehiculo / record.dias_trabajo_mes
            mantenimiento_hora = mantenimiento_diario / record.horas_trabajo_dia
            
            # Conductor por hora
            salario_con_prestaciones = record.salario_conductor * record.factor_prestaciones_conductor
            conductor_hora = salario_con_prestaciones / record.horas_trabajo_mes
            
            # Otros costos (camisa, dotación, carnet, combustible, parqueadero, seguro)
            # Simplificado: se puede agregar más detalle si es necesario
            otros_costos_hora = 0  # Se puede calcular más detalladamente
            
            record.costo_hora_vehiculo = (
                depreciacion_hora + 
                mantenimiento_hora + 
                conductor_hora + 
                otros_costos_hora
            )
    
    @api.depends('salario_tecnico', 'factor_prestaciones_tecnico', 
                 'horas_trabajo_mes')
    def _compute_costo_hora_tecnico(self):
        """Calcula el costo por hora de técnico"""
        for record in self:
            if record.horas_trabajo_mes > 0:
                salario_con_prestaciones = (
                    record.salario_tecnico * record.factor_prestaciones_tecnico
                )
                # Costo para 3 horas (como en el Excel)
                record.costo_hora_tecnico = (salario_con_prestaciones / record.horas_trabajo_mes) * 3
            else:
                record.costo_hora_tecnico = 0
    
    @api.depends('costo_internet_claro', 'costo_internet_etb', 
                 'dias_trabajo_mes', 'horas_trabajo_dia')
    def _compute_costo_hora_internet(self):
        """Calcula el costo por hora de internet"""
        for record in self:
            # Costo diario de internet
            costo_diario_claro = record.costo_internet_claro / record.dias_trabajo_mes
            costo_diario_etb = record.costo_internet_etb / record.dias_trabajo_mes
            
            # Costo por hora
            costo_hora_claro = costo_diario_claro / record.horas_trabajo_dia
            costo_hora_etb = costo_diario_etb / record.horas_trabajo_dia
            
            # Infraestructura por hora (simplificado)
            horas_mes_totales = record.dias_trabajo_mes * record.horas_trabajo_dia
            costo_infra_hora = record.costo_infraestructura_total / (horas_mes_totales * 60) / 3
            
            record.costo_hora_internet = costo_hora_claro + costo_hora_etb + costo_infra_hora
    
    @api.depends('costo_hora_tecnico', 'costo_hora_internet')
    def _compute_costo_hora_remoto(self):
        """Calcula el costo por hora de soporte remoto"""
        for record in self:
            # Costo técnico por hora (dividido entre 3)
            costo_tecnico_remoto = record.costo_hora_tecnico / 3
            
            # Otros costos (energía, espacio, PC, telefonía) - simplificado
            otros_costos = record.costo_hora_internet * 0.5  # Estimación
            
            record.costo_hora_remoto = costo_tecnico_remoto + otros_costos
    
    @api.depends('costo_hora_tecnico', 'costo_hora_internet')
    def _compute_costo_alistamiento(self):
        """Calcula el costo de alistamiento"""
        for record in self:
            # 3 horas técnico + consumo internet + orden entrega + entrega
            horas_tecnico = 3
            horas_internet = 36
            
            costo_tecnico = (record.costo_hora_tecnico / 3) * horas_tecnico
            costo_internet = record.costo_hora_internet * horas_internet
            
            # Costos fijos estimados (orden de entrega, entrega)
            costos_fijos = 50000  # Estimación
            
            record.costo_alistamiento = costo_tecnico + costo_internet + costos_fijos
    
    @api.depends('costo_hora_tecnico')
    def _compute_costo_instalacion(self):
        """Calcula el costo de instalación"""
        for record in self:
            # 3 horas técnico + orden de servicio
            horas_tecnico = 3
            costo_tecnico = (record.costo_hora_tecnico / 3) * horas_tecnico
            
            # Costo fijo estimado (orden de servicio)
            costo_fijo = 30000  # Estimación
            
            record.costo_instalacion = costo_tecnico + costo_fijo
    
    @api.model
    def create(self, vals):
        """Sobrescribir create para cargar valores por defecto"""
        parametros = self.env['calculadora.parametros.financieros'].search([], limit=1)
        if parametros:
            if 'horas_trabajo_mes' not in vals:
                vals['horas_trabajo_mes'] = parametros.horas_trabajo_mes_default
            if 'dias_trabajo_mes' not in vals:
                vals['dias_trabajo_mes'] = parametros.dias_trabajo_mes_default
            if 'horas_trabajo_dia' not in vals:
                vals['horas_trabajo_dia'] = parametros.horas_trabajo_mes_default
        return super(APUServicio, self).create(vals)
