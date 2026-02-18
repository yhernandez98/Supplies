# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PermissionManagerModuleLine(models.TransientModel):
    """Líneas de módulos para el gestor de permisos."""
    
    _name = 'permission.manager.module.line'
    _description = 'Línea de Módulo en Gestor de Permisos'
    _order = 'module_id'
    
    manager_id = fields.Many2one(
        'permission.manager',
        string='Gestor',
        required=True,
        ondelete='cascade'
    )
    
    module_id = fields.Many2one(
        'ir.module.module',
        string='Módulo',
        required=True
    )
    
    module_name = fields.Char(
        related='module_id.name',
        string='Nombre Técnico',
        store=False,
        readonly=True
    )
    
    module_display_name = fields.Char(
        related='module_id.shortdesc',
        string='Nombre',
        store=False,
        readonly=True
    )
    
    @api.onchange('is_allowed', 'is_blocked')
    def _onchange_toggles(self):
        """Asegurar que no estén ambos activados al mismo tiempo."""
        if self.is_allowed and self.is_blocked:
            # Si ambos están activados, desactivar el bloqueado
            self.is_blocked = False
    
    is_allowed = fields.Boolean(
        string='Permitir',
        default=False,
        help='Marcar para permitir acceso a este módulo'
    )
    
    is_blocked = fields.Boolean(
        string='Bloquear',
        default=False,
        help='Marcar para bloquear acceso a este módulo'
    )
    
    @api.constrains('module_id')
    def _check_module_id(self):
        """Validar que module_id esté presente."""
        for record in self:
            if not record.module_id or not record.module_id.id:
                # En lugar de lanzar error, eliminar la línea automáticamente
                try:
                    record.sudo().unlink()
                except Exception:
                    pass
    