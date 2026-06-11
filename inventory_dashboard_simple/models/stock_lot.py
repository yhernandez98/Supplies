# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.osv import expression
import logging

_logger = logging.getLogger(__name__)


class StockLot(models.Model):
    _inherit = 'stock.lot'
    
    internal_ref_id = fields.Many2one(
        'internal.reference',
        string='Referencia Interna',
        compute='_compute_internal_ref_id',
        inverse='_inverse_internal_ref_id',
        store=False,
        help='Referencia interna del lote (filtrada por producto)',
        domain="[('product_id', '=', product_id)]"
    )
    
    product_asset_category_id = fields.Many2one(
        'product.asset.category',
        string='Categoría de Activo del Producto',
        related='product_id.asset_category_id',
        readonly=True,
        store=True,
        help='Categoría de activo del producto (almacenado para permitir agrupación)'
    )
    
    product_asset_class_id = fields.Many2one(
        'product.asset.class',
        string='Clase de Activo del Producto',
        related='product_id.asset_class_id',
        readonly=True,
        store=True,
        help='Clase de activo del producto (almacenado para permitir agrupación)'
    )
    
    # Campos para la vista de lotes incompletos
    display_location_id = fields.Many2one(
        'stock.location',
        string='Ubicación',
        compute='_compute_display_location_contact',
        store=True,
        index=True,
        help='Ubicación actual del lote (desde quants; almacenado para listados rápidos).'
    )
    
    display_contact_id = fields.Many2one(
        'res.partner',
        string='Contacto',
        compute='_compute_display_location_contact',
        store=True,
        index=True,
        help='Contacto asociado a la ubicación del lote (índice para agrupar en listados).'
    )

    is_stock_in_supp_existencias = fields.Boolean(
        string='Stock en almacén Supp',
        compute='_compute_is_stock_in_supp_existencias',
        store=True,
        index=True,
        help='True si hay cantidad > 0 en ubicación interna del árbol «Supp/…» (Existencias, Alistamiento, Laboratorio, etc.); se excluye de pendientes de información.',
    )

    invdash_pending_info = fields.Boolean(
        string='Pendiente información (dashboard)',
        compute='_compute_invdash_pending_info',
        store=True,
        index=True,
        help='Pre-calculado con el mismo criterio que «Productos Pendientes de Información» para consultas rápidas.',
    )

    invdash_serial_multi_location = fields.Boolean(
        string='Serie en varias ubicaciones',
        compute='_compute_invdash_serial_multi_location',
        store=True,
        index=True,
        help='True si hay cantidad > 0 en más de una ubicación (interna o tránsito). Un serial no debería estar '
             'repartido entre dos almacenes distintos.',
    )
    invdash_multi_location_detail = fields.Text(
        string='Detalle por ubicación',
        compute='_compute_invdash_serial_multi_location',
        store=True,
        help='Listado de ubicaciones con cantidad positiva cuando hay más de una.',
    )

    has_excluded_supply_elements = fields.Boolean(
        string='Tiene Elementos Excluidos',
        compute='_compute_has_excluded_supply_elements',
        store=True,
        help='Indica si tiene elementos asociados que deben ser excluidos de la vista COMPUTO'
    )
    
    @api.depends('lot_supply_line_ids', 'lot_supply_line_ids.product_id', 
                 'lot_supply_line_ids.product_id.asset_category_id', 
                 'lot_supply_line_ids.product_id.asset_class_id',
                 'lot_supply_line_ids.item_type')
    def _compute_has_excluded_supply_elements(self):
        """Verificar si tiene TODOS los elementos requeridos para ser excluido.
        
        Un producto COMPUTO solo se excluye si tiene TODOS estos elementos:
        - Complemento + Clase: Adaptador
        - Componente + Clase: Disco Duro
        - Componente + Clase: Procesador
        - Componente + Clase: Memoria RAM
        - Periférico + Clase: Mouse
        - Periférico + Clase: Teclado
        
        Si falta alguno, debe aparecer en la lista (has_excluded_supply_elements = False).
        """
        # Definir las combinaciones REQUERIDAS (todas deben estar presentes)
        required_combinations = [
            {'item_type': 'complement', 'category_name': 'complemento', 'class_name': 'adaptador'},
            {'item_type': 'component', 'category_name': 'componente', 'class_name': 'disco duro'},
            {'item_type': 'component', 'category_name': 'componente', 'class_name': 'procesador'},
            {'item_type': 'component', 'category_name': 'componente', 'class_name': 'memoria ram'},
            {'item_type': 'peripheral', 'category_name': 'periferico', 'class_name': 'mouse'},
            {'item_type': 'peripheral', 'category_name': 'periferico', 'class_name': 'teclado'},
        ]
        
        # Cachear las categorías y clases para evitar búsquedas repetidas
        AssetCategory = self.env['product.asset.category']
        AssetClass = self.env['product.asset.class']
        
        # Buscar todas las categorías y clases necesarias una sola vez
        category_cache = {}
        class_cache = {}
        
        for combo in required_combinations:
            cat_name = combo['category_name']
            class_name = combo['class_name']
            
            if cat_name not in category_cache:
                category_cache[cat_name] = AssetCategory.search([('name', 'ilike', cat_name)], limit=1)
            
            if class_name not in class_cache:
                class_cache[class_name] = AssetClass.search([('name', 'ilike', class_name)], limit=1)
        
        for lot in self:
            # Inicializar en False (debe aparecer en la lista por defecto)
            lot.has_excluded_supply_elements = False
            
            if not lot.id:
                continue
            
            # Si no tiene líneas de suministro, debe aparecer en la lista (ya está en False)
            if not hasattr(lot, 'lot_supply_line_ids') or not lot.lot_supply_line_ids:
                _logger.debug(
                    "Lote %s no tiene líneas de suministro, aparecerá en la lista",
                    lot.name or lot.id
                )
                continue
            
            # Crear un conjunto para rastrear qué combinaciones se han encontrado
            found_combinations = set()
            
            # Verificar cada línea de suministro
            for supply_line in lot.lot_supply_line_ids:
                if not supply_line.product_id:
                    continue
                
                product = supply_line.product_id
                item_type = supply_line.item_type
                asset_category = product.asset_category_id
                asset_class = product.asset_class_id
                
                if not asset_category or not asset_class:
                    continue
                
                # Verificar cada combinación requerida
                for idx, combo in enumerate(required_combinations):
                    if item_type != combo['item_type']:
                        continue
                    
                    expected_cat = category_cache.get(combo['category_name'])
                    expected_class = class_cache.get(combo['class_name'])
                    
                    if (expected_cat and asset_category.id == expected_cat.id and
                        expected_class and asset_class.id == expected_class.id):
                        # Marcar esta combinación como encontrada
                        found_combinations.add(idx)
                        _logger.debug(
                            "Lote %s tiene elemento requerido %d: %s - %s / %s",
                            lot.name or lot.id,
                            idx,
                            item_type,
                            asset_category.name,
                            asset_class.name
                        )
                        break
            
            # Solo se excluye si tiene TODAS las combinaciones requeridas
            if len(found_combinations) == len(required_combinations):
                lot.has_excluded_supply_elements = True
                _logger.debug(
                    "Lote %s tiene TODOS los elementos requeridos, será excluido de la lista",
                    lot.name or lot.id
                )
            else:
                missing = len(required_combinations) - len(found_combinations)
                _logger.debug(
                    "Lote %s le faltan %d elementos requeridos, aparecerá en la lista",
                    lot.name or lot.id,
                    missing
                )
    
    @api.model
    def recompute_has_excluded_supply_elements(self):
        """Método para forzar el recálculo de has_excluded_supply_elements haciendo un barrido por todas las ubicaciones."""
        _logger.info("=== INICIANDO BARRIDO COMPLETO POR UBICACIONES ===")
        
        # Buscar categoría COMPUTO
        computo_category = self.env['product.asset.category'].search([('name', 'ilike', 'computo')], limit=1)
        if not computo_category:
            _logger.error("No se encontró la categoría COMPUTO")
            return False
        
        _logger.info("Categoría COMPUTO encontrada: %s (ID: %s)", computo_category.name, computo_category.id)
        
        # Buscar todas las ubicaciones internas
        all_locations = self.env['stock.location'].search([
            ('usage', '=', 'internal')
        ])
        _logger.info("Total de ubicaciones internas encontradas: %d", len(all_locations))
        
        # Buscar todos los quants con lotes COMPUTO en ubicaciones internas
        _logger.info("Buscando quants con lotes COMPUTO en todas las ubicaciones...")
        quants = self.env['stock.quant'].search([
            ('location_id.usage', '=', 'internal'),
            ('quantity', '>', 0),
            ('lot_id', '!=', False),
            ('lot_id.product_id.asset_category_id', '=', computo_category.id)
        ])
        
        # Obtener lotes únicos
        lot_ids = list(set(quants.mapped('lot_id').ids))
        _logger.info("Total de lotes COMPUTO únicos encontrados: %d", len(lot_ids))
        
        if not lot_ids:
            _logger.warning("No se encontraron lotes COMPUTO")
            return False
        
        # Definir las combinaciones requeridas
        required_combinations = [
            {'item_type': 'complement', 'category_name': 'complemento', 'class_name': 'adaptador'},
            {'item_type': 'component', 'category_name': 'componente', 'class_name': 'disco duro'},
            {'item_type': 'component', 'category_name': 'componente', 'class_name': 'procesador'},
            {'item_type': 'component', 'category_name': 'componente', 'class_name': 'memoria ram'},
            {'item_type': 'peripheral', 'category_name': 'periferico', 'class_name': 'mouse'},
            {'item_type': 'peripheral', 'category_name': 'periferico', 'class_name': 'teclado'},
        ]
        
        # Cachear categorías y clases
        AssetCategory = self.env['product.asset.category']
        AssetClass = self.env['product.asset.class']
        category_cache = {}
        class_cache = {}
        
        for combo in required_combinations:
            cat_name = combo['category_name']
            class_name = combo['class_name']
            
            if cat_name not in category_cache:
                category_cache[cat_name] = AssetCategory.search([('name', 'ilike', cat_name)], limit=1)
            
            if class_name not in class_cache:
                class_cache[class_name] = AssetClass.search([('name', 'ilike', class_name)], limit=1)
        
        # Procesar lotes en lotes
        batch_size = 100
        total_processed = 0
        total_with_all_elements = 0
        total_without_all_elements = 0
        
        for i in range(0, len(lot_ids), batch_size):
            batch_ids = lot_ids[i:i + batch_size]
            lots = self.browse(batch_ids)
            
            # Cargar las líneas de suministro para este lote
            lots.mapped('lot_supply_line_ids')
            
            for lot in lots:
                has_excluded = False
                
                # Verificar si tiene líneas de suministro
                if hasattr(lot, 'lot_supply_line_ids') and lot.lot_supply_line_ids:
                    found_combinations = set()
                    
                    # Verificar cada línea de suministro
                    for supply_line in lot.lot_supply_line_ids:
                        if not supply_line.product_id:
                            continue
                        
                        product = supply_line.product_id
                        item_type = supply_line.item_type
                        asset_category = product.asset_category_id
                        asset_class = product.asset_class_id
                        
                        if not asset_category or not asset_class:
                            continue
                        
                        # Verificar cada combinación requerida
                        for idx, combo in enumerate(required_combinations):
                            if item_type != combo['item_type']:
                                continue
                            
                            expected_cat = category_cache.get(combo['category_name'])
                            expected_class = class_cache.get(combo['class_name'])
                            
                            if (expected_cat and asset_category.id == expected_cat.id and
                                expected_class and asset_class.id == expected_class.id):
                                found_combinations.add(idx)
                                break
                    
                    # Solo se excluye si tiene TODAS las combinaciones requeridas
                    if len(found_combinations) == len(required_combinations):
                        has_excluded = True
                        total_with_all_elements += 1
                    else:
                        total_without_all_elements += 1
                else:
                    # Sin líneas de suministro = debe aparecer en la lista
                    total_without_all_elements += 1
                
                # Actualizar directamente en la base de datos
                self.env.cr.execute(
                    "UPDATE stock_lot SET has_excluded_supply_elements = %s WHERE id = %s",
                    (has_excluded, lot.id)
                )
            
            total_processed += len(lots)
            self.env.cr.commit()
            _logger.info("Procesados %d/%d lotes (con todos: %d, sin todos: %d)", 
                        total_processed, len(lot_ids), total_with_all_elements, total_without_all_elements)
        
        _logger.info("=== BARRIDO COMPLETADO ===")
        _logger.info("Total procesados: %d", total_processed)
        _logger.info("Lotes con TODOS los elementos (excluidos): %d", total_with_all_elements)
        _logger.info("Lotes sin todos los elementos (aparecerán en lista): %d", total_without_all_elements)
        
        # Invalidar cache para refrescar vistas
        self.env.invalidate_all()
        
        return True
    
    def action_recompute_excluded_elements(self):
        """Acción para ejecutar el recálculo desde la interfaz."""
        try:
            result = self.env['stock.lot'].recompute_has_excluded_supply_elements()
            if result:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Actualización Completada',
                        'message': 'El barrido por ubicaciones se completó exitosamente. Los productos COMPUTO se han actualizado.',
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Error',
                        'message': 'No se pudo completar el recálculo. Revisa los logs del servidor.',
                        'type': 'danger',
                        'sticky': True,
                    }
                }
        except Exception as e:
            _logger.error('Error al ejecutar recálculo desde la interfaz: %s', str(e), exc_info=True)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Error al ejecutar el recálculo: {str(e)}',
                    'type': 'danger',
                    'sticky': True,
                }
            }
    
    def _invdash_partner_from_location_chain(self, location, loc_partner_cache=None):
        """Cliente cuya ubicación stock (`property_stock_customer`) coincide con esta ubicación o un padre (ej. serial en KANGU/Existencias → partner en KANGU)."""
        Partner = self.env['res.partner'].sudo()
        origin = location
        loc = location
        while loc:
            if loc_partner_cache is not None and loc.id in loc_partner_cache:
                cached = loc_partner_cache[loc.id]
                if cached:
                    return cached
                loc = loc.location_id
                continue
            partner = Partner.search([('property_stock_customer', '=', loc.id)], limit=1)
            res = partner[:1] if partner else self.env['res.partner']
            if loc_partner_cache is not None:
                loc_partner_cache[loc.id] = res
            if res:
                return res
            loc = loc.location_id
        # Fallback: inferir cliente por nombre raíz de la ubicación interna (ej. "IMCD/Existencias" -> partner "IMCD ...").
        if origin and origin.complete_name:
            root_name = (origin.complete_name.split('/')[0] or '').strip()
            if root_name:
                key = f'root::{root_name.lower()}'
                if loc_partner_cache is not None and key in loc_partner_cache:
                    cached = loc_partner_cache[key]
                    if cached:
                        return cached
                candidates = Partner.search(
                    [
                        ('is_company', '=', True),
                        '|',
                        ('name', 'ilike', root_name),
                        ('display_name', 'ilike', root_name),
                    ],
                    limit=8,
                )
                partner = self.env['res.partner']
                if candidates:
                    commercial = candidates.mapped('commercial_partner_id')
                    commercial = commercial.filtered(lambda p: p)
                    if len(commercial) == 1:
                        partner = commercial[:1]
                    else:
                        # Si hay empate, tomar coincidencia exacta por nombre (si existe) para evitar asignaciones erróneas.
                        exact = candidates.filtered(lambda p: (p.name or '').strip().lower() == root_name.lower())
                        if len(exact) == 1:
                            partner = exact.commercial_partner_id or exact
                if loc_partner_cache is not None:
                    loc_partner_cache[key] = partner
                if partner:
                    return partner
        return self.env['res.partner']

    def _invdash_resolve_display_contact(self, quant, loc_partner_cache=None):
        """Prioridad: jerarquía de ubicación → propietario quant → suscripción → usuario relacionado (empresa)."""
        self.ensure_one()
        Partner = self.env['res.partner']
        if quant and quant.location_id:
            partner = self._invdash_partner_from_location_chain(quant.location_id, loc_partner_cache)
            if partner:
                return partner
            if hasattr(quant, 'owner_id') and quant.owner_id:
                return quant.owner_id
        if 'active_subscription_id' in self._fields and self.active_subscription_id:
            sub = self.active_subscription_id
            if getattr(sub, 'partner_id', False):
                return sub.partner_id
        if 'related_partner_id' in self._fields and self.related_partner_id:
            rel = self.related_partner_id
            return rel.commercial_partner_id or rel
        return Partner.browse()

    @api.depends(
        'quant_ids',
        'quant_ids.location_id',
        'quant_ids.quantity',
        'quant_ids.location_id.complete_name',
        'active_subscription_id',
        'active_subscription_id.partner_id',
        'related_partner_id',
        'related_partner_id.commercial_partner_id',
    )
    def _compute_display_location_contact(self):
        """Calcular ubicación y contacto desde los quants del lote (1 consulta a quants por lote en lote)."""
        Quant = self.env['stock.quant']
        loc_partner_cache = {}

        for lot in self:
            lot.display_location_id = False
            lot.display_contact_id = False

        records = self.filtered(lambda l: l.id)
        if not records:
            return

        # Una sola búsqueda de quants; por lote se toma el de mayor cantidad (orden global por lote)
        quants = Quant.search(
            [
                ('lot_id', 'in', records.ids),
                ('quantity', '>', 0),
                ('location_id.usage', '=', 'internal'),
            ],
            order='lot_id asc, quantity desc, in_date desc',
        )
        best_quant_by_lot = {}
        for q in quants:
            lid = q.lot_id.id
            if lid not in best_quant_by_lot:
                best_quant_by_lot[lid] = q

        for lot in records:
            quant = best_quant_by_lot.get(lot.id)
            if quant and quant.location_id:
                lot.display_location_id = quant.location_id
                lot.display_contact_id = lot._invdash_resolve_display_contact(quant, loc_partner_cache)

    @api.model
    def _invdash_supp_subtree_location_ids(self):
        """IDs de todo el subárbol bajo la carpeta «Supp» (Existencias, tránsito, laboratorio, etc.).

        En pantalla muchas hijas son «tránsito», no «internas»; antes solo se tomaban internas y el stock
        en Supp/Alistamiento, Supp/Laboratorio, etc. no contaba y los lotes seguían como pendientes.

        Raíz: ubicación llamada «Supp» (la carpeta suele ser vista u operativa). Descendientes: `child_of`
        sin filtrar por tipo — mismas rutas `complete_name` que empiezan por Supp/.
        """
        Location = self.env['stock.location'].sudo()
        # La carpeta «Supp» no siempre es internal (a menudo es vista); no filtrar solo internal aquí.
        roots = Location.search([('name', '=ilike', 'supp')])
        if not roots:
            anchors = Location.search([
                '|', '|',
                ('complete_name', 'ilike', '%Supp/Existencias%'),
                ('complete_name', 'ilike', '%/Supp/%'),
                ('complete_name', 'ilike', 'Supp/%'),
            ], limit=80)
            root_ids = set()
            for loc in anchors:
                cur = loc
                depth = 0
                while cur and depth < 40:
                    nm = (cur.name or '').strip().lower()
                    if nm == 'supp':
                        root_ids.add(cur.id)
                        break
                    cur = cur.location_id
                    depth += 1
            if root_ids:
                roots = Location.browse(list(root_ids))
        if not roots:
            _logger.debug(
                'invdash: sin carpeta «Supp» ni ancla en nombre completo; '
                'revisar ubicaciones en Inventario.'
            )
            return frozenset()
        subtree = Location.search([('id', 'child_of', roots.ids)])
        return frozenset(subtree.ids)

    @api.depends(
        'quant_ids',
        'quant_ids.quantity',
        'quant_ids.location_id',
        'quant_ids.location_id.complete_name',
        'quant_ids.location_id.usage',
    )
    def _compute_is_stock_in_supp_existencias(self):
        """Stock en subárbol de la carpeta «Supp» (Existencias, Alistamiento, Laboratorio, etc.)."""
        lots = self.filtered(lambda l: l.id)
        for lot in self:
            lot.is_stock_in_supp_existencias = False
        if not lots:
            return

        supp_loc_ids = self.env['stock.lot']._invdash_supp_subtree_location_ids()
        if not supp_loc_ids:
            return

        if len(lots) == 1:
            lot = lots
            for q in lot.quant_ids:
                if (q.quantity or 0) <= 0:
                    continue
                if q.location_id and q.location_id.id in supp_loc_ids:
                    lot.is_stock_in_supp_existencias = True
                    break
            return

        Quants = self.env['stock.quant'].search(
            [
                ('lot_id', 'in', lots.ids),
                ('quantity', '>', 0),
            ]
        )
        hit_ids = set()
        for q in Quants:
            if q.location_id and q.location_id.id in supp_loc_ids:
                hit_ids.add(q.lot_id.id)
        for lot in lots:
            if lot.id in hit_ids:
                lot.is_stock_in_supp_existencias = True

    def _invdash_meets_pending_info_criteria(self):
        """Misma lógica que el dominio histórico de la vista (un solo lugar para mantener)."""
        self.ensure_one()
        if not self.id:
            return False
        cls = self.product_id.classification if self.product_id else False
        if cls in ('component', 'peripheral'):
            return False
        if self.product_id:
            cat_name = (self.product_id.asset_category_id.name or '').strip().lower()
            class_name = (self.product_id.asset_class_id.name or '').strip().lower()
            # Excluir solo ADAPTADOR (categoria COMPLEMENTO + clase ADAPTADOR), no todos los complementos.
            if cat_name == 'complemento' and class_name == 'adaptador':
                return False
        if self.is_stock_in_supp_existencias:
            return False

        def _empty_char(val):
            return val in (False, None, '')

        missing = (
            _empty_char(self.inventory_plate)
            or _empty_char(self.billing_code)
            or not self.entry_date
            or not self.subscription_service_product_id
            or not self.active_subscription_id
        )
        return bool(missing)

    @api.depends(
        'inventory_plate',
        'security_plate',
        'ref',
        'billing_code',
        'entry_date',
        'subscription_service_product_id',
        'active_subscription_id',
        'product_id',
        'product_id.classification',
        'product_id.asset_category_id',
        'product_id.asset_class_id',
        'is_stock_in_supp_existencias',
    )
    def _compute_invdash_pending_info(self):
        for lot in self:
            lot.invdash_pending_info = lot._invdash_meets_pending_info_criteria()

    @api.depends(
        'quant_ids',
        'quant_ids.quantity',
        'quant_ids.location_id',
        'quant_ids.location_id.usage',
    )
    def _compute_invdash_serial_multi_location(self):
        """Detectar serial con stock positivo en más de una ubicación (mismo lote = mismo producto)."""
        for lot in self:
            lot.invdash_serial_multi_location = False
            lot.invdash_multi_location_detail = ''
        records = self.filtered(lambda l: l.id)
        if not records:
            return
        Quant = self.env['stock.quant'].sudo()
        quants = Quant.search(
            [
                ('lot_id', 'in', records.ids),
                ('quantity', '>', 0),
                ('location_id.usage', 'in', ('internal', 'transit')),
            ]
        )
        loc_qty = defaultdict(lambda: defaultdict(float))
        for q in quants:
            loc_qty[q.lot_id.id][q.location_id.id] += q.quantity

        Location = self.env['stock.location'].sudo()
        for lot in records:
            lmap = loc_qty.get(lot.id) or {}
            if len(lmap) < 2:
                continue
            lot.invdash_serial_multi_location = True
            loc_ids = list(lmap.keys())
            locs = Location.browse(loc_ids)
            name_by_id = {loc.id: (loc.complete_name or loc.name or '') for loc in locs}

            def _sort_key(loc_id):
                return name_by_id.get(loc_id, '')

            parts = []
            for loc_id in sorted(lmap.keys(), key=_sort_key):
                qty = lmap[loc_id]
                nm = name_by_id.get(loc_id, '')
                if float(qty).is_integer():
                    qtxt = str(int(qty))
                else:
                    qtxt = f'{float(qty):.2f}'.rstrip('0').rstrip('.')
                parts.append(f'{nm} ({qtxt})')
            lot.invdash_multi_location_detail = '; '.join(parts)

    @api.depends('ref', 'product_id')
    def _compute_internal_ref_id(self):
        """Calcular internal_ref_id desde el campo ref, filtrando por producto."""
        for lot in self:
            if lot.ref and lot.product_id:
                internal_ref = self.env['internal.reference'].search([
                    ('name', '=', lot.ref),
                    ('product_id', '=', lot.product_id.id)
                ], limit=1)
                lot.internal_ref_id = internal_ref.id if internal_ref else False
            else:
                lot.internal_ref_id = False
    
    def _inverse_internal_ref_id(self):
        """Actualizar ref desde internal_ref_id."""
        for lot in self:
            if lot.internal_ref_id:
                lot.ref = lot.internal_ref_id.name
            else:
                lot.ref = False
    
    @api.onchange('product_id')
    def _onchange_product_id_internal_ref(self):
        """Limpiar referencia interna cuando cambia el producto."""
        for lot in self:
            if lot.internal_ref_id:
                # Verificar que la referencia interna pertenezca al producto actual
                if lot.internal_ref_id.product_id != lot.product_id:
                    lot.internal_ref_id = False
                    lot.ref = False

    def _delivery_route_wizard_lot_domain(self, domain):
        wizard_id = self.env.context.get('delivery_route_wizard_id')
        if not wizard_id:
            return domain
        wizard = self.env['delivery.route.trigger.wizard'].browse(
            int(wizard_id)
        )
        if not wizard.exists():
            return domain
        lots = wizard.route_available_lot_ids
        product_id = self.env.context.get('delivery_route_product_id')
        if product_id:
            lots = lots.filtered(
                lambda lot: lot.product_id.id == int(product_id)
            )
        if not lots:
            return [('id', '=', 0)]
        return expression.AND([domain or [], [('id', 'in', lots.ids)]])

    @api.model
    def name_search(self, name='', domain=None, operator='ilike', limit=100, **kwargs):
        """Procesar Ruta: catálogo precalculado del wizard (Odoo 19 name_search)."""
        legacy_args = kwargs.pop('args', None)
        if legacy_args is not None and domain is None:
            domain = legacy_args
        kwargs.pop('order', None)

        # Selector Serial en líneas de suministro: no aplicar filtros del dashboard.
        ctx = self.env.context
        if ctx.get('supply_line_serial_pick') or (
            ctx.get('supply_line_product_id') and ctx.get('supply_line_parent_lot_id')
        ):
            return super().name_search(name, domain, operator, limit)

        domain = self._delivery_route_wizard_lot_domain(domain)
        if domain == [('id', '=', 0)]:
            return []
        return super().name_search(name, domain, operator, limit)

    @api.model
    def web_search_read(
        self, domain, specification, offset=0, limit=None, order=None, count_limit=None,
    ):
        # Selector Serial en líneas de suministro: delegar a product_suppiles sin filtros propios.
        ctx = self.env.context
        if ctx.get('supply_line_serial_pick') or (
            ctx.get('supply_line_product_id') and ctx.get('supply_line_parent_lot_id')
        ):
            return super().web_search_read(
                domain,
                specification,
                offset=offset,
                limit=limit,
                order=order,
                count_limit=count_limit,
            )

        if self.env.context.get('delivery_route_wizard_id'):
            domain = self._delivery_route_wizard_lot_domain(domain)
            if domain == [('id', '=', 0)]:
                return {'length': 0, 'records': []}
            specification = {'display_name': {}}
            limit = min(limit or 80, 80)
        return super().web_search_read(
            domain,
            specification,
            offset=offset,
            limit=limit,
            order=order,
            count_limit=count_limit,
        )

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, order=None):
        """Permitir búsqueda por número de serie y placa de inventario, con filtro de ubicación según el contexto.
        
        Basado en la implementación de mesa_ayuda_inventario/models/customer_inventory_lot.py
        """
        if args is None:
            args = []

        ctx = self.env.context
        if ctx.get('supply_line_serial_pick') or (
            ctx.get('supply_line_product_id') and ctx.get('supply_line_parent_lot_id')
        ):
            return super(StockLot, self)._name_search(
                name=name, args=args, operator=operator, limit=limit, order=order,
            )

        # Verificar si se debe filtrar por ubicación desde el contexto
        filter_by_location = self.env.context.get('filter_by_location', False)
        operation_type = self.env.context.get('wizard_operation_type', False)
        partner_id = self.env.context.get('wizard_partner_id', False)
        
        # Mantener compatibilidad con el contexto antiguo
        filter_by_supplies = self.env.context.get('filter_by_supplies_location', False)
        if filter_by_supplies and not filter_by_location:
            filter_by_location = True
            operation_type = 'delivery'
        
        # Obtener lotes disponibles según el tipo de operación
        available_lot_ids = None
        if filter_by_location:
            location_to_use = None
            
            if operation_type == 'delivery':
                # ENTREGA: Buscar lotes en Supp/Existencias
                supplies_location = self.env['stock.location'].search([
                    ('complete_name', 'ilike', 'Supp/Existencias'),
                    ('usage', '=', 'internal'),
                ], limit=1)
                
                if supplies_location:
                    location_to_use = supplies_location
                else:
                    _logger.warning("No se encontró la ubicación Supp/Existencias")
                    return []
                    
            elif operation_type == 'return' and partner_id:
                # DEVOLUCIÓN: Buscar lotes en la ubicación del cliente
                partner = self.env['res.partner'].browse(partner_id)
                customer_location = partner.property_stock_customer
                
                if customer_location:
                    location_to_use = customer_location
                else:
                    _logger.warning("Cliente %s no tiene ubicación configurada", partner.name)
                    return []
            else:
                # Fallback: usar Supp/Existencias si no se especifica
                supplies_location = self.env['stock.location'].search([
                    ('complete_name', 'ilike', 'Supp/Existencias'),
                    ('usage', '=', 'internal'),
                ], limit=1)
                
                if supplies_location:
                    location_to_use = supplies_location
                else:
                    return []
            
            if location_to_use:
                # Obtener todas las ubicaciones hijas
                location_ids = self.env['stock.location'].search([
                    ('id', 'child_of', location_to_use.id)
                ]).ids
                
                # Buscar quants en la ubicación correspondiente con cantidad > 0
                quants = self.env['stock.quant'].search([
                    ('location_id', 'in', location_ids),
                    ('quantity', '>', 0),
                    ('lot_id', '!=', False),
                ])
                
                # Obtener IDs únicos de lotes disponibles
                available_lot_ids = list(set(quants.mapped('lot_id').ids))
                
                if not available_lot_ids:
                    _logger.debug("No hay lotes disponibles en la ubicación seleccionada")
                    return []
        
        # Si hay un término de búsqueda, buscar en múltiples campos
        # Buscar en: inventory_plate, name (número de serie), y display_contact_id (contacto)
        if name and name.strip():
            search_term = name.strip()
            
            # Búsqueda normal: buscar en múltiples campos
            # Buscar contactos que coincidan con el término de búsqueda
            partner_ids = []
            try:
                partners = self.env['res.partner'].search([
                    '|',
                    ('name', operator, search_term),
                    ('display_name', operator, search_term)
                ], limit=100)
                partner_ids = partners.ids
            except Exception:
                pass
            
            # Construir dominio de búsqueda: inventory_plate, name, o display_contact_id
            search_domain = [
                '|', '|',
                ('inventory_plate', operator, search_term),  # Buscar en placa de inventario
                ('name', operator, search_term),  # Buscar en número de serie
            ]
            
            # Si se encontraron contactos, agregar búsqueda por contacto
            if partner_ids:
                search_domain.append(('display_contact_id', 'in', partner_ids))
            else:
                # Si no se encontraron contactos, aún buscar por display_contact_id.name
                search_domain.append(('display_contact_id.name', operator, search_term))
            
            # Si hay filtro de ubicación, aplicarlo directamente
            if available_lot_ids is not None:
                location_filter = [('id', 'in', available_lot_ids)]
                domain = ['&'] + search_domain + location_filter
            else:
                # Si no hay filtro de ubicación, usar args si existen
                if args:
                    domain = ['&'] + search_domain + args
                else:
                    domain = search_domain
            
            _logger.debug("Búsqueda de lotes - name: %s, operation_type: %s, available_lots: %d, partners: %d", 
                         name, operation_type, len(available_lot_ids) if available_lot_ids else 0, len(partner_ids))
            
            # Llamar al método padre con name='' porque ya construimos el dominio completo
            return super(StockLot, self)._name_search(name='', args=domain, operator=operator, limit=limit, order=order)
        
        # Si no hay término de búsqueda, aplicar solo filtros de ubicación
        if available_lot_ids is not None:
            domain = [('id', 'in', available_lot_ids)]
            return super(StockLot, self)._name_search(name='', args=domain, operator=operator, limit=limit, order=order)
        
        # Si no hay filtro de ubicación ni búsqueda, usar método padre normal
        return super(StockLot, self)._name_search(name=name, args=args, operator=operator, limit=limit, order=order)
    
    def action_open_quant_editor(self):
        """Abrir wizard para actualizar cantidad de inventario con este lote."""
        self.ensure_one()
        
        # Verificar que el lote esté guardado (tenga ID)
        if not self.id or (hasattr(self, '_origin') and self._origin.id == False):
            raise UserError(_('Debe guardar el lote primero antes de actualizar la cantidad.'))
        
        # Buscar ubicación Supp/Existencias por defecto
        supplies_location = self.env['stock.location'].search([
            ('complete_name', 'ilike', 'Supp/Existencias'),
            ('usage', '=', 'internal'),
        ], limit=1)
        
        # Construir contexto con TODA la información necesaria
        context = {
            'default_lot_id': self.id,
            'default_location_id': supplies_location.id if supplies_location else False,
            'active_id': self.id,
            'active_model': 'stock.lot',
        }
        
        # CRÍTICO: Agregar producto SIEMPRE si existe
        if self.product_id:
            context['default_product_id'] = self.product_id.id
            _logger.info("Abriendo wizard con lote %s y producto %s", self.name, self.product_id.name)
        else:
            _logger.warning("Lote %s no tiene producto asignado", self.name)
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Actualizar Cantidad de Inventario'),
            'res_model': 'quant.editor.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
        }

    @api.model
    def domain_stock_lot_pending_information(self):
        """Mismo criterio que la acción «Productos Pendientes de Información» (lista + badge)."""
        return [('invdash_pending_info', '=', True)]

    @api.model
    def _refresh_invdash_pending_fields(self):
        """Recalcula campos almacenados usados por la vista de pendientes.

        Útil cuando cantidad/ubicación se actualiza por SQL directo (fuera del ORM),
        porque los depends de campos store=True no se disparan automáticamente.
        """
        # IMPORTANTE rendimiento:
        # no recorrer todo el inventario al abrir la vista (puede bloquear).
        # Recalcular solo los lotes actualmente marcados como pendientes.
        lot_ids = self.search([('invdash_pending_info', '=', True)]).ids
        if not lot_ids:
            return

        batch_size = 300
        for i in range(0, len(lot_ids), batch_size):
            batch_ids = lot_ids[i:i + batch_size]
            lots = self.browse(batch_ids)
            lots._compute_display_location_contact()
            lots._compute_is_stock_in_supp_existencias()
            lots._compute_invdash_pending_info()

    @api.model
    def action_open_incomplete_fields_refreshed(self):
        """Abre la vista de pendientes forzando refresh previo de campos store."""
        self._refresh_invdash_pending_fields()
        return self.env['ir.actions.act_window']._for_xml_id(
            'inventory_dashboard_simple.action_stock_lot_incomplete_fields'
        )

    @api.model
    def incomplete_pending_information_count(self):
        """Conteo para badge en menú Inventario → Dashboard → Consultas."""
        return self.env['stock.lot'].search_count(self.domain_stock_lot_pending_information())

    @api.model
    def domain_stock_lot_serial_multi_location(self):
        """Mismo criterio que la acción «Series en varias ubicaciones»."""
        return [('invdash_serial_multi_location', '=', True)]

    @api.model
    def serial_multi_location_count(self):
        """Conteo para badge de «Series en varias ubicaciones»."""
        return self.env['stock.lot'].search_count(self.domain_stock_lot_serial_multi_location())

    @api.model
    def dashboard_queries_badge_counts(self):
        """Conteos de consultas del dashboard para pintar badges del menú."""
        pending = self.incomplete_pending_information_count()
        serial_multi = self.serial_multi_location_count()
        excess_qty = self.env['stock.quant'].search_count([('quantity', '>', 1)])
        delivery_billing = self.env['stock.picking'].delivery_route_billing_pending_count()
        return {
            'pending_info': pending,
            'serial_multi_location': serial_multi,
            'excess_quantity': excess_qty,
            'delivery_billing': delivery_billing,
            'dashboard_total': pending + serial_multi + excess_qty + delivery_billing,
        }