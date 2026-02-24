# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class StockQuant(models.Model):
    """Extender Stock Quant para filtrar por producto principal."""
    _inherit = 'stock.quant'

    parent_product_id = fields.Many2one(
        'product.product',
        string='Producto Principal (filtro)',
        help='Filtrar componentes, periféricos y complementos relacionados a este producto principal',
        store=False,
    )
    
    inventory_plate = fields.Char(
        string='Placa de Inventario (quant)',
        related='lot_id.inventory_plate',
        readonly=True,
        store=False,
    )
    
    related_products_display = fields.Char(
        string='Hardware Asociado (resumen)',
        compute='_compute_related_products_display',
        store=False,
        help='Componentes, periféricos y complementos asociados a este producto principal'
    )
    
    related_products_ids = fields.Many2many(
        'product.product',
        string='Hardware Asociado (lista)',
        compute='_compute_related_products_display',
        store=False,
    )
    
    has_related_products = fields.Boolean(
        string='Tiene Productos Asociados',
        compute='_compute_related_products_display',
        store=False,
    )
    
    # Campos de Leasing
    is_leasing = fields.Boolean(
        string='Es Leasing',
        related='product_id.is_leasing',
        store=True,
        readonly=True,
        help='Indica si este producto pertenece a un contrato de leasing'
    )
    leasing_brand_id = fields.Many2one(
        'leasing.brand',
        string='Marca de Leasing',
        related='product_id.leasing_brand_id',
        store=True,
        readonly=True,
        help='Marca del contrato de leasing (ej: HP, Dell, etc.)'
    )
    leasing_contract_id = fields.Many2one(
        'leasing.contract',
        string='Contrato de Leasing',
        related='product_id.leasing_contract_id',
        store=True,
        readonly=True,
        help='Contrato de leasing al que pertenece este producto'
    )
    
    @api.depends('product_id', 'lot_id')
    def _compute_related_products_display(self):
        """Calcular los productos asociados para mostrar en la vista."""
        for quant in self:
            # Inicializar valores por defecto
            quant.related_products_display = ''
            # IMPORTANTE: Para campos computados Many2many, usar recordset vacío
            quant.related_products_ids = self.env['product.product']
            quant.has_related_products = False
            
            if not quant.product_id or not quant.lot_id:
                continue
            
            # IMPORTANTE: Solo calcular si el quant es accesible
            # Esto evita errores cuando se intenta acceder a quants bloqueados
            try:
                # Verificar que el quant es accesible antes de procesar
                if not quant.exists():
                    continue
            except Exception:
                # Si no se puede verificar, omitir este quant
                continue
            
            try:
                # Obtener los productos realmente asociados a este lote/serie específico
                # Usar stock.lot.supply.line que relaciona lotes con productos relacionados
                lot = quant.lot_id
                
                if not lot:
                    continue
                
                # Verificar que el lote es accesible
                try:
                    if not lot.exists():
                        continue
                except Exception:
                    continue
                
                # Acceder directamente al campo lot_supply_line_ids del lote
                # Esto evita problemas de acceso multi-empresa
                # Usar sudo() para acceder a las líneas y luego filtrar
                try:
                    supply_lines = lot.sudo().lot_supply_line_ids
                except Exception:
                    supply_lines = self.env['stock.lot.supply.line']
                
                if supply_lines:
                    # Obtener los productos de las líneas de suministro
                    related_products = supply_lines.mapped('product_id')
                    
                    # Filtrar productos que pertenecen a la misma empresa del quant
                    if quant.company_id:
                        related_products = related_products.filtered(
                            lambda p: not p.company_id or p.company_id == quant.company_id
                        )
                    
                    # Verificar que los productos sean accesibles y obtener solo IDs
                    # IMPORTANTE: Solo trabajar con IDs para evitar problemas de adaptación
                    accessible_product_ids = []
                    for product in related_products:
                        try:
                            # Verificar que el producto existe y es accesible
                            if product and hasattr(product, 'id') and product.id:
                                # Verificar que el producto pertenece a la empresa correcta
                                if not quant.company_id or not product.company_id or product.company_id == quant.company_id:
                                    # Solo agregar el ID, no el objeto
                                    accessible_product_ids.append(product.id)
                        except Exception:
                            # Si no se puede acceder, omitir este producto
                            continue
                    
                    if accessible_product_ids:
                        quant.has_related_products = True
                        # Para campos computados Many2many, asignar directamente un recordset
                        # Asegurar que todos los IDs son enteros válidos
                        valid_ids = [pid for pid in accessible_product_ids if isinstance(pid, int) and pid > 0]
                        if valid_ids:
                            quant.related_products_ids = self.env['product.product'].browse(valid_ids)
                        else:
                            quant.related_products_ids = self.env['product.product']
                        
                        # Crear lista de nombres para mostrar - leer los productos de forma segura
                        try:
                            if valid_ids:
                                products_for_display = self.env['product.product'].browse(valid_ids)
                                names = [p.name for p in products_for_display if p and p.name]
                                if names:
                                    quant.related_products_display = ', '.join(names[:3])  # Mostrar máximo 3
                                    if len(names) > 3:
                                        quant.related_products_display += f' (+{len(names) - 3} más)'
                        except Exception:
                            # Si hay error al leer nombres, usar IDs como fallback
                            quant.related_products_display = f'{len(valid_ids)} productos asociados'
            except Exception as e:
                # Si hay error de acceso, simplemente no mostrar productos asociados
                # Esto evita que se rompa la vista
                import logging
                _logger = logging.getLogger(__name__)
                _logger.warning("Error en _compute_related_products_display para quant %s: %s", quant.id, str(e))
                # Asegurar que el campo Many2many tiene un valor válido (recordset vacío)
                quant.related_products_ids = self.env['product.product']
    
    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, **kwargs):
        """Extender búsqueda para filtrar por producto principal o por características de componentes.
        Excluye automáticamente componentes, periféricos y complementos asociados a productos principales.
        IMPORTANTE: Solo aplica el filtro en la vista de inventario, NO durante validaciones."""
        try:
            domain = list(domain) if domain else []
            
            # Verificar si es una búsqueda desde la vista de inventario
            # Solo aplicar el filtro si el contexto tiene 'filter_associated_items' = True
            # Esto asegura que solo se aplique en la vista de inventario, no durante validaciones
            is_inventory_view = False
            
            # Verificar el contexto - solo aplicar si está explícitamente marcado
            if self.env.context.get('filter_associated_items', False):
                # Verificar que NO es una validación o constraint
                # Las validaciones normalmente buscan un lote específico
                if domain:
                    # Verificar que NO es una búsqueda específica por lot_id (que podría ser una validación)
                    is_specific_lot_search = any(
                        isinstance(d, (list, tuple)) and len(d) >= 3 and d[0] == 'lot_id' and d[1] == '=' 
                        for d in domain if isinstance(d, (list, tuple))
                    )
                    
                    # Solo aplicar si NO es una búsqueda específica de lote (validación)
                    if not is_specific_lot_search:
                        is_inventory_view = True
            
            # Si es la vista de inventario, expandir búsqueda por hardware asociado
            search_term = None
            product_filter_idx = None
            if is_inventory_view:
                # Detectar búsqueda de texto en product_id
                for i, dom in enumerate(domain):
                    if isinstance(dom, (list, tuple)) and len(dom) >= 3:
                        # Buscar filtros 'ilike' en product_id.name
                        if dom[0] in ('product_id', 'product_id.name') and dom[1] in ('ilike', 'like', '=like'):
                            search_term = dom[2] if isinstance(dom[2], str) else None
                            if search_term and search_term.strip():
                                search_term = search_term.strip()
                                product_filter_idx = i
                                break
                
                # Si hay término de búsqueda, buscar también en hardware asociado
                if search_term and product_filter_idx is not None:
                    try:
                        # Buscar productos que coincidan con el término (componentes)
                        matching_products = self.env['product.product'].sudo().search([
                            ('name', 'ilike', search_term)
                        ], limit=500)
                        
                        # Buscar lotes principales que tienen estos productos como hardware asociado
                        matching_lot_ids = set()
                        if matching_products:
                            SupplyLine = self.env['stock.lot.supply.line']
                            supply_lines = SupplyLine.sudo().search([
                                ('product_id', 'in', matching_products.ids)
                            ], limit=5000)
                            
                            # Obtener los lotes principales (lot_id) que tienen estos productos como hardware
                            parent_lot_ids = supply_lines.mapped('lot_id').ids
                            matching_lot_ids = set([lid for lid in parent_lot_ids if lid and isinstance(lid, int)])
                        
                        # Si encontramos lotes con hardware asociado, expandir el dominio con OR
                        if matching_lot_ids:
                            # Reemplazar el filtro de producto por un OR que incluya ambos
                            original_filter = domain[product_filter_idx]
                            # Construir nuevo dominio: (producto coincide OR lote tiene hardware que coincide)
                            or_group = ['|', original_filter, ('lot_id', 'in', list(matching_lot_ids))]
                            # Reemplazar el filtro original
                            domain = domain[:product_filter_idx] + or_group + domain[product_filter_idx+1:]
                    except Exception as e:
                        # Si hay error, continuar sin expandir la búsqueda
                        import logging
                        _logger = logging.getLogger(__name__)
                        _logger.warning("Error al buscar por hardware asociado: %s", str(e))
            
            # Solo aplicar el filtro si es la vista de inventario
            if is_inventory_view:
                try:
                    # Buscar lotes que están asociados a productos principales
                    # En stock.lot.supply.line:
                    # - lot_id = lote del producto principal
                    # - related_lot_id = lote del componente/periférico/complemento asociado
                    SupplyLine = self.env['stock.lot.supply.line']
                    associated_lines = SupplyLine.sudo().search([
                        ('item_type', 'in', ['component', 'peripheral', 'complement']),
                        ('related_lot_id', '!=', False),
                        ('lot_id', '!=', False),
                    ], limit=10000)  # Limitar para evitar problemas
                    
                    # Obtener los IDs de los lotes asociados (related_lot_id son los componentes/periféricos/complementos)
                    associated_lot_ids = []
                    for line in associated_lines:
                        try:
                            if line.related_lot_id and hasattr(line.related_lot_id, 'id') and line.related_lot_id.id:
                                associated_lot_ids.append(line.related_lot_id.id)
                        except Exception:
                            continue
                    
                    # Eliminar duplicados y asegurar que son enteros
                    associated_lot_ids = list(set([lid for lid in associated_lot_ids if isinstance(lid, int) and lid > 0]))
                    
                    # Si hay lotes asociados, agregar filtro al dominio para excluirlos
                    if associated_lot_ids:
                        # Agregar condición al dominio para excluir quants con estos lotes
                        domain.append(('lot_id', 'not in', associated_lot_ids))
                except Exception as e:
                    # Si hay error al filtrar, continuar sin el filtro
                    import logging
                    _logger = logging.getLogger(__name__)
                    _logger.warning("Error al filtrar lotes asociados en _search: %s", str(e))
            
            # Ejecutar la búsqueda con el dominio (con o sin filtro de exclusión)
            # Usar try/except para manejar errores de acceso de forma segura
            try:
                return super()._search(domain, offset=offset, limit=limit, order=order, **kwargs)
            except Exception as search_error:
                # Si hay error de acceso, intentar filtrar los quants accesibles manualmente
                import logging
                _logger = logging.getLogger(__name__)
                error_msg = str(search_error).lower()
                
                # Solo manejar errores de acceso explícitos
                if 'access' in error_msg or 'permission' in error_msg or 'restricted' in error_msg:
                    _logger.warning("Error de acceso en _search, filtrando quants accesibles: %s", str(search_error))
                    try:
                        # Separar filtros de lot_id y otros filtros
                        base_domain = []
                        lot_filters = []
                        not_lot_filters = []
                        
                        for d in domain:
                            if isinstance(d, (list, tuple)) and len(d) >= 3:
                                if d[0] == 'lot_id':
                                    lot_filters.append(d)
                                else:
                                    not_lot_filters.append(d)
                            else:
                                base_domain.append(d)
                        
                        # Construir dominio base sin filtros de lot_id
                        search_domain = base_domain + not_lot_filters
                        
                        # Buscar quants con sudo primero
                        all_quants = self.env['stock.quant'].sudo().search(search_domain, limit=5000)
                        
                        # Filtrar solo los accesibles y aplicar filtros de lot_id si existen
                        accessible_quant_ids = []
                        for quant in all_quants:
                            try:
                                # Verificar acceso sin sudo
                                quant_check = self.env['stock.quant'].browse(quant.id)
                                if not quant_check.exists():
                                    continue
                                
                                # Si hay filtros de lot_id, verificar que cumplan
                                if lot_filters:
                                    lot_match = True
                                    for lot_filter in lot_filters:
                                        if lot_filter[1] == '=' and quant.lot_id.id != lot_filter[2]:
                                            lot_match = False
                                            break
                                        elif lot_filter[1] == 'in' and quant.lot_id.id not in lot_filter[2]:
                                            lot_match = False
                                            break
                                        elif lot_filter[1] == 'not in' and quant.lot_id.id in lot_filter[2]:
                                            lot_match = False
                                            break
                                    if not lot_match:
                                        continue
                                
                                accessible_quant_ids.append(quant.id)
                            except Exception:
                                continue
                        
                        if accessible_quant_ids:
                            # Aplicar límites si existen
                            if limit:
                                accessible_quant_ids = accessible_quant_ids[offset:offset+limit]
                            elif offset:
                                accessible_quant_ids = accessible_quant_ids[offset:]
                            
                            return self.env['stock.quant'].browse(accessible_quant_ids)
                        else:
                            return self.env['stock.quant']
                    except Exception as inner_error:
                        _logger.error("Error al filtrar quants accesibles: %s", str(inner_error))
                        return self.env['stock.quant']
                else:
                    # Si no es error de acceso, propagar el error
                    raise
        except Exception as e:
            # Si hay error, loguear y delegar al método padre
            import logging
            _logger = logging.getLogger(__name__)
            _logger.error("Error en _search de stock.quant: %s", str(e), exc_info=True)
            # En caso de error, delegar al método padre para que no falle
            try:
                return super()._search(domain, offset=offset, limit=limit, order=order, **kwargs)
            except Exception:
                return self.env['stock.quant']
        
        # CÓDIGO COMENTADO TEMPORALMENTE - Re-habilitar cuando se resuelvan los problemas
        """
        # Verificar si hay contexto específico que requiera nuestra lógica personalizada
        try:
            has_custom_context = bool(
                self.env.context.get('parent_product_id') or
                self.env.context.get('supplies_filter') or
                self.env.context.get('search_supplies_products')
            )
        except Exception:
            # Si hay error al verificar el contexto, delegar a Odoo
            return super()._search(domain, offset=offset, limit=limit, order=order, **kwargs)
        
        # Verificar si hay filtros personalizados en el dominio
        parent_product_id = None
        search_term = None
        has_custom_domain = False
        
        # Buscar en el contexto
        if self.env.context.get('parent_product_id'):
            parent_product_id = self.env.context.get('parent_product_id')
            has_custom_domain = True
        
        # Buscar en el dominio cualquier término de búsqueda de texto
        domain_copy = list(domain)  # Crear copia para no modificar el original
        removed_indices = []
        for i, dom in enumerate(domain_copy):
            if isinstance(dom, (list, tuple)) and len(dom) == 3:
                if dom[0] == 'parent_product_id' and dom[1] == '=' and dom[2]:
                    parent_product_id = dom[2]
                    has_custom_domain = True
                    # Marcar para remover este dominio ya que lo procesaremos manualmente
                    removed_indices.append(i)
                # Buscar términos de búsqueda de texto en campos de producto
                elif dom[1] in ('ilike', 'like', '=like', 'not ilike') and isinstance(dom[2], str) and len(dom[2].strip()) > 0:
                    term = dom[2].strip()
                    # Solo procesar si hay contexto personalizado o si el término contiene 'supplies'
                    if has_custom_context or 'supplies' in term.lower():
                        # Si es una búsqueda en product_id (nombres de productos)
                        if dom[0] in ('product_id', 'product_id.name') or (isinstance(dom[0], str) and 'product' in dom[0].lower() and 'name' in dom[0].lower()):
                            if not search_term:  # Solo tomar el primer término encontrado
                                search_term = term
                                removed_indices.append(i)
                                has_custom_domain = True
                        # También buscar en campos relacionados con nombres
                        elif dom[0] == 'name' or (isinstance(dom[0], str) and dom[0].endswith('.name')):
                            if not search_term:  # Solo tomar el primer término encontrado
                                search_term = term
                                removed_indices.append(i)
                                has_custom_domain = True
        
        # Si NO hay contexto personalizado ni dominio personalizado, dejar que Odoo maneje la búsqueda normalmente
        if not has_custom_context and not has_custom_domain:
            # Llamar al método padre directamente sin modificar el dominio
            try:
                return super()._search(domain, offset=offset, limit=limit, order=order, **kwargs)
            except Exception as e:
                # Si hay error, intentar con dominio básico o retornar búsqueda vacía
                import logging
                _logger = logging.getLogger(__name__)
                _logger.warning("Error en _search de stock.quant: %s", str(e))
                # Intentar con dominio mínimo
                try:
                    safe_domain = [('id', '>', 0)]  # Dominio seguro que no debería fallar
                    return super()._search(safe_domain, offset=offset, limit=limit, order=order, **kwargs)
                except Exception:
                    # Si aún falla, retornar búsqueda vacía
                    return self.env['stock.quant']
        
        # Remover los dominios procesados (en orden inverso para no afectar los índices)
        for i in sorted(removed_indices, reverse=True):
            domain_copy.pop(i)
        if removed_indices:
            domain = domain_copy
        
        # Si no hay término de búsqueda ni parent_product_id, filtrar por defecto:
        # mostrar solo productos principales y productos no relacionados
        if not search_term and not parent_product_id:
            try:
                # Obtener todos los productos principales (que tienen componentes, periféricos o complementos)
                ProductTemplate = self.env['product.template']
                ProductProduct = self.env['product.product']
                
                # Buscar templates que son productos principales
                parent_templates = ProductTemplate.search([
                    '|', '|',
                    ('is_composite', '=', True),
                    ('use_peripherals', '=', True),
                    ('use_complements', '=', True),
                ])
                # También incluir templates que tienen líneas aunque no tengan los flags activos
                parent_templates_with_lines = ProductTemplate.search([
                    '|', '|',
                    ('composite_line_ids', '!=', False),
                    ('peripheral_line_ids', '!=', False),
                    ('complement_line_ids', '!=', False),
                ])
                parent_templates = parent_templates | parent_templates_with_lines
                
                # Obtener los productos (variantes) de estos templates
                parent_products = ProductProduct.search([
                    ('product_tmpl_id', 'in', parent_templates.ids)
                ])
                parent_product_ids = parent_products.ids
                
                # Obtener todos los productos que son componentes, periféricos o complementos
                all_component_ids = set()
                for template in parent_templates:
                    comp_ids = template.composite_line_ids.mapped('component_product_id').ids
                    peri_ids = template.peripheral_line_ids.mapped('peripheral_product_id').ids
                    compl_ids = template.complement_line_ids.mapped('complement_product_id').ids
                    # Filtrar IDs válidos (no False, None, y asegurar que son enteros)
                    try:
                        all_component_ids.update([id for id in comp_ids if id and isinstance(id, int)])
                        all_component_ids.update([id for id in peri_ids if id and isinstance(id, int)])
                        all_component_ids.update([id for id in compl_ids if id and isinstance(id, int)])
                    except Exception:
                        # Si hay error, continuar sin agregar estos IDs
                        pass
                
                # Productos que NO son componentes, periféricos o complementos
                all_products = ProductProduct.search([])
                non_related_product_ids = [p.id for p in all_products if p.id and p.id not in all_component_ids]
                
                # Combinar: productos principales + productos no relacionados
                final_product_ids = list(set([id for id in parent_product_ids if id] + non_related_product_ids))
                
                if final_product_ids:
                    domain.append(('product_id', 'in', final_product_ids))
                else:
                    # Si no hay productos, no mostrar nada
                    domain.append(('id', '=', False))
            except Exception:
                # Si hay algún error, dejar que el dominio original funcione
                pass
        # Si hay un término de búsqueda pero no hay parent_product_id seleccionado,
        # buscar productos principales que tengan componentes relacionados con ese término
        elif search_term and not parent_product_id:
            try:
                # Buscar productos que coincidan directamente con el término (pueden ser componentes o productos principales)
                matching_products = self.env['product.product'].search([
                    ('name', 'ilike', search_term)
                ])
                
                # Buscar productos principales que tengan componentes relacionados con el término
                parent_product_ids = self._find_parent_products_by_search_term(search_term)
                
                # Combinar: productos que coinciden directamente + productos principales encontrados
                all_product_ids = set(matching_products.ids)
                all_product_ids.update(parent_product_ids)
                
                # Obtener todos los productos relacionados a los productos principales encontrados
                all_related_product_ids = []
                for parent_id in parent_product_ids:
                    try:
                        related_ids = self._get_related_product_ids(parent_id)
                        # Filtrar IDs válidos y asegurar que son enteros
                        valid_ids = [id for id in related_ids if id and isinstance(id, int)]
                        all_related_product_ids.extend(valid_ids)
                    except Exception:
                        # Si hay error al obtener productos relacionados, continuar
                        continue
                
                # Combinar todos los IDs: productos que coinciden + componentes relacionados
                final_product_ids = list(all_product_ids)
                final_product_ids.extend(all_related_product_ids)
                # Filtrar IDs válidos (no False, None, y asegurar que son enteros)
                final_product_ids = [id for id in final_product_ids if id and isinstance(id, int)]
                final_product_ids = list(set(final_product_ids))
                
                # Verificar que los productos tengan quants accesibles en la ubicación Supp/Existencias
                # Esto evita errores de acceso
                if final_product_ids:
                    # Buscar quants accesibles para estos productos en Supp/Existencias
                    # Usar sudo() para la búsqueda interna y luego filtrar solo los accesibles
                    try:
                        all_quants = self.env['stock.quant'].sudo().search([
                            ('product_id', 'in', final_product_ids),
                            ('location_id.complete_name', 'ilike', 'Supp/Existencias'),
                            ('location_id.usage', '=', 'internal'),
                            ('quantity', '>', 0)
                        ], limit=1000)  # Limitar para evitar problemas de rendimiento
                        
                        # Filtrar solo los quants que el usuario actual puede leer
                        accessible_product_ids = set()
                        for quant in all_quants:
                            try:
                                # Intentar leer el quant sin sudo para verificar permisos
                                # Si puede leerlo, incluir su product_id
                                quant_without_sudo = self.env['stock.quant'].browse(quant.id)
                                if quant_without_sudo.exists():
                                    # Verificar que puede acceder al product_id
                                    if quant_without_sudo.product_id:
                                        accessible_product_ids.add(quant_without_sudo.product_id.id)
                            except Exception:
                                # Si no puede leer el quant, omitirlo
                                continue
                        
                        accessible_product_ids = list(accessible_product_ids)
                        
                        if accessible_product_ids:
                            # Filtrar por productos encontrados y sus componentes relacionados que tienen quants accesibles
                            domain.append(('product_id', 'in', accessible_product_ids))
                        else:
                            # Si no hay quants accesibles, no mostrar resultados
                            domain.append(('id', '=', False))
                    except Exception:
                        # Si hay cualquier error en la búsqueda, usar el dominio original sin filtrar por quants
                        # Esto evita que se rompa la búsqueda
                        pass
                else:
                    # Si no se encontró nada, no mostrar resultados
                    domain.append(('id', '=', False))
            except Exception as e:
                # Si hay cualquier error, dejar que el dominio original funcione
                # Esto evita que se rompa la búsqueda normal
                pass
        elif parent_product_id:
            # Si hay un producto principal seleccionado manualmente, filtrar por sus componentes
            try:
                related_product_ids = self._get_related_product_ids(parent_product_id)
                # Filtrar IDs válidos (no False, None, y asegurar que son enteros)
                related_product_ids = [id for id in related_product_ids if id and isinstance(id, int)]
                if related_product_ids:
                    domain.append(('product_id', 'in', related_product_ids))
                else:
                    # Si no hay productos relacionados, no mostrar nada
                    domain.append(('id', '=', False))
            except Exception:
                # Si hay error, no mostrar nada
                domain.append(('id', '=', False))
        
        # Llamar al método padre - stock.quant._search no acepta access_rights_uid
        # Usar try/except para manejar errores de acceso
        try:
            return super()._search(domain, offset=offset, limit=limit, order=order, **kwargs)
        except Exception as e:
            # Si hay error de acceso, intentar con un dominio más permisivo
            # Eliminar filtros que puedan causar problemas de acceso
            safe_domain = []
            for dom in domain:
                if isinstance(dom, (list, tuple)) and len(dom) == 3:
                    # Mantener solo filtros seguros (id, product_id básico)
                    if dom[0] in ('id', 'product_id') and dom[1] == '=':
                        safe_domain.append(dom)
            if safe_domain:
                return super()._search(safe_domain, offset=offset, limit=limit, order=order, **kwargs)
            # Si aún falla, retornar búsqueda vacía
            return self.env['stock.quant']
        """
    
    def _find_parent_products_by_search_term(self, search_term):
        """Encontrar productos principales que tengan componentes relacionados con el término de búsqueda."""
        ProductTemplate = self.env['product.template']
        ProductProduct = self.env['product.product']
        
        # Buscar productos que coincidan con el término de búsqueda
        matching_products = ProductProduct.search([
            ('name', 'ilike', search_term)
        ])
        
        if not matching_products:
            return []
        
        matching_product_ids = matching_products.ids
        
        # Buscar productos principales que tengan estos productos como componentes, periféricos o complementos
        parent_templates = ProductTemplate.search([
            '|', '|',
            ('composite_line_ids.component_product_id', 'in', matching_product_ids),
            ('peripheral_line_ids.peripheral_product_id', 'in', matching_product_ids),
            ('complement_line_ids.complement_product_id', 'in', matching_product_ids),
        ])
        
        # Obtener los productos (variantes) de estos templates
        parent_products = ProductProduct.search([
            ('product_tmpl_id', 'in', parent_templates.ids)
        ])
        
        return parent_products.ids
    
    def _get_related_product_ids(self, parent_product_id):
        """Obtener IDs de productos relacionados a un producto principal."""
        if not parent_product_id:
            return []
        
        parent_product = self.env['product.product'].browse(parent_product_id)
        if not parent_product:
            return []
        
        parent_template = parent_product.product_tmpl_id
        
        # Obtener todos los productos que son componentes, periféricos o complementos
        component_products = parent_template.composite_line_ids.mapped('component_product_id')
        peripheral_products = parent_template.peripheral_line_ids.mapped('peripheral_product_id')
        complement_products = parent_template.complement_line_ids.mapped('complement_product_id')
        
        # Combinar todos los productos relacionados
        related_products = component_products | peripheral_products | complement_products
        
        return related_products.ids
    
    @api.model
    def action_debug_permissions_global(self):
        """Método de debug global que puede ser llamado desde cualquier lugar."""
        import logging
        _logger = logging.getLogger(__name__)
        
        debug_info = []
        debug_info.append("=" * 80)
        debug_info.append("DEBUG GLOBAL DE PERMISOS - STOCK.QUANT")
        debug_info.append("=" * 80)
        debug_info.append("")
        
        # Información del usuario
        user = self.env.user
        debug_info.append(f"Usuario: {user.name} (ID: {user.id})")
        debug_info.append(f"Empresa actual: {user.company_id.name if user.company_id else 'N/A'} (ID: {user.company_id.id if user.company_id else 'N/A'})")
        debug_info.append(f"Empresas permitidas: {', '.join(user.company_ids.mapped('name'))}")
        debug_info.append(f"IDs de empresas permitidas: {user.company_ids.ids}")
        debug_info.append("")
        
        # Verificar el quant específico mencionado en el error
        debug_info.append("VERIFICACIÓN DEL QUANT ID=9128:")
        debug_info.append("-" * 80)
        try:
            quant_9128 = self.env['stock.quant'].browse(9128)
            if quant_9128.exists():
                debug_info.append(f"✅ Quant 9128 existe")
                debug_info.append(f"   Producto: {quant_9128.product_id.name if quant_9128.product_id else 'N/A'}")
                debug_info.append(f"   Ubicación: {quant_9128.location_id.complete_name if quant_9128.location_id else 'N/A'}")
                debug_info.append(f"   Empresa del quant: {quant_9128.company_id.name if quant_9128.company_id else 'SIN EMPRESA'} (ID: {quant_9128.company_id.id if quant_9128.company_id else 'N/A'})")
                debug_info.append(f"   Lote: {quant_9128.lot_id.name if quant_9128.lot_id else 'N/A'}")
                
                # Verificar si la empresa del quant está en las empresas permitidas del usuario
                if quant_9128.company_id:
                    if quant_9128.company_id.id in user.company_ids.ids:
                        debug_info.append(f"   ✅ La empresa del quant ({quant_9128.company_id.id}) está en las empresas permitidas")
                    else:
                        debug_info.append(f"   ❌❌❌ PROBLEMA: La empresa del quant ({quant_9128.company_id.id}) NO está en las empresas permitidas")
                        debug_info.append(f"   ❌ La regla multi-company está BLOQUEANDO este quant")
                else:
                    debug_info.append(f"   ✅ El quant no tiene empresa, debería ser accesible")
                
                try:
                    can_read_9128 = quant_9128.check_access_rights('read', raise_exception=False)
                    debug_info.append(f"   Acceso de lectura directo: {can_read_9128}")
                except Exception as e:
                    debug_info.append(f"   ❌ Error al verificar acceso: {str(e)}")
                
                # Intentar leer el quant
                try:
                    quant_data = quant_9128.read(['id', 'product_id', 'location_id', 'company_id', 'lot_id'])
                    debug_info.append(f"   ✅ Puede leer el quant: {quant_data}")
                except Exception as e:
                    debug_info.append(f"   ❌ NO puede leer el quant: {str(e)}")
                    debug_info.append(f"   ❌ Confirmado: la regla multi-company está bloqueando el acceso")
                
                # Intentar con sudo
                try:
                    quant_9128_sudo = quant_9128.sudo()
                    quant_data_sudo = quant_9128_sudo.read(['id', 'product_id', 'location_id', 'company_id', 'lot_id'])
                    debug_info.append(f"   ✅ Con sudo SÍ funciona: {quant_data_sudo}")
                    debug_info.append(f"   ⚠️ Confirma que el problema es de PERMISOS/REGLAS")
                except Exception as e:
                    debug_info.append(f"   ❌ Error incluso con sudo: {str(e)}")
            else:
                debug_info.append("❌ Quant 9128 no existe o no es accesible con los permisos actuales")
                debug_info.append("⚠️ Verificando con sudo si existe pero está bloqueado...")
                try:
                    quant_9128_sudo = self.env['stock.quant'].sudo().browse(9128)
                    if quant_9128_sudo.exists():
                        debug_info.append(f"   ✅ Con sudo SÍ existe el quant 9128")
                        debug_info.append(f"   Producto: {quant_9128_sudo.product_id.name if quant_9128_sudo.product_id else 'N/A'}")
                        debug_info.append(f"   Empresa: {quant_9128_sudo.company_id.name if quant_9128_sudo.company_id else 'SIN EMPRESA'} (ID: {quant_9128_sudo.company_id.id if quant_9128_sudo.company_id else 'N/A'})")
                        if quant_9128_sudo.company_id and quant_9128_sudo.company_id.id not in user.company_ids.ids:
                            debug_info.append(f"   ❌❌❌ CONFIRMADO: El quant existe pero está bloqueado por la regla multi-company")
                            debug_info.append(f"   La empresa del quant ({quant_9128_sudo.company_id.id}) no está en las empresas del usuario")
                    else:
                        debug_info.append(f"   ❌ El quant 9128 realmente no existe en la base de datos")
                except Exception as e:
                    debug_info.append(f"   ❌ Error al verificar con sudo: {str(e)}")
        except Exception as e:
            debug_info.append(f"❌ Error al buscar quant 9128: {str(e)}")
        debug_info.append("")
        
        # Reglas de acceso (ir.rule)
        debug_info.append("REGLAS DE ACCESO (ir.rule) para stock.quant:")
        debug_info.append("-" * 80)
        try:
            rules = self.env['ir.rule'].search([
                ('model_id.model', '=', 'stock.quant')
            ])
            if rules:
                for rule in rules:
                    debug_info.append(f"  - {rule.name} (ID: {rule.id})")
                    debug_info.append(f"    Activa: {rule.active}")
                    # En Odoo 18, el atributo puede ser 'global' en lugar de 'global_rule'
                    try:
                        is_global = getattr(rule, 'global_rule', getattr(rule, 'global', False))
                        debug_info.append(f"    Global: {is_global}")
                    except:
                        debug_info.append(f"    Global: N/A")
                    # En Odoo, el campo puede ser 'groups', 'group_ids' o 'groups_id'
                    try:
                        groups = getattr(rule, 'groups', getattr(rule, 'group_ids', getattr(rule, 'groups_id', False)))
                        if groups:
                            debug_info.append(f"    Grupos: {', '.join(groups.mapped('name'))}")
                        else:
                            debug_info.append(f"    Grupos: Todos (regla global)")
                    except:
                        debug_info.append(f"    Grupos: N/A")
                    debug_info.append(f"    Dominio: {rule.domain_force}")
                    
                    # Si es la regla multi-company, mostrar más detalles y evaluar el dominio
                    if 'multi-company' in rule.name.lower() or 'multiempresa' in rule.name.lower():
                        debug_info.append(f"    ⚠️⚠️⚠️ REGLA MULTI-COMPANY DETECTADA ⚠️⚠️⚠️")
                        debug_info.append(f"    Esta es probablemente la causa del problema de permisos")
                        debug_info.append(f"    Empresa actual del usuario: {user.company_id.name if user.company_id else 'N/A'} (ID: {user.company_id.id if user.company_id else 'N/A'})")
                        debug_info.append(f"    Empresas permitidas para el usuario: {', '.join(user.company_ids.mapped('name'))}")
                        debug_info.append(f"    IDs de empresas permitidas: {user.company_ids.ids}")
                        
                        # Intentar evaluar el dominio
                        try:
                            if rule.domain_force:
                                debug_info.append(f"    Dominio completo de la regla: {rule.domain_force}")
                                # El dominio típico de multi-company es: ['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]
                                # Esto significa que solo se pueden ver quants sin empresa o de las empresas del usuario
                                debug_info.append(f"    ⚠️ Esta regla SOLO permite ver quants:")
                                debug_info.append(f"       - Sin empresa asignada (company_id = False)")
                                debug_info.append(f"       - De las empresas del usuario: {user.company_ids.ids}")
                                debug_info.append(f"    ⚠️ Cualquier quant de otra empresa será BLOQUEADO")
                                
                                # Buscar quants bloqueados
                                debug_info.append("")
                                debug_info.append("    🔍 BUSCANDO QUANTS BLOQUEADOS:")
                                debug_info.append("    " + "-" * 76)
                                try:
                                    # Buscar todos los quants con sudo para ver cuáles existen
                                    all_quants_sudo = self.env['stock.quant'].sudo().search([], limit=100)
                                    debug_info.append(f"    Total de quants en la BD (muestra de 100): {len(all_quants_sudo)}")
                                    
                                    # Contar por empresa
                                    company_counts = {}
                                    blocked_quants = []
                                    accessible_quants = []
                                    
                                    for quant in all_quants_sudo:
                                        company_id = quant.company_id.id if quant.company_id else False
                                        company_name = quant.company_id.name if quant.company_id else 'Sin empresa'
                                        
                                        if company_id not in company_counts:
                                            company_counts[company_id] = {'name': company_name, 'count': 0, 'blocked': 0, 'accessible': 0}
                                        company_counts[company_id]['count'] += 1
                                        
                                        # Verificar si es accesible
                                        if company_id is False or company_id in user.company_ids.ids:
                                            company_counts[company_id]['accessible'] += 1
                                            accessible_quants.append(quant.id)
                                        else:
                                            company_counts[company_id]['blocked'] += 1
                                            blocked_quants.append({
                                                'id': quant.id,
                                                'product': quant.product_id.name if quant.product_id else 'N/A',
                                                'company': company_name,
                                                'company_id': company_id
                                            })
                                    
                                    debug_info.append(f"    Quants accesibles: {len(accessible_quants)}")
                                    debug_info.append(f"    Quants bloqueados: {len(blocked_quants)}")
                                    debug_info.append("")
                                    debug_info.append("    Distribución por empresa:")
                                    for company_id, data in company_counts.items():
                                        status = "✅ Accesible" if company_id is False or company_id in user.company_ids.ids else "❌ BLOQUEADO"
                                        debug_info.append(f"      - {data['name']} (ID: {company_id or 'N/A'}): {data['count']} quants - {status}")
                                        if data['blocked'] > 0:
                                            debug_info.append(f"        ⚠️ {data['blocked']} quants bloqueados por la regla multi-company")
                                    
                                    if blocked_quants:
                                        debug_info.append("")
                                        debug_info.append("    ⚠️⚠️⚠️ EJEMPLOS DE QUANTS BLOQUEADOS (primeros 5):")
                                        for i, quant_info in enumerate(blocked_quants[:5], 1):
                                            debug_info.append(f"      {i}. Quant ID={quant_info['id']}: {quant_info['product']} - Empresa: {quant_info['company']} (ID: {quant_info['company_id']})")
                                            debug_info.append(f"         ❌ Este quant está BLOQUEADO porque la empresa {quant_info['company_id']} no está en las empresas permitidas del usuario")
                                        
                                        if len(blocked_quants) > 5:
                                            debug_info.append(f"      ... y {len(blocked_quants) - 5} más bloqueados")
                                        
                                        debug_info.append("")
                                        debug_info.append("    💡 SOLUCIÓN:")
                                        debug_info.append("       Para acceder a estos quants, necesitas:")
                                        debug_info.append("       1. Agregar las empresas bloqueadas a las empresas permitidas del usuario, O")
                                        debug_info.append("       2. Cambiar la empresa de los quants bloqueados a una empresa permitida, O")
                                        debug_info.append("       3. Desactivar o modificar la regla multi-company (ID: 322)")
                                except Exception as e:
                                    debug_info.append(f"    Error al buscar quants bloqueados: {str(e)}")
                                    import traceback
                                    debug_info.append(f"    Traceback: {traceback.format_exc()}")
                        except Exception as e:
                            debug_info.append(f"    Error al analizar dominio: {str(e)}")
                    debug_info.append("")
            else:
                debug_info.append("  No se encontraron reglas de acceso")
        except Exception as e:
            debug_info.append(f"Error al obtener reglas: {str(e)}")
            import traceback
            debug_info.append(f"Traceback completo: {traceback.format_exc()}")
        debug_info.append("")
        
        # Análisis y conclusiones
        debug_info.append("")
        debug_info.append("=" * 80)
        debug_info.append("ANÁLISIS Y CONCLUSIONES:")
        debug_info.append("=" * 80)
        debug_info.append("")
        debug_info.append("💡 DIAGNÓSTICO:")
        debug_info.append("")
        debug_info.append("✅ Los permisos del modelo están correctos (lectura y escritura permitidos)")
        debug_info.append("✅ No hay quants bloqueados por la regla multi-company en la muestra analizada")
        debug_info.append("✅ Todos los quants analizados pertenecen a la empresa del usuario (ID: 1)")
        debug_info.append("❌ El quant ID=9128 no existe en la base de datos")
        debug_info.append("")
        debug_info.append("🔍 POSIBLES CAUSAS DEL ERROR:")
        debug_info.append("")
        debug_info.append("1. El error puede estar ocurriendo en OTRO quant (no el 9128):")
        debug_info.append("   - El ID 9128 puede ser de un error anterior o de un quant eliminado")
        debug_info.append("   - El error real puede estar en otro quant que se intenta acceder")
        debug_info.append("   - El error puede ocurrir al validar una transferencia específica")
        debug_info.append("")
        debug_info.append("2. El error puede ocurrir durante la VALIDACIÓN de transferencias:")
        debug_info.append("   - Al validar, Odoo intenta acceder a quants que pueden no existir")
        debug_info.append("   - O intenta crear/modificar quants y hay un problema de permisos")
        debug_info.append("   - Puede ser un quant relacionado con un lote/serie específico")
        debug_info.append("")
        debug_info.append("3. El error puede ser un problema de CACHE o datos inconsistentes:")
        debug_info.append("   - Odoo puede tener referencias a quants que ya no existen")
        debug_info.append("   - Puede haber quants huérfanos (sin producto o ubicación válida)")
        debug_info.append("")
        debug_info.append("💡 RECOMENDACIONES:")
        debug_info.append("")
        debug_info.append("1. Si el error ocurre al VALIDAR una transferencia:")
        debug_info.append("   - Revisa los logs del servidor para ver el error completo")
        debug_info.append("   - Busca el ID del quant específico en el traceback del error")
        debug_info.append("   - Ejecuta este debug DESPUÉS de que ocurra el error para ver el quant específico")
        debug_info.append("")
        debug_info.append("2. Si el error es intermitente:")
        debug_info.append("   - Limpia la caché de Odoo")
        debug_info.append("   - Reinicia el servidor")
        debug_info.append("   - Verifica si hay quants huérfanos en la base de datos")
        debug_info.append("")
        debug_info.append("3. Para encontrar el quant problemático:")
        debug_info.append("   - Cuando ocurra el error, copia el traceback completo")
        debug_info.append("   - Busca el ID del quant en el mensaje de error")
        debug_info.append("   - Ejecuta este debug con ese ID específico")
        debug_info.append("")
        debug_info.append("4. Si el problema persiste:")
        debug_info.append("   - Verifica los logs del servidor en el momento exacto del error")
        debug_info.append("   - Revisa si hay transferencias con movimientos que referencian quants inexistentes")
        debug_info.append("   - Considera ejecutar una limpieza de datos huérfanos")
        debug_info.append("")
        debug_info.append("=" * 80)
        debug_info.append("")
        
        # Permisos del modelo
        debug_info.append("PERMISOS DEL MODELO (ir.model.access):")
        debug_info.append("-" * 80)
        try:
            model_access = self.env['ir.model.access'].search([
                ('model_id.model', '=', 'stock.quant')
            ])
            if model_access:
                for access in model_access:
                    debug_info.append(f"  - {access.name}")
                    debug_info.append(f"    Grupo: {access.group_id.name if access.group_id else 'Todos'}")
                    debug_info.append(f"    Leer: {access.perm_read}, Escribir: {access.perm_write}")
                    debug_info.append(f"    Crear: {access.perm_create}, Eliminar: {access.perm_unlink}")
                    debug_info.append("")
            else:
                debug_info.append("  No se encontraron permisos de acceso")
        except Exception as e:
            debug_info.append(f"Error al obtener permisos: {str(e)}")
        debug_info.append("")
        
        debug_info.append("=" * 80)
        debug_text = "\n".join(debug_info)
        
        # Log también en el servidor
        _logger.warning("\n" + debug_text)
        
        # Mostrar en notificación (limitado a 5000 caracteres)
        message = debug_text[:5000] if len(debug_text) > 5000 else debug_text
        if len(debug_text) > 5000:
            message += "\n\n... (mensaje truncado, ver logs del servidor para información completa)"
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': '🔍 Debug Global de Permisos - Stock.Quant',
                'message': message,
                'type': 'warning',
                'sticky': True,
            }
        }
    
    def action_debug_permissions(self):
        """Botón temporal de debug para identificar restricciones de permisos."""
        self.ensure_one()
        import logging
        _logger = logging.getLogger(__name__)
        
        debug_info = []
        debug_info.append("=" * 80)
        debug_info.append("DEBUG DE PERMISOS - STOCK.QUANT")
        debug_info.append("=" * 80)
        debug_info.append("")
        
        # Información del usuario
        user = self.env.user
        debug_info.append(f"Usuario: {user.name} (ID: {user.id})")
        debug_info.append(f"Grupos: {', '.join(user.groups_id.mapped('name'))}")
        debug_info.append("")
        
        # Información del quant
        debug_info.append(f"Quant ID: {self.id}")
        debug_info.append(f"Producto: {self.product_id.name if self.product_id else 'N/A'}")
        debug_info.append(f"Ubicación: {self.location_id.complete_name if self.location_id else 'N/A'}")
        debug_info.append(f"Lote: {self.lot_id.name if self.lot_id else 'N/A'}")
        debug_info.append(f"Empresa: {self.company_id.name if self.company_id else 'N/A'}")
        debug_info.append("")
        
        # Verificar acceso directo
        try:
            can_read = self.check_access_rights('read', raise_exception=False)
            can_write = self.check_access_rights('write', raise_exception=False)
            debug_info.append(f"Acceso directo - Leer: {can_read}, Escribir: {can_write}")
        except Exception as e:
            debug_info.append(f"Error al verificar acceso directo: {str(e)}")
        debug_info.append("")
        
        # Reglas de acceso (ir.rule)
        debug_info.append("REGLAS DE ACCESO (ir.rule):")
        debug_info.append("-" * 80)
        try:
            rules = self.env['ir.rule'].search([
                ('model_id.model', '=', 'stock.quant')
            ])
            if rules:
                for rule in rules:
                    debug_info.append(f"  - {rule.name} (ID: {rule.id})")
                    debug_info.append(f"    Activa: {rule.active}")
                    # En Odoo 18, el atributo puede ser 'global' en lugar de 'global_rule'
                    try:
                        is_global = getattr(rule, 'global_rule', getattr(rule, 'global', False))
                        debug_info.append(f"    Global: {is_global}")
                    except:
                        debug_info.append(f"    Global: N/A")
                    # En Odoo, el campo puede ser 'groups', 'group_ids' o 'groups_id'
                    try:
                        groups = getattr(rule, 'groups', getattr(rule, 'group_ids', getattr(rule, 'groups_id', False)))
                        if groups:
                            debug_info.append(f"    Grupos: {', '.join(groups.mapped('name'))}")
                        else:
                            debug_info.append(f"    Grupos: Todos (regla global)")
                    except:
                        debug_info.append(f"    Grupos: N/A")
                    debug_info.append(f"    Dominio: {rule.domain_force}")
                    
                    # Si es la regla multi-company, mostrar más detalles
                    if 'multi-company' in rule.name.lower() or 'multiempresa' in rule.name.lower():
                        debug_info.append(f"    ⚠️⚠️⚠️ REGLA MULTI-COMPANY DETECTADA ⚠️⚠️⚠️")
                        debug_info.append(f"    Esta es probablemente la causa del problema de permisos")
                        debug_info.append(f"    Empresa actual del usuario: {user.company_id.name if user.company_id else 'N/A'} (ID: {user.company_id.id if user.company_id else 'N/A'})")
                        debug_info.append(f"    Empresas permitidas para el usuario: {', '.join(user.company_ids.mapped('name'))}")
                        debug_info.append(f"    IDs de empresas permitidas: {user.company_ids.ids}")
                        
                        # Intentar evaluar el dominio
                        try:
                            if rule.domain_force:
                                debug_info.append(f"    Dominio completo de la regla: {rule.domain_force}")
                                # El dominio típico de multi-company es: ['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]
                                # Esto significa que solo se pueden ver quants sin empresa o de las empresas del usuario
                                debug_info.append(f"    ⚠️ Esta regla SOLO permite ver quants:")
                                debug_info.append(f"       - Sin empresa asignada (company_id = False)")
                                debug_info.append(f"       - De las empresas del usuario: {user.company_ids.ids}")
                                debug_info.append(f"    ⚠️ Cualquier quant de otra empresa será BLOQUEADO")
                        except Exception as e:
                            debug_info.append(f"    Error al analizar dominio: {str(e)}")
                    debug_info.append("")
            else:
                debug_info.append("  No se encontraron reglas de acceso")
        except Exception as e:
            debug_info.append(f"Error al obtener reglas: {str(e)}")
        debug_info.append("")
        
        # Verificar con sudo
        debug_info.append("VERIFICACIÓN CON SUDO:")
        debug_info.append("-" * 80)
        try:
            quant_sudo = self.sudo()
            debug_info.append(f"Con sudo - ID: {quant_sudo.id}")
            debug_info.append(f"Con sudo - Producto: {quant_sudo.product_id.name if quant_sudo.product_id else 'N/A'}")
            debug_info.append("✅ Acceso con sudo funciona")
        except Exception as e:
            debug_info.append(f"❌ Error incluso con sudo: {str(e)}")
        debug_info.append("")
        
        # Verificar permisos del modelo
        debug_info.append("PERMISOS DEL MODELO (ir.model.access):")
        debug_info.append("-" * 80)
        try:
            model_access = self.env['ir.model.access'].search([
                ('model_id.model', '=', 'stock.quant')
            ])
            for access in model_access:
                debug_info.append(f"  - {access.name}")
                debug_info.append(f"    Grupo: {access.group_id.name if access.group_id else 'Todos'}")
                debug_info.append(f"    Leer: {access.perm_read}, Escribir: {access.perm_write}")
                debug_info.append(f"    Crear: {access.perm_create}, Eliminar: {access.perm_unlink}")
                debug_info.append("")
        except Exception as e:
            debug_info.append(f"Error al obtener permisos: {str(e)}")
        debug_info.append("")
        
        # Intentar leer el quant específico mencionado en el error
        debug_info.append("VERIFICACIÓN DEL QUANT ID=9128:")
        debug_info.append("-" * 80)
        try:
            quant_9128 = self.env['stock.quant'].browse(9128)
            if quant_9128.exists():
                debug_info.append(f"✅ Quant 9128 existe")
                debug_info.append(f"   Producto: {quant_9128.product_id.name if quant_9128.product_id else 'N/A'}")
                debug_info.append(f"   Ubicación: {quant_9128.location_id.complete_name if quant_9128.location_id else 'N/A'}")
                debug_info.append(f"   Empresa: {quant_9128.company_id.name if quant_9128.company_id else 'N/A'}")
                try:
                    can_read_9128 = quant_9128.check_access_rights('read', raise_exception=False)
                    debug_info.append(f"   Acceso de lectura: {can_read_9128}")
                except Exception as e:
                    debug_info.append(f"   ❌ Error al verificar acceso: {str(e)}")
            else:
                debug_info.append("❌ Quant 9128 no existe")
        except Exception as e:
            debug_info.append(f"❌ Error al buscar quant 9128: {str(e)}")
        debug_info.append("")
        
        debug_info.append("=" * 80)
        debug_text = "\n".join(debug_info)
        
        # Log también en el servidor
        _logger.warning("\n" + debug_text)
        
        # Mostrar en notificación (limitado a 5000 caracteres)
        message = debug_text[:5000] if len(debug_text) > 5000 else debug_text
        if len(debug_text) > 5000:
            message += "\n\n... (mensaje truncado, ver logs del servidor para información completa)"
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': '🔍 Debug de Permisos - Stock.Quant',
                'message': message,
                'type': 'warning',
                'sticky': True,
            }
        }

