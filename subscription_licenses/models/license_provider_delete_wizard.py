# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class LicenseProviderDeleteWizard(models.TransientModel):
    _name = 'license.provider.delete.wizard'
    _description = 'Wizard de Confirmación para Eliminar Proveedor'

    provider_stock_id = fields.Many2one(
        'license.provider.stock',
        string='Proveedor a Eliminar',
        required=True,
        readonly=True
    )
    provider_name = fields.Char(
        string='Proveedor',
        related='provider_stock_id.provider_id.name',
        readonly=True
    )
    license_name = fields.Char(
        string='Licencia',
        related='provider_stock_id.license_product_id.name',
        readonly=True
    )
    assigned_quantity = fields.Integer(
        string='Cantidad Asignada',
        related='provider_stock_id.assigned_quantity',
        readonly=True,
        help='Cantidad de licencias asignadas activas de este proveedor'
    )
    warning_message = fields.Html(
        string='Advertencia',
        compute='_compute_warning_message',
        readonly=True
    )

    @api.depends('assigned_quantity')
    def _compute_warning_message(self):
        """Genera el mensaje de advertencia según si hay asignaciones activas."""
        for rec in self:
            if rec.assigned_quantity and rec.assigned_quantity > 0:
                rec.warning_message = _(
                    '<div class="alert alert-warning" role="alert">'
                    '<strong>⚠️ Advertencia:</strong><br/>'
                    'Este proveedor tiene <strong>%d licencia(s) asignada(s) activa(s)</strong>.<br/>'
                    'Si elimina este proveedor, las asignaciones existentes seguirán funcionando, '
                    'pero ya no podrá asignar nuevas licencias desde este proveedor.<br/><br/>'
                    '<strong>¿Está seguro de que desea eliminar este proveedor?</strong>'
                    '</div>'
                ) % rec.assigned_quantity
            else:
                rec.warning_message = _(
                    '<div class="alert alert-info" role="alert">'
                    '<strong>ℹ️ Información:</strong><br/>'
                    'Este proveedor no tiene licencias asignadas activas.<br/><br/>'
                    '<strong>¿Está seguro de que desea eliminar este proveedor?</strong>'
                    '</div>'
                )

    def action_confirm_delete(self):
        """Confirma y elimina el proveedor."""
        self.ensure_one()
        provider_stock = self.provider_stock_id
        provider_name = provider_stock.provider_id.name or 'Proveedor'
        license_name = provider_stock.license_product_id.name or 'Licencia'
        
        # Eliminar el registro
        provider_stock.unlink()
        
        # Mensaje de confirmación
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Proveedor Eliminado'),
                'message': _('El proveedor "%s" ha sido eliminado de la licencia "%s".') % (provider_name, license_name),
                'type': 'success',
                'sticky': False,
            }
        }
