# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class LicenseEquipmentDeleteWarningWizard(models.TransientModel):
    _name = 'license.equipment.delete.warning.wizard'
    _description = 'Advertencia al eliminar equipo o usuario asignado'

    equipment_id = fields.Many2one(
        'license.equipment',
        string='Equipo/Usuario a Eliminar',
        required=True,
        readonly=True
    )
    equipment_name = fields.Char(
        string='Equipo/Usuario',
        compute='_compute_equipment_info',
        readonly=True
    )
    item_type = fields.Char(
        string='Tipo',
        compute='_compute_equipment_info',
        readonly=True
    )
    assignment_quantity = fields.Integer(
        string='Cantidad de Licencias',
        related='equipment_id.assignment_id.quantity',
        readonly=True
    )
    contracting_type = fields.Selection(
        related='equipment_id.contracting_type',
        string='Tipo de Contratación',
        readonly=True
    )
    warning_message = fields.Html(
        string='Mensaje',
        compute='_compute_warning_message',
        readonly=True
    )

    @api.depends('equipment_id')
    def _compute_equipment_info(self):
        for rec in self:
            if rec.equipment_id and rec.equipment_id.exists():
                if rec.equipment_id.lot_id:
                    rec.equipment_name = rec.equipment_id.lot_id.name
                    rec.item_type = _('equipo')
                elif rec.equipment_id.contact_id:
                    rec.equipment_name = rec.equipment_id.contact_id.name
                    rec.item_type = _('usuario')
                else:
                    rec.equipment_name = _('Elemento')
                    rec.item_type = _('elemento')
            else:
                rec.equipment_name = ''
                rec.item_type = ''

    @api.depends('equipment_id', 'contracting_type', 'assignment_quantity', 'item_type', 'equipment_name')
    def _compute_warning_message(self):
        for rec in self:
            if not rec.equipment_id or not rec.equipment_id.exists():
                rec.warning_message = _(
                    '<div style="padding: 16px; background-color: #ffebee; border: 2px solid #f44336; border-radius: 6px;">'
                    '<p style="margin: 0; color: #c62828;"><strong>⚠️ Error:</strong> El registro ya no existe o fue eliminado.</p>'
                    '</div>'
                )
                continue
            
            contracting_type_name = dict(rec.equipment_id.assignment_id._fields['contracting_type'].selection).get(
                rec.contracting_type, rec.contracting_type
            ) if rec.contracting_type and rec.equipment_id.assignment_id else _('Mensual')
            
            if rec.contracting_type in ('annual_monthly_commitment', 'annual'):
                rec.warning_message = _(
                    '<div style="padding: 16px; background-color: #fff3cd; border: 2px solid #ff9800; border-radius: 6px; margin-bottom: 12px;">'
                    '<p style="margin: 0 0 12px 0; font-size: 16px;"><strong>⚠️ ADVERTENCIA IMPORTANTE</strong></p>'
                    '<p style="margin: 0 0 10px 0;">Está a punto de <strong>eliminar la asignación</strong> del %s <strong>"%s"</strong> del listado.</p>'
                    '<div style="background-color: #ffebee; padding: 12px; border-radius: 4px; border-left: 4px solid #f44336; margin-top: 10px;">'
                    '<p style="margin: 0 0 8px 0; color: #c62828;"><strong>📋 IMPORTANTE:</strong></p>'
                    '<ul style="margin: 0; padding-left: 20px; color: #b71c1c;">'
                    '<li style="margin-bottom: 6px;">La asignación se eliminará del listado.</li>'
                    '<li style="margin-bottom: 6px;"><strong>La cantidad de licencias (%d) NO se reducirá</strong> por el contrato "%s".</li>'
                    '<li style="margin-bottom: 6px;">La licencia <strong>quedará disponible para reasignar</strong> a otro equipo o usuario.</li>'
                    '<li>Puedes asignar otro %s en su lugar; la cantidad total de licencias se mantiene durante todo el período del contrato.</li>'
                    '</ul>'
                    '</div>'
                    '<p style="margin-top: 12px; margin-bottom: 0;"><strong>¿Desea continuar con la eliminación?</strong></p>'
                    '</div>'
                ) % (
                    rec.item_type,
                    rec.equipment_name,
                    rec.assignment_quantity,
                    contracting_type_name,
                    rec.item_type
                )
            else:
                rec.warning_message = _(
                    '<div style="padding: 16px; background-color: #e3f2fd; border: 2px solid #2196F3; border-radius: 6px; margin-bottom: 12px;">'
                    '<p style="margin: 0 0 10px 0;">Está a punto de <strong>eliminar la asignación</strong> del %s <strong>"%s"</strong> del listado.</p>'
                    '<p style="margin: 0;"><strong>¿Desea continuar con la eliminación?</strong></p>'
                    '</div>'
                ) % (rec.item_type, rec.equipment_name)

    @api.model
    def default_get(self, fields_list):
        """Asegura que el equipment_id se carga correctamente desde el contexto."""
        res = super().default_get(fields_list)
        # Intentar obtener el ID desde diferentes lugares del contexto
        equipment_id = (
            self.env.context.get('default_equipment_id') or 
            self.env.context.get('active_id')
        )
        if equipment_id:
            equipment = self.env['license.equipment'].browse(equipment_id)
            if equipment.exists():
                res['equipment_id'] = equipment_id
        return res

    def action_confirm_delete(self):
        """Confirma y elimina el equipo/usuario."""
        self.ensure_one()
        
        # Validar que el equipo existe
        if not self.equipment_id or not self.equipment_id.exists():
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('El registro ya no existe o fue eliminado.'),
                    'type': 'danger',
                    'sticky': True,
                }
            }
        
        equipment = self.equipment_id
        equipment_name = self.equipment_name
        item_type = self.item_type
        assignment_quantity = self.assignment_quantity
        contracting_type = self.contracting_type
        
        # Eliminar el registro
        equipment.unlink()
        
        # Cerrar el wizard (la ventana se cierra; el listado se actualiza y se ve el cambio)
        return {'type': 'ir.actions.act_window_close'}
