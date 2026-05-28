# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class MesaAyudaActaOtherOperationsWizard(models.TransientModel):
    _name = 'mesa.ayuda.acta.other.operations.wizard'
    _description = 'Otras operaciones (acta de visita)'

    helpdesk_ticket_id = fields.Many2one('helpdesk.ticket', string='Ticket', required=True, readonly=True)
    info = fields.Html(string='Información', readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        tid = self.env.context.get('default_helpdesk_ticket_id') or self.env.context.get('active_id')
        if tid and 'helpdesk_ticket_id' in fields_list:
            res['helpdesk_ticket_id'] = tid
        if 'info' in fields_list:
            res['info'] = (
                '<p>%s</p><ul><li>%s</li><li>%s</li></ul>'
                % (
                    _('Este espacio queda listo para acciones adicionales que defina el área.'),
                    _('Ejemplos: retiros, altas, traslados de licencias, solicitudes especiales, etc.'),
                    _('Indique al administrador Odoo qué botones o formularios desea aquí.'),
                )
            )
        return res
