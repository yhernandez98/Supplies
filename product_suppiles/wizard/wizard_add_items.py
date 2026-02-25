# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class PurchaseAddItemsWizard(models.TransientModel):
    _name = "purchase.add.items.wizard"
    _description = "Agregar Items a línea de compra (Componentes/Periféricos/Complementos)"

    order_line_id = fields.Many2one("purchase.order.line", required=True, ondelete="cascade")
    product_tmpl_id = fields.Many2one(related="order_line_id.product_id.product_tmpl_id", store=False, readonly=True)

    preview_product_component_lines = fields.One2many(
        "purchase.add.items.preview.line", "wizard_id", string="Componentes del producto",
        domain=[("item_type", "=", "component"), ("source", "=", "product")], readonly=True
    )
    preview_product_peripheral_lines = fields.One2many(
        "purchase.add.items.preview.line", "wizard_id", string="Periféricos del producto",
        domain=[("item_type", "=", "peripheral"), ("source", "=", "product")], readonly=True
    )
    preview_product_complement_lines = fields.One2many(
        "purchase.add.items.preview.line", "wizard_id", string="Complementos del producto",
        domain=[("item_type", "=", "complement"), ("source", "=", "product")], readonly=True
    )

    preview_buffer_component_lines = fields.One2many(
        "purchase.add.items.preview.line", "wizard_id", string="Componentes en esta compra",
        domain=[("item_type", "=", "component"), ("source", "=", "buffer")], readonly=True
    )
    preview_buffer_peripheral_lines = fields.One2many(
        "purchase.add.items.preview.line", "wizard_id", string="Periféricos en esta compra",
        domain=[("item_type", "=", "peripheral"), ("source", "=", "buffer")], readonly=True
    )
    preview_buffer_complement_lines = fields.One2many(
        "purchase.add.items.preview.line", "wizard_id", string="Complementos en esta compra",
        domain=[("item_type", "=", "complement"), ("source", "=", "buffer")], readonly=True
    )

    component_lines = fields.One2many(
        "purchase.add.items.wizard.line", "wizard_id",
        string="Agregar/editar Componentes", domain=[("item_type", "=", "component")]
    )
    peripheral_lines = fields.One2many(
        "purchase.add.items.wizard.line", "wizard_id",
        string="Agregar/editar Periféricos", domain=[("item_type", "=", "peripheral")]
    )
    complement_lines = fields.One2many(
        "purchase.add.items.wizard.line", "wizard_id",
        string="Agregar/editar Complementos", domain=[("item_type", "=", "complement")]
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        line_id = self.env.context.get("default_order_line_id")
        if not line_id:
            return res

        pol = self.env["purchase.order.line"].browse(line_id)
        tmpl = pol.product_id.product_tmpl_id

        prod_comp_vals = []
        for cl in tmpl.composite_line_ids:
            prod_comp_vals.append((0, 0, {
                "item_type": "component",
                "product_id": cl.component_product_id.id,
                "quantity": cl.component_qty,
                "uom_id": cl.component_uom_id.id or cl.component_product_id.uom_id.id,
                "source": "product",
            }))
        prod_per_vals = []
        for pl in tmpl.peripheral_line_ids:
            prod_per_vals.append((0, 0, {
                "item_type": "peripheral",
                "product_id": pl.peripheral_product_id.id,
                "quantity": pl.peripheral_qty,
                "uom_id": pl.peripheral_uom_id.id or pl.peripheral_product_id.uom_id.id,
                "source": "product",
            }))
        prod_com_vals = []
        for cm in tmpl.complement_line_ids:
            prod_com_vals.append((0, 0, {
                "item_type": "complement",
                "product_id": cm.complement_product_id.id,
                "quantity": cm.complement_qty,
                "uom_id": cm.complement_uom_id.id or cm.complement_product_id.uom_id.id,
                "source": "product",
            }))

        buf_comp_vals, buf_per_vals, buf_com_vals = [], [], []
        edit_comp_vals, edit_per_vals, edit_com_vals = [], [], []

        buffer = self.env["purchase.line.item.buffer"].search([("order_line_id", "=", pol.id)], limit=1)
        if buffer:
            for bl in buffer.line_ids:
                preview_val = (0, 0, {
                    "item_type": bl.item_type,
                    "product_id": bl.product_id.id,
                    "quantity": bl.quantity,
                    "uom_id": bl.uom_id.id or bl.product_id.uom_id.id,
                    "source": "buffer",
                })
                edit_val = (0, 0, {
                    "item_type": bl.item_type,
                    "product_id": bl.product_id.id,
                    "quantity": bl.quantity,
                    "uom_id": bl.uom_id.id or bl.product_id.uom_id.id,
                })
                if bl.item_type == "component":
                    buf_comp_vals.append(preview_val); edit_comp_vals.append(edit_val)
                elif bl.item_type == "peripheral":
                    buf_per_vals.append(preview_val); edit_per_vals.append(edit_val)
                else:
                    buf_com_vals.append(preview_val); edit_com_vals.append(edit_val)

        res.update({
            "preview_product_component_lines": prod_comp_vals,
            "preview_product_peripheral_lines": prod_per_vals,
            "preview_product_complement_lines": prod_com_vals,
            "preview_buffer_component_lines": buf_comp_vals,
            "preview_buffer_peripheral_lines": buf_per_vals,
            "preview_buffer_complement_lines": buf_com_vals,
            "component_lines": edit_comp_vals,
            "peripheral_lines": edit_per_vals,
            "complement_lines": edit_com_vals,
        })
        return res

    def _persist_buffer_lines(self, buffer, lines, item_type):
        BufferLine = self.env["purchase.line.item.buffer.line"]
        for l in lines:
            if l.product_id and l.quantity > 0:
                BufferLine.create({
                    "buffer_id": buffer.id,
                    "item_type": item_type,
                    "product_id": l.product_id.id,
                    "quantity": l.quantity,
                    "uom_id": l.uom_id.id if l.uom_id else l.product_id.uom_id.id,
                })

    def action_confirm(self):
        self.ensure_one()
        if not self.order_line_id:
            raise UserError(_("Faltan datos de la línea de compra."))

        buffer = self.env["purchase.line.item.buffer"].search(
            [("order_line_id", "=", self.order_line_id.id)], limit=1
        )
        if not buffer:
            buffer = self.env["purchase.line.item.buffer"].create({
                "order_line_id": self.order_line_id.id,
                "product_tmpl_id": self.product_tmpl_id.id,
            })
        else:
            buffer.line_ids.unlink()

        self._persist_buffer_lines(buffer, self.component_lines, "component")
        self._persist_buffer_lines(buffer, self.peripheral_lines, "peripheral")
        self._persist_buffer_lines(buffer, self.complement_lines, "complement")

        return {"type": "ir.actions.act_window_close"}


class PurchaseAddItemsWizardLine(models.TransientModel):
    _name = "purchase.add.items.wizard.line"
    _description = "Línea wizard agregar items"

    wizard_id = fields.Many2one("purchase.add.items.wizard", required=True, ondelete="cascade")
    item_type = fields.Selection(
        [("component", "Componente"), ("peripheral", "Periférico"), ("complement", "Complemento"), ("monitor", "Monitores"), ("ups", "UPS")],
        required=True, default="component"
    )

    product_id = fields.Many2one(
        "product.product", required=True,
        domain="[('type','in',('consu','product')),"
               " ('classification','=', item_type=='component' and 'component' or item_type=='peripheral' and 'peripheral' or item_type=='complement' and 'complement' or item_type=='monitor' and 'monitor' or item_type=='ups' and 'ups')]"
    )
    quantity = fields.Float(string="Cantidad", required=True, default=1.0, digits="Product Unit of Measure")
    uom_id = fields.Many2one(
        "uom.uom", string="Unidad",
        domain=[],
    )

    @api.onchange("product_id")
    def _onchange_product(self):
        for l in self:
            if l.product_id and not l.uom_id:
                l.uom_id = l.product_id.uom_id


class PurchaseAddItemsPreviewLine(models.TransientModel):
    _name = "purchase.add.items.preview.line"
    _description = "Vista previa de items (producto/buffer) - solo lectura"

    wizard_id = fields.Many2one("purchase.add.items.wizard", required=True, ondelete="cascade")
    item_type = fields.Selection([("component", "Componente"), ("peripheral", "Periférico"), ("complement", "Complemento"), ("monitor", "Monitores"), ("ups", "UPS")], required=True)
    product_id = fields.Many2one("product.product", required=True, readonly=True)
    quantity = fields.Float(string="Cantidad", required=True, readonly=True)
    uom_id = fields.Many2one("uom.uom", string="Unidad", readonly=True)
    source = fields.Selection([("product", "Producto"), ("buffer", "Esta compra")], required=True, readonly=True)
