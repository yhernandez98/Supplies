# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class LicenseTemplate(models.Model):
    _name = 'license.template'
    _description = 'Plantilla de Licencia'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    code = fields.Char(string='Código', required=True, tracking=True, help='Código único de la licencia (ej: LIANT, LIMIC-RDP)')
    name = fields.Many2one(
        'license.category',
        string='Categorías',
        required=True,
        tracking=True,
        help='Categoría de licencia para agrupar en suscripciones (ej: Office 365, Google Workspace). Todas las licencias con la misma categoría se agruparán juntas en la pestaña Facturable.',
        ondelete='restrict'
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto/Servicio',
        required=True,
        domain=[('type', '=', 'service')],
        tracking=True,
        help='Producto de tipo servicio asociado a esta licencia. Este producto debe tener su precio en USD configurado en la lista de precios del cliente.'
    )
    product_tmpl_id = fields.Many2one(
        'product.template',
        related='product_id.product_tmpl_id',
        string='Plantilla de Producto',
        store=True,
        readonly=True
    )
    active = fields.Boolean(string='Activo', default=True, tracking=True)
    applies_to_equipment = fields.Boolean(
        string='Aplica para Equipo',
        default=False,
        tracking=True,
        help='Indica si esta licencia puede ser asignada a equipos (hardware/dispositivos)'
    )
    applies_to_user = fields.Boolean(
        string='Aplica para Usuario',
        default=False,
        tracking=True,
        help='Indica si esta licencia puede ser asignada a usuarios'
    )
    description = fields.Text(string='Descripción')
    
    # Campos relacionados con asignaciones
    assignment_ids = fields.One2many('license.assignment', 'license_id', string='Asignaciones')
    assignment_count = fields.Integer(string='Total Asignaciones', compute='_compute_assignment_count')
    total_quantity = fields.Integer(string='Cantidad Total Asignada', compute='_compute_total_quantity')

    # Pestaña "Cantidad por proveedor": líneas por product_id (computed para no depender de license_template_id)
    provider_stock_ids = fields.One2many(
        'license.provider.stock',
        'license_template_id',
        string='Cantidad por proveedor',
        compute='_compute_provider_stock_ids',
        inverse='_inverse_provider_stock_ids',
        search='_search_provider_stock_ids',
        help='Proveedores y cantidades (o Ilimitado) para esta licencia.',
    )
    provider_stock_count = fields.Integer(
        string='Proveedores',
        compute='_compute_provider_stock_info',
        help='Número de proveedores que ofrecen este producto/servicio.',
    )
    provider_stock_total = fields.Integer(
        string='Total de proveedores (cantidad)',
        compute='_compute_provider_stock_info',
        help='Suma de cantidades de proveedores con cantidad fija. Si algún proveedor es Ilimitado, no se usa.',
    )
    provider_has_unlimited = fields.Boolean(
        string='Algún proveedor ilimitado',
        compute='_compute_provider_stock_info',
        help='True si al menos un proveedor marca Ilimitado para esta licencia.',
    )
    stock_display = fields.Char(
        string='Licencias disponibles (resumen)',
        compute='_compute_stock_display',
        help='Texto para mostrar en formulario: total desde proveedores o manual.',
    )

    # Campos de stock y control de licencias
    stock = fields.Integer(
        string='Licencias Disponibles',
        default=0,
        tracking=True,
        help='Cantidad total de licencias disponibles para asignar. Si está en 0, no se controla el stock.'
    )
    used_licenses = fields.Integer(
        string='Cantidad en Uso',
        compute='_compute_used_licenses',
        store=True,
        help='Cantidad total de licencias actualmente asignadas y activas'
    )
    available_licenses = fields.Char(
        string='Licencias Disponibles Restantes',
        compute='_compute_available_licenses',
        store=False,
        help='Restantes: desde proveedores (suma o Ilimitado) o desde stock manual; menos cantidad en uso.'
    )
    
    # Campo computed para mostrar información completa en la vista
    display_name_full = fields.Char(
        string='Nombre Completo',
        compute='_compute_display_name_full',
        store=False
    )
    
    def _compute_display_name_full(self):
        """Calcula el nombre completo para mostrar en la vista"""
        for rec in self:
            category_name = rec.name.name if rec.name else 'Sin Categoría'
            product_name = rec.product_id.name if rec.product_id else ''
            if product_name:
                rec.display_name_full = f"{category_name} - {product_name}"
            else:
                rec.display_name_full = category_name
    
    _sql_constraints = [
        ('unique_code', 'unique(code)', 'El código de la licencia debe ser único.')
    ]

    def _auto_init(self):
        """Limpiar datos ANTES de que Odoo intente convertir el campo."""
        import logging
        _logger = logging.getLogger(__name__)
        
        if self._auto:
            cr = self.env.cr
            
            try:
                # Verificar si el campo name existe y es de tipo char
                cr.execute("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public'
                    AND table_name = 'license_template' 
                    AND column_name = 'name'
                """)
                column_info = cr.fetchone()
                
                if column_info:
                    column_type = column_info[1]
                    
                    # Si es texto, limpiar ANTES de que Odoo intente convertir
                    if column_type in ('character varying', 'text', 'varchar'):
                        _logger.info("=== Limpiando campo name antes de conversión ===")
                        
                        # Opción 1: Eliminar la columna completamente
                        try:
                            cr.execute("""
                                ALTER TABLE license_template 
                                DROP COLUMN name
                            """)
                            _logger.info("✓ Columna name eliminada, Odoo la creará como Many2one")
                            cr.commit()
                        except Exception as drop_error:
                            _logger.warning("No se pudo eliminar la columna: %s", str(drop_error))
                            # Opción 2: Si no se puede eliminar, poner NULL
                            try:
                                cr.execute("""
                                    UPDATE license_template 
                                    SET name = NULL 
                                    WHERE name IS NOT NULL
                                """)
                                _logger.info("✓ Datos limpiados (puestos en NULL)")
                                cr.commit()
                            except Exception as update_error:
                                _logger.error("No se pudo limpiar los datos: %s", str(update_error))
                                cr.rollback()
                    elif column_type == 'integer':
                        _logger.info("El campo name ya es Many2one (integer), no se requiere limpieza")
                
            except Exception as e:
                _logger.error('Error en _auto_init limpiando campo name: %s', str(e), exc_info=True)
                try:
                    cr.rollback()
                except:
                    pass
        
        # AHORA llamar a super() para que Odoo haga la conversión
        res = super()._auto_init()
        
        return res

    @api.depends('assignment_ids')
    def _compute_assignment_count(self):
        for rec in self:
            rec.assignment_count = len(rec.assignment_ids)

    def _search_provider_stock_ids(self, operator, value):
        """Permite que Odoo determine qué plantillas recomputar cuando se modifica license.provider.stock (Odoo 19)."""
        if operator in ('in', '='):
            ids = value if isinstance(value, (list, tuple)) else ([value] if value else [])
            if not ids:
                return [('id', 'in', [])]
            stocks = self.env['license.provider.stock'].browse(ids)
            template_ids = stocks.mapped('license_template_id').ids
            return [('id', 'in', template_ids)]
        if operator in ('not in', '!='):
            ids = value if isinstance(value, (list, tuple)) else ([value] if value else [])
            if not ids:
                return []
            stocks = self.env['license.provider.stock'].browse(ids)
            template_ids = stocks.mapped('license_template_id').ids
            return [('id', 'not in', template_ids)]
        return []

    @api.depends('product_id')
    def _compute_provider_stock_ids(self):
        Stock = self.env['license.provider.stock']
        for rec in self:
            if rec.product_id:
                rec.provider_stock_ids = Stock.search([('license_product_id', '=', rec.product_id.id)])
            else:
                rec.provider_stock_ids = Stock.browse([])

    def _inverse_provider_stock_ids(self):
        """Al añadir/editar líneas desde la pestaña: asegurar license_template_id y license_product_id."""
        for rec in self:
            for line in rec.provider_stock_ids:
                if line.license_template_id != rec or line.license_product_id != rec.product_id:
                    line.write({
                        'license_template_id': rec.id,
                        'license_product_id': rec.product_id.id,
                    })

    @api.depends('product_id')
    def _compute_provider_stock_info(self):
        for rec in self:
            lines = rec.provider_stock_ids
            rec.provider_stock_count = len(lines)
            rec.provider_has_unlimited = any(line.is_unlimited for line in lines)
            rec.provider_stock_total = sum(line.quantity for line in lines if not line.is_unlimited)

    @api.depends('provider_stock_count', 'provider_stock_total', 'provider_has_unlimited', 'stock')
    def _compute_stock_display(self):
        for rec in self:
            if rec.provider_stock_count and rec.provider_stock_count > 0:
                rec.stock_display = _('Ilimitado') if rec.provider_has_unlimited else str(rec.provider_stock_total)
            else:
                rec.stock_display = str(rec.stock) if rec.stock else _('Ilimitado')

    def action_view_provider_stock(self):
        """Abre el stock por proveedor para este producto/licencia (uno o más proveedores)."""
        self.ensure_one()
        if not self.product_id:
            return {}
        return {
            'name': _('Proveedores de "%s"') % (self.product_id.name or self.code),
            'type': 'ir.actions.act_window',
            'res_model': 'license.provider.stock',
            'view_mode': 'list,form',
            'domain': [('license_product_id', '=', self.product_id.id)],
            'context': {'default_license_product_id': self.product_id.id, 'default_provider_id': False},
        }

    @api.depends('assignment_ids.quantity')
    def _compute_total_quantity(self):
        for rec in self:
            rec.total_quantity = sum(rec.assignment_ids.mapped('quantity'))
    
    @api.depends('assignment_ids.quantity', 'assignment_ids.state')
    def _compute_used_licenses(self):
        """Calcula la cantidad de licencias en uso (solo asignaciones activas)"""
        for rec in self:
            # Sumar solo las cantidades de asignaciones activas
            active_assignments = rec.assignment_ids.filtered(lambda a: a.state == 'active')
            rec.used_licenses = sum(active_assignments.mapped('quantity'))
    
    @api.depends('stock', 'used_licenses', 'provider_stock_count', 'provider_stock_total', 'provider_has_unlimited')
    def _compute_available_licenses(self):
        """Calcula las licencias disponibles restantes: desde proveedores (varios, con opción ilimitado) o desde stock manual."""
        for rec in self:
            # Si hay proveedores definidos para este producto, usar su suma (o Ilimitado)
            if rec.provider_stock_count and rec.provider_stock_count > 0:
                if rec.provider_has_unlimited:
                    rec.available_licenses = _('Ilimitado')
                else:
                    total = rec.provider_stock_total or 0
                    available = max(0, total - rec.used_licenses)
                    rec.available_licenses = str(available)
            else:
                # Sin proveedores: usar el stock manual de la licencia
                if rec.stock > 0:
                    available = max(0, rec.stock - rec.used_licenses)
                    rec.available_licenses = str(available)
                else:
                    rec.available_licenses = _('Ilimitado')

    def name_get(self):
        result = []
        for rec in self:
            category_name = rec.name.name if rec.name else 'Sin Categoría'
            product_name = rec.product_id.name if rec.product_id else ''
            
            # Si hay producto, mostrar: [Código] Categoría - Producto/Servicio
            # Si no hay producto, mostrar: [Código] Categoría
            if product_name:
                name = f"[{rec.code}] {category_name} - {product_name}"
            else:
                name = f"[{rec.code}] {category_name}"
            result.append((rec.id, name))
        return result

    def action_activate(self):
        """Activa la licencia"""
        for rec in self:
            rec.active = True

    def action_deactivate(self):
        """Desactiva la licencia"""
        for rec in self:
            rec.active = False

