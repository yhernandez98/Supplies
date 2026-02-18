# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class ResUsers(models.Model):
    """Extender res.users para agregar método de gestor de permisos."""
    
    _inherit = 'res.users'

    def action_open_permission_manager(self):
        """Abrir el gestor de permisos para este usuario."""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Gestor de Permisos - %s') % self.name,
            'res_model': 'permission.manager',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_user_id': self.id,
            },
        }
