# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class StockLotCustomerInventory(models.Model):
    """Modelo para consulta de productos principales en inventario de clientes."""
    _inherit = 'stock.lot'

    # Campos computados para mostrar información del cliente
    customer_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        compute='_compute_customer_info',
        store=True,  # Almacenado para permitir agrupamiento
        search='_search_customer_id',
        help='Cliente que tiene este producto en su inventario'
    )
    
    customer_location_id = fields.Many2one(
        'stock.location',
        string='Ubicación del Cliente',
        compute='_compute_customer_info',
        store=True,  # Almacenado para mejor rendimiento
        help='Ubicación específica del cliente donde está el producto'
    )
    
    quantity_at_customer = fields.Float(
        string='Cantidad en Cliente',
        compute='_compute_customer_info',
        store=True,  # Almacenado para mejor rendimiento
        help='Cantidad disponible en la ubicación del cliente'
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
    
    is_main_product = fields.Boolean(
        string='Es Producto Principal',
        compute='_compute_is_main_product',
        store=False,
        search='_search_is_main_product',
        help='Indica si es un producto principal (no componente/periférico/complemento)'
    )
    
    product_image = fields.Binary(
        related='product_id.image_1920',
        string='Imagen del Producto',
        store=False
    )
    
    product_category_name = fields.Char(
        string="Categoria",
        compute="_compute_product_category_name",
        store=False,
        help="Categoría del producto (solo para visualización)"
    )

    # -------------------------------------------------------------------------
    # Compatibilidad agrupaciones (group_by)
    # -------------------------------------------------------------------------
    # En algunos casos (favoritos guardados / UI) Odoo puede enviar groupby como
    # una sola cadena con comas: "a,b,c". Eso rompe read_group porque espera
    # una lista de especificaciones, no un string con múltiples campos.
    # Este override lo normaliza para evitar el ValueError.
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        # Blindaje de alcance por cliente (evita que filtros con OR rompan el dominio)
        allowed_ids = self.env.context.get('customer_inventory_allowed_lot_ids')
        if allowed_ids is not None and not self.env.context.get('skip_customer_inventory_scope'):
            scope = [('id', 'in', allowed_ids)] if allowed_ids else [('id', '=', False)]
            domain = (fields.Domain(domain or []) & fields.Domain(scope))
        if isinstance(groupby, str):
            groupby = [g.strip() for g in groupby.split(',') if g.strip()]
        elif isinstance(groupby, (list, tuple)):
            normalized = []
            for g in groupby:
                if isinstance(g, str) and ',' in g and ':' not in g:
                    normalized.extend([p.strip() for p in g.split(',') if p.strip()])
                else:
                    normalized.append(g)
            groupby = normalized
        return super().read_group(domain, fields, groupby, offset=offset, limit=limit, orderby=orderby, lazy=lazy)
    
    @api.depends('product_id', 'product_id.categ_id')
    def _compute_product_category_name(self):
        """Calcular el nombre de la categoría del producto"""
        for lot in self:
            if lot.product_id and lot.product_id.categ_id:
                lot.product_category_name = lot.product_id.categ_id.name or ''
            else:
                lot.product_category_name = ''
    
    lot_image = fields.Binary(
        string='Imagen',
        help='Imagen específica de este número de serie. Si no se sube, se usará la imagen del producto.',
        attachment=True
    )
    
    report_image = fields.Binary(
        string='Imagen para Reporte',
        compute='_compute_report_image',
        store=False,
        help='Imagen preparada para reportes PDF'
    )
    
    # Campos para la vista de inventario detallado
    assigned_licenses_count = fields.Integer(
        string='Licencias Asignadas',
        compute='_compute_assigned_licenses_info',
        store=False,
        help='Cantidad de licencias asignadas a este equipo'
    )
    
    assigned_licenses_display = fields.Char(
        string='Licencias',
        compute='_compute_assigned_licenses_info',
        store=False,
        help='Lista de licencias asignadas'
    )
    
    assigned_licenses_list_display = fields.Char(
        string='Licencias',
        compute='_compute_assigned_licenses_list_display',
        store=False,
        help='Licencias asignadas formateadas para vista de lista (compacto)'
    )
    
    associated_products_count = fields.Integer(
        string='Productos Asociados',
        compute='_compute_associated_products_info',
        store=False,
        help='Cantidad de productos asociados (componentes, periféricos, complementos)'
    )
    
    associated_products_display = fields.Char(
        string='Productos Asociados',
        compute='_compute_associated_products_info',
        store=False,
        help='Lista de productos asociados'
    )
    
    associated_products_list_display = fields.Char(
        string='Componentes',
        compute='_compute_associated_products_list_display',
        store=False,
        help='Componentes asociados formateados para vista de lista (compacto)'
    )
    
    associated_products_count_display = fields.Char(
        string='Productos',
        compute='_compute_associated_products_info',
        store=False,
        help='Cantidad de productos asociados formateada'
    )
    
    assigned_licenses_count_display = fields.Char(
        string='Licencias',
        compute='_compute_assigned_licenses_info',
        store=False,
        help='Cantidad de licencias formateada'
    )
    
    associated_products_tree_display = fields.Char(
        string='📦 Productos Asociados',
        compute='_compute_tree_display',
        store=False,
        help='Productos asociados formateados para vista árbol'
    )
    
    # Campos para mostrar elementos asociados en columnas separadas (máximo 10 elementos)
    # Solo Producto (sin placas)
    associated_item_1_product = fields.Char(string='Componente 1', compute='_compute_associated_items_columns', store=False)
    associated_item_2_product = fields.Char(string='Componente 2', compute='_compute_associated_items_columns', store=False)
    associated_item_3_product = fields.Char(string='Componente 3', compute='_compute_associated_items_columns', store=False)
    associated_item_4_product = fields.Char(string='Componente 4', compute='_compute_associated_items_columns', store=False)
    associated_item_5_product = fields.Char(string='Componente 5', compute='_compute_associated_items_columns', store=False)
    associated_item_6_product = fields.Char(string='Componente 6', compute='_compute_associated_items_columns', store=False)
    associated_item_7_product = fields.Char(string='Componente 7', compute='_compute_associated_items_columns', store=False)
    associated_item_8_product = fields.Char(string='Componente 8', compute='_compute_associated_items_columns', store=False)
    associated_item_9_product = fields.Char(string='Componente 9', compute='_compute_associated_items_columns', store=False)
    associated_item_10_product = fields.Char(string='Componente 10', compute='_compute_associated_items_columns', store=False)
    
    # Campos para mostrar licencias asignadas en columnas separadas (máximo 10 licencias)
    license_1_name = fields.Char(string='Licencia 1', compute='_compute_licenses_columns', store=False)
    license_2_name = fields.Char(string='Licencia 2', compute='_compute_licenses_columns', store=False)
    license_3_name = fields.Char(string='Licencia 3', compute='_compute_licenses_columns', store=False)
    license_4_name = fields.Char(string='Licencia 4', compute='_compute_licenses_columns', store=False)
    license_5_name = fields.Char(string='Licencia 5', compute='_compute_licenses_columns', store=False)
    license_6_name = fields.Char(string='Licencia 6', compute='_compute_licenses_columns', store=False)
    license_7_name = fields.Char(string='Licencia 7', compute='_compute_licenses_columns', store=False)
    license_8_name = fields.Char(string='Licencia 8', compute='_compute_licenses_columns', store=False)
    license_9_name = fields.Char(string='Licencia 9', compute='_compute_licenses_columns', store=False)
    license_10_name = fields.Char(string='Licencia 10', compute='_compute_licenses_columns', store=False)
    
    def _get_product_type_name(self, product_name):
        """Obtener nombre del tipo de producto para nombrar columnas."""
        product_lower = product_name.lower()
        
        if any(keyword in product_lower for keyword in ['procesador', 'processor', 'cpu', 'ryzen', 'intel core', 'xeon', 'amd']):
            return 'Procesador'
        elif any(keyword in product_lower for keyword in ['das', 'disco', 'disk', 'ssd', 'hdd', 'storage', 'almacenamiento', '240 gb', '512 gb', '1tb', '2tb']):
            return 'Disco'
        elif any(keyword in product_lower for keyword in ['ram', 'memoria', 'memory', 'ddr']):
            return 'RAM'
        elif any(keyword in product_lower for keyword in ['monitor', 'mon', 'pantalla', 'display']):
            return 'Monitor'
        elif any(keyword in product_lower for keyword in ['teclado', 'keyboard', 'mouse', 'ratón', 'tcl']):
            return 'Periférico'
        elif any(keyword in product_lower for keyword in ['ups', 'regulador', 'regulador de voltaje']):
            return 'UPS'
        else:
            return 'Otro'
    
    def _get_product_type_priority(self, product_name):
        """Obtener prioridad de ordenamiento según el tipo de producto."""
        product_lower = product_name.lower()
        
        # Orden de prioridad: procesadores primero, luego discos, luego otros
        if any(keyword in product_lower for keyword in ['procesador', 'processor', 'cpu', 'ryzen', 'intel core', 'xeon', 'amd']):
            return 1  # Procesadores primero
        elif any(keyword in product_lower for keyword in ['das', 'disco', 'disk', 'ssd', 'hdd', 'storage', 'almacenamiento', '240 gb', '512 gb', '1tb', '2tb']):
            return 2  # Discos segundo
        elif any(keyword in product_lower for keyword in ['ram', 'memoria', 'memory', 'ddr']):
            return 3  # RAM tercero
        elif any(keyword in product_lower for keyword in ['monitor', 'mon', 'pantalla', 'display']):
            return 4  # Monitores cuarto
        elif any(keyword in product_lower for keyword in ['teclado', 'keyboard', 'mouse', 'ratón', 'tcl']):
            return 5  # Periféricos quinto
        elif any(keyword in product_lower for keyword in ['ups', 'regulador', 'regulador de voltaje']):
            return 6  # UPS sexto
        else:
            return 7  # Otros últimos
    
    @api.depends('lot_supply_line_ids', 'lot_supply_line_ids.related_lot_id', 
                 'lot_supply_line_ids.related_lot_id.inventory_plate',
                 'lot_supply_line_ids.product_id')
    def _compute_associated_items_columns(self):
        """Calcular elementos asociados en columnas separadas para vista jerárquica, ordenados por tipo."""
        for lot in self:
            # Inicializar todos los campos (hasta 10 elementos)
            for i in range(1, 11):
                setattr(lot, f'associated_item_{i}_product', '')
            
            if not lot.lot_supply_line_ids:
                continue
            
            # Obtener líneas con elementos asociados (que tengan related_lot_id)
            lines_with_lots = lot.lot_supply_line_ids.filtered(lambda l: l.related_lot_id)
            
            # Ordenar por tipo de producto (procesadores primero, luego discos, etc.)
            def sort_key(line):
                product_name = line.product_id.name or ''
                # Limpiar nombre del producto para ordenar
                if ']' in product_name:
                    parts = product_name.split(']', 1)
                    if len(parts) > 1:
                        product_name = parts[1].strip()
                return lot._get_product_type_priority(product_name)
            
            # Ordenar las líneas por prioridad de tipo
            sorted_lines = sorted(lines_with_lots, key=sort_key)
            
            # Procesar máximo 10 elementos ordenados
            for idx, line in enumerate(sorted_lines[:10], start=1):
                # Producto
                product_name = line.product_id.name or ''
                # Limpiar nombre del producto (quitar prefijos entre corchetes)
                if ']' in product_name:
                    parts = product_name.split(']', 1)
                    if len(parts) > 1:
                        product_name = parts[1].strip()
                
                setattr(lot, f'associated_item_{idx}_product', product_name)
    
    @api.depends('assigned_licenses_count')
    def _compute_licenses_columns(self):
        """Calcular licencias asignadas en columnas separadas para vista jerárquica."""
        for lot in self:
            # Inicializar todos los campos de licencias (hasta 10)
            for i in range(1, 11):
                setattr(lot, f'license_{i}_name', '')
            
            if not lot.id or lot.assigned_licenses_count == 0:
                continue
            
            # Verificar que el producto tenga categoría de activo "COMPUTO" (acceso seguro por permisos)
            try:
                cat = lot.product_id.asset_category_id if lot.product_id else None
            except Exception:
                cat = None
            if not lot.product_id or not cat:
                continue
            if cat.name != 'COMPUTO':
                continue
            
            # Obtener las licencias asignadas
            try:
                if 'license.equipment' not in lot.env:
                    continue
                
                LicenseEquipment = lot.env['license.equipment']
                
                # Buscar licencias asignadas directamente al equipo
                license_equipments = LicenseEquipment.search([
                    ('lot_id', '=', lot.id),
                    ('state', '=', 'assigned')
                ])
                
                # También buscar licencias asignadas al usuario relacionado
                if hasattr(lot, 'related_partner_id') and lot.related_partner_id:
                    user_licenses = LicenseEquipment.search([
                        ('contact_id', '=', lot.related_partner_id.id),
                        ('state', '=', 'assigned')
                    ])
                    
                    # Combinar evitando duplicados por license_id
                    seen_license_ids = set()
                    for eq in license_equipments:
                        if eq.license_id:
                            seen_license_ids.add(eq.license_id.id)
                    
                    for user_license in user_licenses:
                        if user_license.license_id and user_license.license_id.id not in seen_license_ids:
                            license_equipments |= user_license
                            seen_license_ids.add(user_license.license_id.id)
                
                # Procesar máximo 10 licencias
                for idx, license_eq in enumerate(license_equipments[:10], start=1):
                    if license_eq.license_id and license_eq.license_id.license_template_id:
                        license_name = license_eq.license_id.license_template_id.name or ''
                        # Limpiar nombre de licencia si tiene prefijos
                        if ']' in license_name:
                            parts = license_name.split(']', 1)
                            if len(parts) > 1:
                                license_name = parts[1].strip()
                        setattr(lot, f'license_{idx}_name', license_name)
            except Exception:
                # Si hay error al obtener licencias, dejar vacío
                pass
    
    assigned_licenses_tree_display = fields.Char(
        string='📜 Licencias',
        compute='_compute_tree_display',
        store=False,
        help='Licencias formateadas para vista árbol'
    )
    
    # Campo para mostrar solo el nombre del contacto asignado (sin compañía)
    related_partner_name_only = fields.Char(
        string='Nombre del Usuario',
        compute='_compute_related_partner_name_only',
        store=False,
        help='Solo el nombre del contacto asignado, sin la compañía'
    )
    
    @api.depends('related_partner_id')
    def _compute_related_partner_name_only(self):
        """Calcular solo el nombre del contacto, sin la compañía."""
        for lot in self:
            if lot.related_partner_id:
                # related_partner_id es un Many2one, así que podemos acceder directamente a .name
                lot.related_partner_name_only = lot.related_partner_id.name or ''
            else:
                lot.related_partner_name_only = ''
    
    maintenance_ids = fields.One2many(
        'stock.lot.maintenance',
        'lot_id',
        string='Mantenimientos y Revisiones',
        help='Historial de mantenimientos, revisiones y trabajos realizados en este producto'
    )
    
    # Campo computed para obtener todos los cambios de componentes del equipo
    component_change_history_ids = fields.One2many(
        'maintenance.component.change',
        'lot_id',
        string='Historial de Cambios de Componentes',
        compute='_compute_component_change_history',
        store=False,
        help='Historial de todos los cambios de componentes realizados en este equipo'
    )
    
    def action_view_license_equipment(self):
        """Abrir vista de licencias asignadas a este equipo, eliminando duplicados."""
        self.ensure_one()
        
        # Intentar acceder directamente al modelo - si subscription_licenses está instalado, funcionará
        # Buscar todas las licencias asignadas a este equipo
        license_equipments = self.env['license.equipment'].search([
            ('lot_id', '=', self.id),
            ('state', '=', 'assigned')
        ])
        
        # Eliminar duplicados: agrupar por license_id y tomar solo uno de cada
        seen_license_ids = set()
        unique_equipment_ids = []
        
        for equipment in license_equipments:
            license_id = equipment.license_id.id if equipment.license_id else None
            if license_id and license_id not in seen_license_ids:
                seen_license_ids.add(license_id)
                unique_equipment_ids.append(equipment.id)
            elif not license_id:
                # Si no tiene licencia, también incluirlo
                unique_equipment_ids.append(equipment.id)
        
        # Usar la vista existente del módulo subscription_licenses con contexto de solo lectura
        # Intentar obtener la vista existente del módulo subscription_licenses
        view_ref = self.env.ref('subscription_licenses.view_license_equipment_tree', raise_if_not_found=False)
        view_id = view_ref.id if view_ref else False
        
        return {
            'name': _('Licencias Asignadas (Solo Consulta)'),
            'type': 'ir.actions.act_window',
            'res_model': 'license.equipment',
            'view_mode': 'list',
            'view_id': view_id,
            'domain': [('id', 'in', unique_equipment_ids)] if unique_equipment_ids else [('id', '=', False)],
            'context': {
                'default_lot_id': self.id,
                'create': False,
                'search_default_assigned': 1,
            },
            'target': 'current',
        }
    
    @api.depends('maintenance_ids', 'maintenance_ids.component_change_ids')
    def _compute_component_change_history(self):
        """Calcular todos los cambios de componentes relacionados con este equipo."""
        for lot in self:
            # Obtener todos los cambios de componentes de todos los mantenimientos del equipo
            all_changes = self.env['maintenance.component.change']
            for maintenance in lot.maintenance_ids:
                all_changes |= maintenance.component_change_ids
            lot.component_change_history_ids = all_changes.sorted('change_date', reverse=True)
    
    def _get_assigned_licenses(self):
        """Obtener todas las licencias asignadas a este equipo y al usuario relacionado (para reportes).
        Retorna todas las licencias sin eliminar duplicados para mostrar la cantidad real asignada."""
        self.ensure_one()
        if not self.id:
            return []
        
        try:
            if 'license.equipment' not in self.env:
                return []
            
            # Buscar todas las licencias asignadas directamente al equipo
            license_equipments = self.env['license.equipment'].search([
                ('lot_id', '=', self.id),
                ('state', '=', 'assigned')
            ])
            
            # También buscar licencias asignadas al usuario relacionado con el equipo
            if hasattr(self, 'related_partner_id') and self.related_partner_id:
                user_licenses = self.env['license.equipment'].search([
                    ('contact_id', '=', self.related_partner_id.id),
                    ('state', '=', 'assigned')
                ])
                
                # Combinar ambas listas (incluir todas, incluso duplicados)
                license_equipments |= user_licenses
            
            # Filtrar solo licencias válidas (verificar fechas si es necesario)
            from datetime import date
            today = date.today()
            valid_licenses = []
            
            for equipment in license_equipments:
                # Verificar que la licencia esté asignada
                if equipment.state != 'assigned':
                    continue
                
                # Verificar fechas si existen
                # Si tiene fecha de desasignación y ya pasó, no es válida
                if equipment.unassignment_date and equipment.unassignment_date < today:
                    continue
                
                # Si tiene fecha de asignación futura, aún no es válida
                if equipment.assignment_date and equipment.assignment_date > today:
                    continue
                
                valid_licenses.append(equipment)
            
            return valid_licenses
        except Exception:
            return []
    
    @api.depends('related_partner_id', 'product_id', 'product_id.asset_category_id')
    def _compute_assigned_licenses_info(self):
        """Calcular información de licencias asignadas para mostrar en vista.
        Incluye licencias asignadas directamente al equipo y al usuario relacionado.
        Solo muestra licencias válidas (asignadas y activas).
        Solo muestra licencias para productos categorizados como COMPUTO."""
        for lot in self:
            lot.assigned_licenses_count = 0
            lot.assigned_licenses_display = ''
            lot.assigned_licenses_count_display = '-'
            
            if not lot.id:
                continue
            
            # Verificar que el producto tenga categoría de activo "COMPUTO" (acceso seguro por permisos)
            try:
                cat = lot.product_id.asset_category_id if lot.product_id else None
            except Exception:
                cat = None
            if not lot.product_id or not cat or cat.name != 'COMPUTO':
                continue
            
            try:
                # Verificar si el modelo existe de forma segura
                try:
                    LicenseEquipment = self.env['license.equipment']
                except KeyError:
                    # El modelo no existe, continuar sin error
                    continue
                
                # Buscar licencias asignadas directamente al equipo (válidas)
                license_equipments = LicenseEquipment.search([
                    ('lot_id', '=', lot.id),
                    ('state', '=', 'assigned')
                ])
                
                # También buscar licencias asignadas al usuario relacionado con el equipo
                if hasattr(lot, 'related_partner_id') and lot.related_partner_id:
                    user_licenses = LicenseEquipment.search([
                        ('contact_id', '=', lot.related_partner_id.id),
                        ('state', '=', 'assigned')
                    ])
                    
                    # Combinar ambas listas, evitando duplicados por license_id
                    seen_license_ids = set()
                    for eq in license_equipments:
                        if eq.license_id:
                            seen_license_ids.add(eq.license_id.id)
                    
                    for user_license in user_licenses:
                        # Agregar si no está ya en la lista Y si la licencia no está duplicada
                        if user_license.id not in license_equipments.ids:
                            if user_license.license_id:
                                if user_license.license_id.id not in seen_license_ids:
                                    license_equipments |= user_license
                                    seen_license_ids.add(user_license.license_id.id)
                            else:
                                # Si no tiene license_id, agregarlo de todas formas
                                license_equipments |= user_license
                
                # Filtrar solo licencias válidas (verificar fechas si es necesario)
                from datetime import date
                today = date.today()
                valid_licenses = []
                
                for equipment in license_equipments:
                    # Verificar que la licencia esté asignada
                    if equipment.state != 'assigned':
                        continue
                    
                    # Verificar fechas si existen
                    # Si tiene fecha de desasignación y ya pasó, no es válida
                    if equipment.unassignment_date and equipment.unassignment_date < today:
                        continue
                    
                    # Si tiene fecha de asignación futura, aún no es válida
                    if equipment.assignment_date and equipment.assignment_date > today:
                        continue
                    
                    valid_licenses.append(equipment)
                
                if valid_licenses:
                    lot.assigned_licenses_count = len(valid_licenses)
                    # Crear lista de licencias únicas usando el nombre del servicio/producto
                    seen_license_ids = set()
                    license_names = []
                    
                    for equipment in valid_licenses:
                        # Usar el nombre del servicio (service_product_id) si está disponible,
                        # sino usar el nombre de la licencia (license_id)
                        if equipment.service_product_id:
                            license_name = equipment.service_product_id.name or 'Sin nombre'
                        elif equipment.license_id:
                            license_name = equipment.license_id.name or 'Sin nombre'
                        else:
                            license_name = 'Sin licencia'
                        
                        # Evitar duplicados por license_id
                        if equipment.license_id:
                            if equipment.license_id.id not in seen_license_ids:
                                seen_license_ids.add(equipment.license_id.id)
                                license_names.append(license_name)
                        else:
                            # Si no tiene license_id, agregarlo de todas formas
                            license_names.append(license_name)
                    
                    # Formatear: primera línea sin indentar, siguientes con indentación
                    if license_names:
                        formatted_licenses = []
                        for i, name in enumerate(license_names[:10]):
                            if i == 0:
                                formatted_licenses.append(name)
                            else:
                                # Indentar líneas siguientes con espacios
                                formatted_licenses.append('          %s' % name)
                        lot.assigned_licenses_display = '\n'.join(formatted_licenses)
                        if len(license_names) > 10:
                            lot.assigned_licenses_display += '\n          (+%s más)' % (len(license_names) - 10)
                        # Formatear el contador para mostrar solo si > 0
                        if lot.assigned_licenses_count > 0:
                            lot.assigned_licenses_count_display = '%d Licencias' % lot.assigned_licenses_count
                    else:
                        lot.assigned_licenses_display = ''
            except Exception as e:
                # Log del error para depuración
                import logging
                _logger = logging.getLogger(__name__)
                _logger.warning('Error al calcular licencias para lot %s: %s', lot.id, str(e))
                pass
    
    @api.depends('assigned_licenses_count', 'assigned_licenses_display')
    def _compute_assigned_licenses_list_display(self):
        """Calcular formato compacto de licencias para vista de lista."""
        for lot in self:
            if lot.assigned_licenses_count == 0 or not lot.assigned_licenses_display:
                lot.assigned_licenses_list_display = ''
            else:
                # Tomar las primeras 3-4 licencias y mostrar de forma compacta
                license_lines = lot.assigned_licenses_display.split('\n')
                # Filtrar líneas vacías, líneas que empiezan con "(+" y limpiar espacios de indentación
                license_names = []
                for line in license_lines:
                    cleaned = line.strip()
                    if cleaned and not cleaned.startswith('(+'):
                        license_names.append(cleaned)
                
                if license_names:
                    # Mostrar TODAS las licencias separadas por comas (sin límite)
                    lot.assigned_licenses_list_display = ', '.join(license_names)
                else:
                    lot.assigned_licenses_list_display = ''
    
    @api.depends('lot_supply_line_ids')
    def _compute_associated_products_info(self):
        """Calcular información de productos asociados para mostrar en vista."""
        for lot in self:
            lot.associated_products_count = 0
            lot.associated_products_display = ''
            lot.associated_products_count_display = '-'
            
            if not lot.lot_supply_line_ids:
                continue
            
            lot.associated_products_count = len(lot.lot_supply_line_ids)
            product_names = []
            for line in lot.lot_supply_line_ids:
                if line.product_id:
                    # Solo incluir el nombre del producto sin prefijos
                    product_name = line.product_id.name or 'Sin nombre'
                    product_names.append(product_name)
            
            # Formatear: primera línea sin indentar, siguientes con indentación
            if product_names:
                formatted_names = []
                for i, name in enumerate(product_names[:10]):
                    if i == 0:
                        formatted_names.append(name)
                    else:
                        # Indentar líneas siguientes con espacios (aproximadamente 10 espacios)
                        formatted_names.append('          %s' % name)
                lot.associated_products_display = '\n'.join(formatted_names)
                if len(product_names) > 10:
                    lot.associated_products_display += '\n          (+%s más)' % (len(product_names) - 10)
                # Formatear el contador para mostrar solo si > 0
                if lot.associated_products_count > 0:
                    lot.associated_products_count_display = '%d Productos' % lot.associated_products_count
            else:
                lot.associated_products_display = ''
    
    @api.depends('lot_supply_line_ids', 'lot_supply_line_ids.product_id', 'lot_supply_line_ids.related_lot_id')
    def _compute_associated_products_list_display(self):
        """Calcular formato compacto de componentes asociados para vista de lista."""
        for lot in self:
            if not lot.lot_supply_line_ids:
                lot.associated_products_list_display = ''
            else:
                # Obtener líneas con elementos asociados (que tengan related_lot_id)
                lines_with_lots = lot.lot_supply_line_ids.filtered(lambda l: l.related_lot_id)
                
                if not lines_with_lots:
                    lot.associated_products_list_display = ''
                else:
                    # Ordenar por tipo de producto (procesadores primero, luego discos, etc.)
                    def sort_key(line):
                        product_name = line.product_id.name or ''
                        # Limpiar nombre del producto para ordenar
                        if ']' in product_name:
                            parts = product_name.split(']', 1)
                            if len(parts) > 1:
                                product_name = parts[1].strip()
                        return lot._get_product_type_priority(product_name)
                    
                    # Ordenar las líneas por prioridad de tipo
                    sorted_lines = sorted(lines_with_lots, key=sort_key)
                    
                    # Obtener nombres de productos limpios
                    product_names = []
                    for line in sorted_lines:
                        if line.product_id:
                            product_name = line.product_id.name or 'Sin nombre'
                            # Limpiar nombre del producto (quitar prefijos entre corchetes)
                            if ']' in product_name:
                                parts = product_name.split(']', 1)
                                if len(parts) > 1:
                                    product_name = parts[1].strip()
                            product_names.append(product_name)
                    
                    if product_names:
                        # Mostrar TODOS los componentes separados por comas (sin límite)
                        lot.associated_products_list_display = ', '.join(product_names)
                    else:
                        lot.associated_products_list_display = ''
    
    @api.depends('lot_supply_line_ids', 'lot_supply_line_ids.product_id',
                 'assigned_licenses_count', 'assigned_licenses_display')
    def _compute_tree_display(self):
        """Calcular visualización tipo árbol para productos y licencias asociados."""
        for lot in self:
            # Productos asociados - formato texto con indentación
            products_text = ''
            if lot.lot_supply_line_ids:
                product_names = []
                for line in lot.lot_supply_line_ids:
                    if line.product_id:
                        product_name = line.product_id.name or 'Sin nombre'
                        # Remover prefijos entre corchetes si existen
                        if ']' in product_name:
                            parts = product_name.split(']', 1)
                            if len(parts) > 1:
                                product_name = parts[1].strip()
                        product_names.append(product_name)
                
                if product_names:
                    # Formatear con indentación usando espacios
                    products_lines = []
                    for name in product_names[:10]:
                        products_lines.append(f'  ▸ {name}')
                    if len(product_names) > 10:
                        products_lines.append(f'  (+{len(product_names) - 10} más)')
                    products_text = '\n'.join(products_lines)
            
            lot.associated_products_tree_display = products_text
            
            # Licencias - formato texto con indentación
            licenses_text = ''
            if lot.assigned_licenses_count > 0 and lot.assigned_licenses_display:
                license_names = lot.assigned_licenses_display.split('\n')
                license_names = [name.strip() for name in license_names if name.strip() and not name.strip().startswith('(+')]
                if license_names:
                    licenses_lines = []
                    for name in license_names[:10]:
                        licenses_lines.append(f'  ▸ {name}')
                    if len(license_names) > 10:
                        licenses_lines.append(f'  (+{len(license_names) - 10} más)')
                    licenses_text = '\n'.join(licenses_lines)
            
            lot.assigned_licenses_tree_display = licenses_text
    
    def name_get(self):
        """Personalizar la visualización para mostrar primero la placa de inventario si existe."""
        result = []
        for lot in self:
            # Si tiene placa de inventario, mostrar SOLO la placa (prioridad)
            if lot.inventory_plate:
                display_name = lot.inventory_plate
            else:
                # Si no tiene placa, mostrar solo el número de serie
                display_name = lot.name or _('Nuevo')
            result.append((lot.id, display_name))
        return result

    @api.depends('name', 'product_id', 'is_principal', 'principal_lot_id', 'product_id.classification')
    def _compute_is_main_product(self):
        """Determinar si es un producto principal."""
        for lot in self:
            # Es principal si:
            # 1. is_principal=True (marcado como principal)
            # 2. O si principal_lot_id es False (no está asociado a otro producto)
            # 3. Y no es un componente/periférico/complemento según classification
            lot.is_main_product = (
                lot.is_principal or 
                (not lot.principal_lot_id and 
                 lot.product_id.classification not in ('component', 'peripheral', 'complement'))
            )

    def _search_is_main_product(self, operator, value):
        """Búsqueda para filtrar solo productos principales."""
        if operator == '=' and value:
            # Buscar lotes principales: is_principal=True O (principal_lot_id=False Y classification no es component/peripheral/complement)
            domain = [
                '|',
                ('is_principal', '=', True),
                '&',
                ('principal_lot_id', '=', False),
                ('product_id.classification', 'not in', ['component', 'peripheral', 'complement'])
            ]
            lot_ids = self.search(domain).ids
            return [('id', 'in', lot_ids)]
        return []

    @api.depends('name', 'product_id')
    def _compute_customer_info(self):
        """Calcular información del cliente basándose en stock.quant y ubicaciones de contacto.
        OPTIMIZADO: Procesa en batch para mejorar rendimiento."""
        # Inicializar valores por defecto
        lot_ids = self.filtered(lambda l: l.id).ids
        if not lot_ids:
            for lot in self:
                lot.customer_id = False
                lot.customer_location_id = False
                lot.quantity_at_customer = 0.0
            return
        
        Quant = self.env['stock.quant']
        Partner = self.env['res.partner']
        
        # 1. Buscar todos los quants de una vez (optimización batch)
        quants_by_lot = {}
        all_quants = Quant.search([
            ('lot_id', 'in', lot_ids),
            ('quantity', '>', 0),
            ('location_id.usage', 'in', ['customer', 'internal']),
        ], order='lot_id, quantity desc')
        
        # Agrupar quants por lot_id
        for quant in all_quants:
            if quant.lot_id.id not in quants_by_lot:
                quants_by_lot[quant.lot_id.id] = []
            quants_by_lot[quant.lot_id.id].append(quant)
        
        # 2. Pre-cargar todas las ubicaciones y sus partners asociados
        location_ids = set()
        for quants in quants_by_lot.values():
            for quant in quants:
                location_ids.add(quant.location_id.id)
        
        # Mapeo: location_id -> partner_id (para ubicaciones customer)
        location_to_partner = {}
        if location_ids:
            # Buscar partners por ubicación de cliente (una sola consulta)
            partners = Partner.search([
                ('property_stock_customer', 'in', list(location_ids)),
                '|',
                ('is_company', '=', True),
                ('property_stock_customer.location_id.usage', '=', 'customer'),
            ])
            for partner in partners:
                if partner.property_stock_customer:
                    location_to_partner[partner.property_stock_customer.id] = partner.id
        
        # 3. Pre-cargar pickings más recientes por lote (una consulta agrupada)
        picking_data = {}
        if lot_ids:
            # Buscar el picking más reciente por lote
            self._cr.execute("""
                SELECT DISTINCT ON (ml.lot_id) 
                    ml.lot_id, sp.partner_id, sp.id as picking_id
                FROM stock_move_line ml
                JOIN stock_picking sp ON sp.id = ml.picking_id
                JOIN stock_picking_type spt ON spt.id = sp.picking_type_id
                WHERE ml.lot_id IN %s
                    AND sp.state = 'done'
                    AND spt.code = 'outgoing'
                    AND sp.partner_id IS NOT NULL
                ORDER BY ml.lot_id, sp.date desc, sp.id desc
            """, (tuple(lot_ids),))
            
            for row in self._cr.dictfetchall():
                if row['lot_id'] and row['partner_id']:
                    picking_data[row['lot_id']] = row['partner_id']
        
        # 4. Procesar cada lote con datos pre-cargados
        for lot in self:
            lot.customer_id = False
            lot.customer_location_id = False
            lot.quantity_at_customer = 0.0
            
            if not lot.id or lot.id not in quants_by_lot:
                continue
            
            quants = quants_by_lot[lot.id]
            
            # Buscar cliente para cada quant (prioridad)
            for quant in quants:
                location = quant.location_id
                
                # Método 1: Buscar en mapeo pre-cargado
                partner_id = location_to_partner.get(location.id)
                if partner_id:
                    lot.customer_id = partner_id
                    lot.customer_location_id = location
                    lot.quantity_at_customer = quant.quantity
                    break
                
                # Método 2: Si es ubicación interna, buscar a través de pickings
                if location.usage == 'internal':
                    partner_id = picking_data.get(lot.id)
                    if partner_id:
                        partner = Partner.browse(partner_id)
                        customer_location = partner.property_stock_customer
                        if customer_location and customer_location.id == location.id:
                            lot.customer_id = partner_id
                            lot.customer_location_id = location
                            lot.quantity_at_customer = quant.quantity
                            break
            
            # Si aún no encontramos cliente, usar el primer quant y partner del picking
            if not lot.customer_id and quants:
                quant = quants[0]
                location = quant.location_id
                lot.customer_location_id = location
                lot.quantity_at_customer = quant.quantity
                
                # Usar partner del picking más reciente si existe
                partner_id = picking_data.get(lot.id)
                if partner_id:
                    lot.customer_id = partner_id

    def _search_customer_id(self, operator, value):
        """Búsqueda por cliente."""
        if not value:
            return []
        
        # Buscar ubicaciones de cliente
        locations = self.env['stock.location'].search([
            ('usage', '=', 'customer'),
        ])
        
        if not locations:
            return [('id', '=', False)]
        
        # Buscar pickings donde el cliente recibió lotes
        pickings = self.env['stock.picking'].search([
            ('location_dest_id', 'in', locations.ids),
            ('state', '=', 'done'),
            ('partner_id', operator, value),
        ])
        
        if not pickings:
            return [('id', '=', False)]
        
        # Obtener los lotes de esos pickings
        move_lines = pickings.mapped('move_line_ids').filtered(lambda ml: ml.lot_id)
        lot_ids = move_lines.mapped('lot_id').ids
        
        if not lot_ids:
            return [('id', '=', False)]
        
        return [('id', 'in', lot_ids)]

    @api.model
    def _get_customer_lots_domain(self):
        """Dominio base para obtener solo productos principales en clientes."""
        return [
            ('is_main_product', '=', True),
            ('customer_id', '!=', False),
        ]

    def write(self, vals):
        """Sobrescribir write para registrar cambios en el chatter."""
        # Campos que queremos trackear
        tracked_fields = ['model_name', 'inventory_plate', 'security_plate', 'billing_code', 'name']
        
        # Evitar procesar cuando se está propagando related_partner_id desde product_suppiles_partner
        # para evitar recursión infinita
        # Si solo se está actualizando related_partner_id (sin otros campos trackeados), no hacer tracking
        has_tracked_fields = any(k in tracked_fields for k in vals.keys())
        
        if (self.env.context.get('skip_tracking', False) or 
            (not has_tracked_fields and 'related_partner_id' in vals)):
            # Si solo se actualiza related_partner_id sin campos trackeados, hacer write directo
            return super().write(vals)
        tracked_vals = {k: v for k, v in vals.items() if k in tracked_fields}
        
        # Guardar valores antiguos antes de escribir
        old_values = {}
        if tracked_vals:
            for record in self:
                old_values[record.id] = {}
                for field in tracked_vals.keys():
                    old_values[record.id][field] = getattr(record, field, False)
        
        result = super().write(vals)
        
        # Registrar mensaje en el chatter si hay cambios en campos trackeados
        # Solo si no estamos en modo de propagación
        if tracked_vals and old_values and not self.env.context.get('skip_tracking', False):
            field_labels = {
                'model_name': _('Modelo'),
                'inventory_plate': _('Placa de Inventario'),
                'security_plate': _('Placa de Seguridad'),
                'billing_code': _('Código de Facturación'),
                'name': _('Número de Serie'),
            }
            
            for record in self:
                changes = []
                record_old_vals = old_values.get(record.id, {})
                for field, new_value in tracked_vals.items():
                    old_value = record_old_vals.get(field, False)
                    if old_value != new_value:
                        field_label = field_labels.get(field, field)
                        changes.append(_('%s: %s → %s') % (
                            field_label,
                            old_value or _('Sin valor'),
                            new_value or _('Sin valor')
                        ))
                
                if changes:
                    # Formatear el mensaje correctamente sin mostrar <br/> como texto
                    if len(changes) == 1:
                        # Si hay un solo cambio, no usar <br/> adicional
                        message_body = _('Modificaciones realizadas por %s: %s') % (
                            self.env.user.name,
                            changes[0]
                        )
                    else:
                        # Si hay múltiples cambios, usar <br/> para separarlos
                        message_body = _('Modificaciones realizadas por %s:<br/>%s') % (
                            self.env.user.name,
                            '<br/>'.join(changes)
                        )
                    
                    record.message_post(
                        body=message_body,
                        subject=_('Actualización de Producto')
                    )
        
        return result

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, **kwargs):
        """Sobrescribe la búsqueda para que cuando se busque por 'name' (número de serie),
        también busque automáticamente en 'inventory_plate' (placa de inventario).
        También excluye automáticamente los componentes asociados a productos principales."""
        # Blindaje de alcance por cliente (evita que filtros con OR rompan el dominio)
        allowed_ids = self.env.context.get('customer_inventory_allowed_lot_ids')
        if allowed_ids is not None and not self.env.context.get('skip_customer_inventory_scope'):
            scope = [('id', 'in', allowed_ids)] if allowed_ids else [('id', '=', False)]
            domain = (fields.Domain(domain or []) & fields.Domain(scope))

        # Evitar procesar cuando se está en contexto de propagación para evitar recursión
        # También evitar si el dominio es muy simple (búsquedas internas del sistema)
        if (self.env.context.get('skip_search_enhancement', False) or 
            self.env.context.get('skip_tracking', False) or
            self.env.context.get('active_test', False)):
            return super()._search(domain, offset=offset, limit=limit, order=order, **kwargs)
        
        # Si el dominio solo contiene condiciones simples (no búsquedas de texto),
        # no procesar para evitar problemas con búsquedas internas
        try:
            # Convertir domain a lista si es necesario
            if not isinstance(domain, list):
                domain = list(domain) if domain else []
            
            # Si el dominio es muy simple (solo IDs o condiciones directas), no procesar
            simple_domains = [('id', 'in', []), ('id', '=', 0), ('principal_lot_id', '=', 0)]
            if len(domain) == 1 and isinstance(domain[0], (list, tuple)) and len(domain[0]) >= 2:
                field = domain[0][0]
                if field in ('id', 'principal_lot_id') and domain[0][1] in ('=', 'in'):
                    return super()._search(domain, offset=offset, limit=limit, order=order, **kwargs)
            
            # Crear una copia del dominio para no modificar el original
            domain_copy = list(domain)
            
            # Buscar si hay una condición de búsqueda por 'name' (número de serie) o 'inventory_plate' (placa)
            # y hacer que busquen en ambos campos simultáneamente
            name_condition = None
            inventory_plate_condition = None
            text_operators = ('ilike', 'like', '=like', '=', '!=')
            
            for condition in domain_copy:
                if isinstance(condition, (list, tuple)) and len(condition) >= 3:
                    field_name = condition[0]
                    operator = condition[1]
                    value = condition[2]
                    
                    # Si se busca por 'name' con un operador de texto
                    if field_name == 'name' and operator in text_operators:
                        if value and isinstance(value, str) and value.strip():
                            name_condition = condition
                    # Si se busca por 'inventory_plate' con un operador de texto
                    elif field_name == 'inventory_plate' and operator in text_operators:
                        if value and isinstance(value, str) and value.strip():
                            inventory_plate_condition = condition
            
            # Si se busca por 'name' y NO hay búsqueda por 'inventory_plate', agregar búsqueda por 'inventory_plate'
            if name_condition and not inventory_plate_condition:
                operator = name_condition[1]
                value = name_condition[2]
                
                # Crear condición para inventory_plate con el mismo operador y valor
                inventory_plate_condition_new = ('inventory_plate', operator, value)
                
                # Reemplazar la condición de 'name' con una búsqueda OR en ambos campos
                name_index = domain_copy.index(name_condition)
                domain_copy[name_index] = '|'
                domain_copy.insert(name_index + 1, name_condition)
                domain_copy.insert(name_index + 2, inventory_plate_condition_new)
            
            # Si se busca por 'inventory_plate' y NO hay búsqueda por 'name', agregar búsqueda por 'name'
            elif inventory_plate_condition and not name_condition:
                operator = inventory_plate_condition[1]
                value = inventory_plate_condition[2]
                
                # Crear condición para name con el mismo operador y valor
                name_condition_new = ('name', operator, value)
                
                # Reemplazar la condición de 'inventory_plate' con una búsqueda OR en ambos campos
                plate_index = domain_copy.index(inventory_plate_condition)
                domain_copy[plate_index] = '|'
                domain_copy.insert(plate_index + 1, inventory_plate_condition)
                domain_copy.insert(plate_index + 2, name_condition_new)
            
            # Llamar al método padre con el dominio modificado
            # Usar un modelo base sin nuestras mejoras para evitar recursión
            StockLotBase = self.env['stock.lot'].with_context(skip_search_enhancement=True)
            return StockLotBase._search(domain_copy, offset=offset, limit=limit, order=order, **kwargs)
        except Exception as e:
            # Si hay algún error, usar el dominio original con contexto de skip
            _logger.warning("Error en _search de stock.lot: %s", str(e))
            return super()._search(domain, offset=offset, limit=limit, order=order, **kwargs)

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, order=None):
        """Sobrescribe la búsqueda para buscar también por placa de inventario.
        Prioriza la búsqueda en inventory_plate sobre name.
        Busca en ambos campos simultáneamente cuando se escribe en la barra de búsqueda general."""
        if args is None:
            args = []
        
        # Si hay un término de búsqueda, buscar tanto en 'inventory_plate' como en 'name'
        # Priorizar inventory_plate primero, pero buscar en ambos campos
        if name and name.strip():
            # Buscar en ambos campos usando OR
            # Esto permite encontrar resultados tanto por placa como por número de serie
            domain = [
                '|',
                ('inventory_plate', operator, name.strip()),  # Prioridad: buscar primero en placa
                ('name', operator, name.strip())
            ]
            # Combinar con los args existentes usando AND
            if args:
                domain = ['&'] + domain + args
            args = domain
            # Llamar al método padre con name='' porque ya construimos el dominio completo
            return super()._name_search(name='', args=args, operator=operator, limit=limit, order=order)
        
        # Si no hay término de búsqueda, usar el método padre normal
        return super()._name_search(name=name, args=args, operator=operator, limit=limit, order=order)

    def action_view_components(self):
        """Ver componentes asociados a este producto principal."""
        self.ensure_one()
        if not self.lot_supply_line_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin componentes'),
                    'message': _('Este producto no tiene componentes asociados.'),
                    'type': 'info',
                    'sticky': False,
                }
            }
        
        # Obtener los lotes de componentes
        component_lots = self.lot_supply_line_ids.mapped('related_lot_id')
        
        return {
            'name': _('Componentes de %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'stock.lot',
            'view_mode': 'list,form',
            'domain': [('id', 'in', component_lots.ids)],
            'context': {'default_is_principal': False},
            'target': 'current',
        }

    def action_view_customer_products(self):
        """Abrir vista de productos de este cliente."""
        self.ensure_one()
        if not self.customer_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin cliente'),
                    'message': _('Este producto no tiene cliente asignado.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        return {
            'name': _('Inventario de %s') % self.customer_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'stock.lot',
            'view_mode': 'kanban,list,form',
            'domain': [('customer_id', '=', self.customer_id.id)],
            'context': {'default_customer_id': self.customer_id.id},
            'target': 'current',
        }
    
    @api.depends('lot_image', 'product_id', 'product_id.image_1920')
    def _compute_report_image(self):
        """Calcular imagen para reportes - lee desde attachments si es necesario."""
        for record in self:
            image_data = False
            
            # Con attachment=True, la imagen se guarda en ir.attachment
            # Intentar leer desde attachment primero
            if record.id:
                try:
                    attachment = self.env['ir.attachment'].sudo().search([
                        ('res_model', '=', 'stock.lot'),
                        ('res_id', '=', record.id),
                        ('res_field', '=', 'lot_image'),
                    ], limit=1)
                    if attachment and attachment.datas:
                        image_data = attachment.datas
                except Exception:
                    pass
            
            # Si no está en attachment, intentar el campo directamente
            if not image_data:
                try:
                    # Leer el campo binario explícitamente
                    lot_data = record.sudo().read(['lot_image'])
                    if lot_data and lot_data[0].get('lot_image'):
                        image_data = lot_data[0]['lot_image']
                except Exception:
                    pass
            
            # Si no hay imagen en lot, usar la del producto
            if not image_data and record.product_id:
                try:
                    # Leer la imagen del producto
                    product_data = record.product_id.sudo().read(['image_1920'])
                    if product_data and product_data[0].get('image_1920'):
                        image_data = product_data[0]['image_1920']
                except Exception:
                    pass
            
            record.report_image = image_data
    
    def _get_image_base64(self):
        """Obtener imagen en formato base64 string para reportes."""
        self.ensure_one()
        # Usar el campo computed
        if self.report_image:
            return self.report_image
        return False
    
    def _get_report_image(self):
        """Obtener imagen para reportes - método helper que asegura que el campo esté disponible."""
        self.ensure_one()
        
        # Con attachment=True, la imagen se guarda en ir.attachment
        # Intentar leer desde el attachment primero
        try:
            attachment = self.env['ir.attachment'].sudo().search([
                ('res_model', '=', 'stock.lot'),
                ('res_id', '=', self.id),
                ('res_field', '=', 'lot_image'),
            ], limit=1)
            if attachment and attachment.datas:
                return attachment.datas
        except Exception:
            pass
        
        # Si no está en attachment, intentar acceder al campo directamente
        try:
            if hasattr(self, 'lot_image') and self.lot_image:
                # Forzar la lectura del campo binario
                self.sudo().invalidate_recordset(['lot_image'])
                if self.lot_image:
                    return self.lot_image
        except Exception:
            pass
        
        # Si no hay imagen en lot, intentar con la del producto
        if self.product_id:
            try:
                if hasattr(self.product_id, 'image_1920') and self.product_id.image_1920:
                    # Forzar la lectura del campo binario del producto
                    self.product_id.sudo().invalidate_recordset(['image_1920'])
                    if self.product_id.image_1920:
                        return self.product_id.image_1920
            except Exception:
                pass
        
        return False
    
    def action_generate_life_sheet(self):
        """Generar hoja de vida del producto con historial de mantenimientos en PDF."""
        self.ensure_one()
        
        # Forzar el cálculo del campo computed report_image antes de generar el reporte
        # Esto asegura que la imagen esté disponible incluso si viene de attachments
        self._compute_report_image()
        
        # Preparar datos para el reporte
        report = self.env.ref('mesa_ayuda_inventario.action_report_stock_lot_life_sheet')
        return report.report_action(self)
    
    def action_generate_all_life_sheets_for_customer(self):
        """Generar PDF combinado con todas las hojas de vida del cliente actual.
        Este método puede ser llamado desde una acción de servidor o desde un botón.
        Si no hay registros seleccionados, usa el contexto para obtener el cliente."""
        # Obtener el cliente desde el contexto primero
        customer_id = self.env.context.get('active_partner_id') or self.env.context.get('default_customer_id')
        
        if not customer_id:
            # Si hay registros seleccionados, intentar obtener el cliente desde ellos
            if self:
                customers = self.mapped('customer_id')
                if len(customers) == 1:
                    customer_id = customers.id
                elif len(customers) > 1:
                    raise UserError(_('Hay múltiples clientes en los registros seleccionados. Por favor, asegúrese de estar visualizando el inventario de un cliente específico.'))
                else:
                    # Si no hay customer_id en los lotes, buscar por ubicación
                    locations = self.mapped('customer_location_id')
                    if locations:
                        # Buscar partners con estas ubicaciones
                        partners = self.env['res.partner'].search([
                            ('property_stock_customer', 'in', locations.ids)
                        ])
                        if len(partners) == 1:
                            customer_id = partners.id
                    
                    if not customer_id:
                        raise UserError(_('No se pudo determinar el cliente para generar las hojas de vida. Por favor, asegúrese de estar visualizando el inventario de un cliente específico.'))
            else:
                # Si no hay registros seleccionados, buscar el cliente desde el dominio de la vista
                # Esto es útil cuando se llama desde una acción de servidor sin selección
                active_domain = self.env.context.get('active_domain', [])
                for domain_item in active_domain:
                    if isinstance(domain_item, (list, tuple)) and len(domain_item) == 3:
                        field, operator, value = domain_item
                        if field == 'customer_id' and operator in ('=', 'in'):
                            if operator == '=':
                                customer_id = value
                            elif operator == 'in' and isinstance(value, list) and len(value) == 1:
                                customer_id = value[0]
                            break
                
                if not customer_id:
                    raise UserError(_('No se pudo determinar el cliente para generar las hojas de vida. Por favor, asegúrese de estar visualizando el inventario de un cliente específico.'))
        
        customer = self.env['res.partner'].browse(customer_id)
        if not customer.exists():
            raise UserError(_('El cliente especificado no existe.'))
        
        return customer.action_generate_all_life_sheets()
    
    def action_equipment_change(self):
        """Abrir wizard para crear actividad de cambio de equipo."""
        self.ensure_one()
        
        # Obtener el cliente directamente desde customer_id
        partner_id = self.customer_id.id if self.customer_id else False
        
        return {
            'name': _('Cambio de Equipo'),
            'type': 'ir.actions.act_window',
            'res_model': 'equipment.change.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_lot_id': self.id,
                'default_partner_id': partner_id,
            }
        }
    
    def action_request_element(self):
        """Abrir wizard para solicitar un elemento/componente."""
        self.ensure_one()
        
        # Obtener el cliente directamente desde customer_id
        partner_id = self.customer_id.id if self.customer_id else False
        
        return {
            'name': _('Solicitar Elemento/Componente'),
            'type': 'ir.actions.act_window',
            'res_model': 'request.element.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_lot_id': self.id,
                'default_partner_id': partner_id,
            }
        }
    
    @api.model
    def action_switch_to_list_view(self):
        """Cambiar a vista lista con agrupación jerárquica."""
        # Obtener el cliente del contexto
        customer_id = self.env.context.get('active_partner_id') or self.env.context.get('default_customer_id')
        
        # Si no está en el contexto, intentar obtener del dominio o de los registros visibles
        if not customer_id:
            # Buscar en los registros actuales (si hay alguno seleccionado)
            active_ids = self.env.context.get('active_ids', [])
            if active_ids:
                lots = self.browse(active_ids)
                customers = lots.mapped('customer_id').filtered(lambda c: c)
                if customers:
                    # Usar el customer_id más común
                    customer_id = customers[0].id
        
        # Si aún no hay customer_id, intentar obtenerlo del dominio de la acción actual
        if not customer_id:
            # Buscar en la acción actual
            action = self.env['ir.actions.act_window'].search([
                ('res_model', '=', 'stock.lot'),
                ('name', 'ilike', 'Cliente Supplies')
            ], limit=1)
            if action and action.domain:
                # Intentar extraer customer_id del dominio
                import ast
                try:
                    domain = ast.literal_eval(action.domain) if isinstance(action.domain, str) else action.domain
                    for condition in domain:
                        if isinstance(condition, (list, tuple)) and len(condition) >= 3:
                            if condition[0] == 'customer_id' and condition[1] == '=':
                                customer_id = condition[2]
                                break
                except:
                    pass
        
        if not customer_id:
            raise UserError(_('No se pudo determinar el cliente para cambiar de vista. Por favor, asegúrate de estar viendo el inventario de un cliente específico.'))
        
        customer = self.env['res.partner'].browse(customer_id)
        return customer.action_view_customer_inventory_list()
    
    @api.model
    def action_switch_to_kanban_view(self):
        """Cambiar a vista kanban sin agrupación."""
        # Obtener el cliente del contexto
        customer_id = self.env.context.get('active_partner_id') or self.env.context.get('default_customer_id')
        
        # Si no está en el contexto, intentar obtener del dominio o de los registros visibles
        if not customer_id:
            # Buscar en los registros actuales (si hay alguno seleccionado)
            active_ids = self.env.context.get('active_ids', [])
            if active_ids:
                lots = self.browse(active_ids)
                customers = lots.mapped('customer_id').filtered(lambda c: c)
                if customers:
                    # Usar el customer_id más común
                    customer_id = customers[0].id
        
        # Si aún no hay customer_id, intentar obtenerlo del dominio de la acción actual
        if not customer_id:
            # Buscar en la acción actual
            action = self.env['ir.actions.act_window'].search([
                ('res_model', '=', 'stock.lot'),
                ('name', 'ilike', 'Cliente Supplies')
            ], limit=1)
            if action and action.domain:
                # Intentar extraer customer_id del dominio
                import ast
                try:
                    domain = ast.literal_eval(action.domain) if isinstance(action.domain, str) else action.domain
                    for condition in domain:
                        if isinstance(condition, (list, tuple)) and len(condition) >= 3:
                            if condition[0] == 'customer_id' and condition[1] == '=':
                                customer_id = condition[2]
                                break
                except:
                    pass
        
        if not customer_id:
            raise UserError(_('No se pudo determinar el cliente para cambiar de vista. Por favor, asegúrate de estar viendo el inventario de un cliente específico.'))
        
        customer = self.env['res.partner'].browse(customer_id)
        return customer.action_view_customer_inventory_kanban()
    
    def action_view_component_changes(self):
        """Abrir vista del historial completo de cambios de componentes para este equipo."""
        self.ensure_one()
        
        # Obtener todos los cambios de componentes relacionados con este equipo
        all_changes = self.env['maintenance.component.change']
        for maintenance in self.maintenance_ids:
            all_changes |= maintenance.component_change_ids
        
        # Obtener los IDs únicos
        change_ids = all_changes.sorted('change_date', reverse=True).ids
        
        return {
            'name': _('Historial de Cambios de Componentes - %s') % (self.name or ''),
            'type': 'ir.actions.act_window',
            'res_model': 'maintenance.component.change',
            'view_mode': 'list,form',
            'domain': [('id', 'in', change_ids)],
            'context': {
                'default_lot_id': self.id,
                'search_default_lot_id': self.id,
            },
            'target': 'current',
        }
