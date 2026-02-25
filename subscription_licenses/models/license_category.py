# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class LicenseCategory(models.Model):
    """Modelo para categorías de licencias (ej: Office 365, Google Workspace)."""
    _name = 'license.category'
    _description = 'Categoría de Licencia'
    _order = 'name'
    _rec_name = 'name'

    name = fields.Char(
        string='Categoría',
        required=True,
        help='Nombre de la categoría de licencia (ej: Office 365, Google Workspace, Adobe Creative Cloud)',
        index=True
    )
    code = fields.Char(
        string='Código',
        help='Código único para la categoría (opcional)',
        index=True
    )
    description = fields.Text(string='Descripción')
    active = fields.Boolean(string='Activo', default=True)
    
    # Contador de licencias en esta categoría
    license_count = fields.Integer(string='Total Licencias', compute='_compute_license_count', store=False)
    
    _sql_constraints = [
        ('unique_name', 'unique(name)', 'El nombre de la categoría debe ser único.')
    ]

    @api.depends('name')
    def _compute_license_count(self):
        """Cuenta cuántas licencias pertenecen a esta categoría."""
        for rec in self:
            if 'license.template' in self.env:
                rec.license_count = self.env['license.template'].search_count([
                    ('name', '=', rec.id),
                    ('active', '=', True)
                ])
            else:
                rec.license_count = 0

    def action_view_licenses(self):
        """Abre la vista de licencias de esta categoría."""
        self.ensure_one()
        if 'license.template' in self.env:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Licencias de %s') % self.name,
                'res_model': 'license.template',
                'view_mode': 'list,form',
                'domain': [('name', '=', self.id), ('active', '=', True)],
                'context': {'default_name': self.id},
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('El modelo license.template no está disponible.'),
                    'type': 'warning',
                }
            }

    def action_activate(self):
        """Activa la categoría."""
        for rec in self:
            rec.active = True

    def action_deactivate(self):
        """Desactiva la categoría."""
        for rec in self:
            rec.active = False
