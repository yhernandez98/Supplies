# -*- coding: utf-8 -*-
from odoo import models, fields, api


class PartnerPricelistDebugWizard(models.TransientModel):
    _name = 'partner.pricelist.debug.wizard'
    _description = 'Asistente debug lista de precios en contacto'

    partner_id = fields.Many2one('res.partner', string='Contacto', required=True, readonly=True)
    debug_text = fields.Text(string='Informe', readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        partner_id = (
            res.get('partner_id')
            or self.env.context.get('default_partner_id')
            or self.env.context.get('active_id')
        )
        if partner_id and 'debug_text' in fields_list:
            partner = self.env['res.partner'].browse(partner_id)
            if partner.exists():
                res['partner_id'] = partner.id
                res['debug_text'] = partner._get_pricelist_debug_report()
        return res


class PartnerSetSpecificPricelistWizard(models.TransientModel):
    _name = 'partner.set.specific.pricelist.wizard'
    _description = 'Asistente para fijar lista específica en contacto'

    partner_id = fields.Many2one('res.partner', string='Contacto', required=True, readonly=True)
    pricelist_id = fields.Many2one(
        'product.pricelist',
        string='Lista de precios a fijar',
        required=True,
        domain="[('company_id', 'in', [False, company_id])]",
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        readonly=True,
        default=lambda self: self.env.company,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        partner_id = (
            res.get('partner_id')
            or self.env.context.get('default_partner_id')
            or self.env.context.get('active_id')
        )
        if partner_id:
            partner = self.env['res.partner'].browse(partner_id)
            if partner.exists():
                res['partner_id'] = partner.id
                current = partner.property_product_pricelist
                if current and 'pricelist_id' in fields_list:
                    res['pricelist_id'] = current.id
        return res

    def action_apply(self):
        self.ensure_one()
        self.partner_id.write({
            'specific_property_product_pricelist': self.pricelist_id.id,
        })
        return {'type': 'ir.actions.act_window_close'}
