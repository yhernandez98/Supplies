# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SubscriptionSubscription(models.Model):
    _inherit = 'subscription.subscription'

    def action_open_admin_reassign_wizard(self):
        self.ensure_one()
        if not self.location_id:
            raise UserError(_('La suscripción debe tener ubicación para hacer la corrección administrativa.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Corrección administrativa de serial'),
            'res_model': 'subscription.admin.reassign.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_origin_subscription_id': self.id,
            },
        }


class SubscriptionAdminReassignWizard(models.TransientModel):
    _name = 'subscription.admin.reassign.wizard'
    _description = 'Corrección administrativa de serial sin cobro'

    origin_subscription_id = fields.Many2one(
        'subscription.subscription',
        string='Suscripción origen',
        required=True,
    )
    origin_location_id = fields.Many2one(
        'stock.location',
        related='origin_subscription_id.location_id',
        readonly=True,
        string='Ubicación origen',
    )
    lot_id = fields.Many2one(
        'stock.lot',
        string='Serial principal',
        required=True,
        domain="[('id', 'in', available_lot_ids)]",
    )
    available_lot_ids = fields.Many2many(
        'stock.lot',
        compute='_compute_available_lot_ids',
        store=False,
    )
    destination_partner_id = fields.Many2one(
        'res.partner',
        string='Cliente destino',
        domain="[('parent_id', '=', False)]",
        help='Solo contactos principales (no contactos relacionados).',
    )
    destination_location_id = fields.Many2one(
        'stock.location',
        string='Ubicación destino',
        readonly=True,
    )
    available_destination_subscription_ids = fields.Many2many(
        'subscription.subscription',
        compute='_compute_available_destination_options',
        store=False,
    )
    destination_subscription_id = fields.Many2one(
        'subscription.subscription',
        string='Suscripción destino (opcional)',
        domain="[('id', 'in', available_destination_subscription_ids)]",
    )
    available_destination_service_product_ids = fields.Many2many(
        'product.product',
        compute='_compute_available_destination_options',
        store=False,
    )
    destination_service_product_id = fields.Many2one(
        'product.product',
        string='Servicio destino (opcional)',
        domain="[('id', 'in', available_destination_service_product_ids)]",
    )
    destination_entry_date = fields.Date(
        string='Fecha Activación Renting',
        help='Fecha de activación para el cliente destino.',
    )
    destination_exit_date = fields.Date(
        string='Fecha Finalización Renting',
        help='Fecha finalización para el cliente destino (opcional).',
    )
    is_destination_supplies = fields.Boolean(
        string='Destino es Supp/Existencias',
        compute='_compute_is_destination_supplies',
        store=False,
    )
    move_associated_items = fields.Boolean(
        string='Mover también elementos asociados',
        default=True,
    )
    clear_usage_history = fields.Boolean(
        string='Eliminar historial de uso en suscripción origen',
        default=True,
        help='Útil para corregir asignaciones erróneas sin dejar cobro ni trazabilidad de devolución.',
    )
    note = fields.Text(string='Nota interna')

    @api.depends('destination_partner_id', 'destination_location_id')
    def _compute_is_destination_supplies(self):
        for wizard in self:
            location = wizard.destination_location_id
            partner = wizard.destination_partner_id
            location_name = ((location.complete_name or location.display_name or location.name) if location else '') or ''
            partner_name = (partner.name or '') if partner else ''
            is_supp_location = 'SUPP/EXISTENCIAS' in location_name.upper()
            is_supplies_partner = partner_name.strip().upper() == 'SUPPLIES DE COLOMBIA SAS'
            wizard.is_destination_supplies = bool(is_supp_location and is_supplies_partner)

    @api.depends('origin_subscription_id', 'origin_location_id')
    def _compute_available_lot_ids(self):
        Quant = self.env['stock.quant']
        for wizard in self:
            wizard.available_lot_ids = False
            if not wizard.origin_location_id:
                continue
            main_lines = wizard.origin_subscription_id.line_ids.filtered(
                lambda l: l.is_active and not l.is_component_line and l.display_in_lines
            )
            main_product_ids = []
            for line in main_lines:
                stock_product = line.stock_product_id or line.product_id
                if stock_product and stock_product.id not in main_product_ids:
                    main_product_ids.append(stock_product.id)
            if not main_product_ids:
                continue
            location_ids = self.env['stock.location'].search([
                ('id', 'child_of', wizard.origin_location_id.id),
            ]).ids
            quants = Quant.search([
                ('location_id', 'in', location_ids),
                ('product_id', 'in', main_product_ids),
                ('lot_id', '!=', False),
                ('quantity', '>', 0),
            ])
            lots = quants.mapped('lot_id')
            wizard.available_lot_ids = lots

    @api.depends('destination_partner_id', 'destination_location_id')
    def _compute_available_destination_options(self):
        Subscription = self.env['subscription.subscription']
        PricelistItem = self.env['product.pricelist.item']
        for wizard in self:
            wizard.available_destination_subscription_ids = False
            wizard.available_destination_service_product_ids = False
            partner = wizard.destination_partner_id
            if not partner:
                continue

            sub_domain = [
                ('state', 'in', ('draft', 'active')),
                ('partner_id', '=', partner.id),
            ]
            if wizard.destination_location_id:
                sub_domain.append(('location_id', '=', wizard.destination_location_id.id))
            subscriptions = Subscription.search(sub_domain)
            wizard.available_destination_subscription_ids = subscriptions

            service_products = self.env['product.product']
            pricelist = partner.property_product_pricelist
            if pricelist:
                items = PricelistItem.search([('pricelist_id', '=', pricelist.id)])
                service_products |= items.mapped('product_id').filtered(lambda p: p and p.type == 'service')
                tmpl_services = items.mapped('product_tmpl_id').mapped('product_variant_ids').filtered(lambda p: p and p.type == 'service')
                service_products |= tmpl_services
            # Complemento: servicios que ya usa este cliente en sus suscripciones
            partner_subs = Subscription.search([('partner_id', '=', partner.id)])
            service_products |= partner_subs.mapped('line_ids.product_id').filtered(lambda p: p and p.type == 'service')
            wizard.available_destination_service_product_ids = service_products

    @api.onchange('destination_partner_id')
    def _onchange_destination_partner_id(self):
        self.destination_subscription_id = False
        self.destination_service_product_id = False
        self.destination_exit_date = False
        if self.destination_partner_id:
            self.destination_location_id = self.destination_partner_id.property_stock_customer
            if self.destination_location_id:
                self.destination_entry_date = fields.Date.context_today(self)
        else:
            self.destination_location_id = False
            self.destination_entry_date = False

    @api.onchange('destination_subscription_id')
    def _onchange_destination_subscription_id(self):
        if self.destination_subscription_id:
            self.destination_partner_id = self.destination_subscription_id.partner_id
        if self.destination_subscription_id and self.destination_subscription_id.location_id:
            self.destination_location_id = self.destination_subscription_id.location_id

    def action_apply_admin_reassignment(self):
        self.ensure_one()
        if not self.origin_subscription_id.location_id:
            raise UserError(_('La suscripción origen no tiene ubicación.'))
        if not self.destination_partner_id:
            raise UserError(_('Debe seleccionar un cliente destino.'))
        destination_location = self.destination_location_id or self.destination_partner_id.sudo().property_stock_customer
        if not destination_location:
            raise UserError(_('El cliente destino no tiene ubicación de cliente configurada.'))
        is_destination_supplies = (
            (self.destination_partner_id.name or '').strip().upper() == 'SUPPLIES DE COLOMBIA SAS'
            and ('SUPP/EXISTENCIAS' in ((destination_location.complete_name or destination_location.display_name or destination_location.name or '').upper()))
        )
        if not is_destination_supplies and not self.destination_entry_date:
            raise UserError(_('Debe indicar la Fecha Activación Renting para el cliente destino.'))
        if self.destination_subscription_id and self.destination_subscription_id.location_id and destination_location:
            if self.destination_subscription_id.location_id.id != destination_location.id:
                raise UserError(_('Si define suscripción destino, la ubicación destino debe coincidir con esa suscripción.'))
            if self.destination_subscription_id.partner_id.id != self.destination_partner_id.id:
                raise UserError(_('La suscripción destino debe pertenecer al cliente destino seleccionado.'))

        all_lots = self._collect_lots_to_move(self.lot_id, include_associated=self.move_associated_items)

        # Limpiar vínculo/campos de la asignación errónea (servicio/suscripción/fechas) en todos los lotes a corregir.
        all_lots.with_context(skip_subscription_exit_tracking=True).write({
            'active_subscription_id': False,
            'subscription_service_product_id': False,
            'entry_date': False,
            'exit_date': False,
            'last_entry_date_display': False,
            'last_exit_date_display': False,
            'last_subscription_id': False,
            'last_subscription_service_id': False,
            'pending_removal_date': False,
            'last_subscription_entry_date': False,
            'last_subscription_exit_date': False,
        })

        if self.clear_usage_history:
            usage_domain = [
                ('subscription_id', '=', self.origin_subscription_id.id),
                ('lot_id', 'in', all_lots.ids),
            ]
            self.env['subscription.subscription.usage'].search(usage_domain).unlink()

        # Limpiar ajustes manuales de fechas para estos seriales en origen/destino,
        # para que no prevalezcan fechas antiguas al renderizar "Ver Detalles".
        if 'subscription.lot.date.override' in self.env:
            subs_for_override = self.origin_subscription_id
            if self.destination_subscription_id:
                subs_for_override |= self.destination_subscription_id
            self.env['subscription.lot.date.override'].search([
                ('subscription_id', 'in', subs_for_override.ids),
                ('lot_id', 'in', all_lots.ids),
            ]).unlink()

        for lot in all_lots:
            self._move_lot_to_location(lot, destination_location)

        # Aplicar fechas destino a los lotes trasladados (en Supp/Existencias pueden quedar vacías).
        destination_date_vals = {
            'entry_date': self.destination_entry_date or False,
            'exit_date': self.destination_exit_date or False,
        }
        all_lots.with_context(skip_subscription_exit_tracking=True).write(destination_date_vals)

        # Solo para serial principal: destino opcional
        main_vals = {}
        if self.destination_subscription_id:
            main_vals['active_subscription_id'] = self.destination_subscription_id.id
        if self.destination_service_product_id:
            main_vals['subscription_service_product_id'] = self.destination_service_product_id.id
        if self.destination_entry_date:
            main_vals['entry_date'] = self.destination_entry_date
        main_vals['exit_date'] = self.destination_exit_date or False
        if main_vals:
            self.lot_id.with_context(skip_subscription_exit_tracking=True).write(main_vals)

        # Re-sincronizar para limpiar líneas de origen SIN generar nuevos registros de uso/cobro.
        self._sync_subscription_without_usage(self.origin_subscription_id)
        if self.destination_subscription_id:
            self.destination_subscription_id.action_sync_from_location()

        body = _(
            'Corrección administrativa sin cobro aplicada para serial principal %s. '
            'Lotes movidos: %s. %s'
        ) % (
            self.lot_id.display_name,
            ', '.join(all_lots.mapped('display_name')),
            self.note or '',
        )
        self.origin_subscription_id.message_post(body=body)
        if self.destination_subscription_id:
            self.destination_subscription_id.message_post(body=body)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Corrección aplicada'),
                'message': _('Se movió el serial y se limpió la suscripción origen sin cobro.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def _collect_lots_to_move(self, root_lot, include_associated=False):
        lots = self.env['stock.lot'].browse(root_lot.id)
        if not include_associated:
            return lots
        pending = [root_lot]
        seen = {root_lot.id}
        SupplyLine = self.env['stock.lot.supply.line']
        while pending:
            current = pending.pop(0)
            # Hijos directos (principal -> asociados)
            related = current.lot_supply_line_ids.mapped('related_lot_id').filtered(lambda l: l)
            # Relaciones inversas (si current es asociado de otro principal)
            reverse_related = SupplyLine.search([
                ('related_lot_id', '=', current.id),
                ('lot_id', '!=', False),
            ]).mapped('lot_id')
            # Complemento: asociaciones por principal_lot_id cuando exista en el modelo
            by_principal_field = self.env['stock.lot'].browse()
            if 'principal_lot_id' in self.env['stock.lot']._fields:
                by_principal_field = self.env['stock.lot'].search([('principal_lot_id', '=', current.id)])
            related |= reverse_related | by_principal_field
            for rel in related:
                if rel.id in seen:
                    continue
                seen.add(rel.id)
                lots |= rel
                pending.append(rel)
        return lots

    def _sync_subscription_without_usage(self, subscription):
        """Sincroniza ubicación sin crear/cerrar usage para evitar cobro por corrección administrativa."""
        if not subscription or not subscription.location_id:
            return
        products_info = subscription._get_location_products()
        main_products = products_info.get('main_products', [])
        component_items = products_info.get('component_items', [])
        subscription._normalize_component_lines(component_items)
        subscription._sync_subscription_lines(
            main_products,
            remove_missing=True,
            track_usage=False,
            sync_datetime=fields.Datetime.now(),
        )
        subscription._sync_component_lines(
            component_items,
            remove_missing=True,
            track_usage=False,
            sync_datetime=fields.Datetime.now(),
        )
        subscription._fix_existing_lines_visibility()
        subscription._consolidate_duplicate_lines()

    def _move_lot_to_location(self, lot, destination_location):
        quants = self.env['stock.quant'].search([
            ('lot_id', '=', lot.id),
            ('quantity', '>', 0),
        ])
        if not quants:
            return

        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('warehouse_id', '!=', False),
        ], limit=1)

        for quant in quants:
            if quant.location_id.id == destination_location.id:
                continue
            if not picking_type:
                self._move_quant_direct(quant, destination_location)
                continue
            picking = self.env['stock.picking'].create({
                'picking_type_id': picking_type.id,
                'location_id': quant.location_id.id,
                'location_dest_id': destination_location.id,
            })
            move = self.env['stock.move'].create({
                'product_id': lot.product_id.id,
                'product_uom': lot.product_id.uom_id.id,
                'location_id': quant.location_id.id,
                'location_dest_id': destination_location.id,
                'product_uom_qty': quant.quantity,
                'picking_id': picking.id,
            })
            picking.action_confirm()
            picking.action_assign()
            move_lines = move.move_line_ids.filtered(lambda ml: ml.product_id == lot.product_id)
            if move_lines:
                for move_line in move_lines:
                    move_line.lot_id = lot.id
                    move_line.qty_done = quant.quantity
            else:
                self.env['stock.move.line'].create({
                    'move_id': move.id,
                    'product_id': lot.product_id.id,
                    'product_uom_id': lot.product_id.uom_id.id,
                    'lot_id': lot.id,
                    'location_id': quant.location_id.id,
                    'location_dest_id': destination_location.id,
                    'qty_done': quant.quantity,
                    'product_uom_qty': quant.quantity,
                })
            picking.button_validate()

    def _move_quant_direct(self, quant, destination_location):
        move = self.env['stock.move'].create({
            'product_id': quant.product_id.id,
            'product_uom': quant.product_id.uom_id.id,
            'location_id': quant.location_id.id,
            'location_dest_id': destination_location.id,
            'product_uom_qty': quant.quantity,
        })
        move._action_confirm()
        move._action_assign()
        move_lines = move.move_line_ids.filtered(lambda ml: ml.product_id == quant.product_id)
        if move_lines:
            for move_line in move_lines:
                move_line.lot_id = quant.lot_id.id
                move_line.qty_done = quant.quantity
        else:
            self.env['stock.move.line'].create({
                'move_id': move.id,
                'product_id': quant.product_id.id,
                'product_uom_id': quant.product_id.uom_id.id,
                'lot_id': quant.lot_id.id,
                'location_id': quant.location_id.id,
                'location_dest_id': destination_location.id,
                'qty_done': quant.quantity,
                'product_uom_qty': quant.quantity,
            })
        move._action_done()
