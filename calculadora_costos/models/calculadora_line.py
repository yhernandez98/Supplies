# -*- coding: utf-8 -*-

from odoo import models, fields, api


class CalculadoraCostosLine(models.Model):
    _name = 'calculadora.costos.line'
    _description = 'Línea de equipo en calculadora de costos'
    _order = 'sequence, id'

    calculadora_id = fields.Many2one(
        'calculadora.costos',
        string='Calculadora',
        required=True,
        ondelete='cascade'
    )
    sequence = fields.Integer(string='Secuencia', default=1)
    product_id = fields.Many2one(
        'product.product',
        string='Producto / Bien',
        help='Opcional: seleccione un producto del inventario. Si lo elige, se usará su nombre como equipo.'
    )
    name = fields.Char(
        string='Equipo',
        help='Nombre del equipo. Editable o se completa al elegir un producto.'
    )

    # Valores del equipo (según moneda del padre)
    valor_usd = fields.Float(
        string='Valor en USD',
        default=0.0,
        digits=(16, 0)
    )
    valor_garantia_usd = fields.Float(
        string='Garantía (USD)',
        default=0.0,
        digits=(16, 0)
    )
    valor_cop = fields.Float(
        string='Valor en COP',
        default=0.0,
        digits=(16, 0)
    )
    valor_garantia_cop = fields.Float(
        string='Garantía (COP)',
        default=0.0,
        digits=(16, 0)
    )

    costo_total_cop = fields.Float(
        string='Costo Total (COP)',
        compute='_compute_costo_total_cop',
        store=True,
        digits=(16, 0)
    )
    costo_equipo_cop = fields.Float(
        string='Costo Equipo (COP)',
        compute='_compute_costo_equipo_cop',
        store=True,
        digits=(16, 0)
    )

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.display_name or self.product_id.name

    @api.depends('valor_usd', 'valor_garantia_usd', 'valor_cop', 'valor_garantia_cop',
                 'calculadora_id.moneda_cotizacion', 'calculadora_id.porcentaje_utilidad', 'calculadora_id.trm')
    def _compute_costo_total_cop(self):
        for line in self:
            calc = line.calculadora_id
            if not calc:
                line.costo_total_cop = 0.0
                line.costo_equipo_cop = 0.0
                continue
            factor = 1 + (calc.porcentaje_utilidad / 100.0)
            if calc.moneda_cotizacion == 'usd':
                total_usd = line.valor_usd + line.valor_garantia_usd
                line.costo_total_cop = int(round(total_usd * factor * calc.trm, 0))
            else:
                total_cop = line.valor_cop + line.valor_garantia_cop
                line.costo_total_cop = int(round(total_cop * factor, 0))

    @api.depends('valor_usd', 'valor_garantia_usd', 'valor_cop', 'valor_garantia_cop',
                 'calculadora_id.moneda_cotizacion', 'calculadora_id.porcentaje_utilidad', 'calculadora_id.trm')
    def _compute_costo_equipo_cop(self):
        for line in self:
            calc = line.calculadora_id
            if not calc:
                line.costo_equipo_cop = 0.0
                continue
            factor = 1 + (calc.porcentaje_utilidad / 100.0)
            if calc.moneda_cotizacion == 'usd':
                line.costo_equipo_cop = int(round((line.valor_usd + line.valor_garantia_usd) * factor * calc.trm, 0))
            else:
                line.costo_equipo_cop = int(round((line.valor_cop + line.valor_garantia_cop) * factor, 0))
