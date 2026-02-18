# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
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
        store=False,
        help='Ubicación actual del lote (desde quants)'
    )
    
    display_contact_id = fields.Many2one(
        'res.partner',
        string='Contacto',
        compute='_compute_display_location_contact',
        store=True,
        help='Contacto asociado a la ubicación del lote'
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
    
    @api.depends('quant_ids', 'quant_ids.location_id', 'quant_ids.quantity', 'quant_ids.location_id.complete_name')
    def _compute_display_location_contact(self):
        """Calcular ubicación y contacto desde los quants del lote."""
        for lot in self:
            lot.display_location_id = False
            lot.display_contact_id = False
            
            if not lot.id:
                continue
            
            # Buscar el quant con mayor cantidad en ubicación interna
            quant = self.env['stock.quant'].search([
                ('lot_id', '=', lot.id),
                ('quantity', '>', 0),
                ('location_id.usage', '=', 'internal'),
            ], order='quantity desc, in_date desc', limit=1)
            
            if quant and quant.location_id:
                lot.display_location_id = quant.location_id
                
                # Buscar contacto desde la ubicación
                # Buscar contacto desde property_stock_customer (ubicación del cliente)
                partner = self.env['res.partner'].search([
                    ('property_stock_customer', '=', quant.location_id.id)
                ], limit=1)
                if partner:
                    lot.display_contact_id = partner
                # Si no se encuentra por property_stock_customer, intentar buscar por owner_id del quant
                elif hasattr(quant, 'owner_id') and quant.owner_id:
                    lot.display_contact_id = quant.owner_id
    
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

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, order=None):
        """Permitir búsqueda por número de serie y placa de inventario, con filtro de ubicación según el contexto.
        
        Basado en la implementación de mesa_ayuda_inventario/models/customer_inventory_lot.py
        """
        if args is None:
            args = []
        
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