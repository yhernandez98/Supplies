# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta


class CustomerOwnInventory(models.Model):
    """Modelo para gestionar inventario propio de clientes.
    
    Este modelo representa productos que son propiedad del cliente,
    no de la empresa. Diferente del inventario de stock.lot que
    representa productos de la empresa que están en ubicación del cliente.
    """
    _name = 'customer.own.inventory'
    _description = 'Inventario Propio de Clientes'
    _order = 'partner_id, product_id, serial_number'
    _rec_name = 'display_name'
    
    # ========== Campos Principales ==========
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        required=True,
        index=True,
        domain=[('is_company', '=', True)],
        help='Cliente propietario del producto'
    )
    
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        required=True,
        index=True,
        domain=[('type', '=', 'product')],
        help='Mismo catálogo de productos de la empresa. Solo se registra aquí para identificación; NO modifica stock ni inventario.'
    )
    
    product_tmpl_id = fields.Many2one(
        'product.template',
        related='product_id.product_tmpl_id',
        string='Plantilla de Producto',
        store=True,
        readonly=True
    )
    
    product_categ_id = fields.Many2one(
        'product.category',
        related='product_id.categ_id',
        string='Categoría de producto',
        store=False,
        readonly=True,
        help='Categoría del producto (solo lectura, desde el catálogo)'
    )
    
    product_image = fields.Binary(
        related='product_id.image_1920',
        string='Imagen del producto',
        readonly=True
    )
    
    serial_number = fields.Char(
        string='Número de Serie',
        index=True,
        help='Número de serie único del producto'
    )
    
    display_name = fields.Char(
        string='Nombre',
        compute='_compute_display_name',
        store=True,
        index=True
    )
    
    # ========== Información del Producto ==========
    description = fields.Text(
        string='Descripción',
        help='Descripción detallada del producto'
    )
    
    model = fields.Char(
        string='Modelo',
        help='Modelo específico del producto'
    )
    
    brand = fields.Char(
        string='Marca',
        help='Marca del producto'
    )
    
    # ========== Fechas Importantes ==========
    purchase_date = fields.Date(
        string='Fecha de Compra',
        help='Fecha en que el cliente adquirió el producto'
    )
    
    warranty_end_date = fields.Date(
        string='Fin de Garantía',
        help='Fecha de finalización de la garantía'
    )
    
    warranty_status = fields.Selection(
        [
            ('active', 'En Garantía'),
            ('expired', 'Garantía Vencida'),
            ('no_warranty', 'Sin Garantía'),
        ],
        string='Estado de Garantía',
        compute='_compute_warranty_status',
        store=True,
        help='Estado actual de la garantía'
    )
    
    # ========== Estado y Ubicación ==========
    status = fields.Selection(
        [
            ('active', 'Activo'),
            ('inactive', 'Inactivo'),
            ('maintenance', 'En Mantenimiento'),
            ('repair', 'En Reparación'),
            ('disposed', 'Desechado'),
            ('sold', 'Vendido'),
        ],
        string='Estado',
        default='active',
        required=True,
        help='Estado actual del producto'
    )
    
    location = fields.Char(
        string='Ubicación Física',
        help='Ubicación física del producto en las instalaciones del cliente'
    )
    
    # ========== Información Adicional ==========
    notes = fields.Text(
        string='Notas',
        help='Notas adicionales sobre el producto'
    )
    
    purchase_price = fields.Monetary(
        string='Precio de Compra',
        currency_field='currency_id',
        help='Precio al que el cliente adquirió el producto'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        related='partner_id.currency_id',
        string='Moneda',
        readonly=True
    )
    
    # ========== Relaciones ==========
    maintenance_ids = fields.One2many(
        'stock.lot.maintenance',
        'own_inventory_id',
        string='Mantenimientos',
        help='Mantenimientos realizados a este producto'
    )
    
    maintenance_count = fields.Integer(
        string='Cantidad de Mantenimientos',
        compute='_compute_maintenance_count',
        store=False
    )
    
    own_inventory_line_ids = fields.One2many(
        'customer.own.inventory.line',
        'own_inventory_id',
        string='Productos asociados',
        help='Componentes, periféricos y complementos asociados a este equipo'
    )
    
    associated_count = fields.Integer(
        string='Cant. asociados',
        compute='_compute_associated_count',
        store=False
    )
    
    # ========== Campos Computados ==========
    @api.depends('partner_id', 'product_id', 'serial_number')
    def _compute_display_name(self):
        """Calcular el nombre de visualización."""
        for record in self:
            parts = []
            if record.partner_id:
                parts.append(record.partner_id.name)
            if record.product_id:
                parts.append(record.product_id.name)
            if record.serial_number:
                parts.append(f"[{record.serial_number}]")
            record.display_name = ' - '.join(parts) if parts else _('Nuevo')
    
    @api.depends('warranty_end_date', 'purchase_date')
    def _compute_warranty_status(self):
        """Calcular el estado de la garantía."""
        today = fields.Date.today()
        for record in self:
            if not record.warranty_end_date:
                if record.purchase_date:
                    # Si no hay fecha de fin de garantía pero hay fecha de compra,
                    # considerar sin garantía
                    record.warranty_status = 'no_warranty'
                else:
                    record.warranty_status = 'no_warranty'
            elif record.warranty_end_date >= today:
                record.warranty_status = 'active'
            else:
                record.warranty_status = 'expired'
    
    def _compute_maintenance_count(self):
        """Calcular cantidad de mantenimientos."""
        for record in self:
            record.maintenance_count = len(record.maintenance_ids)
    
    def _compute_associated_count(self):
        """Calcular cantidad de productos asociados."""
        for record in self:
            record.associated_count = len(record.own_inventory_line_ids)
    
    # ========== Constraints ==========
    _sql_constraints = [
        ('unique_serial_partner',
         'UNIQUE(serial_number, partner_id)',
         'El número de serie debe ser único por cliente.'),
    ]
    
    @api.constrains('warranty_end_date', 'purchase_date')
    def _check_dates(self):
        """Validar que las fechas sean lógicas."""
        for record in self:
            if record.warranty_end_date and record.purchase_date:
                if record.warranty_end_date < record.purchase_date:
                    raise ValidationError(_(
                        'La fecha de fin de garantía no puede ser anterior a la fecha de compra.'
                    ))
    
    # ========== Métodos de Acción ==========
    def action_view_maintenances(self):
        """Abrir vista de mantenimientos de este producto."""
        self.ensure_one()
        return {
            'name': _('Mantenimientos - %s') % self.display_name,
            'type': 'ir.actions.act_window',
            'res_model': 'stock.lot.maintenance',
            'view_mode': 'list,form',
            'domain': [('own_inventory_id', '=', self.id)],
            'context': {
                'default_own_inventory_id': self.id,
                'default_lot_id': False,
                'default_customer_id': self.partner_id.id,
            },
        }
    
    def action_report_life_sheet(self):
        """Abrir reporte PDF Hoja de vida del producto propio."""
        self.ensure_one()
        report = self.env.ref(
            'mesa_ayuda_inventario.action_report_customer_own_inventory_life_sheet',
            raise_if_not_found=False
        )
        if not report:
            raise UserError(_('El reporte Hoja de Vida no está disponible.'))
        return report.report_action(self)
    
    def name_get(self):
        """Personalizar nombre para mostrar."""
        result = []
        for record in self:
            name = record.display_name or _('Nuevo')
            result.append((record.id, name))
        return result

