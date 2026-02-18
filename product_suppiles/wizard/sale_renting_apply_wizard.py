# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class SaleRentingApplyWizard(models.TransientModel):
    _name = "sale.renting.apply.wizard"
    _description = "Aplicar Renting a Producto Objetivo"

    order_id = fields.Many2one("sale.order", required=True, ondelete="cascade")
    order_line_id = fields.Many2one("sale.order.line", required=True, ondelete="cascade")
    renting_src_tmpl_id = fields.Many2one("product.template", string="Producto Renting (Template)", required=True)
    # applies_to_tmpl_id = fields.Many2one(
    #     "product.template",
    #     string="Producto Objetivo",
    #     required=True,
    #     domain="[('id','in', renting_src_tmpl_id and renting_src_tmpl_id.renting_applicable_tmpl_ids.ids or [])]"
    # )
    applies_to_tmpl_id = fields.Many2one(
        "product.template",
        string="Producto Objetivo",
        required=True,
    )

    @api.onchange("renting_src_tmpl_id")
    def _onchange_renting_src_tmpl_id_set_domain(self):
        ids = []
        if self.renting_src_tmpl_id:
            ids = self.renting_src_tmpl_id.renting_applicable_tmpl_ids.ids
        if self.applies_to_tmpl_id and self.applies_to_tmpl_id.id not in ids:
            self.applies_to_tmpl_id = False
        return {"domain": {"applies_to_tmpl_id": [("id", "in", ids)]}}
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        line_id = self.env.context.get("default_order_line_id")
        if not line_id:
            return res

        line = self.env["sale.order.line"].browse(line_id)
        if not line or not line.product_id:
            return res

        tmpl = line.product_id.product_tmpl_id
        if not tmpl.product_renting:
            raise UserError(_("La línea seleccionada no es de un producto Renting."))

        res["renting_src_tmpl_id"] = tmpl.id

        if not tmpl.renting_applicable_tmpl_ids:
            raise UserError(_("No hay productos objetivo configurados para este Renting."))

        res.setdefault("applies_to_tmpl_id", tmpl.renting_applicable_tmpl_ids[:1].id)
        return res

    def action_confirm(self):
        self.ensure_one()
        if not self.order_line_id:
            raise UserError(_("No se encontró la línea de venta."))

        order = self.order_id
        sol = self.order_line_id
        dst_tmpl = self.applies_to_tmpl_id
        if not dst_tmpl:
            raise UserError(_("Debes seleccionar el producto objetivo."))

        sol.write({"renting_applies_to_tmpl_id": dst_tmpl.id})


        sol._unlink_previous_generated_lines()

        def _to_product(prod_or_tmpl):
            if not prod_or_tmpl:
                return False
            if getattr(prod_or_tmpl, "_name", "") == "product.template":
                return prod_or_tmpl.product_variant_id
            return prod_or_tmpl

        def _sale_desc(prod_or_tmpl):
            p = _to_product(prod_or_tmpl)
            p = p.with_context(lang=order.partner_id.lang) if order.partner_id else p
            return p.get_product_multiline_description_sale()

        qty_factor = sol.product_uom_qty or 1.0
        lines_to_create = []

        obj_prod = _to_product(dst_tmpl)
        lines_to_create.append({
            "order_id": order.id,
            "product_id": obj_prod.id,
            "name": _sale_desc(obj_prod),
            "product_uom": obj_prod.uom_id.id,
            "product_uom_qty": qty_factor,
            "price_unit": 0.0,
            "line_type": "objective",
            "is_auto": True,
            "billable": False,
        })

        def _push_exploded(exploded, kind):
            for item in (exploded or []):
                pr = item["product"]
                pr_uom = item["uom"]
                pr_qty = (item.get("qty") or 0.0) * qty_factor
                if pr_uom != pr.uom_id:
                    pr_qty = pr_uom._compute_quantity(pr_qty, pr.uom_id, rounding_method="HALF-UP")
                lines_to_create.append({
                    "order_id": order.id,
                    "product_id": pr.id,
                    "name": _sale_desc(pr),
                    "product_uom": pr.uom_id.id,
                    "product_uom_qty": pr_qty,
                    "price_unit": 0.0,
                    "line_type": kind, 
                    "is_auto": True,
                    "billable": False,
                })

        _push_exploded(dst_tmpl._explode_components(1.0), "component")
        _push_exploded(dst_tmpl._explode_peripherals(1.0), "peripheral")
        _push_exploded(dst_tmpl._explode_complements(1.0), "complement")

        if lines_to_create:
            self.env["sale.order.renting.line"].create(lines_to_create)

        return {"type": "ir.actions.act_window_close"}

