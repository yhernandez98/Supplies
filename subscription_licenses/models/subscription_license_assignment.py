# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SubscriptionLicenseAssignment(models.Model):
    """Modelo para asignar licencias a clientes, equipos y suscripciones.
    
    Optimizado para manejar grandes volúmenes de registros (1000+ licencias).
    """
    _name = 'subscription.license.assignment'
    _description = 'Asignación de Licencia'
    _order = 'subscription_id, license_type_id, id'
    _rec_name = 'display_name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    subscription_id = fields.Many2one('subscription.subscription', string='Suscripción', required=True, ondelete='cascade', index=True)
    partner_id = fields.Many2one('res.partner', string='Cliente', related='subscription_id.partner_id', store=True, readonly=True, index=True)
    license_type_id = fields.Many2one('product.license.type', string='Tipo de Licencia', required=True, index=True)
    license_code = fields.Char(string='Código', related='license_type_id.code', store=True, readonly=True, index=True)
    quantity = fields.Integer(string='Cantidad', required=True, default=1)
    price_usd = fields.Float(string='Precio USD', related='license_type_id.price_usd', store=True, readonly=True, digits=(16, 2))
    
    # TRM y conversión
    trm_rate = fields.Float(string='TRM', compute='_compute_trm_and_amounts', store=True, digits=(16, 2))
    amount_usd = fields.Monetary(string='Valor USD', compute='_compute_trm_and_amounts', store=True, currency_field='usd_currency_id')
    amount_local = fields.Monetary(string='Valor Total', compute='_compute_trm_and_amounts', store=True, currency_field='currency_id')
    usd_currency_id = fields.Many2one('res.currency', string='Moneda USD', compute='_compute_usd_currency', store=False)
    
    @api.depends()
    def _compute_usd_currency(self):
        usd = self.env.ref('base.USD', raise_if_not_found=False)
        for rec in self:
            rec.usd_currency_id = usd.id if usd else False
    
    currency_id = fields.Many2one('res.currency', string='Moneda Local', related='subscription_id.currency_id', store=True, readonly=True)
    
    # Asociación con equipos (opcional) - importante para rastrear quién tiene qué
    equipment_lot_id = fields.Many2one('stock.lot', string='Equipo (Serie)', help='Equipo al que está asignada la licencia', index=True)
    equipment_product_id = fields.Many2one('product.product', string='Producto Equipo', help='Producto del equipo', index=True)
    
    # Fechas
    start_date = fields.Date(string='Fecha Inicio', default=fields.Date.today, index=True)
    end_date = fields.Date(string='Fecha Fin', index=True)
    active = fields.Boolean(string='Activo', default=True, index=True)
    
    # Campos para búsqueda y filtrado
    display_name = fields.Char(string='Nombre', compute='_compute_display_name', store=True, index=True)
    
    # Notas
    notes = fields.Text(string='Notas', help='Información adicional sobre la asignación de la licencia')

    @api.depends('license_type_id', 'quantity', 'subscription_id')
    def _compute_display_name(self):
        for rec in self:
            if rec.license_type_id:
                rec.display_name = f"{rec.license_type_id.name} - Qty: {rec.quantity}"
            else:
                rec.display_name = _('Nueva Licencia')

    @api.depends('quantity', 'price_usd', 'subscription_id', 'start_date', 'license_type_id')
    def _compute_trm_and_amounts(self):
        ExchangeRate = self.env['exchange.rate.monthly']
        for rec in self:
            if not rec.subscription_id or not rec.price_usd:
                rec.trm_rate = 0.0
                rec.amount_usd = 0.0
                rec.amount_local = 0.0
                continue
            
            # Obtener TRM para la fecha de inicio o fecha actual
            date_for_trm = rec.start_date or fields.Date.today()
            company_id = rec.subscription_id.company_id.id if rec.subscription_id.company_id else False
            trm = ExchangeRate.get_rate_for_date(date_for_trm, company_id)
            rec.trm_rate = trm
            
            # Calcular montos
            rec.amount_usd = rec.price_usd * rec.quantity
            rec.amount_local = rec.amount_usd * trm if trm > 0 else 0.0

    @api.onchange('equipment_lot_id')
    def _onchange_equipment_lot_id(self):
        """Actualiza el producto del equipo cuando se selecciona un lote."""
        for rec in self:
            if rec.equipment_lot_id and rec.equipment_lot_id.product_id:
                rec.equipment_product_id = rec.equipment_lot_id.product_id

    @api.constrains('quantity')
    def _check_quantity(self):
        """Valida que la cantidad sea positiva."""
        for rec in self:
            if rec.quantity <= 0:
                raise ValidationError(_('La cantidad debe ser mayor a cero.'))

    def name_get(self):
        """Mejora el nombre mostrado para búsquedas."""
        result = []
        for rec in self:
            name = rec.display_name or _('Nueva Licencia')
            if rec.partner_id:
                name = f"{rec.partner_id.name} - {name}"
            if rec.equipment_lot_id:
                name = f"{name} [{rec.equipment_lot_id.name}]"
            result.append((rec.id, name))
        return result

