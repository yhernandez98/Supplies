# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
import re

_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    # ========================================
    # CAMPOS PERSONALIZADOS - TIPO DE CONTACTO
    # ========================================
    
    tipo_contacto = fields.Selection([
        ('proveedor', 'Proveedor'),
        ('cliente', 'Cliente'),
        ('ambos', 'Proveedor y Cliente')
    ], string='Tipo de Contacto', default='cliente', required=True,
       help='Define el tipo de relación comercial con este contacto')
    
    # ========================================
    # CAMPOS PERSONALIZADOS - CREACIÓN AUTOMÁTICA
    # ========================================
    
    auto_create_contact = fields.Boolean(
        string='Crear contacto automático',
        default=True,
        help='Si está activo se creará automáticamente un contacto individual (solo para empresas)'
    )
    
    auto_created_contact_id = fields.Many2one(
        'res.partner',
        string='Contacto creado automáticamente',
        readonly=True,
        ondelete="set null",
        help='Contacto individual creado automáticamente para esta empresa'
    )
    
    # Campos de configuración personalizable
    contact_name_template = fields.Char(
        string='Plantilla de nombre',
        default='Contacto {company_name}',
        help='Plantilla para el nombre del contacto automático. Use {company_name} para el nombre de la empresa'
    )
    
    contact_email_template = fields.Char(
        string='Plantilla de email',
        default='contacto@{domain}',
        help='Plantilla para el email del contacto automático. Variables disponibles: {domain}, {company_name}, {contact_name}'
    )

    # ========================================
    # CONSTRAINTS Y VALIDACIONES
    # ========================================
    
    @api.constrains('tipo_contacto')
    def _check_tipo_contacto_consistency(self):
        """Valida consistencia del tipo de contacto con los ranks nativos"""
        for partner in self:
            if partner.tipo_contacto == 'proveedor' and partner.customer_rank > 0:
                raise ValidationError(_('Un proveedor no puede tener customer_rank > 0'))
            elif partner.tipo_contacto == 'cliente' and partner.supplier_rank > 0:
                raise ValidationError(_('Un cliente no puede tener supplier_rank > 0'))
    
    @api.constrains('auto_created_contact_id')
    def _check_contact_consistency(self):
        """Valida consistencia del contacto automático"""
        for partner in self:
            if partner.auto_created_contact_id:
                if partner.auto_created_contact_id.parent_id != partner:
                    raise ValidationError(_('El contacto automático debe pertenecer a esta empresa'))
                if partner.auto_created_contact_id.is_company:
                    raise ValidationError(_('El contacto automático debe ser una persona, no una empresa'))
    
    @api.constrains('contact_name_template', 'contact_email_template')
    def _check_template_format(self):
        """Valida formato de las plantillas"""
        for partner in self:
            if partner.contact_name_template and '{company_name}' not in partner.contact_name_template:
                raise ValidationError(_('La plantilla de nombre debe contener {company_name}'))
            
            if partner.contact_email_template:
                valid_vars = ['{domain}', '{company_name}', '{contact_name}']
                has_valid_var = any(var in partner.contact_email_template for var in valid_vars)
                if not has_valid_var and '@' not in partner.contact_email_template:
                    raise ValidationError(_('La plantilla de email debe contener una variable válida: {domain}, {company_name}, {contact_name} o ser un email completo'))
    
    # ========================================
    # MÉTODOS ONCHANGE
    # ========================================
    
    @api.onchange('tipo_contacto')
    def _onchange_tipo_contacto(self):
        """Sincroniza tipo_contacto con customer_rank y supplier_rank"""
        for partner in self:
            if partner.tipo_contacto == 'proveedor':
                partner.supplier_rank = 1
                partner.customer_rank = 0
            elif partner.tipo_contacto == 'cliente':
                partner.supplier_rank = 0
                partner.customer_rank = 1
            elif partner.tipo_contacto == 'ambos':
                partner.supplier_rank = 1
                partner.customer_rank = 1
    
    @api.onchange('is_company')
    def _onchange_is_company(self):
        """Desactiva creación automática si no es empresa"""
        if not self.is_company:
            self.auto_create_contact = False
            self.auto_created_contact_id = False
    
    # ========================================
    # MÉTODOS DE CREACIÓN Y ESCRITURA
    # ========================================
    
    @api.model_create_multi
    def create(self, vals_list):
        """Creación optimizada con procesamiento en lote"""
        partners = super().create(vals_list)
        companies = partners.filtered(lambda p: p.is_company and p.auto_create_contact and not p.auto_created_contact_id)
        if companies:
            self._create_auto_contacts_batch(companies)
        return partners
    
    def write(self, vals):
        """Maneja cambios en creación automática"""
        result = super().write(vals)
        # Si se activa la creación automática después de crear la empresa
        if 'auto_create_contact' in vals and vals['auto_create_contact']:
            companies = self.filtered(lambda p: p.is_company and p.auto_create_contact and not p.auto_created_contact_id)
            if companies:
                self._create_auto_contacts_batch(companies)
        return result
    
    # ========================================
    # MÉTODOS PRIVADOS - CREACIÓN AUTOMÁTICA
    # ========================================
    
    def _create_auto_contacts_batch(self, companies):
        """Crea contactos automáticos en lote para mejor rendimiento"""
        contacts_to_create = []
        company_contact_map = {}
        
        for company in companies:
            if not company.auto_created_contact_id:
                contact_vals = self._prepare_contact_vals(company)
                contacts_to_create.append(contact_vals)
                company_contact_map[company.id] = len(contacts_to_create) - 1
        
        if contacts_to_create:
            try:
                contacts = self.env['res.partner'].create(contacts_to_create)
                # Asignar contactos a empresas
                for company in companies:
                    if not company.auto_created_contact_id:
                        contact_index = company_contact_map[company.id]
                        company.auto_created_contact_id = contacts[contact_index].id
                        _logger.info(f'Contacto automático creado: {contacts[contact_index].name} para empresa: {company.name}')
            except Exception as e:
                _logger.error(f'Error creando contactos automáticos en lote: {str(e)}')
                # Fallback: crear individualmente
                for company in companies:
                    if not company.auto_created_contact_id:
                        self._create_auto_contact_individual(company)
    
    def _prepare_contact_vals(self, company):
        """Prepara los valores para crear un contacto automático"""
        contact_name = self._generate_contact_name(company)
        contact_email = self._generate_contact_email(company)
        
        return {
            'name': contact_name,
            'is_company': False,
            'parent_id': company.id,
            'type': 'contact',
            'email': contact_email,
            'phone': company.phone,
            'mobile': company.mobile,
            'street': company.street,
            'street2': company.street2,
            'city': company.city,
            'state_id': company.state_id.id if company.state_id else False,
            'zip': company.zip,
            'country_id': company.country_id.id if company.country_id else False,
            'comment': f'Contacto creado automáticamente para {company.name or "empresa"}',
            'active': True,
        }
    
    def _generate_contact_name(self, company):
        """Genera el nombre del contacto usando la plantilla"""
        template = company.contact_name_template or 'Contacto {company_name}'
        company_name = company.name or 'Genérico'
        return template.format(company_name=company_name)
    
    def _generate_contact_email(self, company):
        """Genera un email válido para el contacto automático usando las plantillas"""
        # Obtener la plantilla de email (si está configurada)
        email_template = company.contact_email_template or 'contacto@{domain}'
        
        # Obtener el dominio
        if company.email and '@' in company.email:
            # Usar el dominio de la empresa existente
            _, domain = company.email.split('@', 1)
        elif company.name:
            # Generar dominio basado en el nombre de la empresa
            base_domain = re.sub(r'[^a-zA-Z0-9]', '.', company.name.lower())
            base_domain = re.sub(r'\.+', '.', base_domain)  # Limpiar puntos múltiples
            domain = f"{base_domain}.com"
        else:
            return False
        
        # Si la plantilla contiene {domain}, usar la plantilla directamente
        if '{domain}' in email_template:
            return email_template.format(domain=domain)
        
        # Si la plantilla contiene {company_name}, generar basado en el nombre de la empresa
        elif '{company_name}' in email_template:
            company_name_clean = re.sub(r'[^a-zA-Z0-9]', '.', company.name.lower())
            company_name_clean = re.sub(r'\.+', '.', company_name_clean)
            company_name_clean = company_name_clean.strip('.')
            return email_template.format(company_name=company_name_clean, domain=domain)
        
        # Si la plantilla contiene {contact_name}, usar el nombre del contacto generado
        elif '{contact_name}' in email_template:
            contact_name = self._generate_contact_name(company)
            contact_name_clean = re.sub(r'[^a-zA-Z0-9]', '.', contact_name.lower())
            contact_name_clean = re.sub(r'\.+', '.', contact_name_clean)
            contact_name_clean = contact_name_clean.strip('.')
            return email_template.format(contact_name=contact_name_clean, domain=domain)
        
        # Si no contiene variables, usar la plantilla tal como está
        else:
            return email_template
    
    def _create_auto_contact_individual(self, company):
        """Crea un contacto automático individual (fallback)"""
        try:
            contact_vals = self._prepare_contact_vals(company)
            contact = self.env['res.partner'].create(contact_vals)
            company.auto_created_contact_id = contact.id
            _logger.info(f'Contacto automático creado: {contact.name} para empresa: {company.name}')
        except Exception as e:
            _logger.error(f'Error creando contacto automático para {company.name}: {str(e)}')
    
    # ========================================
    # MÉTODOS DE ACCIÓN
    # ========================================
    
    def action_view_auto_contact(self):
        """Abre la vista del contacto automático"""
        self.ensure_one()
        if self.auto_created_contact_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Contacto Automático'),
                'res_model': 'res.partner',
                'res_id': self.auto_created_contact_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return False
    
    def action_recreate_auto_contact(self):
        """Recrea el contacto automático"""
        self.ensure_one()
        if self.company_type != 'company':
            raise ValidationError(_('Solo se pueden recrear contactos automáticos para empresas'))
        
        # Eliminar contacto actual si existe
        if self.auto_created_contact_id:
            self.auto_created_contact_id.unlink()
            self.auto_created_contact_id = False
        
        # Crear nuevo contacto
        if self.auto_create_contact:
            self._create_auto_contact_individual(self)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Éxito'),
                    'message': _('Contacto automático recreado correctamente'),
                    'type': 'success',
                }
            }
        return False
    
    # ========================================
    # CAMPOS PERSONALIZADOS - PRODUCTOS INDIVIDUALES
    # ========================================
    
    # Producto de bien: usa tipo_producto en product.template
    individual_good_product_id = fields.Many2one(
        'product.product',
        string='Product (Good)',
        domain=[('product_tmpl_id.tipo_producto', 'in', ['consu', 'factura'])],
        help='Producto tipo Bien vinculado al contacto individual.'
    )

    # Producto de servicio: usa tipo_producto en product.template
    individual_service_product_id = fields.Many2one(
        'product.product',
        string='Product (Service)',
        domain=[('product_tmpl_id.tipo_producto', '=', 'service')],
        help='Producto tipo Servicio vinculado al contacto individual.'
    )

    # Serial numbers (lots) for the selected good product
    individual_good_lot_ids = fields.Many2many(
        'stock.lot',
        'res_partner_individual_good_lot_rel',
        'partner_id',
        'lot_id',
        string='Serial Numbers',
        help='Serial numbers linked to the selected good product.'
    )
    
    @api.onchange('individual_good_product_id')
    def _onchange_individual_good_product_id(self):
        # Remove serials that do not match the selected good product
        for partner in self:
            if partner.individual_good_product_id and partner.individual_good_lot_ids:
                partner.individual_good_lot_ids = partner.individual_good_lot_ids.filtered(
                    lambda l: l.product_id == partner.individual_good_product_id
                )
            elif partner.individual_good_lot_ids:
                partner.individual_good_lot_ids = [(5, 0, 0)]
    
    @api.constrains('individual_good_product_id', 'individual_service_product_id', 'individual_good_lot_ids')
    def _check_product_types_and_lot(self):
        """Validar que los productos y el numero de serie correspondan al tipo correcto"""
        for partner in self:
            # Validar producto de bien por tipo_producto en template
            if partner.individual_good_product_id and partner.individual_good_product_id.product_tmpl_id.tipo_producto not in ['consu', 'factura']:
                raise ValidationError('El producto Good debe tener tipo_producto = consu o factura')

            # Validar producto de servicio por tipo_producto en template
            if partner.individual_service_product_id and partner.individual_service_product_id.product_tmpl_id.tipo_producto != 'service':
                raise ValidationError('El producto Service debe tener tipo_producto = service')

            # Validar lotes (numeros de serie)
            if partner.individual_good_lot_ids:
                if not partner.individual_good_product_id:
                    raise ValidationError('Select a good product before choosing serial numbers')
                # product must be serial-tracked
                if partner.individual_good_product_id.tracking != 'serial':
                    raise ValidationError('Selected good product must have tracking = serial')
                # all lots must belong to the selected product
                wrong_lots = partner.individual_good_lot_ids.filtered(
                    lambda l: l.product_id != partner.individual_good_product_id
                )
                if wrong_lots:
                    raise ValidationError('All selected serial numbers must belong to the selected good product')
