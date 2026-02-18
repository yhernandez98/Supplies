# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError


class CalculadoraRenting(models.Model):
    _name = 'calculadora.renting'
    _description = 'Calculadora de Renting'
    _order = 'create_date desc'

    name = fields.Char(
        string='Nombre del Contrato',
        required=True,
        help='Nombre o descripción del contrato de renting'
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
        default=4000.0
    )
    
    costo_total_cop = fields.Float(
        string='Costo Total (COP)',
        compute='_compute_costo_total_cop',
        store=True
    )
    
    # Costos de Servicios
    costo_servicios_completos = fields.Float(
        string='Costo Servicios Completos',
        default=0.0
    )
    
    porcentaje_margen_servicio = fields.Float(
        string='Porcentaje Margen Servicio (%)',
        default=25.0,
        help='Porcentaje de margen aplicado a servicios (ej: 25 = 25%)'
    )
    
    servicio_con_margen = fields.Float(
        string='Servicio con Margen',
        compute='_compute_servicio_con_margen',
        store=True
    )
    
    # Parámetros Financieros
    tasa_nominal = fields.Float(
        string='Tasa Nominal (%)',
        default=21.0,
        required=True
    )
    
    tasa_efectiva_anual = fields.Float(
        string='Tasa Efectiva Anual (%)',
        compute='_compute_tasa_efectiva_anual',
        store=True
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
        default='48',
        required=True,
        help='Plazo del renting en meses (12, 24, 36, 48, 60)'
    )
    
    # Opción de Compra
    porcentaje_opcion_compra = fields.Float(
        string='Porcentaje Opción de Compra (%)',
        default=0.0,
        help='Porcentaje del valor del equipo para opción de compra'
    )
    
    valor_opcion_compra = fields.Float(
        string='Valor Opción de Compra (COP)',
        compute='_compute_valor_opcion_compra',
        store=True
    )
    
    # Pago Mensual
    pago_mensual = fields.Float(
        string='Pago Mensual (COP)',
        compute='_compute_pago_mensual',
        store=True
    )
    
    # Valores para diferentes plazos
    valor_24_meses = fields.Float(
        string='Valor 24 Meses',
        compute='_compute_valores_plazos',
        store=True
    )
    
    valor_36_meses = fields.Float(
        string='Valor 36 Meses',
        compute='_compute_valores_plazos',
        store=True
    )
    
    valor_48_meses = fields.Float(
        string='Valor 48 Meses',
        compute='_compute_valores_plazos',
        store=True
    )
    
    # Relación con Cliente y Suscripciones
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        help='Cliente asociado a esta calculadora de renting'
    )
    
    subscription_count = fields.Integer(
        string='Suscripciones Activas',
        compute='_compute_subscription_count',
        store=False,
        help='Cantidad de suscripciones no contables activas del cliente'
    )
    
    # Información adicional
    active = fields.Boolean(
        string='Activo',
        default=True
    )
    
    notas = fields.Text(
        string='Notas'
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
    @api.depends('valor_usd', 'valor_garantia_usd', 'porcentaje_utilidad', 'trm')
    def _compute_costo_total_cop(self):
        """Calcula el costo total en COP"""
        for record in self:
            costo_total_usd = record.valor_usd + record.valor_garantia_usd
            # Aplicar utilidad: Precio = Costo × (1 + Utilidad/100)
            factor_utilidad = 1 + (record.porcentaje_utilidad / 100.0)
            costo_con_utilidad = costo_total_usd * factor_utilidad
            record.costo_total_cop = costo_con_utilidad * record.trm
    
    @api.depends('costo_servicios_completos', 'porcentaje_margen_servicio')
    def _compute_servicio_con_margen(self):
        """Calcula el servicio con margen aplicado"""
        for record in self:
            # Aplicar margen: Precio = Costo × (1 + Margen/100)
            margen = 1 + (record.porcentaje_margen_servicio / 100.0)
            record.servicio_con_margen = record.costo_servicios_completos * margen
    
    @api.depends('tasa_nominal', 'plazo_meses')
    def _compute_tasa_efectiva_anual(self):
        """Calcula la tasa efectiva anual"""
        for record in self:
            plazo = int(record.plazo_meses or 0) if record.plazo_meses else 0
            if plazo > 0:
                tasa_mensual_decimal = (record.tasa_nominal / 100.0) / 12.0
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
        """Calcula el pago mensual"""
        for record in self:
            plazo = int(record.plazo_meses or 0) if record.plazo_meses else 0
            if plazo > 0:
                tasa_mensual_decimal = (record.tasa_nominal / 100.0) / 12.0
                
                if tasa_mensual_decimal > 0:
                    factor = (1 + tasa_mensual_decimal) ** plazo
                    pago_base = (record.costo_total_cop * tasa_mensual_decimal * factor) / (factor - 1)
                    
                    if record.valor_opcion_compra > 0:
                        ajuste_opcion = (record.valor_opcion_compra * tasa_mensual_decimal) / (factor - 1)
                        pago_base = pago_base - ajuste_opcion
                else:
                    pago_base = record.costo_total_cop / plazo
                
                record.pago_mensual = pago_base + record.servicio_con_margen
            else:
                record.pago_mensual = 0.0
    
    @api.depends('costo_total_cop', 'tasa_nominal', 'servicio_con_margen')
    def _compute_valores_plazos(self):
        """Calcula valores para diferentes plazos"""
        for record in self:
            # Calcular para 24 meses
            record.valor_24_meses = self._calcular_pago_plazo(record, 24)
            # Calcular para 36 meses
            record.valor_36_meses = self._calcular_pago_plazo(record, 36)
            # Calcular para 48 meses
            record.valor_48_meses = self._calcular_pago_plazo(record, 48)
    
    def _calcular_pago_plazo(self, record, plazo):
        """Método auxiliar para calcular pago en un plazo específico"""
        if plazo > 0:
            tasa_mensual_decimal = (record.tasa_nominal / 100.0) / 12.0
            
            if tasa_mensual_decimal > 0:
                factor = (1 + tasa_mensual_decimal) ** plazo
                pago_base = (record.costo_total_cop * tasa_mensual_decimal * factor) / (factor - 1)
                
                if record.valor_opcion_compra > 0:
                    ajuste_opcion = (record.valor_opcion_compra * tasa_mensual_decimal) / (factor - 1)
                    pago_base = pago_base - ajuste_opcion
            else:
                pago_base = record.costo_total_cop / plazo
            
            return pago_base + record.servicio_con_margen
        return 0.0
    
    @api.depends('partner_id')
    def _compute_subscription_count(self):
        """Calcula el número de suscripciones activas del cliente"""
        for record in self:
            if record.partner_id:
                # Verificar si el modelo subscription.subscription existe
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
        
        # Verificar si el modelo subscription.subscription existe
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
                vals['porcentaje_utilidad'] = 10.0  # 10% por defecto
            if 'tasa_nominal' not in vals:
                vals['tasa_nominal'] = parametros.tasa_nominal_default
        return super(CalculadoraRenting, self).create(vals)
