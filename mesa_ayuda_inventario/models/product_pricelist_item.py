# -*- coding: utf-8 -*-

from odoo import fields, models


class ProductPricelistItem(models.Model):
    _inherit = 'product.pricelist.item'

    admin_supplies_mh = fields.Boolean(
        string='Admin Supplies',
        compute='_compute_admin_supplies_mh',
        inverse='_inverse_admin_supplies_mh',
        help='Preferencia de administración por servicio para el cliente asociado a esta lista de precios.',
    )

    def _get_partner_candidates_for_pricelist(self):
        self.ensure_one()
        if not self.pricelist_id:
            return self.env['res.partner']
        # property_product_pricelist es un campo property (no almacenado en SQL),
        # por lo que no puede usarse en dominios de búsqueda SQL directos.
        partners = self.env['res.partner'].search([
            ('is_company', '=', True),
            ('active', '=', True),
        ])
        return partners.filtered(lambda p: p.property_product_pricelist == self.pricelist_id)

    def _get_service_key(self):
        self.ensure_one()
        product = self.product_id or self.product_tmpl_id.product_variant_id
        if not product:
            return (False, False)
        line = getattr(product, 'business_line_id', False)
        business_line_name = line.name if line else 'Sin linea de negocio'
        service_name = product.display_name or self.product_tmpl_id.display_name
        return (business_line_name, service_name)

    def _compute_admin_supplies_mh(self):
        Flag = self.env['customer.admin.supplies.service.flag']
        for item in self:
            business_line_name, service_name = item._get_service_key()
            if not business_line_name or not service_name:
                item.admin_supplies_mh = False
                continue
            partners = item._get_partner_candidates_for_pricelist()
            if not partners:
                item.admin_supplies_mh = False
                continue
            flag = Flag.search([
                ('partner_id', 'in', partners.ids),
                ('business_line_name', '=', business_line_name),
                ('service_name', '=', service_name),
                ('admin_supplies', '=', True),
            ], limit=1)
            item.admin_supplies_mh = bool(flag)

    def _inverse_admin_supplies_mh(self):
        Flag = self.env['customer.admin.supplies.service.flag']
        for item in self:
            business_line_name, service_name = item._get_service_key()
            if not business_line_name or not service_name:
                continue
            partners = item._get_partner_candidates_for_pricelist()
            for partner in partners:
                existing = Flag.search([
                    ('partner_id', '=', partner.id),
                    ('business_line_name', '=', business_line_name),
                    ('service_name', '=', service_name),
                ], limit=1)
                if existing:
                    existing.write({'admin_supplies': bool(item.admin_supplies_mh)})
                else:
                    Flag.create({
                        'partner_id': partner.id,
                        'business_line_name': business_line_name,
                        'service_name': service_name,
                        'admin_supplies': bool(item.admin_supplies_mh),
                    })
