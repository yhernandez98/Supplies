# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class LicenseProviderStock(models.Model):
    _name = 'license.provider.stock'
    _description = 'Stock de Licencias por Proveedor'
    _order = 'provider_id, license_product_id'
    _rec_name = 'license_product_id'

    provider_id = fields.Many2one(
        'res.partner',
        string='Proveedor',
        required=True,
        ondelete='cascade',
        help='Proveedor de licenciamiento'
    )
    provider_partner_id = fields.Many2one(
        'license.provider.partner',
        string='Proveedor (lista)',
        ondelete='set null',
        index=True,
        help='Enlace al registro de la lista Proveedores; permite mostrar esta línea en la pestaña Licencias del proveedor.',
    )
    license_product_id = fields.Many2one(
        'product.product',
        string='Licencia (Servicio)',
        required=True,
        domain=[('type', '=', 'service')],
        help='Solo productos configurados como licencia en Configuración → Licencias.',
    )
    license_template_id = fields.Many2one(
        'license.template',
        string='Licencia (plantilla)',
        ondelete='set null',
        help='Se rellena por producto para mostrar esta línea en la pestaña de la licencia.',
    )
    quantity = fields.Integer(
        string='Cantidad Disponible',
        default=0,
        help='Cantidad de licencias disponibles de este proveedor. Ignorado si Ilimitado está marcado.'
    )
    is_unlimited = fields.Boolean(
        string='Ilimitado',
        default=False,
        help='Si está marcado, este proveedor entrega licencias ilimitadas de este producto (no se usa la cantidad).'
    )
    cost_per_unit_usd = fields.Float(
        string='Costo Proveedor (USD)',
        digits=(16, 2),
        help='Costo unitario que se paga a este proveedor por esta licencia. Se usa en asignaciones y en el reporte del proveedor (ganancia = precio a cliente − este costo).',
    )
    license_category_id = fields.Many2one(
        'license.category',
        string='Categoría',
        compute='_compute_license_category',
        store=True,
        help='Categoría de la licencia'
    )
    assigned_quantity = fields.Integer(
        string='Cantidad Asignada',
        compute='_compute_assigned_quantity',
        store=False,
        help='Cantidad de licencias asignadas activas de este proveedor para esta licencia'
    )
    available_quantity_display = fields.Char(
        string='Disponible',
        compute='_compute_available_quantity_display',
        store=False,
        help='Cantidad disponible restante de este proveedor (o "Ilimitado" si es ilimitado)'
    )
    
    @api.depends('provider_id', 'license_template_id')
    def _compute_assigned_quantity(self):
        """Calcula la cantidad asignada de este proveedor para esta licencia."""
        for rec in self:
            if not rec.provider_id or not rec.license_template_id:
                rec.assigned_quantity = 0
                continue
            
            # Buscar asignaciones activas de este proveedor para esta licencia
            assignments = self.env['license.assignment'].search([
                ('license_provider_id', '=', rec.provider_id.id),
                ('license_id', '=', rec.license_template_id.id),
                ('state', '=', 'active')
            ])
            rec.assigned_quantity = sum(assignments.mapped('quantity'))
    
    @api.depends('is_unlimited', 'quantity', 'assigned_quantity')
    def _compute_available_quantity_display(self):
        """Calcula la cantidad disponible restante o muestra 'Ilimitado'."""
        for rec in self:
            if rec.is_unlimited:
                rec.available_quantity_display = 'Ilimitado'
            else:
                available = rec.quantity - rec.assigned_quantity
                rec.available_quantity_display = str(max(0, available))
    
    @api.model_create_multi
    def create(self, vals_list):
        # Asegurar provider_id y provider_partner_id al crear desde la pestaña Licencias del proveedor.
        # Al guardar desde el modal "Crear Licencias" a veces no vienen en vals; usar contexto.
        PartnerModel = self.env['license.provider.partner']
        ctx = self.env.context
        for vals in vals_list:
            # Respaldo: default_provider_partner_id (lista embebida) o active_id (modal abierto desde formulario proveedor)
            provider_partner_id = (
                vals.get('provider_partner_id')
                or ctx.get('default_provider_partner_id')
                or (ctx.get('active_model') == 'license.provider.partner' and ctx.get('active_id'))
            )
            provider_id = vals.get('provider_id') or ctx.get('default_provider_id')
            if provider_partner_id:
                partner = PartnerModel.browse(provider_partner_id)
                if partner.exists() and partner.partner_id:
                    vals['provider_partner_id'] = partner.id
                    vals['provider_id'] = partner.partner_id.id
            elif provider_id:
                vals['provider_id'] = provider_id
        recs = super().create(vals_list)
        recs._set_license_template_from_product()
        return recs

    def write(self, vals):
        res = super().write(vals)
        if 'license_product_id' in vals:
            self._set_license_template_from_product()
        return res

    def _set_license_template_from_product(self):
        """Rellena license_template_id cuando hay license_product_id para enlazar con la pestaña de la licencia."""
        Template = self.env['license.template']
        for rec in self:
            if rec.license_product_id and not rec.license_template_id:
                t = Template.search([('product_id', '=', rec.license_product_id.id)], limit=1)
                if t:
                    rec.license_template_id = t.id
            elif not rec.license_product_id and rec.license_template_id:
                rec.license_template_id = False

    @api.depends('license_product_id')
    def _compute_license_category(self):
        """Obtiene la categoría de la licencia desde license.template si existe."""
        for rec in self:
            if rec.license_product_id:
                try:
                    # Buscar si hay un license.template con este producto
                    if 'license.template' in self.env:
                        license_template = self.env['license.template'].search([
                            ('product_id', '=', rec.license_product_id.id)
                        ], limit=1)
                        if license_template and license_template.name:
                            rec.license_category_id = license_template.name.id
                        else:
                            rec.license_category_id = False
                    else:
                        rec.license_category_id = False
                except Exception:
                    rec.license_category_id = False
            else:
                rec.license_category_id = False

    _sql_constraints = [
        ('unique_provider_license', 'unique(provider_id, license_product_id)',
         'Ya existe un registro para este proveedor y esta licencia. Edite el existente en lugar de crear uno nuevo.'),
    ]

    @api.constrains('quantity')
    def _check_quantity(self):
        """Validar que la cantidad no sea negativa."""
        for rec in self:
            if not rec.is_unlimited and rec.quantity < 0:
                raise ValidationError(_('La cantidad no puede ser negativa.'))
    
    def action_open_delete_wizard(self):
        """Abre el wizard de confirmación para eliminar el proveedor."""
        self.ensure_one()
        return {
            'name': _('Confirmar Eliminación de Proveedor'),
            'type': 'ir.actions.act_window',
            'res_model': 'license.provider.delete.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_provider_stock_id': self.id,
            }
        }
