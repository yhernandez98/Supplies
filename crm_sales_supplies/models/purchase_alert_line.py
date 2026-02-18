# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class PurchaseAlertLine(models.Model):
    """Línea de producto en una alerta de compra."""
    _name = 'purchase.alert.line'
    _description = 'Línea de Producto en Alerta de Compra'
    _order = 'sequence, id'

    alert_id = fields.Many2one(
        'purchase.alert',
        string='Alerta',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(
        string='Secuencia',
        default=10,
        help='Orden de visualización',
        index=True,
    )
    sale_order_line_id = fields.Many2one(
        'sale.order.line',
        string='Línea de Venta',
        readonly=True,
        ondelete='set null',
        help='Línea de venta relacionada',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        required=True,
        readonly=True,
    )
    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Plantilla de Producto',
        related='product_id.product_tmpl_id',
        readonly=True,
        store=True,
    )
    quantity_requested = fields.Float(
        string='Cantidad Solicitada',
        required=True,
        readonly=True,
        default=1.0,
    )
    quantity_available = fields.Float(
        string='Stock Disponible',
        compute='_compute_stock_info',
        readonly=True,
        store=False,
    )
    quantity_missing = fields.Float(
        string='Cantidad Faltante',
        compute='_compute_stock_info',
        readonly=True,
        store=False,
    )
    uom_id = fields.Many2one(
        'uom.uom',
        string='Unidad de Medida',
        related='product_id.uom_id',
        readonly=True,
        store=True,
    )

    @api.depends('product_id', 'quantity_requested', 'alert_id.warehouse_id')
    def _compute_stock_info(self):
        """Calcular stock disponible y cantidad faltante."""
        for line in self:
            if not line.product_id or not line.alert_id.warehouse_id:
                line.quantity_available = 0.0
                line.quantity_missing = line.quantity_requested or 0.0
                continue

            location = line.alert_id.warehouse_id.lot_stock_id
            try:
                # Usar sudo() para _gather y luego filtrar solo los accesibles
                all_quants = self.env['stock.quant'].sudo()._gather(
                    line.product_id,
                    location,
                )
                # Filtrar solo los quants que el usuario actual puede leer
                accessible_quants = self.env['stock.quant']
                for quant in all_quants:
                    try:
                        quant_check = self.env['stock.quant'].browse(quant.id)
                        if quant_check.exists():
                            accessible_quants |= quant_check
                    except Exception:
                        continue
                quantity_available = sum(accessible_quants.mapped('quantity'))
                line.quantity_available = quantity_available
            except Exception:
                line.quantity_available = line.product_id.qty_available or 0.0

            missing = max(0.0, (line.quantity_requested or 0.0) - line.quantity_available)
            line.quantity_missing = missing

    @api.model_create_multi
    def create(self, vals_list):
        """Sobrescribir creación para actualizar componentes de la alerta cuando hay múltiples productos."""
        lines = super().create(vals_list)
        
        # Agrupar por alerta para actualizar una vez por alerta
        alerts_to_update = {}
        for line in lines:
            if line.alert_id and line.alert_id.id not in alerts_to_update:
                alerts_to_update[line.alert_id.id] = line.alert_id
        
        # Actualizar componentes para cada alerta que tenga múltiples productos
        for alert in alerts_to_update.values():
            if len(alert.alert_line_ids) > 1:
                # Invalidar cache para asegurar que se leen las líneas actualizadas
                alert.invalidate_recordset(['alert_line_ids'])
                alert._update_component_lines()
        
        return lines

