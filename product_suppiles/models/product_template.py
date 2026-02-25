# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class ProductTemplate(models.Model):
    _inherit = "product.template"

    # Extender el campo type para agregar más opciones
    type = fields.Selection(
        selection_add=[
            # Aquí puedes agregar tus nuevas opciones
            # Formato: ('valor_interno', 'Etiqueta Visible')
            # Ejemplo: ('nuevo_tipo', 'Nuevo Tipo de Producto'),
        ],
        ondelete={
            # Mapear qué hacer cuando se elimina cada opción
            # 'nuevo_tipo': 'set default',  # o 'cascade', 'restrict'
        }
    )

    classification = fields.Selection(
        selection=[
            ("component", "Componente"),
            ("peripheral", "Periférico"),
            ("complement", "Complemento"),
            ("monitor", "Monitores"),
            ("ups", "UPS"),
        ],
        string="Clasificación",
        help="Clasifica el producto para filtrar en el wizard de compras."
    )

    is_composite = fields.Boolean(
        string="Componentes",
        help="Si está activo, el producto se explota en componentes en recepciones."
    )

    use_peripherals = fields.Boolean(
        string="Periféricos",
        help="Si está activo, el producto maneja líneas de periféricos"
    )
    use_complements = fields.Boolean(
        string="Complementos",
        help="Si está activo, el producto maneja líneas de complementos"
    )

    composite_line_ids = fields.One2many(
        "product.composite.line", "parent_product_tmpl_id",
        string="Componentes",
        help="Defina los componentes por unidad del producto compuesto."
    )

    peripheral_line_ids = fields.One2many(
        "product.peripheral.line", "parent_product_tmpl_id",
        string="Periféricos",
        help="Periféricos por unidad del producto."
    )

    complement_line_ids = fields.One2many(
        "product.complement.line", "parent_product_tmpl_id",
        string="Complementos",
        help="Complementos por unidad del producto."
    )

    component_cost_method = fields.Selection(
        selection=[("std_prorata", "Prorrateo por costo estándar"), ("equal", "Prorrateo en partes iguales")],
        string="Método de reparto de costo (compras)",
        default="std_prorata",
    )

    receive_parent_stock = fields.Boolean(
        string="Incrementar stock del padre en recepciones"
    )

    parent_valuation_policy = fields.Selection(
        [("none", "Padre sin valoración (costo en componentes)"),
         ("full", "Padre con valoración (componentes sin costo)")],
        string="Valoración del padre en recepción",
        default="none",
    )

    model_name = fields.Char(string="Modelo")
    inventory_plate = fields.Char(string="Placa de Inventario")
    security_plate = fields.Char(string="Placa de Seguridad")
    billing_code = fields.Char(string="Código de Facturación")

    asset_category_id = fields.Many2one(
        "product.asset.category",
        string="Categoría de Activo",
        ondelete="restrict",
    )

    asset_class_id = fields.Many2one(
        "product.asset.class",
        string="Clase de Activo",
        ondelete="restrict",
        domain="[('category_id', '=', asset_category_id), ('company_id', '=', company_id)]",
        help="Solo muestra clases pertenecientes a la categoría seleccionada.",
    )
    business_line_id = fields.Many2one(
        "product.business.line",
        string="Linea de negocio",
        ondelete="restrict",
    )

    history_component_ids = fields.One2many(
        "supplies.item.history", "parent_product_tmpl_id",
        string="Historial Componentes",
        domain=[("item_type", "=", "component")],
        readonly=True,
    )
    history_peripheral_ids = fields.One2many(
        "supplies.item.history", "parent_product_tmpl_id",
        string="Historial Periféricos",
        domain=[("item_type", "=", "peripheral")],
        readonly=True,
    )
    history_complement_ids = fields.One2many(
        "supplies.item.history", "parent_product_tmpl_id",
        string="Historial Complementos",
        domain=[("item_type", "=", "complement")],
        readonly=True,
    )
    product_renting = fields.Boolean(
        string="Producto Renting",
        help="Si está activo, al vender este producto se pedirá a qué producto objetivo (con comp./perif./compl.) aplica.",
        tracking=True,
    )

    renting_applicable_tmpl_ids = fields.Many2many(
        "product.template",
        "product_renting_applicable_rel",
        "renting_src_tmpl_id",
        "renting_dst_tmpl_id",
        string="Aplicable a productos",
        help="Selecciona los productos objetivo (que ya definiste con componentes/periféricos/complementos).",
    )
    ui_apply_defaults = fields.Boolean(
        compute="_compute_ui_apply_defaults",
        store=False,
        help="Trigger técnico para aplicar defaults según el tipo de producto."
    )

    @api.depends("type")
    def _compute_ui_apply_defaults(self):
        for rec in self:
            vals = {}
            if rec.type == "service":
                if not rec.sale_ok:
                    vals["sale_ok"] = True
                if "recurring_invoice" in rec._fields and not rec.recurring_invoice:
                    vals["recurring_invoice"] = True
                # if rec.purchase_ok:
                #     vals["purchase_ok"] = False

            elif rec.type in ("product", "consu"):
                if not rec.sale_ok:
                    vals["sale_ok"] = True
                if not rec.purchase_ok:
                    vals["purchase_ok"] = True
                if "recurring_invoice" in rec._fields and rec.recurring_invoice:
                    vals["recurring_invoice"] = False

            if vals:
                rec.write(vals)

            rec.ui_apply_defaults = True

    @api.onchange("type")
    def _onchange_type_defaults(self):
        for rec in self:
            if rec.type == "service":
                rec.sale_ok = True
                if "recurring_invoice" in rec._fields:
                    rec.recurring_invoice = True
                    
    def write(self, vals):
        """Sobrescribir write para validar componentes después de guardar las líneas."""
        result = super().write(vals)
        
        # Si se modificó is_composite o composite_line_ids, validar después de guardar
        if 'is_composite' in vals or 'composite_line_ids' in vals:
            for tmpl in self:
                if tmpl.is_composite:
                    # Refrescar el recordset para obtener las líneas actualizadas
                    tmpl.invalidate_recordset(['composite_line_ids'])
                    # Validar después de que las líneas se hayan guardado
                    tmpl._validate_composite_lines()
        
        return result
    
    @api.model_create_multi
    def create(self, vals_list):
        """Sobrescribir create para validar componentes después de crear las líneas."""
        records = super().create(vals_list)
        
        # Validar después de crear
        for record in records:
            if record.is_composite:
                record._validate_composite_lines()
        
        return records
    
    def _validate_composite_lines(self):
        """Validar que un producto compuesto tenga al menos un componente."""
        for tmpl in self:
            if not tmpl.is_composite:
                continue
            
            # Obtener todas las líneas (ya guardadas)
            all_lines = tmpl.composite_line_ids
            
            if not all_lines:
                raise ValidationError(_("Debe definir al menos un componente cuando el producto es compuesto."))
            
            # Validar cada línea
            for line in all_lines:
                if not line.component_product_id:
                    raise ValidationError(_("Línea de componente sin producto."))
                if line.component_qty <= 0:
                    raise ValidationError(_("La cantidad del componente debe ser mayor a 0."))
                if line.component_product_id.product_tmpl_id == tmpl:
                    raise ValidationError(_("El producto no puede ser componente de sí mismo."))
    
    @api.constrains("is_composite", "composite_line_ids")
    def _check_composite_lines(self):
        """Validación legacy - ahora se hace en write/create."""
        # Esta validación se mantiene por compatibilidad pero la lógica real está en _validate_composite_lines
        pass

    def _explode_components(self, qty, uom=None):
        self.ensure_one()
        if not self.is_composite:
            return []
        qty_in_base = qty
        if uom and uom != self.uom_id:
            qty_in_base = uom._compute_quantity(qty, self.uom_id, rounding_method="HALF-UP")
        result = []
        for line in self.composite_line_ids:
            comp_uom = line.component_uom_id or line.component_product_id.uom_id
            comp_qty_base = line.component_qty * qty_in_base
            comp_qty = self.uom_id._compute_quantity(comp_qty_base, comp_uom, rounding_method="HALF-UP")
            result.append({"product": line.component_product_id, "qty": comp_qty, "uom": comp_uom})
        return result

    def _explode_peripherals(self, qty, uom=None):
        self.ensure_one()
        if not self.use_peripherals:
            return []
        qty_in_base = qty
        if uom and uom != self.uom_id:
            qty_in_base = uom._compute_quantity(qty, self.uom_id, rounding_method="HALF-UP")
        result = []
        for line in self.peripheral_line_ids:
            per_uom = line.peripheral_uom_id or line.peripheral_product_id.uom_id
            per_qty_base = line.peripheral_qty * qty_in_base
            per_qty = self.uom_id._compute_quantity(per_qty_base, per_uom, rounding_method="HALF-UP")
            result.append({"product": line.peripheral_product_id, "qty": per_qty, "uom": per_uom})
        return result

    def _explode_complements(self, qty, uom=None):
        self.ensure_one()
        if not (self.use_complements or getattr(self, "use_complements", False)):
            return []
        qty_in_base = qty
        if uom and uom != self.uom_id:
            qty_in_base = uom._compute_quantity(qty, self.uom_id, rounding_method="HALF-UP")
        result = []
        for line in self.complement_line_ids:
            com_uom = line.complement_uom_id or line.complement_product_id.uom_id
            com_qty_base = line.complement_qty * qty_in_base
            com_qty = self.uom_id._compute_quantity(com_qty_base, com_uom, rounding_method="HALF-UP")
            result.append({"product": line.complement_product_id, "qty": com_qty, "uom": com_uom})
        return result
    @api.onchange("asset_category_id")
    def _onchange_asset_category_id_reset_class(self):
        for rec in self:
            if rec.asset_class_id and rec.asset_class_id.category_id != rec.asset_category_id:
                rec.asset_class_id = False

