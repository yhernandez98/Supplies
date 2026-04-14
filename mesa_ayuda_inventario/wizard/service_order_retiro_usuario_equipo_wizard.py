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
        string='Quitar usuario del equipo',
        default=True,
        help='Limpia el usuario asignado en el serial (related_partner_id) y lo propaga a componentes '
             'vinculados según la configuración de inventario. Las licencias no se modifican salvo que '
             'marque la opción siguiente.',
    )
    client_requests_license_removal = fields.Boolean(
        string='El cliente solicita retirar/cancelar licencias',
        default=False,
        help='Si está marcado, se aplican acciones según el tipo de contratación en Licenciamientos '
             '(license.assignment): Mensual mensual → se elimina la línea de asignación al equipo/usuario; '
             'Anual / Anual compromiso mensual → solo desasignación (el cupo del contrato se mantiene, '
             'como en el módulo de licencias).',
    )

    relation_info_html = fields.Html(
        string='Información relacionada',
        compute='_compute_relation_info_html',
        sanitize=False,
        readonly=True,
    )

    @api.model
    def _lots_for_partner_locations(self, partner):
        """Lotes principales por cliente, priorizando placas con inventario."""
        Lot = self.env['stock.lot']
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
            rec.lot_id = False
            plate = (rec.inventory_plate or '').strip()
            if not rec.partner_id or not plate:
                continue
            candidates = rec.allowed_lot_ids.filtered(
                lambda l: (l.inventory_plate or '').strip().lower() == plate.lower()
            )
            if len(candidates) == 1:
                rec.lot_id = candidates
            elif len(candidates) > 1:
                # Si el wizard se abrió desde un serial/lote, priorizar ese registro.
                if rec.origin_model == 'stock.lot' and rec.origin_id:
                    origin = rec.env['stock.lot'].browse(rec.origin_id)
                    if origin in candidates:
                        rec.lot_id = origin
                        continue

                # Con duplicados, elegir el candidato con más información relacionada.
                def score(lot):
                    lic_count = 0
                    supply_count = 0
                    user_score = 0
                    if hasattr(lot, 'license_equipment_ids'):
                        lic_count = len(lot.license_equipment_ids.filtered(lambda l: l.state == 'assigned'))
                    if hasattr(lot, 'lot_supply_line_ids'):
                        supply_count = len(lot.lot_supply_line_ids)
                    if hasattr(lot, 'related_partner_id') and lot.related_partner_id:
                        user_score = 1
                    return (lic_count, supply_count, user_score, lot.id)

                rec.lot_id = sorted(candidates, key=score, reverse=True)[0]

    @api.depends(
        'search_mode',
        'partner_id',
        'lot_id',
        'contact_id',
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
            parts.extend(self._html_block_supply_lines(self.lot_id))
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
        lic_count = len(self._get_equipment_license_payload(partner, lot))
        with_cost, no_cost = self._get_supply_lines_split(lot)
        user_name = ''
        if lot and hasattr(lot, 'related_partner_id') and lot.related_partner_id:
            user_name = lot.related_partner_id.name or ''
        items = [
            (_('Cliente'), partner.display_name if partner else ''),
            (_('Placa'), (lot.inventory_plate if lot else '') or ''),
            (_('Serial'), (lot.name if lot else '') or ''),
            (_('Usuario'), user_name),
            (_('Licencias del equipo'), str(lic_count)),
            (_('Elementos con costo'), str(len(with_cost))),
            (_('Elementos sin costo'), str(len(no_cost))),
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

    def _html_block_exec_summary_user(self, partner, contact):
        payload = self._get_user_license_payload(partner, contact)
        lic_count = len(payload)
        lots = self._lots_for_user_all(partner, contact)
        items = [
            (_('Cliente'), partner.display_name if partner else ''),
            (_('Usuario'), contact.name if contact else ''),
            (_('Equipos asociados'), str(len(lots))),
            (_('Licencias del usuario'), str(lic_count)),
        ]
        return self._html_exec_box(_('Resumen ejecutivo (usuario)'), items)

    def _html_exec_box(self, title, items):
        parts = [
            Markup('<div style="padding:10px 12px;border:1px solid #b8d8ea;background:linear-gradient(180deg,#f5fcff 0%%,#eef8ff 100%%);border-radius:8px;margin-bottom:10px;">'),
            Markup('<p style="margin:0 0 8px 0;color:#134b6f;"><strong>%s</strong></p>') % escape(title),
            Markup('<table style="width:100%;border-collapse:collapse;font-size:13px;background:#fff;border:1px solid #e3edf3;">'),
        ]
        for label, value in items:
            parts.append(
                Markup('<tr><td style="width:32%%;padding:5px 8px;border-bottom:1px solid #edf3f7;background:#f9fcff;"><strong>%s</strong></td>'
                       '<td style="padding:5px 8px;border-bottom:1px solid #edf3f7;">%s</td></tr>')
                % (escape(label), escape(value or _('No definido')))
            )
        parts.extend([Markup('</table>'), Markup('</div>')])
        return parts

    def _license_equipment_model(self):
        # 1) Ruta estándar (requiere módulo subscription_licenses instalado y dependencia declarada)
        try:
            return self.env['license.equipment']
        except KeyError:
            pass

        # 2) Desde campos en stock.lot (por si el nombre del modelo cambiara)
        lot_model = self.env['stock.lot']
        for fname in ('license_equipment_ids', 'license_user_ids'):
            field = lot_model._fields.get(fname)
            comodel = getattr(field, 'comodel_name', False) if field else False
            if comodel:
                try:
                    return self.env[comodel]
                except KeyError:
                    continue

        # 3) ir.model (último recurso)
        im = self.env['ir.model'].sudo().search([('model', '=', 'license.equipment')], limit=1)
        if im:
            try:
                return self.env[im.model]
            except KeyError:
                pass
        return None

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
        """Filas para tabla licencias de equipo (sin mezclar usuario)."""
        LE = self._license_equipment_model()
        if LE and lot:
            lines = self._get_equipment_license_lines(lot) or LE.browse([])
            out = []
            for line in lines:
                serv = line.service_product_id.display_name if getattr(line, 'service_product_id', False) else ''
                lic = line.license_id.display_name if line.license_id else ''
                out.append({
                    'service': serv,
                    'license': lic,
                    'contracting_type': self._contracting_type_label(line),
                    'contract_state': line.assignment_id.state if line.assignment_id else '',
                })
            if out:
                return out
        names = self._fallback_equipment_license_names_from_lot(lot)
        names = self._filter_name_list_excluding_user_licenses_for_lot(partner, lot, names)
        return [
            {
                'service': n,
                'license': n,
                'contracting_type': '',
                'contract_state': '',
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

    def _get_user_license_payload(self, partner, contact):
        """Solo licencias de usuario (pestaña Usuario), no las de equipo."""
        lines = self._get_user_license_lines(partner, contact)
        if lines is not None:
            lines = self._dedupe_user_license_lines_for_display(lines, contact)
            out = []
            for line in lines:
                lot_label = ''
                lot = self._user_license_line_lot(line)
                if lot:
                    lot_label = lot.inventory_plate or lot.name or ''
                out.append({
                    'service': line.service_product_id.display_name if getattr(line, 'service_product_id', False) else '',
                    'license': line.license_id.display_name if line.license_id else '',
                    'contracting_type': self._contracting_type_label(line),
                    'equipment': lot_label,
                })
            return out

        # Sin modelo: agrupar por nombre de licencia (no por lote); equipo = lote principal entre los candidatos.
        buckets = defaultdict(lambda: {'label': None, 'lots': []})
        for lot in self._lots_for_user_all(partner, contact):
            user_txt = (getattr(lot, 'mesa_user_only_licenses_list_display', '') or '').strip()
            if not user_txt:
                continue
            for part in self._split_license_name_parts(user_txt):
                norm = (part or '').strip().lower()
                if not norm:
                    continue
                b = buckets[norm]
                b['lots'].append(lot)
                if b['label'] is None:
                    b['label'] = part
        payload = []
        for norm in sorted(buckets.keys()):
            b = buckets[norm]
            primary = self._pick_primary_lot_for_user_license(b['lots'], contact)
            payload.append({
                'service': '',
                'license': b['label'] or norm,
                'contracting_type': '',
                'equipment': self._lot_heading(primary) if primary else '',
            })
        return payload

    def _get_user_license_lines(self, partner, contact):
        """Registros license.equipment de tipo usuario (contacto), no solo equipo."""
        LE = self._license_equipment_model()
        if not LE or not contact:
            return LE.browse([]) if LE else None
        lines = LE.browse([])
        Lot = self.env['stock.lot']

        lots_domain = [('related_partner_id', '=', contact.id)]
        if partner:
            lots_domain = [
                ('related_partner_id', '=', contact.id),
                '|',
                ('customer_id.commercial_partner_id', '=', partner.id),
                ('related_partner_id.commercial_partner_id', '=', partner.id),
            ]
        user_lots = Lot.search(lots_domain)

        # 1) Misma fuente que la pestaña "Licencias del Usuario" en stock.lot.
        for lot in user_lots:
            if hasattr(lot, 'license_user_ids'):
                lines |= lot.license_user_ids.filtered(lambda l: l.state == 'assigned')

            location_partner_id, lot_location_id = self._get_license_scope_data_for_lot(lot)
            domain = [
                ('contact_id', '=', contact.id),
                ('state', '=', 'assigned'),
            ]
            if location_partner_id:
                domain.append(('partner_id', '=', location_partner_id))
            if lot_location_id:
                domain.append(('location_id', '=', lot_location_id))
            lines |= LE.search(domain)

        # 2) Búsqueda global por contacto (sin traer filas solo de equipo).
        domain_global = [('contact_id', '=', contact.id), ('state', '=', 'assigned')]
        if partner:
            domain_global = [
                ('contact_id', '=', contact.id),
                ('state', '=', 'assigned'),
                '|',
                ('partner_id', '=', partner.id),
                ('partner_id.commercial_partner_id', '=', partner.id),
            ]
        lines |= LE.search(domain_global)

        # 3) Asignaciones agrupadas: solo líneas con contacto = usuario (no filas solo equipo).
        if 'license.assignment' in self.env:
            Assignment = self.env['license.assignment']
            assign_domain = [('state', '=', 'active')]
            if partner:
                assign_domain += [
                    '|',
                    ('partner_id', '=', partner.id),
                    ('partner_id.commercial_partner_id', '=', partner.id),
                ]
            for assignment in Assignment.search(assign_domain):
                lines |= assignment.equipment_ids.filtered(
                    lambda l: l.state == 'assigned'
                    and l.contact_id
                    and l.contact_id.id == contact.id
                )

        # Quitar duplicados y filas que solo son de equipo (sin contacto en la línea).
        lines = lines.filtered(lambda l: l.contact_id and l.contact_id.id == contact.id)
        lines = lines.browse(sorted(set(lines.ids)))
        return lines

    def _contracting_type_label(self, line):
        assignment = getattr(line, 'assignment_id', False)
        if not assignment:
            return ''
        val = assignment.contracting_type
        if not val:
            return ''
        sel = assignment._fields['contracting_type'].selection
        pairs = sel(assignment) if callable(sel) else (sel or [])
        return dict(pairs).get(val, val)

    def _get_equipment_license_lines(self, lot):
        LE = self._license_equipment_model()
        if not LE or not lot:
            return LE.browse([]) if LE else None
        if hasattr(lot, 'license_equipment_ids'):
            return lot.license_equipment_ids.filtered(
                lambda rec: rec.state == 'assigned' and not rec.contact_id
            )
        return LE.search([
            ('lot_id', '=', lot.id),
            ('state', '=', 'assigned'),
            ('contact_id', '=', False),
        ])

    def _get_all_assigned_license_lines_for_lot(self, lot):
        """Todas las asignaciones activas en el lote (pestaña equipo y pestaña usuario)."""
        LE = self._license_equipment_model()
        if not LE or not lot:
            return LE.browse([]) if LE else None
        lines = LE.browse([])
        if hasattr(lot, 'license_equipment_ids'):
            lines |= lot.license_equipment_ids.filtered(lambda l: l.state == 'assigned')
        if hasattr(lot, 'license_user_ids'):
            lines |= lot.license_user_ids.filtered(lambda l: l.state == 'assigned')
        return lines

    def _lot_has_renting_permanencia(self, lot):
        """True si el plazo de renting implica permanencia (no es «Sin permanencia»)."""
        if not lot:
            return False
        plazo = getattr(lot, 'reining_plazo', None)
        if not plazo:
            return False
        if plazo == 'sin_permanencia':
            return False
        return True

    def _lots_for_permanencia_check(self):
        """Lotes a revisar para la advertencia de permanencia."""
        self.ensure_one()
        if self.search_mode == 'inventory':
            return self.lot_id
        return self._lots_for_user_all(self.partner_id, self.contact_id)

    def _get_assigned_license_lines_for_current_wizard(self):
        """Líneas license.equipment a desasignar según el modo del wizard."""
        self.ensure_one()
        LE = self._license_equipment_model()
        if not LE:
            try:
                return self.env['license.equipment'].browse([])
            except KeyError:
                return None
        if self.search_mode == 'inventory':
            inv_lines = self._get_all_assigned_license_lines_for_lot(self.lot_id)
            return inv_lines if inv_lines is not None else LE.browse([])
        lines = self._get_user_license_lines(self.partner_id, self.contact_id)
        if lines is None:
            return LE.browse([])
        return lines

    def _clear_user_from_equipment_lots(self):
        """Quita related_partner_id del equipo (modo placa) o de todos los equipos del usuario en el cliente."""
        self.ensure_one()
        Lot = self.env['stock.lot']
        if self.search_mode == 'inventory':
            lot = self.lot_id
            if lot and getattr(lot, 'related_partner_id', False):
                lot.write({'related_partner_id': False})
                return True
            return False
        contact = self.contact_id
        partner = self.partner_id
        if not contact:
            return False
        domain = [
            ('related_partner_id', '=', contact.id),
            ('is_main_product', '=', True),
        ]
        lots = Lot.search(domain)
        if partner:
            lots = lots.filtered(
                lambda l: (
                    (l.customer_id and l.customer_id.commercial_partner_id.id == partner.id)
                    or (
                        l.related_partner_id
                        and l.related_partner_id.commercial_partner_id.id == partner.id
                    )
                    or not l.customer_id
                )
            )
        for lot in lots:
            lot.write({'related_partner_id': False})
        return bool(lots)

    def _apply_client_license_cancellation(self, lines):
        """Retira licencias según contracting_type del módulo subscription_licenses (license.assignment)."""
        self.ensure_one()
        if not lines:
            return {'count': 0, 'detail_lines': []}
        today = fields.Date.context_today(self)
        detail_lines = []
        count = 0
        for rid in tuple(lines.ids):
            rec = self.env['license.equipment'].browse(rid)
            if not rec.exists() or rec.state != 'assigned':
                continue
            lic_name = rec.license_id.display_name if rec.license_id else _('Licencia')
            ctype = rec.contracting_type or ''
            type_label = self._contracting_type_label(rec) or ctype or _('No definido')

            if ctype == 'monthly_monthly':
                rec.unlink()
                detail_lines.append(
                    _('%s (%s): eliminada la asignación (mensual mensual; puede ajustar cantidad en la asignación si aplica).')
                    % (lic_name, type_label)
                )
                count += 1
            elif ctype in ('annual_monthly_commitment', 'annual'):
                rec.write({'unassignment_date': today, 'state': 'unassigned'})
                detail_lines.append(
                    _(
                        '%s (%s): desasignada; la cantidad contratada se mantiene hasta el fin del periodo '
                        '(licencia reasignable a otro equipo/usuario, coherente con el módulo de licencias).'
                    )
                    % (lic_name, type_label)
                )
                count += 1
            else:
                rec.write({'unassignment_date': today, 'state': 'unassigned'})
                detail_lines.append(
                    _('%s (%s): desasignada (tipo de contratación no estándar o vacío).')
                    % (lic_name, type_label)
                )
                count += 1
        return {'count': count, 'detail_lines': detail_lines}

    def _create_followup_ticket_and_activity(
        self,
        permanencia_lots,
        lic_names_detected,
        unlink_user_done,
        cancel_licenses,
        license_removal_count,
        license_removal_detail_lines,
    ):
        """Crea helpdesk.ticket + mail.activity (tarea) con descripción y advertencias."""
        self.ensure_one()
        partner = self.partner_id
        Ticket = self.env['helpdesk.ticket']
        assignee = self.env.user

        scoped = self._lots_for_permanencia_check()
        first_lot = scoped[:1]
        lot_id = first_lot.id if first_lot else False

        if self.search_mode == 'inventory':
            title = _('Retiro / consulta por equipo: %s') % (
                (self.lot_id.inventory_plate or self.lot_id.name or '')[:80],
            )
        else:
            title = _('Retiro / consulta por usuario: %s — %s') % (
                (partner.name or '')[:40],
                (self.contact_id.name or '')[:40],
            )

        lic_names = list(dict.fromkeys([n for n in (lic_names_detected or []) if n]))[:30]

        warn_html = ''
        if permanencia_lots:
            items = []
            for lot in permanencia_lots:
                plazo = getattr(lot, 'reining_plazo', '') or ''
                sel = lot._fields.get('reining_plazo') and lot._fields['reining_plazo'].selection
                pairs = sel(lot) if callable(sel) else (sel or [])
                plazo_label = dict(pairs).get(plazo, plazo) if plazo else ''
                items.append(
                    '<li>%s — %s: <strong>%s</strong></li>'
                    % (
                        escape(self._lot_heading(lot)),
                        escape(_('Plazo renting')),
                        escape(plazo_label or _('(definido)')),
                    )
                )
            warn_html = (
                '<div style="background:#fff8e6;border-left:4px solid #f0ad4e;padding:12px 14px;margin:12px 0;">'
                '<p style="margin:0 0 8px 0;font-weight:700;color:#856404;">%s</p>'
                '<p style="margin:0 0 8px 0;">%s</p><ul style="margin:0;padding-left:18px;">%s</ul></div>'
            ) % (
                escape(_('Advertencia: permanencia de renting')),
                escape(_(
                    'Uno o más equipos tienen plazo de renting distinto de «Sin permanencia». '
                    'Revise condiciones contractuales antes de completar el retiro físico o cambios definitivos.'
                )),
                Markup(''.join(items)),
            )

        action_parts = []
        if unlink_user_done:
            action_parts.append(
                '<p><strong>%s</strong> %s</p>'
                % (escape(_('Usuario en equipo:')), escape(_('desvinculado del serial (y componentes según inventario).')))
            )
        else:
            action_parts.append(
                '<p class="text-muted"><strong>%s</strong> %s</p>'
                % (escape(_('Usuario en equipo:')), escape(_('no se modificó (opción desmarcada).')))
            )

        if cancel_licenses:
            if license_removal_count and license_removal_detail_lines:
                det = ''.join('<li>%s</li>' % escape(d) for d in license_removal_detail_lines[:40])
                action_parts.append(
                    '<p><strong>%s</strong> (%s)</p><ul>%s</ul>'
                    % (
                        escape(_('Licencias — retiro solicitado por el cliente')),
                        escape(_('%s registro(s)') % license_removal_count),
                        det,
                    )
                )
            elif license_removal_count == 0:
                action_parts.append(
                    '<p class="text-muted">%s</p>'
                    % escape(_('Se marcó retiro de licencias, pero no había líneas asignadas en este alcance.'))
                )
        else:
            if lic_names:
                action_parts.append(
                    '<p><strong>%s</strong></p><ul>%s</ul>'
                    % (
                        escape(_('Licencias detectadas (se mantienen; el cliente no solicitó cancelación):')),
                        ''.join('<li>%s</li>' % escape(n) for n in lic_names),
                    )
                )
            else:
                action_parts.append(
                    '<p class="text-muted">%s</p>'
                    % escape(_('Licencias: sin líneas asignadas en este alcance o sin módulo de licencias.'))
                )

        lic_block = ''.join(action_parts)

        sm_sel = self._fields['search_mode'].selection
        sm_pairs = sm_sel(self) if callable(sm_sel) else (sm_sel or [])
        mode_label = dict(sm_pairs).get(self.search_mode, self.search_mode)

        body = Markup(
            '<div style="padding:4px 0;">'
            '<p>%s</p>'
            '<p><strong>%s</strong> %s<br/>'
            '<strong>%s</strong> %s</p>'
            '%s'
            '%s'
            '</div>'
        ) % (
            escape(_('Registro generado desde el wizard Retiro de Usuario/Equipo (Mesa de Ayuda).')),
            escape(_('Modo:')),
            escape(mode_label),
            escape(_('Cliente:')),
            escape(partner.display_name if partner else ''),
            Markup(warn_html),
            Markup(lic_block),
        )

        ticket_vals = {
            'name': title[:200],
            'partner_id': partner.id if partner else False,
            'description': body,
            'lot_id': lot_id,
            'user_id': assignee.id,
            'maintenance_category': 'change',
        }
        ticket = Ticket.create(ticket_vals)

        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        model_rec = self.env['ir.model'].sudo().search([('model', '=', 'helpdesk.ticket')], limit=1)
        if activity_type and model_rec:
            self.env['mail.activity'].create({
                'res_model_id': model_rec.id,
                'res_id': ticket.id,
                'activity_type_id': activity_type.id,
                'summary': _('Seguimiento retiro/consulta — %s') % (partner.name or '')[:120],
                'note': _('Revisar ticket y trazabilidad de licencias/equipo.'),
                'user_id': assignee.id,
                'date_deadline': fields.Date.context_today(self),
            })

        ticket.message_post(
            body=_('Actividad creada automáticamente junto con el registro de consulta/retiro.'),
            subject=_('Tarea de seguimiento'),
        )
        return ticket

    def _lots_for_user_licenses(self, partner, contact):
        lines = self._get_user_license_lines(partner, contact)
        if lines is None:
            return self.env['stock.lot'].browse([])
        lots = lines.mapped('lot_id') | lines.mapped('display_lot_id')
        return lots.filtered(lambda l: l)

    def _lots_for_user_all(self, partner, contact):
        Lot = self.env['stock.lot']
        lots = Lot
        if contact:
            lots |= Lot.search([('related_partner_id', '=', contact.id), ('is_main_product', '=', True)])
        lots |= self._lots_for_user_licenses(partner, contact)
        if partner:
            lots = lots.filtered(
                lambda l: (
                    (hasattr(l, 'customer_id') and l.customer_id and l.customer_id.commercial_partner_id.id == partner.id)
                    or (hasattr(l, 'related_partner_id') and l.related_partner_id and l.related_partner_id.commercial_partner_id.id == partner.id)
                    or not getattr(l, 'customer_id', False)
                )
            )
        return lots.sorted(key=lambda l: ((l.inventory_plate or '').lower(), (l.name or '').lower(), l.id))

    def _html_block_supply_lines(self, lot):
        parts = []
        if not lot:
            parts.append(
                Markup('<h4 class="mt-3">%s</h4><p class="text-muted">%s</p>')
                % (escape(_('Elementos asociados al equipo')), escape(_('Sin líneas de suministro en este equipo.')))
            )
            return parts

        if hasattr(lot, 'lot_supply_line_con_costo_ids') and hasattr(lot, 'lot_supply_line_sin_costo_ids'):
            # Usa las mismas relaciones de las pestañas "Elementos Con Costo" y "Elementos Sin Costo".
            with_cost = lot.lot_supply_line_con_costo_ids
            no_cost = lot.lot_supply_line_sin_costo_ids
        elif hasattr(lot, 'lot_supply_line_ids'):
            with_cost = lot.lot_supply_line_ids.filtered(lambda s: s.has_cost)
            no_cost = lot.lot_supply_line_ids.filtered(lambda s: not s.has_cost)
        else:
            with_cost = self.env['stock.lot.supply.line']
            no_cost = self.env['stock.lot.supply.line']

        # Fallback robusto: si no llegaron líneas por relaciones, buscar directamente en el modelo.
        # Esto cubre casos donde el serial tiene líneas asociadas pero no están precargadas en las
        # relaciones calculadas del lote en este contexto.
        if not with_cost and not no_cost:
            SupplyLine = self.env['stock.lot.supply.line']
            direct_lines = SupplyLine.search([('lot_id', '=', lot.id)])
            if not direct_lines:
                # Último fallback: líneas donde este serial aparece como related_lot_id.
                direct_lines = SupplyLine.search([('related_lot_id', '=', lot.id)])
            with_cost = direct_lines.filtered(lambda s: s.has_cost)
            no_cost = direct_lines.filtered(lambda s: not s.has_cost)

        def render_lines(lines, section_title):
            if not lines:
                return []
            block = [Markup('<h4 class="mt-3">%s</h4>') % escape(section_title)]
            block.append(Markup(
                '<table style="width:100%;border-collapse:collapse;font-size:13px;background:#fff;border:1px solid #eceff3;">'
                '<thead><tr>'
                '<th style="text-align:left;padding:6px 8px;border-bottom:1px solid #d9d9d9;background:#f5f8fb;">Producto</th>'
                '<th style="text-align:left;padding:6px 8px;border-bottom:1px solid #d9d9d9;background:#f5f8fb;">Tipo de producto</th>'
                '<th style="text-align:left;padding:6px 8px;border-bottom:1px solid #d9d9d9;background:#f5f8fb;">Serial/Placa</th>'
                '<th style="text-align:left;padding:6px 8px;border-bottom:1px solid #d9d9d9;background:#f5f8fb;">Detalle</th>'
                '</tr></thead><tbody>'
            ))
            for sl in lines:
                prod = sl.product_id.display_name if sl.product_id else ''
                prod_type = (
                    getattr(getattr(sl.product_id, 'asset_class_id', False), 'name', '')
                    if sl.product_id else ''
                )
                serial = sl.related_lot_id.name if sl.related_lot_id else ''
                plate = sl.related_lot_id.inventory_plate if sl.related_lot_id else ''
                SupplyLine = sl.env['stock.lot.supply.line']
                field_sel = SupplyLine._fields['item_type'].selection
                if callable(field_sel):
                    sel_pairs = field_sel(SupplyLine)
                else:
                    sel_pairs = field_sel or []
                tipo = dict(sel_pairs).get(sl.item_type, sl.item_type or '')
                cost_txt = ''
                if sl.has_cost:
                    cost_txt = _('Costo: %s') % (sl.cost or 0.0)
                extra = ', '.join(x for x in (tipo, cost_txt) if x)
                block.append(
                    Markup('<tr><td style="padding:5px 8px;border-bottom:1px solid #efefef;">%s</td>'
                           '<td style="padding:5px 8px;border-bottom:1px solid #efefef;">%s</td>'
                           '<td style="padding:5px 8px;border-bottom:1px solid #efefef;">%s</td>'
                           '<td style="padding:5px 8px;border-bottom:1px solid #efefef;">%s</td></tr>')
                    % (
                        escape(prod),
                        escape(prod_type or _('No definido')),
                        escape(plate or serial or ''),
                        escape(extra or ''),
                    )
                )
            block.append(Markup('</tbody></table>'))
            return block

        parts.extend(
            render_lines(with_cost, _('Elementos asociados con costo'))
        )
        parts.extend(
            render_lines(no_cost, _('Elementos asociados sin costo'))
        )
        if not parts:
            parts.append(Markup('<p class="text-muted">%s</p>') % escape(_('Sin elementos asociados en este equipo.')))
        return parts

    def _get_supply_lines_split(self, lot):
        SupplyLine = self.env['stock.lot.supply.line']
        if not lot:
            return SupplyLine, SupplyLine
        if hasattr(lot, 'lot_supply_line_con_costo_ids') and hasattr(lot, 'lot_supply_line_sin_costo_ids'):
            with_cost = lot.lot_supply_line_con_costo_ids
            no_cost = lot.lot_supply_line_sin_costo_ids
        elif hasattr(lot, 'lot_supply_line_ids'):
            with_cost = lot.lot_supply_line_ids.filtered(lambda s: s.has_cost)
            no_cost = lot.lot_supply_line_ids.filtered(lambda s: not s.has_cost)
        else:
            with_cost = SupplyLine
            no_cost = SupplyLine
        return with_cost, no_cost

    @api.onchange('search_mode')
    def _onchange_search_mode(self):
        for rec in self:
            rec.lot_id = False
            rec.inventory_plate = False
            rec.partner_id = False
            rec.contact_id = False

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        for rec in self:
            rec.lot_id = False
            rec.inventory_plate = False
            rec.contact_id = False

    def _check_retiro_consulta_ready(self):
        """Validaciones previas (mismas que Continuar antes de registrar)."""
        self.ensure_one()
        if self.search_mode == 'inventory':
            if not self.partner_id:
                raise UserError(_('Debe seleccionar un cliente.'))
            if not self.inventory_plate:
                raise UserError(_('Digite la placa de inventario.'))
            if not self.lot_id:
                raise UserError(_('Seleccione un equipo por placa de inventario.'))
            allowed = self._lots_for_partner_locations(self.partner_id)
            if self.lot_id not in allowed:
                raise UserError(
                    _('El equipo seleccionado no pertenece al cliente o no tiene stock en la ubicación del cliente.')
                )
        elif self.search_mode == 'user':
            if not self.partner_id:
                raise UserError(_('Debe seleccionar un cliente.'))
            if not self.contact_id:
                raise UserError(_('Debe seleccionar un usuario/contacto.'))
            if self.contact_id.parent_id != self.partner_id:
                raise UserError(_('El contacto debe pertenecer al cliente seleccionado.'))

    def action_register_followup(self):
        """Ticket + tarea; opcionalmente quita usuario del equipo; licencias solo si el cliente lo solicita."""
        self.ensure_one()
        if self.consultation_only:
            raise UserError(_(
                'Esta ventana es solo informativa. Para registrar retiro, ticket y tarea, use el menú «Retiro de Usuario/Equipo».'
            ))
        self._check_retiro_consulta_ready()
        license_lines = self._get_assigned_license_lines_for_current_wizard()
        if license_lines is None:
            LE = self._license_equipment_model()
            if not LE:
                raise UserError(_('No está disponible el modelo de licencias (license.equipment).'))
            license_lines = LE.browse([])
        lic_names_detected = license_lines.mapped('license_id.display_name')
        lots_all = self._lots_for_permanencia_check()
        permanencia_lots = lots_all.filtered(lambda l: self._lot_has_renting_permanencia(l))

        unlink_user_done = False
        if self.unlink_user_from_equipment:
            unlink_user_done = bool(self._clear_user_from_equipment_lots())

        cancel_licenses = bool(self.client_requests_license_removal)
        removal_count = 0
        removal_details = []
        if cancel_licenses:
            res = self._apply_client_license_cancellation(license_lines)
            removal_count = res['count']
            removal_details = res['detail_lines']

        ticket = self._create_followup_ticket_and_activity(
            permanencia_lots,
            lic_names_detected,
            unlink_user_done,
            cancel_licenses,
            removal_count,
            removal_details,
        )
        return {
            'type': 'ir.actions.act_window',
            'name': _('Ticket'),
            'res_model': 'helpdesk.ticket',
            'res_id': ticket.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_continue(self):
        """Continuar: registrar seguimiento (ticket, tarea, opciones de usuario y licencias)."""
        return self.action_register_followup()

    def action_debug_user_license_sources(self):
        self.ensure_one()
        if self.search_mode != 'user':
            raise UserError(_('El debug aplica solo en modo "Por usuario/cliente".'))
        if not self.partner_id or not self.contact_id:
            raise UserError(_('Seleccione cliente y usuario antes de ejecutar debug.'))

        LE = self._license_equipment_model()
        if not LE:
            fallback_payload = self._get_user_license_payload(self.partner_id, self.contact_id)
            msg = _(
                'DEBUG fallback (sin license.equipment)\\n'
                '- licencias detectadas en campos de stock.lot: %(count)s\\n'
                '- muestra: %(sample)s'
            ) % {
                'count': len(fallback_payload),
                'sample': ', '.join([x.get('license') or '' for x in fallback_payload[:8]]) or _('sin registros')
            }
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Debug licencias por usuario'),
                    'message': msg,
                    'sticky': True,
                    'type': 'warning',
                }
            }

        contact = self.contact_id
        partner = self.partner_id
        commercial_contact = contact.commercial_partner_id

        q_contact = LE.search_count([('state', '=', 'assigned'), ('contact_id', '=', contact.id)])
        q_lot_rel = LE.search_count([('state', '=', 'assigned'), ('lot_id.related_partner_id', '=', contact.id)])
        q_assigned = LE.search_count([('state', '=', 'assigned'), ('assigned_partner_id', '=', contact.id)])
        q_partner = LE.search_count([
            ('state', '=', 'assigned'),
            '|',
            ('partner_id', '=', partner.id),
            ('partner_id.commercial_partner_id', '=', partner.id),
        ])
        q_contact_commercial = 0
        if commercial_contact:
            q_contact_commercial = LE.search_count([
                ('state', '=', 'assigned'),
                '|', '|',
                ('contact_id.commercial_partner_id', '=', commercial_contact.id),
                ('lot_id.related_partner_id.commercial_partner_id', '=', commercial_contact.id),
                ('assigned_partner_id.commercial_partner_id', '=', commercial_contact.id),
            ])

        final_lines = self._get_user_license_lines(partner, contact)
        sample = ', '.join(
            ['%s[%s]' % (x.license_id.display_name or 'Lic', x.id) for x in final_lines[:8]]
        ) or _('sin registros')

        msg = _(
            'DEBUG licencias usuario\\n'
            '- contact_id exacto: %(q_contact)s\\n'
            '- lot.related_partner_id: %(q_lot_rel)s\\n'
            '- assigned_partner_id: %(q_assigned)s\\n'
            '- por cliente seleccionado: %(q_partner)s\\n'
            '- por commercial partner usuario: %(q_contact_commercial)s\\n'
            '- resultado final wizard: %(final)s\\n'
            '- muestra IDs/licencias: %(sample)s'
        ) % {
            'q_contact': q_contact,
            'q_lot_rel': q_lot_rel,
            'q_assigned': q_assigned,
            'q_partner': q_partner,
            'q_contact_commercial': q_contact_commercial,
            'final': len(final_lines),
            'sample': sample,
        }

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Debug licencias por usuario'),
                'message': msg,
                'sticky': True,
                'type': 'warning',
            }
        }


def escape(text):
    if text is None:
        return ''
    return html_lib.escape(str(text))
