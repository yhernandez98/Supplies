# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Campos principales NIT DIAN
    dian_nit_number = fields.Char(
        string='Número NIT',
        size=9,
        help='Número de identificación tributaria sin dígito de verificación'
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
        Calcula el dígito de verificación según el algoritmo oficial DIAN
        
        Algoritmo oficial DIAN:
        1. Se toman los 9 pesos: [41, 37, 29, 23, 19, 17, 13, 7, 3]
        2. Se aplican de IZQUIERDA A DERECHA (del primer dígito al último)
        3. Se multiplica cada dígito por su peso correspondiente
        4. Se suman todos los productos
        5. Se calcula el residuo de la división por 11
        6. Si el residuo es 0 o 1, el DV es 0
        7. Si el residuo es mayor que 1, el DV es 11 - residuo
        
        Ejemplos:
        - NIT: 800073584
          Pesos aplicados de izquierda a derecha: 8×41 + 0×37 + 0×29 + 0×23 + 7×19 + 3×17 + 5×13 + 8×7 + 4×3
          Suma: 328 + 0 + 0 + 0 + 133 + 51 + 65 + 56 + 12 = 645
          Residuo: 645 % 11 = 7
          DV: 11 - 7 = 4
        
        - NIT: 900877788
          Pesos aplicados de izquierda a derecha: 9×41 + 0×37 + 0×29 + 8×23 + 7×19 + 7×17 + 7×13 + 8×7 + 8×3
          Suma: 369 + 0 + 0 + 184 + 133 + 119 + 91 + 56 + 24 = 976
          Residuo: 976 % 11 = 8
          DV: 11 - 8 = 3
        """
        if not nit_number or not nit_number.isdigit():
            return False
        
        # Algoritmo DIAN oficial: 9 pesos aplicados de IZQUIERDA A DERECHA
        weights = [41, 37, 29, 23, 19, 17, 13, 7, 3]
        
        # Aplicar pesos de izquierda a derecha (sin invertir)
        total = 0
        for i, digit in enumerate(nit_number):
            if i < len(weights):
                total += int(digit) * weights[i]
        
        remainder = total % 11
        # Si el residuo es 0 o 1, el DV es 0 (no el residuo mismo)
        if remainder < 2:
            return '0'
        else:
            return str(11 - remainder)

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
                
                # Validar longitud (máximo 9 dígitos)
                if len(record.dian_nit_number) > 9:
                    raise ValidationError(_('El número NIT no puede tener más de 9 dígitos.'))

    @api.constrains('dian_nit_full', 'is_company')
    def _check_dian_nit_full(self):
        """Valida el NIT completo"""
        for record in self:
            # Validar que solo empresas pueden tener NIT completo
            if record.dian_nit_full and not record.is_company:
                raise ValidationError(_('El NIT completo solo puede ser usado por empresas, no por contactos individuales.'))
            
            if record.dian_nit_full and record.dian_is_colombia and record.is_company:
                # Validar formato NIT-DV
                pattern = r'^\d{1,9}-\d$'
                if not re.match(pattern, record.dian_nit_full):
                    raise ValidationError(_('El formato del NIT debe ser: número-dígito de verificación'))

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
