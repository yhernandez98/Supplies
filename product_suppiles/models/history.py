# -*- coding: utf-8 -*-
from odoo import api, fields, models

class SuppliesItemHistory(models.Model):
    _name = "supplies.item.history"
    _description = "Historial de compras de componentes/periféricos/complementos"
    _order = "purchase_date desc, id desc"

    item_type = fields.Selection(
        [("component", "Componente"), ("peripheral", "Periférico"), ("complement", "Complemento"), ("monitor", "Monitores"), ("ups", "UPS")],
        required=True,
    )
    parent_product_tmpl_id = fields.Many2one("product.template", string="Producto padre", required=True, index=True)
    product_id = fields.Many2one("product.product", string="Producto (línea)", required=True, index=True)
    purchase_id = fields.Many2one("purchase.order", string="Orden de Compra", required=True, index=True)
    purchase_line_id = fields.Many2one("purchase.order.line", string="Línea OC")
    vendor_id = fields.Many2one("res.partner", string="Proveedor", related="purchase_id.partner_id", store=True)
    company_id = fields.Many2one("res.company", string="Compañía", related="purchase_id.company_id", store=True)
    purchase_date = fields.Datetime(string="Fecha OC", related="purchase_id.date_approve", store=True)
    quantity = fields.Float(string="Cantidad", digits="Product Unit of Measure")
    uom_id = fields.Many2one("uom.uom", string="UoM")
    state = fields.Selection(related="purchase_id.state", store=True)
