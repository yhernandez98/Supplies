# -*- coding: utf-8 -*-

from odoo import fields, models, _
from odoo.exceptions import UserError


class MesaServiceSolicitudesWizard(models.TransientModel):
    _name = 'mesa.service.solicitudes.wizard'
    _description = 'Solicitudes (órdenes de servicio)'

    request_type = fields.Selection(
        [
            ('retiro_usuario_equipo', 'Retiro de Usuario/Equipo'),
        ],
        string='Seleccione',
        required=True,
        help='Seleccione el tipo de solicitud que desea registrar.',
    )

    def action_confirm(self):
        self.ensure_one()
        if not self.request_type:
            raise UserError(_('Debe seleccionar un tipo de solicitud.'))

        if self.request_type == 'retiro_usuario_equipo':
            return {
                'name': _('Retiro de Usuario/Equipo'),
                'type': 'ir.actions.act_window',
                'res_model': 'mesa.service.retiro.usuario.equipo.wizard',
                'view_mode': 'form',
                'view_id': self.env.ref(
                    'mesa_ayuda_inventario.view_mesa_service_retiro_usuario_equipo_wizard_form'
                ).id,
                'target': 'new',
                'context': {
                    'default_origin_model': self.env.context.get('active_model'),
                    'default_origin_id': self.env.context.get('active_id'),
                },
            }

        # Fallback genérico (por si en el futuro se añaden más tipos y aún no tienen flujo)
        return {'type': 'ir.actions.act_window_close'}
