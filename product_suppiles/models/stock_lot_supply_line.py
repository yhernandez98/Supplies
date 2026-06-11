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
        [
            ("component", "Componente"),
            ("peripheral", "Periférico"),
            ("complement", "Complemento"),
            ("monitor", "Monitores"),
            ("ups", "UPS"),
            ("spare", "Repuestos"),
        ],
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

    cost_additional = fields.Boolean(
        string="Costo Adicional",
        default=False,
        help="Solo se muestra para componentes/complementos/periféricos."
    )
    cost_additional_value = fields.Float(
        string="Valor Costo Adicional",
        digits=(16, 2),
        compute="_compute_cost_additional_value",
        store=False,
        help="Muestra el valor de costo adicional definido en el serial relacionado.",
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
        index=True,
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
    def _supply_line_invalidate_pick_cache(self):
        if hasattr(self.env, '_supply_line_blocked_cache'):
            del self.env._supply_line_blocked_cache

    @api.model
    def _supply_line_location_ids_for_search(self, location):
        """Ubicaciones (incl. hijas) donde buscar stock para asociar seriales."""
        if not location:
            return []
        cache = getattr(self.env, '_supply_line_loc_child_cache', None)
        if cache is None:
            cache = {}
            self.env._supply_line_loc_child_cache = cache
        if location.id not in cache:
            cache[location.id] = self.env['stock.location'].search([
                ('id', 'child_of', location.id),
                ('usage', 'in', ('internal', 'transit')),
            ]).ids
        return cache[location.id]

    def _resolve_supply_parent_stock_location(self, parent_lot):
        """Ubicación donde buscar seriales disponibles para asociar al padre."""
        if not parent_lot:
            return self.env['stock.location']
        ctx = self.env.context
        picking_id = ctx.get('route_editor_picking_id')
        if ctx.get('from_route_lot_editor') and picking_id:
            picking = self.env['stock.picking'].browse(int(picking_id))
            if picking.exists() and picking.location_id:
                return picking.location_id
        if getattr(parent_lot, 'current_location_id', False):
            return parent_lot.current_location_id
        if parent_lot.location_id:
            return parent_lot.location_id
        quant = self.env['stock.quant'].search([
            ('lot_id', '=', parent_lot.id),
            ('quantity', '>', 0),
            ('location_id.usage', 'in', ('internal', 'transit')),
        ], order='in_date desc, id desc', limit=1)
        return quant.location_id if quant else self.env['stock.location']

    @api.model
    def _supply_line_blocked_related_lot_ids(self, exclude_line_id=None, parent_lot=None):
        """Seriales no disponibles: ya asociados a otro equipo o son equipos principales."""
        parent_lot_id = parent_lot.id if parent_lot else 0
        exclude_id = (
            exclude_line_id
            if isinstance(exclude_line_id, int) and exclude_line_id > 0
            else 0
        )
        cache = getattr(self.env, '_supply_line_blocked_cache', None)
        if cache is None:
            cache = {}
            self.env._supply_line_blocked_cache = cache
        cache_key = (exclude_id, parent_lot_id)
        if cache_key in cache:
            return cache[cache_key]

        blocked = set()
        try:
            cr = self.env.cr
            if exclude_id:
                cr.execute(
                    """
                    SELECT DISTINCT related_lot_id
                    FROM stock_lot_supply_line
                    WHERE related_lot_id IS NOT NULL AND id != %s
                    """,
                    (exclude_id,),
                )
            else:
                cr.execute(
                    """
                    SELECT DISTINCT related_lot_id
                    FROM stock_lot_supply_line
                    WHERE related_lot_id IS NOT NULL
                    """,
                )
            blocked.update(row[0] for row in cr.fetchall())
            cr.execute(
                """
                SELECT DISTINCT lot_id
                FROM stock_lot_supply_line
                WHERE lot_id IS NOT NULL
                """,
            )
            blocked.update(row[0] for row in cr.fetchall())
            if parent_lot_id:
                blocked.add(parent_lot_id)
        except Exception:
            pass
        cache[cache_key] = blocked
        return blocked

    def _supply_line_available_related_lot_ids(
        self, product, parent_lot, has_cost=False, exclude_line_id=None,
    ):
        """Seriales candidatos: mismo producto, stock en ubicación del padre/albarán."""
        if not product or not parent_lot:
            return []
        location = self._resolve_supply_parent_stock_location(parent_lot)
        if not location:
            return []
        loc_ids = self._supply_line_location_ids_for_search(location)
        if not loc_ids:
            return []
        quant_domain = [
            ('product_id', '=', product.id),
            ('location_id', 'in', loc_ids),
            ('lot_id', '!=', False),
            ('quantity', '>', 0),
        ]
        if has_cost:
            quant_domain.append(('lot_id.cost_additional', '=', True))
        else:
            quant_domain.append(('lot_id.cost_additional', '=', False))
        try:
            candidate_ids = set(
                self.env['stock.quant'].search(quant_domain).mapped('lot_id').ids
            )
        except Exception:
            candidate_ids = set()
        blocked = self._supply_line_blocked_related_lot_ids(
            exclude_line_id=exclude_line_id,
            parent_lot=parent_lot,
        )
        return list(candidate_ids - blocked)

    @api.model
    def default_get(self, fields_list):
        """Asegurar has_cost desde contexto al crear desde Con Costo / Sin Costo."""
        res = super().default_get(fields_list)
        if res is None:
            res = {}
        if "has_cost" not in res and "default_has_cost" in self.env.context:
            res["has_cost"] = bool(self.env.context["default_has_cost"])
        return res

    @api.depends(
        "related_lot_id",
        "related_lot_id.cost_additional",
        "related_lot_id.cost_additional_value",
    )
    def _compute_cost_additional_value(self):
        """Mostrar el valor adicional del serial relacionado solo cuando aplique."""
        for rec in self:
            related = rec.related_lot_id
            if related and getattr(related, "cost_additional", False):
                rec.cost_additional_value = float(getattr(related, "cost_additional_value", 0.0) or 0.0)
            else:
                rec.cost_additional_value = 0.0

    @api.depends_context(
        'from_route_lot_editor', 'route_editor_picking_id', 'delivery_route_stage',
    )
    @api.depends('item_type', 'lot_id', 'lot_id.location_id', 'has_cost')
    def _compute_available_product_ids(self):
        """Calcular productos disponibles por tipo y ubicación del cliente."""
        for r in self:
            Product = self.env['product.product']
            Quant = self.env['stock.quant']

            # Base por clasificación/tipo
            product_domain = [('type', 'in', ('consu', 'product'))]
            if r.item_type:
                product_domain.append(('classification', '=', r.item_type))

            location = r._resolve_supply_parent_stock_location(r.lot_id)
            if not location:
                r.available_product_ids = Product.search(product_domain)
                continue

            loc_ids = r._supply_line_location_ids_for_search(location)
            quant_domain = [
                ('location_id', 'in', loc_ids or [location.id]),
                ('lot_id', '!=', False),
                ('quantity', '>', 0),
            ]

            # Mantener coherencia con pestaña Con Costo / Sin Costo.
            if r.has_cost:
                quant_domain.append(('lot_id.cost_additional', '=', True))
            else:
                quant_domain.append(('lot_id.cost_additional', '=', False))

            quants = Quant.search(quant_domain)
            exclude_id = r.id if isinstance(r.id, int) and r.id > 0 else None
            blocked = r._supply_line_blocked_related_lot_ids(
                exclude_line_id=exclude_id,
                parent_lot=r.lot_id,
            )
            free_product_ids = list({
                q.product_id.id
                for q in quants
                if q.lot_id.id not in blocked
            })

            if free_product_ids:
                product_domain.append(('id', 'in', free_product_ids))
            else:
                product_domain.append(('id', '=', 0))

            r.available_product_ids = Product.search(product_domain)
    
    @api.onchange("item_type", "lot_id", "has_cost")
    def _onchange_item_type_filter_product(self):
        """Actualizar dominio de product_id y avisar si no hay opciones en la ubicación."""
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

            result = {
                'domain': {
                    'product_id': [('id', 'in', r.available_product_ids.ids)]
                }
            }

            # Aviso amigable cuando no hay productos disponibles en la ubicación del cliente.
            location = r._resolve_supply_parent_stock_location(r.lot_id)
            if r.lot_id and location and not r.available_product_ids:
                tab_label = _("Elementos Con Costo") if r.has_cost else _("Elementos Sin Costo")
                location_name = location.display_name or location.name or ''
                result['warning'] = {
                    'title': _("Sin Productos Disponibles"),
                    'message': _(
                        "No hay productos disponibles para '%(tab)s' en la ubicación '%(location)s'. "
                        "Valida que existan seriales con stock en esa ubicación."
                    ) % {
                        'tab': tab_label,
                        'location': location_name,
                    }
                }

            # Retornar dominio dinámico usando el campo computed
            return result

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
                    if classification in ('component', 'peripheral', 'complement', 'monitor', 'ups', 'spare'):
                        r.item_type = classification
                        r._compute_available_product_ids()

            exclude_id = r.id if isinstance(r.id, int) else None
            available_ids = r._supply_line_available_related_lot_ids(
                r.product_id,
                r.lot_id,
                r.has_cost,
                exclude_line_id=exclude_id,
            ) if r.product_id and r.lot_id else []
            if r.related_lot_id and r.related_lot_id.id not in available_ids:
                r.related_lot_id = False
            return {
                'domain': {
                    'related_lot_id': (
                        [('id', 'in', available_ids)] if available_ids else [('id', '=', 0)]
                    ),
                },
            }

    @api.constrains("quantity")
    def _check_quantity_positive(self):
        for r in self:
            if r.quantity <= 0:
                raise ValidationError(_("La cantidad debe ser mayor que 0."))

    @api.constrains("related_lot_id")
    def _check_related_lot_unique(self):
        """Evitar que un mismo serial se asocie a más de un elemento."""
        for r in self.filtered(lambda l: l.related_lot_id):
            dup = self.search([
                ("id", "!=", r.id),
                ("related_lot_id", "=", r.related_lot_id.id),
            ], limit=1)
            if dup:
                raise ValidationError(_(
                    "El serial '%s' ya está asociado a otro elemento. "
                    "No puede usarse más de una vez."
                ) % (r.related_lot_id.display_name or r.related_lot_id.name or r.related_lot_id.id))
    
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
        for r in self:
            domain = [("id", "=", 0)]
            if not r.product_id or not r.lot_id:
                r.related_lot_id = False
                return {"domain": {"related_lot_id": domain}}
            try:
                exclude_id = r.id if isinstance(r.id, int) else None
                available_ids = r._supply_line_available_related_lot_ids(
                    r.product_id,
                    r.lot_id,
                    r.has_cost,
                    exclude_line_id=exclude_id,
                )
                if available_ids:
                    domain = [("id", "in", available_ids)]
                    if len(available_ids) == 1 and not r.related_lot_id:
                        r.related_lot_id = available_ids[0]
                elif not r.related_lot_id:
                    r.related_lot_id = False
            except Exception:
                domain = [("id", "=", 0)]
            return {"domain": {"related_lot_id": domain}}



    @api.model_create_multi
    def create(self, vals_list):
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        ctx = self._context or {}
        prepared = []
        for vals in vals_list:
            vals = dict(vals)
            if not vals.get("lot_id") and ctx.get("default_lot_id"):
                vals["lot_id"] = ctx["default_lot_id"]
            if not vals.get("item_type") and ctx.get("default_item_type"):
                vals["item_type"] = ctx["default_item_type"]
            if "has_cost" not in vals and "default_has_cost" in ctx:
                vals["has_cost"] = bool(ctx["default_has_cost"])
            if not vals.get("item_type") and vals.get("product_id"):
                product = self.env['product.product'].browse(vals["product_id"])
                if product.exists() and product.product_tmpl_id and hasattr(product.product_tmpl_id, 'classification'):
                    classification = product.product_tmpl_id.classification
                    if classification in ('component', 'peripheral', 'complement', 'monitor', 'ups', 'spare'):
                        vals["item_type"] = classification
            prepared.append(vals)
        records = super().create(prepared)
        self._supply_line_invalidate_pick_cache()
        for rec in records:
            if not rec.has_cost and ctx.get("default_has_cost"):
                rec.has_cost = True
            try:
                if rec.related_lot_id and rec.lot_id:
                    parent_user = rec.lot_id.related_partner_id
                    if parent_user:
                        rec.related_lot_id.related_partner_id = parent_user.id
            except Exception:
                pass
            try:
                if not rec.related_lot_id and rec.product_id and rec.lot_id:
                    available_ids = rec._supply_line_available_related_lot_ids(
                        rec.product_id,
                        rec.lot_id,
                        rec.has_cost,
                        exclude_line_id=rec.id,
                    )
                    if available_ids:
                        rec.related_lot_id = available_ids[0]
            except Exception:
                pass
        return records

    def write(self, vals):
        res = super().write(vals)
        if {'related_lot_id', 'lot_id', 'product_id'} & set(vals):
            self._supply_line_invalidate_pick_cache()
        
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
            if self.env.context.get('invdash_skip_supply_autofill'):
                return res
            for rec in self:
                need_autofill = (
                    not rec.related_lot_id and
                    rec.product_id and
                    rec.lot_id
                )
                if need_autofill:
                    available_ids = rec._supply_line_available_related_lot_ids(
                        rec.product_id,
                        rec.lot_id,
                        rec.has_cost,
                        exclude_line_id=rec.id,
                    )
                    if available_ids:
                        rec.related_lot_id = available_ids[0]
        except Exception:
            pass
        return res

    @api.constrains("related_lot_id", "lot_id", "product_id")
    def _check_related_lot_same_location(self):
        # Validación desactivada: no exigir misma ubicación para ningún tipo de ubicación,
        # de modo que conversiones Genérico→Específico, transferencias y asociaciones
        # funcionen sin fallar por diferencia de ubicación (GESTO/Existencias, ajustes, etc.).
        # El lote relacionado puede estar en cualquier ubicación.
        return


    @api.depends_context(
        'from_route_lot_editor', 'route_editor_picking_id', 'delivery_route_stage',
    )
    @api.depends('product_id', 'lot_id', 'has_cost')
    def _compute_available_related_lot_ids(self):
        """Calcula los lotes disponibles para relacionar, evitando problemas durante instalación."""
        for r in self:
            exclude_id = r.id if isinstance(r.id, int) else None
            available_ids = r._supply_line_available_related_lot_ids(
                r.product_id,
                r.lot_id,
                r.has_cost,
                exclude_line_id=exclude_id,
            )
            r.available_related_lot_ids = (
                [(6, 0, available_ids)] if available_ids else [(5, 0, 0)]
            )

    @staticmethod
    def _strip_virtual_m2m_from_web_spec(specification):
        """M2M calculados sin tabla rompen _parseServerValues en listas editables (Odoo 19)."""
        spec = dict(specification or {})
        for virtual_m2m in ('available_related_lot_ids', 'associated_items_serials'):
            spec.pop(virtual_m2m, None)
        return spec

    def web_read(self, specification):
        return super().web_read(self._strip_virtual_m2m_from_web_spec(specification))

    def web_save(self, vals, specification):
        return super().web_save(vals, self._strip_virtual_m2m_from_web_spec(specification))

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
