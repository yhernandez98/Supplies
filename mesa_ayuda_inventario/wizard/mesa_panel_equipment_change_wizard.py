# -*- coding: utf-8 -*-

from markupsafe import Markup, escape

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MesaPanelEquipmentChangeWizard(models.TransientModel):
    _name = 'mesa.panel.equipment.change.wizard'
    _description = 'Cambio de equipo desde panel de operaciones'

    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        domain=[('is_company', '=', True)],
        required=True,
    )
    inventory_plate = fields.Char(
        string='Placa de inventario',
        help='Digite la placa para ubicar el equipo del cliente.',
    )
    lot_id = fields.Many2one(
        'stock.lot',
        string='Equipo',
    )
    allowed_lot_ids = fields.Many2many(
        'stock.lot',
        compute='_compute_allowed_lot_ids',
    )
    equipment_preview_html = fields.Html(
        string='Resumen del equipo',
        compute='_compute_equipment_preview_html',
        sanitize=False,
        readonly=True,
    )

    @api.model
    def _commercial_partner(self, partner):
        return partner.commercial_partner_id if partner else self.env['res.partner']

    @api.model
    def _normalize_plate(self, plate):
        return (plate or '').strip().lower()

    @api.model
    def _is_main_equipment_lot(self, lot):
        """Solo equipos principales; excluye elementos asociados (componentes, periféricos, etc.)."""
        if not lot:
            return False
        if getattr(lot, 'principal_lot_id', False):
            return False
        if getattr(lot, 'associated_to_principal_lot_id', False):
            return False
        if getattr(lot, 'is_principal', False):
            return True
        if hasattr(lot, 'is_main_product'):
            return bool(lot.is_main_product)
        classification = getattr(lot.product_id, 'classification', None) if lot.product_id else None
        return classification not in ('component', 'peripheral', 'complement', 'spare')

    @api.model
    def _filter_main_equipment_lots(self, lots):
        return lots.filtered(lambda lot: self._is_main_equipment_lot(lot))

    @api.model
    def _pick_lot_by_plate(self, lots, plate_key):
        """Un lote principal por placa; si solo hay asociados, devuelve su equipo principal."""
        mains = self._filter_main_equipment_lots(lots)
        matched = mains.filtered(
            lambda l: self._normalize_plate(l.inventory_plate) == plate_key
        )
        if matched:
            return matched[0] if len(matched) == 1 else sorted(matched, key=lambda l: l.id)[0]
        associated = lots.filtered(
            lambda l: self._normalize_plate(l.inventory_plate) == plate_key
            and getattr(l, 'principal_lot_id', False)
        )
        principals = self._filter_main_equipment_lots(associated.mapped('principal_lot_id'))
        if principals:
            return principals[0] if len(principals) == 1 else sorted(principals, key=lambda l: l.id)[0]
        return self.env['stock.lot']

    @api.model
    def _lot_belongs_to_partner(self, lot, commercial):
        """True si el lote pertenece al cliente (empresa o contactos hijos)."""
        if not lot or not commercial:
            return False
        if lot.customer_id and lot.customer_id.commercial_partner_id == commercial:
            return True
        related = getattr(lot, 'related_partner_id', False)
        if related and related.commercial_partner_id == commercial:
            return True
        cust_loc = commercial.property_stock_customer
        if cust_loc:
            quants = self.env['stock.quant'].sudo().search([
                ('lot_id', '=', lot.id),
                ('location_id', 'child_of', cust_loc.id),
                ('quantity', '>', 0),
            ], limit=1)
            if quants:
                return True
        return False

    @api.model
    def _lots_for_partner(self, partner):
        """Lotes del cliente: lista amplia (placa + usuario + inventario retiro)."""
        commercial = self._commercial_partner(partner)
        if not commercial:
            return self.env['stock.lot']
        Lot = self.env['stock.lot'].sudo()
        lots = Lot.browse()
        # Búsqueda amplia por relaciones de contacto / cliente almacenado.
        lots |= Lot.search([
            '|', '|',
            ('customer_id', 'child_of', commercial.id),
            ('related_partner_id.commercial_partner_id', '=', commercial.id),
            ('related_partner_id', 'child_of', commercial.id),
        ], limit=500)
        # Complemento: misma lógica que retiro (productos principales con placa).
        Retiro = self.env['mesa.service.retiro.usuario.equipo.wizard']
        lots |= Retiro._lots_for_partner_locations(partner)
        return self._filter_main_equipment_lots(lots)

    @api.depends('partner_id')
    def _compute_allowed_lot_ids(self):
        for wiz in self:
            if wiz.partner_id:
                wiz.allowed_lot_ids = wiz._lots_for_partner(wiz.partner_id)
            else:
                wiz.allowed_lot_ids = self.env['stock.lot']

    def _find_lot_by_inventory_plate(self):
        """Ubica el equipo por placa para el cliente seleccionado."""
        self.ensure_one()
        plate = (self.inventory_plate or '').strip()
        if not self.partner_id or not plate:
            return self.env['stock.lot']
        commercial = self._commercial_partner(self.partner_id)
        plate_key = self._normalize_plate(plate)
        Lot = self.env['stock.lot'].sudo()

        # 1) Lotes principales del cliente con esa placa.
        from_partner = self._pick_lot_by_plate(
            self._lots_for_partner(self.partner_id), plate_key,
        )
        if from_partner:
            return from_partner

        # 2) Por placa en sistema; solo equipo principal del cliente.
        by_plate = Lot.search([
            '|',
            ('inventory_plate', '=', plate),
            ('inventory_plate', 'ilike', plate),
        ], limit=40)
        for lot in self._filter_main_equipment_lots(by_plate):
            if self._normalize_plate(lot.inventory_plate) != plate_key:
                continue
            if self._lot_belongs_to_partner(lot, commercial):
                return lot
        # Placa repetida en elemento asociado: resolver al principal del cliente.
        associated = by_plate.filtered(
            lambda l: self._normalize_plate(l.inventory_plate) == plate_key
            and getattr(l, 'principal_lot_id', False)
        )
        for principal in self._filter_main_equipment_lots(associated.mapped('principal_lot_id')):
            if self._lot_belongs_to_partner(principal, commercial):
                return principal

        return self.env['stock.lot']

    def _build_equipment_preview_html(self, lot):
        self.ensure_one()
        if not self.partner_id or not lot:
            return Markup('<p class="text-muted">%s</p>') % escape(
                _('Seleccione cliente y equipo para ver el resumen.')
            )
        prod = lot.product_id.display_name if lot.product_id else ''
        lines = [
            _('Cliente: %s') % (self.partner_id.display_name or ''),
            _('Serie: %s') % (lot.name or ''),
            _('Placa: %s') % (lot.inventory_plate or _('Sin placa')),
            _('Producto: %s') % prod,
        ]
        if getattr(lot, 'related_partner_id', False) and lot.related_partner_id:
            lines.append(_('Usuario: %s') % lot.related_partner_id.display_name)
        parts = [
            Markup(
                '<div style="padding:8px 10px;background:#f6fcf8;'
                'border:1px solid #c8e6d4;border-radius:8px;">'
            ),
        ]
        parts.extend(
            Markup('<p style="margin:4px 0;">%s</p>') % escape(line) for line in lines
        )
        parts.append(Markup('</div>'))
        return Markup('').join(parts)

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        for wiz in self:
            wiz.lot_id = False
            if wiz.partner_id:
                wiz.allowed_lot_ids = wiz._lots_for_partner(wiz.partner_id)
                if (wiz.inventory_plate or '').strip():
                    lot = wiz._find_lot_by_inventory_plate()
                    wiz.lot_id = lot
                    if lot:
                        wiz.allowed_lot_ids = wiz.allowed_lot_ids | lot
                        wiz.equipment_preview_html = wiz._build_equipment_preview_html(lot)
                        continue
            else:
                wiz.allowed_lot_ids = self.env['stock.lot']
            wiz.equipment_preview_html = wiz._build_equipment_preview_html(False)

    @api.onchange('inventory_plate', 'partner_id')
    def _onchange_inventory_plate(self):
        for wiz in self:
            if not wiz.partner_id:
                wiz.lot_id = False
                wiz.equipment_preview_html = wiz._build_equipment_preview_html(False)
                continue
            plate = (wiz.inventory_plate or '').strip()
            if not plate:
                wiz.lot_id = False
                wiz.equipment_preview_html = wiz._build_equipment_preview_html(False)
                continue
            lot = wiz._find_lot_by_inventory_plate()
            wiz.lot_id = lot
            if lot:
                allowed = wiz._lots_for_partner(wiz.partner_id)
                wiz.allowed_lot_ids = allowed | lot
                wiz.equipment_preview_html = wiz._build_equipment_preview_html(lot)
            else:
                wiz.equipment_preview_html = Markup(
                    '<p class="text-warning" style="margin:4px 0;">%s</p>'
                ) % escape(
                    _('No se encontró equipo con placa «%s» para %s.')
                    % (plate, wiz.partner_id.display_name)
                )

    @api.depends('partner_id', 'lot_id', 'inventory_plate')
    def _compute_equipment_preview_html(self):
        for wiz in self:
            lot = wiz.lot_id or wiz._find_lot_by_inventory_plate()
            wiz.equipment_preview_html = wiz._build_equipment_preview_html(lot)

    def action_create_ticket(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_('Seleccione el cliente.'))
        plate = (self.inventory_plate or '').strip()
        if not plate:
            raise UserError(_('Digite la placa de inventario.'))
        lot = self.lot_id or self._find_lot_by_inventory_plate()
        if not lot:
            raise UserError(
                _(
                    'No se encontró ningún equipo principal con la placa «%s» para el cliente %s. '
                    'Verifique la placa o que el equipo esté asignado al cliente.'
                )
                % (plate, self.partner_id.display_name)
            )
        if not self._is_main_equipment_lot(lot):
            raise UserError(
                _(
                    'La placa «%s» corresponde a un elemento asociado, no al equipo principal. '
                    'Use la placa del equipo principal.'
                )
                % plate
            )
        commercial = self._commercial_partner(self.partner_id)
        if not self._lot_belongs_to_partner(lot, commercial):
            raise UserError(_('El equipo no pertenece al cliente seleccionado.'))
        if self.lot_id != lot:
            self.lot_id = lot

        ticket = self.env['helpdesk.ticket']._mesa_create_panel_request_ticket(
            lot,
            self.partner_id,
            request_type='equipment_change',
        )
        return {
            'type': 'ir.actions.act_window',
            'name': ticket.name,
            'res_model': 'helpdesk.ticket',
            'view_mode': 'form',
            'res_id': ticket.id,
            'target': 'current',
        }
