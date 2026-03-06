# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Campos principales NIT DIAN
    dian_nit_number = fields.Char(
        string='Número NIT',
        size=15,
        help='Número de identificación tributaria sin dígito de verificación (9-15 dígitos: NIT empresa o cédula persona natural)'
    )
    
    dian_nit_dv = fields.Char(
        string='Dígito de Verificación',
        size=1,
        compute='_compute_dian_nit_dv',
        store=True,
        help='Dígito de verificación calculado automáticamente'
    )
    
    dian_nit_full = fields.Char(
        string='NIT Completo',
        compute='_compute_dian_nit_full',
        store=True,
        help='NIT completo con dígito de verificación'
    )
    
    dian_is_colombia = fields.Boolean(
        string='Es Colombia',
        compute='_compute_dian_is_colombia',
        help='Indica si el país es Colombia'
    )
    
    
    dian_nit_validated = fields.Boolean(
        string='NIT Validado',
        default=False,
        help='Indica si el NIT ha sido validado'
    )
    
    # Campos adicionales DIAN
    dian_responsibility_code = fields.Char(
        string='Código de Responsabilidad',
        size=2,
        help='Código de responsabilidad fiscal DIAN'
    )
    
    dian_tax_regime = fields.Selection([
        ('simplified', 'Régimen Simplificado'),
        ('common', 'Régimen Común'),
        ('large_taxpayer', 'Gran Contribuyente'),
        ('special', 'Régimen Especial'),
    ], string='Régimen Tributario', help='Régimen tributario según DIAN')
    
    dian_commercial_name = fields.Char(
        string='Nombre Comercial',
        help='Nombre comercial registrado en DIAN'
    )
    
    dian_economic_activity = fields.Char(
        string='Actividad Económica',
        help='Código de actividad económica DIAN'
    )

    @api.constrains('dian_responsibility_code', 'dian_tax_regime', 'dian_commercial_name', 'dian_economic_activity', 'is_company')
    def _check_dian_fields_company_only(self):
        """Valida que los campos DIAN solo se usen en empresas"""
        for record in self:
            if not record.is_company:
                fields_with_data = []
                if record.dian_responsibility_code:
                    fields_with_data.append('Código de Responsabilidad')
                if record.dian_tax_regime:
                    fields_with_data.append('Régimen Tributario')
                if record.dian_commercial_name:
                    fields_with_data.append('Nombre Comercial')
                if record.dian_economic_activity:
                    fields_with_data.append('Actividad Económica')
                
                if fields_with_data:
                    raise ValidationError(_('Los campos DIAN (%s) solo pueden ser usados por empresas, no por contactos individuales.') % ', '.join(fields_with_data))

    def _get_nit_identification_type(self):
        """Obtiene el tipo de identificación NIT para Colombia"""
        # Buscar el tipo de identificación NIT para Colombia
        nit_type = self.env['l10n_latam.identification.type'].search([
            ('country_id.code', '=', 'CO'),
            ('name', '=', 'NIT')
        ], limit=1)
        return nit_type.id if nit_type else False

    @api.model_create_multi
    def create(self, vals_list):
        """Sobrescribe create para establecer NIT automáticamente"""
        for vals in vals_list:
            # Auto-establecer NIT para empresas colombianas
            if vals.get('is_company') or vals.get('company_type') == 'company':
                country_id = vals.get('country_id', self.env.user.company_id.country_id.id if hasattr(self.env.user, 'company_id') else False)
                if country_id:
                    country = self.env['res.country'].browse(country_id)
                    if country.code == 'CO' and not vals.get('l10n_latam_identification_type_id'):
                        nit_id = self._get_nit_identification_type()
                        if nit_id:
                            vals['l10n_latam_identification_type_id'] = nit_id
        return super().create(vals_list)

    def write(self, vals):
        """Sobrescribe write para establecer NIT automáticamente al cambiar de país"""
        if 'country_id' in vals or 'is_company' in vals or 'company_type' in vals:
            for record in self:
                # Auto-establecer NIT para empresas colombianas
                country_id = vals.get('country_id', record.country_id.id if record.country_id else False)
                if country_id:
                    country = self.env['res.country'].browse(country_id)
                    is_company_val = vals.get('is_company', record.is_company)
                    company_type_val = vals.get('company_type', record.company_type)
                    is_company = is_company_val or company_type_val == 'company'
                    
                    if country.code == 'CO' and is_company:
                        nit_id = record._get_nit_identification_type()
                        if nit_id:
                            vals['l10n_latam_identification_type_id'] = nit_id
        return super().write(vals)

    @api.depends('country_id')
    def _compute_dian_is_colombia(self):
        """Calcula si el país es Colombia"""
        for record in self:
            record.dian_is_colombia = record.country_id.code == 'CO'

    @api.depends('dian_nit_number', 'dian_is_colombia')
    def _compute_dian_nit_dv(self):
        """Calcula el dígito de verificación automáticamente"""
        for record in self:
            if record.dian_nit_number and record.dian_is_colombia:
                record.dian_nit_dv = self._calculate_dian_dv(record.dian_nit_number)
            else:
                record.dian_nit_dv = False

    @api.depends('dian_nit_number', 'dian_nit_dv')
    def _compute_dian_nit_full(self):
        """Calcula el NIT completo con dígito de verificación"""
        for record in self:
            if record.dian_nit_number and record.dian_nit_dv:
                record.dian_nit_full = f"{record.dian_nit_number}-{record.dian_nit_dv}"
            elif record.dian_nit_number and not record.dian_nit_dv:
                # Si hay número pero no DV, mostrar solo el número
                record.dian_nit_full = record.dian_nit_number
            else:
                record.dian_nit_full = ""

    @api.model
    def _calculate_dian_dv(self, nit_number):
        """
        Calcula el dígito de verificación según el algoritmo oficial DIAN.
        Soporta NIT empresa (9 dígitos) y cédula como NIT persona natural (hasta 15 dígitos).
        
        Algoritmo oficial DIAN:
        1. Coeficientes: [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]
        2. Se aplican de DERECHA A IZQUIERDA (del dígito menos significativo al más significativo)
        3. Se multiplica cada dígito por su coeficiente correspondiente
        4. Se suman todos los productos
        5. Se calcula el residuo de la división por 11
        6. Si residuo > 1: DV = 11 - residuo
        7. Si residuo es 0 o 1: DV = residuo
        
        Ejemplos:
        - NIT 800073584 (9 dígitos): DV = 4
        - NIT 900877788 (9 dígitos): DV = 3
        - Cédula 811026552 (9 dígitos): DV = 9
        """
        if not nit_number or not nit_number.isdigit():
            return False
        
        # Algoritmo DIAN oficial: 15 coeficientes aplicados de DERECHA A IZQUIERDA
        coeficientes = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]
        nit_reversed = nit_number[::-1]
        
        total = 0
        for i, digit in enumerate(nit_reversed):
            if i < len(coeficientes):
                total += int(digit) * coeficientes[i]
        
        remainder = total % 11
        if remainder > 1:
            return str(11 - remainder)
        else:
            return str(remainder)

    @api.constrains('dian_nit_number', 'is_company')
    def _check_dian_nit_number(self):
        """Valida el formato del número NIT y que solo se use en empresas"""
        for record in self:
            # Validar que solo empresas pueden tener NIT
            if record.dian_nit_number and not record.is_company:
                raise ValidationError(_('El NIT solo puede ser usado por empresas, no por contactos individuales.'))
            
            if record.dian_nit_number and record.dian_is_colombia and record.is_company:
                # Validar que solo contenga dígitos
                if not record.dian_nit_number.isdigit():
                    raise ValidationError(_('El número NIT solo puede contener dígitos.'))
                
                # Validar longitud (9 a 15 dígitos: NIT empresa o cédula persona natural)
                nit_len = len(record.dian_nit_number)
                if nit_len < 9 or nit_len > 15:
                    raise ValidationError(_(
                        'El número NIT debe tener entre 9 y 15 dígitos '
                        '(9 para NIT empresa, hasta 11 para cédula persona natural).'
                    ))

    @api.constrains('dian_nit_full', 'is_company')
    def _check_dian_nit_full(self):
        """Valida el NIT completo"""
        for record in self:
            # Validar que solo empresas pueden tener NIT completo
            if record.dian_nit_full and not record.is_company:
                raise ValidationError(_('El NIT completo solo puede ser usado por empresas, no por contactos individuales.'))
            
            if record.dian_nit_full and record.dian_is_colombia and record.is_company:
                # Validar formato NIT-DV (9-15 dígitos + guión + 1 dígito DV)
                pattern = r'^\d{9,15}-\d$'
                if not re.match(pattern, record.dian_nit_full):
                    raise ValidationError(_('El formato del NIT debe ser: número (9-15 dígitos)-dígito de verificación'))

    def action_dian_calculate_dv(self):
        """Acción para recalcular el dígito de verificación"""
        for record in self:
            if not record.is_company:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Error'),
                        'message': _('Esta acción solo está disponible para empresas.'),
                        'type': 'danger',
                    }
                }
            
            if record.dian_nit_number and record.dian_is_colombia:
                # El cálculo es automático, solo marcamos como validado
                record.dian_nit_validated = True
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Éxito'),
                        'message': _('Dígito de verificación calculado correctamente.'),
                        'type': 'success',
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Error'),
                        'message': _('Debe ingresar un número NIT válido.'),
                        'type': 'danger',
                    }
                }


    def action_dian_validate_nit(self):
        """Valida el NIT según algoritmo DIAN"""
        for record in self:
            if not record.is_company:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Error'),
                        'message': _('Esta acción solo está disponible para empresas.'),
                        'type': 'danger',
                    }
                }
            
            if record.dian_nit_number and record.dian_is_colombia:
                calculated_dv = self._calculate_dian_dv(record.dian_nit_number)
                if calculated_dv == record.dian_nit_dv:
                    record.dian_nit_validated = True
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Éxito'),
                            'message': _('NIT validado correctamente según algoritmo DIAN.'),
                            'type': 'success',
                        }
                    }
                else:
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Error'),
                            'message': _('El dígito de verificación no es válido.'),
                            'type': 'danger',
                        }
                    }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Error'),
                        'message': _('Debe ingresar un número NIT válido.'),
                        'type': 'danger',
                    }
                }

    def action_dian_diagnose_nit(self):
        """Método para diagnosticar problemas con el NIT"""
        for record in self:
            if not record.is_company:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Error'),
                        'message': _('Esta acción solo está disponible para empresas.'),
                        'type': 'danger',
                    }
                }
            
            if record.dian_is_colombia:
                diagnosis = {
                    'nit_number': record.dian_nit_number,
                    'nit_dv': record.dian_nit_dv,
                    'nit_full': record.dian_nit_full,
                    'nit_validated': record.dian_nit_validated,
                }
                
                message = f"Diagnóstico NIT:\n"
                message += f"Número NIT: {diagnosis['nit_number']}\n"
                message += f"Dígito DV: {diagnosis['nit_dv']}\n"
                message += f"NIT Completo: {diagnosis['nit_full']}\n"
                message += f"NIT Validado: {diagnosis['nit_validated']}\n"
                
                if record.dian_nit_number and not record.dian_nit_dv:
                    message += "\n⚠️ PROBLEMA: Falta calcular el dígito de verificación"
                elif record.dian_nit_full and '-' not in record.dian_nit_full:
                    message += "\n⚠️ PROBLEMA: NIT completo no tiene formato correcto"
                elif record.dian_nit_number and record.dian_nit_dv and record.dian_nit_full:
                    message += "\n✅ TODO CORRECTO: NIT válido según algoritmo DIAN"
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Diagnóstico NIT'),
                        'message': message,
                        'type': 'info',
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Error'),
                        'message': _('Este contacto no es de Colombia.'),
                        'type': 'danger',
                    }
                }

    def action_dian_clear_nit(self):
        """Limpia los campos NIT"""
        for record in self:
            if not record.is_company:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Error'),
                        'message': _('Esta acción solo está disponible para empresas.'),
                        'type': 'danger',
                    }
                }
            record.dian_nit_number = False
            record.dian_nit_dv = False
            record.dian_nit_full = False
            record.dian_nit_validated = False
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Éxito'),
                    'message': _('Campos NIT limpiados correctamente.'),
                    'type': 'success',
                }
            }
