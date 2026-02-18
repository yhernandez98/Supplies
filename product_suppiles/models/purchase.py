# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.tools.float_utils import float_is_zero

class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    _open_wizard_pending = fields.Boolean(default=False)

    def action_open_add_items_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Agregar Items (Comp./Perif./Compl.)"),
            "res_model": "purchase.add.items.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_order_line_id": self.id},
        }

    @api.onchange("product_id")
    def _onchange_product_id_open_wizard(self):
        for line in self:
            if line.product_id:
                line._open_wizard_pending = True
                return {
                    "type": "ir.actions.act_window",
                    "name": _("Agregar Items (Comp./Perif./Compl.)"),
                    "res_model": "purchase.add.items.wizard",
                    "view_mode": "form",
                    "target": "new",
                    "context": {"default_order_line_id": line.id},
                }

    def unlink(self):
        buffers = self.env["purchase.line.item.buffer"].search([("order_line_id", "in", self.ids)])
        buffers.unlink()
        return super().unlink()
    
    def copy(self, default=None):
        """Copiar la línea de compra y su buffer de relaciones."""
        new_line = super().copy(default=default)
        
        # Copiar el buffer si existe
        old_buffer = self.env["purchase.line.item.buffer"].search(
            [("order_line_id", "=", self.id)], limit=1
        )
        
        if old_buffer and old_buffer.line_ids:
            new_buffer = self.env["purchase.line.item.buffer"].create({
                "order_line_id": new_line.id,
                "product_tmpl_id": old_buffer.product_tmpl_id.id,
            })
            
            for old_line in old_buffer.line_ids:
                self.env["purchase.line.item.buffer.line"].create({
                    "buffer_id": new_buffer.id,
                    "item_type": old_line.item_type,
                    "product_id": old_line.product_id.id,
                    "quantity": old_line.quantity,
                    "uom_id": old_line.uom_id.id if old_line.uom_id else old_line.product_id.uom_id.id,
                })
        
        return new_line
    
    def _prepare_stock_moves(self, picking):
        self.ensure_one()
        res = super()._prepare_stock_moves(picking)
        if not res:
            return res

        product = self.product_id
        tmpl = product.product_tmpl_id
        is_incoming = bool(picking.picking_type_id and picking.picking_type_id.code == "incoming")

        if not (
            is_incoming
            and (
                getattr(tmpl, "use_components", False)
                or getattr(tmpl, "use_peripherals", False)
                or getattr(tmpl, "use_complements", False)
                or getattr(tmpl, "is_composite", False)
            )
        ):
            return res

        base_vals = res[0].copy()
        base_qty = base_vals.get("product_uom_qty", 0.0)
        base_uom = self.product_uom
        base_price_unit = base_vals.get("price_unit", 0.0)

        if float_is_zero(base_qty, precision_rounding=base_uom.rounding):
            return res

        # PRIORIDAD: Usar relaciones del buffer si existen, sino usar las del template
        # Esto asegura que las relaciones definidas en la compra se respeten
        buffer = self.env["purchase.line.item.buffer"].search(
            [("order_line_id", "=", self.id)], limit=1
        )
        
        exploded_components = []
        exploded_peripherals = []
        exploded_complements = []
        
        if buffer and buffer.line_ids:
            # Usar relaciones del buffer (definidas en esta compra específica)
            # Convertir base_qty a la UOM base del template para multiplicar correctamente
            qty_in_base = base_qty
            if base_uom != tmpl.uom_id:
                qty_in_base = base_uom._compute_quantity(base_qty, tmpl.uom_id, rounding_method="HALF-UP")
            
            for bl in buffer.line_ids:
                # bl.quantity es la cantidad por unidad del producto principal (igual que component_qty en template)
                comp_uom = bl.uom_id or bl.product_id.uom_id
                comp_qty_base = bl.quantity * qty_in_base
                # Convertir a la UOM del componente
                comp_qty = tmpl.uom_id._compute_quantity(comp_qty_base, comp_uom, rounding_method="HALF-UP")
                
                item = {
                    "product": bl.product_id,
                    "qty": comp_qty,
                    "uom": comp_uom,
                }
                if bl.item_type == "component":
                    exploded_components.append(item)
                elif bl.item_type == "peripheral":
                    exploded_peripherals.append(item)
                elif bl.item_type == "complement":
                    exploded_complements.append(item)
                elif bl.item_type in ("monitor", "ups"):
                    # Monitores y UPS se tratan como periféricos
                    exploded_peripherals.append(item)
        else:
            # Usar relaciones del template (comportamiento original)
            exploded_components = tmpl._explode_components(base_qty, uom=base_uom) or []
            exploded_peripherals = tmpl._explode_peripherals(base_qty, uom=base_uom) or []
            exploded_complements = tmpl._explode_complements(base_qty, uom=base_uom) or []

        if not exploded_components and not exploded_peripherals and not exploded_complements:
            return res

        exploded_all = []
        for item in exploded_components or []:
            exploded_all.append({**item, "kind": "component"})
        for item in exploded_peripherals or []:
            exploded_all.append({**item, "kind": "peripheral"})
        for item in exploded_complements or []:
            exploded_all.append({**item, "kind": "complement"})

        method = getattr(tmpl, "component_cost_method", "std_prorata") or "std_prorata"

        total_base = 0.0
        if method == "std_prorata":
            for item in exploded_all:
                comp = item["product"]
                qty = item.get("qty") or 0.0
                total_base += (comp.standard_price or 0.0) * qty

        move_lines = []

        count = len(exploded_all) or 1
        for item in exploded_all:
            comp = item["product"]
            comp_qty = item["qty"]
            comp_uom = item["uom"]

            # Política de valoración del padre
            if getattr(tmpl, "receive_parent_stock", False) and getattr(tmpl, "parent_valuation_policy", "none") == "full":
                price_unit_item = 0.0
            else:
                if method == "equal":
                    price_unit_item = base_price_unit / count
                else:
                    base = (comp.standard_price or 0.0) * (comp_qty or 0.0)
                    price_unit_item = base_price_unit * (base / total_base) if total_base else (base_price_unit / count)

            vals = base_vals.copy()
            vals.update({
                "name": f"{base_vals.get('name') or product.display_name} - {comp.display_name}",
                "product_id": comp.id,
                "product_uom": comp_uom.id,
                "product_uom_qty": comp_qty,
                "price_unit": price_unit_item,
                "purchase_line_id": self.id,
                "supply_kind": item["kind"],
            })
            move_lines.append(vals)

        if getattr(tmpl, "receive_parent_stock", False):
            parent_price = 0.0 if getattr(tmpl, "parent_valuation_policy", "none") == "none" else base_price_unit
            parent_vals = base_vals.copy()
            parent_vals.update({
                "name": base_vals.get("name") or product.display_name,
                "product_id": product.id,
                "product_uom": base_uom.id,
                "product_uom_qty": base_qty,
                "price_unit": parent_price,
                "purchase_line_id": self.id,
                "supply_kind": "parent",
            })
            move_lines.append(parent_vals)

        return move_lines