class ProductCompositeLine(models.Model):
    _name = "product.composite.line"
    _description = "Componente de producto compuesto"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    parent_product_tmpl_id = fields.Many2one("product.template", string="Producto compuesto", required=True, ondelete="cascade", index=True)
    component_product_id = fields.Many2one("product.product", string="Componente", required=True,
                                           domain="[('type','in',('consu','product'))]")
    component_qty = fields.Float(string="Cantidad (por 1 compuesto)", required=True, default=1.0, digits="Product Unit of Measure")
    component_uom_id = fields.Many2one(
        "uom.uom", string="Unidad componente",
        # Odoo 19: uom.uom ya no tiene category_id; el onchange asigna la UdM del producto.
        domain=[],
    )

    @api.onchange("component_product_id")
    def _onchange_component_product_id(self):
        for line in self:
            if line.component_product_id and not line.component_uom_id:
                line.component_uom_id = line.component_product_id.uom_id


class ProductPeripheralLine(models.Model):
    _name = "product.peripheral.line"
    _description = "Periférico asociado al producto"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    parent_product_tmpl_id = fields.Many2one("product.template", string="Producto", required=True, ondelete="cascade", index=True)
    peripheral_product_id = fields.Many2one("product.product", string="Periférico", required=True,
                                            domain="[('type','in',('consu','product'))]")
    peripheral_qty = fields.Float(string="Cantidad (por 1 producto)", required=True, default=1.0, digits="Product Unit of Measure")
    peripheral_uom_id = fields.Many2one(
        "uom.uom", string="Unidad periférico",
        domain=[],
    )

    @api.onchange("peripheral_product_id")
    def _onchange_peripheral_product_id(self):
        for line in self:
            if line.peripheral_product_id and not line.peripheral_uom_id:
                line.peripheral_uom_id = line.peripheral_product_id.uom_id


