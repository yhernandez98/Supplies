# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo import _


class StockLot(models.Model):
    _inherit = "stock.lot"

    # Campo computed para obtener el partner de la ubicación (para filtrar contactos)
    location_partner_id = fields.Many2one(
        'res.partner',
        string='Cliente de la Ubicación',
        compute='_compute_location_partner',
        store=False,
        help='Cliente asociado a la ubicación del lote (para filtrar contactos)'
    )

    user_scope_partner_id = fields.Many2one(
        'res.partner',
        string='Cliente para filtro de usuario',
        compute='_compute_user_scope_partner',
        store=False,
        help='Cliente efectivo para filtrar usuarios en el serial: usa cliente forzado del contexto o el cliente de la ubicación.'
    )
    
    related_partner_id = fields.Many2one(
        "res.partner",
        string="Usuario",
        domain="[('parent_id', '=', user_scope_partner_id), ('is_company', '=', False)]",
        help="Usuario (contacto) relacionado de la empresa según la ubicación del producto serializado.",
        index=True,
    )

    @api.depends('location_partner_id')
    def _compute_user_scope_partner(self):
        for lot in self:
            forced_partner_id = self.env.context.get('force_license_partner_id')
            if forced_partner_id:
                forced_partner = self.env['res.partner'].browse(forced_partner_id)
                lot.user_scope_partner_id = forced_partner.commercial_partner_id if forced_partner else False
            else:
                lot.user_scope_partner_id = lot.location_partner_id.commercial_partner_id if lot.location_partner_id else False
    
    @api.depends('quant_ids', 'quant_ids.location_id', 'quant_ids.quantity')
    def _compute_location_partner(self):
        """Calcula el partner asociado a la ubicación del lote"""
        for lot in self:
            lot.location_partner_id = False
            
            if not lot.id:
                continue
            
            # Buscar el quant con mayor cantidad en ubicación interna
            quant = self.env['stock.quant'].search([
                ('lot_id', '=', lot.id),
                ('quantity', '>', 0),
                ('location_id.usage', '=', 'internal'),
            ], order='quantity desc, in_date desc', limit=1)
            
            if quant and quant.location_id:
                location = quant.location_id
                # Buscar partner que tiene esta ubicación como property_stock_customer
                partner = self.env['res.partner'].search([
                    ('property_stock_customer', '=', location.id)
                ], limit=1)
                
                if partner:
                    lot.location_partner_id = partner

    @api.constrains('related_partner_id', 'product_id')
    def _check_partner_and_tracking(self):
        """Valida condiciones al asignar contactos/empresas a un serial"""
        for lot in self:
            # Validar que el producto tenga trazabilidad serial si se asigna un contacto/empresa
            if lot.related_partner_id and lot.product_id:
                if lot.product_id.tracking != 'serial':
                    raise ValidationError(_(
                        'El producto "%s" debe tener trazabilidad tipo "Serial" para poder asignarlo a un contacto o empresa. '
                        'Tipo de trazabilidad actual: %s'
                    ) % (lot.product_id.display_name, lot.product_id.tracking or 'Ninguna'))

    def write(self, vals):
        """Propaga el contacto a todos los elementos relacionados (componentes, periféricos, complementos)"""
        # En el editor modal de ruta solo debe afectar el serial editado.
        if self.env.context.get('from_route_lot_editor'):
            return super().write(vals)

        # Evitar recursión: si ya estamos propagando, no propagar de nuevo
        if 'related_partner_id' in vals and not self.env.context.get('skip_propagation', False):
            partner_id = vals.get('related_partner_id')
            for lot in self:
                # Si se está asignando un contacto (no es False/None)
                if partner_id:
                    # Obtener todos los lotes relacionados a través de las líneas de suministro
                    related_lots = lot._get_related_lots()
                    # Asignar el mismo contacto a todos los lotes relacionados
                    # Usar contexto para evitar recursión en otros módulos y en la propagación
                    if related_lots:
                        related_lots.with_context(
                            skip_tracking=True, 
                            skip_search_enhancement=True,
                            skip_propagation=True  # Evitar que estos lotes propaguen de nuevo
                        ).write({'related_partner_id': partner_id})
                # Si se está quitando el contacto, también quitarlo de los relacionados
                else:
                    related_lots = lot._get_related_lots()
                    if related_lots:
                        related_lots.with_context(
                            skip_tracking=True, 
                            skip_search_enhancement=True,
                            skip_propagation=True  # Evitar que estos lotes propaguen de nuevo
                        ).write({'related_partner_id': False})

        return super().write(vals)

    def _get_related_lots(self, visited=None):
        """Obtiene todos los lotes relacionados a este lote (componentes, periféricos, complementos)"""
        if visited is None:
            visited = set()
        
        # Evitar recursión infinita
        if self.id in visited:
    