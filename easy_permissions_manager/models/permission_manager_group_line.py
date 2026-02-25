# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PermissionManagerGroupLine(models.TransientModel):
    """Líneas de grupos para el gestor de permisos."""
    
    _name = 'permission.manager.group.line'
    _description = 'Línea de Grupo en Gestor de Permisos'
    _order = 'group_id'
    
    manager_id = fields.Many2one(
        'permission.manager',
        string='Gestor',
        required=True,
        ondelete='cascade'
    )
    
    group_id = fields.Many2one(
        'res.groups',
        string='Grupo',
        required=True
    )
    
    group_name = fields.Char(
        related='group_id.name',
        string='Nombre',
        store=False,
        readonly=True
    )
    
    category_name = fields.Char(
        string='Categoría',
        compute='_compute_category_name',
        store=False,
        readonly=True
    )
    
    @api.depends('group_id')
    def _compute_category_name(self):
        for line in self:
            if not line.group_id:
                line.category_name = ''
            elif hasattr(line.group_id, 'category_id') and line.group_id.category_id:
                line.category_name = line.group_id.category_id.name or ''
            else:
                line.category_name = ''
    
    is_selected = fields.Boolean(
        string='Activar',
        default=False,
        help='Marcar para dar este grupo al usuario'
    )
    
    is_excluded = fields.Boolean(
        string='Excluir',
        default=False,
        help='Marcar para remover este grupo del usuario'
    )
    
    @api.onchange('is_selected', 'is_excluded')
    def _onchange_toggles(self):
        """Asegurar que no estén ambos activados al mismo tiempo."""
        if self.is_selected and self.is_excluded:
            # Si ambos están activados, desactivar el excluido
            self.is_excluded = False
    
    @api.constrains('group_id')
    def _check_group_id(self):
        """Validar que group_id esté presente."""
        for record in self:
            if not record.group_id or not record.group_id.id:
                # En lugar de lanzar error, eliminar la línea automáticamente
                try:
                    record.sudo().unlink()
                except Exception:
                    pass
    