class ProductComplementLine(models.Model):
    _name = "product.complement.line"
    _description = "Complemento asociado al producto"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    parent_product_tmpl_id = fields.Many2one("product.template", string="Producto", required=True, ondelete="cascade", index=True)
    complement_product_id = fields.Many2one("product.product", string="Complemento", required=True,
                                            domain="[('type','in',('consu','product'))]")
    complement_qty = fields.Float(string="Cantidad (por 1 producto)", required=True, default=1.0, digits="Product Unit of Measure")
    complement_uom_id = fields.Many2one(
        "uom.uom", string="Unidad complemento",
        domain=[],
    )

    @api.onchange("complement_product_id")
    def _onchange_complement_product_id(self):
        for line in self:
            if line.complement_product_id and not line.complement_uom_id:
                line.complement_uom_id = line.complement_product_id.uom_id


class ProductProduct(models.Model):
    _inherit = "product.product"

    serial_cc = fields.Char(
        string="Serial (Único)",
        copy=False,
        index=True,
        help="Identificador único por variante; actúa como 'cédula' del producto."
    )

    model_name = fields.Char(related="product_tmpl_id.model_name", readonly=False)
    inventory_plate = fields.Char(related="product_tmpl_id.inventory_plate", readonly=False)
    security_plate = fields.Char(related="product_tmpl_id.security_plate", readonly=False)
    billing_code = fields.Char(related="product_tmpl_id.billing_code", readonly=False)
    asset_category_id = fields.Many2one(
        "product.asset.category",
        related="product_tmpl_id.asset_category_id",
        readonly=False,
        ondelete="restrict",
    )
    asset_class_id = fields.Many2one(
        "product.asset.class",
        related="product_tmpl_id.asset_class_id",
        readonly=False,
        ondelete="restrict",
    )
    business_line_id = fields.Many2one(
        "product.business.line",
        related="product_tmpl_id.business_line_id",
        readonly=False,
        ondelete="restrict",
    )
    classification = fields.Selection(
        related="product_tmpl_id.classification", readonly=False
    )

    serial_cc_unique = models.Constraint(
        "unique(serial_cc)",
        "El Serial (Único) debe ser único en todas las variantes.",
    )

    @api.constrains("serial_cc")
    def _check_unique_serial_cc(self):
        for rec in self:
            if rec.serial_cc:
                domain = [("serial_cc", "=", rec.serial_cc)]
                if rec.id:
                    domain.append(("id", "!=", rec.id))
                if self.search_count(domain):
                    raise ValidationError(_("El Serial (Único) ya existe en otra variante de producto."))
