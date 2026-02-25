# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class PurchaseLineItemBuffer(models.Model):
    _name = "purchase.line.item.buffer"
    _description = "Buffer temporal de items por línea de compra"
    _order = "id desc"

    order_line_id = fields.Many2one("purchase.order.line", required=True, ondelete="cascade", index=True)
    product_tmpl_id = fields.Many2one("product.template", required=True, ondelete="cascade", index=True)
    line_ids = fields.One2many("purchase.line.item.buffer.line", "buffer_id", string="Líneas")
    finalized = fields.Boolean(string="Finalizado", help="Marcado cuando se procesó en la confirmación de OC.")

    def merge_into_product_template(self):

        for buf in self:
            tmpl = buf.product_tmpl_id

            comp_map = {l.component_product_id.id: l for l in tmpl.composite_line_ids}
            per_map  = {l.peripheral_product_id.id: l for l in tmpl.peripheral_line_ids}
            com_map  = {l.complement_product_id.id: l for l in tmpl.complement_line_ids}

            for bl in buf.line_ids:
                if bl.item_type == "component":
                    if bl.product_id.id in comp_map:
                        line = comp_map[bl.product_id.id]
                        line.component_qty += bl.quantity
                        if bl.uom_id and bl.uom_id != line.component_uom_id:
                            line.component_uom_id = bl.uom_id
                    else:
                        self.env["product.composite.line"].create({
                            "parent_product_tmpl_id": tmpl.id,
                            "component_product_id": bl.product_id.id,
                            "component_qty": bl.quantity,
                            "component_uom_id": bl.uom_id.id or bl.product_id.uom_id.id,
                        })
                elif bl.item_type == "peripheral":
                    if bl.product_id.id in per_map:
                        line = per_map[bl.product_id.id]
                        line.peripheral_qty += bl.quantity
                        if bl.uom_id and bl.uom_id != line.peripheral_uom_id:
                            line.peripheral_uom_id = bl.uom_id
                    else:
                        self.env["product.peripheral.line"].create({
                            "parent_product_tmpl_id": tmpl.id,
                            "peripheral_product_id": bl.product_id.id,
                            "peripheral_qty": bl.quantity,
                            "peripheral_uom_id": bl.uom_id.id or bl.product_id.uom_id.id,
                        })
                elif bl.item_type == "complement":
                    if bl.product_id.id in com_map:
                        line = com_map[bl.product_id.id]
                        line.complement_qty += bl.quantity
                        if bl.uom_id and bl.uom_id != line.complement_uom_id:
                            line.complement_uom_id = bl.uom_id
                    else:
                        self.env["product.complement.line"].create({
                            "parent_product_tmpl_id": tmpl.id,
                            "complement_product_id": bl.product_id.id,
                            "complement_qty": bl.quantity,
                            "complement_uom_id": bl.uom_id.id or bl.product_id.uom_id.id,
                        })
                elif bl.item_type in ("monitor", "ups"):
                    # Monitores y UPS se tratan como periféricos
                    if bl.product_id.id in per_map:
                        line = per_map[bl.product_id.id]
                        line.peripheral_qty += bl.quantity
                        if bl.uom_id and bl.uom_id != line.peripheral_uom_id:
                            line.peripheral_uom_id = bl.uom_id
                    else:
                        self.env["product.peripheral.line"].create({
                            "parent_product_tmpl_id": tmpl.id,
                            "peripheral_product_id": bl.product_id.id,
                            "peripheral_qty": bl.quantity,
                            "peripheral_uom_id": bl.uom_id.id or bl.product_id.uom_id.id,
                        })
                else:
                    raise ValidationError(_("Tipo inválido (component/peripheral/complement/monitor/ups)."))

            buf.finalized = True


class PurchaseLineItemBufferLine(models.Model):
    _name = "purchase.line.item.buffer.line"
    _description = "Línea de buffer (component/peripheral/complement)"
    _order = "id asc"

    buffer_id = fields.Many2one("purchase.line.item.buffer", required=True, ondelete="cascade")
    item_type = fields.Selection([("component", "Componente"),
                                  ("peripheral", "Periférico"),
                                  ("complement", "Complemento"),
                                  ("monitor", "Monitores"),
                                  ("ups", "UPS")],
                                 required=True)
    product_id = fields.Many2one("product.product", required=True,
                                 domain="[('type','in',('consu','product'))]")
    quantity = fields.Float(string="Cantidad", required=True, default=1.0, digits="Product Unit of Measure")
    uom_id = fields.Many2one(
        "uom.uom", string="Unidad",
        domain="[('category_id','=', product_id and product_id.uom_id and product_id.uom_id.category_id)]",
    )

    @api.onchange("product_id")
    def _onchange_product_set_uom(self):
        for l in self:
            if l.product_id and not l.uom_id:
                l.uom_id = l.product_id.uom_id
