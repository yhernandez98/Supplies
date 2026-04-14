# -*- coding: utf-8 -*-
from odoo import fields, models, _


class ComponentLabActa(models.Model):
    _name = 'component.lab.acta'
    _description = 'Acta de control laboratorio'
    _order = 'id desc'

    name = fields.Char(string='Número acta', required=True, default=lambda self: _('Nueva'))
    assignment_id = fields.Many2one('component.lab.assignment', string='Asignación', required=True, ondelete='cascade', index=True)
    acta_type = fields.Selection(
        [
            ('assign_technician', 'Entrega a técnico'),
            ('tech_return_request', 'Solicitud devolución técnico'),
            ('tech_return_approved', 'Aprobación devolución técnico'),
            ('tech_return_rejected', 'Rechazo devolución técnico'),
        ],
        string='Tipo acta',
        required=True,
        index=True,
    )
    event_date = fields.Datetime(string='Fecha evento', required=True, default=fields.Datetime.now)
    responsible_user_id = fields.Many2one('res.users', string='Responsable (lab.)')
    technician_user_id = fields.Many2one('res.users', string='Técnico')
    created_by_user_id = fields.Many2one('res.users', string='Registrado por', default=lambda self: self.env.user, required=True)
    expected_return_date = fields.Date(string='Fecha estimada')
    note = fields.Text(string='Detalle')
    company_id = fields.Many2one('res.company', string='Compañía', related='assignment_id.company_id', store=True)

    def _next_name(self):
        return self.env['ir.sequence'].next_by_code('inventory_dashboard_simple.lab_acta') or _('ACTA/LAB/SN')

    @staticmethod
    def _default_note_map():
        return {
            'assign_technician': _('Acta de entrega de activo a técnico.'),
            'tech_return_request': _('Acta de devolución registrada por técnico (pendiente aprobación responsable).'),
            'tech_return_approved': _('Acta de aprobación de devolución por responsable de laboratorio.'),
            'tech_return_rejected': _('Acta de rechazo de devolución por responsable de laboratorio.'),
        }

    @classmethod
    def create_from_assignment(cls, assignment, acta_type, note='', acta_name=''):
        values = {
            'name': acta_name or assignment.env['component.lab.acta']._next_name(),
            'assignment_id': assignment.id,
            'acta_type': acta_type,
            'responsible_user_id': assignment.responsible_user_id.id,
            'technician_user_id': assignment.technician_user_id.id or False,
            'expected_return_date': assignment.expected_return_date,
            'note': note or cls._default_note_map().get(acta_type, ''),
        }
        return assignment.env['component.lab.acta'].create(values)

