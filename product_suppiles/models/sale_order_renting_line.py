# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleOrderRentingLine(models.Model):
    _name = "sale.order.renting.line"
    _description = "Sale Order Renting Line"
    _order = "id"

    order_id = fields.Many2one(
        "sale.order", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        related="order_id.company_id", store=True, readonly=True
    )
    currency_id = fields.Many2one(
        related="order_id.currency_id", store=True, readonly=True
    )

    product_id = fields.Many2one(
        "product.product", string="Producto", required=True,
        domain="[('sale_ok','=',True)]",
    )
    name = fields.Text(string="Descripción")
    product_uom = fields.Many2one(
        "uom.uom", string="UdM",
        domain=[],
    )
    product_uom_qty = fields.Float(string="Cantidad", default=1.0, digits="Product UoS")
    price_unit = fields.Monetary(string="Precio", default=0.0)

    line_type = fields.Selection(
        selection=[
            ("objective", "Objetivo"),
            ("component", "Componente"),
            ("peripheral", "Periférico"),
            ("complement", "Complemento"),
            ("monitor", "Monitores"),
            ("ups", "UPS"),
            ("extra", "Extra (facturable)"),
        ],
        string="Tipo",
        required=True,
        default="component",
    )

    is_auto = fields.Boolean(
        string="Generada automáticamente", default=False,
        help="Marcado por el wizard: objetivo/comp/perif/complementos generados."
    )

    billable = fields.Boolean(
        string="Facturable", default=False,
        help="Si está activo, esta línea generará/actualizará una línea comercial de la orden."
    )

    sale_line_id = fields.Many2one(
        "sale.order.line", string="Línea de venta vinculada", ondelete="set null"
    )

    @api.onchange("product_id")
    def _onchange_product_id_set_defaults(self):
        for r in self:
            if r.product_id:
                r.product_uom = r.product_id.uom_id
                r.name = r.product_id.get_product_multiline_description_sale()

    def _map_taxes(self, product):
        self.ensure_one()
        order = self.order_id
        taxes = product.taxes_id.filtered(lambda t: t.company_id == order.company_id)
        if order.fiscal_position_id:
            taxes = order.fiscal_position_id.map_tax(taxes, product, order.partner_id)
        return [(6, 0, taxes.ids)]

    def _prepare_sale_line_vals(self):
        self.ensure_one()
        product = self.product_id
        order = self.order_id
        if not product:
            raise UserError(_("Debes seleccionar un producto para facturar."))

        return {
            "order_id": order.id,
            "product_id": product.id,
            "name": self.name or product.get_product_multiline_description_sale(),
            "product_uom_qty": self.product_uom_qty or 1.0,
            "product_uom": self.product_uom.id or product.uom_id.id,
            "price_unit": self.price_unit or 0.0,
            "tax_id": self._map_taxes(product),
            "renting_line_id": self.id,
            "from_renting_extra": True,
        }

    def _sync_sale_line(self):
        for r in self:
            if r.is_auto:
                if r.sale_line_id:
                    r.sale_line_id.unlink()
                    r.sale_line_id = False
                continue

            if r.billable and (r.price_unit or 0) > 0:
                vals = r._prepare_sale_line_vals()
                if r.sale_line_id:
                    # actualizar
                    r.sale_line_id.write(vals)
                else:
                    sol = self.env["sale.order.line"].create(vals)
                    r.sale_line_id = sol.id
            else:
                if r.sale_line_id:
                    r.sale_line_id.unlink()
                    r.sale_line_id = False

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for r in records:
            r._sync_sale_line()
        return records

    def write(self, vals):
        res = super().write(vals)
        for r in self:
            r._sync_sale_line()
        return res

    def unlink(self):
        for r in self:
            if r.sale_line_id:
                r.sale_line_id.unlink()
        return super().unlink()
