# -*- coding: utf-8 -*-
import logging

from odoo import models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _pricelist_debug_format_pl(self, pricelist):
        if not pricelist:
            return 'False'
        return '%s (id=%s)' % (pricelist.display_name, pricelist.id)

    def _partner_pricelist_debug_fetch_property_rows(self, res_id_str):
        """Filas de property_product_pricelist para res.partner,<id>.

        En Odoo 19+ el modelo ``ir.property`` puede no estar expuesto en ``env``
        (KeyError); en ese caso se lee la tabla ``ir_property`` por SQL.
        """
        try:
            Prop = self.env['ir.property'].sudo()
        except KeyError:
            Prop = None
        if Prop is not None:
            props = Prop.search(
                [
                    ('name', '=', 'property_product_pricelist'),
                    ('type', '=', 'many2one'),
                    ('res_id', '=', res_id_str),
                ]
            )
            return [
                (
                    prop.id,
                    prop.company_id.name if prop.company_id else 'Global',
                    prop.value_reference,
                )
                for prop in props
            ]
        try:
            with self.env.cr.savepoint():
                self.env.cr.execute(
                    """
                    SELECT p.id, c.name, p.value_reference
                    FROM ir_property p
                    LEFT JOIN res_company c ON c.id = p.company_id
                    WHERE p.name = %s
                      AND p.type = %s
                      AND p.res_id = %s
                    """,
                    ('property_product_pricelist', 'many2one', res_id_str),
                )
                return [
                    (row[0], row[1] or 'Global', row[2])
                    for row in self.env.cr.fetchall()
                ]
        except Exception as exc:
            _logger.warning(
                'partner_pricelist_debug: lectura ir_property falló (%s): %s',
                res_id_str,
                exc,
            )
            return []

    def _partner_pricelist_debug_fetch_default_property_rows(self):
        """Filas de ir_property sin contacto (valor por defecto del modelo/campo)."""
        try:
            with self.env.cr.savepoint():
                self.env.cr.execute(
                    """
                    SELECT p.id, c.name, p.value_reference, COALESCE(p.res_id::text, '')
                    FROM ir_property p
                    LEFT JOIN res_company c ON c.id = p.company_id
                    WHERE p.name = %s
                      AND p.type = %s
                      AND (p.res_id IS NULL OR btrim(COALESCE(p.res_id::text, '')) = '')
                    ORDER BY p.company_id NULLS LAST, p.id
                    """,
                    ('property_product_pricelist', 'many2one'),
                )
                return [
                    (row[0], row[1] or 'Global', row[2], row[3])
                    for row in self.env.cr.fetchall()
                ]
        except Exception as exc:
            _logger.warning(
                'partner_pricelist_debug: lectura defaults ir_property: %s', exc
            )
            return []

    def _partner_pricelist_debug_company_default_pricelists(self):
        """Intenta leer listas por defecto desde res.company (nombres de campo varían por versión/módulos)."""
        out = []
        Company = self.env['res.company']
        candidate_fields = [
            'sale_order_default_pricelist_id',  # algunas versiones / personalizaciones
            'property_product_pricelist_id',
        ]
        try:
            companies = Company.search([])
        except Exception as exc:
            _logger.warning(
                'partner_pricelist_debug: no fue posible leer res.company: %s', exc
            )
            return out
        for company in companies:
            bits = []
            for fname in candidate_fields:
                if fname not in Company._fields:
                    continue
                try:
                    pl = company[fname]
                    if pl:
                        bits.append('%s=%s (id=%s)' % (fname, pl.display_name, pl.id))
                except Exception:
                    continue
            if bits:
                out.append('  [%s] %s' % (company.name, '; '.join(bits)))
        return out

    def _partner_pricelist_debug_get_icp_pricelist_fallbacks(self):
        """Lee parámetros usados por product.pricelist._get_partner_pricelist_multi en v19."""
        ICP = self.env['ir.config_parameter'].sudo()
        rows = []
        generic_key = 'res.partner.property_product_pricelist'
        generic_value = ICP.get_param(generic_key)
        rows.append((generic_key, generic_value))
        for company in self.env['res.company'].search([]):
            key = 'res.partner.property_product_pricelist_%s' % company.id
            value = ICP.get_param(key)
            rows.append((key, value))
        return rows

    def _get_pricelist_debug_report(self):
        """Texto plano para diagnosticar por qué la lista de precios parece borrarse o cambiar."""
        self.ensure_one()
        lines = []
        partner = self
        commercial = partner.commercial_partner_id

        lines.append('=== CONTACTO ===')
        lines.append('ID: %s' % partner.id)
        lines.append('Nombre: %s' % (partner.name or ''))
        lines.append('Es empresa: %s' % partner.is_company)
        lines.append(
            'Padre: %s (id=%s)'
            % (
                partner.parent_id.name if partner.parent_id else '-',
                partner.parent_id.id if partner.parent_id else '-',
            )
        )
        lines.append(
            'Partner comercial: %s (id=%s)'
            % (commercial.name or '', commercial.id)
        )
        lines.append('Usuario actual: %s' % self.env.user.display_name)
        allowed_ids = self.env.context.get('allowed_company_ids')
        if allowed_ids:
            allowed_cos = self.env['res.company'].browse(allowed_ids)
            lines.append(
                'Compañías en contexto (allowed_company_ids): %s'
                % ', '.join(allowed_cos.mapped('name'))
            )
        else:
            lines.append(
                'Compañía actual (env.company): %s' % (self.env.company.name or '')
            )
        lines.append('')

        lines.append('=== property_product_pricelist (ORM, compañía actual del env) ===')
        lines.append('Este registro: %s' % self._pricelist_debug_format_pl(partner.property_product_pricelist))
        lines.append(
            'specific_property_product_pricelist (actual): %s'
            % self._pricelist_debug_format_pl(partner.specific_property_product_pricelist)
        )
        if commercial != partner:
            lines.append(
                'Partner comercial: %s'
                % self._pricelist_debug_format_pl(commercial.property_product_pricelist)
            )
        lines.append('')

        lines.append('=== Origen por defecto (default_get) ===')
        default_vals = self.env['res.partner'].default_get(['property_product_pricelist'])
        default_pl_id = default_vals.get('property_product_pricelist')
        if default_pl_id:
            default_pl = self.env['product.pricelist'].browse(default_pl_id)
            lines.append(
                'default_get(property_product_pricelist): %s'
                % self._pricelist_debug_format_pl(default_pl)
            )
        else:
            lines.append('default_get(property_product_pricelist): False')
        lines.append('')

        lines.append('=== property_product_pricelist (with_company por cada compañía) ===')
        companies = self.env['res.company'].search([])
        for company in companies:
            pl = partner.with_company(company).property_product_pricelist
            specific_pl = partner.with_company(company).specific_property_product_pricelist
            lines.append(
                '  [%s] este contacto: %s | specific=%s'
                % (
                    company.name,
                    self._pricelist_debug_format_pl(pl),
                    self._pricelist_debug_format_pl(specific_pl),
                )
            )
        if commercial != partner:
            lines.append('--- Mismo análisis para partner comercial ---')
            for company in companies:
                pl = commercial.with_company(company).property_product_pricelist
                specific_pl = commercial.with_company(company).specific_property_product_pricelist
                lines.append(
                    '  [%s] comercial: %s | specific=%s'
                    % (
                        company.name,
                        self._pricelist_debug_format_pl(pl),
                        self._pricelist_debug_format_pl(specific_pl),
                    )
                )
        lines.append('')

        lines.append('=== Definición técnica del campo en runtime ===')
        field = self._fields.get('property_product_pricelist')
        if not field:
            lines.append('No existe self._fields["property_product_pricelist"] en este modelo.')
        else:
            lines.append('type=%s' % getattr(field, 'type', ''))
            lines.append('store=%s' % getattr(field, 'store', ''))
            lines.append('readonly=%s' % getattr(field, 'readonly', ''))
            lines.append(
                'company_dependent=%s'
                % getattr(field, 'company_dependent', '')
            )
            lines.append('related=%r' % (getattr(field, 'related', None),))
            lines.append('compute=%r' % (getattr(field, 'compute', None),))
        lines.append('')

        lines.append('=== Fallback en ir.config_parameter (Odoo 19) ===')
        lines.append(
            'Claves esperadas por _get_partner_pricelist_multi: '
            'res.partner.property_product_pricelist y '
            'res.partner.property_product_pricelist_<company_id>'
        )
        for key, raw_val in self._partner_pricelist_debug_get_icp_pricelist_fallbacks():
            if not raw_val:
                lines.append('  %s = %r' % (key, raw_val))
                continue
            pl_display = 'no encontrado'
            try:
                pl = self.env['product.pricelist'].browse(int(raw_val))
                if pl.exists():
                    pl_display = '%s (id=%s)' % (pl.display_name, pl.id)
            except Exception:
                pl_display = 'valor no entero'
            lines.append('  %s = %r -> %s' % (key, raw_val, pl_display))
        lines.append('')

        lines.append('=== Default por país (product.pricelist._get_country_pricelist_multi) ===')
        country = partner.country_id
        if not country:
            lines.append('El contacto no tiene país.')
        else:
            try:
                country_defaults = self.env['product.pricelist']._get_country_pricelist_multi([country.id])
                country_pl = country_defaults.get(country.id)
                lines.append(
                    'País %s (%s) -> %s'
                    % (
                        country.name,
                        country.code or '',
                        self._pricelist_debug_format_pl(country_pl),
                    )
                )
            except Exception as exc:
                lines.append('No fue posible calcular default por país: %s' % exc)
        lines.append('')

        lines.append('=== Propiedades guardadas (property_product_pricelist / ir_property) ===')
        try:
            self.env['ir.property']
        except KeyError:
            lines.append(
                '(Aviso: el modelo ir.property no está en el API de env en esta versión; '
                'las filas siguientes se leen por SQL si existe la tabla ir_property.)'
            )

        def dump_properties(label, p):
            lines.append('-- %s (res.partner,id=%s) --' % (label, p.id))
            rows = self._partner_pricelist_debug_fetch_property_rows('res.partner,%s' % p.id)
            if not rows:
                lines.append('  (sin filas para este contacto o tabla no disponible)')
            for prop_id, company_name, value_reference in rows:
                lines.append(
                    '  id=%s | company=%s | value_reference=%r'
                    % (prop_id, company_name, value_reference)
                )

        dump_properties('Este contacto', partner)
        if commercial != partner:
            dump_properties('Partner comercial', commercial)
        lines.append('')

        lines.append('=== Valor crudo en tabla res_partner (v19 JSONB/columna) ===')
        try:
            with self.env.cr.savepoint():
                self.env.cr.execute(
                    "SELECT property_product_pricelist FROM res_partner WHERE id = %s",
                    (partner.id,),
                )
                row = self.env.cr.fetchone()
                raw_value = row[0] if row else None
                lines.append('res_partner.property_product_pricelist = %r' % (raw_value,))
        except Exception as exc:
            lines.append(
                'No se pudo leer columna res_partner.property_product_pricelist: %s'
                % exc
            )
        lines.append('')

        lines.append('=== Valores por defecto (ir_property sin res_id de contacto) ===')
        lines.append(
            'Si arriba no hay filas para el contacto pero aquí sí, la lista que ves suele ser '
            'la predeterminada de la compañía (todos los clientes “heredan” la misma hasta que '
            'guardes una lista explícita en el contacto).'
        )
        def_rows = self._partner_pricelist_debug_fetch_default_property_rows()
        if not def_rows:
            lines.append('  (sin filas de defecto o consulta no disponible)')
        else:
            for prop_id, company_name, value_reference, res_raw in def_rows:
                lines.append(
                    '  id=%s | company=%s | value_reference=%r | res_id=%r'
                    % (prop_id, company_name, value_reference, res_raw)
                )
        lines.append('')

        lines.append('=== Campos en res.company relacionados (si existen) ===')
        company_bits = self._partner_pricelist_debug_company_default_pricelists()
        if not company_bits:
            lines.append('  (no se detectaron campos estándar de lista por defecto en res.company)')
        else:
            lines.extend(company_bits)
        lines.append('')

        orm_pl = partner.property_product_pricelist
        rows_partner_explicit = self._partner_pricelist_debug_fetch_property_rows(
            'res.partner,%s' % partner.id
        )
        lines.append('=== Conclusión automática (orientativa) ===')
        if rows_partner_explicit and orm_pl:
            lines.append(
                '- Hay filas en ir_property para este contacto: la lista está asociada explícitamente '
                'al partner (no solo por defecto).'
            )
        elif not rows_partner_explicit and orm_pl:
            lines.append(
                '- No hay fila específica en ir_property para este contacto (o no es visible por SQL), '
                'pero el ORM devuelve lista: %s.'
                % self._pricelist_debug_format_pl(orm_pl)
            )
            matched_default = False
            for _pid, _cname, vref in def_rows:
                if not vref or 'product.pricelist' not in vref:
                    continue
                try:
                    pl_id = int(str(vref).split(',')[-1])
                except (ValueError, TypeError):
                    continue
                if pl_id == orm_pl.id:
                    lines.append(
                        '- Ese id coincide con un valor por DEFECTO en ir_property para '
                        'compañía "%s": es normal que muchos contactos muestren la misma lista.'
                        % (_cname or 'Global')
                    )
                    matched_default = True
                    break
            if def_rows and not matched_default:
                lines.append(
                    '- Hay defaults en ir_property pero ninguno coincide por id con la lista ORM; '
                    'puede haber otro origen (Odoo 19 con otro almacenamiento, módulo de terceros, etc.).'
                )
            if not def_rows:
                lines.append(
                    '- Tampoco hay filas de “defecto” visibles por SQL: el valor puede venir de la nueva '
                    'capa de propiedades de Odoo 19 (fuera de ir_property) o de un valor calculado.'
                )
        lines.append('')

        lines.append('=== Notas ===')
        lines.append(
            '- Si ves lista en una compañía y False en otra, al guardar con distinta '
            'compañía activa solo se escribe la propiedad de esa compañía.'
        )
        lines.append(
            '- En contactos hijo, la lista mostrada puede seguir la del partner comercial '
            'según reglas de Odoo / vista.'
        )
        lines.append(
            '- Si no hay fila en ir.property, Odoo usa el valor por defecto (p. ej. lista de la compañía).'
        )

        return '\n'.join(lines)

    def action_debug_partner_pricelist(self):
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_('Solo administradores pueden usar esta herramienta.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Debug: lista de precios'),
            'res_model': 'partner.pricelist.debug.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_id': self.id,
            },
        }

    def action_set_specific_pricelist_from_current(self):
        """Abre asistente para fijar explícitamente la lista específica del contacto."""
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_('Solo administradores pueden usar esta herramienta.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Fijar lista específica'),
            'res_model': 'partner.set.specific.pricelist.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_id': self.id,
            },
        }
