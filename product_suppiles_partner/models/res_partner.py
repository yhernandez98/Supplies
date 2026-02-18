# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class ResPartner(models.Model):
    _inherit = "res.partner"

    lot_ids = fields.One2many(
        "stock.lot",
        "related_partner_id",
        string="Productos/Seriales Relacionados",
        help="Seriales asociados directamente a este contacto o empresa."
    )

    main_lot_ids = fields.Many2many(
        "stock.lot",
        string="Seriales Principales Asociados",
        compute="_compute_main_lot_ids",
        store=False,
        help="Seriales asignados a este contacto y a todos los contactos vinculados a su empresa."
    )

    all_lot_ids = fields.Many2many(
        "stock.lot",
        string="Todos los Seriales (Incluyendo Componentes)",
        compute="_compute_all_lot_ids",
        store=False,
        help="Todos los lotes asignados a este contacto, incluyendo componentes, periféricos y complementos."
    )
    
    related_lot_count = fields.Integer(
        string="Cantidad de Seriales Principales",
        compute="_compute_related_lot_count",
        store=False
    )
    
    total_lot_count = fields.Integer(
        string="Total Seriales (Incluyendo Componentes)",
        compute="_compute_total_lot_count",
        store=False
    )

    def _get_hierarchy_partners(self):
        """Devuelve los contactos que deben considerarse para las asignaciones."""
        self.ensure_one()
        if self.is_company:
            return self.env['res.partner'].search([('commercial_partner_id', '=', self.id)])
        return self

    @api.depends("lot_ids", "child_ids.lot_ids")
    def _compute_main_lot_ids(self):
        StockLot = self.env['stock.lot']
        for partner in self:
            linked_partners = partner._get_hierarchy_partners()
            if not linked_partners:
                partner.main_lot_ids = StockLot.browse()
                continue
            partner.main_lot_ids = StockLot.search([
                ('related_partner_id', 'in', linked_partners.ids)
            ])

    @api.depends("lot_ids", "child_ids.lot_ids")
    def _compute_related_lot_count(self):
        """Calcula el conteo de seriales principales de forma optimizada"""
        for partner in self:
            partner.related_lot_count = len(partner.main_lot_ids)

    @api.depends("lot_ids", "child_ids.lot_ids")
    def _compute_all_lot_ids(self):
        """Calcula todos los lotes asignados, incluyendo componentes, periféricos y complementos
        Optimizado para mejor rendimiento con muchos lotes"""
        for partner in self:
            main_lots = partner.main_lot_ids
            all_lots = main_lots
            if not main_lots:
                partner.all_lot_ids = all_lots
                continue
            
            # Optimización: buscar todos los lotes relacionados en una sola consulta
            # si el módulo product_suppiles está instalado
            if hasattr(self.env['stock.lot'], 'lot_supply_line_ids'):
                # Buscar todos los lotes relacionados en una sola consulta
                supply_lines = self.env['stock.lot.supply.line'].search([
                    ('lot_id', 'in', main_lots.ids),
                    ('related_lot_id', '!=', False)
                ])
                
                # Obtener todos los lotes relacionados únicamente
                related_lot_ids = supply_lines.mapped('related_lot_id').ids
                
                # Combinar lotes principales y relacionados
                all_lot_ids = list(set(main_lots.ids + related_lot_ids))
                all_lots = self.env['stock.lot'].browse(all_lot_ids)
            
            partner.all_lot_ids = all_lots

    @api.depends("all_lot_ids")
    def _compute_total_lot_count(self):
        for partner in self:
            partner.total_lot_count = len(partner.all_lot_ids)

    def action_view_related_lots(self):
        """Abre la vista de lotes relacionados a este contacto (incluyendo componentes)"""
        self.ensure_one()
        # Incluir todos los lotes relacionados
        all_lot_ids = self.all_lot_ids.ids
        action = {
            'name': _('Seriales Relacionados'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.lot',
            'view_mode': 'list,form',
            'domain': [('id', 'in', all_lot_ids)],
            'context': {'default_related_partner_id': self.id, 'search_default_filter_today': 1},
        }
        return action

