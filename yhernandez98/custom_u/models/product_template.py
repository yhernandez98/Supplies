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
    
    @api.constrains('tipo_producto', 'type')
    def _check_consistency(self):
        """Valida consistencia entre tipo_producto y type"""
        for product in self:
            if product.tipo_producto and product.type:
                expected_type = self._map_tipo_to_type(product.tipo_producto)
                if product.type != expected_type:
                    raise ValidationError(_(
                        'Los campos "Tipo de Producto" y "Tipo de Producto Nativo" deben ser consistentes. '
                        'Tipo de Producto: %s, Tipo esperado: %s'
                    ) % (product.tipo_producto, expected_type))
    
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
    
    # ========================================
    # MÉTODOS DE CREACIÓN Y ESCRITURA
    # ========================================
    
    @api.model_create_multi
    def create(self, vals_list):
        """Creación con sincronización automática"""
        for vals in vals_list:
            # Sincronizar tipo_producto -> type
            if 'tipo_producto' in vals and 'type' not in vals:
                vals['type'] = self._map_tipo_to_type(vals['tipo_producto'])
            # Sincronizar type -> tipo_producto
            elif 'type' in vals and 'tipo_producto' not in vals:
                vals['tipo_producto'] = self._map_type_to_tipo(vals['type'])
        return super().create(vals_list)
    
    def write(self, vals):
        """Escritura con sincronización automática"""
        # Sincronizar tipo_producto -> type
        if 'tipo_producto' in vals and 'type' not in vals:
            vals['type'] = self._map_tipo_to_type(vals['tipo_producto'])
        # Sincronizar type -> tipo_producto
        elif 'type' in vals and 'tipo_producto' not in vals:
            vals['tipo_producto'] = self._map_type_to_tipo(vals['type'])
        return super().write(vals)
    
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
    
