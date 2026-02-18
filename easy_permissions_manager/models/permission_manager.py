# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class PermissionManager(models.TransientModel):
    """Modelo para gestionar permisos de usuarios de forma simplificada."""
    
    _name = 'permission.manager'
    _description = 'Gestor de Permisos'

    user_id = fields.Many2one(
        'res.users',
        string='Usuario',
        required=True,
        help='Usuario al que se le asignarán los permisos'
    )
    
    copy_from_user_id = fields.Many2one(
        'res.users',
        string='Copiar Permisos de',
        help='Seleccione un usuario para copiar sus permisos a este usuario'
    )
    
    module_line_ids = fields.One2many(
        'permission.manager.module.line',
        'manager_id',
        string='Módulos',
        help='Lista de módulos con opción de activar/desactivar'
    )
    
    group_line_ids = fields.One2many(
        'permission.manager.group.line',
        'manager_id',
        string='Grupos',
        help='Lista de grupos con opción de activar/desactivar'
    )
    
    current_user_groups = fields.Many2many(
        'res.groups',
        'permission_manager_current_groups_rel',
        'manager_id',
        'group_id',
        string='Grupos Actuales del Usuario',
        compute='_compute_current_user_groups',
        store=False,
        help='Grupos de permisos que el usuario tiene actualmente'
    )
    
    current_user_modules = fields.Many2many(
        'ir.module.module',
        'permission_manager_current_modules_rel',
        'manager_id',
        'module_id',
        string='Módulos con Acceso Actual',
        compute='_compute_current_user_modules',
        store=False,
        help='Módulos a los que el usuario tiene acceso actualmente'
    )
    
    @api.depends('user_id', 'user_id.groups_id')
    def _compute_current_user_groups(self):
        """Calcular grupos actuales del usuario."""
        for record in self:
            if record.user_id:
                record.current_user_groups = record.user_id.groups_id
            else:
                record.current_user_groups = self.env['res.groups']
    
    @api.depends('user_id', 'user_id.groups_id')
    def _compute_current_user_modules(self):
        """Calcular módulos a los que el usuario tiene acceso actualmente."""
        for record in self:
            if not record.user_id:
                record.current_user_modules = self.env['ir.module.module']
                continue
            
            # Obtener todos los grupos del usuario
            user_groups = record.user_id.groups_id
            
            # Buscar módulos relacionados con estos grupos
            # Buscar en ir.model.data los grupos del usuario
            group_data = self.env['ir.model.data'].search([
                ('model', '=', 'res.groups'),
                ('res_id', 'in', user_groups.ids)
            ])
            
            # Obtener nombres de módulos únicos
            module_names = list(set(group_data.mapped('module')))
            
            # Buscar módulos instalados
            if module_names:
                modules = self.env['ir.module.module'].search([
                    ('name', 'in', module_names),
                    ('state', '=', 'installed')
                ])
                record.current_user_modules = modules
            else:
                record.current_user_modules = self.env['ir.module.module']
    
    module_ids = fields.Many2many(
        'ir.module.module',
        string='Módulos',
        domain=[('state', '=', 'installed')],
        help='Módulos instalados en el sistema'
    )
    
    role_ids = fields.Many2many(
        'permission.role',
        'permission_manager_role_rel',
        'manager_id',
        'role_id',
        string='Roles Predefinidos',
        help='Seleccione uno o más roles predefinidos para aplicar permisos rápidamente'
    )
    
    role_apply_mode = fields.Selection([
        ('add', 'Agregar al Existente (Mantener permisos actuales y agregar los del rol)'),
        ('replace', 'Reemplazar Todo (Eliminar todos los permisos y aplicar solo los del rol)'),
    ], string='Modo de Aplicación de Roles',
       default='add',
       help='Agregar permisos del rol a los existentes o reemplazar todos los permisos con los del rol')
    
    allowed_modules = fields.Many2many(
        'ir.module.module',
        'permission_manager_allowed_module_rel',
        'manager_id',
        'module_id',
        string='Módulos Permitidos',
        domain=[('state', '=', 'installed')],
        help='Seleccione los módulos a los que el usuario tendrá acceso. Los módulos NO seleccionados serán bloqueados automáticamente.'
    )
    
    apply_restriction = fields.Boolean(
        string='Aplicar Restricción de Módulos',
        default=False,
        help='Si está activado, solo se permitirán los módulos seleccionados y se bloquearán todos los demás'
    )
    
    restriction_mode = fields.Selection([
        ('allow_list', 'Lista de Permitidos (Permitir solo seleccionados)'),
        ('block_list', 'Lista de Bloqueados (Bloquear solo seleccionados)'),
    ], string='Modo de Restricción',
       default='allow_list',
       help='Permitir solo módulos seleccionados o bloquear solo módulos seleccionados')
    
    operation_mode = fields.Selection([
        ('add', 'Agregar Permisos (Sin quitar existentes)'),
        ('replace', 'Reemplazar Permisos (Solo los seleccionados)'),
    ], string='Modo de Operación',
       default='replace',
       help='Agregar permisos a los existentes o reemplazar todos los permisos con solo los seleccionados')
    
    blocked_modules = fields.Many2many(
        'ir.module.module',
        'permission_manager_blocked_module_rel',
        'manager_id',
        'module_id',
        string='Módulos a Bloquear',
        domain=[('state', '=', 'installed')],
        help='Seleccione los módulos que desea bloquear específicamente. Solo estos módulos serán bloqueados.'
    )
    
    groups_to_exclude = fields.Many2many(
        'res.groups',
        'permission_manager_excluded_groups_rel',
        'manager_id',
        'group_id',
        string='Grupos a Excluir (Control Fino)',
        help='Grupos específicos que se removerán incluso si pertenecen a módulos permitidos. Útil para dejar solo lo esencial.'
    )
    
    preview_groups = fields.Many2many(
        'res.groups',
        'permission_manager_preview_groups_rel',
        'manager_id',
        'group_id',
        string='Grupos que se Agregarán (Vista Previa)',
        compute='_compute_preview_groups',
        store=False,
        help='Vista previa de los grupos que se agregarán basados en los módulos seleccionados'
    )
    
    @api.depends('allowed_modules', 'apply_restriction')
    def _compute_preview_groups(self):
        """Calcular grupos que se agregarán basados en módulos permitidos."""
        for record in self:
            if record.apply_restriction and record.allowed_modules:
                record.preview_groups = self._get_groups_from_modules(record.allowed_modules)
            else:
                record.preview_groups = self.env['res.groups']
    
    @api.model
    def default_get(self, fields_list):
        """Cargar módulos instalados por defecto."""
        res = super().default_get(fields_list)
        
        if 'module_ids' in fields_list:
            installed_modules = self.env['ir.module.module'].search([
                ('state', '=', 'installed')
            ])
            res['module_ids'] = [(6, 0, installed_modules.ids)]
        
        return res
    
    @api.onchange('user_id')
    def _onchange_user_id(self):
        """Cargar módulos y grupos cuando se selecciona un usuario."""
        # Solo cargar automáticamente si se está usando la nueva interfaz con líneas
        # La vista original no necesita esta carga automática
        if self.user_id:
            # No cargar automáticamente para evitar conflictos con la vista original
            pass
    
    @api.onchange('role_ids')
    def _onchange_role_ids(self):
        """Aplicar permisos de los roles seleccionados."""
        if self.role_ids:
            # Aquí se aplicarían los permisos de los roles
            # Por ahora solo mostramos información
            pass
    
    def action_debug_user_groups(self):
        """Método de debug para validar grupos del usuario y detectar conflictos de tipo de usuario."""
        self.ensure_one()
        
        if not self.user_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Debug: Error',
                    'message': 'Por favor seleccione un usuario primero.',
                    'type': 'warning',
                }
            }
        
        # Obtener grupos actuales del usuario
        current_groups = self.user_id.groups_id
        
        # Obtener grupos esenciales (tipos de usuario)
        essential_groups = self.env['res.groups'].search([
            '|', '|',
            ('name', '=', 'Internal User'),
            ('name', '=', 'Portal'),
            ('name', '=', 'Public'),
        ])
        
        # Detectar tipo de usuario actual
        internal_user_group = essential_groups.filtered(lambda g: 'Internal User' in g.name)
        portal_group = essential_groups.filtered(lambda g: 'Portal' in g.name)
        public_group = essential_groups.filtered(lambda g: 'Public' in g.name)
        
        current_user_type = None
        current_user_type_code = None  # Código interno: 'internal', 'portal', 'public', o None
        if current_groups & internal_user_group:
            current_user_type = 'Internal User'
            current_user_type_code = 'internal'
        elif current_groups & portal_group:
            current_user_type = 'Portal'
            current_user_type_code = 'portal'
        elif current_groups & public_group:
            current_user_type = 'Public'
            current_user_type_code = 'public'
        else:
            current_user_type = 'Sin tipo (debería ser Internal User)'
            current_user_type_code = None  # Sin tipo de usuario
            # IMPORTANTE: Agregar Internal User automáticamente si el usuario no tiene tipo
            if internal_user_group and not (current_groups & internal_user_group):
                groups_to_add |= internal_user_group
                _logger.warning('Usuario sin tipo de usuario detectado. Agregando Internal User automáticamente.')
                current_user_type_code = 'internal'  # Ahora tiene tipo
        
        # Obtener grupos esenciales que tiene el usuario
        user_essential_groups = current_groups & essential_groups
        
        # Construir mensaje de debug
        debug_parts = []
        debug_parts.append('=== DEBUG: Información de Grupos del Usuario ===')
        debug_parts.append('')
        debug_parts.append('Usuario: %s (ID: %s)' % (self.user_id.name, self.user_id.id))
        debug_parts.append('')
        debug_parts.append('Tipo de Usuario Actual: %s' % current_user_type)
        debug_parts.append('')
        debug_parts.append('Total de Grupos del Usuario: %d' % len(current_groups))
        debug_parts.append('')
        
        # Información sobre grupos esenciales
        debug_parts.append('=== Grupos de Tipo de Usuario ===')
        if user_essential_groups:
            debug_parts.append('⚠️ PROBLEMA DETECTADO: El usuario tiene %d tipo(s) de usuario:' % len(user_essential_groups))
            for group in user_essential_groups:
                debug_parts.append('  - %s (ID: %s)' % (group.name, group.id))
        else:
            debug_parts.append('✅ El usuario NO tiene grupos de tipo de usuario (esto es un problema)')
        debug_parts.append('')
        
        # Información sobre grupos que se agregarían
        if self.apply_restriction and self.restriction_mode == 'allow_list' and self.allowed_modules:
            debug_parts.append('=== Grupos que se Agregarían (de módulos permitidos) ===')
            module_groups = self._get_groups_from_modules(self.allowed_modules)
            essential_in_module_groups = module_groups & essential_groups
            if essential_in_module_groups:
                debug_parts.append('⚠️ PROBLEMA: Los módulos seleccionados incluyen grupos de tipo de usuario:')
                for group in essential_in_module_groups:
                    debug_parts.append('  - %s (ID: %s)' % (group.name, group.id))
            else:
                debug_parts.append('✅ Los módulos seleccionados NO incluyen grupos de tipo de usuario')
            debug_parts.append('Total grupos de módulos: %d' % len(module_groups))
            debug_parts.append('')
        
        # Información sobre grupos de roles
        if self.role_ids:
            debug_parts.append('=== Grupos de los Roles Seleccionados ===')
            debug_parts.append('Roles seleccionados: %s' % ', '.join(self.role_ids.mapped('name')))
            debug_parts.append('Modo de aplicación: %s' % ('Reemplazar Todo' if self.role_apply_mode == 'replace' else 'Agregar al Existente'))
            role_groups_to_add, role_groups_to_remove = self._get_role_groups()
            essential_in_role_groups = role_groups_to_add & essential_groups
            if essential_in_role_groups:
                debug_parts.append('⚠️ PROBLEMA: Los roles incluyen grupos de tipo de usuario:')
                for group in essential_in_role_groups:
                    debug_parts.append('  - %s (ID: %s)' % (group.name, group.id))
            else:
                debug_parts.append('✅ Los roles NO incluyen grupos de tipo de usuario')
            debug_parts.append('Total grupos de los roles: %d' % len(role_groups_to_add))
            debug_parts.append('')
        
        # Simular cálculo de grupos finales
        debug_parts.append('=== Simulación de Grupos Finales ===')
        groups_to_add = self.env['res.groups']
        groups_to_remove = self.env['res.groups']
        
        if self.apply_restriction and self.restriction_mode == 'allow_list' and self.allowed_modules:
            module_groups = self._get_groups_from_modules(self.allowed_modules)
            groups_to_add |= module_groups
        
        if self.role_ids:
            role_groups_to_add, role_groups_to_remove = self._get_role_groups()
            if self.role_apply_mode == 'replace':
                # En modo reemplazar, se eliminan todos los grupos actuales excepto esenciales
                groups_to_remove = current_groups - essential_groups
                groups_to_add = role_groups_to_add
                groups_to_remove |= role_groups_to_remove
            else:
                # En modo agregar, se mantienen los actuales y se agregan los del rol
                groups_to_add |= role_groups_to_add
                groups_to_remove |= role_groups_to_remove
        
        # Simular final_groups
        final_groups = current_groups | groups_to_add
        final_groups = final_groups - groups_to_remove
        
        final_essential = final_groups & essential_groups
        if len(final_essential) > 1:
            debug_parts.append('❌ ERROR: Los grupos finales contienen %d tipos de usuario:' % len(final_essential))
            for group in final_essential:
                debug_parts.append('  - %s (ID: %s)' % (group.name, group.id))
            debug_parts.append('')
            debug_parts.append('⚠️ Esto causará el error: "El usuario no puede tener más de un tipo de usuario"')
        elif len(final_essential) == 1:
            debug_parts.append('✅ Los grupos finales contienen solo 1 tipo de usuario: %s' % final_essential[0].name)
        else:
            debug_parts.append('⚠️ Los grupos finales NO contienen ningún tipo de usuario (se agregará Internal User)')
        
        debug_parts.append('')
        debug_parts.append('Total grupos finales simulados: %d' % len(final_groups))
        debug_parts.append('')
        debug_parts.append('=== Fin del Debug ===')
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Debug: Información de Grupos',
                'message': '\n'.join(debug_parts),
                'type': 'info',
                'sticky': True,
            }
        }
    
    def action_apply_permissions(self):
        """Aplicar los permisos configurados al usuario."""
        self.ensure_one()
        
        if not self.user_id:
            raise UserError(_('Debe seleccionar un usuario.'))
        
        # VALIDACIÓN CRÍTICA: Asegurar que self.user_id es un registro único y válido
        if not self.user_id.id:
            raise UserError(_('El usuario seleccionado no tiene un ID válido. Por favor, seleccione un usuario diferente.'))
        
        # Verificar que el usuario existe y es único
        user_check = self.env['res.users'].browse(self.user_id.id).exists()
        if not user_check:
            raise UserError(_('El usuario seleccionado no existe en la base de datos. ID: %s') % self.user_id.id)
        
        if len(user_check) > 1:
            raise UserError(_('Error: Se encontraron múltiples usuarios con el mismo ID. Esto no debería ocurrir. ID: %s') % self.user_id.id)
        
        # CRÍTICO: Definir target_user al inicio para usarlo en todo el método
        target_user = self.env['res.users'].browse(self.user_id.id)
        if not target_user.exists():
            raise UserError(_('El usuario con ID %s no existe en la base de datos.') % self.user_id.id)
        
        if len(target_user) > 1:
            raise UserError(_('Error crítico: Se encontraron múltiples usuarios con el mismo ID %s. Esto no debería ocurrir.') % self.user_id.id)
        
        # VALIDACIÓN ESPECIAL: Verificar si el usuario fue duplicado y tiene relaciones compartidas
        # Cuando se duplica un usuario en Odoo, algunas relaciones many2many pueden no limpiarse correctamente
        # Verificar grupos compartidos de forma sospechosa (más de X grupos en común con otro usuario)
        current_user_groups = target_user.groups_id
        if len(current_user_groups) > 0:
            # Buscar otros usuarios que tengan muchos grupos en común (posible duplicado)
            all_users = self.env['res.users'].search([
                ('id', '!=', self.user_id.id),
                ('active', 'in', [True, False])  # Incluir usuarios inactivos también
            ])
            
            for other_user in all_users:
                other_user_groups = other_user.groups_id
                common_groups = current_user_groups & other_user_groups
                
                # Si comparten más del 80% de los grupos, puede ser un duplicado
                if len(current_user_groups) > 0:
                    similarity = len(common_groups) / len(current_user_groups) if len(current_user_groups) > 0 else 0
                    if similarity > 0.8 and len(common_groups) > 5:  # Más de 5 grupos en común y >80% similitud
                        _logger.warning('⚠️ ADVERTENCIA: El usuario %s (ID: %s) comparte %d grupos (%d%%) con el usuario %s (ID: %s). '
                                      'Esto puede indicar que fue duplicado. Verificando relaciones compartidas...',
                                      self.user_id.name, self.user_id.id, len(common_groups), int(similarity * 100),
                                      other_user.name, other_user.id)
                        
                        # Verificar si comparten partner_id (esto sería un error crítico)
                        if self.user_id.partner_id and other_user.partner_id:
                            if self.user_id.partner_id.id == other_user.partner_id.id:
                                _logger.error('❌ ERROR CRÍTICO: Los usuarios %s (ID: %s) y %s (ID: %s) comparten el mismo partner_id (%s)',
                                            self.user_id.name, self.user_id.id, other_user.name, other_user.id,
                                            self.user_id.partner_id.id)
                                raise UserError(_(
                                    'Error crítico: Los usuarios "%s" (ID: %s) y "%s" (ID: %s) comparten el mismo contacto (partner_id: %s).\n\n'
                                    'Esto ocurre cuando se duplica un usuario y no se asigna un contacto único.\n\n'
                                    'Por favor, asigne contactos diferentes a cada usuario antes de aplicar permisos.'
                                ) % (self.user_id.name, self.user_id.id, other_user.name, other_user.id,
                                     self.user_id.partner_id.id))
                        
                        # Verificar si comparten login (esto también sería un error)
                        if self.user_id.login and other_user.login:
                            if self.user_id.login == other_user.login:
                                _logger.error('❌ ERROR CRÍTICO: Los usuarios %s (ID: %s) y %s (ID: %s) comparten el mismo login (%s)',
                                            self.user_id.name, self.user_id.id, other_user.name, other_user.id,
                                            self.user_id.login)
                                raise UserError(_(
                                    'Error crítico: Los usuarios "%s" (ID: %s) y "%s" (ID: %s) comparten el mismo login "%s".\n\n'
                                    'Esto ocurre cuando se duplica un usuario y no se cambia el login.\n\n'
                                    'Por favor, asigne logins diferentes a cada usuario antes de aplicar permisos.'
                                ) % (self.user_id.name, self.user_id.id, other_user.name, other_user.id,
                                     self.user_id.login))
        
        # VALIDACIÓN ESPECIAL: Verificar si el usuario fue duplicado y tiene relaciones compartidas
        # Cuando se duplica un usuario en Odoo, algunas relaciones many2many pueden no limpiarse correctamente
        # Verificar grupos compartidos de forma sospechosa (más de X grupos en común con otro usuario)
        current_user_groups = self.user_id.groups_id
        if len(current_user_groups) > 0:
            # Buscar otros usuarios que tengan muchos grupos en común (posible duplicado)
            all_users = self.env['res.users'].search([
                ('id', '!=', self.user_id.id),
                ('active', 'in', [True, False])  # Incluir usuarios inactivos también
            ])
            
            for other_user in all_users:
                other_user_groups = other_user.groups_id
                common_groups = current_user_groups & other_user_groups
                
                # Si comparten más del 80% de los grupos, puede ser un duplicado
                if len(current_user_groups) > 0:
                    similarity = len(common_groups) / len(current_user_groups) if len(current_user_groups) > 0 else 0
                    if similarity > 0.8 and len(common_groups) > 5:  # Más de 5 grupos en común y >80% similitud
                        _logger.warning('⚠️ ADVERTENCIA: El usuario %s (ID: %s) comparte %d grupos (%d%%) con el usuario %s (ID: %s). '
                                      'Esto puede indicar que fue duplicado. Verificando relaciones compartidas...',
                                      self.user_id.name, self.user_id.id, len(common_groups), int(similarity * 100),
                                      other_user.name, other_user.id)
                        
                        # Verificar si comparten partner_id (esto sería un error crítico)
                        if self.user_id.partner_id and other_user.partner_id:
                            if self.user_id.partner_id.id == other_user.partner_id.id:
                                _logger.error('❌ ERROR CRÍTICO: Los usuarios %s (ID: %s) y %s (ID: %s) comparten el mismo partner_id (%s)',
                                            self.user_id.name, self.user_id.id, other_user.name, other_user.id,
                                            self.user_id.partner_id.id)
                                raise UserError(_(
                                    'Error crítico: Los usuarios "%s" (ID: %s) y "%s" (ID: %s) comparten el mismo contacto (partner_id: %s).\n\n'
                                    'Esto ocurre cuando se duplica un usuario y no se asigna un contacto único.\n\n'
                                    'Por favor, asigne contactos diferentes a cada usuario antes de aplicar permisos.'
                                ) % (self.user_id.name, self.user_id.id, other_user.name, other_user.id,
                                     self.user_id.partner_id.id))
                        
                        # Verificar si comparten login (esto también sería un error)
                        if self.user_id.login and other_user.login:
                            if self.user_id.login == other_user.login:
                                _logger.error('❌ ERROR CRÍTICO: Los usuarios %s (ID: %s) y %s (ID: %s) comparten el mismo login (%s)',
                                            self.user_id.name, self.user_id.id, other_user.name, other_user.id,
                                            self.user_id.login)
                                raise UserError(_(
                                    'Error crítico: Los usuarios "%s" (ID: %s) y "%s" (ID: %s) comparten el mismo login "%s".\n\n'
                                    'Esto ocurre cuando se duplica un usuario y no se cambia el login.\n\n'
                                    'Por favor, asigne logins diferentes a cada usuario antes de aplicar permisos.'
                                ) % (self.user_id.name, self.user_id.id, other_user.name, other_user.id,
                                     self.user_id.login))
        
        # Log detallado del usuario antes de aplicar permisos
        _logger.info('=' * 80)
        _logger.info('APLICANDO PERMISOS - Usuario específico:')
        _logger.info('  - Nombre: %s', self.user_id.name)
        _logger.info('  - ID: %s', self.user_id.id)
        _logger.info('  - Login: %s', self.user_id.login)
        _logger.info('  - Partner ID: %s', self.user_id.partner_id.id if self.user_id.partner_id else 'N/A')
        _logger.info('  - Partner Name: %s', self.user_id.partner_id.name if self.user_id.partner_id else 'N/A')
        _logger.info('=' * 80)
        
        # Si se usaron las líneas de módulos/grupos (nueva interfaz), procesarlas primero
        # Pero solo si hay líneas válidas
        valid_module_lines = self.module_line_ids.filtered(
            lambda l: l.module_id and hasattr(l.module_id, 'id') and l.module_id.id
        )
        valid_group_lines = self.group_line_ids.filtered(
            lambda l: l.group_id and hasattr(l.group_id, 'id') and l.group_id.id
        )
        
        if valid_module_lines or valid_group_lines:
            # Eliminar líneas inválidas antes de procesar
            invalid_module_lines = self.module_line_ids - valid_module_lines
            invalid_group_lines = self.group_line_ids - valid_group_lines
            
            if invalid_module_lines:
                try:
                    invalid_module_lines.sudo().unlink()
                except Exception:
                    pass
            
            if invalid_group_lines:
                try:
                    invalid_group_lines.sudo().unlink()
                except Exception:
                    pass
            
            return self._apply_permissions_from_lines()
        
        # Obtener grupos actuales del usuario
        current_groups = self.user_id.groups_id
        groups_to_remove = self.env['res.groups']
        groups_to_add = self.env['res.groups']
        
        # IMPORTANTE: Detectar el tipo de usuario actual ANTES de procesar grupos
        # Esto es necesario para filtrar grupos conflictivos desde el principio
        essential_groups = self.env['res.groups'].search([
            '|', '|',
            ('name', '=', 'Internal User'),
            ('name', '=', 'Portal'),
            ('name', '=', 'Public'),
        ])
        
        current_user_type = None
        current_user_type_code = None  # Código interno: 'internal', 'portal', 'public', o None
        internal_user_group = essential_groups.filtered(lambda g: 'Internal User' in g.name)
        portal_group = essential_groups.filtered(lambda g: 'Portal' in g.name)
        public_group = essential_groups.filtered(lambda g: 'Public' in g.name)
        
        if current_groups & internal_user_group:
            current_user_type = 'Internal User'
            current_user_type_code = 'internal'
        elif current_groups & portal_group:
            current_user_type = 'Portal'
            current_user_type_code = 'portal'
        elif current_groups & public_group:
            current_user_type = 'Public'
            current_user_type_code = 'public'
        else:
            # Si no tiene ningún tipo, asumir Internal User por defecto
            current_user_type = 'Sin tipo (debería ser Internal User)'
            current_user_type_code = None  # Sin tipo de usuario
            # IMPORTANTE: Agregar Internal User automáticamente si el usuario no tiene tipo
            if internal_user_group and not (current_groups & internal_user_group):
                groups_to_add |= internal_user_group
                _logger.warning('Usuario sin tipo de usuario detectado. Agregando Internal User automáticamente.')
                current_user_type_code = 'internal'  # Ahora tiene tipo
        
        # Determinar grupos de tipo de usuario conflictivos según el tipo actual
        conflicting_user_type_groups = self.env['res.groups']
        if current_user_type_code == 'internal':
            conflicting_user_type_groups = portal_group | public_group
        elif current_user_type_code == 'portal':
            conflicting_user_type_groups = internal_user_group | public_group
        elif current_user_type_code == 'public':
            conflicting_user_type_groups = internal_user_group | portal_group
        else:
            # Si no tiene tipo, no hay conflictos (pero se agregará Internal User)
            conflicting_user_type_groups = portal_group | public_group
        
        # Variables para tracking de desbloqueo
        menus_reactivated_count = 0
        rules_removed_count = 0
        
        # 1. Si está activada la restricción de módulos, aplicar lógica según el modo
        modules_to_block = self.env['ir.module.module']
        if self.apply_restriction:
            if self.restriction_mode == 'allow_list' and self.allowed_modules:
                # Modo: Lista de Permitidos
                # IMPORTANTE: Primero desbloquear los módulos permitidos (reactivar menús y eliminar reglas de bloqueo)
                menus_reactivated_count = self._unblock_module_menus(self.allowed_modules)
                if menus_reactivated_count > 0:
                    _logger.info('Menús reactivados: %d', menus_reactivated_count)
                
                rules_removed_count, block_groups_to_remove = self._remove_blocking_ir_rules(self.allowed_modules)
                if rules_removed_count > 0:
                    _logger.info('Reglas de bloqueo eliminadas: %d', rules_removed_count)
                    # Remover los grupos de bloqueo del usuario
                    if block_groups_to_remove:
                        groups_to_remove |= block_groups_to_remove
                        _logger.info('Grupos de bloqueo a remover: %s', ', '.join(block_groups_to_remove.mapped('name')))
                
                # Agregar grupos de módulos permitidos
                module_groups = self._get_groups_from_modules(self.allowed_modules)
                
                # IMPORTANTE: Filtrar grupos de tipo de usuario conflictivos ANTES de agregar
                if conflicting_user_type_groups:
                    removed_conflicts = module_groups & conflicting_user_type_groups
                    if removed_conflicts:
                        _logger.warning('Grupos de tipo de usuario conflictivos filtrados de módulos: %s', 
                                      ', '.join(removed_conflicts.mapped('name')))
                    module_groups = module_groups - conflicting_user_type_groups
                
                # Excluir grupos específicos que el usuario quiere remover (control fino)
                if self.groups_to_exclude:
                    module_groups = module_groups - self.groups_to_exclude
                    groups_to_remove |= self.groups_to_exclude
                    _logger.info('Grupos excluidos manualmente: %s', ', '.join(self.groups_to_exclude.mapped('name')))
                
                # Verificar el modo de operación
                operation_mode = getattr(self, 'operation_mode', False) or 'replace'
                
                if operation_mode == 'add':
                    # Modo Agregar: Solo agregar permisos, NO quitar los existentes
                    groups_to_add |= module_groups
                    _logger.info('Modo: Lista de Permitidos - AGREGAR (sin quitar existentes)')
                    _logger.info('Módulos a los que se agregarán permisos: %s', ', '.join(self.allowed_modules.mapped('name')))
                    _logger.info('Grupos que se agregarán: %d', len(module_groups))
                else:
                    # Modo Reemplazar: Reemplazar todos los permisos con solo los seleccionados
                    # Obtener todos los módulos instalados
                    all_installed_modules = self.env['ir.module.module'].search([
                        ('state', '=', 'installed')
                    ])
                    
                    # Módulos a bloquear = todos los instalados - módulos permitidos
                    modules_to_block = all_installed_modules - self.allowed_modules
                    
                    groups_to_add |= module_groups
                    
                    # Remover grupos de módulos bloqueados
                    blocked_groups = self._get_groups_from_modules(modules_to_block)
                    
                    # CRÍTICO: NO remover grupos compartidos esenciales (base.group_user, stock.group_stock_manager, etc.)
                    # Estos grupos son usados por múltiples módulos y removerlos afectaría a todos los usuarios
                    essential_shared_groups = self.env['res.groups'].search([
                        '|', '|', '|',
                        ('name', '=', 'Internal User'),
                        ('name', '=', 'Portal'),
                        ('name', '=', 'Public'),
                        ('category_id.name', '=', 'Inventory / Stock'),
                    ])
                    
                    # Filtrar grupos compartidos esenciales
                    blocked_groups = blocked_groups - essential_shared_groups
                    if essential_shared_groups & blocked_groups:
                        _logger.warning('⚠️ Grupos compartidos esenciales excluidos de remoción: %s', 
                                      ', '.join((essential_shared_groups & blocked_groups).mapped('name')))
                        _logger.info('ℹ️ El bloqueo se hará mediante reglas ir.rule específicas por usuario, no removiendo grupos compartidos.')
                    
                    groups_to_remove |= blocked_groups
                    
                    _logger.info('Modo: Lista de Permitidos - REEMPLAZAR (solo los seleccionados)')
                    _logger.info('Módulos permitidos: %s', ', '.join(self.allowed_modules.mapped('name')))
                    _logger.info('Módulos bloqueados: %s', ', '.join(modules_to_block.mapped('name')))
            
            elif self.restriction_mode == 'block_list' and self.blocked_modules:
                # Modo: Lista de Bloqueados - Solo bloquear los seleccionados
                # Bloquear solo los módulos seleccionados
                modules_to_block = self.blocked_modules
                
                # Remover grupos de módulos bloqueados
                blocked_groups = self._get_groups_from_modules(modules_to_block)
                
                # CRÍTICO: NO remover grupos compartidos esenciales (base.group_user, stock.group_stock_manager, etc.)
                # Estos grupos son usados por múltiples módulos y removerlos afectaría a todos los usuarios
                # En su lugar, usamos reglas ir.rule específicas por usuario para bloquear el acceso
                essential_shared_groups = self.env['res.groups'].search([
                    '|', '|', '|',
                    ('name', '=', 'Internal User'),
                    ('name', '=', 'Portal'),
                    ('name', '=', 'Public'),
                    ('category_id.name', '=', 'Inventory / Stock'),
                ])
                
                # Filtrar grupos compartidos esenciales
                blocked_groups = blocked_groups - essential_shared_groups
                if essential_shared_groups & blocked_groups:
                    _logger.warning('⚠️ Grupos compartidos esenciales excluidos de remoción: %s', 
                                  ', '.join((essential_shared_groups & blocked_groups).mapped('name')))
                    _logger.info('ℹ️ El bloqueo se hará mediante reglas ir.rule específicas por usuario, no removiendo grupos compartidos.')
                
                groups_to_remove |= blocked_groups
                
                # Si no se encontraron grupos, intentar buscar de forma más agresiva
                if not blocked_groups:
                    _logger.warning('No se encontraron grupos específicos para los módulos bloqueados. Intentando búsqueda más amplia...')
                    # Buscar todos los grupos que puedan estar relacionados
                    for module in modules_to_block:
                        # Buscar por nombre del módulo en cualquier campo
                        all_groups = self.env['res.groups'].search([
                            '|', '|',
                            ('name', 'ilike', module.name or ''),
                            ('category_id.name', 'ilike', module.name or ''),
                            ('category_id.name', 'ilike', module.shortdesc or ''),
                        ])
                        # Filtrar grupos compartidos esenciales
                        all_groups = all_groups - essential_shared_groups
                        if all_groups:
                            blocked_groups |= all_groups
                            _logger.info('Módulo %s: %d grupos encontrados por búsqueda amplia (después de filtrar grupos compartidos)', 
                                       module.name, len(all_groups))
                    groups_to_remove |= blocked_groups
                
                # Ocultar menús de los módulos bloqueados
                menus_hidden = self._block_module_menus(modules_to_block)
                if menus_hidden > 0:
                    _logger.info('Menús ocultados: %d', menus_hidden)
                
                # Crear reglas de dominio (ir.rule) para bloquear completamente el acceso a los modelos
                # IMPORTANTE: Este método también crea grupos de bloqueo y los asigna al usuario
                ir_rules_created, block_groups = self._create_restrictive_ir_rules(modules_to_block)
                if ir_rules_created > 0:
                    _logger.info('Reglas de dominio (ir.rule) creadas: %d', ir_rules_created)
                
                # Agregar los grupos de bloqueo a los grupos finales para que no se pierdan
                if block_groups:
                    groups_to_add |= block_groups
                    _logger.info('✅ Grupos de bloqueo agregados a groups_to_add: %s', ', '.join(block_groups.mapped('name')))
                    _logger.info('✅ IDs de grupos de bloqueo: %s', ', '.join([str(g.id) for g in block_groups]))
                else:
                    _logger.warning('⚠️ No se crearon grupos de bloqueo para los módulos bloqueados')
                
                # Excluir grupos específicos que el usuario quiere remover (control fino)
                if self.groups_to_exclude:
                    groups_to_remove |= self.groups_to_exclude
                    _logger.info('Grupos excluidos manualmente: %s', ', '.join(self.groups_to_exclude.mapped('name')))
                
                _logger.info('Modo: Lista de Bloqueados')
                _logger.info('Módulos bloqueados: %s', ', '.join(self.blocked_modules.mapped('name')))
                _logger.info('Grupos encontrados para bloquear: %d', len(blocked_groups))
                if blocked_groups:
                    _logger.info('Grupos que se removerán: %s', ', '.join(blocked_groups.mapped('name')[:10]))
        
        # 2. Aplicar permisos de los roles si están seleccionados
        if self.role_ids:
            role_groups_to_add, role_groups_to_remove = self._get_role_groups()
            
            # IMPORTANTE: Filtrar grupos de tipo de usuario conflictivos de los grupos de roles
            if conflicting_user_type_groups:
                removed_conflicts = role_groups_to_add & conflicting_user_type_groups
                if removed_conflicts:
                    _logger.warning('Grupos de tipo de usuario conflictivos filtrados de roles: %s', 
                                  ', '.join(removed_conflicts.mapped('name')))
                role_groups_to_add = role_groups_to_add - conflicting_user_type_groups
            
            if self.role_apply_mode == 'replace':
                # Modo reemplazar: eliminar todos los grupos actuales excepto esenciales
                _logger.info('Modo REEMPLAZAR: Se eliminarán todos los permisos excepto los esenciales y se aplicarán solo los del rol')
                # Obtener todos los grupos actuales del usuario
                current_user_groups = target_user.groups_id
                # Remover todos excepto los esenciales
                groups_to_remove = current_user_groups - essential_groups
                # Agregar solo los grupos del rol
                groups_to_add = role_groups_to_add
                # CRÍTICO: Asegurar que base.group_user (Internal User) esté siempre presente
                if internal_user_group and internal_user_group not in groups_to_add:
                    groups_to_add |= internal_user_group
                    _logger.info('CRÍTICO: Agregando Internal User al modo reemplazar para asegurar acceso al sistema')
                # Los grupos a remover del rol se agregan a groups_to_remove
                # PERO proteger grupos esenciales
                role_groups_to_remove_protected = role_groups_to_remove - essential_groups
                groups_to_remove |= role_groups_to_remove_protected
            else:
                # Modo agregar: mantener permisos actuales y agregar los del rol
                _logger.info('Modo AGREGAR: Se mantendrán los permisos actuales y se agregarán los del rol')
                groups_to_add |= role_groups_to_add
                groups_to_remove |= role_groups_to_remove
        
        # 2.5. Siempre remover grupos excluidos manualmente (incluso si no hay restricción de módulos)
        # PERO proteger grupos esenciales
        if self.groups_to_exclude:
            groups_to_exclude_protected = self.groups_to_exclude - essential_groups
            groups_to_remove |= groups_to_exclude_protected
        
        # 3. Proteger grupos básicos esenciales que no se deben remover
        # Estos grupos son necesarios para que el usuario pueda usar Odoo
        # NOTA: essential_groups, current_user_type, conflicting_user_type_groups ya fueron definidos al inicio
        
        # FILTRADO FINAL: Asegurar que NO haya grupos de tipo de usuario conflictivos en groups_to_add
        # Esto es una medida de seguridad adicional por si algún grupo se agregó sin filtrar
        if conflicting_user_type_groups:
            removed_conflicts = groups_to_add & conflicting_user_type_groups
            if removed_conflicts:
                _logger.warning('FILTRADO FINAL: Grupos de tipo de usuario conflictivos removidos: %s', 
                              ', '.join(removed_conflicts.mapped('name')))
            groups_to_add = groups_to_add - conflicting_user_type_groups
        
        # Si el usuario no tiene tipo de usuario, agregar Internal User por defecto
        # (Esto ya se hizo arriba, pero lo verificamos nuevamente aquí por seguridad)
        if not current_user_type_code:
            if internal_user_group and not (current_groups & internal_user_group):
                groups_to_add |= internal_user_group
                _logger.warning('CRÍTICO: Usuario sin tipo de usuario. Agregando Internal User automáticamente.')
                current_user_type_code = 'internal'
        
        # No remover grupos esenciales
        groups_to_remove = groups_to_remove - essential_groups
        if essential_groups & groups_to_remove:
            _logger.warning('Grupos esenciales protegidos: %s', ', '.join((essential_groups & groups_to_remove).mapped('name')))
        
        # CRÍTICO: Asegurar que el usuario SIEMPRE tenga Internal User si es usuario interno
        # Esto es necesario para que pueda acceder a su propio perfil (res.users)
        if current_user_type_code == 'internal' and internal_user_group:
            if not (current_groups & internal_user_group):
                groups_to_add |= internal_user_group
                _logger.info('Manteniendo grupo esencial: Internal User')
            # También asegurar que esté en final_groups (se verificará después)
        elif current_user_type_code == 'portal' and portal_group:
            if not (current_groups & portal_group):
                groups_to_add |= portal_group
                _logger.info('Manteniendo grupo esencial: Portal')
        elif current_user_type_code == 'public' and public_group:
            if not (current_groups & public_group):
                groups_to_add |= public_group
                _logger.info('Manteniendo grupo esencial: Public')
        else:
            # Si no tiene tipo de usuario, agregar Internal User por defecto
            if internal_user_group:
                groups_to_add |= internal_user_group
                _logger.warning('Usuario sin tipo de usuario. Agregando Internal User para acceso básico.')
        
        # 3. Calcular grupos finales
        # Primero agregar los nuevos grupos
        final_groups = current_groups | groups_to_add
        # Luego remover los grupos que deben ser bloqueados (excepto esenciales)
        final_groups = final_groups - groups_to_remove
        
        # Verificar que los grupos de bloqueo estén en final_groups
        block_groups_in_final = final_groups.filtered(lambda g: 'Blocked:' in g.name)
        if block_groups_in_final:
            _logger.info('✅ Grupos de bloqueo en final_groups: %s', ', '.join(block_groups_in_final.mapped('name')))
        else:
            # Buscar grupos de bloqueo en groups_to_add
            block_groups_in_to_add = groups_to_add.filtered(lambda g: 'Blocked:' in g.name)
            if block_groups_in_to_add:
                _logger.warning('⚠️ ADVERTENCIA: Grupos de bloqueo en groups_to_add pero no en final_groups: %s', 
                             ', '.join(block_groups_in_to_add.mapped('name')))
                _logger.warning('⚠️ Esto puede causar que el usuario siga teniendo acceso. Verificando...')
            else:
                _logger.warning('⚠️ ADVERTENCIA: No se encontraron grupos de bloqueo en groups_to_add ni en final_groups.')
        
        # FILTRADO FINAL DE SEGURIDAD: Asegurar que final_groups NO tenga grupos de tipo de usuario conflictivos
        # Esto es crítico para evitar el error "El usuario no puede tener más de un tipo de usuario"
        if conflicting_user_type_groups:
            # Mantener solo el tipo de usuario actual en final_groups
            final_conflicts = final_groups & conflicting_user_type_groups
            if final_conflicts:
                _logger.warning('FILTRADO CRÍTICO: Removiendo grupos de tipo de usuario conflictivos de final_groups: %s', 
                              ', '.join(final_conflicts.mapped('name')))
                final_groups = final_groups - final_conflicts
        
        # Asegurar que el usuario mantenga su tipo de usuario actual (no cambiar el tipo)
        # CRÍTICO: Si el usuario no tiene ningún tipo de usuario, agregar Internal User
        final_essential_check = final_groups & essential_groups
        if not final_essential_check:
            # El usuario no tiene ningún tipo de usuario - esto es un error crítico
            if internal_user_group:
                final_groups |= internal_user_group
                _logger.error('CRÍTICO: final_groups no contiene ningún tipo de usuario. Agregando Internal User.')
        elif current_user_type_code == 'internal' and internal_user_group:
            # CRÍTICO: Asegurar que Internal User esté SIEMPRE presente para usuarios internos
            # Esto es necesario para que puedan acceder a su propio perfil (res.users)
            if not (final_groups & internal_user_group):
                final_groups |= internal_user_group
                _logger.warning('CRÍTICO: Internal User faltante en final_groups. Agregando para acceso a res.users.')
        elif current_user_type_code == 'portal' and portal_group:
            if not (final_groups & portal_group):
                final_groups |= portal_group
                _logger.info('Asegurando grupo esencial: Portal')
        elif current_user_type_code == 'public' and public_group:
            if not (final_groups & public_group):
                final_groups |= public_group
                _logger.info('Asegurando grupo esencial: Public')
        
        # VERIFICACIÓN FINAL: Asegurar que usuarios internos SIEMPRE tengan Internal User
        # Esto previene el error "No puede modificar registros 'Usuario' (res.users)"
        if current_user_type_code == 'internal' and internal_user_group:
            if not (final_groups & internal_user_group):
                final_groups |= internal_user_group
                _logger.error('VERIFICACIÓN FINAL: Internal User faltante. Agregando para prevenir error de acceso a res.users.')
        
        # VALIDACIÓN FINAL CRÍTICA: Verificar que final_groups NO tenga múltiples tipos de usuario
        # Esto es la última línea de defensa antes de escribir a la base de datos
        final_essential_in_final = final_groups & essential_groups
        if len(final_essential_in_final) > 1:
            # Hay múltiples tipos de usuario en final_groups - esto causará error
            _logger.error('ERROR CRÍTICO: final_groups contiene múltiples tipos de usuario: %s', 
                         ', '.join(final_essential_in_final.mapped('name')))
            # Mantener solo el tipo de usuario actual
            if current_user_type == 'internal' and internal_user_group:
                final_groups = (final_groups - essential_groups) | internal_user_group
            elif current_user_type == 'portal' and portal_group:
                final_groups = (final_groups - essential_groups) | portal_group
            elif current_user_type == 'public' and public_group:
                final_groups = (final_groups - essential_groups) | public_group
            else:
                # Por defecto, mantener Internal User
                final_groups = (final_groups - essential_groups) | internal_user_group
            _logger.warning('CORREGIDO: final_groups ahora contiene solo un tipo de usuario')
        
        # Log detallado de grupos esenciales antes de escribir
        final_essential = final_groups & essential_groups
        _logger.info('Grupos esenciales en final_groups antes de escribir: %s', 
                    ', '.join(final_essential.mapped('name')) if final_essential else 'Ninguno')
        
        # VERIFICACIÓN FINAL ABSOLUTA: Asegurar que usuarios internos SIEMPRE tengan Internal User
        # Esto es crítico para prevenir el error "No puede modificar registros 'Usuario' (res.users)"
        if current_user_type_code == 'internal' and internal_user_group:
            if not (final_groups & internal_user_group):
                final_groups |= internal_user_group
                _logger.critical('VERIFICACIÓN ABSOLUTA: Internal User faltante antes de escribir. Agregando para prevenir error de acceso a res.users.')
        elif not current_user_type_code and internal_user_group:
            # Si no tiene tipo de usuario, agregar Internal User por defecto
            final_groups |= internal_user_group
            _logger.warning('Usuario sin tipo de usuario. Agregando Internal User por defecto antes de escribir.')
        
        # Verificación final de que final_groups contiene al menos un tipo de usuario
        final_essential_check = final_groups & essential_groups
        if not final_essential_check and internal_user_group:
            final_groups |= internal_user_group
            _logger.critical('VERIFICACIÓN FINAL: final_groups no contiene ningún tipo de usuario. Agregando Internal User como último recurso.')
        
        # 4. Aplicar cambios con manejo de errores
        # CRÍTICO: target_user ya está definido al inicio del método
        # Verificación adicional de seguridad
        if not target_user.exists():
            raise UserError(_('El usuario con ID %s no existe en la base de datos.') % self.user_id.id)
        
        if len(target_user) > 1:
            raise UserError(_('Error crítico: Se encontraron múltiples usuarios con el mismo ID %s. Esto no debería ocurrir.') % self.user_id.id)
        
        # VERIFICACIÓN FINAL ANTES DE ESCRIBIR: Confirmar que el usuario es único
        # Buscar por ID, login y partner_id para asegurar que no hay duplicados
        target_user_id = target_user.id
        target_login = target_user.login
        target_partner_id = target_user.partner_id.id if target_user.partner_id else None
        
        # Verificar que no hay otros usuarios con el mismo login
        if target_login:
            other_users_by_login = self.env['res.users'].search([
                ('login', '=', target_login),
                ('id', '!=', target_user_id)
            ])
            if other_users_by_login:
                _logger.error('❌ ERROR: Se encontraron usuarios con el mismo login "%s": %s', target_login,
                            ', '.join([f'{u.name} (ID: {u.id})' for u in other_users_by_login]))
                raise UserError(_(
                    'Error: Se encontraron otros usuarios con el mismo login "%s".\n\n'
                    'Usuarios encontrados:\n'
                    '- %s (ID: %s)\n'
                    '- %s\n\n'
                    'Esto puede causar que los permisos se apliquen a múltiples usuarios.\n'
                    'Por favor, corrija los usuarios duplicados antes de continuar.'
                ) % (target_login, target_user.name, target_user_id,
                     '\n'.join([f'- {u.name} (ID: {u.id})' for u in other_users_by_login])))
        
        # Verificar que no hay otros usuarios con el mismo partner_id
        if target_partner_id:
            other_users_by_partner = self.env['res.users'].search([
                ('partner_id', '=', target_partner_id),
                ('id', '!=', target_user_id)
            ])
            if other_users_by_partner:
                _logger.error('❌ ERROR: Se encontraron usuarios con el mismo partner_id %s: %s', target_partner_id,
                            ', '.join([f'{u.name} (ID: {u.id}, Login: {u.login})' for u in other_users_by_partner]))
                raise UserError(_(
                    'Error: Se encontraron otros usuarios con el mismo contacto (partner_id: %s).\n\n'
                    'Usuarios encontrados:\n'
                    '- %s (ID: %s, Login: %s)\n'
                    '- %s\n\n'
                    'Esto puede causar que los permisos se apliquen a múltiples usuarios.\n'
                    'Por favor, corrija los usuarios duplicados antes de continuar.'
                ) % (target_partner_id, target_user.name, target_user_id, target_user.login,
                     '\n'.join([f'- {u.name} (ID: {u.id}, Login: {u.login})' for u in other_users_by_partner])))
        
        _logger.info('✅ VERIFICACIÓN DE UNICIDAD COMPLETADA - Usuario: %s (ID: %s, Login: %s, Partner ID: %s)',
                    target_user.name, target_user_id, target_login, target_partner_id)
        
        # VERIFICACIÓN FINAL ANTES DE ESCRIBIR: Confirmar que el usuario es único
        # Buscar por ID, login y partner_id para asegurar que no hay duplicados
        target_user_id = target_user.id
        target_login = target_user.login
        target_partner_id = target_user.partner_id.id if target_user.partner_id else None
        
        # Verificar que no hay otros usuarios con el mismo ID (por si acaso)
        other_users_by_id = self.env['res.users'].search([
            ('id', '=', target_user_id),
            ('id', '!=', target_user_id)  # Esto no debería encontrar nada, pero lo verificamos
        ])
        if other_users_by_id:
            _logger.error('❌ ERROR: Se encontraron usuarios con el mismo ID %s: %s', target_user_id, 
                        ', '.join([f'{u.name} (Login: {u.login})' for u in other_users_by_id]))
            raise UserError(_('Error: Se encontraron usuarios duplicados con el mismo ID. Por favor, contacte al administrador.'))
        
        # Verificar que no hay otros usuarios con el mismo login
        if target_login:
            other_users_by_login = self.env['res.users'].search([
                ('login', '=', target_login),
                ('id', '!=', target_user_id)
            ])
            if other_users_by_login:
                _logger.error('❌ ERROR: Se encontraron usuarios con el mismo login "%s": %s', target_login,
                            ', '.join([f'{u.name} (ID: {u.id})' for u in other_users_by_login]))
                raise UserError(_(
                    'Error: Se encontraron otros usuarios con el mismo login "%s".\n\n'
                    'Usuarios encontrados:\n'
                    '- %s (ID: %s)\n'
                    '- %s\n\n'
                    'Esto puede causar que los permisos se apliquen a múltiples usuarios.\n'
                    'Por favor, corrija los usuarios duplicados antes de continuar.'
                ) % (target_login, target_user.name, target_user_id,
                     '\n'.join([f'- {u.name} (ID: {u.id})' for u in other_users_by_login])))
        
        # Verificar que no hay otros usuarios con el mismo partner_id
        if target_partner_id:
            other_users_by_partner = self.env['res.users'].search([
                ('partner_id', '=', target_partner_id),
                ('id', '!=', target_user_id)
            ])
            if other_users_by_partner:
                _logger.error('❌ ERROR: Se encontraron usuarios con el mismo partner_id %s: %s', target_partner_id,
                            ', '.join([f'{u.name} (ID: {u.id}, Login: {u.login})' for u in other_users_by_partner]))
                raise UserError(_(
                    'Error: Se encontraron otros usuarios con el mismo contacto (partner_id: %s).\n\n'
                    'Usuarios encontrados:\n'
                    '- %s (ID: %s, Login: %s)\n'
                    '- %s\n\n'
                    'Esto puede causar que los permisos se apliquen a múltiples usuarios.\n'
                    'Por favor, corrija los usuarios duplicados antes de continuar.'
                ) % (target_partner_id, target_user.name, target_user_id, target_user.login,
                     '\n'.join([f'- {u.name} (ID: {u.id}, Login: {u.login})' for u in other_users_by_partner])))
        
        _logger.info('✅ VERIFICACIÓN DE UNICIDAD COMPLETADA - Usuario: %s (ID: %s, Login: %s, Partner ID: %s)',
                    target_user.name, target_user_id, target_login, target_partner_id)
        
        # Log antes de escribir
        _logger.info('ESCRIBIENDO GRUPOS - Usuario específico: %s (ID: %s)', target_user.name, target_user.id)
        _logger.info('Total grupos a asignar: %d', len(final_groups))
        _logger.info('IDs de grupos: %s', final_groups.ids[:10])  # Primeros 10 para no saturar el log
        
        try:
            # Usar el registro específico obtenido con browse
            target_user.sudo().write({
                'groups_id': [(6, 0, final_groups.ids)]
            })
            _logger.info('✅ Grupos escritos exitosamente al usuario %s (ID: %s)', target_user.name, target_user.id)
        except Exception as e:
            # Si hay un error, loggear información detallada
            _logger.error('❌ ERROR al escribir grupos al usuario %s (ID: %s): %s', target_user.name, target_user.id, str(e))
            _logger.error('Grupos esenciales en final_groups: %s', 
                         ', '.join((final_groups & essential_groups).mapped('name')))
            _logger.error('Total grupos en final_groups: %d', len(final_groups))
            # Re-lanzar el error para que el usuario lo vea
            raise
        
        # 5. Invalidar caché del usuario específico para que los cambios surtan efecto
        target_user.invalidate_recordset(['groups_id'])
        
        # Verificación post-escritura: confirmar que solo este usuario tiene estos grupos
        _logger.info('VERIFICACIÓN POST-ESCRITURA:')
        _logger.info('  - Usuario modificado: %s (ID: %s)', target_user.name, target_user.id)
        _logger.info('  - Grupos actuales del usuario: %d', len(target_user.groups_id))
        _logger.info('  - Grupos esperados: %d', len(final_groups))
        
        # Log detallado
        removed_names = ', '.join(groups_to_remove.mapped('name')[:5]) if groups_to_remove else 'Ninguno'
        added_names = ', '.join(groups_to_add.mapped('name')[:5]) if groups_to_add else 'Ninguno'
        
        _logger.info('Permisos aplicados al usuario %s (ID: %s)', self.user_id.name, self.user_id.id)
        _logger.info('  - Grupos agregados: %d', len(groups_to_add))
        _logger.info('  - Grupos removidos: %d', len(groups_to_remove))
        _logger.info('  - Total grupos finales: %d', len(final_groups))
        _logger.info('=' * 80)
        
        # Construir mensaje detallado
        message_parts = []
        message_parts.append(_('Permisos aplicados correctamente al usuario %s (ID: %s).') % (target_user.name, target_user.id))
        message_parts.append('')
        
        # Información sobre roles aplicados
        if self.role_ids:
            message_parts.append(_('✅ Roles aplicados: %s') % ', '.join(self.role_ids.mapped('name')))
            message_parts.append(_('📋 Modo de aplicación: %s') % ('Reemplazar Todo' if self.role_apply_mode == 'replace' else 'Agregar al Existente'))
            if self.role_apply_mode == 'replace':
                message_parts.append(_('⚠️ NOTA: Todos los permisos anteriores fueron eliminados (excepto los esenciales) y se aplicaron solo los permisos de los roles seleccionados.'))
            else:
                message_parts.append(_('ℹ️ NOTA: Se mantuvieron los permisos actuales y se agregaron los permisos de los roles seleccionados.'))
            message_parts.append('')
        
        if self.apply_restriction:
            if self.restriction_mode == 'allow_list' and self.allowed_modules:
                operation_mode = getattr(self, 'operation_mode', False) or 'replace'
                if operation_mode == 'add':
                    message_parts.append(_('✅ Modo: Lista de Permitidos - AGREGAR'))
                    message_parts.append(_('✅ Módulos a los que se agregarán permisos: %d') % len(self.allowed_modules))
                    message_parts.append('  - ' + '\n  - '.join(self.allowed_modules.mapped('name')[:10]))
                    if len(self.allowed_modules) > 10:
                        message_parts.append(_('  ... y %d más') % (len(self.allowed_modules) - 10))
                    message_parts.append('')
                    message_parts.append(_('ℹ️ Los permisos existentes del usuario NO se quitaron.'))
                    message_parts.append('')
                else:
                    message_parts.append(_('✅ Modo: Lista de Permitidos - REEMPLAZAR'))
                    message_parts.append(_('✅ Módulos permitidos: %d') % len(self.allowed_modules))
                    message_parts.append('  - ' + '\n  - '.join(self.allowed_modules.mapped('name')[:10]))
                    if len(self.allowed_modules) > 10:
                        message_parts.append(_('  ... y %d más') % (len(self.allowed_modules) - 10))
                    message_parts.append('')
                    message_parts.append(_('🚫 Módulos bloqueados automáticamente: %d') % len(modules_to_block))
                    message_parts.append('')
                
                # Mostrar información de desbloqueo si hubo
                if menus_reactivated_count > 0:
                    message_parts.append(_('✅ Menús reactivados: %d') % menus_reactivated_count)
                if rules_removed_count > 0:
                    message_parts.append(_('✅ Reglas de bloqueo eliminadas: %d') % rules_removed_count)
                if menus_reactivated_count > 0 or rules_removed_count > 0:
                    message_parts.append('')
            elif self.restriction_mode == 'block_list' and self.blocked_modules:
                message_parts.append(_('🚫 Modo: Lista de Bloqueados'))
                message_parts.append(_('🚫 Módulos bloqueados: %d') % len(self.blocked_modules))
                message_parts.append('  - ' + '\n  - '.join(self.blocked_modules.mapped('name')[:10]))
                if len(self.blocked_modules) > 10:
                    message_parts.append(_('  ... y %d más') % (len(self.blocked_modules) - 10))
                message_parts.append('')
        
        message_parts.append(_('Grupos agregados: %d') % len(groups_to_add))
        if groups_to_add and len(groups_to_add) <= 10:
            message_parts.append('  - ' + '\n  - '.join(groups_to_add.mapped('name')))
        message_parts.append('')
        message_parts.append(_('Grupos removidos: %d') % len(groups_to_remove))
        if groups_to_remove and len(groups_to_remove) <= 10:
            message_parts.append('  - ' + '\n  - '.join(groups_to_remove.mapped('name')))
        message_parts.append('')
        message_parts.append(_('⚠️ IMPORTANTE: El usuario debe cerrar sesión y volver a iniciar sesión para que los cambios surtan efecto completamente.'))
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Permisos Aplicados'),
                'message': '\n'.join(message_parts),
                'type': 'success',
                'sticky': True,
            }
        }
    
    def _get_groups_from_modules(self, modules):
        """Obtener todos los grupos relacionados con los módulos especificados."""
        groups = self.env['res.groups']
        
        for module in modules:
            module_name = module.name or ''
            module_shortdesc = module.shortdesc or module_name
            
            _logger.info('Buscando grupos para módulo: %s', module_name)
            
            # Método 1: Buscar grupos por ir.model.data (xml_id)
            # Los grupos se definen en XML con xml_id como "module_name.group_name"
            # Buscar todos los ir.model.data del módulo que sean de tipo res.groups
            try:
                module_data = self.env['ir.model.data'].search([
                    ('module', '=', module_name),
                    ('model', '=', 'res.groups')
                ])
                
                if module_data:
                    group_ids = [data.res_id for data in module_data if data.res_id]
                    if group_ids:
                        data_groups = self.env['res.groups'].browse(group_ids)
                        groups |= data_groups
                        _logger.info('Módulo %s: %d grupos encontrados por ir.model.data', module_name, len(data_groups))
            except Exception as e:
                _logger.warning('Error buscando grupos por ir.model.data para %s: %s', module_name, str(e))
            
            # Método 2: Buscar grupos a través de ir.model.access (permisos de acceso a modelos)
            # Esto es importante para módulos como subscription_licenses que no tienen grupos personalizados
            # pero sí tienen permisos de acceso configurados en ir.model.access.csv
            try:
                # Buscar reglas de acceso que mencionen el módulo en su nombre
                # Las reglas de acceso suelen tener nombres como "module_name.model_name.group_name"
                access_rules = self.env['ir.model.access'].search([
                    ('name', 'like', module_name)
                ])
                
                # También buscar modelos del módulo directamente
                # Los modelos del módulo subscription_licenses son:
                # license.trm, license.template, license.assignment, license.equipment, 
                # subscription.license.assignment, product.license.type, exchange.rate.monthly
                model_keywords = []
                if 'license' in module_name.lower() or 'subscription' in module_name.lower():
                    model_keywords = ['license', 'trm', 'subscription.license']
                elif 'sale' in module_name.lower():
                    model_keywords = ['sale']
                elif 'purchase' in module_name.lower():
                    model_keywords = ['purchase']
                elif 'stock' in module_name.lower() or 'inventory' in module_name.lower():
                    model_keywords = ['stock', 'inventory']
                
                # Buscar modelos que contengan las palabras clave
                model_names = []
                if model_keywords:
                    all_models = self.env['ir.model'].search([])
                    for model in all_models:
                        if model.model:
                            for keyword in model_keywords:
                                if keyword in model.model.lower():
                                    model_names.append(model.model)
                                    break
                
                # También buscar modelos específicos conocidos de subscription_licenses
                if 'subscription_licenses' in module_name or 'subscription.licenses' in module_name:
                    known_models = [
                        'license.trm', 'license.template', 'license.assignment', 
                        'license.equipment', 'subscription.license.assignment',
                        'product.license.type', 'exchange.rate.monthly',
                        'license.trm.recalculate.wizard', 'license.partner.summary',
                        'license.report.wizard'
                    ]
                    for known_model in known_models:
                        if known_model not in model_names:
                            # Verificar si el modelo existe
                            if self.env['ir.model'].search([('model', '=', known_model)], limit=1):
                                model_names.append(known_model)
                
                # También buscar modelos específicos conocidos de calculadora_costos
                if 'calculadora_costos' in module_name or 'calculadora.costos' in module_name:
                    known_models = [
                        'calculadora.costos', 'calculadora.parametros.financieros',
                        'calculadora.equipo', 'calculadora.renting', 'apu.servicio',
                    ]
                    for known_model in known_models:
                        if known_model not in model_names:
                            # Verificar si el modelo existe
                            if self.env['ir.model'].search([('model', '=', known_model)], limit=1):
                                model_names.append(known_model)
                
                # También buscar modelos específicos conocidos de mesa_ayuda_inventario
                if 'mesa_ayuda_inventario' in module_name or 'mesa.ayuda' in module_name:
                    known_models = [
                        'maintenance.order', 'stock.lot.maintenance',
                        'maintenance.component.change', 'repair.component.change',
                        'customer.own.inventory', 'maintenance.dashboard',
                        'mesa_ayuda.debug.log', 'maintenance.technician.performance',
                        'maintenance.client.summary', 'maintenance.monthly.trend',
                        'maintenance.type.distribution', 'maintenance.weekday.activity',
                        'maintenance.avg.resolution.time', 'maintenance.problematic.equipment',
                        'maintenance.visit.by.technician', 'maintenance.visit.by.type',
                        'maintenance.visit.monthly.trend', 'maintenance.order.technician.signature',
                    ]
                    for known_model in known_models:
                        if known_model not in model_names:
                            # Verificar si el modelo existe
                            if self.env['ir.model'].search([('model', '=', known_model)], limit=1):
                                model_names.append(known_model)
                
                # Buscar reglas de acceso para estos modelos
                if model_names:
                    model_access = self.env['ir.model.access'].search([
                        ('model_id.model', 'in', model_names),
                        ('perm_read', '=', True)  # Solo grupos con permiso de lectura
                    ])
                    access_rules |= model_access
                
                # Obtener grupos únicos de las reglas de acceso
                access_group_ids = access_rules.mapped('group_id').filtered(lambda g: g).ids
                if access_group_ids:
                    access_groups = self.env['res.groups'].browse(access_group_ids)
                    groups |= access_groups
                    _logger.info('Módulo %s: %d grupos encontrados por ir.model.access (modelos: %s)', 
                               module_name, len(access_groups), ', '.join(model_names[:5]))
            except Exception as e:
                _logger.warning('Error buscando grupos por ir.model.access para %s: %s', module_name, str(e))
            
            # Método 3: Buscar grupos por nombre que contenga el nombre del módulo o shortdesc
            # Esto es un fallback para grupos que no están en ir.model.data
            try:
                search_terms = [module_name]
                if module_shortdesc and module_shortdesc != module_name:
                    search_terms.append(module_shortdesc)
                
                domain = []
                for term in search_terms:
                    if term:
                        domain.append('|')
                        domain.append(('name', 'ilike', term))
                        # Buscar también en el nombre completo si existe
                        if hasattr(self.env['res.groups'], 'full_name'):
                            domain.append(('full_name', 'ilike', term))
                
                if domain:
                    # Remover el primer '|' si existe
                    if domain[0] == '|':
                        domain = domain[1:]
                    name_groups = self.env['res.groups'].search(domain)
                    groups |= name_groups
                    if name_groups:
                        _logger.info('Módulo %s: %d grupos encontrados por nombre', module_name, len(name_groups))
            except Exception as e:
                _logger.warning('Error buscando grupos por nombre para %s: %s', module_name, str(e))
        
        # Eliminar duplicados
        groups = groups.sudo()
        _logger.info('Total grupos únicos encontrados: %d', len(groups))
        
        return groups
    
    def _block_module_menus(self, modules):
        """Bloquear acceso a menús relacionados con los módulos bloqueados.
        
        Estrategia:
        1. Buscar todos los menús del módulo a través de ir.model.data
        2. Ocultar los menús globalmente (active=False) para bloquear el acceso
        3. Los menús se reactivarán cuando se desbloquee el módulo
        
        NOTA: Esta es una solución temporal. Idealmente, los menús deberían ocultarse
        solo para usuarios específicos, pero Odoo no soporta esto nativamente.
        La solución definitiva es usar grupos de bloqueo y reglas ir.rule.
        """
        menus_hidden = 0
        
        # VALIDACIÓN CRÍTICA: Asegurar que solo se afecte al usuario específico
        if not self.user_id or not self.user_id.id:
            _logger.warning('⚠️ No se puede bloquear menús: usuario no válido')
            return 0
        
        # Verificar que el usuario existe y es único
        target_user = self.env['res.users'].browse(self.user_id.id)
        if not target_user.exists():
            _logger.error('❌ El usuario con ID %s no existe. No se pueden bloquear menús.', self.user_id.id)
            return 0
        
        if len(target_user) > 1:
            _logger.error('❌ Error crítico: Múltiples usuarios con el mismo ID %s. No se pueden bloquear menús.', self.user_id.id)
            return 0
        
        _logger.info('🔒 BLOQUEANDO ACCESO A MENÚS - Usuario específico: %s (ID: %s)', target_user.name, target_user.id)
        
        for module in modules:
            module_name = module.name or ''
            try:
                # Buscar menús del módulo a través de ir.model.data
                menu_data = self.env['ir.model.data'].search([
                    ('module', '=', module_name),
                    ('model', '=', 'ir.ui.menu')
                ])
                
                if menu_data:
                    menu_ids = [data.res_id for data in menu_data if data.res_id and data.res_id > 0]
                    if menu_ids:
                        menus = self.env['ir.ui.menu'].browse(menu_ids).exists()
                        # Ocultar menús que estén activos
                        active_menus = menus.filtered(lambda m: m.active)
                        if active_menus:
                            active_menus.sudo().write({'active': False})
                            menus_hidden += len(active_menus)
                            _logger.info('Módulo %s: %d menús ocultos', module_name, len(active_menus))
                
                # También buscar menús hijos recursivamente del menú raíz del módulo
                root_menu_xml_ids = [
                    f'{module_name}.menu_licenses_root',
                    f'{module_name}.menu_{module_name}',
                    f'{module_name}.menu_calculadora_costos_root',
                    f'{module_name}.menu_calculadora',
                    f'{module_name}.menu_helpdesk_inventory_root',
                ]
                for xml_id in root_menu_xml_ids:
                    try:
                        root_menu = self.env.ref(xml_id, raise_if_not_found=False)
                        if root_menu and root_menu.active:
                            # Buscar todos los menús hijos recursivamente
                            def get_all_children(menu):
                                children = self.env['ir.ui.menu'].search([('parent_id', '=', menu.id)])
                                all_children = children
                                for child in children:
                                    all_children |= get_all_children(child)
                                return all_children
                            
                            children = get_all_children(root_menu)
                            all_menus_to_hide = root_menu | children
                            active_menus_to_hide = all_menus_to_hide.filtered(lambda m: m.active)
                            if active_menus_to_hide:
                                active_menus_to_hide.sudo().write({'active': False})
                                menus_hidden += len(active_menus_to_hide)
                                _logger.info('Módulo %s: Menú raíz y %d menús hijos ocultos', module_name, len(active_menus_to_hide))
                    except Exception as e:
                        _logger.warning('Error buscando menú raíz %s: %s', xml_id, str(e))
                        
            except Exception as e:
                _logger.warning('Error buscando menús para bloquear en %s: %s', module_name, str(e))
        
        _logger.info('✅ Total menús ocultos: %d para usuario %s (ID: %s)', menus_hidden, target_user.name, target_user.id)
        return menus_hidden
    
    def _create_restrictive_ir_rules(self, modules):
        """Crear reglas de dominio (ir.rule) para bloquear acceso a modelos del módulo SOLO para el usuario específico.
        
        IMPORTANTE: Las reglas ir.rule bloquean el acceso a nivel de base de datos,
        por lo que incluso con links directos, el usuario NO podrá acceder a los registros.
        
        Estrategia: 
        1. Crear un grupo específico "Blocked: [Module] - User [ID]" para identificar usuarios bloqueados
        2. Asignar este grupo SOLO al usuario bloqueado
        3. Crear reglas ir.rule que bloqueen el acceso SOLO para usuarios que tienen este grupo
        4. Los demás usuarios (sin el grupo) NO se verán afectados
        
        Retorna:
            tuple: (rules_created, block_groups) donde:
                - rules_created: número de reglas creadas
                - block_groups: grupos de bloqueo creados (para agregarlos al usuario)
        """
        rules_created = 0
        block_groups = self.env['res.groups']
        
        # VALIDACIÓN CRÍTICA: Asegurar que solo se afecte al usuario específico
        if not self.user_id:
            return rules_created, block_groups
        
        if not self.user_id.id:
            _logger.error('❌ El usuario seleccionado no tiene un ID válido. No se pueden crear reglas de bloqueo.')
            return rules_created, block_groups
        
        # Verificar que el usuario existe y es único
        target_user = self.env['res.users'].browse(self.user_id.id)
        if not target_user.exists():
            _logger.error('❌ El usuario con ID %s no existe en la base de datos. No se pueden crear reglas de bloqueo.', self.user_id.id)
            return rules_created, block_groups
        
        if len(target_user) > 1:
            _logger.error('❌ Error crítico: Se encontraron múltiples usuarios con el mismo ID %s. No se pueden crear reglas de bloqueo.', self.user_id.id)
            return rules_created, block_groups
        
        _logger.info('🔒 CREANDO REGLAS DE BLOQUEO - Usuario específico: %s (ID: %s)', target_user.name, target_user.id)
        
        for module in modules:
            module_name = module.name or ''
            
            # Obtener modelos del módulo usando múltiples métodos
            model_names = []
            
            # Método 1: Buscar modelos conocidos para módulos específicos
            if 'subscription_licenses' in module_name or 'subscription.licenses' in module_name:
                known_models = [
                    'license.trm', 'license.template', 'license.assignment', 
                    'license.equipment', 'subscription.license.assignment',
                    'product.license.type', 'exchange.rate.monthly',
                ]
                for model_name in known_models:
                    if self.env['ir.model'].search([('model', '=', model_name)], limit=1):
                        model_names.append(model_name)
            elif 'calculadora_costos' in module_name or 'calculadora.costos' in module_name:
                known_models = [
                    'calculadora.costos', 'calculadora.parametros.financieros',
                    'calculadora.equipo', 'calculadora.renting', 'apu.servicio',
                ]
                for model_name in known_models:
                    if self.env['ir.model'].search([('model', '=', model_name)], limit=1):
                        model_names.append(model_name)
            elif 'mesa_ayuda_inventario' in module_name or 'mesa.ayuda' in module_name:
                known_models = [
                    'maintenance.order', 'stock.lot.maintenance',
                    'maintenance.component.change', 'repair.component.change',
                    'customer.own.inventory', 'maintenance.dashboard',
                    'mesa_ayuda.debug.log', 'maintenance.technician.performance',
                    'maintenance.client.summary', 'maintenance.monthly.trend',
                    'maintenance.type.distribution', 'maintenance.weekday.activity',
                    'maintenance.avg.resolution.time', 'maintenance.problematic.equipment',
                    'maintenance.visit.by.technician', 'maintenance.visit.by.type',
                    'maintenance.visit.monthly.trend', 'maintenance.order.technician.signature',
                ]
                for model_name in known_models:
                    if self.env['ir.model'].search([('model', '=', model_name)], limit=1):
                        model_names.append(model_name)
            
            # Método 2: Buscar modelos a través de ir.model.data (más confiable para módulos personalizados)
            try:
                # Buscar todos los ir.model.data del módulo que sean de tipo ir.model
                model_data = self.env['ir.model.data'].search([
                    ('module', '=', module_name),
                    ('model', '=', 'ir.model')
                ])
                
                if model_data:
                    # Obtener los modelos reales desde ir.model
                    for data in model_data:
                        if data.res_id:
                            model = self.env['ir.model'].browse(data.res_id)
                            if model.exists() and model.model and model.model not in model_names:
                                model_names.append(model.model)
                    _logger.info('Módulo %s: %d modelos encontrados por ir.model.data', module_name, len(model_data))
            except Exception as e:
                _logger.warning('Error buscando modelos por ir.model.data para %s: %s', module_name, str(e))
            
            # Método 3: Buscar modelos a través de ir.model.access (reglas de acceso del módulo)
            try:
                # Buscar reglas de acceso que tengan el nombre del módulo
                access_rules = self.env['ir.model.access'].search([
                    ('name', 'like', module_name)
                ])
                
                if access_rules:
                    # Obtener los modelos únicos de las reglas de acceso
                    access_models = access_rules.mapped('model_id.model')
                    for model_name in access_models:
                        if model_name and model_name not in model_names:
                            # Verificar que el modelo existe
                            if self.env['ir.model'].search([('model', '=', model_name)], limit=1):
                                model_names.append(model_name)
                    _logger.info('Módulo %s: %d modelos encontrados por ir.model.access', module_name, len(access_models))
            except Exception as e:
                _logger.warning('Error buscando modelos por ir.model.access para %s: %s', module_name, str(e))
            
            # Método 4: Buscar modelos por palabras clave (fallback)
            if not model_names:
                try:
                    all_models = self.env['ir.model'].search([])
                    module_words = module_name.replace('_', ' ').split()
                    for model in all_models:
                        if model.model and model.model not in model_names:
                            for word in module_words:
                                if word and len(word) > 3 and word.lower() in model.model.lower():
                                    model_names.append(model.model)
                                    break
                    if model_names:
                        _logger.info('Módulo %s: %d modelos encontrados por palabras clave', module_name, len(model_names))
                except Exception as e:
                    _logger.warning('Error buscando modelos por palabras clave para %s: %s', module_name, str(e))
            
            # Eliminar duplicados
            model_names = list(set(model_names))
            _logger.info('Módulo %s: Total %d modelos únicos encontrados para bloquear', module_name, len(model_names))
            
            # Crear un grupo específico para identificar usuarios bloqueados en este módulo
            # Usar target_user para asegurar que solo se afecte al usuario específico
            block_group_name = f'Blocked: {module_name} - User {target_user.id}'
            block_group = self.env['res.groups'].search([
                ('name', '=', block_group_name)
            ], limit=1)
            
            if not block_group:
                # Crear el grupo de bloqueo
                try:
                    # Buscar categoría oculta para grupos del sistema
                    hidden_category = self.env.ref('base.module_category_hidden', raise_if_not_found=False)
                    block_group = self.env['res.groups'].sudo().create({
                        'name': block_group_name,
                        'category_id': hidden_category.id if hidden_category else False,
                        'comment': f'Grupo para bloquear acceso al módulo {module_name} para el usuario {target_user.name} (ID: {target_user.id})',
                    })
                    _logger.info('✅ Grupo de bloqueo creado: %s (ID: %s) para usuario %s (ID: %s)', 
                               block_group_name, block_group.id, target_user.name, target_user.id)
                except Exception as e:
                    _logger.warning('❌ Error creando grupo de bloqueo para usuario %s (ID: %s): %s', 
                                  target_user.name, target_user.id, str(e))
                    block_group = False
            
            # Agregar el grupo de bloqueo a la lista para que se asigne al usuario específico
            if block_group:
                block_groups |= block_group
                _logger.info('✅ Grupo de bloqueo preparado para asignar al usuario %s (ID: %s): %s (ID: %s)', 
                           target_user.name, target_user.id, block_group.name, block_group.id)
            else:
                _logger.error('❌ No se pudo crear el grupo de bloqueo para el módulo %s y usuario %s (ID: %s)', 
                            module_name, target_user.name, target_user.id)
            
            # Crear reglas de dominio que bloqueen el acceso SOLO para usuarios con el grupo de bloqueo
            for model_name in model_names:
                try:
                    model = self.env['ir.model'].search([('model', '=', model_name)], limit=1)
                    if not model:
                        continue
                    
                    # Buscar si ya existe una regla de bloqueo para este módulo y modelo
                    # Usar target_user.id para asegurar que solo se afecte al usuario específico
                    rule_name = f'Block {module_name} - {model_name} - User {target_user.id}'
                    existing_rule = self.env['ir.rule'].search([
                        ('name', '=', rule_name),
                        ('model_id', '=', model.id),
                    ], limit=1)
                    
                    if not existing_rule and block_group:
                        # Crear regla de dominio que bloquea el acceso SOLO para usuarios con el grupo de bloqueo
                        # Esta regla se aplicará SOLO al usuario bloqueado, no a los demás
                        try:
                            self.env['ir.rule'].sudo().create({
                                'name': rule_name,
                                'model_id': model.id,
                                'domain_force': '[(0, "=", 1)]',  # Dominio que siempre es falso = sin acceso
                                'global': False,  # No global
                                'groups': [(6, 0, [block_group.id])],  # SOLO se aplica a usuarios con este grupo
                                'active': True,
                            })
                            rules_created += 1
                            _logger.info('✅ Regla restrictiva creada para %s.%s (usuario: %s, ID: %s). '
                                       'NOTA: Esta regla bloquea el acceso SOLO para el usuario %s (ID: %s), '
                                       'incluso con links directos, porque se aplica a nivel de base de datos. '
                                       'Los demás usuarios NO se verán afectados.', 
                                       module_name, model_name, target_user.name, target_user.id, 
                                       target_user.name, target_user.id)
                        except Exception as create_error:
                            _logger.warning('Error creando regla ir.rule: %s', str(create_error))
                except Exception as e:
                    _logger.warning('Error procesando regla ir.rule para %s.%s: %s', module_name, model_name, str(e))
        
        return rules_created, block_groups
    
    def _unblock_module_menus(self, modules):
        """Reactivar menús relacionados con los módulos que se están desbloqueando.
        
        NOTA: Excluye el menú 'Información general' (stock.stock_picking_type_menu) 
        que debe permanecer oculto según inventory_dashboard_simple.
        """
        menus_reactivated = 0
        menus_to_reactivate = self.env['ir.ui.menu']
        
        # Lista de menús que NO deben reactivarse nunca (independientemente del módulo)
        menus_to_never_reactivate = [
            'stock.stock_picking_type_menu',  # Menú "Información general" - debe permanecer oculto
        ]
        
        for module in modules:
            module_name = module.name or ''
            try:
                # Buscar menús del módulo
                menu_data = self.env['ir.model.data'].search([
                    ('module', '=', module_name),
                    ('model', '=', 'ir.ui.menu')
                ])
                
                if menu_data:
                    menu_ids = [data.res_id for data in menu_data if data.res_id and data.res_id > 0]
                    if menu_ids:
                        menus = self.env['ir.ui.menu'].browse(menu_ids).exists()
                        # Filtrar menús que NO deben reactivarse
                        for menu in menus:
                            menu_xml_id = menu.get_external_id().get(menu.id, '')
                            if menu_xml_id not in menus_to_never_reactivate:
                                menus_to_reactivate |= menu
                            else:
                                _logger.info('Menú excluido de reactivación: %s (debe permanecer oculto)', menu_xml_id)
                        _logger.info('Módulo %s: %d menús encontrados para reactivar (después de filtrar)', module_name, len(menus_to_reactivate))
                
                # También buscar menús hijos recursivamente del menú raíz del módulo
                root_menu_xml_ids = [
                    f'{module_name}.menu_licenses_root',
                    f'{module_name}.menu_{module_name}',
                    f'{module_name}.menu_calculadora_costos_root',
                    f'{module_name}.menu_calculadora',
                    f'{module_name}.menu_helpdesk_inventory_root',
                ]
                for xml_id in root_menu_xml_ids:
                    try:
                        root_menu = self.env.ref(xml_id, raise_if_not_found=False)
                        if root_menu:
                            # Buscar todos los menús hijos recursivamente
                            def get_all_children(menu):
                                children = self.env['ir.ui.menu'].search([('parent_id', '=', menu.id)])
                                all_children = children
                                for child in children:
                                    all_children |= get_all_children(child)
                                return all_children
                            
                            children = get_all_children(root_menu)
                            # Filtrar menús que NO deben reactivarse (incluyendo hijos)
                            all_menus_to_check = root_menu | children
                            for menu in all_menus_to_check:
                                menu_xml_id = menu.get_external_id().get(menu.id, '')
                                if menu_xml_id not in menus_to_never_reactivate:
                                    menus_to_reactivate |= menu
                                else:
                                    _logger.info('Menú excluido de reactivación (hijo): %s (debe permanecer oculto)', menu_xml_id)
                            _logger.info('Módulo %s: Menú raíz y %d menús hijos encontrados para reactivar (después de filtrar)', module_name, len(menus_to_reactivate))
                    except Exception:
                        pass
                        
            except Exception as e:
                _logger.warning('Error buscando menús para reactivar en %s: %s', module_name, str(e))
        
        # NO reactivar menús globalmente - nunca los ocultamos globalmente
        # El desbloqueo se hace mediante remoción de grupos de bloqueo y reglas ir.rule
        # que se eliminan en _remove_blocking_ir_rules
        
        _logger.info('✅ DESBLOQUEO DE MENÚS COMPLETADO - Usuario: %s (ID: %s)', target_user.name, target_user.id)
        _logger.info('ℹ️ Los menús ya estaban activos. El acceso se restaura mediante grupos de permisos.')
        
        return 0  # Retornar 0 porque no reactivamos menús globalmente
    
    def _remove_blocking_ir_rules(self, modules):
        """Eliminar reglas ir.rule de bloqueo para los módulos que se están desbloqueando."""
        rules_removed = 0
        block_groups_to_remove = self.env['res.groups']
        
        # VALIDACIÓN CRÍTICA: Asegurar que solo se afecte al usuario específico
        if not self.user_id:
            return rules_removed, block_groups_to_remove
        
        if not self.user_id.id:
            _logger.error('❌ El usuario seleccionado no tiene un ID válido. No se pueden eliminar reglas de bloqueo.')
            return rules_removed, block_groups_to_remove
        
        # Verificar que el usuario existe y es único
        target_user = self.env['res.users'].browse(self.user_id.id)
        if not target_user.exists():
            _logger.error('❌ El usuario con ID %s no existe en la base de datos. No se pueden eliminar reglas de bloqueo.', self.user_id.id)
            return rules_removed, block_groups_to_remove
        
        if len(target_user) > 1:
            _logger.error('❌ Error crítico: Se encontraron múltiples usuarios con el mismo ID %s. No se pueden eliminar reglas de bloqueo.', self.user_id.id)
            return rules_removed, block_groups_to_remove
        
        _logger.info('🔓 ELIMINANDO REGLAS DE BLOQUEO - Usuario específico: %s (ID: %s)', target_user.name, target_user.id)
        
        for module in modules:
            module_name = module.name or ''
            
            # Buscar el grupo de bloqueo específico para este usuario y módulo
            # Usar target_user.id para asegurar que solo se afecte al usuario específico
            block_group_name = f'Blocked: {module_name} - User {target_user.id}'
            block_group = self.env['res.groups'].search([
                ('name', '=', block_group_name)
            ], limit=1)
            
            if block_group:
                block_groups_to_remove |= block_group
                
                # Buscar y eliminar todas las reglas ir.rule asociadas a este grupo
                blocking_rules = self.env['ir.rule'].search([
                    ('groups', 'in', [block_group.id])
                ])
                
                if blocking_rules:
                    try:
                        blocking_rules.sudo().unlink()
                        rules_removed += len(blocking_rules)
                        _logger.info('✅ Eliminadas %d reglas de bloqueo para el módulo %s (usuario: %s, ID: %s)', 
                                   len(blocking_rules), module_name, target_user.name, target_user.id)
                    except Exception as e:
                        _logger.warning('❌ Error eliminando reglas ir.rule para usuario %s (ID: %s): %s', 
                                      target_user.name, target_user.id, str(e))
                
                # También buscar reglas por nombre (por si acaso)
                rule_pattern = f'Block {module_name} -'
                rules_by_name = self.env['ir.rule'].search([
                    ('name', 'ilike', rule_pattern),
                    ('groups', 'in', [block_group.id])
                ])
                if rules_by_name:
                    try:
                        rules_by_name.sudo().unlink()
                        rules_removed += len(rules_by_name)
                        _logger.info('✅ Eliminadas %d reglas adicionales por nombre para el módulo %s (usuario: %s, ID: %s)', 
                                   len(rules_by_name), module_name, target_user.name, target_user.id)
                    except Exception as e:
                        _logger.warning('❌ Error eliminando reglas adicionales para usuario %s (ID: %s): %s', 
                                      target_user.name, target_user.id, str(e))
        
        _logger.info('✅ REGLAS DE BLOQUEO ELIMINADAS - Usuario: %s (ID: %s) - Reglas eliminadas: %d',
                   target_user.name, target_user.id, rules_removed)
        
        return rules_removed, block_groups_to_remove
    
    def _get_role_groups(self):
        """Obtener grupos del rol."""
        if not self.role_ids:
            return self.env['res.groups'], self.env['res.groups']
        
        # Agregar grupos de todos los roles seleccionados
        groups_to_add = self.env['res.groups']
        groups_to_remove = self.env['res.groups']
        
        for role in self.role_ids:
            groups_to_add |= role.group_ids
            groups_to_remove |= role.excluded_group_ids
        
        return groups_to_add, groups_to_remove
    
    def _apply_permissions_from_lines(self):
        """Aplicar permisos desde las líneas de módulos y grupos."""
        # Primero, eliminar cualquier línea inválida que pueda haber quedado
        invalid_module_lines = self.module_line_ids.filtered(
            lambda l: not l.module_id or not hasattr(l, 'module_id') or not l.module_id.id
        )
        invalid_group_lines = self.group_line_ids.filtered(
            lambda l: not l.group_id or not hasattr(l, 'group_id') or not l.group_id.id
        )
        
        if invalid_module_lines:
            try:
                invalid_module_lines.sudo().unlink()
            except Exception:
                pass  # Ignorar errores al eliminar
        
        if invalid_group_lines:
            try:
                invalid_group_lines.sudo().unlink()
            except Exception:
                pass  # Ignorar errores al eliminar
        
        groups_to_add = self.env['res.groups']
        groups_to_remove = self.env['res.groups']
        
        # Procesar líneas de grupos (solo las que tienen group_id válido y existe)
        valid_group_lines = self.group_line_ids.filtered(
            lambda l: l.group_id and hasattr(l.group_id, 'id') and l.group_id.id
        )
        for line in valid_group_lines:
            try:
                if line.is_selected and line.group_id and line.group_id.id:
                    groups_to_add |= line.group_id
                elif line.is_excluded and line.group_id and line.group_id.id:
                    groups_to_remove |= line.group_id
            except Exception as e:
                _logger.warning('Error procesando línea de grupo: %s', str(e))
                continue
        
        # Procesar líneas de módulos (solo las que tienen module_id válido y existe)
        valid_module_lines = self.module_line_ids.filtered(
            lambda l: l.module_id and hasattr(l.module_id, 'id') and l.module_id.id
        )
        allowed_modules = self.env['ir.module.module']
        blocked_modules = self.env['ir.module.module']
        
        for line in valid_module_lines:
            try:
                if line.is_allowed and line.module_id and line.module_id.id:
                    allowed_modules |= line.module_id
                elif line.is_blocked and line.module_id and line.module_id.id:
                    blocked_modules |= line.module_id
            except Exception as e:
                _logger.warning('Error procesando línea de módulo: %s', str(e))
                continue
        
        if allowed_modules:
            # Agregar grupos de módulos permitidos
            module_groups = self._get_groups_from_modules(allowed_modules)
            groups_to_add |= module_groups
        
        if blocked_modules:
            # Remover grupos de módulos bloqueados
            blocked_groups = self._get_groups_from_modules(blocked_modules)
            groups_to_remove |= blocked_groups
        
        # Obtener grupos actuales del usuario
        current_groups = self.user_id.groups_id
        
        # Calcular grupos finales
        final_groups = current_groups | groups_to_add
        final_groups = final_groups - groups_to_remove
        
        # Proteger grupos esenciales
        essential_groups = self.env['res.groups'].search([
            '|', '|',
            ('name', '=', 'Internal User'),
            ('name', '=', 'Portal'),
            ('name', '=', 'Public'),
        ])
        
        groups_to_remove = groups_to_remove - essential_groups
        
        # Asegurar Internal User
        if not (final_groups & essential_groups.filtered(lambda g: 'Internal User' in g.name)):
            internal_user = self.env['res.groups'].search([('name', '=', 'Internal User')], limit=1)
            if internal_user:
                final_groups |= internal_user
        
        # Aplicar cambios
        self.user_id.sudo().write({
            'groups_id': [(6, 0, final_groups.ids)]
        })
        
        self.user_id.invalidate_recordset(['groups_id'])
        
        # Mensaje de confirmación
        message_parts = []
        message_parts.append(_('Permisos aplicados correctamente al usuario %s.') % self.user_id.name)
        message_parts.append('')
        message_parts.append(_('Grupos agregados: %d') % len(groups_to_add))
        message_parts.append(_('Grupos removidos: %d') % len(groups_to_remove))
        message_parts.append('')
        message_parts.append(_('⚠️ IMPORTANTE: El usuario debe cerrar sesión y volver a iniciar sesión.'))
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Permisos Aplicados'),
                'message': '\n'.join(message_parts),
                'type': 'success',
                'sticky': True,
            }
        }
    
    def _load_modules_and_groups(self):
        """Cargar lista de módulos y grupos."""
        # Cargar módulos instalados
        installed_modules = self.env['ir.module.module'].search([
            ('state', '=', 'installed')
        ], order='shortdesc')
        
        # Obtener módulos actuales del usuario
        user_modules = self._get_current_user_modules()
        
        # Crear líneas de módulos usando la sintaxis de Odoo [(5, 0, 0), (0, 0, {...})]
        module_lines = [(5, 0, 0)]  # Eliminar todas las líneas existentes
        for module in installed_modules:
            is_allowed = module in user_modules
            module_lines.append((0, 0, {
                'module_id': module.id,
                'is_allowed': is_allowed,
                'is_blocked': False,
            }))
        
        self.module_line_ids = module_lines
        
        # Cargar grupos disponibles
        all_groups = self.env['res.groups'].search([], order='name')
        
        # Obtener grupos actuales del usuario
        user_groups = self.user_id.groups_id
        
        # Crear líneas de grupos usando la sintaxis de Odoo [(5, 0, 0), (0, 0, {...})]
        group_lines = [(5, 0, 0)]  # Eliminar todas las líneas existentes
        for group in all_groups:
            is_selected = group in user_groups
            group_lines.append((0, 0, {
                'group_id': group.id,
                'is_selected': is_selected,
                'is_excluded': False,
            }))
        
        self.group_line_ids = group_lines
    
    def _get_current_user_modules(self):
        """Obtener módulos a los que el usuario tiene acceso actualmente."""
        if not self.user_id:
            return self.env['ir.module.module']
        
        user_groups = self.user_id.groups_id
        group_data = self.env['ir.model.data'].search([
            ('model', '=', 'res.groups'),
            ('res_id', 'in', user_groups.ids)
        ])
        
        module_names = list(set(group_data.mapped('module')))
        if module_names:
            return self.env['ir.module.module'].search([
                ('name', 'in', module_names),
                ('state', '=', 'installed')
            ])
        return self.env['ir.module.module']
    
    def action_load_modules_groups(self):
        """Cargar módulos y grupos disponibles."""
        self.ensure_one()
        if not self.user_id:
            raise UserError(_('Debe seleccionar un usuario primero.'))
        
        self._load_modules_and_groups()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Lista Cargada'),
                'message': _('Módulos y grupos cargados. Puede activar/desactivar según necesite.'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_diagnose_user_duplicates(self):
        """Herramienta de diagnóstico para detectar usuarios duplicados o con relaciones compartidas."""
        self.ensure_one()
        
        if not self.user_id:
            raise UserError(_('Debe seleccionar un usuario para diagnosticar.'))
        
        target_user = self.env['res.users'].browse(self.user_id.id)
        if not target_user.exists():
            raise UserError(_('El usuario con ID %s no existe.') % self.user_id.id)
        
        diagnostic_info = []
        diagnostic_info.append('=' * 80)
        diagnostic_info.append(f'DIAGNÓSTICO DE USUARIO - ID: {target_user.id}')
        diagnostic_info.append('=' * 80)
        diagnostic_info.append(f'Nombre: {target_user.name}')
        diagnostic_info.append(f'Login: {target_user.login}')
        diagnostic_info.append(f'Partner ID: {target_user.partner_id.id if target_user.partner_id else "N/A"}')
        diagnostic_info.append(f'Partner Name: {target_user.partner_id.name if target_user.partner_id else "N/A"}')
        diagnostic_info.append(f'Activo: {target_user.active}')
        diagnostic_info.append(f'Total Grupos: {len(target_user.groups_id)}')
        diagnostic_info.append('')
        
        # Buscar usuarios con el mismo partner_id
        if target_user.partner_id:
            users_same_partner = self.env['res.users'].search([
                ('partner_id', '=', target_user.partner_id.id),
                ('id', '!=', target_user.id)
            ])
            if users_same_partner:
                diagnostic_info.append('❌ PROBLEMA DETECTADO: Usuarios con el mismo partner_id:')
                for u in users_same_partner:
                    diagnostic_info.append(f'  - Usuario: {u.name} (ID: {u.id}, Login: {u.login})')
                diagnostic_info.append('')
            else:
                diagnostic_info.append('✅ OK: No hay otros usuarios con el mismo partner_id')
                diagnostic_info.append('')
        
        # Buscar usuarios con el mismo login
        if target_user.login:
            users_same_login = self.env['res.users'].search([
                ('login', '=', target_user.login),
                ('id', '!=', target_user.id)
            ])
            if users_same_login:
                diagnostic_info.append('❌ PROBLEMA DETECTADO: Usuarios con el mismo login:')
                for u in users_same_login:
                    diagnostic_info.append(f'  - Usuario: {u.name} (ID: {u.id}, Partner ID: {u.partner_id.id if u.partner_id else "N/A"})')
                diagnostic_info.append('')
            else:
                diagnostic_info.append('✅ OK: No hay otros usuarios con el mismo login')
                diagnostic_info.append('')
        
        # Buscar usuarios con muchos grupos en común (posibles duplicados)
        target_groups = target_user.groups_id
        if len(target_groups) > 0:
            all_users = self.env['res.users'].search([
                ('id', '!=', target_user.id),
                ('active', 'in', [True, False])
            ])
            
            similar_users = []
            for other_user in all_users:
                other_groups = other_user.groups_id
                common_groups = target_groups & other_groups
                if len(target_groups) > 0:
                    similarity = len(common_groups) / len(target_groups)
                    if similarity > 0.7 and len(common_groups) > 3:
                        similar_users.append({
                            'user': other_user,
                            'common_groups': len(common_groups),
                            'similarity': similarity
                        })
            
            if similar_users:
                diagnostic_info.append('⚠️ ADVERTENCIA: Usuarios con muchos grupos en común (posibles duplicados):')
                for info in sorted(similar_users, key=lambda x: x['similarity'], reverse=True)[:5]:
                    u = info['user']
                    diagnostic_info.append(f'  - Usuario: {u.name} (ID: {u.id}, Login: {u.login})')
                    diagnostic_info.append(f'    Grupos en común: {info["common_groups"]} ({int(info["similarity"] * 100)}% similitud)')
                    diagnostic_info.append(f'    Partner ID: {u.partner_id.id if u.partner_id else "N/A"}')
                diagnostic_info.append('')
            else:
                diagnostic_info.append('✅ OK: No se encontraron usuarios con muchos grupos en común')
                diagnostic_info.append('')
        
        # Mostrar grupos actuales del usuario
        diagnostic_info.append('Grupos actuales del usuario:')
        for group in target_user.groups_id.sorted('name'):
            diagnostic_info.append(f'  - {group.name} (ID: {group.id})')
        diagnostic_info.append('')
        diagnostic_info.append('=' * 80)
        
        # Mostrar en notificación
        message = '\n'.join(diagnostic_info)
        _logger.info(message)
        
        # Si hay usuarios con 100% de similitud, mostrar advertencia adicional
        if '100% similitud' in message:
            diagnostic_info.append('')
            diagnostic_info.append('⚠️ PROBLEMA CRÍTICO DETECTADO:')
            diagnostic_info.append('Este usuario tiene exactamente los mismos grupos que otros usuarios.')
            diagnostic_info.append('Esto causa que los cambios de permisos se repliquen a todos.')
            diagnostic_info.append('')
            diagnostic_info.append('RECOMENDACIÓN:')
            diagnostic_info.append('1. Revisa cada usuario y ajusta sus permisos según su rol')
            diagnostic_info.append('2. Usa el gestor de permisos para cada usuario individualmente')
            diagnostic_info.append('3. Asegúrate de que cada usuario tenga solo los grupos necesarios para su trabajo')
            diagnostic_info.append('')
            diagnostic_info.append('=' * 80)
            message = '\n'.join(diagnostic_info)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Diagnóstico de Usuario - ID: %s') % target_user.id,
                'message': message,
                'type': 'warning' if 'PROBLEMA DETECTADO' in message or 'ADVERTENCIA' in message or '100% similitud' in message else 'info',
                'sticky': True,
            }
        }
    
    def action_copy_permissions(self):
        """Copiar permisos de otro usuario."""
        self.ensure_one()
        
        if not self.copy_from_user_id:
            raise UserError(_('Debe seleccionar un usuario del cual copiar permisos.'))
        
        if not self.user_id:
            raise UserError(_('Debe seleccionar un usuario destino.'))
        
        # VALIDACIÓN: Verificar que no haya duplicados antes de copiar
        target_user = self.env['res.users'].browse(self.user_id.id)
        source_user = self.env['res.users'].browse(self.copy_from_user_id.id)
        
        # Verificar partner_id
        if target_user.partner_id and source_user.partner_id:
            if target_user.partner_id.id == source_user.partner_id.id:
                raise UserError(_(
                    'Error: Los usuarios "%s" (ID: %s) y "%s" (ID: %s) comparten el mismo contacto (partner_id: %s).\n\n'
                    'No se pueden copiar permisos entre usuarios con el mismo contacto.\n'
                    'Por favor, asigne contactos diferentes a cada usuario.'
                ) % (target_user.name, target_user.id, source_user.name, source_user.id,
                     target_user.partner_id.id))
        
        # Verificar login
        if target_user.login and source_user.login:
            if target_user.login == source_user.login:
                raise UserError(_(
                    'Error: Los usuarios "%s" (ID: %s) y "%s" (ID: %s) comparten el mismo login "%s".\n\n'
                    'No se pueden copiar permisos entre usuarios con el mismo login.\n'
                    'Por favor, asigne logins diferentes a cada usuario.'
                ) % (target_user.name, target_user.id, source_user.name, source_user.id,
                     target_user.login))
        
        # Copiar grupos del usuario origen directamente al usuario destino
        source_groups = source_user.groups_id
        
        # Aplicar los grupos directamente al usuario usando el ID específico
        target_user.sudo().write({
            'groups_id': [(6, 0, source_groups.ids)]
        })
        
        # Invalidar cache para que se reflejen los cambios
        target_user.invalidate_recordset(['groups_id'])
        
        # Obtener módulos del usuario origen para mostrarlos en allowed_modules
        source_user_groups = self.copy_from_user_id.groups_id
        group_data = self.env['ir.model.data'].search([
            ('model', '=', 'res.groups'),
            ('res_id', 'in', source_user_groups.ids)
        ])
        module_names = list(set(group_data.mapped('module')))
        source_modules = self.env['ir.module.module']
        if module_names:
            source_modules = self.env['ir.module.module'].search([
                ('name', 'in', module_names),
                ('state', '=', 'installed')
            ])
        
        # Si se está usando la vista original (con allowed_modules), actualizar los campos
        # Esto permite ver qué módulos tiene el usuario origen
        self.allowed_modules = [(6, 0, source_modules.ids)]
        self.apply_restriction = True
        self.restriction_mode = 'allow_list'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Permisos Copiados'),
                'message': _('✅ Los permisos de %s se han copiado a %s.\n\nLos grupos se han aplicado directamente. Los módulos permitidos se han cargado en la pestaña "Módulos Permitidos" para su revisión.') % (
                    self.copy_from_user_id.name, self.user_id.name
                ),
                'type': 'success',
                'sticky': True,
            }
        }
    
    def _get_user_modules(self, user):
        """Obtener módulos de un usuario."""
        user_groups = user.groups_id
        group_data = self.env['ir.model.data'].search([
            ('model', '=', 'res.groups'),
            ('res_id', 'in', user_groups.ids)
        ])
        
        module_names = list(set(group_data.mapped('module')))
        if module_names:
            return self.env['ir.module.module'].search([
                ('name', 'in', module_names),
                ('state', '=', 'installed')
            ])
        return self.env['ir.module.module']
    
    def action_view_current_groups(self):
        """Ver los grupos actuales del usuario."""
        self.ensure_one()
        
        if not self.user_id:
            raise UserError(_('Debe seleccionar un usuario.'))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Grupos Actuales - %s') % self.user_id.name,
            'res_model': 'res.groups',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.user_id.groups_id.ids)],
            'target': 'new',
        }
    
