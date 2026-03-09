# -*- coding: utf-8 -*-

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
        ('equipo', 'Equipo'),
        ('renting', 'Renting/Leasing')
    ], string='Tipo de Cálculo', default='equipo', required=True,
       help='Tipo de cálculo a realizar')
    
    # Relación con Cliente
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        help='Cliente asociado a este cálculo'
    )
    
    subscription_count = fields.Integer(
        string='Suscripciones Activas',
        compute='_compute_subscription_count',
        store=False,
        help='Cantidad de suscripciones no contables activas del cliente'
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
        help='Costo aplicando porcentaje de utilidad'
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
    
    porcentaje_margen_servicio = fields.Float(
        string='Porcentaje Margen Servicio (%)',
        default=15.0,
        help='Porcentaje de margen aplicado a servicios (ej: 15 = 15%, 25 = 25%)'
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
    
    plazo_meses = fields.Integer(
        string='Plazo (Meses)',
        default=24,
        required=True,
        help='Plazo del financiamiento en meses (24, 36, 48)'
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
    
    # Campo auxiliar para mostrar el costo del equipo sin servicios
    costo_equipo_cop = fields.Float(
        string='Costo Equipo (COP)',
        compute='_compute_costo_equipo_cop',
        store=True,
        help='Costo del equipo sin incluir servicios'
    )
    
    # Valores para diferentes plazos (solo para renting)
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
    
    # Total a Pagar
    total_pagar = fields.Float(
        string='Total a Pagar',
        compute='_compute_total_pagar',
        store=True,
        help='Total a pagar durante todo el plazo'
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
            factor_utilidad = 1 + (record.porcentaje_utilidad / 100.0)
            record.costo_con_utilidad_usd = record.costo_total_usd * factor_utilidad
    
    @api.depends('costo_con_utilidad_usd', 'trm')
    def _compute_costo_equipo_cop(self):
        """Calcula el costo del equipo en pesos colombianos (sin servicios)"""
        for record in self:
            record.costo_equipo_cop = record.costo_con_utilidad_usd * record.trm
    
    @api.depends('costo_equipo_cop', 'servicio_con_margen', 'plazo_meses')
    def _compute_costo_total_cop(self):
        """Calcula el costo total en pesos colombianos (equipo + servicios totales)"""
        for record in self:
            # Costo total de servicios durante todo el plazo
            costo_servicios_totales = record.servicio_con_margen * record.plazo_meses if record.plazo_meses > 0 else 0
            # Costo total = equipo + servicios totales
            record.costo_total_cop = record.costo_equipo_cop + costo_servicios_totales
    
    @api.depends('costo_servicios_completos', 'porcentaje_margen_servicio')
    def _compute_servicio_con_margen(self):
        """Calcula el servicio con margen aplicado"""
        for record in self:
            margen = 1 + (record.porcentaje_margen_servicio / 100.0)
            record.servicio_con_margen = record.costo_servicios_completos * margen
    
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
            if record.plazo_meses > 0:
                # Calcular con mayor precisión usando Decimal
                tasa_nominal_decimal = Decimal(str(record.tasa_nominal)) / Decimal('100')
                tasa_mensual_decimal = tasa_nominal_decimal / Decimal('12')
                uno_mas_tasa = Decimal('1') + tasa_mensual_decimal
                factor = uno_mas_tasa ** 12
                tasa_efectiva_decimal = factor - Decimal('1')
                record.tasa_efectiva_anual = float(tasa_efectiva_decimal * Decimal('100'))
            else:
                record.tasa_efectiva_anual = 0.0
    
    @api.depends('costo_equipo_cop', 'porcentaje_opcion_compra')
    def _compute_valor_opcion_compra(self):
        """Calcula el valor de la opción de compra (solo sobre el costo del equipo, no servicios)"""
        for record in self:
            # La opción de compra se calcula sobre el costo del equipo, no sobre servicios
            porcentaje = record.porcentaje_opcion_compra / 100.0
            record.valor_opcion_compra = record.costo_equipo_cop * porcentaje
    
    @api.depends('costo_equipo_cop', 'tasa_nominal', 'plazo_meses', 
                 'porcentaje_opcion_compra', 'servicio_con_margen')
    def _compute_pago_mensual(self):
        """
        Calcula el pago mensual usando la función PMT.
        Usa la misma lógica que _calcular_escenario y _calcular_pago_plazo para garantizar consistencia.
        """
        for record in self:
            if record.plazo_meses > 0:
                tasa_mensual_decimal = (record.tasa_nominal / 100.0) / 12.0
                
                if tasa_mensual_decimal > 0:
                    factor = (1 + tasa_mensual_decimal) ** record.plazo_meses
                    # Calcular pago base solo sobre el costo del equipo
                    pago_base = (record.costo_equipo_cop * tasa_mensual_decimal * factor) / (factor - 1)
                    
                    # Ajustar por opción de compra si aplica (misma lógica que _calcular_escenario)
                    if record.porcentaje_opcion_compra > 0:
                        porcentaje_opcion = record.porcentaje_opcion_compra / 100.0
                        valor_opcion = record.costo_equipo_cop * porcentaje_opcion
                        ajuste_opcion = (valor_opcion * tasa_mensual_decimal) / (factor - 1)
                        pago_base = pago_base - ajuste_opcion
                else:
                    pago_base = record.costo_equipo_cop / record.plazo_meses
                
                # Sumar el servicio mensual al pago base
                record.pago_mensual = pago_base + record.servicio_con_margen
            else:
                record.pago_mensual = 0.0
    
    @api.depends('costo_equipo_cop', 'tasa_nominal', 'servicio_con_margen', 'valor_opcion_compra')
    def _compute_valores_plazos(self):
        """Calcula valores para diferentes plazos (24, 36, 48 meses)"""
        for record in self:
            record.valor_24_meses = self._calcular_pago_plazo(record, 24)
            record.valor_36_meses = self._calcular_pago_plazo(record, 36)
            record.valor_48_meses = self._calcular_pago_plazo(record, 48)
    
    def _calcular_pago_plazo(self, record, plazo):
        """
        Método auxiliar para calcular pago en un plazo específico.
        Usa la misma lógica que _calcular_escenario para garantizar consistencia.
        """
        if plazo > 0:
            tasa_mensual_decimal = (record.tasa_nominal / 100.0) / 12.0
            
            if tasa_mensual_decimal > 0:
                factor = (1 + tasa_mensual_decimal) ** plazo
                # Calcular pago base solo sobre el costo del equipo
                pago_base = (record.costo_equipo_cop * tasa_mensual_decimal * factor) / (factor - 1)
                
                # Ajustar por opción de compra si aplica (misma lógica que _calcular_escenario)
                if record.porcentaje_opcion_compra > 0:
                    porcentaje_opcion = record.porcentaje_opcion_compra / 100.0
                    valor_opcion = record.costo_equipo_cop * porcentaje_opcion
                    ajuste_opcion = (valor_opcion * tasa_mensual_decimal) / (factor - 1)
                    pago_base = pago_base - ajuste_opcion
            else:
                pago_base = record.costo_equipo_cop / plazo
            
            # Sumar el servicio mensual al pago base
            return pago_base + record.servicio_con_margen
        return 0.0
    
    @api.depends('pago_mensual', 'plazo_meses')
    def _compute_total_pagar(self):
        """Calcula el total a pagar durante todo el plazo (solo cuotas mensuales)"""
        for record in self:
            # Total a pagar = suma de todas las cuotas mensuales
            # La opción de compra es un pago adicional opcional al final, no se incluye aquí
            record.total_pagar = record.pago_mensual * record.plazo_meses
    
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
    
    @api.model
    def create(self, vals):
        """Sobrescribir create para cargar valores por defecto"""
        parametros = self.env['calculadora.parametros.financieros'].search([], limit=1)
        if parametros:
            if 'trm' not in vals or not vals.get('trm'):
                vals['trm'] = parametros.trm_actual
            if 'porcentaje_utilidad' not in vals:
                vals['porcentaje_utilidad'] = parametros.porcentaje_utilidad_default
            if 'tasa_nominal' not in vals:
                vals['tasa_nominal'] = parametros.tasa_nominal_default
            if 'porcentaje_margen_servicio' not in vals:
                # Usar margen_servicio_default si existe, sino 15% por defecto
                if hasattr(parametros, 'margen_servicio_default'):
                    vals['porcentaje_margen_servicio'] = parametros.margen_servicio_default
                else:
                    vals['porcentaje_margen_servicio'] = 15.0
            # Ajustar valores por defecto según tipo
            if 'tipo_calculo' not in vals:
                vals['tipo_calculo'] = 'equipo'
            if vals.get('tipo_calculo') == 'renting':
                if 'plazo_meses' not in vals:
                    vals['plazo_meses'] = 48
                if 'porcentaje_opcion_compra' not in vals:
                    vals['porcentaje_opcion_compra'] = 0.0
                if 'porcentaje_margen_servicio' not in vals:
                    vals['porcentaje_margen_servicio'] = 25.0
            else:  # equipo
                if 'plazo_meses' not in vals:
                    vals['plazo_meses'] = 24
                if 'porcentaje_opcion_compra' not in vals:
                    vals['porcentaje_opcion_compra'] = 20.0
        return super(Calculadora, self).create(vals)
    
    def _calcular_escenario(self, incluir_seguro=True, incluir_servicios=True, plazo=None):
        """
        Calcula los valores para un escenario específico
        
        :param incluir_seguro: Si True, incluye la garantía extendida (seguro)
        :param incluir_servicios: Si True, incluye los servicios técnicos
        :param plazo: Plazo en meses (si None, usa el plazo_meses del registro)
        :return: Diccionario con los valores calculados
        """
        self.ensure_one()
        plazo_calc = plazo if plazo else self.plazo_meses
        
        # Calcular costo del equipo base (sin garantía)
        costo_equipo_base_usd = self.valor_usd
        if incluir_seguro:
            costo_equipo_base_usd += self.valor_garantia_usd
        
        # Aplicar utilidad
        costo_con_utilidad_usd = costo_equipo_base_usd * (1 + self.porcentaje_utilidad / 100.0)
        
        # Convertir a COP
        costo_equipo_cop = costo_con_utilidad_usd * self.trm
        
        # Calcular servicios
        servicio_mensual = 0.0
        if incluir_servicios:
            servicio_mensual = self.servicio_con_margen
        
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
        
        # Calcular valor del equipo sin garantía (siempre)
        valor_equipo_sin_garantia_cop = self.valor_usd * (1 + self.porcentaje_utilidad / 100.0) * self.trm
        
        # Calcular valor de garantía en COP si está incluida
        garantia_cop = 0.0
        if incluir_seguro and self.valor_garantia_usd > 0:
            garantia_cop = self.valor_garantia_usd * (1 + self.porcentaje_utilidad / 100.0) * self.trm
        
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
        los valores valor_24_meses, valor_36_meses, valor_48_meses mostrados en
        la interfaz web cuando el equipo tiene garantía configurada.
        
        :return: Diccionario con los 4 escenarios y sus valores para 24, 36 y 48 meses
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
            for plazo in [24, 36, 48]:
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
        if self.plazo_meses in [24, 36, 48]:
            escenario_1 = self.get_escenarios_resumen()['escenario_1']
            valor_plazo_escenario = escenario_1['plazos'][self.plazo_meses]['pago_mensual_total']
            diferencia = abs(self.pago_mensual - valor_plazo_escenario)
            
            if diferencia > 1.0:
                resultados['valido'] = False
                resultados['errores'].append(
                    f"pago_mensual ({self.pago_mensual:,.2f}) no coincide con "
                    f"Escenario 1 a {self.plazo_meses} meses ({valor_plazo_escenario:,.2f}). "
                    f"Diferencia: {diferencia:,.2f} COP"
                )
        
        return resultados
    
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