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
        lines = self.search([('lot_id', 'in', lot_ids)])
        if lines:
            lines.with_context(**{_CTX_SKIP_RECOMPUTE_SHOW_TABS: True})._compute_show_on_lot_tabs()

    _unique_lot_assignment = models.Constraint(
        'unique(assignment_id, lot_id, state)',
        'Este equipo ya está asignado a esta licencia. Solo puede haber una asignación activa por equipo.',
    )

    @api.constrains('contact_id', 'license_id', 'state')
    def _check_unique_contact_license_assigned(self):
        """Un contacto no puede tener dos asignaciones activas del mismo tipo de licencia."""
        for rec in self:
            if rec.state == 'assigned' and rec.contact_id and rec.license_id:
                other = self.search([
                    ('contact_id', '=', rec.contact_id.id),
                    ('license_id', '=', rec.license_id.id),
                    ('state', '=', 'assigned'),
                    ('id', '!=', rec.id),
                ], limit=1)
                if other:
                    raise ValidationError(
                        _('Este contacto ya tiene una asignación activa de este tipo de licencia. No se puede duplicar.')
                    )

    @api.depends('location_id')
    def _compute_available_lot_ids(self):
        """Calcula los lotes disponibles en la ubicación del cliente con categoría COMPUTO"""
        for rec in self:
            rec.available_lot_ids = [(5, 0, 0)]  # Limpiar
            if rec.location_id:
                # Buscar categoría de activo "COMPUTO"
                computo_category = self.env['product.asset.category'].search([
                    ('name', '=', 'COMPUTO')
                ], limit=1)
                
                # Buscar lotes que tengan quants en la ubicación del cliente
                quants = self.env['stock.quant'].search([
                    ('location_id', 'child_of', rec.location_id.id),
                    ('lot_id', '!=', False),
                    ('quantity', '>', 0)
                ])
                
                # Filtrar lotes que tengan productos con categoría COMPUTO
                lot_ids = []
                for quant in quants:
                    if quant.lot_id and quant.lot_id.product_id:
                        product = quant.lot_id.product_id
                        # Verificar si el producto tiene categoría COMPUTO
                        if computo_category and product.asset_category_id and product.asset_category_id.id == computo_category.id:
                            if quant.lot_id.id not in lot_ids:
                                lot_ids.append(quant.lot_id.id)
                
                if lot_ids:
                    rec.available_lot_ids = [(6, 0, lot_ids)]

    @api.onchange('assignment_id')
    def _onchange_assignment_id(self):
        """Sincroniza contact_id según la pestaña (Equipo/Usuario) al cambiar asignación.

        Esto evita que una misma asignación quede visible en ambas pestañas.
        """
        if not self.assignment_id:
            return

        tab_type = self.env.context.get('license_tab_type')
        default_contact_id = self.env.context.get('default_contact_id')

        # partner_id y location_id se actualizan automáticamente por ser fields related.
        if tab_type == 'user':
            # En "Licencias del Usuario", el grid no debería requerir que el usuario elija
            # manualmente el contacto; lo tomamos del contexto (stock.lot -> related_partner_id).
            if default_contact_id:
                self.contact_id = default_contact_id
            elif self.lot_id and getattr(self.lot_id, 'related_partner_id', None):
                self.contact_id = self.lot_id.related_partner_id.id
            # Si no hay default/contacto, dejamos el valor actual (para permitir edición manual).
        elif tab_type == 'equipment':
            # En "Licencias del Equipo", la pestaña filtra por contact_id=False.
            self.contact_id = False
        else:
            # Fallback conservador
            self.contact_id = False

        # Recalcular lotes disponibles cuando cambia la asignación.
        self._compute_available_lot_ids()

    @api.depends('lot_id', 'contact_id')
    def _compute_available_assignment_ids(self):
        """Filtra asignaciones activas por cliente/ubicación y tipo (equipo/usuario)."""
        Assignment = self.env['license.assignment']
        for rec in self:
            rec.available_assignment_ids = [(5, 0, 0)]

            # Soportar edición inline desde stock.lot (usando contexto del tab)
            lot = rec.lot_id
            if not lot and self.env.context.get('default_lot_id'):
                lot = self.env['stock.lot'].browse(self.env.context.get('default_lot_id'))

            contact = rec.contact_id
            if not contact and self.env.context.get('default_contact_id'):
                contact = self.env['res.partner'].browse(self.env.context.get('default_contact_id'))

            tab_type = self.env.context.get('license_tab_type') or ''

            domain = [('state', '=', 'active')]

            # Filtrar por cliente/ubicación del serial (si tenemos lote)
            location_partner_id = False
            lot_location_id = False
            if lot and lot.exists():
                try:
                    if hasattr(lot, 'location_partner_id') and lot.location_partner_id:
                        location_partner_id = lot.location_partner_id.id
                except Exception:
                    pass
                # Preferir la ubicación directa del serial en formulario.
                try:
                    if hasattr(lot, 'location_id') and lot.location_id:
                        lot_location_id = lot.location_id.id
                except Exception:
                    pass
                try:
                    if not lot_location_id:
                        quant = self.env['stock.quant'].search([
                            ('lot_id', '=', lot.id),
                            ('quantity', '>', 0),
                        ], order='quantity desc, in_date desc', limit=1)
                        if quant and quant.location_id:
                            lot_location_id = quant.location_id.id
                except Exception:
                    pass

            # Regla segura: si estamos en contexto de serial y no se puede resolver
            # ni cliente ni ubicación, no exponer asignaciones para evitar mezclar clientes.
            if lot and not (location_partner_id or lot_location_id):
                rec.available_assignment_ids = Assignment.browse([])
                continue

            if location_partner_id:
                domain.append(('partner_id', '=', location_partner_id))
            if lot_location_id:
                domain.append(('location_id', '=', lot_location_id))

            # Tipo de licenciamiento según pestaña
            if tab_type == 'equipment':
                domain.append(('license_applies_to_equipment', '=', True))
                domain.append(('license_applies_to_user', '=', False))
            elif tab_type == 'user':
                domain.append(('license_applies_to_user', '=', True))
            else:
                # Fallback por datos de la línea
                if lot:
                    domain.append(('license_applies_to_equipment', '=', True))
                    domain.append(('license_applies_to_user', '=', False))
                elif contact:
                    domain.append(('license_applies_to_user', '=', True))

            rec.available_assignment_ids = Assignment.search(domain)

    @api.constrains('contact_id', 'lot_id', 'license_id', 'state')
    def _check_license_applies_to(self):
        """Exige Contacto o Equipo según la configuración de la licencia (applies_to_user / applies_to_equipment)."""
        for rec in self:
            if not rec.license_id or rec.state == 'unassigned':
                continue
            applies_eq = rec.license_id.applies_to_equipment
            applies_usr = rec.license_id.applies_to_user
            has_contact = bool(rec.contact_id)
            has_lot = bool(rec.lot_id)
            if applies_eq and not applies_usr:
                if not has_lot:
                    raise ValidationError(
                        _('La licencia "%s" está configurada solo para Equipo. Debe seleccionar un Equipo (Lote/Serie).')
                        % (rec.license_id.display_name or rec.license_id.code)
                    )
            elif applies_usr and not applies_eq:
                if not has_contact:
                    raise ValidationError(
                        _('La licencia "%s" está configurada solo para Usuario. Debe seleccionar un Contacto.')
                        % (rec.license_id.display_name or rec.license_id.code)
                    )
            elif applies_eq and applies_usr:
                if not has_contact and not has_lot:
                    raise ValidationError(
                        _('La licencia "%s" aplica para Equipo y Usuario. Debe indicar al menos un Contacto o un Equipo (Lote/Serie).')
                        % (rec.license_id.display_name or rec.license_id.code)
                    )
            else:
                if not has_contact and not has_lot:
                    raise ValidationError(
                        _('Configure la licencia "%s" en Licenciamientos: marque "Aplica para Equipo" y/o "Aplica para Usuario", e indique al menos un Contacto o un Equipo aquí.')
                        % (rec.license_id.display_name or rec.license_id.code)
                    )

    @api.constrains('contact_id', 'license_id', 'state')
    def _check_unique_contact_license(self):
        """Valida que no haya duplicados: mismo contacto + mismo tipo de licencia en estado assigned"""
        for rec in self:
            if rec.state == 'assigned' and rec.contact_id and rec.license_id:
                existing = self.search([
                    ('contact_id', '=', rec.contact_id.id),
                    ('license_id', '=', rec.license_id.id),
                    ('state', '=', 'assigned'),
                    ('id', '!=', rec.id)
                ], limit=1)
                if existing:
                    raise ValidationError(
                        _('El contacto %s ya tiene una asignación activa de la licencia %s. '
                          'No se puede crear una asignación duplicada.')
                        % (rec.contact_id.name, rec.license_id.name)
                    )

    @api.constrains('lot_id', 'location_id')
    def _check_lot_location(self):
        """Verifica que el lote esté en la ubicación del cliente"""
        bypass_route_scope = bool(self.env.context.get('force_license_location_id'))
        for rec in self:
            if rec.lot_id and rec.location_id:
                # Flujo de entregas por etapas: se permite preasignar desde Alistamiento
                # usando alcance del cliente/ubicación final (forzado por contexto).
                if bypass_route_scope:
                    continue
                # Verificar que el lote tenga quants en la ubicación
                quants = self.env['stock.quant'].search([
                    ('lot_id', '=', rec.lot_id.id),
                    ('location_id', 'child_of', rec.location_id.id),
                    ('quantity', '>', 0)
                ])
                if not quants:
                    raise ValidationError(
                        _('El equipo %s no se encuentra en la ubicación %s.')
                        % (rec.lot_id.name, rec.location_id.complete_name)
                    )

    @api.model
    def _create_unassignment_history_vals(self, records, source, unassignment_date=None,
                                         helpdesk_ticket_id=False, helpdesk_ticket_name=False):
        """Valores para archivar una fila antes de eliminarla del listado activo."""
        today = unassignment_date or fields.Date.context_today(self)
        state_unassigned = _('Desasignado')
        vals_list = []
        for rec in records:
            if not rec.exists():
                continue
            asign = rec.assignment_id.license_display_name if rec.assignment_id else ''
            if not asign and rec.assignment_id:
                asign = rec.assignment_id.display_name
            categoria = rec.license_id.display_name if rec.license_id else ''
            licencia = rec.service_product_id.display_name if rec.service_product_id else ''
            serial = rec.lot_id.name if rec.lot_id else ''
            assigned = rec.assigned_name_display if hasattr(rec, 'assigned_name_display') else ''
            if not assigned and rec.contact_id:
                assigned = rec.contact_id.name
            vals_list.append({
                'assignment_id': rec.assignment_id.id,
                'license_equipment_ref': rec.id,
                'license_id': rec.license_id.id if rec.license_id else False,
                'lot_id': rec.lot_id.id if rec.lot_id else False,
                'contact_id': rec.contact_id.id if rec.contact_id else False,
                'equipment_serial': serial,
                'assigned_name': assigned,
                'assignment_label': asign or licencia,
                'category_name': categoria,
                'license_product_name': licencia,
                'assignment_date': rec.assignment_date,
                'unassignment_date': rec.unassignment_date or today,
                'state_label': state_unassigned,
                'source': source,
                'helpdesk_ticket_id': helpdesk_ticket_id or 0,
                'helpdesk_ticket_name': helpdesk_ticket_name or False,
                'removed_by_id': self.env.user.id,
                'removed_at': fields.Datetime.now(),
            })
        return vals_list

    @api.model
    def _create_unassignment_history(self, records, source, unassignment_date=None,
                                     helpdesk_ticket_id=False, helpdesk_ticket_name=False):
        History = self.env['license.equipment.unassignment.history'].sudo()
        vals_list = self._create_unassignment_history_vals(
            records,
            source,
            unassignment_date=unassignment_date,
            helpdesk_ticket_id=helpdesk_ticket_id,
            helpdesk_ticket_name=helpdesk_ticket_name,
        )
        return History.create(vals_list) if vals_list else History.browse()

    def _unlink_duplicate_manual_unassignment_history(self, records):
        """Quita historial «Eliminación manual» duplicado cuando el retiro viene de Mesa de Ayuda."""
        History = self.env['license.equipment.unassignment.history'].sudo()
        for rec in records:
            if not rec.assignment_id:
                continue
            base_domain = [
                ('assignment_id', '=', rec.assignment_id.id),
                ('source', '=', 'manual_delete'),
            ]
            by_ref = list(base_domain) + [('license_equipment_ref', '=', rec.id)]
            dupes = History.search(by_ref)
            serial = rec.lot_id.name if rec.lot_id else False
            if serial:
                dupes |= History.search(
                    base_domain + [('equipment_serial', '=', serial)]
                )
            if dupes:
                dupes.unlink()

    def _mesa_retiro_history_exists(self, rec):
        History = self.env['license.equipment.unassignment.history'].sudo()
        if not rec.assignment_id:
            return False
        domain = [
            ('assignment_id', '=', rec.assignment_id.id),
            ('source', '=', 'mesa_retiro'),
            ('license_equipment_ref', '=', rec.id),
        ]
        if History.search(domain, limit=1):
            return True
        serial = rec.lot_id.name if rec.lot_id else False
        if serial:
            return bool(History.search(
                domain[:2] + [('equipment_serial', '=', serial)],
                limit=1,
            ))
        return False

    def remove_from_assignment_list(self, source='manual_delete', helpdesk_ticket_id=False,
                                   helpdesk_ticket_name=False):
        """Registra historial y elimina la fila (equivalente a Eliminar en la asignación)."""
        records = self.exists()
        if not records:
            return self.browse()
        if source == 'mesa_retiro':
            self._unlink_duplicate_manual_unassignment_history(records)
            self._create_unassignment_history(
                records,
                source,
                helpdesk_ticket_id=helpdesk_ticket_id,
                helpdesk_ticket_name=helpdesk_ticket_name,
            )
        elif source == 'manual_delete':
            to_log = records.filtered(lambda r: not self._mesa_retiro_history_exists(r))
            if to_log:
                self._create_unassignment_history(to_log, source)
        else:
            self._create_unassignment_history(
                records,
                source,
                helpdesk_ticket_id=helpdesk_ticket_id,
                helpdesk_ticket_name=helpdesk_ticket_name,
            )
        ctx = dict(
            self.env.context,
            skip_license_delete_notification=bool(helpdesk_ticket_id),
            license_skip_history_on_unlink=True,
        )
        records.with_context(**ctx).unlink()
        return True

    def action_unassign(self):
        """Desasigna el equipo de la licencia"""
        for rec in self:
            if rec.state == 'unassigned':
                continue
            rec.unassignment_date = fields.Date.today()
            rec.state = 'unassigned'
            # Mostrar mensaje informativo si es contrato anual
            if rec.assignment_id and rec.assignment_id.state == 'active':
                if rec.contracting_type in ('annual_monthly_commitment', 'annual'):
                    contracting_type_name = dict(rec.assignment_id._fields['contracting_type'].selection).get(rec.contracting_type, rec.contracting_type)
                    item_name = rec.lot_id.name if rec.lot_id else (rec.contact_id.name if rec.contact_id else _('elemento'))
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Asignación quitada'),
                            'message': _(
                                '✅ Se ha quitado la asignación del %s "%s" del listado.\n\n'
                                '📋 <strong>La cantidad de licencias (%d) se mantiene</strong> por el contrato "%s".\n\n'
                                '💡 Puedes asignar otro equipo o usuario en su lugar, pero la cantidad total de licencias no se reducirá durante el período del contrato.'
                            ) % (
                                _('equipo') if rec.lot_id else _('usuario'),
                                item_name,
                                rec.assignment_id.quantity,
                                contracting_type_name
                            ),
                            'type': 'warning',
                            'sticky': True,
                        }
                    }
    
    def unlink(self):
        """Historial de desasignación + aviso en contratos anuales al eliminar desde cualquier vista."""
        if not self.env.context.get('license_skip_history_on_unlink'):
            to_log = self.filtered(
                lambda r: r.state == 'assigned'
                and r.assignment_id
                and not self._mesa_retiro_history_exists(r)
            )
            if to_log:
                self._create_unassignment_history(to_log, 'manual_delete')

        lots = list(set(self.mapped('lot_id').ids))
        partners_before_unlink = self.mapped('contact_id')
        # Guardar información antes de eliminar para el mensaje
        items_to_delete = []
        for rec in self:
            if rec.assignment_id and rec.assignment_id.state == 'active':
                if rec.contracting_type in ('annual_monthly_commitment', 'annual'):
                    item_name = rec.lot_id.name if rec.lot_id else (rec.contact_id.name if rec.contact_id else _('elemento'))
                    item_type = _('equipo') if rec.lot_id else _('usuario')
                    items_to_delete.append({
                        'name': item_name,
                        'type': item_type,
                        'assignment': rec.assignment_id,
                        'contracting_type': rec.contracting_type,
                    })
        
        # Eliminar los registros
        result = super().unlink()
        self.env['license.equipment']._recompute_show_tabs_for_lot_ids(lots)
        self.env['license.equipment']._invalidate_stock_lot_user_tab_for_partners(partners_before_unlink)
        
        # Mostrar mensaje informativo si se eliminaron elementos en contratos anuales
        if items_to_delete and not self.env.context.get('skip_license_delete_notification'):
            # Agrupar por asignación para mostrar un mensaje por asignación
            assignments_info = {}
            for item in items_to_delete:
                assignment_id = item['assignment'].id
                if assignment_id not in assignments_info:
                    assignments_info[assignment_id] = {
                        'assignment': item['assignment'],
                        'contracting_type': item['contracting_type'],
                        'items': []
                    }
                assignments_info[assignment_id]['items'].append(item)
            
            # Mostrar un mensaje por cada asignación afectada
            for assignment_id, info in assignments_info.items():
                contracting_type_name = dict(info['assignment']._fields['contracting_type'].selection).get(info['contracting_type'], info['contracting_type'])
                items_text = ', '.join([f"{item['type']} \"{item['name']}\"" for item in info['items']])
                if len(info['items']) == 1:
                    item_text = info['items'][0]
                    message = _(
                        '✅ Se ha eliminado la asignación del %s "%s" del listado.\n\n'
                        '📋 <strong>La cantidad de licencias (%d) se mantiene</strong> por el contrato "%s".\n\n'
                        '💡 Puedes asignar otro equipo o usuario en su lugar, pero la cantidad total de licencias no se reducirá durante el período del contrato.'
                    ) % (
                        item_text['type'],
                        item_text['name'],
                        info['assignment'].quantity,
                        contracting_type_name
                    )
                else:
                    message = _(
                        '✅ Se han eliminado las asignaciones de: %s del listado.\n\n'
                        '📋 <strong>La cantidad de licencias (%d) se mantiene</strong> por el contrato "%s".\n\n'
                        '💡 Puedes asignar otros equipos o usuarios en su lugar, pero la cantidad total de licencias no se reducirá durante el período del contrato.'
                    ) % (
                        items_text,
                        info['assignment'].quantity,
                        contracting_type_name
                    )
                
                # Mostrar notificación (solo la primera para evitar spam)
                if assignment_id == list(assignments_info.keys())[0]:
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Asignaciones eliminadas'),
                            'message': message,
                            'type': 'warning',
                            'sticky': True,
                        }
                    }
        
        return result

    def action_open_delete_wizard(self):
        """Abre el wizard de confirmación para eliminar el equipo/usuario."""
        self.ensure_one()
        # Validar que el registro existe
        if not self.exists():
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('El registro ya no existe o fue eliminado.'),
                    'type': 'danger',
                    'sticky': True,
                }
            }
        # Guardar el ID antes de crear el wizard para evitar problemas de contexto
        equipment_id = self.id
        ctx = {
            'default_equipment_id': equipment_id,
            'active_id': equipment_id,
        }
        if self.lot_id:
            ctx['return_lot_id'] = self.lot_id.id
        elif self.env.context.get('active_model') == 'stock.lot' and self.env.context.get('active_id'):
            ctx['return_lot_id'] = self.env.context['active_id']
        for key in (
            'license_tab_type',
            'from_route_lot_editor',
            'force_license_partner_id',
            'force_license_location_id',
        ):
            if self.env.context.get(key):
                ctx[key] = self.env.context[key]
        return {
            'name': _('Confirmar Eliminación'),
            'type': 'ir.actions.act_window',
            'res_model': 'license.equipment.delete.warning.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': ctx,
        }

    def _default_assignment_date(self, assignment):
        """Fecha de asignación: inicio de contrato, o el día de hoy si se agrega después (ej. contrato en enero, agregó equipo el 27)."""
        today = fields.Date.context_today(self)
        if not assignment or not assignment.start_date:
            return today
        # Si hoy es posterior al inicio del contrato, usar hoy (día en que se asigna); si no, usar inicio del contrato
        return max(assignment.start_date, today)

    @api.model
    def default_get(self, fields_list):
        """Fecha de asignación = fecha de inicio del contrato, o hoy si se agrega después del inicio."""
        res = super().default_get(fields_list)
        assignment_id = self.env.context.get('default_assignment_id') or self.env.context.get('assignment_id')
        if assignment_id and 'assignment_date' in fields_list and 'assignment_date' not in res:
            assignment = self.env['license.assignment'].browse(assignment_id)
            res['assignment_date'] = self._default_assignment_date(assignment)
        elif 'assignment_date' in fields_list and 'assignment_date' not in res:
            res['assignment_date'] = fields.Date.context_today(self)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        """Sobrescribe create para actualizar fecha de inicio de la asignación cuando se asignan equipos/usuarios."""
        tab_type = self.env.context.get('license_tab_type')
        default_contact_id = self.env.context.get('default_contact_id')
        default_lot_id = self.env.context.get('default_lot_id')
        for vals in vals_list:
            if 'assignment_date' not in vals and vals.get('assignment_id'):
                assignment = self.env['license.assignment'].browse(vals['assignment_id'])
                vals['assignment_date'] = self._default_assignment_date(assignment)

            # Asegurar contact_id correcto según pestaña al crear inline desde stock.lot
            # (evita que el mismo registro "salga" en ambas grillas).
            if tab_type == 'user':
                if not vals.get('contact_id') and default_contact_id:
                    vals['contact_id'] = default_contact_id
                elif tab_type == 'user' and not vals.get('contact_id') and vals.get('lot_id'):
                    lot = self.env['stock.lot'].browse(vals['lot_id'])
                    if lot.exists() and getattr(lot, 'related_partner_id', None):
                        vals['contact_id'] = lot.related_partner_id.id
                # Si se crea desde la vista del serial, conservar ese serial en la asignación de usuario.
                # Esto permite que la columna "Equipo" se llene en Licenciamientos.
                if not vals.get('lot_id') and default_lot_id:
                    vals['lot_id'] = default_lot_id
            elif tab_type == 'equipment':
                # En equipo, por diseño la grilla usa contact_id=False.
                vals['contact_id'] = False
        records = super().create(vals_list)
        # Actualizar fecha de inicio de la asignación si es necesario
        for rec in records:
            rec._update_assignment_start_date()
        # Validar que equipos/usuarios no superen la cantidad de licencias de la asignación
        for assignment in records.mapped('assignment_id'):
            assignment._check_equipment_quantity()
        self.env['license.equipment']._recompute_show_tabs_for_lot_ids(records.mapped('lot_id').ids)
        self._invalidate_stock_lot_user_tab_for_partners(records.mapped('contact_id'))
        return records

    def write(self, vals):
        """Sobrescribe write para actualizar fecha de inicio de la asignación cuando se asignan equipos/usuarios."""
        # Guard anti-recursión: durante el cómputo de flags de pestañas, Odoo hace write()
        # de estos mismos campos; en ese caso NO aplicar sincronización por tab ni recomputar.
        if self.env.context.get(_CTX_SKIP_RECOMPUTE_SHOW_TABS) and set(vals).issubset(_LICENSE_SHOW_TAB_FIELDS):
            return super().write(vals)

        # Asegurar que el registro queda categorizado por pestaña
        # (evita que un registro creado/editarado desde "Equipo" quede con contact_id
        # y luego aparezca en "Usuario", o viceversa).
        tab_type = self.env.context.get('license_tab_type')
        default_contact_id = self.env.context.get('default_contact_id')
        default_lot_id = self.env.context.get('default_lot_id')
        if tab_type == 'equipment':
            vals['contact_id'] = False
        elif tab_type == 'user' and default_contact_id:
            vals['contact_id'] = default_contact_id
            if not vals.get('lot_id') and default_lot_id:
                vals['lot_id'] = default_lot_id

        lots_before = set(self.mapped('lot_id').ids)
        partners_before = self.mapped('contact_id')
        result = super().write(vals)
        # Evitar bucle: el cómputo almacenado asigna estos campos y cada asignación llama a write().
        if not set(vals).issubset(_LICENSE_SHOW_TAB_FIELDS) and not self.env.context.get(_CTX_SKIP_RECOMPUTE_SHOW_TABS):
            lots_touched = lots_before | set(self.mapped('lot_id').ids)
            self.env['license.equipment']._recompute_show_tabs_for_lot_ids(list(lots_touched))
        # Si se cambió assignment_date o state a 'assigned', actualizar fecha de inicio
        if 'assignment_date' in vals or (vals.get('state') == 'assigned'):
            for rec in self:
                rec._update_assignment_start_date()
        # Si cambió algo que afecta el conteo (equipos/usuarios), validar que no se exceda la cantidad de licencias
        if any(k in vals for k in ('assignment_id', 'contact_id', 'lot_id', 'state')):
            for assignment in self.mapped('assignment_id'):
                assignment._check_equipment_quantity()
        if not set(vals).issubset(_LICENSE_SHOW_TAB_FIELDS):
            self._invalidate_stock_lot_user_tab_for_partners(partners_before | self.mapped('contact_id'))
        return result

    def _update_assignment_start_date(self):
        """Actualiza la fecha de inicio de la asignación solo si aún no está definida.

        - Para contratos anuales, si la asignación NO tiene start_date, se toma la fecha
          del día que se asigna el primer equipo/usuario.
        - Si el usuario ya definió manualmente la fecha de inicio, NO se vuelve a tocar.
        """
        for rec in self:
            assignment = rec.assignment_id
            if not assignment:
                continue

            # Solo aplicar a contratos anuales
            if assignment.contracting_type not in ('annual_monthly_commitment', 'annual'):
                continue

            # Si ya hay fecha de inicio definida (por el usuario), no la tocamos
            if assignment.start_date:
                continue

            # Solo actualizar si este es el primer equipo/usuario asignado (no hay otros asignados antes)
            assigned_items = assignment.equipment_ids.filtered(
                lambda e: e.state == 'assigned' and e.assignment_date and e.id != rec.id
            )
            
            # Si este es el primer equipo/usuario asignado (no hay otros), usar su fecha de asignación
            if not assigned_items and rec.state == 'assigned' and rec.assignment_date:
                from dateutil.relativedelta import relativedelta
                assignment.start_date = rec.assignment_date
                # Calcular fecha de fin automáticamente (12 meses desde la fecha de inicio)
                assignment.end_date = rec.assignment_date + relativedelta(months=12) - relativedelta(days=1)

    def action_reassign(self):
        """Reasigna el equipo a la licencia"""
        for rec in self:
            if rec.state == 'assigned':
                continue
            # Validar que no haya duplicados antes de reasignar
            if rec.contact_id and rec.license_id:
                existing = self.search([
                    ('contact_id', '=', rec.contact_id.id),
                    ('license_id', '=', rec.license_id.id),
                    ('state', '=', 'assigned'),
                    ('id', '!=', rec.id)
                ], limit=1)
                if existing:
                    raise ValidationError(
                        _('El contacto %s ya tiene una asignación activa de la licencia %s. '
                          'No se puede reasignar esta asignación.')
                        % (rec.contact_id.name, rec.license_id.name)
                    )
            rec.unassignment_date = False
            rec.state = 'assigned'
            # Misma regla: inicio de contrato, o hoy si se reasigna después
            rec.assignment_date = self._default_assignment_date(rec.assignment_id)
            # Actualizar fecha de inicio de la asignación
            rec._update_assignment_start_date()

    def _license_equipment_display_label(self):
        """Etiqueta legible (misma lógica que columna Asignación en Licencias del Equipo)."""
        self.ensure_one()
        if self.assignment_id:
            label = self.assignment_id.license_display_name
            if not label:
                label = self.assignment_id.display_name
            if label:
                return label
        if self.service_product_id:
            return self.service_product_id.display_name
        if self.license_id:
            category = self.license_id.name.name if self.license_id.name else ''
            product = self.license_id.product_id.display_name if self.license_id.product_id else ''
            if category and product:
                return '%s - %s' % (category, product)
            return product or category or self.license_id.code or ''
        return _('Licencia #%s') % self.id

    @api.depends(
        'assignment_id',
        'assignment_id.license_display_name',
        'assignment_id.license_display_name_stored',
        'assignment_id.contracting_type',
        'license_id',
        'license_id.name',
        'license_id.product_id',
        'license_id.code',
        'service_product_id',
        'service_product_id.display_name',
        'state',
    )
    @api.depends_context('mesa_retiro_license_select')
    def _compute_display_name(self):
        """Odoo 19: many2many_checkboxes y búsquedas usan display_name, no name_get."""
        state_finfo = self._fields['state']
        if hasattr(state_finfo, '_description_selection'):
            state_labels = dict(state_finfo._description_selection(self.env))
        else:
            state_labels = dict(state_finfo.selection or [])
        contracting_labels = {}
        Assignment = self.env['license.assignment']
        if 'contracting_type' in Assignment._fields:
            ctype_finfo = Assignment._fields['contracting_type']
            if hasattr(ctype_finfo, '_description_selection'):
                contracting_labels = dict(ctype_finfo._description_selection(self.env))
            else:
                sel = ctype_finfo.selection
                contracting_labels = dict(sel(Assignment) if callable(sel) else (sel or []))
        for rec in self:
            label = rec._license_equipment_display_label()
            extras = []
            if self.env.context.get('mesa_retiro_license_select'):
                ctype = rec.contracting_type or (
                    rec.assignment_id.contracting_type if rec.assignment_id else False
                )
                if ctype:
                    clabel = contracting_labels.get(ctype, ctype)
                    if clabel and clabel not in label:
                        extras.append(clabel)
            state_lbl = state_labels.get(rec.state)
            if state_lbl:
                extras.append(state_lbl)
            extras = list(dict.fromkeys(extras))
            rec.display_name = '%s — %s' % (label, ' · '.join(extras)) if extras else label

    def name_get(self):
        return [(rec.id, rec.display_name) for rec in self]

