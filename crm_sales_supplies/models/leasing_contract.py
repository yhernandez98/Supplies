# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class LeasingContract(models.Model):
    _name = 'leasing.contract'
    _description = 'Contrato de Leasing'
    _order = 'start_date desc, name desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Número de Contrato',
        required=True,
        copy=False,
        index=True,
        default=lambda self: _('Nuevo'),
        tracking=True
    )
    brand_id = fields.Many2one(
        'leasing.brand',
        string='Marca Principal',
        required=False,
        tracking=True,
        help='Marca principal del contrato (ej: HP, Dell, etc.). Deprecated: usar brand_ids.'
    )
    brand_ids = fields.Many2many(
        'leasing.brand',
        'leasing_contract_brand_rel',
        'contract_id',
        'brand_id',
        string='Marcas',
        required=True,
        tracking=True,
        help='Marcas incluidas en el contrato (ej: HP, Dell, etc.). Puede incluir múltiples marcas.'
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        required=True,
        tracking=True,
        help='Cliente que firma el contrato (la gran empresa)'
    )
    start_date = fields.Date(
        string='Fecha Inicio',
        required=True,
        tracking=True,
        default=fields.Date.today
    )
    end_date = fields.Date(
        string='Fecha Fin',
        tracking=True
    )
    state = fields.Selection(
        [
            ('draft', 'Borrador'),
            ('active', 'Activo'),
            ('expired', 'Vencido'),
            ('cancelled', 'Cancelado'),
        ],
        string='Estado',
        default='draft',
        tracking=True
    )
    active = fields.Boolean(
        string='Activo',
        default=True
    )
    
    # Proveedores asignados por la marca
    provider_ids = fields.Many2many(
        'res.partner',
        'leasing_contract_provider_rel',
        'contract_id',
        'provider_id',
        string='Proveedores Asignados',
        domain=[('supplier_rank', '>', 0)],
        help='Proveedores que la marca ha indicado que despacharán los productos'
    )
    provider_count = fields.Integer(
        string='Proveedores',
        compute='_compute_provider_count'
    )
    
    # Productos incluidos en el contrato
    product_line_ids = fields.One2many(
        'leasing.contract.product.line',
        'contract_id',
        string='Productos Incluidos'
    )
    product_count = fields.Integer(
        string='Productos',
        compute='_compute_product_count'
    )
    
    # Notas y documentación
    notes = fields.Text(
        string='Notas',
        tracking=True
    )
    
    # Plantilla de contrato
    template_id = fields.Many2one(
        'leasing.contract.template',
        string='Plantilla',
        tracking=True,
        help='Plantilla utilizada para generar este contrato'
    )
    rendered_content = fields.Html(
        string='Contenido Renderizado',
        compute='_compute_rendered_content',
        store=False,
        help='Contenido del contrato renderizado con los datos actuales'
    )
    
    # Campos relacionados
    purchase_order_ids = fields.One2many(
        'purchase.order',
        'leasing_contract_id',
        string='Órdenes de Compra'
    )
    purchase_order_count = fields.Integer(
        string='Nº Órdenes de Compra',
        compute='_compute_purchase_order_count'
    )

    @api.depends('provider_ids')
    def _compute_provider_count(self):
        for record in self:
            record.provider_count = len(record.provider_ids)

    @api.depends('product_line_ids')
    def _compute_product_count(self):
        for record in self:
            record.product_count = len(record.product_line_ids)

    @api.depends('purchase_order_ids')
    def _compute_purchase_order_count(self):
        for record in self:
            record.purchase_order_count = len(record.purchase_order_ids)

    @api.depends('template_id', 'name', 'partner_id', 'brand_ids', 'start_date', 'end_date', 'provider_ids', 'notes')
    def _compute_rendered_content(self):
        """Renderizar el contenido del contrato usando la plantilla y los datos del contrato."""
        for record in self:
            if record.template_id and record.template_id.contract_content:
                content = record.template_id.contract_content
                
                # Reemplazar variables
                replacements = {
                    'contract_name': record.name or '',
                    'partner_name': record.partner_id.name if record.partner_id else '',
                    'brand_names': ', '.join(record.brand_ids.mapped('name')) if record.brand_ids else (record.brand_id.name if record.brand_id else ''),
                    'start_date': record.start_date.strftime('%d/%m/%Y') if record.start_date else '',
                    'end_date': record.end_date.strftime('%d/%m/%Y') if record.end_date else '',
                    'provider_names': ', '.join(record.provider_ids.mapped('name')) if record.provider_ids else '',
                    'notes': record.notes or '',
                }
                
                # Reemplazar variables en formato %(variable)s y [[variable]]
                for key, value in replacements.items():
                    # Sintaxis Python estándar %(variable)s
                    content = content.replace(f'%({key})s', str(value))
                    # Sintaxis alternativa [[variable]]
                    content = content.replace(f'[[{key}]]', str(value))
                
                record.rendered_content = content
            else:
                record.rendered_content = False

    @api.model
    def create(self, vals):
        if vals.get('name', _('Nuevo')) == _('Nuevo'):
            vals['name'] = self.env['ir.sequence'].next_by_code('leasing.contract') or _('Nuevo')
        
        # Si viene brand_id pero no brand_ids, migrar automáticamente
        if vals.get('brand_id') and not vals.get('brand_ids'):
            vals['brand_ids'] = [(6, 0, [vals['brand_id']])]
        
        contract = super().create(vals)
        
        # Si viene desde purchase.order, asociar automáticamente
        purchase_order_id = self.env.context.get('return_to_purchase_order')
        if purchase_order_id:
            purchase_order = self.env['purchase.order'].browse(purchase_order_id)
            if purchase_order.exists():
                purchase_order.write({
                    'leasing_contract_id': contract.id,
                    'is_leasing': True,
                })
        
        return contract

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.start_date and record.end_date:
                if record.end_date < record.start_date:
                    raise ValidationError(_('La fecha de fin debe ser posterior a la fecha de inicio.'))

    def action_activate(self):
        """Activa el contrato"""
        self.write({'state': 'active'})

    def action_expire(self):
        """Marca el contrato como vencido"""
        self.write({'state': 'expired'})

    def action_cancel(self):
        """Cancela el contrato"""
        self.write({'state': 'cancelled'})

    def action_view_providers(self):
        """Abre la vista de proveedores del contrato"""
        self.ensure_one()
        action = {
            'name': f'Proveedores - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.provider_ids.ids)],
        }
        return action

    def action_view_products(self):
        """Abre la vista de productos del contrato"""
        self.ensure_one()
        action = {
            'name': f'Productos - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'leasing.contract.product.line',
            'view_mode': 'tree,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id},
        }
        return action

    def action_view_purchase_orders(self):
        """Abre la vista de órdenes de compra relacionadas"""
        self.ensure_one()
        action = {
            'name': f'Órdenes de Compra - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'domain': [('leasing_contract_id', '=', self.id)],
            'context': {'default_leasing_contract_id': self.id},
        }
        return action


class LeasingContractProductLine(models.Model):
    _name = 'leasing.contract.product.line'
    _description = 'Línea de Producto en Contrato de Leasing'
    _order = 'contract_id, product_id'

    contract_id = fields.Many2one(
        'leasing.contract',
        string='Contrato',
        required=True,
        ondelete='cascade',
        index=True
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        required=True,
        domain=[('type', '=', 'product')],
        help='Producto incluido en el contrato de leasing'
    )
    product_tmpl_id = fields.Many2one(
        'product.template',
        related='product_id.product_tmpl_id',
        string='Plantilla de Producto',
        store=True,
        readonly=True
    )
    active = fields.Boolean(
        string='Activo',
        default=True,
        help='Si está desactivado, este producto ya no está incluido en el contrato'
    )

    _unique_product_contract = models.Constraint(
        'unique(contract_id, product_id)',
        'El producto ya está incluido en este contrato.',
    )

