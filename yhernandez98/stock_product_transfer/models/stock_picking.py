# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def write(self, vals):
        """
        Proteger el tipo de operación de recepción para que no se cambie automáticamente
        cuando se guarda o actualiza el picking.
        """
        # Si el picking ya existe y tiene un tipo de operación de recepción (incoming),
        # protegerlo para que no se cambie automáticamente
        if 'picking_type_id' not in vals:
            for picking in self:
                # Si el picking ya tiene un tipo de operación de recepción
                if picking.picking_type_id and picking.picking_type_id.code == 'incoming':
                    # Si se están modificando las ubicaciones, asegurarse de que el tipo de operación
                    # no cambie automáticamente
                    if 'location_id' in vals or 'location_dest_id' in vals:
                        # Mantener el tipo de operación original
                        vals['picking_type_id'] = picking.picking_type_id.id
        
        result = super().write(vals)
        
        # Después de escribir, verificar que el tipo de operación no haya cambiado
        # (por si algún método onchange lo cambió)
        for picking in self:
            if picking.picking_type_id and picking.picking_type_id.code == 'incoming':
                # Si el picking tiene un purchase_id, es una recepción y debe mantener su tipo
                if picking.purchase_id:
                    # Verificar que el tipo de operación siga siendo incoming
                    if picking.picking_type_id.code != 'incoming':
                        # Restaurar el tipo de operación correcto
                        incoming_type = self.env['stock.picking.type'].search([
                            ('code', '=', 'incoming'),
                            ('warehouse_id', '=', picking.warehouse_id.id if picking.warehouse_id else False),
                        ], limit=1)
                        if incoming_type:
                            picking.picking_type_id = incoming_type.id
        
        return result

    @api.model_create_multi
    def create(self, vals_list):
        """
        Asegurar que los pickings de recepción mantengan su tipo de operación correcto.
        """
        for vals in vals_list:
            # Si se está creando un picking con tipo de operación de recepción,
            # asegurarse de que las ubicaciones sean correctas
            if 'picking_type_id' in vals:
                picking_type = self.env['stock.picking.type'].browse(vals['picking_type_id'])
                if picking_type.exists() and picking_type.code == 'incoming':
                    # Si no se especificaron ubicaciones, usar las del tipo de operación
                    if 'location_id' not in vals:
                        vals['location_id'] = picking_type.default_location_src_id.id
                    if 'location_dest_id' not in vals:
                        vals['location_dest_id'] = picking_type.default_location_dest_id.id
        
        return super().create(vals_list)

    @api.onchange('location_id', 'location_dest_id')
    def _onchange_location(self):
        """
        Prevenir que el tipo de operación cambie automáticamente cuando se modifican las ubicaciones
        en un picking de recepción existente.
        """
        # Si el picking ya tiene un tipo de operación de recepción, no permitir que cambie
        if self.picking_type_id and self.picking_type_id.code == 'incoming':
            # Si tiene un purchase_id, es definitivamente una recepción
            if self.purchase_id:
                # Mantener el tipo de operación original
                return
        
        # Para otros casos, dejar que Odoo maneje el cambio normalmente
        return