class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def _log_supplies_history_from_buffer(self, buffers):
        """Crea registros en el historial por cada línea del buffer."""
        History = self.env["supplies.item.history"]
        for buf in buffers:
            tmpl = buf.product_tmpl_id
            for bl in buf.line_ids:
                History.create({
                    "item_type": bl.item_type,
                    "parent_product_tmpl_id": tmpl.id,
                    "product_id": bl.product_id.id,
                    "purchase_id": self.id,
                    "purchase_line_id": buf.order_line_id.id,
                    "quantity": bl.quantity,
                    "uom_id": bl.uom_id.id,
                })

    def button_confirm(self):
        buffers = self.env["purchase.line.item.buffer"].search([("order_line_id", "in", self.order_line.ids)])
        for buf in buffers:
            buf.merge_into_product_template()

        res = super().button_confirm()

        if self.state in ("purchase", "done"):
            self._log_supplies_history_from_buffer(buffers)

        return res
    
    def copy(self, default=None):
        """Copiar la orden de compra y sus buffers de relaciones."""
        new_order = super().copy(default=default)
        
        # Mapear líneas antiguas a nuevas por producto y cantidad
        old_to_new_lines = {}
        for old_line in self.order_line:
            # Buscar la línea correspondiente en la nueva orden
            new_line = new_order.order_line.filtered(
                lambda l: l.product_id.id == old_line.product_id.id and 
                         l.product_qty == old_line.product_qty
            )
            if new_line and len(new_line) == 1:
                old_to_new_lines[old_line.id] = new_line[0]
        
        # Copiar buffers de las líneas antiguas a las nuevas
        old_buffers = self.env["purchase.line.item.buffer"].search([
            ("order_line_id", "in", self.order_line.ids)
        ])
        
        for old_buffer in old_buffers:
            old_line_id = old_buffer.order_line_id.id
            if old_line_id in old_to_new_lines:
                new_line = old_to_new_lines[old_line_id]
                
                # Crear nuevo buffer para la nueva línea
                new_buffer = self.env["purchase.line.item.buffer"].create({
                    "order_line_id": new_line.id,
                    "product_tmpl_id": old_buffer.product_tmpl_id.id,
                })
                
                # Copiar líneas del buffer
                for old_bl in old_buffer.line_ids:
                    self.env["purchase.line.item.buffer.line"].create({
                        "buffer_id": new_buffer.id,
                        "item_type": old_bl.item_type,
                        "product_id": old_bl.product_id.id,
                        "quantity": old_bl.quantity,
                        "uom_id": old_bl.uom_id.id if old_bl.uom_id else old_bl.product_id.uom_id.id,
                    })
        
        return new_order
