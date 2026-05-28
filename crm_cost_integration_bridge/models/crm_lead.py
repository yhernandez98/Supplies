# -*- coding: utf-8 -*-
from odoo import _, fields, models


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    integration_case_ids = fields.One2many(
        'commercial.integration.case',
        'lead_id',
        string='Casos integración',
        readonly=True,
    )
    integration_case_count = fields.Integer(
        compute='_compute_integration_case_count',
        string='Casos integración',
    )

    def _compute_integration_case_count(self):
        for lead in self:
            lead.integration_case_count = len(lead.integration_case_ids)

    def action_view_integration_cases(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Casos integración'),
            'res_model': 'commercial.integration.case',
            'view_mode': 'list,form',
            'domain': [('lead_id', '=', self.id)],
            'context': {'default_lead_id': self.id, 'default_partner_id': self.partner_id.id if self.partner_id else False},
        }
