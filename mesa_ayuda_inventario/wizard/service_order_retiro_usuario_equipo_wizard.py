# -*- coding: utf-8 -*-

import html as html_lib
from collections import defaultdict

from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MesaServiceRetiroUsuarioEquipoWizard(models.TransientModel):
    _name = 'mesa.service.retiro.usuario.equipo.wizard'
    _description = 'Retiro de Usuario/Equipo - Selección de origen'

    origin_model = fields.Char(string='Modelo origen', readonly=True)
    origin_id = fields.Integer(string='ID origen', readonly=True)

    consultation_only = fields.Boolean(
        string='Solo consulta informativa',
        default=False,
        help='Desde el menú Consulta: solo muestra información; no crear ticket ni tarea.',
    )

    search_mode = fields.Selection(
        [
            ('inventory', 'Por placa de inventario'),
            ('user', 'Por usuario/cliente'),
        ],
        string='Buscar por',
        required=True,
        default='inventory',
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        domain=[('is_company', '=', True)],
        help='Cliente (empresa) donde aplica el retiro o la consulta.',
    )

    lot_id = fields.Many2one(
        'stock.lot',
        string='Equipo (placa de inventario)',
        domain="[('id', 'in', allowed_lot_ids)]",
        help='Solo equipos principales del cliente con stock en la ubicación del cliente.',
    )
    inventory_plate = fields.Char(
        string='Placa de inventario',
        help='Digite la placa para ubicar el equipo.',
    )

    allowed_lot_ids = fields.Many2many(
        'stock.lot',
        string='Lotes permitidos',
        compute='_compute_allowed_lot_ids',
        store=False,
    )

    contact_id = fields.Many2one(
        'res.partner',
        string='Usuario (Contacto)',
        domain="[('parent_id', '=', partner_id), ('is_company', '=', False)]",
        help='Contacto de la empresa seleccionada.',
    )

    unlink_user_from_equipment = fields.Boolean(
        string='Devolución Equipo',
        default=True,
        help='Quita el usuario asignado al equipo (related_partner_id). El ticket incluirá la ficha del '
             'equipo y sus licencias de equipo. No modifica licencias salvo que marque «Retirar Licencias».',
    )
    client_requests_license_removal = fields.Boolean(
        string='Retirar Licencias',
        default=False,
        help='Permite elegir qué licencias del equipo desasignar (la cantidad contratada en la asignación '
             'no se reduce). El ticket solo listará las licencias seleccionadas. En búsqueda por placa '
             'se abre un paso previo de selección.',
    )
    inactivate_user = fields.Boolean(
        string='Inactivar usuario',
        default=False,
        help='Solo en búsqueda por usuario/cliente: pregunta devolución de equipos y retiro de '
             'licencias (como el flujo habitual), crea los tickets correspondientes y archiva el contacto.',
    )
    inactivate_flow_active = fields.Boolean(
        string='Flujo inactivar usuario activo',
        default=False,
        help='Técnico: indica que se está recorriendo el asistente de inactivación.',
    )
    user_return_lot_ids = fields.Many2many(
        'stock.lot',
        'mesa_retiro_user_return_lot_rel',
        'wizard_id',
        'lot_id',
        string='Equipos a devolver (usuario)',
        help='Equipos elegidos en el asistente de devolución por usuario.',
    )
    user_return_license_line_ids = fields.Many2many(
        'license.equipment',
        'mesa_retiro_user_return_lic_rel',
        'wizard_id',
        'license_equipment_id',
        string='Licencias de equipo a retirar (usuario)',
    )
    user_return_license_prompt_done_lot_ids = fields.Many2many(
        'stock.lot',
        'mesa_retiro_user_lic_done_lot_rel',
        'wizard_id',
        'lot_id',
        string='Equipos con pregunta de licencias respondida',
    )
    user_return_current_lot_id = fields.Many2one(
        'stock.lot',
        string='Equipo en selección de licencias',
        help='Equipo cuyas licencias se están eligiendo en el flujo por usuario.',
    )
    user_tab_license_line_ids = fields.Many2many(
        'license.equipment',
        'mesa_retiro_user_tab_lic_rel',
        'wizard_id',
        'license_equipment_id',
        string='Licencias del usuario a retirar',
        help='Licencias de la pestaña «Licencias del Usuario» elegidas en el asistente.',
    )
    user_license_discovery_ids = fields.Many2many(
        'license.equipment',
        'mesa_retiro_user_lic_disc_rel',
        'wizard_id',
        'license_equipment_id',
        string='Licencias usuario detectadas',
        compute='_compute_user_license_discovery_ids',
        store=False,
        help='Misma detección que inventario (license_user_ids); usada al registrar retiro.',
    )
    user_license_debug_html = fields.Html(
        string='Diagnóstico licencias',
        readonly=True,
        sanitize=False,
        help='Resultado del botón «Debug licencias» (ORM, SQL y contactos equivalentes).',
    )

    relation_info_html = fields.Html(
        string='Información relacionada',
        compute='_compute_relation_info_html',
        readonly=True,
    )

    @api.model
    def _lots_for_partner_locations(self, partner):
        """Lotes principales por cliente, priorizando placas con inventario."""
        Lot = self._stock_lot_retiro_env()
        if not partner:
            return Lot
        # 1) Buscar por cliente propietario directo o por usuarios/contactos del cliente.
        domain = [
            ('is_main_product', '=', True),
            ('inventory_plate', '!=', False),
            '|',
            ('customer_id', '=', partner.id),
            ('related_partner_id.commercial_partner_id', '=', partner.id),
        ]
        lots = Lot.search(domain)

        # 2) Si no hay resultados con placa, permitir fallback por serial/nombre para no bloquear.
        if not lots:
            domain = [
                ('is_main_product', '=', True),
                '|',
                ('customer_id', '=', partner.id),
                ('related_partner_id.commercial_partner_id', '=', partner.id),
            ]
            lots = Lot.search(domain)

        # 3) Orden visual amigable por placa (cuando exista).
        lots = lots.sorted(key=lambda l: ((l.inventory_plate or '').lower(), (l.name or '').lower()))
        return lots

    @api.model
    def _normalize_plate(self, plate):
        return (plate or '').strip().lower()

    @api.model
    def _is_main_equipment_lot(self, lot):
        """Solo equipo principal; excluye componentes/periféricos con la misma placa o serial."""
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
    def _pick_main_lot_among_serial_siblings(self, lots):
        """Varios stock.lot comparten el mismo serial (name); elegir el equipo principal."""
        lots = lots.exists()
        if not lots:
            return self.env['stock.lot']
        mains = self._filter_main_equipment_lots(lots)
        if len(mains) == 1:
            return mains[0]
        if len(mains) > 1:
            return sorted(mains, key=lambda l: self._score_main_lot_for_plate_pick(l), reverse=True)[0]
        principals = self._filter_main_equipment_lots(
            lots.mapped('principal_lot_id') | lots.mapped('associated_to_principal_lot_id')
        )
        if len(principals) == 1:
            return principals[0]
        if len(principals) > 1:
            return sorted(principals, key=lambda l: self._score_main_lot_for_plate_pick(l), reverse=True)[0]
        return lots[0]

    @api.model
    def _retiro_lot_cluster_ids(self, lot):
        """IDs del principal + componentes (principal_lot_id) + misma placa/serial."""
        Lot = self._stock_lot_retiro_env()
        main = self._retiro_resolve_main_lot(lot)
        if not main:
            return []
        ids = {main.id}
        if 'principal_lot_id' in Lot._fields:
            ids |= set(Lot.search([('principal_lot_id', '=', main.id)]).ids)
        plate = (main.inventory_plate or '').strip()
        if plate:
            ids |= set(Lot.search([('inventory_plate', '=', plate)], limit=200).ids)
        serial = (main.name or '').strip()
        if serial:
            ids |= set(Lot.search([('name', '=', serial)], limit=200).ids)
        return list(ids)

    @api.model
    def _pick_main_lot_by_plate(self, lots, plate_key):
        """Un solo lote principal por placa; si solo hay asociados, usa su equipo principal."""
        mains = self._filter_main_equipment_lots(lots)
        matched = mains.filtered(
            lambda l: self._normalize_plate(l.inventory_plate) == plate_key
        )
        if matched:
            if len(matched) == 1:
                return matched[0]
            return sorted(matched, key=lambda l: self._score_main_lot_for_plate_pick(l), reverse=True)[0]
        associated = lots.filtered(
            lambda l: self._normalize_plate(l.inventory_plate) == plate_key
            and getattr(l, 'principal_lot_id', False)
        )
        principals = self._filter_main_equipment_lots(associated.mapped('principal_lot_id'))
        if principals:
            return principals[0] if len(principals) == 1 else sorted(principals, key=lambda l: l.id)[0]
        return self.env['stock.lot']

    @api.model
    def _retiro_resolve_main_lot(self, lot):
        """Si el lote es elemento asociado, usar el equipo principal para licencias y tickets."""
        if not lot:
            return lot
        if self._is_main_equipment_lot(lot):
            return lot
        principal = getattr(lot, 'principal_lot_id', False) or getattr(
            lot, 'associated_to_principal_lot_id', False
        )
        return principal if principal else lot

    @api.model
    def _commercial_partner(self, partner):
        return partner.commercial_partner_id if partner else self.env['res.partner']

    @api.model
    def _lot_belongs_to_partner(self, lot, commercial):
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

    def _score_main_lot_for_plate_pick(self, lot):
        """Prioriza el principal con licencias, elementos y usuario asignado."""
        lic_count = 0
        supply_count = 0
        user_score = 0
        main = self._retiro_resolve_main_lot(lot)
        try:
            Le = self.env['license.equipment'].sudo()
            lic_count = Le.search_count([
                ('lot_id', '=', main.id),
                ('state', '=', 'assigned'),
            ])
            if hasattr(Le, '_equipment_tab_lines_for_lot'):
                lic_count = max(lic_count, len(Le._equipment_tab_lines_for_lot(main)))
        except KeyError:
            if hasattr(main, 'license_equipment_ids'):
                lic_count = len(main.license_equipment_ids.filtered(
                    lambda l: l.state == 'assigned'
                ))
        if hasattr(main, 'lot_supply_line_ids'):
            supply_count = len(main.lot_supply_line_ids)
        if getattr(main, 'related_partner_id', False):
            user_score = 1
        return (lic_count, supply_count, user_score, main.id)

    def _find_lot_by_inventory_plate(self):
        """Ubica el equipo principal que realmente tiene licencias en Licenciamientos."""
        self.ensure_one()
        plate = (self.inventory_plate or '').strip()
        if self.search_mode != 'inventory' or not self.partner_id or not plate:
            return self.env['stock.lot']
        hint = self.env['stock.lot']
        if self.origin_model == 'stock.lot' and self.origin_id:
            hint = self.env['stock.lot'].sudo().browse(self.origin_id).exists()
        return self._retiro_main_lot_for_partner_plate(lot_hint=hint or self.lot_id)

    def _stock_lot_retiro_env(self):
        """Búsqueda de seriales sin filtros extra del inventario de cliente."""
        return self.env['stock.lot'].sudo().with_context(
            skip_search_enhancement=True,
            skip_customer_inventory_scope=True,
        )

    def _lots_candidates_for_plate(self, partner, plate, lot_hint=None):
        """Todos los stock.lot con esa placa (principal + componentes + mismo serial)."""
        Lot = self._stock_lot_retiro_env()
        plate = (plate or '').strip()
        if not plate:
            return Lot.browse(lot_hint.ids) if lot_hint else Lot
        commercial = self._commercial_partner(partner) if partner else False
        plate_key = self._normalize_plate(plate)
        candidates = Lot.browse()
        if lot_hint:
            candidates |= lot_hint
        candidates |= Lot.search([('inventory_plate', '=', plate)], limit=200)
        if partner:
            candidates |= self._lots_for_partner_locations(partner).filtered(
                lambda l: self._normalize_plate(l.inventory_plate) == plate_key
            )
        candidates = candidates.filtered(
            lambda l: self._normalize_plate(l.inventory_plate) == plate_key
        )
        serials = {l.name for l in candidates if l.name}
        for serial in serials:
            candidates |= Lot.search([('name', '=', serial)], limit=80)
        candidates = candidates.filtered(
            lambda l: self._normalize_plate(l.inventory_plate) == plate_key
        )
        if commercial:
            scoped = candidates.filtered(lambda l: self._lot_belongs_to_partner(l, commercial))
            if scoped:
                candidates = scoped
        return candidates

    def _collect_equipment_tab_license_lines(self, partner=None, plate=None, lot_hint=None):
        """Igual que la pestaña «Licencias del Equipo» en la ficha de cada serial con esa placa."""
        self.ensure_one()
        try:
            LE = self.env['license.equipment'].sudo().with_context(active_test=False)
        except KeyError:
            return self.env['license.equipment'].browse()

        partner = partner or self.partner_id
        plate = (plate or self.inventory_plate or '').strip()
        candidates = self._lots_candidates_for_plate(partner, plate, lot_hint)
        if not candidates:
            return LE.browse()

        lines = LE.browse()
        if hasattr(LE, '_equipment_tab_lines_for_lot'):
            for lot_rec in candidates:
                lines |= LE._equipment_tab_lines_for_lot(lot_rec)
        else:
            lines |= LE.search([
                ('lot_id', 'in', candidates.ids),
                ('state', '=', 'assigned'),
                ('contact_id', '=', False),
            ])

        if plate and hasattr(LE, '_equipment_tab_lines_for_lot'):
            domain = [('inventory_plate', '=', plate), ('state', '=', 'assigned')]
            if partner:
                commercial = self._commercial_partner(partner)
                extra = LE.search(domain + [('partner_id', 'child_of', commercial.id)])
            else:
                extra = LE.search(domain)
            for rec in extra:
                if rec.lot_id and rec in LE._equipment_tab_lines_for_lot(rec.lot_id):
                    lines |= rec

        lines = self._filter_valid_assigned_license_lines(lines)
        if partner and lines:
            commercial = self._commercial_partner(partner)
            on_client = lines.filtered(
                lambda l: l.partner_id
                and l.partner_id.commercial_partner_id == commercial
            )
            if on_client:
                return on_client
        return lines

    def _retiro_main_lot_for_partner_plate(self, partner=None, plate=None, lot_hint=None):
        """Elige el serial donde la pestaña Licencias del Equipo tiene filas asignadas."""
        self.ensure_one()
        Lot = self._stock_lot_retiro_env()
        partner = partner or self.partner_id
        plate = (plate or self.inventory_plate or '').strip()
        lines = self._collect_equipment_tab_license_lines(partner, plate, lot_hint)
        if lines:
            for lot_rec in lines.mapped('lot_id'):
                main = self._retiro_resolve_main_lot(lot_rec)
                if self._is_main_equipment_lot(main):
                    return main
            return self._retiro_resolve_main_lot(lines[0].lot_id)

        if not partner or not plate:
            return self._retiro_resolve_main_lot(lot_hint) if lot_hint else Lot

        candidates = self._lots_candidates_for_plate(partner, plate, lot_hint)
        if not candidates:
            return Lot
        mains = self._filter_main_equipment_lots(candidates)
        if mains:
            return sorted(mains, key=lambda l: self._score_main_lot_for_plate_pick(l), reverse=True)[0]
        picked = self._pick_main_lot_by_plate(candidates, self._normalize_plate(plate))
        return picked if picked else Lot

    def _resolve_inventory_lot(self):
        """Equipo principal con licencias para la placa del cliente."""
        self.ensure_one()
        if self.search_mode != 'inventory':
            return self.lot_id
        lot = self._retiro_main_lot_for_partner_plate(lot_hint=self.lot_id)
        if lot and self.lot_id != lot:
            self.lot_id = lot
        return lot

    @api.depends('partner_id', 'search_mode')
    def _compute_allowed_lot_ids(self):
        Lot = self.env['stock.lot']
        for rec in self:
            if rec.search_mode != 'inventory' or not rec.partner_id:
                rec.allowed_lot_ids = Lot
                continue
            rec.allowed_lot_ids = rec._lots_for_partner_locations(rec.partner_id)

    @api.onchange('inventory_plate', 'partner_id', 'search_mode')
    def _onchange_inventory_plate(self):
        for rec in self:
            if rec.search_mode != 'inventory':
                continue
            plate = (rec.inventory_plate or '').strip()
            if not rec.partner_id or not plate:
                rec.lot_id = False
                continue
            rec.lot_id = rec._find_lot_by_inventory_plate()
            if rec.lot_id:
                rec.allowed_lot_ids = rec._lots_for_partner_locations(rec.partner_id) | rec.lot_id

    @api.depends('search_mode', 'partner_id', 'contact_id')
    def _compute_user_license_discovery_ids(self):
        for rec in self:
            if rec.search_mode != 'user' or not rec.partner_id or not rec.contact_id:
                rec.user_license_discovery_ids = [(5, 0, 0)]
                continue
            lines = rec._discover_user_license_lines()
            rec.user_license_discovery_ids = [(6, 0, lines.ids)]

    @api.depends(
        'search_mode',
        'partner_id',
        'inventory_plate',
        'lot_id',
        'contact_id',
        'user_license_discovery_ids',
        'lot_id.lot_supply_line_ids',
        'lot_id.lot_supply_line_ids.product_id',
        'lot_id.lot_supply_line_ids.has_cost',
        'lot_id.lot_supply_line_ids.cost',
        'lot_id.lot_supply_line_ids.related_lot_id',
        'contact_id.name',
    )
    def _compute_relation_info_html(self):
        for rec in self:
            rec.relation_info_html = rec._build_relation_info_html()

    def _build_relation_info_html(self):
        self.ensure_one()
        parts = [Markup('<div class="o_retiro_relation_info">')]

        if self.search_mode == 'inventory':
            if not self.partner_id or not self.lot_id:
                parts.append(
                    Markup('<p class="text-muted">%s</p>')
                    % _('Seleccione cliente y equipo para ver licencias y elementos asociados.')
                )
                parts.append(Markup('</div>'))
                return Markup('').join(parts)
            parts.extend(self._html_block_exec_summary_inventory(self.partner_id, self.lot_id))
            parts.append(
                Markup('<p class="text-muted mb-2">%s</p>')
                % escape(_('Equipo seleccionado: %s') % self._lot_heading(self.lot_id))
            )
            parts.extend(self._html_block_equipment_contract_info(self.lot_id))
            parts.extend(self._html_block_assigned_user(self.lot_id))
            parts.extend(self._html_block_licenses_equipment(self.partner_id, self.lot_id))
        elif self.search_mode == 'user':
            if not self.partner_id or not self.contact_id:
                parts.append(
                    Markup('<p class="text-muted">%s</p>')
                    % _('Seleccione cliente y usuario para ver licencias y equipos asociados.')
                )
                parts.append(Markup('</div>'))
                return Markup('').join(parts)
            parts.extend(self._html_block_exec_summary_user(self.partner_id, self.contact_id))
            parts.extend(self._html_block_licenses_user(self.partner_id, self.contact_id))
            lots = self._lots_for_user_all(self.partner_id, self.contact_id)
            if lots:
                parts.append(
                    Markup('<h4 class="mt-3">%s</h4>')
                    % _('Equipos e información vinculada al usuario')
                )
                seen = self.env['stock.lot']
                for lot in lots:
                    if lot in seen:
                        continue
                    seen |= lot
                    parts.append(Markup('<div style="margin:10px 0 14px 0;padding:10px 12px;border:1px solid #d9e6f2;background:#fbfdff;border-radius:8px;">'))
                    parts.append(
                        Markup('<p style="margin:0 0 8px 0;font-weight:700;color:#1f2d3d;">%s</p>')
                        % escape(self._lot_heading(lot))
                    )
                    parts.extend(self._html_block_equipment_contract_info(lot))
                    # Licencias del usuario ya están arriba; aquí solo equipo/contrato/elementos.
                    parts.extend(self._html_block_supply_lines(lot))
                    parts.append(Markup('</div>'))
            else:
                parts.append(
                    Markup('<p class="text-muted">%s</p>')
                    % _('No hay equipos asociados a este usuario.')
                )
        parts.append(Markup('</div>'))
        return Markup('').join(parts)

    def _html_block_exec_summary_inventory(self, partner, lot):
        lic_count = len(self._license_lines_linked_to_lot(lot)) if lot else 0
        user_name = ''
        if lot and hasattr(lot, 'related_partner_id') and lot.related_partner_id:
            user_name = lot.related_partner_id.name or ''
        items = [
            (_('Cliente'), partner.display_name if partner else ''),
            (_('Placa'), (lot.inventory_plate if lot else '') or ''),
            (_('Serial'), (lot.name if lot else '') or ''),
            (_('Usuario asignado'), user_name),
            (_('Licencias del equipo'), str(lic_count)),
        ]
        return self._html_exec_box(_('Resumen ejecutivo (equipo)'), items)

    def _lot_heading(self, lot):
        if not lot:
            return ''
        serial = lot.name or str(lot.id)
        asset_class = ''
        if getattr(lot, 'product_id', False) and getattr(lot.product_id, 'asset_class_id', False):
            asset_class = lot.product_id.asset_class_id.name or ''
        if asset_class:
            return '%s %s' % (asset_class, serial)
        return serial

    def _discover_user_license_lines(self, partner=None, contact=None):
        """Licencias de usuario solo vía módulo subscription_licenses (no inventario/serial)."""
        self.ensure_one()
        partner = partner or self.partner_id
        contact = contact or self.contact_id
        if not partner or not contact:
            model = self._license_equipment_model()
            return model.browse() if model else model
        LE = self._license_equipment_sudo()
        if LE is None:
            model = self._license_equipment_model()
            return model.browse() if model else model
        if hasattr(LE, '_user_license_lines_from_license_module'):
            try:
                lines = LE._user_license_lines_from_license_module(contact, partner=partner)
            except TypeError:
                lines = LE._user_license_lines_from_license_module(contact)
        else:
            lines = LE.search([
                ('state', '=', 'assigned'),
                ('contact_id', '=', contact.id),
            ])
        return lines.filtered(lambda l: l.state == 'assigned' and l.contact_id)

    def _html_block_exec_summary_user(self, partner, contact):
        lines = self._discover_user_license_lines(partner, contact)
        lic_count = len(self._dedupe_user_license_lines_for_display(lines, contact)) if lines else 0
        lots = self._lots_for_user_all(partner, contact)
        items = [
            (_('Cliente'), partner.display_name if partner else ''),
            (_('Usuario'), contact.name if contact else ''),
            (_('Equipos asociados'), str(len(lots))),
            (_('Licencias del usuario'), str(lic_count)),
        ]
        return self._html_exec_box(_('Resumen ejecutivo (usuario)'), items)

    def _html_exec_box(self, title, items):
        from odoo.addons.mesa_ayuda_inventario.wizard.acta_html_blocks import (
            mesa_ticket_html_kv_table,
            mesa_ticket_html_section_title,
        )

        rows = [(label, escape(value or _('No definido'))) for label, value in items]
        return [
            Markup(mesa_ticket_html_section_title(title)),
            Markup(mesa_ticket_html_kv_table(rows)),
        ]

    def _license_equipment_model(self):
        """Acceso al modelo license.equipment (subscription_licenses)."""
        registry = self.env.registry
        model_name = 'license.equipment'
        if model_name in registry:
            return self.env[model_name]

        lot_model = self.env['stock.lot']
        for fname in ('license_equipment_ids', 'license_user_ids'):
            field = lot_model._fields.get(fname)
            comodel = getattr(field, 'comodel_name', False) if field else False
            if comodel and comodel in registry:
                return self.env[comodel]

        im = self.env['ir.model'].sudo().search([('model', '=', model_name)], limit=1)
        if im and im.model in registry:
            return self.env[im.model]
        return None

    def _license_assignment_model(self):
        """Acceso al modelo license.assignment."""
        model_name = 'license.assignment'
        if model_name in self.env.registry:
            return self.env[model_name]
        return None

    def _license_equipment_available(self, license_lines=None):
        """True si hay modelo o ya vienen líneas license.equipment del wizard hijo."""
        if license_lines is not None and license_lines._name == 'license.equipment':
            return bool(license_lines) or 'license.equipment' in self.env
        return 'license.equipment' in self.env

    def _get_license_scope_data_for_lot(self, lot):
        """Replica el alcance usado en subscription_licenses.models.stock_lot."""
        location_partner_id = False
        lot_location_id = False
        if not lot:
            return location_partner_id, lot_location_id
        try:
            if hasattr(lot, 'location_partner_id') and lot.location_partner_id:
                location_partner_id = lot.location_partner_id.id
        except Exception:
            pass
        try:
            quant = self.env['stock.quant'].search([
                ('lot_id', '=', lot.id),
                ('quantity', '>', 0),
                ('location_id.usage', '=', 'internal'),
            ], order='quantity desc, in_date desc', limit=1)
            if quant and quant.location_id:
                lot_location_id = quant.location_id.id
        except Exception:
            pass
        return location_partner_id, lot_location_id

    def _html_block_assigned_user(self, lot):
        parts = [Markup('<h4 class="mt-3">%s</h4>') % escape(_('Usuario asignado al equipo'))]
        user_label = ''
        if lot and hasattr(lot, 'related_partner_id') and lot.related_partner_id:
            user_label = lot.related_partner_id.name
        if not user_label and lot and hasattr(lot, 'location_partner_id') and lot.location_partner_id:
            user_label = lot.location_partner_id.display_name
        if user_label:
            parts.append(Markup('<p class="mb-0">%s</p>') % escape(user_label))
        else:
            parts.append(Markup('<p class="text-muted mb-0">%s</p>') % escape(_('Sin usuario asignado.')))
        return parts

    def _html_block_equipment_contract_info(self, lot):
        parts = [Markup('<h4 class="mt-3">%s</h4>') % escape(_('Datos del equipo y contratación'))]
        if not lot:
            parts.append(Markup('<p class="text-muted">%s</p>') % escape(_('Sin información.')))
            return parts

        def selection_label(rec, field_name):
            if field_name not in rec._fields:
                return ''
            val = getattr(rec, field_name, False)
            if not val:
                return ''
            sel = rec._fields[field_name].selection
            pairs = sel(rec) if callable(sel) else (sel or [])
            return dict(pairs).get(val, val)

        entry = getattr(lot, 'entry_date', False) or getattr(lot, 'entry_date_display', False) or ''
        exit_d = getattr(lot, 'exit_date', False) or getattr(lot, 'exit_date_display', False) or ''
        plazo = selection_label(lot, 'reining_plazo')
        service = getattr(getattr(lot, 'subscription_service_product_id', False), 'display_name', '') or ''
        sub = getattr(getattr(lot, 'active_subscription_id', False), 'display_name', '') or ''

        items = [
            (_('Fecha activación renting'), entry),
            (_('Fecha finalización renting'), exit_d),
            (_('Plazo renting'), plazo),
            (_('Servicio'), service),
            (_('Suscripción'), sub),
        ]
        parts.append(Markup('<table style="width:100%;border-collapse:collapse;font-size:13px;background:#fff;border:1px solid #eceff3;">'))
        for label, value in items:
            parts.append(
                Markup('<tr><td style="width:36%%;padding:4px 8px;border-bottom:1px solid #eceff3;background:#fafcff;"><strong>%s</strong></td>'
                       '<td style="padding:4px 8px;border-bottom:1px solid #eceff3;">%s</td></tr>')
                % (escape(label), escape(value or _('No definido')))
            )
        parts.append(Markup('</table>'))
        return parts

    def _html_block_licenses_equipment(self, partner, lot):
        parts = []
        title = _('Licencias vinculadas a este equipo')
        rows = self._get_equipment_license_payload(partner, lot)
        if not rows:
            return []
        if any(row.get('informational_only') for row in rows):
            parts.append(
                Markup('<p class="text-warning small">%s</p>')
                % escape(_(
                    'Las licencias listadas provienen del inventario pero no tienen registro activo '
                    'en Licenciamientos para retirar desde aquí. Revise la asignación en el módulo de licencias.'
                ))
            )
        parts.append(Markup('<h4 class="mt-3">%s</h4>') % escape(title))
        parts.append(Markup(
            '<table style="width:100%;border-collapse:collapse;font-size:13px;background:#fff;border:1px solid #eceff3;">'
            '<thead><tr>'
            '<th style="text-align:left;padding:6px 8px;border-bottom:1px solid #d9d9d9;background:#f5f8fb;">Servicio</th>'
            '<th style="text-align:left;padding:6px 8px;border-bottom:1px solid #d9d9d9;background:#f5f8fb;">Categoría/Licencia</th>'
            '<th style="text-align:left;padding:6px 8px;border-bottom:1px solid #d9d9d9;background:#f5f8fb;">Tipo contratación</th>'
            '<th style="text-align:left;padding:6px 8px;border-bottom:1px solid #d9d9d9;background:#f5f8fb;">Estado contrato</th>'
            '</tr></thead><tbody>'
        ))
        for row in rows:
            serv = row.get('service') or ''
            lic = row.get('license') or ''
            ctype = row.get('contracting_type') or ''
            state = row.get('contract_state') or ''
            parts.append(
                Markup('<tr><td style="padding:5px 8px;border-bottom:1px solid #efefef;">%s</td>'
                       '<td style="padding:5px 8px;border-bottom:1px solid #efefef;">%s</td>'
                       '<td style="padding:5px 8px;border-bottom:1px solid #efefef;">%s</td>'
                       '<td style="padding:5px 8px;border-bottom:1px solid #efefef;">%s</td></tr>')
                % (
                    escape(serv or lic or _('Licencia')),
                    escape(lic or ''),
                    escape(ctype or ''),
                    escape(state or ''),
                )
            )
        parts.append(Markup('</tbody></table>'))
        return parts

    def _split_license_name_parts(self, text):
        if not text:
            return []
        out = []
        for chunk in text.replace('\n', ',').split(','):
            c = chunk.strip()
            if c and not c.startswith('(+'):
                out.append(c)
        return out

    def _fallback_combined_license_names_from_lot(self, lot):
        """Nombres de licencia como en vista inventario (equipo + usuario mezclados)."""
        if not lot:
            return []
        seen = set()
        names = []
        for fname in ('assigned_licenses_list_display', 'assigned_licenses_display'):
            if fname not in lot._fields:
                continue
            raw = (getattr(lot, fname, False) or '').strip()
            for part in self._split_license_name_parts(raw):
                k = part.lower()
                if k not in seen:
                    seen.add(k)
                    names.append(part)
        for i in range(1, 11):
            fname = 'license_%s_name' % i
            if fname not in lot._fields:
                continue
            val = (getattr(lot, fname, False) or '').strip()
            if val and val.lower() not in seen:
                seen.add(val.lower())
                names.append(val)
        return names

    def _fallback_equipment_license_names_from_lot(self, lot):
        """Solo licencias de equipo; si no hay modelo, usa campo dedicado o resta usuario."""
        if not lot:
            return []
        eq_txt = (getattr(lot, 'mesa_equipment_only_licenses_list_display', '') or '').strip()
        if eq_txt:
            return self._split_license_name_parts(eq_txt)
        user_txt = (getattr(lot, 'mesa_user_only_licenses_list_display', '') or '').strip()
        full = self._fallback_combined_license_names_from_lot(lot)
        if not full:
            return []
        if not user_txt:
            return full
        user_set = {x.lower() for x in self._split_license_name_parts(user_txt)}
        rest = [x for x in full if x.lower() not in user_set]
        return rest if rest else full

    def _filter_name_list_excluding_user_licenses_for_lot(self, partner, lot, names):
        """Quita de la lista nombres que correspondan a licencias del usuario asignado al equipo."""
        if not names or not lot or not partner:
            return names
        rp = getattr(lot, 'related_partner_id', False)
        if not rp:
            return names
        user_payload = self._get_user_license_payload(partner, rp)
        user_keys = set()
        for row in user_payload:
            for key in ('license', 'service'):
                val = (row.get(key) or '').strip().lower()
                if val:
                    user_keys.add(val)
        out = []
        for n in names:
            k = (n or '').strip().lower()
            if k and k not in user_keys:
                out.append(n)
        return out

    def _get_equipment_license_payload(self, partner, lot):
        """Filas para tabla licencias vinculadas al equipo (registros license.equipment)."""
        if not lot and not (self.inventory_plate or '').strip():
            return []
        lines = self._license_lines_linked_to_lot(lot)
        if lines:
            out = []
            for line in lines:
                serv = line.service_product_id.display_name if getattr(line, 'service_product_id', False) else ''
                lic = line.license_id.display_name if line.license_id else ''
                out.append({
                    'service': serv,
                    'license': lic,
                    'contracting_type': self._contracting_type_label(line),
                    'contract_state': line.assignment_id.state if line.assignment_id else '',
                    'informational_only': False,
                })
            return out
        names = self._fallback_equipment_license_names_from_lot(lot)
        names = self._filter_name_list_excluding_user_licenses_for_lot(partner, lot, names)
        return [
            {
                'service': n,
                'license': n,
                'contracting_type': '',
                'contract_state': '',
                'informational_only': True,
            }
            for n in names
        ]

    def _html_block_licenses_user(self, partner, contact):
        parts = []
        title = _('Licencias vinculadas a este usuario')
        payload = self._get_user_license_payload(partner, contact)
        if not payload:
            return []
        parts.append(Markup('<h4 class="mt-3">%s</h4>') % escape(title))
        parts.append(Markup(
            '<table style="width:100%;border-collapse:collapse;font-size:13px;background:#fff;border:1px solid #eceff3;">'
            '<thead><tr>'
            '<th style="text-align:left;padding:6px 8px;border-bottom:1px solid #d9d9d9;background:#f5f8fb;">Servicio</th>'
            '<th style="text-align:left;padding:6px 8px;border-bottom:1px solid #d9d9d9;background:#f5f8fb;">Categoría/Licencia</th>'
            '<th style="text-align:left;padding:6px 8px;border-bottom:1px solid #d9d9d9;background:#f5f8fb;">Tipo contratación</th>'
            '<th style="text-align:left;padding:6px 8px;border-bottom:1px solid #d9d9d9;background:#f5f8fb;">Equipo</th>'
            '</tr></thead><tbody>'
        ))
        for row in payload:
            serv = row.get('service') or ''
            lic = row.get('license') or ''
            ctype = row.get('contracting_type') or ''
            lot_label = row.get('equipment') or ''
            parts.append(
                Markup('<tr><td style="padding:5px 8px;border-bottom:1px solid #efefef;">%s</td>'
                       '<td style="padding:5px 8px;border-bottom:1px solid #efefef;">%s</td>'
                       '<td style="padding:5px 8px;border-bottom:1px solid #efefef;">%s</td>'
                       '<td style="padding:5px 8px;border-bottom:1px solid #efefef;">%s</td></tr>')
                % (
                    escape(serv or lic or _('Licencia')),
                    escape(lic or ''),
                    escape(ctype or ''),
                    escape(lot_label or _('sin equipo')),
                )
            )
        parts.append(Markup('</tbody></table>'))
        return parts

    def _user_license_line_lot(self, line):
        if getattr(line, 'lot_id', False):
            return line.lot_id
        if getattr(line, 'display_lot_id', False) and line.display_lot_id:
            return line.display_lot_id
        return False

    def _user_license_line_identity_key(self, line):
        if line.license_id:
            return ('lic', line.license_id.id)
        if getattr(line, 'service_product_id', False) and line.service_product_id:
            return ('srv', line.service_product_id.id)
        serv = line.service_product_id.display_name if getattr(line, 'service_product_id', False) else ''
        lic = line.license_id.display_name if line.license_id else ''
        return ('txt', ('%s|%s' % (serv, lic)).lower())

    def _user_license_line_equipment_score(self, line, contact):
        lot = self._user_license_line_lot(line)
        if not lot:
            return 0
        s = 0
        if getattr(lot, 'is_main_product', False):
            s += 100
        if contact and getattr(lot, 'related_partner_id', False) and lot.related_partner_id.id == contact.id:
            s += 50
        return s

    def _dedupe_user_license_lines_for_display(self, lines, contact):
        """Una fila por licencia; si hay varias líneas (por seriales vinculados), preferir equipo principal."""
        if not lines:
            return lines
        best = {}
        scores = {}
        for line in lines:
            k = self._user_license_line_identity_key(line)
            sc = self._user_license_line_equipment_score(line, contact)
            if k not in best or sc > scores[k]:
                best[k] = line
                scores[k] = sc
        ordered = [best[k] for k in sorted(best.keys())]
        return self.env[lines._name].browse([x.id for x in ordered])

    def _pick_primary_lot_for_user_license(self, lots, contact=None):
        Lot = self.env['stock.lot']
        if not lots:
            return Lot.browse()
        lots_rs = Lot.browse([l.id for l in lots]).exists()
        if not lots_rs:
            return Lot.browse()
        mains = lots_rs.filtered(lambda l: getattr(l, 'is_main_product', False))
        if mains:
            return mains.sorted('id')[0]
        if contact:
            rel = lots_rs.filtered(
                lambda l: getattr(l, 'related_partner_id', False) and l.related_partner_id.id == contact.id
            )
            if rel:
                return rel.sorted('id')[0]
        return lots_rs.sorted('id')[0]

    def _collect_user_tab_license_lines_all(self, partner, contact):
        """Delega en subscription_licenses (license.equipment / license.assignment)."""
        LE = self._license_equipment_sudo()
        if LE is None or not partner or not contact:
            model = self._license_equipment_model()
            return model.browse() if model else model
        if hasattr(LE, '_user_license_lines_from_license_module'):
            try:
                return LE._user_license_lines_from_license_module(contact, partner=partner)
            except TypeError:
                return LE._user_license_lines_from_license_module(contact)
        return LE.search([
            ('state', '=', 'assigned'),
            ('contact_id', '=', contact.id),
        ])

    def _get_user_license_lines_from_client_lots(self, partner, contact):
        """Por cada serial del cliente con este usuario: pestaña Licencias del Usuario."""
        LE = self._license_equipment_sudo()
        if LE is None or not contact:
            model = self._license_equipment_model()
            return model.browse() if model else model
        lines = LE.browse([])
        Lot = self.env['stock.lot'].sudo()
        domain = [('related_partner_id', '!=', False)]
        if partner:
            commercial = self._commercial_partner(partner)
            domain += [
                '|',
                ('customer_id.commercial_partner_id', '=', commercial.id),
                ('related_partner_id.commercial_partner_id', '=', commercial.id),
            ]
        contact_key = ''
        if hasattr(LE, '_partner_person_name_key'):
            contact_key = LE._partner_person_name_key(contact)
        else:
            name = (contact.name or '').strip()
            if ',' in name:
                name = name.split(',')[-1].strip()
            contact_key = name.lower()
        for lot in Lot.search(domain):
            rp = lot.related_partner_id
            if not rp:
                continue
            if rp.id != contact.id:
                if not contact_key or not hasattr(LE, '_partner_person_name_key'):
                    continue
                rp_key = LE._partner_person_name_key(rp)
                if not (
                    contact_key == rp_key
                    or contact_key in rp_key
                    or rp_key in contact_key
                ):
                    continue
            if hasattr(LE, '_user_tab_lines_for_lot'):
                lines |= LE._user_tab_lines_for_lot(lot)
            elif hasattr(lot, 'license_user_ids'):
                lines |= lot.license_user_ids.filtered(lambda l: l.state == 'assigned')
        return lines.filtered(lambda r: r.state == 'assigned' and r.contact_id)

    def _get_user_license_lines_from_lot_display_names(self, partner, contact):
        """Respaldo: texto en inventario (mesa_user_only_licenses_list_display) → registros."""
        LE = self._license_equipment_sudo()
        if LE is None or not contact:
            model = self._license_equipment_model()
            return model.browse() if model else model
        lines = LE.browse([])
        for lot in self._lots_for_user_all(partner, contact):
            user_txt = (getattr(lot, 'mesa_user_only_licenses_list_display', '') or '').strip()
            if not user_txt:
                continue
            rp = getattr(lot, 'related_partner_id', False) or contact
            for part in self._split_license_name_parts(user_txt):
                token = (part or '').strip()
                if len(token) < 3:
                    continue
                found = LE.search([
                    ('contact_id', '=', rp.id),
                    ('state', '=', 'assigned'),
                    '|', '|',
                    ('license_id.name', 'ilike', token),
                    ('service_product_id.name', 'ilike', token),
                    ('assignment_id.license_display_name', 'ilike', token),
                ], limit=5)
                lines |= found
            if hasattr(LE, '_user_tab_lines_for_lot'):
                lines |= LE._user_tab_lines_for_lot(lot.sudo())
        return lines.filtered(lambda r: r.state == 'assigned' and r.contact_id)

    def _get_user_license_payload(self, partner, contact):
        """Solo licencias de usuario (registros license.equipment con contacto)."""
        if self.search_mode == 'user' and self.partner_id and self.contact_id:
            lines = self._discover_user_license_lines(partner, contact)
        else:
            lines = self._collect_user_tab_license_lines_all(partner, contact)
        if not lines:
            return []
        lines = lines.sudo()
        lines = self._dedupe_user_license_lines_for_display(lines, contact)
        out = []
        for line in lines:
            lot_label = ''
            lot = self._user_license_line_lot(line)
            if lot:
                lot_label = lot.inventory_plate or lot.name or ''
            serv = ''
            lic = ''
            if getattr(line, 'service_product_id', False):
                serv = line.service_product_id.display_name or ''
            if line.license_id:
                lic = line.license_id.display_name or ''
            if not lic and line.assignment_id:
                lic = (
                    getattr(line.assignment_id, 'license_display_name', False)
                    or line.assignment_id.display_name
                    or ''
                )
            out.append({
                'service': serv or lic,
                'license': lic or serv,
                'contracting_type': self._contracting_type_label(line),
                'equipment': lot_label,
            })
        return out

    def _get_user_license_lines(self, partner, contact):
        """Licencias de usuario: solo módulo subscription_licenses."""
        return self._collect_user_tab_license_lines_all(partner, contact)

    def _selection_label(self, record, field_name):
        if not record or field_name not in record._fields:
            return ''
        val = record[field_name]
        if not val:
            return ''
        finfo = record._fields[field_name]
        if hasattr(finfo, '_description_selection'):
            pairs = finfo._description_selection(record.env)
        else:
            sel = finfo.selection
            pairs = sel(record) if callable(sel) else (sel or [])
        return dict(pairs).get(val, val)

    def _contracting_type_label(self, line):
        if not line:
            return ''
        val = line.contracting_type or (
            line.assignment_id.contracting_type if line.assignment_id else ''
        )
        if not val:
            return ''
        if line.contracting_type:
            return self._selection_label(line, 'contracting_type') or val
        return self._selection_label(line.assignment_id, 'contracting_type') or val

    def _license_equipment_sudo(self):
        """Env sudo del modelo; None solo si el módulo no está cargado.

        No usar ``if not LE``: un recordset vacío del modelo es falsy en Python
        pero sigue siendo un env válido para .search().
        """
        LE = self._license_equipment_model()
        if LE is None:
            return None
        companies = self.env['res.company'].sudo().search([]).ids
        return LE.sudo().with_context(
            active_test=False,
            allowed_company_ids=companies,
        )

    def _license_assignment_sudo(self):
        Assignment = self._license_assignment_model()
        if Assignment is None:
            return None
        companies = self.env['res.company'].sudo().search([]).ids
        return Assignment.sudo().with_context(
            active_test=False,
            allowed_company_ids=companies,
        )

    def _match_license_lines_from_lot_display(self, lot, LE):
        """Si el inventario muestra nombres pero el search falló, localizar por texto en el cluster."""
        lines = LE.browse()
        cluster_ids = self._all_lot_ids_for_retiro_license_search(lot)
        if not cluster_ids:
            return lines
        for name in self._fallback_equipment_license_names_from_lot(lot):
            token = (name or '').strip()
            if len(token) < 3:
                continue
            found = LE.search([
                ('lot_id', 'in', cluster_ids),
                ('state', '=', 'assigned'),
                '|', '|', '|',
                ('license_id.name', 'ilike', token),
                ('service_product_id.name', 'ilike', token),
                ('assignment_id.license_display_name', 'ilike', token),
                ('assignment_id.name', 'ilike', token),
            ], limit=10)
            lines |= found
        return lines

    def _filter_valid_assigned_license_lines(self, lines):
        """Solo excluye desasignadas en el pasado; no filtra por fecha de asignación futura."""
        if not lines:
            return lines
        today = fields.Date.context_today(self)
        return lines.filtered(
            lambda eq: eq.state == 'assigned'
            and (not eq.unassignment_date or eq.unassignment_date >= today)
        )

    def _all_lot_ids_for_retiro_license_search(self, lot):
        """Todos los stock.lot con la misma placa o serial (componentes + principal)."""
        Lot = self._stock_lot_retiro_env()
        plate = (self.inventory_plate or '').strip()
        if self.search_mode == 'inventory' and self.partner_id and plate:
            return self._lots_candidates_for_plate(self.partner_id, plate, lot).ids
        lot = self._retiro_resolve_main_lot(lot) if lot else lot
        ids = set()
        if lot:
            ids.add(lot.id)
            ids.update(self._retiro_lot_cluster_ids(lot))
        return list(ids)

    def _license_lines_linked_to_lot(self, lot=None):
        """Licencias de la pestaña «Licencias del Equipo» (misma lógica que la ficha del serial)."""
        self.ensure_one()
        if self.search_mode == 'inventory' and self.partner_id:
            return self._collect_equipment_tab_license_lines(
                self.partner_id,
                self.inventory_plate,
                lot or self.lot_id,
            )
        LE = self._license_equipment_sudo()
        if LE is None:
            model = self._license_equipment_model()
            return model.browse() if model else model
        lot = self._retiro_resolve_main_lot(lot or self.lot_id)
        if not lot:
            return LE.browse()
        lines = LE.browse()
        if hasattr(LE, '_equipment_tab_lines_for_lot'):
            lines |= LE._equipment_tab_lines_for_lot(lot.sudo())
        lines |= LE.search([('lot_id', '=', lot.id), ('state', '=', 'assigned')])
        return self._filter_valid_assigned_license_lines(lines)

    def _get_equipment_license_lines(self, lot):
        """Pestaña «Licencias del equipo» (misma lógica que subscription_licenses)."""
        LE = self._license_equipment_model()
        if LE is None or not lot:
            return None if LE is None else LE.browse()
        if hasattr(LE, '_equipment_tab_lines_for_lot'):
            return LE._equipment_tab_lines_for_lot(lot)
        if hasattr(lot, 'license_equipment_ids'):
            return lot.license_equipment_ids.filtered(
                lambda rec: rec.state == 'assigned' and not rec.contact_id
            )
        return LE.search([
            ('lot_id', '=', lot.id),
            ('state', '=', 'assigned'),
            ('contact_id', '=', False),
        ])

    def _get_lot_assigned_license_lines(self, lot):
        """Todas las license.equipment activas en este serial (equipo y/o usuario en el PC)."""
        LE = self._license_equipment_model()
        if LE is None or not lot:
            return None if LE is None else LE.browse()
        return LE.search([
            ('lot_id', '=', lot.id),
            ('state', '=', 'assigned'),
        ])

    def _get_user_license_lines_for_removal(self):
        """Licencias retirables del usuario (pestaña Licencias del Usuario)."""
        self.ensure_one()
        if self.search_mode != 'user' or not self.contact_id:
            return self.env['license.equipment'].browse()
        lines = self._discover_user_license_lines()
        if not lines and self.user_license_discovery_ids:
            lines = self.user_license_discovery_ids
        return lines.filtered(lambda l: l.state == 'assigned' and l.contact_id)

    def _action_inactivate_flow_start(self):
        """Inicia inactivación: equipos (opcional) → licencias por equipo → licencias usuario → archivar."""
        self.ensure_one()
        self._check_retiro_consulta_ready()
        lots = self._lots_for_user_return_candidates()
        if lots:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Devolución de equipos'),
                'res_model': 'mesa.retiro.inactivate.equipment.prompt.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_retiro_wizard_id': self.id,
                    'active_id': self.id,
                    'active_model': 'mesa.service.retiro.usuario.equipo.wizard',
                },
            }
        return self._action_inactivate_user_license_prompt()

    def _action_inactivate_user_license_prompt(self):
        """¿Retirar licencias del usuario? (tras equipos/licencias de equipo)."""
        self.ensure_one()
        lines = self._discover_user_license_lines()
        if lines:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Licencias del usuario'),
                'res_model': 'mesa.retiro.inactivate.user.license.prompt.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_retiro_wizard_id': self.id,
                    'active_id': self.id,
                    'active_model': 'mesa.service.retiro.usuario.equipo.wizard',
                },
            }
        return self._finalize_inactivate_user()

    def _inactivate_actions_summary_text(self, unlink_user_done, equipment_ticket=False):
        """Texto corto de acciones para el ticket de inactivación (sin devolución de equipo)."""
        self.ensure_one()
        parts = []
        if equipment_ticket:
            parts.append(
                _('Devolución de %s equipo(s) — ticket %s')
                % (len(self.user_return_lot_ids), equipment_ticket.display_name)
            )
        elif self.user_return_lot_ids:
            parts.append(
                _('Devolución de %s equipo(s) (caso aparte)') % len(self.user_return_lot_ids)
            )
        else:
            parts.append(_('Sin devolución de equipos'))
        n_eq_lic = len(self.user_return_license_line_ids)
        n_user_lic = len(self.user_tab_license_line_ids)
        if n_eq_lic:
            parts.append(_('Retiro de %s licencia(s) de equipo') % n_eq_lic)
        if n_user_lic:
            parts.append(_('Retiro de %s licencia(s) del usuario') % n_user_lic)
        if not n_eq_lic and not n_user_lic:
            parts.append(_('Sin retiro de licencias'))
        parts.append(_('Contacto archivado'))
        return '; '.join(parts)

    def _create_inactivate_equipment_return_ticket(self, permanencia_lots, unlink_user_done):
        """Ticket aparte de devolución de equipo (igual que retiro por usuario habitual)."""
        self.ensure_one()
        if not self.user_return_lot_ids:
            return self.env['helpdesk.ticket'].browse()
        Ticket = self.env['helpdesk.ticket']
        ref = self._retiro_context_label()
        if unlink_user_done:
            result_txt = _('Retiro de Equipo')
        else:
            result_txt = _(
                'Sin usuario asignado en el alcance (sin cambios en inventario).'
            )
        body = self._retiro_ticket_body_html(result_txt, permanencia_lots)
        from odoo.addons.mesa_ayuda_inventario.wizard.acta_lot_detai