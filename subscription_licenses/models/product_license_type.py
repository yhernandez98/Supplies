# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProductLicenseType(models.Model):
    """Modelo para tipos de licencias (similar a product.business.line)."""
    _name = 'product.license.type'
    _description = 'Tipo de Licencia'
    _order = 'code, name'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Nombre', required=True, translate=False, help='Ej: MICROSOFT 365, GOOGLE WORKSPACE, etc.', index=True)
    code = fields.Char(string='Código', required=True, help='Código único para la licencia (ej: LIMIC-M365-BUSBA)', index=True)
    active = fields.Boolean(string='Activo', default=True, index=True)
    description = fields.Text(string='Descripción')
    price_usd = fields.Float(string='Precio USD', required=True, digits=(16, 2), help='Precio fijo en dólares')
    company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.company, required=True, index=True)
    
    # Contador de asignaciones activas
    assignment_count = fields.Integer(string='Asignaciones Activas', compute='_compute_assignment_count', store=False)

    _unique_code_company = models.Constraint(
        'unique(code, company_id)',
        'El código de licencia debe ser único por compañía.',
    )

    def _compute_assignment_count(self):
        for rec in self:
            # Ya no se usa subscription.license.assignment, usar license.assignment en su lugar
            if 'license.assignment' in self.env:
                rec.assignment_count = self.env['license.assignment'].search_count([
                    ('license_id', '=', rec.id),
                    ('state', '=', 'active'),
                ])
            else:
                rec.assignment_count = 0

    def action_view_assignments(self):
        """Abre la vista de asignaciones de este tipo de licencia."""
        self.ensure_one()
        # Ya no se usa subscription.license.assignment, usar license.assignment en su lugar
        if 'license.assignment' in self.env:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Asignaciones de %s') % self.name,
                'res_model': 'license.assignment',
                'view_mode': 'list,form',
                'domain': [('license_id', '=', self.id)],
                'context': {'default_license_id': self.id},
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('El modelo license.assignment no está disponible.'),
                    'type': 'warning',
                }
            }

    def action_activate(self):
        """Activa el tipo de licencia."""
        for rec in self:
            rec.active = True

    def action_deactivate(self):
        """Desactiva el tipo de licencia."""
        for rec in self:
            rec.active = False

