# -*- coding: utf-8 -*-

from odoo import fields, models, _, api
from odoo.exceptions import UserError


class CustomerQueryWizard(models.TransientModel):
    _name = 'customer.query.wizard'
    _description = 'Wizard de Consulta de Clientes'

    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        required=True,
        domain="[('is_company', '=', True)]",
        help='Seleccione únicamente un cliente empresa.',
    )

    def action_open_customer_inventory(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_('Debe seleccionar un cliente.'))

        pricelist = self.partner_id.property_product_pricelist
        if not pricelist:
            raise UserError(_('El cliente no tiene lista de precios configurada.'))

        # Solo ítems realmente contratados (producto/plantilla), sin reglas generales o por categoría.
        items = self.env['product.pricelist.item'].search(
            [('pricelist_id', '=', pricelist.id)],
            order='applied_on, product_tmpl_id, product_id, id'
        )

        result = self.env['customer.contract.summary.wizard'].create({
            'partner_id': self.partner_id.id,
            'pricelist_id': pricelist.id,
            'currency_id': pricelist.currency_id.id,
            'contact_name': self._get_contact_name(self.partner_id),
            'contact_phone': self._get_contact_phone(self.partner_id),
            'contact_email': self._get_contact_email(self.partner_id),
            'sla_reference': self._get_sla_reference(self.partner_id),
            'technical_notes': self._get_technical_notes(self.partner_id),
        })

        line_vals = []
        today = fields.Date.context_today(self)
        for item in items:
            # Omitir reglas generales/categoría: no representan un servicio puntual contratado.
            if not item.product_id and not item.product_tmpl_id:
                continue

            # Solo vigencias activas al día de hoy.
            if item.date_start and item.date_start > today:
                continue
            if item.date_end and item.date_end < today:
                continue

            if item.product_id:
                product = item.product_id
                service_name = product.display_name
            elif item.product_tmpl_id:
                product = item.product_tmpl_id.product_variant_id or item.product_tmpl_id
                service_name = item.product_tmpl_id.display_name
            else:
                # Safety net: por lógica no debería entrar.
                continue

            business_line_name = result._get_business_line_name(product)
            # Misma casilla que ve el técnico en lista de precios (product.pricelist.item).
            is_administered = bool(getattr(item, 'admin_supplies_mh', False))

            line_vals.append({
                'wizard_id': result.id,
                'business_line_name': business_line_name,
                'service_name': service_name,
                'is_administered': is_administered,
                'fixed_price': item.fixed_price or 0.0,
                'date_start': item.date_start,
                'date_end': item.date_end,
            })

        # Orden amigable por línea de negocio y servicio
        line_vals.sort(key=lambda v: ((v.get('business_line_name') or '').lower(), (v.get('service_name') or '').lower()))

        if not line_vals:
            raise UserError(_(
                'No hay líneas de precios recurrentes vigentes con producto asociado para este cliente.'
            ))

        created_lines = self.env['customer.contract.summary.line.wizard'].create(line_vals)
        result._build_summary_lines_from_details(created_lines)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Ficha Técnica de Servicios Contratados'),
            'res_model': 'customer.contract.summary.wizard',
            'res_id': result.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _get_main_contact(self, partner):
        contact = self.env['res.partner'].search([
            ('parent_id', '=', partner.id),
            ('type', 'in', ('contact', False)),
            ('active', '=', True),
        ], order='id asc', limit=1)
        return contact or partner

    def _get_contact_name(self, partner):
        contact = self._get_main_contact(partner)
        return contact.name or partner.name or ''

    def _get_contact_phone(self, partner):
        contact = self._get_main_contact(partner)
        contact_mobile = getattr(contact, 'mobile', False)
        partner_mobile = getattr(partner, 'mobile', False)
        return contact.phone or contact_mobile or partner.phone or partner_mobile or ''

    def _get_contact_email(self, partner):
        contact = self._get_main_contact(partner)
        return contact.email or partner.email or ''

    def _get_sla_reference(self, partner):
        ticket = self.env['helpdesk.ticket'].search([
            ('partner_id', '=', partner.id),
            ('category_id', '!=', False),
        ], order='create_date desc', limit=1)
        category = ticket.category_id if ticket else False
        if not category:
            return _('No definido')
        resp_d = int(category.sla_response_days or 0)
        resp_h = float(category.sla_response_hours or 0.0)
        res_d = int(category.sla_resolution_days or 0)
        res_h = float(category.sla_resolution_hours or 0.0)
        return _('Respuesta: %(rd)s d %(rh)s h | Resolución: %(sd)s d %(sh)s h') % {
            'rd': resp_d, 'rh': resp_h, 'sd': res_d, 'sh': res_h,
        }

    def _get_technical_notes(self, partner):
        # Reutiliza la nota interna del cliente para que el técnico tenga contexto operativo.
        return (partner.comment or '').strip()


