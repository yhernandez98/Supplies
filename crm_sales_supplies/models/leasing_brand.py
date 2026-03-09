# -*- coding: utf-8 -*-
from odoo import api, fields, models


class LeasingBrand(models.Model):
    _name = 'leasing.brand'
    _description = 'Marca de Leasing'
    _order = 'name'

    name = fields.Char(
        string='Marca',
        required=True,
        index=True,
        help='Nombre de la marca (ej: HP, Dell, Lenovo, etc.)'
    )
    code = fields.Char(
        string='Código',
        help='Código interno de la marca'
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente/Contacto',
        help='Contacto principal de la marca'
    )
    active = fields.Boolean(
        string='Activo',
        default=True
    )
    contract_ids = fields.One2many(
        'leasing.contract',
        'brand_id',
        string='Contratos'
    )
    contract_count = fields.Integer(
        string='Nº Contratos',
        compute='_compute_contract_count'
    )

    @api.depends('contract_ids')
    def _compute_contract_count(self):
        for record in self:
            record.contract_count = len(record.contract_ids)

    def action_view_contracts(self):
        """Abre la vista de contratos de la marca"""
        self.ensure_one()
        action = {
            'name': f'Contratos de {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'leasing.contract',
            'view_mode': 'tree,form',
            'domain': [('brand_ids', 'in', [self.id])],
            'context': {'default_brand_ids': [(6, 0, [self.id])]},
        }
        return action

