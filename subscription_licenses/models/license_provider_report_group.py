# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class LicenseProviderReportGroup(models.Model):
    _name = 'license.provider.report.group'
    _description = 'Agrupación por cliente en reporte del proveedor'
    _order = 'client_name asc'

    provider_partner_id = fields.Many2one(
        'license.provider.partner',
        string='Proveedor',
        required=True,
        ondelete='cascade',
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        required=True,
        ondelete='cascade',
    )
    client_name = fields.Char(
        string='Cliente (nombre)',
        help='Nombre del cliente para mostrar.',
    )
    line_count = fields.Integer(
        string='Líneas',
        compute='_compute_line_count',
        store=False,
    )

    def name_get(self):
        return [(r.id, r.client_name or r.partner_id.name or _('Cliente')) for r in self]

    @api.depends('provider_partner_id', 'partner_id')
    def _compute_line_count(self):
        ReportLine = self.env['license.provider.report.line']
        for rec in self:
            if rec.provider_partner_id and rec.partner_id:
                rec.line_count = ReportLine.search_count([
                    ('provider_partner_id', '=', rec.provider_partner_id.id),
                    ('partner_id', '=', rec.partner_id.id),
                ])
            else:
                rec.line_count = 0

    def action_view_contracted_licenses(self):
        """Abre el detalle de licencias contratadas de este cliente (sin agrupamiento, sin columna Cliente)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Licencias contratadas - %s') % (self.client_name or self.partner_id.name or 'Cliente'),
            'res_model': 'license.provider.report.line',
            'view_mode': 'list',
            'view_id': self.env.ref('subscription_licenses.view_license_provider_report_line_tree_by_client').id,
            'domain': [
                ('provider_partner_id', '=', self.provider_partner_id.id),
                ('partner_id', '=', self.partner_id.id),
            ],
            'context': {
                'default_provider_partner_id': self.provider_partner_id.id,
                'default_partner_id': self.partner_id.id,
                'default_client_name': self.client_name or self.partner_id.name,
            },
        }
