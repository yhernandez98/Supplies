# -*- coding: utf-8 -*-

from odoo import fields, models


class HelpdeskTeam(models.Model):
    _inherit = 'helpdesk.team'

    invdash_responsible_user_id = fields.Many2one(
        'res.users',
        string='Responsable',
        domain="[('active', '=', True)]",
        help='Usuario asignado por defecto a los tickets generados desde traslados E4.',
    )
