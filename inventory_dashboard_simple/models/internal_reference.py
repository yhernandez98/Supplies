# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class InternalReference(models.Model):
    """Modelo para almacenar referencias internas reutilizables."""
    
    _name = 'internal.reference'
    _description = 'Referencia Interna'
    _order = 'name'

    name = fields.Char(
        string='Referencia Interna',
        required=True,
        help='Referencia interna que se puede reutilizar'
    )
    
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        required=True,
        help='Producto al que pertenece esta referencia interna',
        ondelete='cascade'
    )
    
    asset_category_id = fields.Many2one(
        'product.asset.category',
        string='Categoría de Activo',
        related='product_id.asset_category_id',
        readonly=True,
        store=True
    )
    
    asset_class_id = fields.Many2one(
        'product.asset.class',
        string='Clase de Activo',
        related='product_id.asset_class_id',
        readonly=True,
        store=True
    )

    name_product_unique = models.Constraint(
        'UNIQUE(name, product_id)',
        'La referencia interna debe ser única por producto.',
    )
    
    @api.model
    def default_get(self, fields_list):
        """Pre-llenar producto desde el contexto."""
        res = super(InternalReference, self).default_get(fields_list)
        
        # Si product_id está en el contexto pero no en res, agregarlo
        if 'product_id' in fields_list:
            product_id = (
                self.env.context.get('default_product_id') or
                self.env.context.get('product_id')
            )
            if product_id and not res.get('product_id'):
                res['product_id'] = product_id
                _logger.info("Producto pre-llenado desde contexto en default_get: %s", product_id)
        
        return res
    
    @api.model_create_multi
    def create(self, vals_list):
        """Asignar producto desde el contexto si no está en los valores."""
        for vals in vals_list:
            # Si no hay product_id en los valores, intentar obtenerlo del contexto
            if 'product_id' not in vals or not vals.get('product_id'):
                product_id = None
                
                # Prioridad 1: default_product_id del contexto
                product_id = self.env.context.get('default_product_id')
                if product_id:
                    _logger.info("Producto obtenido desde default_product_id: %s", product_id)
                
                # Prioridad 2: product_id directo del contexto
                if not product_id:
                    product_id = self.env.context.get('product_id')
                    if product_id:
                        _logger.info("Producto obtenido desde product_id: %s", product_id)
                
                # Prioridad 3: active_id si active_model es product.product
                if not product_id:
                    active_model = self.env.context.get('active_model')
                    active_id = self.env.context.get('active_id')
                    if active_model == 'product.product' and active_id:
                        product_id = active_id
                        _logger.info("Producto obtenido desde active_id: %s", product_id)
                
                # Prioridad 4: Intentar obtenerlo del registro padre (si se crea desde un Many2one)
                if not product_id:
                    parent_id = self.env.context.get('parent_id')
                    parent_model = self.env.context.get('parent_model')
                    if parent_id and parent_model:
                        try:
                            parent = self.env[parent_model].browse(parent_id)
                            if hasattr(parent, 'product_id') and parent.product_id:
                                product_id = parent.product_id.id
                                _logger.info("Producto obtenido desde registro padre (%s): %s", parent_model, product_id)
                        except Exception as e:
                            _logger.warning("No se pudo obtener product_id del registro padre: %s", str(e))
                
                # Prioridad 5: Intentar obtenerlo desde el active_id si es un wizard o lote
                if not product_id:
                    active_model = self.env.context.get('active_model')
                    active_id = self.env.context.get('active_id')
                    if active_id:
                        try:
                            if active_model == 'quant.editor.wizard':
                                wizard = self.env['quant.editor.wizard'].browse(active_id)
                                if wizard.exists() and wizard.product_id:
                                    product_id = wizard.product_id.id
                                    _logger.info("Producto obtenido desde wizard: %s", product_id)
                            elif active_model == 'stock.lot':
                                lot = self.env['stock.lot'].browse(active_id)
                                if lot.exists() and lot.product_id:
                                    product_id = lot.product_id.id
                                    _logger.info("Producto obtenido desde lote: %s", product_id)
                        except Exception as e:
                            _logger.warning("Error al obtener product_id desde active_id: %s", str(e))
                
                if product_id:
                    vals['product_id'] = product_id
                    _logger.info("✓ Producto asignado al crear referencia interna: %s", product_id)
                else:
                    _logger.warning("⚠ No se pudo obtener product_id del contexto al crear referencia interna")
        
        # Validar que todas las referencias tengan product_id antes de crear
        for vals in vals_list:
            if 'product_id' not in vals or not vals.get('product_id'):
                raise UserError(_('El producto es obligatorio para crear una referencia interna. Por favor, seleccione un producto primero en el formulario.'))
        
        return super(InternalReference, self).create(vals_list)
    
    def action_clean_orphaned_references(self):
        """Eliminar referencias internas huérfanas (sin producto o con producto inválido).
        Puede ser llamado desde un botón en la vista."""
        # Usar el modelo completo, no solo self
        return self.env['internal.reference'].clean_all_orphaned_references()
    
    @api.model
    def clean_all_orphaned_references(self):
        """Método para limpiar todas las referencias huérfanas (llamado desde acción de servidor)."""
        # Buscar referencias sin producto o con producto que no existe
        all_refs = self.search([])
        to_delete = self.env['internal.reference']
        sin_producto = 0
        producto_invalido = 0
        
        for ref in all_refs:
            if not ref.product_id:
                to_delete |= ref
                sin_producto += 1
            elif not ref.product_id.exists():
                to_delete |= ref
                producto_invalido += 1
        
        count = len(to_delete)
        if count > 0:
            # Guardar nombres de las referencias que se van a eliminar para el log
            ref_names = to_delete.mapped('name')
            to_delete.unlink()
            _logger.info("Se eliminaron %d referencias internas huérfanas (%d sin producto, %d con producto inválido)", 
                        count, sin_producto, producto_invalido)
            _logger.info("Referencias eliminadas: %s", ', '.join(ref_names[:10]) + ('...' if len(ref_names) > 10 else ''))
            
            message = _('Se eliminaron %d referencias internas huérfanas:\n- %d sin producto\n- %d con producto inválido') % (
                count, sin_producto, producto_invalido
            )
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Limpieza completada'),
                    'message': message,
                    'type': 'success',
                    'sticky': True,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin referencias huérfanas'),
                    'message': _('No se encontraron referencias internas huérfanas para eliminar. Todas las referencias tienen un producto válido asociado.'),
                    'type': 'info',
                    'sticky': False,
                }
            }

