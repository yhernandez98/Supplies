# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # ========================================
    # CAMPOS PERSONALIZADOS
    # ========================================
    
    # Campo personalizado con opciones en español
    tipo_producto = fields.Selection(
        [
            ('consu', 'Bienes'),
            ('service', 'Servicio'),
            ('factura', 'Producto Facturable'),
        ],
        string='Tipo de Producto',
        required=True,
        default='consu',
        help='Define el tipo de producto según la clasificación interna'
    )
    
    # ========================================
    # CONSTRAINTS Y VALIDACIONES
    # ========================================
    
    @api.constrains('tipo_producto', 'type', 'detailed_type')
    def _check_consistency(self):
        """Valida consistencia entre tipo_producto y type"""
        for product in self:
            if product.tipo_producto and product.type:
                expected_type = self._map_tipo_to_type(product.tipo_producto)
                if product.type != expected_type:
                    raise ValidationError(_(
                        'Los campos "Tipo de Producto" y "Tipo de Producto Nativo" deben ser consistentes. '
                        'Tipo de Producto: %s, Tipo nativo actual: %s, Tipo esperado: %s'
                    ) % (product.tipo_producto, product.type, expected_type))
    
    # ========================================
    # MÉTODOS ONCHANGE (SINCRONIZACIÓN BIDIRECCIONAL)
    # ========================================
    
    @api.onchange('tipo_producto')
    def _onchange_tipo_producto(self):
        """Sincronizar tipo_producto con el campo nativo type"""
        if self.tipo_producto:
            self.type = self._map_tipo_to_type(self.tipo_producto)
    
    @api.onchange('type')
    def _onchange_type(self):
        """Sincronizar type con tipo_producto (sincronización inversa)"""
        if self.type:
            self.tipo_producto = self._map_type_to_tipo(self.type)

    @api.onchange('detailed_type')
    def _onchange_detailed_type(self):
        """Sincronizar detailed_type con tipo_producto cuando Odoo no envía type explícito."""
        if self.detailed_type:
            native_type = self._map_detailed_type_to_type(self.detailed_type)
            self.tipo_producto = self._map_type_to_tipo(native_type)
            self.type = native_type
    
    # ========================================
    # MÉTODOS DE CREACIÓN Y ESCRITURA
    # ========================================
    
    def _reconcile_vals_tipo_and_native(self, vals):
        """
        Sincroniza tipo_producto con type/detailed_type.
        Si vienen ambos (p. ej. default consu + type service desde XML de hr_expense),
        gana el tipo nativo de Odoo.
        """
        native = vals.get('type')
        if not native and vals.get('detailed_type'):
            native = self._map_detailed_type_to_type(vals['detailed_type'])
        if native:
            vals['type'] = native
            vals['tipo_producto'] = self._map_type_to_tipo(native)
            return
        if 'tipo_producto' in vals and 'type' not in vals and 'detailed_type' not in vals:
            vals['type'] = self._map_tipo_to_type(vals['tipo_producto'])

    @api.model_create_multi
    def create(self, vals_list):
        """Creación con sincronización automática"""
        for vals in vals_list:
            self._reconcile_vals_tipo_and_native(vals)
        records = super().create(vals_list)
        # Tras el core: a veces type queda en service y el default dejó consu.
        to_fix = records.filtered(
            lambda r: r.tipo_producto != self._map_type_to_tipo(r.type)
        )
        if to_fix:
            for rec in to_fix:
                rec.write({'tipo_producto': self._map_type_to_tipo(rec.type)})
        return records
    
    def write(self, vals):
        """Escritura con sincronización automática"""
        copy_vals = dict(vals)
        self._reconcile_vals_tipo_and_native(copy_vals)
        return super().write(copy_vals)
    
    # ========================================
    # MÉTODOS HELPER
    # ========================================
    
    def _map_tipo_to_type(self, tipo_producto):
        """Mapea tipo_producto a type nativo"""
        mapping = {
            'consu': 'consu',
            'service': 'service',
            'factura': 'product',
        }
        return mapping.get(tipo_producto, 'consu')
    
    def _map_type_to_tipo(self, type_value):
        """Mapea type nativo a tipo_producto"""
        mapping = {
            'consu': 'consu',
            'service': 'service',
            'product': 'factura',
        }
        return mapping.get(type_value, 'consu')

    def _map_detailed_type_to_type(self, detailed_type):
        """Normaliza detailed_type de Odoo a type nativo."""
        if detailed_type == 'service':
            return 'service'
        if detailed_type in ('consu', 'product'):
            return detailed_type
        # Fallback seguro para tipos extendidos
        return 'consu'
    
