# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


class CleanupRoutesWizard(models.TransientModel):
    """
    Wizard para limpiar rutas, reglas y tipos de operación no utilizados
    """
    _name = 'cleanup.routes.wizard'
    _description = 'Limpieza de Rutas y Reglas No Utilizadas'

    # Filtros
    route_name_pattern = fields.Char(
        string='Patrón de Nombre de Ruta',
        default='SUPP_ALISTAMIENTO_SALIDA_TRANSPORTE_%',
        help='Patrón SQL para filtrar rutas (ej: SUPP_ALISTAMIENTO_SALIDA_TRANSPORTE_%)'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company,
        required=True
    )
    
    # Opciones de limpieza
    only_inactive = fields.Boolean(
        string='Solo Inactivos',
        default=True,
        help='Solo mostrar/eliminar rutas y reglas inactivas'
    )
    
    check_product_usage = fields.Boolean(
        string='Verificar Uso en Productos',
        default=True,
        help='Verificar si las rutas están asignadas a productos'
    )
    
    check_sale_usage = fields.Boolean(
        string='Verificar Uso en Ventas',
        default=True,
        help='Verificar si las rutas están en órdenes de venta'
    )
    
    check_warehouse_usage = fields.Boolean(
        string='Verificar Uso en Almacenes',
        default=True,
        help='Verificar si las rutas están asociadas a almacenes'
    )
    
    # Resultados
    route_ids = fields.Many2many(
        'stock.route',
        string='Rutas a Eliminar',
        readonly=True
    )
    
    rule_ids = fields.Many2many(
        'stock.rule',
        string='Reglas a Eliminar',
        readonly=True
    )
    
    picking_type_ids = fields.Many2many(
        'stock.picking.type',
        string='Tipos de Operación a Eliminar',
        readonly=True
    )
    
    # Estadísticas
    route_count = fields.Integer(
        string='Rutas Encontradas',
        compute='_compute_counts',
        readonly=True
    )
    
    rule_count = fields.Integer(
        string='Reglas Encontradas',
        compute='_compute_counts',
        readonly=True
    )
    
    picking_type_count = fields.Integer(
        string='Tipos de Operación Encontrados',
        compute='_compute_counts',
        readonly=True
    )
    
    # Modo de acción
    action_mode = fields.Selection([
        ('analyze', 'Solo Analizar'),
        ('deactivate', 'Desactivar (Marcar como Inactivo)'),
        ('delete', 'Eliminar Definitivamente'),
    ], string='Modo de Acción', default='analyze', required=True)
    
    @api.depends('route_ids', 'rule_ids', 'picking_type_ids')
    def _compute_counts(self):
        for wizard in self:
            wizard.route_count = len(wizard.route_ids)
            wizard.rule_count = len(wizard.rule_ids)
            wizard.picking_type_count = len(wizard.picking_type_ids)
    
    def action_analyze(self):
        """Analiza y encuentra rutas, reglas y tipos de operación no utilizados"""
        self.ensure_one()
        
        _logger.info("=" * 80)
        _logger.info("INICIO: Análisis de rutas y reglas no utilizadas")
        _logger.info(f"Patrón: {self.route_name_pattern}")
        _logger.info(f"Compañía: {self.company_id.name}")
        _logger.info("=" * 80)
        
        # Buscar rutas que coincidan con el patrón
        # El operador 'like' en Odoo usa '%' como comodín
        pattern = self.route_name_pattern or ''
        domain = [
            ('name', 'like', pattern),
            ('company_id', '=', self.company_id.id)
        ]
        
        if self.only_inactive:
            domain.append(('active', '=', False))
        
        routes = self.env['stock.route'].search(domain)
        _logger.info(f"Rutas encontradas: {len(routes)}")
        
        # Filtrar rutas no utilizadas
        unused_routes = self.env['stock.route']
        used_routes = self.env['stock.route']
        
        for route in routes:
            is_used = False
            
            # Verificar uso en productos
            if self.check_product_usage:
                products = self.env['product.template'].search([
                    ('route_ids', 'in', [route.id])
                ], limit=1)
                if products:
                    is_used = True
                    _logger.info(f"Ruta {route.name} está en uso: asignada a productos")
            
            # Verificar uso en órdenes de venta
            if not is_used and self.check_sale_usage:
                sales = self.env['sale.order'].search([
                    ('route_id', '=', route.id)
                ], limit=1)
                if sales:
                    is_used = True
                    _logger.info(f"Ruta {route.name} está en uso: en órdenes de venta")
            
            # Verificar uso en almacenes
            if not is_used and self.check_warehouse_usage:
                warehouses = self.env['stock.warehouse'].search([
                    ('route_ids', 'in', [route.id])
                ], limit=1)
                if warehouses:
                    is_used = True
                    _logger.info(f"Ruta {route.name} está en uso: asociada a almacenes")
            
            if is_used:
                used_routes |= route
            else:
                unused_routes |= route
        
        _logger.info(f"Rutas no utilizadas: {len(unused_routes)}")
        _logger.info(f"Rutas en uso: {len(used_routes)}")
        
        # Buscar reglas de las rutas no utilizadas
        rules = self.env['stock.rule'].search([
            ('route_id', 'in', unused_routes.ids)
        ])
        _logger.info(f"Reglas encontradas: {len(rules)}")
        
        # Buscar tipos de operación no utilizados
        # Solo tipos que no estén asociados a almacenes
        picking_types = self.env['stock.picking.type'].search([
            ('company_id', '=', self.company_id.id)
        ])
        
        unused_picking_types = self.env['stock.picking.type']
        for pt in picking_types:
            # Verificar si está asociado a algún almacén
            warehouses = self.env['stock.warehouse'].search([
                '|', '|', '|',
                ('in_type_id', '=', pt.id),
                ('out_type_id', '=', pt.id),
                ('pick_type_id', '=', pt.id),
                ('pack_type_id', '=', pt.id)
            ], limit=1)
            
            if not warehouses:
                # Verificar si tiene pickings activos
                pickings = self.env['stock.picking'].search([
                    ('picking_type_id', '=', pt.id),
                    ('state', 'not in', ['done', 'cancel'])
                ], limit=1)
                
                if not pickings:
                    unused_picking_types |= pt
        
        _logger.info(f"Tipos de operación no utilizados: {len(unused_picking_types)}")
        
        # Actualizar wizard
        self.write({
            'route_ids': [(6, 0, unused_routes.ids)],
            'rule_ids': [(6, 0, rules.ids)],
            'picking_type_ids': [(6, 0, unused_picking_types.ids)]
        })
        
        _logger.info("=" * 80)
        _logger.info("FIN: Análisis completado")
        _logger.info("=" * 80)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Análisis Completado'),
                'message': _(
                    'Análisis completado:\n'
                    '✅ Rutas no utilizadas: %s\n'
                    '✅ Reglas a eliminar: %s\n'
                    '✅ Tipos de operación no utilizados: %s\n\n'
                    'Revisa los resultados antes de proceder con la eliminación.'
                ) % (len(unused_routes), len(rules), len(unused_picking_types)),
                'type': 'success',
                'sticky': True,
            }
        }
    
    def action_execute_cleanup(self):
        """Ejecuta la limpieza según el modo seleccionado"""
        self.ensure_one()
        
        if not self.route_ids and not self.rule_ids and not self.picking_type_ids:
            raise UserError(_('No hay elementos para procesar. Ejecuta primero el análisis.'))
        
        _logger.info("=" * 80)
        _logger.info(f"INICIO: Ejecución de limpieza - Modo: {self.action_mode}")
        _logger.info("=" * 80)
        
        deleted_routes = 0
        deleted_rules = 0
        deactivated_routes = 0
        deactivated_rules = 0
        errors = []
        
        try:
            # Procesar reglas primero
            if self.rule_ids:
                if self.action_mode == 'delete':
                    try:
                        self.rule_ids.unlink()
                        deleted_rules = len(self.rule_ids)
                        _logger.info(f"Reglas eliminadas: {deleted_rules}")
                    except Exception as e:
                        error_msg = f"Error al eliminar reglas: {str(e)}"
                        _logger.error(error_msg, exc_info=True)
                        errors.append(error_msg)
                elif self.action_mode == 'deactivate':
                    self.rule_ids.write({'active': False})
                    deactivated_rules = len(self.rule_ids)
                    _logger.info(f"Reglas desactivadas: {deactivated_rules}")
            
            # Procesar rutas
            if self.route_ids:
                if self.action_mode == 'delete':
                    try:
                        self.route_ids.unlink()
                        deleted_routes = len(self.route_ids)
                        _logger.info(f"Rutas eliminadas: {deleted_routes}")
                    except Exception as e:
                        error_msg = f"Error al eliminar rutas: {str(e)}"
                        _logger.error(error_msg, exc_info=True)
                        errors.append(error_msg)
                elif self.action_mode == 'deactivate':
                    self.route_ids.write({'active': False})
                    deactivated_routes = len(self.route_ids)
                    _logger.info(f"Rutas desactivadas: {deactivated_routes}")
            
            # Procesar tipos de operación (solo desactivar, nunca eliminar directamente)
            if self.picking_type_ids:
                if self.action_mode == 'delete':
                    # Para tipos de operación, solo desactivar por seguridad
                    self.picking_type_ids.write({'active': False})
                    _logger.warning("Tipos de operación desactivados (no eliminados por seguridad)")
                elif self.action_mode == 'deactivate':
                    self.picking_type_ids.write({'active': False})
                    _logger.info(f"Tipos de operación desactivados: {len(self.picking_type_ids)}")
            
            _logger.info("=" * 80)
            _logger.info("FIN: Limpieza completada")
            _logger.info("=" * 80)
            
            # Mensaje de resultado
            message_parts = []
            if self.action_mode == 'delete':
                message_parts.append(_('Limpieza completada:\n'))
                if deleted_routes > 0:
                    message_parts.append(_('✅ Rutas eliminadas: %s') % deleted_routes)
                if deleted_rules > 0:
                    message_parts.append(_('✅ Reglas eliminadas: %s') % deleted_rules)
            elif self.action_mode == 'deactivate':
                message_parts.append(_('Desactivación completada:\n'))
                if deactivated_routes > 0:
                    message_parts.append(_('✅ Rutas desactivadas: %s') % deactivated_routes)
                if deactivated_rules > 0:
                    message_parts.append(_('✅ Reglas desactivadas: %s') % deactivated_rules)
                if self.picking_type_ids:
                    message_parts.append(_('✅ Tipos de operación desactivados: %s') % len(self.picking_type_ids))
            
            if errors:
                message_parts.append(_('\n❌ Errores: %s') % len(errors))
                for error in errors[:5]:
                    message_parts.append(f'\n- {error}')
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Limpieza Completada'),
                    'message': '\n'.join(message_parts),
                    'type': 'success' if not errors else 'warning',
                    'sticky': True,
                }
            }
            
        except Exception as e:
            _logger.error(f"Error crítico en limpieza: {str(e)}", exc_info=True)
            raise UserError(_('Error al ejecutar la limpieza: %s') % str(e))

