# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class EquipmentChangeHistory(models.Model):
    _name = 'subscription.equipment.change.history'
    _description = 'Historial de Cambios de Equipo en Suscripciones'
    _order = 'change_date desc, id desc'
    _rec_name = 'change_date'

    subscription_id = fields.Many2one(
        'subscription.subscription',
        string='Suscripción',
        required=True,
        ondelete='cascade',
        index=True,
    )
    
    subscription_line_id = fields.Many2one(
        'subscription.subscription.line',
        string='Línea de Suscripción',
        readonly=True,
        help='Línea de suscripción donde se realizó el cambio',
    )
    
    change_date = fields.Datetime(
        string='Fecha del Cambio',
        required=True,
        default=fields.Datetime.now,
        index=True,
    )
    
    user_id = fields.Many2one(
        'res.users',
        string='Usuario',
        required=True,
        default=lambda self: self.env.user,
        readonly=True,
        help='Usuario que realizó el cambio',
    )
    
    # Equipo viejo
    old_equipment_lot_id = fields.Many2one(
        'stock.lot',
        string='Equipo Anterior',
        required=True,
        readonly=True,
        ondelete='restrict',
    )
    
    old_equipment_name = fields.Char(
        string='Nombre Equipo Anterior',
        readonly=True,
        help='Número de serie del equipo anterior',
    )
    
    old_equipment_inventory_plate = fields.Char(
        string='Placa Equipo Anterior',
        readonly=True,
        help='Placa de inventario del equipo anterior',
    )
    
    old_equipment_product_id = fields.Many2one(
        'product.product',
        string='Producto Equipo Anterior',
        readonly=True,
        help='Producto del equipo anterior',
    )
    
    # Equipo nuevo
    new_equipment_lot_id = fields.Many2one(
        'stock.lot',
        string='Equipo Nuevo',
        required=True,
        readonly=True,
        ondelete='restrict',
    )
    
    new_equipment_name = fields.Char(
        string='Nombre Equipo Nuevo',
        readonly=True,
        help='Número de serie del equipo nuevo',
    )
    
    new_equipment_inventory_plate = fields.Char(
        string='Placa Equipo Nuevo',
        readonly=True,
        help='Placa de inventario del equipo nuevo',
    )
    
    new_equipment_product_id = fields.Many2one(
        'product.product',
        string='Producto Equipo Nuevo',
        readonly=True,
        help='Producto del equipo nuevo',
    )
    
    # Información del cambio
    price_preserved = fields.Monetary(
        string='Precio Preservado',
        currency_field='currency_id',
        readonly=True,
        help='Precio de la suscripción que se preservó durante el cambio',
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        related='subscription_id.currency_id',
        string='Moneda',
        readonly=True,
        store=True,
    )
    
    notes = fields.Text(
        string='Notas',
        readonly=True,
        help='Notas adicionales sobre el cambio de equipo',
    )
    
    # Ubicaciones
    old_location_id = fields.Many2one(
        'stock.location',
        string='Ubicación Anterior',
        readonly=True,
        help='Ubicación del equipo anterior antes del cambio',
    )
    
    new_location_id = fields.Many2one(
        'stock.location',
        string='Ubicación Nueva',
        readonly=True,
        help='Ubicación del equipo nuevo después del cambio',
    )
    
    # Información adicional
    display_name = fields.Char(
        string='Descripción',
        compute='_compute_display_name',
        store=False,
    )
    
    @api.depends('change_date', 'old_equipment_inventory_plate', 'new_equipment_inventory_plate')
    def _compute_display_name(self):
        """Calcula el nombre a mostrar."""
        for record in self:
            old_plate = record.old_equipment_inventory_plate or record.old_equipment_name or 'N/A'
            new_plate = record.new_equipment_inventory_plate or record.new_equipment_name or 'N/A'
            date_str = fields.Datetime.to_string(record.change_date) if record.change_date else ''
            record.display_name = _('Cambio: %s → %s - %s') % (old_plate, new_plate, date_str)
    
    def name_get(self):
        """Personaliza el nombre mostrado."""
        result = []
        for record in self:
            result.append((record.id, record.display_name or _('Cambio de Equipo')))
        return result