class CustomerContractSummaryWizard(models.TransientModel):
    _name = 'customer.contract.summary.wizard'
    _description = 'Ficha Técnica de Servicios Contratados'

    partner_id = fields.Many2one('res.partner', string='Cliente', readonly=True)
    pricelist_id = fields.Many2one('product.pricelist', string='Lista de Precios', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', readonly=True)
    contact_name = fields.Char(string='Contacto principal', readonly=True)
    contact_phone = fields.Char(string='Teléfono contacto', readonly=True)
    contact_email = fields.Char(string='Correo contacto', readonly=True)
    sla_reference = fields.Char(string='SLA de referencia', readonly=True)
    technical_notes = fields.Text(string='Notas técnicas', readonly=True)
    line_ids = fields.One2many(
        'customer.contract.summary.line.wizard',
        'wizard_id',
        string='Servicios (todos)',
        readonly=True,
    )
    # Mismo inverse_name con distinto domain: el cliente web filtra bien (no duplicar el campo en XML).
    line_ids_admin = fields.One2many(
        'customer.contract.summary.line.wizard',
        'wizard_id',
        string='Servicios administrados',
        domain=[('is_administered', '=', True)],
        readonly=True,
    )
    line_ids_no_admin = fields.One2many(
        'customer.contract.summary.line.wizard',
        'wizard_id',
        string='Servicios no administrados',
        domain=[('is_administered', '=', False)],
        readonly=True,
    )
    summary_line_ids = fields.One2many(
        'customer.contract.summary.group.line.wizard',
        'wizard_id',
        string='Resumen (todos)',
        readonly=True,
    )
    summary_line_ids_admin = fields.One2many(
        'customer.contract.summary.group.line.wizard',
        'wizard_id',
        string='Resumen administrados',
        domain=[('is_administered', '=', True)],
        readonly=True,
    )
    summary_line_ids_no_admin = fields.One2many(
        'customer.contract.summary.group.line.wizard',
        'wizard_id',
        string='Resumen no administrados',
        domain=[('is_administered', '=', False)],
        readonly=True,
    )
    line_count = fields.Integer(string='Total servicios', compute='_compute_line_count')

    @api.depends('line_ids')
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    def _build_summary_lines_from_details(self, detail_lines):
        self.ensure_one()
        if not detail_lines:
            return

        GroupLine = self.env['customer.contract.summary.group.line.wizard']
        for administered in (True, False):
            subset = detail_lines.filtered(
                lambda l, adm=administered: bool(l.is_administered) == adm
            )
            if not subset:
                continue
            grouped = {}
            for line in subset:
                key = line.business_line_name or _('Sin línea de negocio')
                if key not in grouped:
                    grouped[key] = {'count': 0, 'total': 0.0}
                grouped[key]['count'] += 1
                grouped[key]['total'] += float(line.fixed_price or 0.0)

            vals = []
            for name in sorted(grouped.keys(), key=lambda x: (x or '').lower()):
                vals.append({
                    'wizard_id': self.id,
                    'business_line_name': name,
                    'service_count': grouped[name]['count'],
                    'total_price': grouped[name]['total'],
                    'is_administered': administered,
                })
            if vals:
                GroupLine.create(vals)

    def _get_business_line_name(self, product):
        line = getattr(product, 'business_line_id', False)
        return line.name if line else _('Sin línea de negocio')

class CustomerContractSummaryLineWizard(models.TransientModel):
    _name = 'customer.contract.summary.line.wizard'
    _description = 'Línea de Ficha Técnica de Servicios'

    wizard_id = fields.Many2one(
        'customer.contract.summary.wizard',
        required=True,
        ondelete='cascade',
    )
    business_line_name = fields.Char(string='Línea de negocio', readonly=True)
    service_name = fields.Char(string='Servicio/Regla', readonly=True)
    is_administered = fields.Boolean(
        string='Administrado en lista de precios',
        readonly=True,
        help='True si el servicio está marcado como Admin Supplies en la lista de precios del cliente.',
    )
    fixed_price = fields.Monetary(string='Precio fijo', currency_field='currency_id', readonly=True)
    currency_id = fields.Many2one(related='wizard_id.currency_id', readonly=True)
    date_start = fields.Date(string='Desde', readonly=True)
    date_end = fields.Date(string='Hasta', readonly=True)

class CustomerContractSummaryGroupLineWizard(models.TransientModel):
    _name = 'customer.contract.summary.group.line.wizard'
    _description = 'Resumen por Línea de negocio (Wizard)'

    wizard_id = fields.Many2one(
        'customer.contract.summary.wizard',
        required=True,
        ondelete='cascade',
    )
    business_line_name = fields.Char(string='Línea de negocio', readonly=True)
    service_count = fields.Integer(string='Servicios', readonly=True)
    total_price = fields.Monetary(string='Total', currency_field='currency_id', readonly=True)
    currency_id = fields.Many2one(related='wizard_id.currency_id', readonly=True)
    is_administered = fields.Boolean(
        string='Administrado en lista de precios',
        readonly=True,
    )

class CustomerAdminSuppliesFlag(models.Model):
    _name = 'customer.admin.supplies.flag'
    _description = 'Preferencia Admin Supplies por cliente y línea de negocio'

    partner_id = fields.Many2one('res.partner', required=True, ondelete='cascade', index=True)
    business_line_name = fields.Char(string='Línea de negocio', required=True, index=True)
    admin_supplies = fields.Boolean(string='Admin Supplies', default=False)

    _sql_constraints = [
        (
            'uniq_partner_business_line_admin_supplies',
            'unique(partner_id, business_line_name)',
            'Ya existe una preferencia Admin Supplies para este cliente y línea de negocio.',
        )
    ]


class CustomerAdminSuppliesServiceFlag(models.Model):
    _name = 'customer.admin.supplies.service.flag'
    _description = 'Preferencia Admin Supplies por cliente/línea/servicio'

    partner_id = fields.Many2one('res.partner', required=True, ondelete='cascade', index=True)
    business_line_name = fields.Char(string='Línea de negocio', required=True, index=True)
    service_name = fields.Char(string='Servicio', required=True, index=True)
    admin_supplies = fields.Boolean(string='Admin Supplies', default=False)

    _sql_constraints = [
        (
            'uniq_partner_business_line_service_admin_supplies',
            'unique(partner_id, business_line_name, service_name)',
            'Ya existe una preferencia Admin Supplies para este cliente, línea y servicio.',
        )
    ]
