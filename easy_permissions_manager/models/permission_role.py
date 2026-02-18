# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class PermissionRole(models.Model):
    """Roles predefinidos para asignar permisos fácilmente."""
    
    _name = 'permission.role'
    _description = 'Rol de Permisos'
    _order = 'name'

    name = fields.Char(
        string='Nombre del Rol',
        required=True,
        help='Nombre descriptivo del rol (ej: "Solo Lectura Inventario")'
    )
    
    description = fields.Text(
        string='Descripción',
        help='Descripción de qué permisos incluye este rol'
    )
    
    group_ids = fields.Many2many(
        'res.groups',
        'permission_role_group_rel',
        'role_id',
        'group_id',
        string='Grupos a Agregar',
        help='Grupos de permisos que se agregarán al usuario'
    )
    
    excluded_group_ids = fields.Many2many(
        'res.groups',
        'permission_role_excluded_group_rel',
        'role_id',
        'group_id',
        string='Grupos a Remover',
        help='Grupos de permisos que se removerán del usuario'
    )
    
    module_ids = fields.Many2many(
        'ir.module.module',
        'permission_role_module_rel',
        'role_id',
        'module_id',
        string='Módulos Afectados',
        help='Módulos que se ven afectados por este rol'
    )
    
    active = fields.Boolean(
        string='Activo',
        default=True,
        help='Si está desactivado, este rol no aparecerá en las opciones'
    )
