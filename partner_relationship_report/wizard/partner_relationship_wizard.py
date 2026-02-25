# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class PartnerRelationshipReportWizard(models.TransientModel):
    _name = 'partner.relationship.report.wizard'
    _description = 'Asistente de Reporte de Relaciones de Contacto'

    partner_id = fields.Many2one(
        'res.partner', string='Contacto', required=True,
        domain=[('is_company', '=', True)]
    )
    report_type = fields.Selection([
        ('view', 'Ver en pantalla'),
        ('xlsx', 'Descargar Excel'),
        ('pdf', 'Descargar PDF'),
    ], required=True, default='view')
    observation = fields.Text(string='Observaciones')

    def _get_today_str(self):
        return fields.Date.today().strftime('%d/%m/%Y')

    def get_report_lines(self):
        self.ensure_one()
        partner = self.partner_id

        lots = self.env['stock.lot'].search([
            ('related_partner_id', '=', partner.id),
            ('product_id', '!=', False),
        ])

        allowed_types = {'component', 'peripheral', 'complement'}
        result = []

        products = (lots.mapped('product_id') | lots.mapped('lot_supply_line_ids.product_id'))
        products.read(['classification', 'display_name'])
        (lots | lots.mapped('lot_supply_line_ids.related_lot_id')).read([
            'name', 'model_name', 'billing_code'
        ])
        lot_lines = lots.mapped('lot_supply_line_ids')
        lot_lines.read(['quantity', 'related_lot_id', 'product_id'])
        for lot in lots:
            principal = {
                'group_key': lot.id,
                'partner_name': partner.display_name or '',
                'principal_serial': lot.name or '',
                'principal_product': lot.product_id.display_name or '',
                'principal_model': lot.model_name or '',
                'principal_billing_code': lot.billing_code or '',
                'principal_qty': lot.product_qty or 0.0,
                'lines': [],
            }

            for line in getattr(lot, 'lot_supply_line_ids', []):
                p = line.product_id
                if not p or p.classification not in allowed_types:
                    continue
                if not line.related_lot_id:
                    continue

                rl = line.related_lot_id 
                principal['lines'].append({
                    #'type': p.classification,
                    'serial': line.related_lot_id.name or '',
                    'product': p.display_name or '',
                    'model': rl.model_name or '',
                    'billing_code': rl.billing_code or '',
                    'qty': line.quantity or 0.0,

                })

            if principal['lines']:
                result.append(principal)

        return result

    def _ref(self, xmlid):
        rec = self.env.ref(xmlid, raise_if_not_found=False)
        if not rec:
            raise UserError(_("No se encontró el XMLID: %s") % xmlid)
        return rec

    def action_generate_report(self):
        self.ensure_one()
        data = {
            'partner_id': self.partner_id.id,
            'observation': self.observation or '',
        }
        t = (self.report_type or '').lower()
        if t == 'pdf':
            return self.env.ref(
                'partner_relationship_report.action_partner_relationship_report_pdf'
            ).report_action(self)
        elif t == 'xlsx':
            return self._ref('partner_relationship_report.action_partner_relationship_report_xlsx').report_action(self, data=data)
        else:
            return {
                'name': _('Relaciones del Contacto'),
                'type': 'ir.actions.act_window',
                'res_model': 'stock.lot',
                'view_mode': 'list,form',
                'domain': [
                    ('related_partner_id', '=', self.partner_id.id),
                    ('lot_supply_line_ids', '!=', False),
                ],
                'context': {'search_default_has_children': 1},
            }
