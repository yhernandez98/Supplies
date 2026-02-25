# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class StockLotSupplyLine(models.Model):
    _name = "stock.lot.supply.line"
    _description = "Líneas de componentes/periféricos/complementos por Lote/Serie"
    _order = "id asc"

    lot_id = fields.Many2one("stock.lot", required=True, ondelete="cascade", index=True)
    has_cost = fields.Boolean(
        string="Con costo",
        default=False,
        help="Si está marcado, el elemento se considera con costo (pestaña Elementos Con Costo); si no, sin costo.",
    )
    item_type = fields.Selection(
        [("component", "Componente"), ("peripheral", "Periférico"), ("complement", "Complemento"), ("monitor", "Monitores"), ("ups", "UPS")],
        required=True,
        default="component",
        string="Tipo",
    )
    product_id = fields.Many2one(
        "product.product",
        required=True,
        domain="[('id', 'in', available_product_ids)]",
        string="Producto"
    )
    cost = fields.Float(
        string="Costo",
        digits=(16, 2),
        help="Costo del elemento (solo para elementos con costo).",
    )
    quantity = fields.Float(string="Cantidad", default=1.0, digits="Product Unit of Measure", required=True)
    uom_id = fields.Many2one(
        "uom.uom",
        string="UdM",
        domain=[],
    )
    # location_id = fields.Many2one(
    #     "stock.location",
    #     string="Ubicación",
    #     help="La serie/lote seleccionado debe tener stock en esta ubicación."
    # )
    available_related_lot_ids = fields.Many2many(
        "stock.lot",
        compute="_compute_available_related_lot_ids",
        string="Lotes disponibles (dominio)",
        store=False,
    )
    
    # Campo computed para filtrar productos según item_type
    available_product_ids = fields.Many2many(
        "product.product",
        compute="_compute_available_product_ids",
        string="Productos disponibles",
        store=False,
        help="Productos disponibles según el tipo seleccionado"
    )
    
    related_lot_id = fields.Many2one(
        "stock.lot",
        string="Serial",
        domain="[('id', 'in', available_related_lot_ids)]",
        help="Serie/Lote del componente; filtrado por producto, ubicación y excluyendo los ya usados.",
    )
    
    has_associated_items = fields.Boolean(
        string="Tiene elementos asociados",
        compute="_compute_associated_items_info",
        store=False,
        help="Indica si este elemento tiene otros elementos asociados"
    )
    
    associated_items_summary = fields.Char(
        string="Elementos asociados",
        compute="_compute_associated_items_info",
        store=False,
        help="Resumen de los elementos asociados a este componente"
    )
    
    associated_items_serials = fields.Many2many(
        "stock.lot",
        string="Seriales asociados",
        compute="_compute_associated_items_info",
        store=False,
        help="Seriales de los elementos asociados a este componente"
    )
    
    associated_items_serials_display = fields.Char(
        string="Seriales asociados (display)",
        compute="_compute_associated_items_info",
        store=False,
        help="Seriales de los elementos asociados para mostrar en la vista"
    )

    @api.model
    def default_get(self, fields_list):
        """Asegurar has_cost desde contexto al crear desde Con Costo / Sin Costo."""
        res = super().default_get(fields_list)
        if res is None:
            res = {}
        if "has_cost" not in res and "default_has_cost" in self.env.context:
            res["has_cost"] = bool(self.env.context["default_has_cost"])
        return res

    @api.depends('item_type')
    def _compute_available_product_ids(self):
        """Calcular productos disponibles según el item_type seleccionado."""
        for r in self:
            if not r.item_type:
                # Si no hay tipo, mostrar todos los productos de tipo consu o product
                r.available_product_ids = self.env['product.product'].search([
                    ('type', 'in', ('consu', 'product'))
                ])
            else:
                # Filtrar por clasificación
                r.available_product_ids = self.env['product.product'].search([
                    ('type', 'in', ('consu', 'product')),
                    ('classification', '=', r.item_type)
                ])
    
    @api.onchange("item_type")
    def _onchange_item_type_filter_product(self):
        """Actualizar dominio de product_id cuando cambia item_type y limpiar producto si no coincide."""
        for r in self:
            # Limpiar product_id si no coincide con el nuevo tipo
            if r.product_id and r.item_type:
                if hasattr(r.product_id.product_tmpl_id, 'classification'):
                    if r.product_id.product_tmpl_id.classification != r.item_type:
                        r.product_id = False
                        r.related_lot_id = False
                        r.uom_id = False
            
            # Forzar recálculo de available_product_ids
            r._compute_available_product_ids()
            
            # Retornar dominio dinámico usando el campo computed
            return {
                'domain': {
                    'product_id': [('id', 'in', r.available_product_ids.ids)]
                }
            }

    @api.onchange("product_id")
    def _onchange_product_set_uom(self):
        for r in self:
            if r.product_id:
                # VALIDACIÓN DESACTIVADA: El usuario puede convertir y actualizar cualquier serial
                # independientemente de su clasificación
                # Verificar que el producto coincida con el tipo seleccionado
                # if r.item_type and hasattr(r.product_id.product_tmpl_id, 'classification'):
                #     product_classification = r.product_id.product_tmpl_id.classification
                #     if product_classification and product_classification != r.item_type:
                #         # Si no coincide, limpiar el producto y mostrar advertencia
                #         r.product_id = False
                #         r.related_lot_id = False
                #         r.uom_id = False
                #         return {
                #             'warning': {
                #                 'title': _('Producto no coincide con el tipo'),
                #                 'message': _(
                #                     'El producto seleccionado tiene clasificación "%s" pero el tipo seleccionado es "%s". '
                #                     'Por favor, seleccione primero el tipo correcto o elija un producto que coincida.'
                #                 ) % (
                #                     dict(r.product_id.product_tmpl_id._fields['classification'].selection).get(product_classification, product_classification),
                #                     dict(r._fields['item_type'].selection).get(r.item_type, r.item_type)
                #                 )
                #             }
                #         }
                
                # Establecer unidad de medida si no está definida
                if not r.uom_id:
                    r.uom_id = r.product_id.uom_id
                
                # IMPORTANTE: Establecer automáticamente el item_type basándose en la clasificación del producto
                # Solo si item_type no está definido o está vacío
                if not r.item_type and r.product_id.product_tmpl_id and hasattr(r.product_id.product_tmpl_id, 'classification'):
                    classification = r.product_id.product_tmpl_id.classification
                    if classification in ('component', 'peripheral', 'complement', 'monitor', 'ups'):
                        r.item_type = classification
                        # Forzar recálculo de available_product_ids
                        r._compute_available_product_ids()

    @api.constrains("quantity")
    def _check_quantity_positive(self):
        for r in self:
            if r.quantity <= 0:
                raise ValidationError(_("La cantidad debe ser mayor que 0."))
    
    @api.constrains("product_id", "item_type")
    def _check_product_classification_match(self):
        """
        Validar que el producto seleccionado coincida con el tipo (item_type).
        
        NOTA: Esta validación ha sido desactivada para permitir convertir y actualizar
        cualquier serial independientemente de su clasificación, según requerimiento del usuario.
        """
        # VALIDACIÓN DESACTIVADA: El usuario puede convertir y actualizar cualquier serial
        # independientemente de su clasificación
        pass
        # for r in self:
        #     if r.product_id and r.item_type:
        #         if hasattr(r.product_id.product_tmpl_id, 'classification'):
        #             product_classification = r.product_id.product_tmpl_id.classification
        #             if product_classification and product_classification != r.item_type:
        #                 raise ValidationError(_(
        #                     "El producto '%s' tiene clasificación '%s' pero se seleccionó tipo '%s'. "
        #                     "Por favor, seleccione un producto que coincida con el tipo seleccionado."
        #                 ) % (
        #                     r.product_id.display_name,
        #                     dict(r.product_id.product_tmpl_id._fields['classification'].selection).get(product_classification, product_classification),
        #                     dict(r._fields['item_type'].selection).get(r.item_type, r.item_type)
        #                 ))
            

    @api.onchange("related_lot_id", "lot_id")
    def _onchange_related_lot_assign_user(self):
        """Asignar automáticamente el usuario del serial padre al elemento asociado."""
        for rec in self:
            if rec.related_lot_id and rec.lot_id:
                # Obtener el usuario del serial padre
                parent_user = rec.lot_id.related_partner_id
                if parent_user:
                    # Actualizar el usuario del elemento asociado
                    rec.related_lot_id.related_partner_id = parent_user.id
    
    @api.onchange("product_id", "lot_id")
    def _onchange_filter_related_lot_by_location(self):
        """Filtra lotes disponibles por ubicación, protegido contra errores de instalación."""
        Quant = self.env["stock.quant"]
        for r in self:
            domain = [("id", "=", 0)]
            r.related_lot_id = False

            # Proteger contra errores durante instalación
            try:
                if not r.product_id or not r.lot_id:
                    return {"domain": {"related_lot_id": domain}}
                
                # Verificar que location_id existe y es accesible
                try:
                    if not r.lot_id.location_id:
                        return {"domain": {"related_lot_id": domain}}
                except Exception:
                    return {"domain": {"related_lot_id": domain}}

                try:
                    quants = Quant.search([
                        ("product_id", "=", r.product_id.id),
                        ("location_id", "=", r.lot_id.location_id.id),
                        ("lot_id", "!=", False),
                        ("quantity", ">", 0),
                    ])
                    lot_ids = set(quants.mapped("lot_id").ids)
                except Exception:
                    lot_ids = set()

                try:
                    used_ids_global = set(self.search([
                        ("related_lot_id", "!=", False),
                    ]).mapped("related_lot_id").ids)
                except Exception:
                    used_ids_global = set()

                try:
                    used_ids_same_parent = set(self.search([
                        ("lot_id", "=", r.lot_id.id),
                        ("related_lot_id", "!=", False),
                    ]).mapped("related_lot_id").ids)
                except Exception:
                    used_ids_same_parent = set()

                blocked = used_ids_global | used_ids_same_parent
                available_ids = list(lot_ids - blocked)

                if available_ids:
                    domain = [("id", "in", available_ids)]

                if len(available_ids) == 1:
                    r.related_lot_id = available_ids[0]
            except Exception:
                # Si hay error, retornar dominio vacío
                domain = [("id", "=", 0)]

            return {"domain": {"related_lot_id": domain}}



    @api.model
    def create(self, vals):
        ctx = self.env.context or {}
        if not vals.get("lot_id") and ctx.get("default_lot_id"):
            vals["lot_id"] = ctx["default_lot_id"]
        if not vals.get("item_type") and ctx.get("default_item_type"):
            vals["item_type"] = ctx["default_item_type"]
        # Aplicar default_has_cost del contexto para que las líneas creadas desde cada pestaña conserven su tipo (también si la clave está en context aunque sea False)
        if "has_cost" not in vals and "default_has_cost" in ctx:
            vals["has_cost"] = bool(ctx["default_has_cost"])

        # IMPORTANTE: Si no se especificó item_type, intentar obtenerlo de la clasificación del producto
        if not vals.get("item_type") and vals.get("product_id"):
            product = self.env['product.product'].browse(vals["product_id"])
            if product.exists() and product.product_tmpl_id and hasattr(product.product_tmpl_id, 'classification'):
                classification = product.product_tmpl_id.classification
                if classification in ('component', 'peripheral', 'complement', 'monitor', 'ups'):
                    vals["item_type"] = classification

        rec = super().create(vals)

        # Fallback: si el contexto pedía has_cost=True y no se aplicó en vals, forzar tras crear (p. ej. cuando el inverse se ejecuta antes que el create)
        if not rec.has_cost and ctx.get("default_has_cost"):
            rec.has_cost = True

        # Asignar automáticamente el usuario del serial padre al elemento asociado
        try:
            if rec.related_lot_id and rec.lot_id:
                # Obtener el usuario del serial padre
                parent_user = rec.lot_id.related_partner_id
                if parent_user:
                    # Actualizar el usuario del elemento asociado
                    rec.related_lot_id.related_partner_id = parent_user.id
        except Exception:
            # Si hay error (campo no existe, etc.), continuar sin asignar
            pass

        # Proteger contra errores durante instalación/actualización
        try:
            if not rec.related_lot_id and rec.product_id and rec.lot_id:
                # Verificar que location_id existe y es accesible
                try:
                    if not rec.lot_id.location_id:
                        return rec
                except Exception:
                    return rec

                Quant = self.env["stock.quant"]

                try:
                    quants = Quant.search([
                        ("product_id", "=", rec.product_id.id),
                        ("location_id", "=", rec.lot_id.location_id.id),
                        ("lot_id", "!=", False),
                        ("quantity", ">", 0),
                    ])
                    lot_ids = set(quants.mapped("lot_id").ids)
                except Exception:
                    lot_ids = set()

                try:
                    used_ids_global = set(self.search([
                        ("related_lot_id", "!=", False),
                    ]).mapped("related_lot_id").ids)
                except Exception:
                    used_ids_global = set()

                try:
                    used_ids_same_parent = set(self.search([
                        ("lot_id", "=", rec.lot_id.id),
                        ("related_lot_id", "!=", False),
                    ]).mapped("related_lot_id").ids)
                except Exception:
                    used_ids_same_parent = set()

                blocked = used_ids_global | used_ids_same_parent
                available_ids = list(lot_ids - blocked)
                if available_ids:
                    rec.related_lot_id = available_ids[0]
        except Exception:
            # Si hay error durante instalación, continuar sin asignar related_lot_id
            pass

        return rec


    def write(self, vals):
        res = super().write(vals)
        
        # Asignar automáticamente el usuario del serial padre a los elementos asociados
        try:
            for rec in self:
                # Si se actualizó related_lot_id o lot_id, actualizar el usuario del elemento asociado
                if 'related_lot_id' in vals or 'lot_id' in vals:
                    if rec.related_lot_id and rec.lot_id:
                        # Obtener el usuario del serial padre
                        parent_user = rec.lot_id.related_partner_id
                        if parent_user:
                            # Actualizar el usuario del elemento asociado
                            rec.related_lot_id.related_partner_id = parent_user.id
        except Exception:
            # Si hay error (campo no existe, etc.), continuar sin asignar
            pass
        
        # Proteger contra errores durante instalación/actualización
        try:
            for rec in self:
                need_autofill = (
                    not rec.related_lot_id and
                    rec.product_id and
                    rec.lot_id
                )
                if need_autofill:
                    # Verificar que location_id existe y es accesible
                    try:
                        if not rec.lot_id.location_id:
                            continue
                    except Exception:
                        continue

                    Quant = self.env["stock.quant"]

                    try:
                        quants = Quant.search([
                            ("product_id", "=", rec.product_id.id),
                            ("location_id", "=", rec.lot_id.location_id.id),
                            ("lot_id", "!=", False),
                            ("quantity", ">", 0),
                        ])
                        lot_ids = set(quants.mapped("lot_id").ids)
                    except Exception:
                        lot_ids = set()

                    try:
                        used_ids_global = set(self.search([
                            ("related_lot_id", "!=", False),
                        ]).mapped("related_lot_id").ids)
                    except Exception:
                        used_ids_global = set()

                    try:
                        used_ids_same_parent = set(self.search([
                            ("lot_id", "=", rec.lot_id.id),
                            ("related_lot_id", "!=", False),
                        ]).mapped("related_lot_id").ids)
                    except Exception:
                        used_ids_same_parent = set()

                    blocked = used_ids_global | used_ids_same_parent
                    available_ids = list(lot_ids - blocked)
                    if available_ids:
                        rec.related_lot_id = available_ids[0]
        except Exception:
            # Si hay error durante instalación, continuar sin asignar related_lot_id
            pass
        return res

    @api.constrains("related_lot_id", "lot_id", "product_id")
    def _check_related_lot_same_location(self):
        # Validación desactivada: no exigir misma ubicación para ningún tipo de ubicación,
        # de modo que conversiones Genérico→Específico, transferencias y asociaciones
        # funcionen sin fallar por diferencia de ubicación (GESTO/Existencias, ajustes, etc.).
        # El lote relacionado puede estar en cualquier ubicación.
        return


    @api.depends("product_id", "lot_id")
    def _compute_available_related_lot_ids(self):
        """Calcula los lotes disponibles para relacionar, evitando problemas durante instalación."""
        Quant = self.env["stock.quant"]
        SupplyLine = self.env["stock.lot.supply.line"]

        # Proteger contra errores durante instalación/actualización
        try:
            used_global = set(SupplyLine.search([
                ("related_lot_id", "!=", False),
            ]).mapped("related_lot_id").ids)
        except Exception:
            # Si hay error (por ejemplo, durante instalación), usar conjunto vacío
            used_global = set()

        for r in self:
            r.available_related_lot_ids = [(5, 0, 0)] 
            if not r.product_id or not r.lot_id:
                continue
            
            # Verificar que location_id existe y es accesible
            try:
                if not r.lot_id.location_id:
                    continue
            except Exception:
                continue

            try:
                quants = Quant.search([
                    ("product_id", "=", r.product_id.id),
                    ("location_id", "=", r.lot_id.location_id.id),
                    ("lot_id", "!=", False),
                    ("quantity", ">", 0),
                ])
                candidate_ids = set(quants.mapped("lot_id").ids)
            except Exception:
                candidate_ids = set()

            try:
                used_same_parent = set(SupplyLine.search([
                    ("lot_id", "=", r.lot_id.id),
                    ("related_lot_id", "!=", False),
                ]).mapped("related_lot_id").ids)
            except Exception:
                used_same_parent = set()

            blocked = used_global | used_same_parent

            available = list(candidate_ids - blocked)
            if available:
                r.available_related_lot_ids = [(6, 0, available)]
    
    @api.depends('related_lot_id', 'related_lot_id.lot_supply_line_ids', 
                 'related_lot_id.lot_supply_line_ids.item_type',
                 'related_lot_id.lot_supply_line_ids.product_id',
                 'related_lot_id.lot_supply_line_ids.related_lot_id',
                 'related_lot_id.lot_supply_line_ids.related_lot_id.name')
    def _compute_associated_items_info(self):
        """Calcular si el related_lot_id tiene elementos asociados y mostrar resumen."""
        for line in self:
            line.has_associated_items = False
            line.associated_items_summary = ''
            line.associated_items_serials = [(5, 0, 0)]  # Limpiar Many2many
            line.associated_items_serials_display = ''
            
            if not line.related_lot_id:
                continue
            
            # Verificar si el related_lot_id tiene elementos asociados
            related_lot = line.related_lot_id
            # Forzar lectura del campo lot_supply_line_ids
            if not hasattr(related_lot, 'lot_supply_line_ids'):
                continue
            
            # Leer explícitamente los lot_supply_line_ids
            try:
                supply_lines = related_lot.lot_supply_line_ids
                if not supply_lines:
                    continue
            except Exception:
                continue
            
            # Recopilar productos y seriales por separado
            product_names = []
            lot_ids = []
            lot_names = []
            
            for supply_line in supply_lines:
                # Obtener nombre del producto (sin prefijos como [GEN], etc.)
                if supply_line.product_id:
                    product_name = supply_line.product_id.name or 'Sin nombre'
                    # Remover prefijos entre corchetes si existen
                    if ']' in product_name:
                        parts = product_name.split(']', 1)
                        if len(parts) > 1:
                            product_name = parts[1].strip()
                    # Limitar longitud del nombre del producto
                    if len(product_name) > 50:
                        product_name = product_name[:47] + '...'
                    product_names.append(product_name)
                
                # Obtener serial del elemento asociado
                if supply_line.related_lot_id:
                    lot_ids.append(supply_line.related_lot_id.id)
                    if supply_line.related_lot_id.name:
                        lot_names.append(supply_line.related_lot_id.name)
            
            if product_names or lot_ids:
                line.has_associated_items = True
                
                # Mostrar productos uno debajo del otro
                line.associated_items_summary = '\n'.join(product_names) if product_names else ''
                
                # Asignar lotes asociados (Many2many) para hacerlos clickables
                if lot_ids:
                    line.associated_items_serials = [(6, 0, lot_ids)]
                
                # Mostrar seriales uno debajo del otro para display
                line.associated_items_serials_display = '\n'.join(lot_names) if lot_names else ''
