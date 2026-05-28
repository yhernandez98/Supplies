# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

# Guardados por _compute_show_on_lot_tabs; si write() solo toca estos campos, no volver a recomputar
# (Odoo 19 dispara write desde el __set__ del cómputo y reentrar provoca RecursionError).
_LICENSE_SHOW_TAB_FIELDS = frozenset({'show_on_lot_equipment_tab', 'show_on_lot_user_tab'})
_CTX_SKIP_RECOMPUTE_SHOW_TABS = 'skip_recompute_show_tabs'


class LicenseEquipment(models.Model):
    _name = 'license.equipment'
    _description = 'Asignación de Licencia a Equipo'
    _order = 'assignment_id, lot_id'

    assignment_id = fields.Many2one(
        'license.assignment',
        string='Asignación de Licencia',
        required=True,
        ondelete='cascade',
        index=True,
        domain="[('id', 'in', available_assignment_ids)]"
    )
    license_id = fields.Many2one(
        'license.template',
        related='assignment_id.license_id',
        string='Licencia',
        store=True,
        readonly=True
    )
    # Campos para visibilidad en vista (desde configuración de la licencia)
    license_applies_to_equipment = fields.Boolean(
        related='license_id.applies_to_equipment',
        string='Licencia aplica a equipo',
        readonly=True
    )
    license_applies_to_user = fields.Boolean(
        related='license_id.applies_to_user',
        string='Licencia aplica a usuario',
        readonly=True
    )
    partner_id = fields.Many2one(
        'res.partner',
        related='assignment_id.partner_id',
        string='Cliente',
        store=True,
        readonly=True
    )
    contracting_type = fields.Selection(
        related='assignment_id.contracting_type',
        string='Tipo de Contratación',
        store=False,
        readonly=True
    )
    contact_id = fields.Many2one(
        'res.partner',
        string='Contacto',
        required=False,
        domain="[('parent_id', '=', partner_id), ('is_company', '=', False)]",
        help='Contacto relacionado de la empresa al que se asigna la licencia (opcional)'
    )
    location_id = fields.Many2one(
        'stock.location',
        related='assignment_id.location_id',
        string='Ubicación',
        store=True,
        readonly=True
    )
    lot_id = fields.Many2one(
        'stock.lot',
        string='Equipo (Lote/Serie)',
        required=False,
        domain="[('id', 'in', available_lot_ids)]",
        help='Equipo específico al que se asigna la licencia (opcional). Solo muestra equipos con categoría COMPUTO.'
    )
    available_lot_ids = fields.Many2many(
        'stock.lot',
        string='Lotes Disponibles',
        compute='_compute_available_lot_ids',
        store=False,
        help='Lotes disponibles en la ubicación del cliente'
    )
    available_assignment_ids = fields.Many2many(
        'license.assignment',
        string='Asignaciones Disponibles',
        compute='_compute_available_assignment_ids',
        store=False,
        help='Asignaciones disponibles según cliente/ubicación y tipo de pestaña (equipo/usuario).',
    )
    product_id = fields.Many2one(
        'product.product',
        related='lot_id.product_id',
        string='Producto del Equipo',
        store=True,
        readonly=True
    )
    inventory_plate = fields.Char(
        related='lot_id.inventory_plate',
        string='Placa de Inventario',
        store=True,
        readonly=True,
        help='Placa de inventario del equipo asignado'
    )
    # Usuario asignado: si hay equipo (lot_id), muestra el Usuario del lote (related_partner_id); si no, el contacto de la línea
    assigned_partner_id = fields.Many2one(
        'res.partner',
        string='Asignado',
        compute='_compute_assigned_partner_id',
        store=True,
        readonly=True,
        help='Usuario del equipo (desde el lote) o contacto asignado a la licencia'
    )
    assigned_name_display = fields.Char(
        string='Asignado',
        compute='_compute_assigned_name_display',
        store=False,
        readonly=True,
        help='Nombre del usuario asignado sin prefijo de empresa.'
    )
    # Equipo a mostrar: si hay lot_id lo muestra; si es fila de usuario (contact_id), muestra el equipo relacionado al usuario (lote con related_partner_id = contact_id)
    display_lot_id = fields.Many2one(
        'stock.lot',
        string='Equipo',
        compute='_compute_display_lot_id',
        store=True,
        readonly=True,
        help='Equipo de la línea o equipo relacionado al usuario asignado'
    )
    service_product_id = fields.Many2one(
        'product.product',
        related='license_id.product_id',
        string='Servicio',
        store=True,
        readonly=True,
        help='Servicio asociado a la licencia (ej: Microsoft 365 Empresa Estándar)'
    )
    assignment_date = fields.Date(
        string='Fecha de Asignación',
        required=True,
        help='Debe coincidir con la fecha de inicio del contrato.'
    )
    unassignment_date = fields.Date(string='Fecha de Desasignación')
    assignment_end_date = fields.Date(
        related='assignment_id.end_date',
        string='Fecha de Fin (contrato)',
        readonly=True,
        help='Fecha de terminación del contrato de la asignación.'
    )
    state = fields.Selection([
        ('assigned', 'Asignado'),
        ('unassigned', 'Desasignado'),
    ], string='Estado', default='assigned', required=True)
    notes = fields.Text(string='Notas')

    # Visibilidad en pestañas del serial (stock.lot): dominios One2many no filtran bien campos related
    # no almacenados; estos booleanos almacenados fijan qué filas ve cada pestaña.
    show_on_lot_equipment_tab = fields.Boolean(
        string='Ver en pestaña Licencias del Equipo',
        compute='_compute_show_on_lot_tabs',
        store=True,
        help='Falso para licencias de usuario en el mismo serial o filas duplicadas sin contacto.',
    )
    show_on_lot_user_tab = fields.Boolean(
        string='Ver en pestaña Licencias del Usuario',
        compute='_compute_show_on_lot_tabs',
        store=True,
    )
    
    # Campo computed para indicar el tipo de asignación
    assignment_type = fields.Selection([
        ('user', 'Por Usuario'),
        ('equipment', 'Por Equipo'),
        ('both', 'Por Usuario y Equipo'),
    ], string='Tipo de Asignación',
       compute='_compute_assignment_type',
       store=False,
       help='Indica si la licencia está asignada por usuario, por equipo, o ambos')
    
    @api.depends('contact_id', 'contact_id.name', 'lot_id', 'lot_id.related_partner_id', 'lot_id.related_partner_id.name')
    def _compute_assigned_partner_id(self):
        """Muestra el usuario del equipo (related_partner_id del lote) o el contacto de la línea."""
        for rec in self:
            if rec.lot_id and getattr(rec.lot_id, 'related_partner_id', None):
                rec.assigned_partner_id = rec.lot_id.related_partner_id
            else:
                rec.assigned_partner_id = rec.contact_id

    @api.depends('contact_id', 'contact_id.name', 'lot_id', 'lot_id.related_partner_id', 'lot_id.related_partner_id.name')
    def _compute_assigned_name_display(self):
        """Muestra solo el nombre del usuario (sin 'Empresa, Usuario')."""
        for rec in self:
            partner = False
            if rec.lot_id and getattr(rec.lot_id, 'related_partner_id', None):
                partner = rec.lot_id.related_partner_id
            elif rec.contact_id:
                partner = rec.contact_id
            rec.assigned_name_display = partner.name if partner else ''

    @api.depends('contact_id', 'lot_id')
    def _compute_display_lot_id(self):
        """Muestra el equipo de la línea.

        Si la fila es de usuario y no trae lot_id, intenta resolver un equipo del usuario
        dentro del alcance de la asignación (cliente/ubicación) para evitar vacíos visuales.
        """
        for rec in self:
            if rec.lot_id:
                rec.display_lot_id = rec.lot_id
            elif rec.contact_id and hasattr(self.env['stock.lot'], 'related_partner_id'):
                lot_domain = [('related_partner_id', '=', rec.contact_id.id)]
                lot = self.env['stock.lot']

                # Preferir equipo dentro de la ubicación de la asignación (si existe)
                if rec.assignment_id and rec.assignment_id.location_id:
                    quant = self.env['stock.quant'].search(
                        [
                            ('lot_id.related_partner_id', '=', rec.contact_id.id),
                            ('location_id', 'child_of', rec.assignment_id.location_id.id),
                            ('quantity', '>', 0),
                        ],
                        order='in_date desc, id desc',
                        limit=1,
                    )
                    if quant and quant.lot_id:
                        lot = quant.lot_id

                if not lot:
                    lot = self.env['stock.lot'].search(lot_domain, limit=1, order='id desc')

                rec.display_lot_id = lot
            else:
                rec.display_lot_id = False

    @api.depends('contact_id', 'lot_id')
    def _compute_assignment_type(self):
        """Calcula el tipo de asignación según si hay usuario, equipo o ambos"""
        for rec in self:
            has_user = bool(rec.contact_id)
            has_equipment = bool(rec.lot_id)
            
            if has_user and has_equipment:
                rec.assignment_type = 'both'
            elif has_user:
                rec.assignment_type = 'user'
            elif has_equipment:
                rec.assignment_type = 'equipment'
            else:
                # Si no hay ni usuario ni equipo, dejar vacío (None)
                rec.assignment_type = None

    @api.model
    def _equipment_tab_lines_for_lot(self, lot):
        """Reglas únicas para «Licencias del Equipo» (serial stock.lot).

        Solo filas sin contacto, licencia solo-equipo (no aplica a usuario), y sin fila
        «fantasma» duplicada (misma asignación ya cubierta por línea de usuario en el serial).
        """
        if not lot:
            return self.browse()
        lines = self.search([('lot_id', '=', lot.id), ('state', '=', 'assigned')])
        user_assign = set()
        for ul in lines.filtered(lambda r: r.contact_id):
            if ul.license_id and ul.license_id.applies_to_user and ul.assignment_id:
                user_assign.add(ul.assignment_id.id)
        out = self.browse()
        for rec in lines:
            if rec.contact_id:
                continue
            lic = rec.license_id
            if not lic:
                continue
            if not lic.applies_to_equipment:
                continue
            if lic.applies_to_user:
                continue
            if rec.assignment_id and rec.assignment_id.id in user_assign:
                continue
            out |= rec
        return out

    @api.model
    def _user_tab_lines_for_lot(self, lot):
        """Licencias de usuario visibles en la ficha del serial.

        Reflejo de lo ya asignado al **contacto** «Usuario» del serial en el módulo de licencias:
        todas las líneas activas tipo usuario para ese contacto, **sin exigir** que el serial
        coincida. Así, si el usuario cambia de PC, la lista se actualiza sola; quitar el usuario
        del serial solo vacía la vista (no borra asignaciones).
        """
        if not lot or not getattr(lot, 'related_partner_id', None):
            return self.browse()
        rp = lot.related_partner_id.id
        lines = self.search([
            ('contact_id', '=', rp),
            ('state', '=', 'assigned'),
        ])
        return self._filter_user_tab_license_lines(lines)

    @api.model
    def _partner_person_name_key(self, partner):
        """Nombre de persona sin prefijo de empresa (p. ej. «BLINDEX, Sandra» → «sandra»)."""
        if not partner:
            return ''
        for attr in ('name', 'display_name'):
            name = (getattr(partner, attr, None) or '').strip()
            if not name:
                continue
            if ',' in name:
                name = name.split(',')[-1].strip()
            return name.lower()
        return ''

    @api.model
    def _user_license_contact_ids(self, contact, partner=None):
        """IDs de contacto equivalentes al usuario del retiro/consulta."""
        if not contact:
            return []
        ids = set(contact.ids)
        contact_key = self._partner_person_name_key(contact)
        Partner = self.env['res.partner'].sudo()

        # Mismo nombre bajo el cliente (evita duplicados «Sandra» id 343 vs id 500).
        if partner:
            commercial = partner.commercial_partner_id
            people_domain = [
                ('is_company', '=', False),
                '|', '|',
                ('parent_id', '=', partner.id),
                ('parent_id', 'child_of', commercial.id),
                ('id', 'child_of', commercial.id),
            ]
            for person in Partner.search(people_domain):
                if person.id in ids:
                    continue
                pk = self._partner_person_name_key(person)
                if contact_key and pk and (contact_key == pk or contact_key in pk or pk in contact_key):
                    ids.add(person.id)
        elif contact.parent_id:
            for person in Partner.search([
                ('parent_id', '=', contact.parent_id.id),
                ('is_company', '=', False),
            ]):
                pk = self._partner_person_name_key(person)
                if contact_key and pk and (contact_key == pk or contact_key in pk or pk in contact_key):
                    ids.add(person.id)

        Lot = self.env['stock.lot'].sudo()
        if 'related_partner_id' not in Lot._fields:
            return list(ids)
        lot_domain = [('related_partner_id', '!=', False)]
        if partner:
            commercial = partner.commercial_partner_id
            lot_domain += [
                '|',
                ('customer_id.commercial_partner_id', '=', commercial.id),
                ('related_partner_id.commercial_partner_id', '=', commercial.id),
            ]
        for lot in Lot.search(lot_domain):
            rp = lot.related_partner_id
            if not rp:
                continue
            if rp.id in ids:
                continue
            if contact.commercial_partner_id and rp.commercial_partner_id != contact.commercial_partner_id:
                continue
            rp_key = self._partner_person_name_key(rp)
            if contact_key and rp_key and (contact_key == rp_key or contact_key in rp_key or rp_key in contact_key):
                ids.add(rp.id)
        # Contactos que ya tienen licencias asignadas bajo este cliente (fuente de verdad).
        if partner:
            commercial = partner.commercial_partner_id
            for eq in self.sudo().search([
                ('state', '=', 'assigned'),
                ('contact_id', '!=', False),
                '|',
                ('partner_id', '=', commercial.id),
                ('partner_id.commercial_partner_id', '=', commercial.id),
            ]):
                rk = self._partner_person_name_key(eq.contact_id)
                if contact_key and rk and (contact_key == rk or contact_key in rk or rk in contact_key):
                    ids.add(eq.contact_id.id)
        return list(ids)

    @api.model
    def _user_tab_assigned_lines_for_lot_user(self, lot):
        """Líneas asignadas al usuario del serial, sin filtrar ``applies_to_user`` (retiro)."""
        if not lot or not getattr(lot, 'related_partner_id', None):
            return self.browse()
        return self.sudo().search([
            ('contact_id', '=', lot.related_partner_id.id),
            ('state', '=', 'assigned'),
        ])

    @api.model
    def _filter_user_tab_license_lines(self, lines):
        """Misma visibilidad que la pestaña «Licencias del Usuario» en stock.lot."""
        return lines.filtered(
            lambda r: r.state == 'assigned'
            and (
                (r.license_id and r.license_id.applies_to_user)
                or getattr(r, 'show_on_lot_user_tab', False)
            )
        )

    @api.model
    def _user_tab_lines_for_contact(self, contact, partner=None):
        """Licencias de usuario de un contacto (misma regla que la pestaña del serial).

        Usa todos los contactos equivalentes (wizard vs. ``related_partner_id`` en seriales)
        y ``assigned_partner_id`` almacenado, sin filtrar por ubicación ni partner de línea.
        """
        if not contact:
            return self.browse()
        contact_ids = self._user_license_contact_ids(contact, partner=partner)
        lines = self.search([
            ('state', '=', 'assigned'),
            '|', '|',
            ('contact_id', 'in', contact_ids),
            ('assigned_partner_id', 'in', contact_ids),
            ('lot_id.related_partner_id', 'in', contact_ids),
        ])
        Lot = self.env['stock.lot'].sudo()
        if 'related_partner_id' in Lot._fields:
            for lot in Lot.search([('related_partner_id', 'in', contact_ids)]):
                lines |= self._user_tab_lines_for_lot(lot)
        return self._filter_user_tab_license_lines(lines).browse(sorted(set(lines.ids)))

    @api.model
    def _user_tab_lines_for_retiro(self, contact, partner=None):
        """Licencias de usuario retirables (mesa de ayuda / tickets).

        Diferencia frente a equipo (``_equipment_tab_lines_for_lot``):
        - Equipo: ``lot_id`` + ``contact_id`` vacío + licencia solo-hardware.
        - Usuario: ``contact_id`` obligatorio; ``lot_id`` puede ir vacío o con el PC actual.

        No exige ``applies_to_user`` en la plantilla: si la fila tiene contacto asignado
        y está activa, es licencia de usuario para retiro (evita desajustes de plantilla).
        """
        if not contact:
            return self.browse()
        contact_ids = self._user_license_contact_ids(contact, partner=partner)
        Lot = self.env['stock.lot'].sudo()
        lines = self.browse()

        # 1) Por contacto directo (líneas «solo usuario» o «usuario + equipo»).
        lines |= self.sudo().search([
            ('state', '=', 'assigned'),
            ('contact_id', 'in', contact_ids),
        ])

        # 2) Por cada serial del cliente con usuario equivalente (usa related_partner del lote).
        if 'related_partner_id' in Lot._fields:
            lot_domain = [('related_partner_id', 'in', contact_ids)]
            if partner:
                commercial = partner.commercial_partner_id
                lot_domain = [
                    ('related_partner_id', '!=', False),
                    '|',
                    ('customer_id.commercial_partner_id', '=', commercial.id),
                    ('related_partner_id.commercial_partner_id', '=', commercial.id),
                ]
                ck = self._partner_person_name_key(contact)
                for lot in Lot.search(lot_domain):
                    rp = lot.related_partner_id
                    if rp.id in contact_ids:
                        lines |= self._user_tab_assigned_lines_for_lot_user(lot)
                    elif ck:
                        pk = self._partner_person_name_key(rp)
                        if pk and (ck == pk or ck in pk or pk in ck):
                            lines |= self._user_tab_assigned_lines_for_lot_user(lot)
            else:
                for lot in Lot.search([('related_partner_id', 'in', contact_ids)]):
                    lines |= self._user_tab_assigned_lines_for_lot_user(lot)

        # 3) Asignaciones activas del cliente: grilla «Usuarios» (contact_id, lot_id opcional).
        if partner:
            commercial = partner.commercial_partner_id
            Assignment = self.env['license.assignment'].sudo()
            assign_domain = [
                ('state', '=', 'active'),
                '|',
                ('partner_id', '=', commercial.id),
                ('partner_id.commercial_partner_id', '=', commercial.id),
            ]
            for assignment in Assignment.search(assign_domain):
                for eq in assignment.equipment_ids:
                    if eq.state != 'assigned' or not eq.contact_id:
                        continue
                    if eq.contact_id.id in contact_ids:
                        lines |= eq
                        continue
                    ck = self._partner_person_name_key(contact)
                    rk = self._partner_person_name_key(eq.contact_id)
                    if ck and rk and (ck == rk or ck in rk or rk in ck):
                        lines |= eq

        # 4) Respaldo: mismo cliente, contacto con nombre equivalente (p. ej. id distinto en Odoo).
        if partner and not lines:
            commercial = partner.commercial_partner_id
            ck = self._partner_person_name_key(contact)
            if ck:
                broad = self.sudo().search([
                    ('state', '=', 'assigned'),
                    ('contact_id', '!=', False),
                    '|',
                    ('partner_id', '=', commercial.id),
                    ('partner_id.commercial_partner_id', '=', commercial.id),
                ])
                for eq in broad:
                    rk = self._partner_person_name_key(eq.contact_id)
                    if rk and (ck == rk or ck in rk or rk in ck):
                        lines |= eq

        return lines.filtered(lambda r: r.contact_id).browse(sorted(set(lines.ids)))

    @api.model
    def _contact_matches_user(self, person, ref_contact):
        """True si el contacto de la línea es el mismo usuario que el del retiro."""
        if not person or not ref_contact:
            return False
        if person.id == ref_contact.id:
            return True
        ck = self._partner_person_name_key(ref_contact)
        pk = self._partner_person_name_key(person)
        return bool(ck and pk and (ck == pk or ck in pk or pk in ck))

    @api.model
    def _contacts_for_retiro_user(self, contact, partner=None):
        """Contactos equivalentes al usuario del retiro (mismo cliente comercial)."""
        if not contact:
            return self.env['res.partner'].browse()
        partner = partner or contact.parent_id
        commercial = (
            partner.commercial_partner_id
            if partner else contact.commercial_partner_id
        )
        Partner = self.env['res.partner'].sudo()
        candidates = Partner.browse(list(set(contact.ids)))
        if commercial:
            candidates |= Partner.search([
                ('is_company', '=', False),
                ('commercial_partner_id', '=', commercial.id),
            ])
        if partner:
            candidates |= Partner.search([
                ('is_company', '=', False),
                ('parent_id', '=', partner.id),
            ])
        matched = candidates.filtered(
            lambda p: self._contact_matches_user(p, contact)
        )
        return (matched | contact)

    @api.model
    def _license_env(self):
        """ORM sin restricciones de compañía (asignaciones M365 pueden estar en otra company)."""
        companies = self.env['res.company'].sudo().search([]).ids
        return self.sudo().with_context(
            active_test=False,
            allowed_company_ids=companies,
        )

    @api.model
    def _assignment_env(self):
        companies = self.env['res.company'].sudo().search([]).ids
        return self.env['license.assignment'].sudo().with_context(
            active_test=False,
            allowed_company_ids=companies,
        )

    @api.model
    def _line_belongs_to_client(self, eq, commercial, partner=None):
        """True si la línea pertenece al cliente del retiro (vía asignación o partner almacenado)."""
        if not eq or not commercial:
            return False
        if eq.assignment_id and eq.assignment_id.partner_id:
            ap = eq.assignment_id.partner_id
            if ap.commercial_partner_id == commercial or ap.id == commercial.id:
                return True
            if partner and ap.id == partner.id:
                return True
        if eq.partner_id:
            if eq.partner_id.commercial_partner_id == commercial:
                return True
            if partner and eq.partner_id.id == partner.id:
                return True
        return False

    @api.model
    def _active_assignments_for_client(self, commercial, partner=None):
        """Asignaciones activas del cliente (árbol de partners + respaldo por id exacto)."""
        Assignment = self._assignment_env()
        if not commercial:
            return Assignment.browse()
        domain = [
            ('state', '=', 'active'),
            ('partner_id', 'child_of', commercial.id),
        ]
        assignments = Assignment.search(domain)
        if partner:
            assignments |= Assignment.search([
                ('state', '=', 'active'),
                '|',
                ('partner_id', '=', partner.id),
                ('partner_id.commercial_partner_id', '=', commercial.id),
            ])
        return assignments

    @api.model
    def _user_license_lines_from_license_module(self, contact, partner=None):
        """Licencias de usuario vía ``license.equipment`` / ``license.assignment`` (pestaña Usuarios)."""
        if not contact:
            return self.browse()
        partner = partner or contact.parent_id
        commercial = (
            partner.commercial_partner_id
            if partner else contact.commercial_partner_id
        )
        if not commercial:
            return self.browse()
        LE = self._license_env()
        contact_ids = self._user_license_contact_ids(contact, partner=partner)
        if contact.id not in contact_ids:
            contact_ids.append(contact.id)
        lines = LE.browse()

        def _active_user_lines(records):
            return records.filtered(
                lambda eq: eq.state == 'assigned' and eq.contact_id
            )

        # 1) Por contacto(s) equivalentes; filtrar cliente en Python (no depender de partner_id en línea).
        for eq in LE.search([
            ('state', '=', 'assigned'),
            ('contact_id', 'in', contact_ids),
        ]):
            if self._line_belongs_to_client(eq, commercial, partner):
                lines |= eq

        # 2) Grilla «Usuarios» de asignaciones activas del cliente.
        for assignment in self._active_assignments_for_client(commercial, partner):
            for eq in assignment.equipment_ids:
                if eq.state != 'assigned' or not eq.contact_id:
                    continue
                if eq.contact_id.id in contact_ids or self._contact_matches_user(
                    eq.contact_id, contact
                ):
                    lines |= eq

        # 3) Mismo cliente: equivalencia de nombre en líneas de las asignaciones activas.
        if not lines:
            for assignment in self._active_assignments_for_client(commercial, partner):
                for eq in assignment.equipment_ids:
                    if eq.state == 'assigned' and eq.contact_id and self._contact_matches_user(
                        eq.contact_id, contact
                    ):
                        lines |= eq

        # 4) Respaldo por tokens del nombre (apellido, p. ej. LONDONO).
        if not lines and contact.name:
            tokens = {t for t in contact.name.split() if len(t) >= 4}
            key = self._partner_person_name_key(contact)
            if key:
                tokens.add(key.split()[-1])
            Partner = self.env['res.partner'].sudo()
            extra_ids = set()
            for token in tokens:
                extra_ids.update(Partner.search([
                    ('is_company', '=', False),
                    ('commercial_partner_id', '=', commercial.id),
                    ('name', 'ilike', token),
                ]).ids)
                for eq in LE.search([
                    ('state', '=', 'assigned'),
                    ('contact_id', '!=', False),
                    ('contact_id.name', 'ilike', token),
                ], limit=80):
                    if self._contact_matches_user(eq.contact_id, contact):
                        if self._line_belongs_to_client(eq, commercial, partner):
                            lines |= eq
            if extra_ids:
                for eq in LE.search([
                    ('state', '=', 'assigned'),
                    ('contact_id', 'in', list(extra_ids)),
                ]):
                    if self._line_belongs_to_client(eq, commercial, partner):
                        lines |= eq

        return _active_user_lines(lines).browse(sorted(set(lines.ids)))

    @api.model
    def _user_tab_lines_inventory_mirror(self, contact, partner=None):
        """Réplica agregada de ``stock.lot.license_user_ids`` para mesa de ayuda / retiro."""
        if not contact:
            return self.browse()
        contact_ids = self._user_license_contact_ids(contact, partner=partner)
        if not contact_ids:
            return self.browse()
        Lot = self.env['stock.lot'].sudo()
        lines = self.browse()
        ck = self._partner_person_name_key(contact)

        lot_domain = []
        if partner:
            commercial = partner.commercial_partner_id
            lot_domain = [
                '|',
                ('customer_id.commercial_partner_id', '=', commercial.id),
                ('related_partner_id.commercial_partner_id', '=', commercial.id),
            ]
        for lot in Lot.search(lot_domain):
            rp = lot.related_partner_id
            if not rp:
                continue
            if rp.id not in contact_ids:
                pk = self._partner_person_name_key(rp)
                if not (ck and pk and (ck == pk or ck in pk or pk in ck)):
                    continue
            lines |= self._user_tab_lines_for_lot(lot)
            lines |= self._user_tab_assigned_lines_for_lot_user(lot)

        lines |= self.sudo().search([
            ('state', '=', 'assigned'),
            ('contact_id', 'in', contact_ids),
        ])
        if 'show_on_lot_user_tab' in self._fields:
            lines |= self.sudo().search([
                ('state', '=', 'assigned'),
                ('show_on_lot_user_tab', '=', True),
                ('contact_id', 'in', contact_ids),
            ])
        return lines.filtered(lambda r: r.contact_id).browse(sorted(set(lines.ids)))

    @api.model
    def _invalidate_stock_lot_user_tab_for_partners(self, partners):
        """Al cambiar licencias de usuario, refrescar el Many2many calculado en stock.lot."""
        partners = partners.filtered(lambda p: p)
        if not partners:
            return
        Lot = self.env['stock.lot']
        if 'related_partner_id' not in Lot._fields:
            return
        lots = Lot.search([('related_partner_id', 'in', partners.ids)])
        if lots:
            lots.invalidate_recordset(['license_user_ids'])

    @api.depends(
        'state',
        'lot_id',
        'contact_id',
        'assignment_id',
        'license_id',
        'license_id.applies_to_equipment',
        'license_id.applies_to_user',
    )
    def _compute_show_on_lot_tabs(self):
        """Separa filas entre pestañas Equipo / Usuario en la ficha del serial.

        Debe coincidir con _equipment_tab_lines_for_lot / _user_tab_lines_for_lot.
        """
        lots = self.mapped('lot_id').filtered(lambda l: l)
        eq_sets = {}
        user_sets = {}
        for lot in lots:
            eq_sets[lot.id] = set(self._equipment_tab_lines_for_lot(lot).ids)
            user_sets[lot.id] = set(self._user_tab_lines_for_lot(lot).ids)
        for rec in self:
            rec.show_on_lot_equipment_tab = False
            rec.show_on_lot_user_tab = False
            if not rec.lot_id:
                continue
            lid = rec.lot_id.id
            if rec.id in eq_sets.get(lid, set()):
                rec.show_on_lot_equipment_tab = True
            if rec.id in user_sets.get(lid, set()):
                rec.show_on_lot_user_tab = True

    @api.model
    def _recompute_show_tabs_for_lot_ids(self, lot_ids):
        lot_ids = [x for x in set(lot_ids or []) if x]
        if not lot_ids:
            return
        lines = self.