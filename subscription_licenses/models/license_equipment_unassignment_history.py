# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class LicenseEquipmentUnassignmentHistory(models.Model):
    _name = 'license.equipment.unassignment.history'
    _description = 'Historial de desasignaciones de licencia'
    _order = 'unassignment_date desc, id desc'

    assignment_id = fields.Many2one(
        'license.assignment',
        string='Asignación',
        required=True,
        ondelete='cascade',
        index=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        related='assignment_id.partner_id',
        string='Cliente',
        store=True,
        readonly=True,
    )
    license_id = fields.Many2one(
        'license.template',
        string='Licencia',
        ondelete='set null',
    )
    license_equipment_ref = fields.Integer(
        string='ID registro eliminado',
        help='Identificador del license.equipment eliminado del listado activo.',
    )
    lot_id = fields.Many2one('stock.lot', string='Equipo', ondelete='set null')
    contact_id = fields.Many2one('res.partner', string='Usuario asignado', ondelete='set null')
    equipment_serial = fields.Char(string='Serial / equipo')
    assigned_name = fields.Char(string='Asignado a')
    assignment_label = fields.Char(
        string='Asignación',
        help='Nombre de la asignación agrupada (categoría - producto).',
    )
    category_name = fields.Char(string='Categoría')
    license_product_name = fields.Char(string='Producto licencia')
    assignment_date = fields.Date(string='Fecha asignación')
    unassignment_date = fields.Date(string='Fecha desasignación', required=True)
    state_label = fields.Char(string='Estado al retirar', default='Desasignado')
    source = fields.Selection(
        [
            ('mesa_retiro', 'Retiro Mesa de Ayuda'),
            ('manual_delete', 'Eliminación manual'),
            ('other', 'Otro'),
        ],
        string='Origen',
        required=True,
        default='manual_delete',
    )
    helpdesk_ticket_id = fields.Integer(string='Ticket helpdesk (id)', index=True)
    helpdesk_ticket_name = fields.Char(string='Ticket helpdesk')
    removed_by_id = fields.Many2one('res.users', string='Registrado por', ondelete='set null')
    removed_at = fields.Datetime(string='Fecha registro', default=fields.Datetime.now)
    notes = fields.Text(string='Notas')

    _rec_name = 'assignment_label'
