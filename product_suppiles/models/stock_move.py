# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class StockMove(models.Model):
    _inherit = "stock.move"

    supply_parent_product_id = fields.Many2one(
        comodel_name="product.product",
        string="Producto principal",
        compute="_compute_supply_parent_product_id",
        store=True,
        readonly=True,
    )

    supply_kind = fields.Selection(
        selection=[
            ("parent", "Principal"),
            ("component", "Componente"),
            ("peripheral", "Periférico"),
            ("complement", "Complemento"),
            ("monitor", "Monitores"),
            ("ups", "UPS"),
        ],
        string="Clasificación supplies",
        default="parent",
        help="Clasifica el movimiento como el producto principal o como parte de la explosión.",
        index=True,
    )

    purchase_tracking_ref = fields.Char(
        string="Seguimiento compra",
        compute="_compute_purchase_tracking_ref",
        store=True,
        readonly=True,
        help="Referencia de seguimiento (PO/Picking).",
    )

    sale_tracking_ref = fields.Char(
        string="Seguimiento venta",
        compute="_compute_sale_tracking_ref",
        store=True,
        readonly=True,
        help="Referencia de seguimiento (SO/Picking).",
    )

    internal_parent_move_id = fields.Many2one(
        "stock.move", string="Movimiento padre (internal)", index=True, ondelete="cascade"
    )
    internal_child_move_ids = fields.One2many(
        "stock.move", "internal_parent_move_id", string="Movimientos hijos (internal)"
    )
    
    # Campos para mostrar elementos asociados en columnas (desde move_line_ids)
    associated_components = fields.Char(
        string='Componentes',
        compute='_compute_associated_elements',
        store=False,
        help='Números de serie de componentes asociados al producto principal'
    )
    
    associated_peripherals = fields.Char(
        string='Periféricos',
        compute='_compute_associated_elements',
        store=False,
        help='Números de serie de periféricos asociados al producto principal'
    )
    
    associated_complements = fields.Char(
        string='Complementos',
        compute='_compute_associated_elements',
        store=False,
        help='Números de serie de complementos asociados al producto principal'
    )
    
    # Campo helper para ocultar líneas no principales en la vista
    show_in_list = fields.Boolean(
        string='Mostrar en lista',
        compute='_compute_show_in_list',
        store=False,
        help='Indica si esta línea debe mostrarse en la vista de operaciones'
    )
    
    @api.depends('supply_kind')
    def _compute_show_in_list(self):
        """Calcular si la línea debe mostrarse (solo líneas principales)"""
        for move in self:
            move.show_in_list = move.supply_kind == 'parent'
    
    principal_lot_serial = fields.Char(
        string='Número de Serie',
        compute='_compute_principal_lot_serial',
        store=False,
        help='Número de serie del producto principal'
    )
    
    principal_lot_id = fields.Many2one(
        'stock.lot',
        string='Lote Principal',
        compute='_compute_principal_lot_serial',
        store=False,
        help='Lote principal del movimiento'
    )
    
    @api.depends('move_line_ids', 'move_line_ids.lot_id', 'move_line_ids.supply_kind', 'supply_kind')
    def _compute_principal_lot_serial(self):
        """Calcular el número de serie del lote principal."""
        for move in self:
            move.principal_lot_serial = ''
            move.principal_lot_id = False
            
            # Solo procesar si es un movimiento principal
            if move.supply_kind != 'parent':
                continue
            
            # Buscar la línea principal (con lote y supply_kind = 'parent')
            principal_line = move.move_line_ids.filtered(
                lambda ml: ml.lot_id and ml.supply_kind == 'parent'
            )
            
            if principal_line and len(principal_line) > 0:
                principal_lot = principal_line[0].lot_id
                if principal_lot:
                    move.principal_lot_id = principal_lot.id
                    if principal_lot.name:
                        move.principal_lot_serial = principal_lot.name
    
    def action_open_lot_wizard(self):
        """Abrir la vista del lote como wizard (modal) para editar elementos asociados."""
        self.ensure_one()
        
        if not self.principal_lot_id:
            raise UserError(_('No hay lote principal asociado a este movimiento.'))
        
        # Verificar que el picking no esté validado
        if self.picking_id and self.picking_id.state == 'done':
            raise UserError(_('No se pueden editar los elementos asociados de un picking ya validado.'))
        
        # Usar siempre la vista raíz: Odoo fusiona herencias (pestañas, campos) automáticamente.
        form_view_id = self.env.ref('stock.view_production_lot_form', raise_if_not_found=False)
        # Abrir la vista del lote como wizard (modal) para que no se salgan de la vista del picking
        return {
            'type': 'ir.actions.act_window',
            'name': _('Editar Elementos Asociados - %s') % self.principal_lot_id.name,
            'res_model': 'stock.lot',
            'res_id': self.principal_lot_id.id,
            'view_mode': 'form',
            'view_id': form_view_id.id if form_view_id else False,
            'target': 'new',  # Abrir como wizard (modal)
            'context': {
                'active_id': self.principal_lot_id.id,
                'active_model': 'stock.lot',
                'default_lot_id': self.principal_lot_id.id,
                'form_view_initial_mode': 'edit',  # Abrir en modo edición
            },
        }
    
    def name_get(self):
        """Sobrescribir name_get para que el campo principal_lot_id muestre el número de serie."""
        res = super().name_get()
        # Esto es solo para el campo principal_lot_id, no afecta otros campos
        return res
    
    @api.depends('move_line_ids', 'move_line_ids.lot_id', 'move_line_ids.lot_id.lot_supply_line_ids',
                 'move_line_ids.lot_id.lot_supply_line_ids.related_lot_id', 
                 'move_line_ids.lot_id.lot_supply_line_ids.item_type',
                 'move_line_ids.lot_id.lot_supply_line_ids.related_lot_id.name',
                 'supply_kind')
    def _compute_associated_elements(self):
        """Calcular elementos asociados agrupados por tipo para mostrar en columnas."""
        for move in self:
            move.associated_components = ''
            move.associated_peripherals = ''
            move.associated_complements = ''
            
            # Solo procesar si es un movimiento principal
            if move.supply_kind != 'parent':
                continue
            
            # Buscar la línea principal (con lote y supply_kind = 'parent')
            principal_line = move.move_line_ids.filtered(
                lambda ml: ml.lot_id and ml.supply_kind == 'parent'
            )
            
            if not principal_line or len(principal_line) == 0:
                continue
            
            principal_lot = principal_line[0].lot_id
            
            if not principal_lot or not hasattr(principal_lot, 'lot_supply_line_ids'):
                continue
            
            if not principal_lot.lot_supply_line_ids:
                continue
            
            # Agrupar elementos asociados por tipo con nombre del producto y serial
            components = []
            peripherals = []
            complements = []
            
            for supply_line in principal_lot.lot_supply_line_ids:
                if not supply_line.related_lot_id:
                    continue
                
                related_lot = supply_line.related_lot_id
                serial_name = related_lot.name or ''
                if not serial_name:
                    continue
                
                # Obtener nombre del producto
                product_name = ''
                if supply_line.product_id:
                    product_name = supply_line.product_id.display_name or supply_line.product_id.name or ''
                
                # Formato: "Nombre Producto - Serial"
                if product_name:
                    display_text = f"{product_name} - {serial_name}"
                else:
                    display_text = serial_name
                
                if supply_line.item_type == 'component':
                    components.append(display_text)
                elif supply_line.item_type == 'peripheral':
                    peripherals.append(display_text)
                elif supply_line.item_type == 'complement':
                    complements.append(display_text)
                elif supply_line.item_type in ('monitor', 'ups'):
                    # Monitores y UPS se muestran como periféricos
                    peripherals.append(display_text)
            
            # Unir los elementos con comas y saltos de línea para mejor visualización
            move.associated_components = '\n'.join(components) if components else ''
            move.associated_peripherals = '\n'.join(peripherals) if peripherals else ''
            move.associated_complements = '\n'.join(complements) if complements else ''

    @api.depends(
        "purchase_line_id.product_id",
        "sale_line_id.renting_applies_to_tmpl_id",
        "sale_line_id.product_id",
        "product_id",
        "supply_kind",
        "picking_id.picking_type_id.code",
        "internal_parent_move_id.product_id",
    )
    def _compute_supply_parent_product_id(self):
        for move in self:
            parent = False
            # CORRECCIÓN: Validar que picking_id y picking_type_id existen antes de acceder
            code = False
            if move.picking_id and move.picking_id.exists() and move.picking_id.picking_type_id and move.picking_id.picking_type_id.exists():
                code = move.picking_id.picking_type_id.code or False

            if code == "incoming":
                # CORRECCIÓN: Validar que purchase_line_id existe antes de acceder
                if move.purchase_line_id and move.purchase_line_id.exists() and move.purchase_line_id.product_id:
                    parent = move.purchase_line_id.product_id
                elif move.supply_kind == "parent" and move.product_id and move.product_id.exists():
                    parent = move.product_id

            elif code == "outgoing":
                if move.supply_kind == "parent" and move.product_id and move.product_id.exists():
                    parent = move.product_id
                else:
                    # CORRECCIÓN: Validar que sale_line_id existe antes de acceder
                    if move.sale_line_id and move.sale_line_id.exists():
                        tmpl = move.sale_line_id.renting_applies_to_tmpl_id
                        if tmpl and tmpl.exists():
                            parent = tmpl.product_variant_id if tmpl.product_variant_id and tmpl.product_variant_id.exists() else False

            elif code == "internal":
                if move.supply_kind == "parent" and move.product_id and move.product_id.exists():
                    parent = move.product_id
                elif move.internal_parent_move_id and move.internal_parent_move_id.exists():
                    if move.internal_parent_move_id.product_id and move.internal_parent_move_id.product_id.exists():
                        parent = move.internal_parent_move_id.product_id

            move.supply_parent_product_id = parent.id if parent else False

    @api.depends(
        "purchase_line_id.order_id.name",
        "picking_id.name",
    )
    def _compute_purchase_tracking_ref(self):
        for move in self:
            # CORRECCIÓN: Validar que purchase_line_id y order_id existen antes de acceder
            po = ""
            if move.purchase_line_id and move.purchase_line_id.exists():
                if move.purchase_line_id.order_id and move.purchase_line_id.order_id.exists():
                    po = move.purchase_line_id.order_id.name or ""
            pick = ""
            if move.picking_id and move.picking_id.exists():
                pick = move.picking_id.name or ""
            move.purchase_tracking_ref = f"{po}/{pick}" if po and pick else (po or pick) or False

    @api.depends(
        "sale_line_id.order_id.name",
        "picking_id.name",
    )
    def _compute_sale_tracking_ref(self):
        for move in self:
            # CORRECCIÓN: Validar que sale_line_id y order_id existen antes de acceder
            so = ""
            if move.sale_line_id and move.sale_line_id.exists():
                if move.sale_line_id.order_id and move.sale_line_id.order_id.exists():
                    so = move.sale_line_id.order_id.name or ""
            pick = ""
            if move.picking_id and move.picking_id.exists():
                pick = move.picking_id.name or ""
            move.sale_tracking_ref = f"{so}/{pick}" if so and pick else (so or pick) or False

    @api.depends(
        "purchase_line_id.product_id",
        "sale_line_id.renting_applies_to_tmpl_id",
        "sale_line_id.product_id",
        "product_id",
        "supply_kind",
        "picking_id.picking_type_id.code",
    )
    def _compute_supply_parent_product_id(self):
        for move in self:
            parent = False
            # CORRECCIÓN: Validar que picking_id y picking_type_id existen antes de acceder
            code = False
            if move.picking_id and move.picking_id.exists() and move.picking_id.picking_type_id and move.picking_id.picking_type_id.exists():
                code = move.picking_id.picking_type_id.code or False

            if code == "incoming":
                # CORRECCIÓN: Validar que purchase_line_id existe antes de acceder
                if move.purchase_line_id and move.purchase_line_id.exists() and move.purchase_line_id.product_id:
                    parent = move.purchase_line_id.product_id
                elif move.supply_kind == "parent" and move.product_id and move.product_id.exists():
                    parent = move.product_id

            elif code in ("outgoing", "internal"):
                if move.supply_kind == "parent" and move.product_id and move.product_id.exists():
                    parent = move.product_id
                else:
                    # CORRECCIÓN: Validar que sale_line_id existe antes de acceder
                    if move.sale_line_id and move.sale_line_id.exists():
                        tmpl = move.sale_line_id.renting_applies_to_tmpl_id
                        if tmpl and tmpl.exists():
                            parent = tmpl.product_variant_id if tmpl.product_variant_id and tmpl.product_variant_id.exists() else False

            move.supply_parent_product_id = parent.id if parent else False

    def _action_assign(self):
        """
        Sobrescribe _action_assign para asegurar que los movimientos hijos usen solo el lote relacionado.
        Limpia líneas duplicadas después de que Odoo asigna el movimiento.
        """
        result = super()._action_assign()
        
        # Para movimientos hijos, asegurar que solo se use el lote relacionado correcto
        for move in self:
            if move.internal_parent_move_id and move.supply_kind in ('component', 'peripheral', 'complement'):
                # Es un movimiento hijo, verificar que use el lote relacionado correcto
                parent_move = move.internal_parent_move_id
                
                # Obtener el lote principal del movimiento padre
                parent_move_lines = parent_move.move_line_ids.filtered(
                    lambda ml: ml.lot_id and ml.lot_id.exists() and ml.supply_kind == "parent"
                )
                if parent_move_lines and len(parent_move_lines) > 0:
                    principal_lot = parent_move_lines[0].lot_id
                    
                    # Buscar el lote relacionado correcto para este producto
                    if principal_lot and principal_lot.exists() and hasattr(principal_lot, 'lot_supply_line_ids'):
                        supply_lines = principal_lot.lot_supply_line_ids.filtered(
                            lambda sl: sl.product_id.id == move.product_id.id and 
                                     sl.related_lot_id and sl.related_lot_id.exists()
                        )
                        if supply_lines and len(supply_lines) > 0:
                            related_lot = supply_lines[0].related_lot_id
                            
                            # CORRECCIÓN: Buscar la línea que tiene el lote relacionado correcto
                            correct_line = move.move_line_ids.filtered(
                                lambda ml: ml.lot_id and ml.lot_id.exists() and ml.lot_id.id == related_lot.id
                            )
                            
                            # CORRECCIÓN CRÍTICA: En lugar de eliminar líneas agresivamente, actualizar las existentes
                            # Esto evita el error "Registro faltante" cuando Odoo intenta acceder a líneas eliminadas
                            
                            # Si hay una línea correcta, asegurar que tenga la cantidad correcta
                            if correct_line and len(correct_line) > 0:
                                # Actualizar la primera línea correcta
                                if correct_line[0].id and correct_line[0].exists():
                                    if correct_line[0].quantity > move.product_uom_qty:
                                        correct_line[0].quantity = move.product_uom_qty
                                    
                                    # Si hay múltiples líneas correctas, consolidar en la primera
                                    if len(correct_line) > 1:
                                        total_qty = sum(correct_line.mapped('quantity'))
                                        if total_qty > move.product_uom_qty:
                                            total_qty = move.product_uom_qty
                                        correct_line[0].quantity = total_qty
                                        
                                        # Solo eliminar líneas duplicadas si hay más de una línea correcta
                                        # y la primera línea tiene la cantidad correcta
                                        if len(correct_line) > 1:
                                            lines_to_unlink = correct_line[1:].filtered(
                                                lambda ml: ml.id and ml.exists() and ml.id != correct_line[0].id
                                            )
                                            if lines_to_unlink:
                                                lines_to_unlink.unlink()
                            
                            # Si no hay línea correcta pero hay líneas existentes, actualizar la primera
                            # NO intentar crear líneas aquí para evitar recursión infinita
                            elif move.move_line_ids:
                                first_line = move.move_line_ids[0]
                                if first_line.id and first_line.exists():
                                    # Actualizar el lote de la primera línea
                                    if not first_line.lot_id or first_line.lot_id.id != related_lot.id:
                                        first_line.lot_id = related_lot.id
                                    # Asegurar que la cantidad sea correcta
                                    if first_line.quantity != move.product_uom_qty:
                                        first_line.quantity = move.product_uom_qty
                            
                            # CORRECCIÓN: Solo eliminar líneas incorrectas si hay una línea correcta
                            # Esto evita eliminar todas las líneas y causar el error "Registro faltante"
                            if correct_line and len(correct_line) > 0:
                                wrong_lines = move.move_line_ids.filtered(
                                    lambda ml: ml.id and ml.exists() and
                                             ml.id != correct_line[0].id and
                                             (not ml.lot_id or not ml.lot_id.exists() or ml.lot_id.id != related_lot.id)
                                )
                                if wrong_lines:
                                    # Verificar que las líneas a eliminar realmente existen
                                    lines_to_unlink = wrong_lines.filtered(lambda ml: ml.id and ml.exists())
                                    if lines_to_unlink:
                                        lines_to_unlink.unlink()
        
        return result
