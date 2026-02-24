# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class SaleOrder(models.Model):
    _inherit = "sale.order"

    renting_line_ids = fields.One2many(
        "sale.order.renting.line", "order_id",
        string="Líneas de Renting",
        help="Líneas de renting (objetivo, componentes, periféricos, complementos y extras).",
    )

    def action_confirm(self):
        res = super().action_confirm()
        self._create_renting_moves()
        # Agregar componentes relacionados para productos normales (no renting)
        self._explode_components_in_pickings()
        return res


    def _create_renting_moves(self):
        Picking = self.env["stock.picking"]
        Move = self.env["stock.move"]

        for order in self:
            # CORRECCIÓN: Validar que product_id y product_tmpl_id existen antes de acceder
            renting_parent_lines = order.order_line.filtered(
                lambda l: l.product_id and l.product_id.exists() and 
                         l.product_id.product_tmpl_id and 
                         getattr(l.product_id.product_tmpl_id, "product_renting", False)
            )
            if not renting_parent_lines:
                continue

            # CORRECCIÓN: Validar que warehouse_id existe antes de acceder
            if not order.warehouse_id or not order.warehouse_id.exists():
                raise UserError(_("La orden de venta no tiene almacén configurado."))
            picking_type = order.warehouse_id.out_type_id
            if not picking_type:
                raise UserError(_("No se encontró el tipo de operación de salida del almacén."))

            # CORRECCIÓN: Validar que partner_shipping_id existe antes de acceder
            if not order.partner_shipping_id or not order.partner_shipping_id.exists():
                raise UserError(_("La orden de venta no tiene dirección de envío configurada."))
            
            picking_vals = {
                "partner_id": order.partner_shipping_id.id,
                "picking_type_id": picking_type.id,
                "location_id": picking_type.default_location_src_id.id if picking_type.default_location_src_id else False,
                "location_dest_id": order.partner_shipping_id.property_stock_customer.id if order.partner_shipping_id.property_stock_customer else False,
                "origin": order.name,
                "sale_id": order.id,
                "company_id": order.company_id.id if order.company_id else False,
                "move_type": "direct",   
            }
            picking = Picking.create(picking_vals)

            def _create_move(product, qty, uom, supply_kind="parent", name=None, sale_line=None):
                vals = {
                    "name": name or product.display_name,
                    "product_id": product.id,
                    "product_uom": uom.id,
                    "product_uom_qty": qty,
                    "picking_id": picking.id,
                    "location_id": picking.location_id.id,
                    "location_dest_id": picking.location_dest_id.id,
                    "company_id": order.company_id.id,
                    "supply_kind": supply_kind,
                }
                if sale_line:
                    vals["sale_line_id"] = sale_line.id
                return Move.create(vals)

            for renting_line in renting_parent_lines:
                dst_tmpl = renting_line.renting_applies_to_tmpl_id
                if not dst_tmpl:
                    # CORRECCIÓN: Validar que order_id existe antes de acceder
                    if renting_line.order_id and renting_line.order_id.exists():
                        renting_obj = renting_line.order_id.renting_line_ids.filtered(lambda r: r.line_type == "objective")
                        if renting_obj and len(renting_obj) > 0:
                            # CORRECCIÓN: Validar que product_id y product_tmpl_id existen
                            if renting_obj[0].product_id and renting_obj[0].product_id.exists():
                                dst_tmpl = renting_obj[0].product_id.product_tmpl_id
                                if dst_tmpl and dst_tmpl.exists():
                                    renting_line.write({"renting_applies_to_tmpl_id": dst_tmpl.id})

                if not dst_tmpl or not dst_tmpl.exists():
                    raise UserError(_("Debes seleccionar el producto objetivo para el renting (línea: %s).") % renting_line.name)
                # CORRECCIÓN: Validar que product_variant_id existe antes de usar
                dst_prod = False
                if dst_tmpl.product_variant_id and dst_tmpl.product_variant_id.exists():
                    dst_prod = dst_tmpl.product_variant_id
                else:
                    dst_prod = self.env["product.product"].search(
                        [("product_tmpl_id", "=", dst_tmpl.id), ("sale_ok", "=", True)], limit=1
                    )
                if not dst_prod or not dst_prod.exists():
                    raise UserError(_("El producto objetivo '%s' no tiene variante vendible.") % (dst_tmpl.display_name,))

                qty = renting_line.product_uom_qty or 1.0
                # CORRECCIÓN: Validar que uom_id existe antes de acceder
                uom = dst_prod.uom_id if dst_prod.uom_id and dst_prod.uom_id.exists() else False
                if not uom:
                    raise UserError(_("El producto objetivo '%s' no tiene unidad de medida configurada.") % (dst_prod.display_name,))
                _create_move(
                    product=dst_prod,
                    qty=qty,
                    uom=uom,
                    supply_kind="parent",
                    name="%s (Objetivo Renting de %s)" % (dst_prod.display_name, renting_line.product_id.display_name if renting_line.product_id else ""),
                    sale_line=renting_line,  
                )       

                def _explode_one(exploded, kind):
                    for item in (exploded or []):
                        pr = item["product"]
                        pr_uom = item["uom"]
                        pr_qty = (item.get("qty") or 0.0) * qty
                        if pr_uom != pr.uom_id:
                            pr_qty = pr_uom._compute_quantity(pr_qty, pr.uom_id, rounding_method="HALF-UP")
                            pr_uom = pr.uom_id
                        _create_move(
                            product=pr,
                            qty=pr_qty,
                            uom=pr_uom,
                            supply_kind=kind,
                            name="%s (%s de %s)" % (pr.display_name, kind, dst_prod.display_name),
                            sale_line=renting_line,
                        )

                _explode_one(dst_tmpl._explode_components(1.0), "component")
                _explode_one(dst_tmpl._explode_peripherals(1.0), "peripheral")
                _explode_one(dst_tmpl._explode_complements(1.0), "complement")

            picking.action_confirm()
            # picking.action_assign()

    def _explode_components_in_pickings(self):
        """
        Marca los movimientos principales como "parent" pero NO crea movimientos para elementos asociados.
        Los elementos asociados se moverán automáticamente cuando se valide el picking
        a través del método _move_associated_lots_with_principal en stock_move_line.py.
        Esto evita errores de seriales duplicados y mantiene la consistencia con el disparador de rutas.
        """
        try:
            for order in self:
                # Buscar todos los pickings creados desde esta orden de venta
                pickings = self.env["stock.picking"].search([
                    ("sale_id", "=", order.id),
                    ("state", "in", ("draft", "waiting", "confirmed", "assigned")),
                ])
                
                if not pickings:
                    continue
                
                for picking in pickings:
                    try:
                        # Buscar movimientos padre (productos principales) que no sean de renting
                        # Los movimientos de renting ya fueron procesados en _create_renting_moves
                        # CORRECCIÓN: Validar que sale_line_id, product_id y product_tmpl_id existen antes de acceder
                        parent_moves = (getattr(picking, 'move_ids_without_package', None) or picking.move_ids).filtered(
                            lambda m: m.sale_line_id and m.sale_line_id.exists()
                            and m.sale_line_id.product_id and m.sale_line_id.product_id.exists()
                            and m.sale_line_id.product_id.product_tmpl_id
                            and not getattr(m.sale_line_id.product_id.product_tmpl_id, "product_renting", False)
                            and m.product_id and m.product_id.exists()
                            and m.product_id.product_tmpl_id
                            and (
                                getattr(m.product_id.product_tmpl_id, "is_composite", False)
                                or getattr(m.product_id.product_tmpl_id, "use_peripherals", False)
                                or getattr(m.product_id.product_tmpl_id, "use_complements", False)
                            )
                            and m.state in ("draft", "confirmed", "waiting", "assigned")
                            and (not hasattr(m, 'supply_kind') or not m.supply_kind or m.supply_kind == "parent")
                        )
                        
                        if not parent_moves:
                            continue
                        
                        # CORRECCIÓN CRÍTICA: Solo marcar los movimientos padre como "parent"
                        # NO crear movimientos para elementos asociados porque:
                        # 1. Se moverán automáticamente cuando se valide el picking
                        # 2. Evita errores de seriales duplicados
                        # 3. Mantiene consistencia con el disparador de rutas
                        # 4. La última operación solo mostrará productos principales
                        for parent_move in parent_moves:
                            if hasattr(parent_move, 'supply_kind') and not parent_move.supply_kind:
                                parent_move.write({"supply_kind": "parent"})
                    except Exception:
                        continue
        except Exception:
            pass


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    renting_applies_to_tmpl_id = fields.Many2one(
        "product.template",
        string="Aplica a (Renting)",
        help="Producto objetivo al que aplica este renting.",
        ondelete="restrict",
    )
    renting_parent_line_id = fields.Many2one(
        "sale.order.line",
        string="Línea Renting Padre",
        help="Si esta línea fue generada por Renting, referencia su línea origen.",
        ondelete="cascade",
        index=True,
    )
    renting_is_generated = fields.Boolean(
        string="Generada por Renting",
        help="Marcado automáticamente en las líneas logísticas generadas por Renting.",
        default=False,
        index=True,
    )
    is_renting_product = fields.Boolean(
        string="Es producto renting",
        related="product_id.product_tmpl_id.product_renting",
        store=False,
    )
    product_tmpl_id_rel = fields.Many2one(
        "product.template",
        string="Plantilla producto (renting)",
        related="product_id.product_tmpl_id",
        store=False,
    )

    renting_line_id = fields.Many2one(
        "sale.order.renting.line",
        string="Línea de Renting origen",
        help="Si esta línea fue creada/actualizada desde Renting, queda enlazada aquí."
    )
    from_renting_extra = fields.Boolean(
        string="Generada por Renting (extra)",
        help="Marcador para identificar la SOL creada por una línea de renting facturable."
    )

    @api.onchange("product_id")
    def _onchange_product_id_open_renting(self):
        for line in self:
            if not line.product_id:
                continue
            tmpl = line.product_id.product_tmpl_id
            if getattr(tmpl, "product_renting", False) and not line.renting_applies_to_tmpl_id:
                applicable = tmpl.renting_applicable_tmpl_ids
                if not applicable:
                    raise UserError(_("El producto Renting no tiene productos objetivo configurados."))
                return {
                    "type": "ir.actions.act_window",
                    "name": _("Aplicar Renting"),
                    "res_model": "sale.renting.apply.wizard",
                    "view_mode": "form",
                    "target": "new",
                    "context": {
                        "default_order_id": line.order_id.id,
                        "default_order_line_id": line.id,
                        "default_renting_src_tmpl_id": tmpl.id,
                    },
                }

    def _unlink_previous_generated_lines(self):
        gen_lines = self.env["sale.order.line"].search([
            ("renting_parent_line_id", "in", self.ids),
            ("renting_is_generated", "=", True),
        ])
        if gen_lines:
            gen_lines.unlink()

    def _create_generated_lines_for_renting(self):
        """
        Genera líneas logísticas (precio 0) del producto objetivo y su explosión
        de comp./perif./compl. Cantidad proporcional a la qty de la línea renting.
        """
        for line in self:
            if not line.product_id or not line.product_id.product_tmpl_id.product_renting:
                continue
            if not line.renting_applies_to_tmpl_id:
                raise UserError(_("Debe seleccionar el producto objetivo al que aplica el renting."))

            if line.state not in ("draft", "sent"):
                continue

            line._unlink_previous_generated_lines()

            order = line.order_id
            dst_tmpl = line.renting_applies_to_tmpl_id

            dst_product = dst_tmpl.product_variant_id if dst_tmpl.product_variant_id and dst_tmpl.product_variant_id.sale_ok else \
                self.env["product.product"].search([("product_tmpl_id", "=", dst_tmpl.id), ("sale_ok", "=", True)], limit=1)
            if not dst_product:
                raise UserError(_("El producto objetivo no tiene variantes vendibles."))

            qty = line.product_uom_qty
            uom_order = dst_product.uom_id

            parent_vals = {
                "order_id": order.id,
                "product_id": dst_product.id,
                "name": "%s (Objetivo de Renting: %s)" % (dst_product.display_name, line.product_id.display_name),
                "product_uom_qty": qty,
                "product_uom": uom_order.id,
                "price_unit": 0.0,
                "tax_id": [(6, 0, [])], 
                "renting_parent_line_id": line.id,
                "renting_is_generated": True,
            }
            self.env["sale.order.line"].create(parent_vals)

            def _explode(lines, factor_qty):
                out = []
                for item in lines or []:
                    pr = item["product"]
                    pr_uom = item["uom"]
                    pr_qty = (item["qty"] or 0.0) * factor_qty
                    if pr_uom != pr.uom_id:
                        pr_qty = pr_uom._compute_quantity(pr_qty, pr.uom_id, rounding_method="HALF-UP")
                        pr_uom = pr.uom_id
                    out.append((pr, pr_qty, pr_uom))
                return out

            exploded_components = dst_tmpl._explode_components(1.0) or []
            exploded_peripherals = dst_tmpl._explode_peripherals(1.0) or []
            exploded_complements = dst_tmpl._explode_complements(1.0) or []

            all_items = []
            all_items += _explode(exploded_components, qty)
            all_items += _explode(exploded_peripherals, qty)
            all_items += _explode(exploded_complements, qty)

            for pr, pr_qty, pr_uom in all_items:
                self.env["sale.order.line"].create({
                    "order_id": order.id,
                    "product_id": pr.id,
                    "name": "%s (Renting de %s → %s)" % (pr.display_name, line.product_id.display_name, dst_product.display_name),
                    "product_uom_qty": pr_qty,
                    "product_uom": pr_uom.id,
                    "price_unit": 0.0,
                    "tax_id": [(6, 0, [])],
                    "renting_parent_line_id": line.id,
                    "renting_is_generated": True,
                })

    @api.onchange("renting_applies_to_tmpl_id", "product_uom_qty")
    def _onchange_regenerate_generated_lines(self):
        for line in self:
            if (line.product_id and line.product_id.product_tmpl_id.product_renting
                and line.state in ("draft", "sent")
                and line.renting_applies_to_tmpl_id):
                line._create_generated_lines_for_renting()

    def write(self, vals):
        res = super().write(vals)
        for line in self:
            if line.state in ("draft", "sent") and line.product_id and line.product_id.product_tmpl_id.product_renting:
                if any(k in vals for k in ("renting_applies_to_tmpl_id", "product_uom_qty")):
                    line._create_generated_lines_for_renting()
        return res

    def unlink(self):
        renting_parents = self.filtered(lambda l: l.product_id and l.product_id.product_tmpl_id.product_renting and not l.renting_is_generated)
        if renting_parents:
            renting_parents._unlink_previous_generated_lines()
        return super().unlink()
