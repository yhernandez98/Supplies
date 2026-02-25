# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class LotSupplyEditorWizard(models.TransientModel):
    """Wizard para editar elementos asociados de un lote (componentes, periféricos, complementos)."""
    
    _name = 'lot.supply.editor.wizard'
    _description = 'Editor de Elementos Asociados del Lote'

    lot_id = fields.Many2one(
        'stock.lot',
        string='Lote/Serie',
        required=True,
        readonly=True,
        help='Lote principal cuyos elementos asociados se van a editar'
    )
    
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        related='lot_id.product_id',
        readonly=True,
        help='Producto del lote principal'
    )
    
    lot_supply_line_ids = fields.One2many(
        'lot.supply.editor.wizard.line',
        'wizard_id',
        string='Elementos Asociados',
        help='Componentes, periféricos y complementos asociados al lote'
    )
    
    component_lines = fields.One2many(
        'lot.supply.editor.wizard.line',
        'wizard_id',
        string='Componentes',
        domain=[('item_type', '=', 'component')],
        help='Componentes asociados al lote'
    )
    
    peripheral_lines = fields.One2many(
        'lot.supply.editor.wizard.line',
        'wizard_id',
        string='Periféricos',
        domain=[('item_type', '=', 'peripheral')],
        help='Periféricos asociados al lote'
    )
    
    complement_lines = fields.One2many(
        'lot.supply.editor.wizard.line',
        'wizard_id',
        string='Complementos',
        domain=[('item_type', '=', 'complement')],
        help='Complementos asociados al lote'
    )
    
    @api.model
    def default_get(self, fields_list):
        """Cargar las líneas de suministro existentes del lote."""
        res = super().default_get(fields_list)
        
        # Solo procesar si tenemos lot_id en el contexto
        lot_id = self.env.context.get('default_lot_id') or self.env.context.get('active_id')
        if not lot_id or 'lot_id' not in fields_list:
            return res
        
        lot = self.env['stock.lot'].browse(lot_id)
        
        if not lot.exists():
            return res
        
        res['lot_id'] = lot.id
        
        # Cargar las líneas existentes según su tipo
        # Usar un set para evitar duplicados por ID de supply_line
        processed_supply_line_ids = set()
        component_vals = []
        peripheral_vals = []
        complement_vals = []
        
        # Obtener todas las líneas existentes del lote
        for supply_line in lot.lot_supply_line_ids:
            # Evitar cargar la misma línea dos veces
            if supply_line.id in processed_supply_line_ids:
                _logger.warning('Línea duplicada detectada en default_get: supply_line_id=%s', supply_line.id)
                continue
            
            processed_supply_line_ids.add(supply_line.id)
            
            line_data = {
                'supply_line_id': supply_line.id,
                'item_type': supply_line.item_type,
                'product_id': supply_line.product_id.id if supply_line.product_id else False,
                'quantity': supply_line.quantity,
                'uom_id': supply_line.uom_id.id if supply_line.uom_id else False,
                'related_lot_id': supply_line.related_lot_id.id if supply_line.related_lot_id else False,
            }
            
            if supply_line.item_type == 'component':
                component_vals.append((0, 0, line_data))
            elif supply_line.item_type == 'peripheral':
                peripheral_vals.append((0, 0, line_data))
            elif supply_line.item_type == 'complement':
                complement_vals.append((0, 0, line_data))
            elif supply_line.item_type in ('monitor', 'ups'):
                # Monitores y UPS se tratan como periféricos en el wizard
                peripheral_vals.append((0, 0, line_data))
        
        # Cargar en los campos correspondientes solo si están en fields_list
        if 'component_lines' in fields_list:
            res['component_lines'] = component_vals
        if 'peripheral_lines' in fields_list:
            res['peripheral_lines'] = peripheral_vals
        if 'complement_lines' in fields_list:
            res['complement_lines'] = complement_vals
        
        # También mantener lot_supply_line_ids para compatibilidad
        if 'lot_supply_line_ids' in fields_list:
            all_vals = component_vals + peripheral_vals + complement_vals
            res['lot_supply_line_ids'] = all_vals
        
        _logger.debug('default_get cargó %d componentes, %d periféricos, %d complementos', 
                     len(component_vals), len(peripheral_vals), len(complement_vals))
        
        return res
    
    def action_save(self):
        """Guardar los cambios en las líneas de suministro usando la misma lógica que Odoo."""
        self.ensure_one()
        
        if not self.lot_id:
            raise UserError(_('No se ha especificado un lote.'))
        
        # Obtener todas las líneas de todas las pestañas
        all_lines = self.component_lines + self.peripheral_lines + self.complement_lines
        
        # PRIMERO: Eliminar duplicados en el wizard antes de procesar
        # Crear un diccionario para detectar duplicados por (supply_line_id, product_id, related_lot_id, item_type)
        seen_lines = {}
        unique_lines = []
        
        for wizard_line in all_lines:
            if not wizard_line.product_id:
                continue
            
            # Crear una clave única para identificar duplicados
            key = (
                wizard_line.supply_line_id.id if wizard_line.supply_line_id else None,
                wizard_line.product_id.id,
                wizard_line.related_lot_id.id if wizard_line.related_lot_id else None,
                wizard_line.item_type
            )
            
            # Si ya vimos esta línea, mantener solo la primera (o la que tiene supply_line_id)
            if key in seen_lines:
                existing_line = seen_lines[key]
                # Si la nueva línea tiene supply_line_id y la existente no, reemplazar
                if wizard_line.supply_line_id and not existing_line.supply_line_id:
                    # Reemplazar en unique_lines
                    idx = unique_lines.index(existing_line)
                    unique_lines[idx] = wizard_line
                    seen_lines[key] = wizard_line
                # Si ambas tienen supply_line_id, mantener la primera
                # Si ninguna tiene, mantener la primera
                continue
            
            seen_lines[key] = wizard_line
            unique_lines.append(wizard_line)
        
        # Validar que no haya seriales duplicados en las líneas únicas
        used_related_lot_ids = {}
        for wizard_line in unique_lines:
            if not wizard_line.product_id or not wizard_line.related_lot_id:
                continue
            
            related_lot_id = wizard_line.related_lot_id.id
            if related_lot_id in used_related_lot_ids:
                raise UserError(_(
                    'El número de serie "%s" está duplicado en las líneas del wizard. '
                    'Cada serial solo puede aparecer una vez.'
                ) % wizard_line.related_lot_id.name)
            
            used_related_lot_ids[related_lot_id] = wizard_line
        
        # Construir comandos ORM estándar de Odoo para actualizar el campo One2many
        # Esto es la misma lógica que usa Odoo cuando editas directamente lot_supply_line_ids
        commands = []
        
        # Obtener todas las líneas existentes
        existing_lines = self.lot_id.lot_supply_line_ids
        
        # Crear un mapa de líneas existentes por su ID
        existing_lines_map = {line.id: line for line in existing_lines}
        
        # Procesar cada línea única del wizard
        processed_ids = set()
        
        for wizard_line in unique_lines:
            if not wizard_line.product_id:
                continue
            
            # Si tiene supply_line_id, es una línea existente que se está editando
            if wizard_line.supply_line_id and wizard_line.supply_line_id.id:
                existing_id = wizard_line.supply_line_id.id
                
                # Evitar procesar la misma línea dos veces
                if existing_id in processed_ids:
                    _logger.warning('Línea duplicada detectada y omitida: supply_line_id=%s', existing_id)
                    continue
                
                processed_ids.add(existing_id)
                
                # Verificar que la línea existe
                if existing_id not in existing_lines_map:
                    # La línea fue eliminada, crear nueva
                    commands.append((0, 0, {
                        'item_type': wizard_line.item_type,
                        'product_id': wizard_line.product_id.id,
                        'quantity': wizard_line.quantity,
                        'uom_id': wizard_line.uom_id.id if wizard_line.uom_id else False,
                        'related_lot_id': wizard_line.related_lot_id.id if wizard_line.related_lot_id else False,
                    }))
                else:
                    # Actualizar línea existente usando comando (1, id, vals)
                    commands.append((1, existing_id, {
                        'item_type': wizard_line.item_type,
                        'product_id': wizard_line.product_id.id,
                        'quantity': wizard_line.quantity,
                        'uom_id': wizard_line.uom_id.id if wizard_line.uom_id else False,
                        'related_lot_id': wizard_line.related_lot_id.id if wizard_line.related_lot_id else False,
                    }))
            else:
                # Es una nueva línea (sin supply_line_id)
                # Verificar que no exista ya una línea con estos valores
                if wizard_line.related_lot_id:
                    duplicate = existing_lines.filtered(
                        lambda l: l.product_id.id == wizard_line.product_id.id
                        and l.related_lot_id
                        and l.related_lot_id.id == wizard_line.related_lot_id.id
                        and l.item_type == wizard_line.item_type
                    )
                    if duplicate:
                        # Actualizar la existente en lugar de crear nueva
                        commands.append((1, duplicate[0].id, {
                            'item_type': wizard_line.item_type,
                            'product_id': wizard_line.product_id.id,
                            'quantity': wizard_line.quantity,
                            'uom_id': wizard_line.uom_id.id if wizard_line.uom_id else False,
                            'related_lot_id': wizard_line.related_lot_id.id if wizard_line.related_lot_id else False,
                        }))
                        continue
                
                commands.append((0, 0, {
                    'item_type': wizard_line.item_type,
                    'product_id': wizard_line.product_id.id,
                    'quantity': wizard_line.quantity,
                    'uom_id': wizard_line.uom_id.id if wizard_line.uom_id else False,
                    'related_lot_id': wizard_line.related_lot_id.id if wizard_line.related_lot_id else False,
                }))
        
        # Aplicar los cambios usando write con comandos ORM estándar
        # Esto es exactamente lo que hace Odoo cuando editas directamente el campo One2many
        self.lot_id.write({
            'lot_supply_line_ids': commands
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Guardado'),
                'message': _('Los elementos asociados se han actualizado correctamente.'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_debug_wizard(self):
        """Método de debug para ver qué está pasando en el wizard."""
        self.ensure_one()
        
        if not self.lot_id:
            raise UserError(_('No se ha especificado un lote.'))
        
        # Obtener todas las líneas de todas las pestañas
        all_lines = self.component_lines + self.peripheral_lines + self.complement_lines
        
        # Obtener todas las líneas existentes del lote
        all_existing_lines = self.lot_id.lot_supply_line_ids
        
        # Construir mensaje de debug
        debug_info = []
        debug_info.append("=== DEBUG WIZARD ===\n")
        debug_info.append(f"Lote Principal: {self.lot_id.name} (ID: {self.lot_id.id})\n")
        debug_info.append(f"Total líneas en wizard: {len(all_lines)}\n")
        debug_info.append(f"Total líneas existentes en BD: {len(all_existing_lines)}\n\n")
        
        debug_info.append("--- LÍNEAS EN EL WIZARD ---\n")
        for i, line in enumerate(all_lines, 1):
            debug_info.append(f"Línea {i}:")
            debug_info.append(f"  - ID wizard_line: {line.id}")
            debug_info.append(f"  - supply_line_id: {line.supply_line_id.id if line.supply_line_id else 'NINGUNO'}")
            debug_info.append(f"  - item_type: {line.item_type}")
            debug_info.append(f"  - product_id: {line.product_id.name if line.product_id else 'NINGUNO'} (ID: {line.product_id.id if line.product_id else 'N/A'})")
            debug_info.append(f"  - related_lot_id: {line.related_lot_id.name if line.related_lot_id else 'NINGUNO'} (ID: {line.related_lot_id.id if line.related_lot_id else 'N/A'})")
            debug_info.append(f"  - quantity: {line.quantity}\n")
        
        debug_info.append("\n--- LÍNEAS EXISTENTES EN BD ---\n")
        for i, line in enumerate(all_existing_lines, 1):
            debug_info.append(f"Línea {i}:")
            debug_info.append(f"  - ID: {line.id}")
            debug_info.append(f"  - item_type: {line.item_type}")
            debug_info.append(f"  - product_id: {line.product_id.name if line.product_id else 'NINGUNO'} (ID: {line.product_id.id if line.product_id else 'N/A'})")
            debug_info.append(f"  - related_lot_id: {line.related_lot_id.name if line.related_lot_id else 'NINGUNO'} (ID: {line.related_lot_id.id if line.related_lot_id else 'N/A'})")
            debug_info.append(f"  - quantity: {line.quantity}\n")
        
        # Detectar duplicados en el wizard
        debug_info.append("\n--- DETECCIÓN DE DUPLICADOS EN WIZARD ---\n")
        seen_keys = {}
        duplicates_found = False
        for i, line in enumerate(all_lines, 1):
            if not line.product_id or not line.related_lot_id:
                continue
            
            key = (line.product_id.id, line.related_lot_id.id, line.item_type)
            if key in seen_keys:
                duplicates_found = True
                debug_info.append(f"⚠️ DUPLICADO ENCONTRADO:")
                debug_info.append(f"  - Línea {i}: {line.product_id.name} - {line.related_lot_id.name} ({line.item_type})")
                debug_info.append(f"  - Línea {seen_keys[key]}: (ya vista anteriormente)\n")
            else:
                seen_keys[key] = i
        
        if not duplicates_found:
            debug_info.append("✓ No se encontraron duplicados en el wizard\n")
        
        # Detectar líneas sin supply_line_id que deberían tenerlo
        debug_info.append("\n--- LÍNEAS SIN supply_line_id (posibles duplicados) ---\n")
        lines_without_supply_id = []
        for line in all_lines:
            if line.product_id and line.related_lot_id and not line.supply_line_id:
                # Buscar si existe una línea en BD con estos valores
                existing = all_existing_lines.filtered(
                    lambda l: l.product_id.id == line.product_id.id 
                    and l.related_lot_id 
                    and l.related_lot_id.id == line.related_lot_id.id
                    and l.item_type == line.item_type
                )
                if existing:
                    lines_without_supply_id.append({
                        'wizard_line': line,
                        'existing_lines': existing
                    })
        
        if lines_without_supply_id:
            for item in lines_without_supply_id:
                debug_info.append(f"⚠️ Línea sin supply_line_id pero existe en BD:")
                debug_info.append(f"  - Producto: {item['wizard_line'].product_id.name}")
                debug_info.append(f"  - Serial: {item['wizard_line'].related_lot_id.name}")
                debug_info.append(f"  - Tipo: {item['wizard_line'].item_type}")
                debug_info.append(f"  - Líneas existentes en BD: {[l.id for l in item['existing_lines']]}\n")
        else:
            debug_info.append("✓ Todas las líneas tienen supply_line_id o son realmente nuevas\n")
        
        debug_message = "".join(debug_info)
        
        # Log también en el servidor
        _logger.info("=== DEBUG WIZARD ===\n%s", debug_message)
        
        # Mostrar en notificación (limitado a 500 caracteres)
        if len(debug_message) > 500:
            debug_message_short = debug_message[:500] + "\n... (ver logs del servidor para información completa)"
        else:
            debug_message_short = debug_message
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Debug Wizard'),
                'message': debug_message_short,
                'type': 'warning',
                'sticky': True,
            }
        }


class LotSupplyEditorWizardLine(models.TransientModel):
    """Líneas del wizard para editar elementos asociados."""
    
    _name = 'lot.supply.editor.wizard.line'
    _description = 'Línea del Editor de Elementos Asociados'

    wizard_id = fields.Many2one(
        'lot.supply.editor.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade'
    )
    
    supply_line_id = fields.Many2one(
        'stock.lot.supply.line',
        string='Línea Original',
        help='Línea de suministro original (si existe)'
    )
    
    item_type = fields.Selection(
        [
            ('component', 'Componente'),
            ('peripheral', 'Periférico'),
            ('complement', 'Complemento'),
            ('monitor', 'Monitores'),
            ('ups', 'UPS')
        ],
        string='Tipo',
        required=True,
        default='component'
    )
    
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        required=True,
        domain="[('type','in',('consu','product'))]",
        help='Producto del componente/periférico/complemento'
    )
    
    quantity = fields.Float(
        string='Cantidad',
        default=1.0,
        digits='Product Unit of Measure',
        required=True
    )
    
    uom_id = fields.Many2one(
        'uom.uom',
        string='UdM',
        domain=[],
        help='Unidad de medida'
    )
    
    related_lot_id = fields.Many2one(
        'stock.lot',
        string='Lote/Serie del Elemento',
        domain="[('id', 'in', available_related_lot_ids)]",
        help='Lote/Serie específico del componente/periférico/complemento'
    )
    
    available_related_lot_ids = fields.Many2many(
        'stock.lot',
        compute='_compute_available_related_lot_ids',
        string='Lotes disponibles',
        store=False,
        help='Lotes disponibles para relacionar'
    )
    
    @api.depends('product_id', 'wizard_id', 'wizard_id.lot_id', 'related_lot_id', 'supply_line_id')
    def _compute_available_related_lot_ids(self):
        """Calcular los lotes disponibles para relacionar, excluyendo los ya asignados."""
        for line in self:
            line.available_related_lot_ids = [(5, 0, 0)]
            
            if not line.product_id or not line.wizard_id or not line.wizard_id.lot_id:
                continue
            
            # Obtener la ubicación del lote principal
            principal_lot = line.wizard_id.lot_id
            try:
                if not principal_lot.location_id:
                    continue
            except Exception:
                continue
            
            # Buscar quants del producto en la misma ubicación
            try:
                Quant = self.env['stock.quant']
                quants = Quant.search([
                    ('product_id', '=', line.product_id.id),
                    ('location_id', '=', principal_lot.location_id.id),
                    ('lot_id', '!=', False),
                    ('quantity', '>', 0),
                ])
            except Exception:
                continue
            
            # Obtener lotes disponibles (excluyendo los ya usados en otras líneas)
            try:
                SupplyLine = self.env['stock.lot.supply.line']
                # Buscar todos los seriales que ya están asignados
                used_supply_lines = SupplyLine.search([
                    ('related_lot_id', '!=', False),
                ])
                
                # Obtener IDs de seriales ya asignados
                used_lot_ids = set(used_supply_lines.mapped('related_lot_id').ids)
                
                # IMPORTANTE: Si esta línea tiene un supply_line_id (es una línea existente),
                # excluir su propio serial de la lista de "usados" para permitir mantenerlo
                if line.supply_line_id and line.supply_line_id.related_lot_id:
                    used_lot_ids.discard(line.supply_line_id.related_lot_id.id)
                
                # También excluir el serial actual si ya está asignado a esta línea
                if line.related_lot_id:
                    used_lot_ids.discard(line.related_lot_id.id)
                    
            except Exception:
                used_lot_ids = set()
            
            # Filtrar lotes disponibles: solo los que tienen quants Y no están asignados
            available_lot_ids = [
                q.lot_id.id for q in quants 
                if q.lot_id and q.lot_id.id not in used_lot_ids
            ]
            
            if available_lot_ids:
                line.available_related_lot_ids = [(6, 0, available_lot_ids)]
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Establecer la unidad de medida por defecto cuando se selecciona un producto."""
        if self.product_id and not self.uom_id:
            self.uom_id = self.product_id.uom_id
