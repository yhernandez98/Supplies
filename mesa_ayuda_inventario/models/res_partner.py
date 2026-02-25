# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
import io
import base64

_logger = logging.getLogger(__name__)

try:
    from PyPDF2 import PdfReader, PdfWriter
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False
    _logger.warning("PyPDF2 no está disponible. No se podrán combinar PDFs múltiples.")

class ResPartner(models.Model):
    """Extender res.partner para agregar funcionalidad de inventario de clientes."""
    _inherit = 'res.partner'

    product_count = fields.Integer(
        string='Cantidad de Productos',
        compute='_compute_product_count',
        store=False,
        help='Cantidad de productos en inventario de este cliente'
    )
    
    @api.depends('property_stock_customer')
    def _compute_product_count(self):
        """Calcular cantidad de productos en inventario del cliente.
        OPTIMIZADO: Procesa en batch y reduce consultas SQL."""
        Quant = self.env['stock.quant']
        Lot = self.env['stock.lot']
        SupplyLine = self.env['stock.lot.supply.line']
        
        # Filtrar partners con ubicación
        partners_with_location = self.filtered(lambda p: p.property_stock_customer)
        partners_without_location = self - partners_with_location
        
        # Inicializar partners sin ubicación
        for partner in partners_without_location:
            partner.product_count = 0
        
        if not partners_with_location:
            return
        
        # OPTIMIZACIÓN: Buscar todos los lotes de todos los partners de una vez
        partner_ids = partners_with_location.ids
        location_ids = partners_with_location.mapped('property_stock_customer').ids
        
        # 1. Buscar lotes por customer_id (una consulta para todos)
        lots_by_customer = Lot.search([('customer_id', 'in', partner_ids)])
        lot_ids_by_customer = {}
        for lot in lots_by_customer:
            if lot.customer_id.id not in lot_ids_by_customer:
                lot_ids_by_customer[lot.customer_id.id] = []
            lot_ids_by_customer[lot.customer_id.id].append(lot.id)
        
        # 2. Buscar lotes por ubicación (una consulta para todos)
        lot_ids_by_location = {}
        if location_ids:
            quants = Quant.search([
                ('location_id', 'in', location_ids),
                ('quantity', '>', 0),
                ('lot_id', '!=', False),
            ])
            for quant in quants:
                partner = partners_with_location.filtered(lambda p: p.property_stock_customer.id == quant.location_id.id)
                if partner:
                    partner_id = partner[0].id
                    if partner_id not in lot_ids_by_location:
                        lot_ids_by_location[partner_id] = []
                    lot_ids_by_location[partner_id].append(quant.lot_id.id)
        
        # 3. Pre-cargar componentes asociados UNA VEZ para todos los lotes relevantes
        all_lot_ids_combined = set()
        for lot_ids in list(lot_ids_by_customer.values()) + list(lot_ids_by_location.values()):
            all_lot_ids_combined.update(lot_ids)
        
        # Buscar componentes asociados SOLO de los lotes del cliente (no todos del sistema)
        associated_component_lot_ids = set()
        if all_lot_ids_combined:
            try:
                # OPTIMIZACIÓN: Solo buscar componentes que estén en los lotes del cliente
                component_lines = SupplyLine.search([
                    ('item_type', '=', 'component'),
                    ('related_lot_id', 'in', list(all_lot_ids_combined)),
                    ('related_lot_id', '!=', False),
                ])
                
                # Validar clasificación del producto (batch)
                component_lot_ids = component_lines.mapped('related_lot_id').filtered(
                    lambda l: l.product_id and l.product_id.classification == 'component'
                ).ids
                associated_component_lot_ids = set(component_lot_ids)
            except Exception:
                pass
        
        # 4. Calcular count para cada partner
        for partner in partners_with_location:
            partner_lot_ids = set()
            
            # Agregar lotes por customer_id
            if partner.id in lot_ids_by_customer:
                partner_lot_ids.update(lot_ids_by_customer[partner.id])
            
            # Agregar lotes por ubicación
            if partner.id in lot_ids_by_location:
                partner_lot_ids.update(lot_ids_by_location[partner.id])
            
            # Excluir componentes asociados
            partner_lot_ids -= associated_component_lot_ids
            
            partner.product_count = len(partner_lot_ids)
    
    def action_view_customer_inventory(self):
        """Abrir vista de inventario de productos de este cliente.
        OPTIMIZADO: Reduce consultas y elimina código de debug.
        Excluye SOLO los componentes que estén asociados a un producto principal.
        Muestra TODO lo demás: productos principales, periféricos, complementos y componentes NO asociados."""
        self.ensure_one()
        # IMPORTANTÍSIMO:
        # Esta acción es la que usa el botón "Ver Inventario" del usuario final.
        # Para evitar que la agrupación (group_by) afecte Kanban, siempre entramos por la acción Kanban,
        # y la vista Lista se abre por la acción separada de Lista (que sí va agrupada por defecto).
        return self.action_view_customer_inventory_kanban()
        
    
    def _get_customer_inventory_domain(self):
        """Método auxiliar para obtener el dominio de inventario del cliente."""
        self.ensure_one()
        
        Lot = self.env['stock.lot']
        Quant = self.env['stock.quant']
        SupplyLine = self.env['stock.lot.supply.line']
        customer_location = self.property_stock_customer
        
        # Buscar lotes del cliente
        lot_ids_by_customer = Lot.search([('customer_id', '=', self.id)]).ids
        
        # Buscar lotes por ubicación
        lot_ids_by_location = []
        if customer_location:
            try:
                quants = Quant.search([
                    ('location_id', '=', customer_location.id),
                    ('quantity', '>', 0),
                    ('lot_id', '!=', False),
                ])
                lot_ids_by_location = quants.mapped('lot_id').ids
            except Exception:
                pass
        
        # Combinar ambos métodos (estos IDs ya son el "alcance" del cliente)
        all_lot_ids = list(set(lot_ids_by_customer + lot_ids_by_location))
        
        # Dominio base: SIEMPRE acotar por IDs (evita que filtros con OR "rompan" el alcance)
        if not all_lot_ids:
            domain = [('id', '=', False)]
        else:
            domain = [('id', 'in', all_lot_ids)]
        
        # Excluir componentes asociados
        try:
            if all_lot_ids:
                component_lines = SupplyLine.search([
                    ('item_type', '=', 'component'),
                    ('related_lot_id', 'in', all_lot_ids),
                    ('related_lot_id', '!=', False),
                ])
                component_lots = component_lines.mapped('related_lot_id').filtered(
                    lambda l: l.product_id and l.product_id.classification == 'component'
                )
                associated_component_lot_ids = component_lots.ids
                component_lots_no_product = component_lines.mapped('related_lot_id').filtered(
                    lambda l: not l.product_id
                )
                associated_component_lot_ids.extend(component_lots_no_product.ids)
                associated_component_lot_ids = list(set(associated_component_lot_ids))
                
                if associated_component_lot_ids:
                    domain.append(('id', 'not in', associated_component_lot_ids))
        except Exception:
            pass
        
        return domain
    
    def action_view_customer_inventory_kanban(self):
        """Abrir vista kanban de inventario usando acción separada."""
        self.ensure_one()
        # Persistir en sesión para que al recargar (F5) se mantenga el alcance del cliente
        try:
            from odoo.http import request
            if request and getattr(request, 'session', None) is not None:
                request.session['customer_inventory_partner_id'] = self.id
        except Exception:
            pass
        domain = self._get_customer_inventory_domain()
        # Guardar el alcance (IDs) en contexto para blindar filtros en lista/kanban
        allowed_ids = []
        for d in domain:
            if isinstance(d, (list, tuple)) and len(d) >= 3 and d[0] == 'id' and d[1] == 'in':
                allowed_ids = d[2] or []
                break
        
        # Usar la acción separada para kanban
        action = self.env.ref('mesa_ayuda_inventario.action_customer_inventory_kanban_only', raise_if_not_found=False)
        if not action:
            # Fallback a la implementación anterior
            view_id = self.env.ref('mesa_ayuda_inventario.view_customer_inventory_lot_kanban_simple', raise_if_not_found=False)
            form_view_id = self.env.ref('product_suppiles.view_production_lot_form_inherit_supplies', raise_if_not_found=False)
            if not form_view_id:
                form_view_id = self.env.ref('stock.view_production_lot_form', raise_if_not_found=False)
            
            return {
                'name': _('Cliente Supplies - %s') % self.name,
                'type': 'ir.actions.act_window',
                'res_model': 'stock.lot',
                'view_mode': 'kanban,form',
                'view_id': view_id.id if view_id else False,
                'views': [
                    (view_id.id if view_id else False, 'kanban'),
                    (form_view_id.id if form_view_id else False, 'form')
                ],
                'domain': domain,
                'context': {
                    'default_customer_id': self.id,
                    'active_partner_id': self.id,
                    'customer_inventory_allowed_lot_ids': allowed_ids,
                },
                'target': 'current',
            }
        
        # Usar la acción separada y modificar dominio y contexto
        # IMPORTANTE: Incluimos 'list' para que aparezca el switcher nativo,
        # pero el contexto fuerza que Kanban NO tenga agrupación
        # sudo(): evita error de acceso para usuarios no Administración/Ajustes (leen el registro ir.actions.act_window)
        action_dict = action.sudo().read()[0]
        action_dict['domain'] = domain
        action_dict['view_mode'] = 'kanban,list,form'
        kanban_view = self.env.ref('mesa_ayuda_inventario.view_customer_inventory_lot_kanban_simple', raise_if_not_found=False)
        list_view = self.env.ref('mesa_ayuda_inventario.view_stock_lot_tree_hierarchical', raise_if_not_found=False)
        # Usar formulario de product_suppiles (Placa, Código, Referencia, etc.) si está instalado; si no, el de stock
        form_view = self.env.ref('product_suppiles.view_production_lot_form_inherit_supplies', raise_if_not_found=False)
        if not form_view:
            form_view = self.env.ref('stock.view_production_lot_form', raise_if_not_found=False)
        action_dict['views'] = [
            (kanban_view.id if kanban_view else False, 'kanban'),
            (list_view.id if list_view else False, 'list'),
            (form_view.id if form_view else False, 'form'),
        ]
        # IMPORTANTE:
        # - En Kanban NO queremos agrupación por defecto (ni que herede group_by guardado)
        # - En Lista sí se aplica agrupación, pero eso lo gestionamos en la acción "Lista" separada
        action_dict['context'] = {
            'default_customer_id': self.id,
            'active_partner_id': self.id,
            'customer_inventory_allowed_lot_ids': allowed_ids,
        }
        action_dict['name'] = _('Cliente Supplies - %s') % self.name
        return action_dict
    
    def action_view_customer_inventory_list(self):
        """Abrir vista lista de inventario usando acción separada."""
        self.ensure_one()
        # Persistir en sesión para que al recargar (F5) se mantenga el alcance del cliente
        try:
            from odoo.http import request
            if request and getattr(request, 'session', None) is not None:
                request.session['customer_inventory_partner_id'] = self.id
        except Exception:
            pass
        domain = self._get_customer_inventory_domain()
        # Guardar el alcance (IDs) en contexto para blindar filtros en lista
        allowed_ids = []
        for d in domain:
            if isinstance(d, (list, tuple)) and len(d) >= 3 and d[0] == 'id' and d[1] == 'in':
                allowed_ids = d[2] or []
                break
        
        # Usar la acción separada para lista
        action = self.env.ref('mesa_ayuda_inventario.action_customer_inventory_list_only', raise_if_not_found=False)
        if not action:
            # Fallback a la implementación anterior
            tree_hierarchical_id = self.env.ref('mesa_ayuda_inventario.view_stock_lot_tree_hierarchical', raise_if_not_found=False)
            form_view_id = self.env.ref('product_suppiles.view_production_lot_form_inherit_supplies', raise_if_not_found=False)
            if not form_view_id:
                form_view_id = self.env.ref('stock.view_production_lot_form', raise_if_not_found=False)
            
            return {
                'name': _('Inventario Lista - %s') % self.name,
                'type': 'ir.actions.act_window',
                'res_model': 'stock.lot',
                'view_mode': 'list,form',
                'view_id': tree_hierarchical_id.id if tree_hierarchical_id else False,
                'views': [
                    (tree_hierarchical_id.id if tree_hierarchical_id else False, 'list'),
                    (form_view_id.id if form_view_id else False, 'form')
                ],
                'domain': domain,
                'context': {
                    'default_customer_id': self.id,
                    'active_partner_id': self.id,
                    'group_by': ['customer_id', 'product_asset_category_id', 'product_asset_class_id'],
                    'customer_inventory_allowed_lot_ids': allowed_ids,
                },
                'target': 'current',
            }
        
        # Usar la acción separada y modificar dominio y contexto (FORZADO)
        # sudo(): evita error de acceso para usuarios no Administración/Ajustes (leen el registro ir.actions.act_window)
        action_dict = action.sudo().read()[0]
        action_dict['domain'] = domain
        action_dict['view_mode'] = 'list,form'
        list_view = self.env.ref('mesa_ayuda_inventario.view_stock_lot_tree_hierarchical', raise_if_not_found=False)
        # Usar formulario de product_suppiles (Placa, Código, Referencia, etc.) si está instalado; si no, el de stock
        form_view = self.env.ref('product_suppiles.view_production_lot_form_inherit_supplies', raise_if_not_found=False)
        if not form_view:
            form_view = self.env.ref('stock.view_production_lot_form', raise_if_not_found=False)
        action_dict['views'] = [
            (list_view.id if list_view else False, 'list'),
            (form_view.id if form_view else False, 'form'),
        ]
        action_dict['context'] = {
            'default_customer_id': self.id,
            'active_partner_id': self.id,
            'customer_inventory_allowed_lot_ids': allowed_ids,
        }
        action_dict['name'] = _('Inventario Lista - %s') % self.name
        return action_dict
    
    def action_view_customer_inventory_detailed(self):
        """Abrir vista detallada de inventario (kanban por defecto, pero con opción de lista)."""
        # Por defecto abre kanban, pero mantiene compatibilidad
        return self.action_view_customer_inventory_kanban()
    
    def action_debug_customer_inventory(self):
        """Botón temporal de debug para validar qué está pasando con el filtro."""
        self.ensure_one()
        import logging
        _logger = logging.getLogger(__name__)
        
        debug_info = []
        debug_info.append("=" * 80)
        debug_info.append("DEBUG - INVENTARIO DE CLIENTE")
        debug_info.append("=" * 80)
        debug_info.append("")
        debug_info.append(f"Cliente: {self.name} (ID: {self.id})")
        debug_info.append("")
        
        # 1. Buscar todos los lotes del cliente (por customer_id Y por ubicación)
        Lot = self.env['stock.lot']
        Quant = self.env['stock.quant']
        
        # Buscar por customer_id
        lots_by_customer_id = Lot.search([('customer_id', '=', self.id)])
        debug_info.append(f"1a. LOTES POR customer_id: {len(lots_by_customer_id)}")
        for lot in lots_by_customer_id:
            debug_info.append(f"   - ID: {lot.id}, Serial: {lot.name}, Producto: {lot.product_id.name if lot.product_id else 'N/A'}")
        debug_info.append("")
        
        # Buscar por ubicación del cliente
        lot_ids_by_location = []
        customer_location = self.property_stock_customer
        if customer_location:
            try:
                quants = Quant.search([
                    ('location_id', '=', customer_location.id),
                    ('quantity', '>', 0),
                    ('lot_id', '!=', False),
                ])
                lot_ids_by_location = quants.mapped('lot_id').ids
                debug_info.append(f"1b. LOTES POR UBICACIÓN ({customer_location.name}): {len(lot_ids_by_location)}")
                lots_by_location = Lot.browse(lot_ids_by_location)
                for lot in lots_by_location:
                    debug_info.append(f"   - ID: {lot.id}, Serial: {lot.name}, Producto: {lot.product_id.name if lot.product_id else 'N/A'}")
            except Exception as e:
                debug_info.append(f"1b. ERROR al buscar por ubicación: {str(e)}")
        else:
            debug_info.append(f"1b. El cliente no tiene ubicación asignada")
        debug_info.append("")
        
        # Combinar ambos
        all_lot_ids = list(set(lots_by_customer_id.ids + lot_ids_by_location))
        all_customer_lots = Lot.browse(all_lot_ids)
        debug_info.append(f"1. TOTAL DE LOTES DEL CLIENTE (combinado): {len(all_customer_lots)}")
        for lot in all_customer_lots:
            debug_info.append(f"   - ID: {lot.id}, Serial: {lot.name}, Producto: {lot.product_id.name if lot.product_id else 'N/A'}")
        debug_info.append("")
        
        # Verificar específicamente "prueba01"
        prueba01_lot = Lot.search([('name', '=', 'prueba01')], limit=1)
        if prueba01_lot:
            prueba01_in_customer = prueba01_lot.id in all_lot_ids
            debug_info.append(f"🔍 VERIFICACIÓN ESPECIAL: 'prueba01' (ID: {prueba01_lot.id})")
            debug_info.append(f"   - ¿Está en los lotes del cliente? {prueba01_in_customer}")
            debug_info.append(f"   - Clasificación del producto: {prueba01_lot.product_id.classification if prueba01_lot.product_id else 'N/A'}")
            if not prueba01_in_customer:
                debug_info.append(f"   ⚠️ 'prueba01' NO está en los lotes del cliente (por customer_id ni por ubicación)")
                # Verificar si está en alguna ubicación
                quants_prueba01 = Quant.search([('lot_id', '=', prueba01_lot.id), ('quantity', '>', 0)])
                debug_info.append(f"   - Quants de 'prueba01': {len(quants_prueba01)}")
                for q in quants_prueba01:
                    debug_info.append(f"     * Ubicación: {q.location_id.name} (ID: {q.location_id.id}), Cantidad: {q.quantity}")
            debug_info.append("")
        
        # 2. Buscar líneas de suministro
        SupplyLine = self.env['stock.lot.supply.line']
        try:
            all_supply_lines = SupplyLine.search([])
            debug_info.append(f"2. TOTAL DE LÍNEAS DE SUMINISTRO EN EL SISTEMA: {len(all_supply_lines)}")
            
            # Filtrar solo las que son componentes asociados
            associated_component_lines = SupplyLine.search([
                ('item_type', '=', 'component'),
                ('related_lot_id', '!=', False),
                ('lot_id', '!=', False),
            ])
            debug_info.append(f"3. LÍNEAS DE COMPONENTES ASOCIADOS EN EL SISTEMA: {len(associated_component_lines)}")
            # Solo mostrar las primeras 5 líneas como ejemplo
            debug_info.append("   (Mostrando solo las primeras 5 líneas como ejemplo)")
            for line in associated_component_lines[:5]:
                debug_info.append(f"   - Línea {line.id}: Principal={line.lot_id.name if line.lot_id else 'N/A'} (ID:{line.lot_id.id if line.lot_id else 'N/A'}) -> Componente={line.related_lot_id.name if line.related_lot_id else 'N/A'} (ID:{line.related_lot_id.id if line.related_lot_id else 'N/A'})")
            debug_info.append("")
            
            # Verificar también periféricos y complementos asociados (para debug)
            all_associated_lines = SupplyLine.search([
                ('related_lot_id', '!=', False),
                ('lot_id', '!=', False),
            ])
            peripheral_lines = all_associated_lines.filtered(lambda l: l.item_type == 'peripheral')
            complement_lines = all_associated_lines.filtered(lambda l: l.item_type == 'complement')
            debug_info.append(f"3b. LÍNEAS DE PERIFÉRICOS ASOCIADOS: {len(peripheral_lines)}")
            debug_info.append(f"3c. LÍNEAS DE COMPLEMENTOS ASOCIADOS: {len(complement_lines)}")
            debug_info.append("")
            
            # Obtener IDs de componentes asociados (SOLO componentes, con doble verificación)
            associated_component_lot_ids = []
            for line in associated_component_lines:
                if line.item_type == 'component' and line.related_lot_id and line.related_lot_id.id:
                    associated_component_lot_ids.append(line.related_lot_id.id)
            associated_component_lot_ids = list(set(associated_component_lot_ids))
            
            # Verificar específicamente "prueba01" si está asociado
            if prueba01_lot:
                prueba01_lines = SupplyLine.search([
                    ('related_lot_id', '=', prueba01_lot.id),
                ])
                debug_info.append(f"🔍 VERIFICACIÓN ESPECIAL: 'prueba01' (ID: {prueba01_lot.id})")
                debug_info.append(f"   - Líneas de suministro que lo tienen como related_lot_id: {len(prueba01_lines)}")
                for line in prueba01_lines:
                    debug_info.append(f"     * Línea ID: {line.id}, item_type: {line.item_type}, Principal: {line.lot_id.name if line.lot_id else 'N/A'}")
                prueba01_is_component = prueba01_lot.id in associated_component_lot_ids
                debug_info.append(f"   - ¿Está en la lista de exclusión (componentes)? {prueba01_is_component}")
                if prueba01_is_component:
                    debug_info.append(f"     ⚠️ PROBLEMA: 'prueba01' está siendo excluido pero es un periférico")
                else:
                    debug_info.append(f"     ✅ 'prueba01' NO está siendo excluido (correcto, es periférico)")
                debug_info.append("")
            debug_info.append(f"4. IDs DE COMPONENTES ASOCIADOS A EXCLUIR (TODOS): {len(associated_component_lot_ids)} IDs")
            debug_info.append(f"   Primeros 20 IDs: {associated_component_lot_ids[:20]}")
            debug_info.append("")
            
            # Verificar cuáles de estos IDs pertenecen al cliente
            customer_component_ids = [lid for lid in associated_component_lot_ids if lid in all_customer_lots.ids]
            debug_info.append(f"5. IDs DE COMPONENTES ASOCIADOS DEL CLIENTE (serán excluidos): {len(customer_component_ids)} IDs")
            if customer_component_ids:
                debug_info.append(f"   IDs: {customer_component_ids}")
                # Mostrar detalles de estos lotes
                for comp_id in customer_component_ids:
                    comp_lot = Lot.browse(comp_id)
                    if comp_lot.exists():
                        debug_info.append(f"   - ID: {comp_id}, Serial: {comp_lot.name}, Producto: {comp_lot.product_id.name if comp_lot.product_id else 'N/A'}")
            else:
                debug_info.append("   ✅ NINGÚN componente asociado pertenece a este cliente")
            debug_info.append("")
            
            # Construir dominio (igual que en action_view_customer_inventory)
            # Buscar por customer_id O por ubicación del cliente
            domain = []
            if customer_location:
                domain = [
                    '|',
                    ('customer_id', '=', self.id),
                    ('customer_location_id', '=', customer_location.id),
                ]
            else:
                domain = [('customer_id', '=', self.id)]
            
            if associated_component_lot_ids:
                domain.append(('id', 'not in', associated_component_lot_ids))
            debug_info.append(f"6. DOMINIO FINAL: {domain}")
            debug_info.append("")
            
            # Verificar si los lotes del cliente están en la lista de exclusión (PROBLEMA)
            debug_info.append(f"7. VERIFICACIÓN: ¿Los lotes del cliente están siendo excluidos incorrectamente?")
            for lot in all_customer_lots:
                is_excluded = lot.id in associated_component_lot_ids
                debug_info.append(f"   - Lote ID {lot.id} (Serial: {lot.name}): {'❌ EXCLUIDO' if is_excluded else '✅ NO excluido'}")
                if is_excluded:
                    debug_info.append(f"     ⚠️ PROBLEMA: Este lote está en la lista de exclusión pero es del cliente")
                    # Verificar si realmente es un componente asociado
                    is_associated_component = any(
                        line.related_lot_id.id == lot.id and line.item_type == 'component'
                        for line in associated_component_lines
                    )
                    debug_info.append(f"     ¿Es realmente un componente asociado? {is_associated_component}")
            debug_info.append("")
            
            # Buscar con el dominio
            filtered_lots = Lot.search(domain)
            debug_info.append(f"8. LOTES DESPUÉS DEL FILTRO: {len(filtered_lots)}")
            for lot in filtered_lots:
                debug_info.append(f"   - ID: {lot.id}, Serial: {lot.name}, Producto: {lot.product_id.name if lot.product_id else 'N/A'}")
            debug_info.append("")
            
            # Verificar qué lotes se están excluyendo
            excluded_lots = all_customer_lots.filtered(lambda l: l.id in associated_component_lot_ids)
            debug_info.append(f"9. LOTES EXCLUIDOS (del cliente): {len(excluded_lots)}")
            if excluded_lots:
                for lot in excluded_lots:
                    debug_info.append(f"   - ID: {lot.id}, Serial: {lot.name}, Producto: {lot.product_id.name if lot.product_id else 'N/A'}")
            else:
                debug_info.append("   ✅ Ningún lote del cliente está siendo excluido")
            debug_info.append("")
            
            # Verificar lotes que NO se están excluyendo pero deberían
            remaining_lots = all_customer_lots - filtered_lots
            if remaining_lots:
                debug_info.append(f"10. ⚠️ LOTES QUE FALTAN (deberían mostrarse pero no se muestran): {len(remaining_lots)}")
                for lot in remaining_lots:
                    debug_info.append(f"   - ID: {lot.id}, Serial: {lot.name}, Producto: {lot.product_id.name if lot.product_id else 'N/A'}")
                    # Verificar si es componente, periférico o complemento
                    if lot.product_id:
                        classification = getattr(lot.product_id, 'classification', False)
                        debug_info.append(f"     Clasificación del producto: {classification}")
            else:
                debug_info.append(f"10. ✅ Todos los lotes del cliente se están mostrando correctamente")
            debug_info.append("")
            
        except Exception as e:
            debug_info.append(f"ERROR: {str(e)}")
            import traceback
            debug_info.append(traceback.format_exc())
        
        debug_info.append("=" * 80)
        debug_text = "\n".join(debug_info)
        
        # Log también en el servidor
        _logger.warning("\n" + debug_text)
        
        # Mostrar en notificación
        message = debug_text[:5000] if len(debug_text) > 5000 else debug_text
        if len(debug_text) > 5000:
            message += "\n\n... (mensaje truncado, ver logs del servidor para información completa)"
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': '🔍 Debug - Inventario de Cliente',
                'message': message,
                'type': 'warning',
                'sticky': True,
            }
        }
    
    def action_generate_all_life_sheets(self):
        """Generar un PDF combinado con todas las hojas de vida de los productos del cliente."""
        self.ensure_one()
        
        # Obtener todos los lotes del cliente usando la misma lógica que action_view_customer_inventory
        Lot = self.env['stock.lot']
        Quant = self.env['stock.quant']
        SupplyLine = self.env['stock.lot.supply.line']
        customer_location = self.property_stock_customer
        
        # Buscar lotes del cliente
        lot_ids_by_customer = Lot.search([('customer_id', '=', self.id)]).ids
        
        # Buscar lotes por ubicación
        lot_ids_by_location = []
        if customer_location:
            try:
                quants = Quant.search([
                    ('location_id', '=', customer_location.id),
                    ('quantity', '>', 0),
                    ('lot_id', '!=', False),
                ])
                lot_ids_by_location = quants.mapped('lot_id').ids
            except Exception:
                pass
        
        # Combinar ambos métodos
        all_lot_ids = list(set(lot_ids_by_customer + lot_ids_by_location))
        
        if not all_lot_ids:
            raise UserError(_('No se encontraron productos en el inventario de este cliente.'))
        
        # Excluir componentes asociados (igual que en action_view_customer_inventory)
        try:
            if all_lot_ids:
                component_lines = SupplyLine.search([
                    ('item_type', '=', 'component'),
                    ('related_lot_id', 'in', all_lot_ids),
                    ('related_lot_id', '!=', False),
                ])
                component_lots = component_lines.mapped('related_lot_id').filtered(
                    lambda l: l.product_id and l.product_id.classification == 'component'
                )
                associated_component_lot_ids = component_lots.ids
                component_lots_no_product = component_lines.mapped('related_lot_id').filtered(
                    lambda l: not l.product_id
                )
                associated_component_lot_ids.extend(component_lots_no_product.ids)
                associated_component_lot_ids = list(set(associated_component_lot_ids))
                
                if associated_component_lot_ids:
                    all_lot_ids = [lid for lid in all_lot_ids if lid not in associated_component_lot_ids]
        except Exception:
            pass
        
        if not all_lot_ids:
            raise UserError(_('No se encontraron productos principales para generar las hojas de vida.'))
        
        # Obtener los lotes
        lots = Lot.browse(all_lot_ids)
        if not lots.exists():
            raise UserError(_('No se encontraron lotes válidos para generar el reporte.'))
        
        # Generar el reporte
        try:
            report = self.env.ref('mesa_ayuda_inventario.action_report_stock_lot_life_sheet')
            
            # Si hay un solo lote, generar directamente (funciona bien)
            if len(lots) == 1:
                return report.report_action(lots)
            
            # Para múltiples lotes, generar uno por uno y combinar
            if not PYPDF2_AVAILABLE:
                # Si PyPDF2 no está disponible, generar solo el primero
                _logger.warning("PyPDF2 no disponible. Generando solo el primer lote.")
                return report.report_action(lots[0])
            
            _logger.info("Generando PDF combinado para %d lotes", len(lots))
            
            # Generar PDFs individuales para cada lote
            pdf_writer = PdfWriter()
            report_ref = report.report_name or 'mesa_ayuda_inventario.report_stock_lot_life_sheet'
            
            for lot in lots:
                try:
                    # Generar PDF para este lote
                    pdf_content, _ = report._render_qweb_pdf(report_ref, res_ids=[lot.id], data=None)
                    if pdf_content:
                        # Leer el PDF generado
                        pdf_reader = PdfReader(io.BytesIO(pdf_content))
                        # Agregar todas las páginas al writer
                        for page_num in range(len(pdf_reader.pages)):
                            pdf_writer.add_page(pdf_reader.pages[page_num])
                        _logger.info("PDF generado para lote ID %s", lot.id)
                except Exception as e:
                    _logger.warning("Error al generar PDF para lote ID %s: %s", lot.id, str(e))
                    continue
            
            if len(pdf_writer.pages) == 0:
                raise UserError(_('No se pudo generar ningún PDF. Verifique los logs para más detalles.'))
            
            # Combinar todos los PDFs en uno solo
            output_pdf = io.BytesIO()
            pdf_writer.write(output_pdf)
            output_pdf.seek(0)
            combined_pdf_content = output_pdf.read()
            
            # Crear un attachment temporal con el PDF combinado
            # Nota: Este attachment NO se elimina automáticamente
            # Se guarda en la base de datos asociado al cliente
            # Si quieres limpiarlos periódicamente, puedes usar un cron job
            attachment_name = 'Hojas_de_Vida_%s_%s.pdf' % (
                (self.name or 'Cliente').replace(' ', '_').replace('/', '_'),
                fields.Datetime.now().strftime('%Y%m%d_%H%M%S')
            )
            attachment = self.env['ir.attachment'].sudo().create({
                'name': attachment_name,
                'type': 'binary',
                'datas': base64.b64encode(combined_pdf_content),
                'res_model': 'res.partner',
                'res_id': self.id,
                'mimetype': 'application/pdf',
            })
            
            # Retornar acción para descargar el attachment
            return {
                'type': 'ir.actions.act_url',
                'url': '/web/content/%s?download=true' % attachment.id,
                'target': 'self',
            }
            
        except UserError:
            # Re-lanzar UserError sin modificar
            raise
        except Exception as e:
            import traceback
            _logger.error("Error al generar reporte de hojas de vida: %s\n%s", str(e), traceback.format_exc())
            raise UserError(_('Error al generar el reporte de hojas de vida: %s\n\nPor favor, contacte al administrador.') % str(e))
    
    @api.model
    def default_get(self, fields_list):
        """Override para evitar errores al abrir desde Kanban."""
        res = super().default_get(fields_list)
        return res

