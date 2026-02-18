# -*- coding: utf-8 -*-
from datetime import date, timedelta
from odoo import http
from odoo.http import request


class LicenseDashboard(http.Controller):

    @http.route('/subscription_licenses/dashboard', type='http', auth='user', website=False)
    def dashboard(self, **kw):
        """Dashboard moderno de licencias con KPIs, vencimientos y proveedores."""
        Template = request.env['license.template'].with_context(active_test=False)
        Assignment = request.env['license.assignment']
        Category = request.env['license.category']
        today = date.today()

        # Solo licencias activas para totales principales
        active_licenses = Template.search([('active', '=', True)])
        total_licenses = len(active_licenses)
        total_used = sum(active_licenses.mapped('used_licenses'))
        total_assignments = Assignment.search_count([('state', '=', 'active')])
        total_providers = request.env['license.provider.partner'].search_count([])

        # Resumen por categoría (licencias activas)
        categories = Category.search([])
        by_category = []
        for cat in categories:
            licenses_in_cat = active_licenses.filtered(lambda l: l.name == cat)
            if not licenses_in_cat:
                continue
            cat_used = sum(licenses_in_cat.mapped('used_licenses'))
            cat_assignments = sum(licenses_in_cat.mapped('assignment_count'))
            by_category.append({
                'name': cat.name or 'Sin categoría',
                'count': len(licenses_in_cat),
                'used': cat_used,
                'assignments': cat_assignments,
            })
        by_category.sort(key=lambda x: x['used'], reverse=True)
        max_cat_used = max(1, max((c['used'] for c in by_category), default=1))
        for c in by_category:
            pct = min(100, int((c['used'] or 0) * 100.0 / max_cat_used))
            c['bar_style'] = 'width: %s%%' % pct

        # Próximas a vencer (asignaciones activas con end_date en 30, 60, 90 días)
        active_assignments = Assignment.search([
            ('state', '=', 'active'),
            ('end_date', '!=', False),
            ('end_date', '>=', today),
        ])
        end_30 = today + timedelta(days=30)
        end_60 = today + timedelta(days=60)
        end_90 = today + timedelta(days=90)
        # Cada licencia solo cuenta en un rango: 1-30 días, 31-60 días o 61-90 días
        expiring_30 = sum(1 for a in active_assignments if a.end_date and a.end_date <= end_30)
        expiring_60 = sum(1 for a in active_assignments if a.end_date and end_30 < a.end_date <= end_60)
        expiring_90 = sum(1 for a in active_assignments if a.end_date and end_60 < a.end_date <= end_90)

        def _license_name(a):
            if a.license_id and a.license_id.product_id:
                return a.license_id.product_id.name or ''
            if a.license_id and a.license_id.name:
                return a.license_id.name.name or ''
            return ''

        expiring_list = sorted(
            [{'client': (a.partner_id.name or ''), 'license': _license_name(a), 'end_date': a.end_date, 'provider': (a.license_provider_id.name or '')}
            for a in active_assignments if a.end_date and a.end_date <= end_90
        ], key=lambda x: x['end_date'])[:15]

        # Proveedores con más licencias contratadas (suma de quantity en asignaciones activas)
        provider_totals = {}
        for a in Assignment.search([('state', '=', 'active'), ('license_provider_id', '!=', False)]):
            name = a.license_provider_id.name or 'Sin proveedor'
            provider_totals[name] = provider_totals.get(name, 0) + (a.quantity or 0)
        top_providers_raw = sorted(provider_totals.items(), key=lambda x: x[1], reverse=True)[:10]
        max_provider_qty = max(1, max((q for _, q in top_providers_raw), default=1))
        top_providers = [{'name': n, 'qty': q, 'bar_style': 'width: %s%%' % min(100, int(q * 100.0 / max_provider_qty))} for n, q in top_providers_raw]

        # Usar la URL de la petición actual (mismo host que el usuario usa)
        try:
            base_url = request.httprequest.url_root.rstrip('/')
        except Exception:
            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url', '').rstrip('/')
        if not base_url:
            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url', '').rstrip('/')
        action_license = request.env.ref('subscription_licenses.action_license', raise_if_not_found=False)
        action_assignments = request.env.ref('subscription_licenses.action_license_assignment_by_partner', raise_if_not_found=False)
        action_providers = request.env.ref('subscription_licenses.action_license_providers_partners', raise_if_not_found=False)

        url_list = '%s/web#action=%s&model=license.template&view_type=list' % (base_url, action_license.id) if action_license else '%s/web#model=license.template' % base_url
        url_assignments = '%s/web#action=%s&model=license.assignment' % (base_url, action_assignments.id) if action_assignments else '%s/web#model=license.assignment' % base_url
        url_providers = '%s/web#action=%s&model=license.provider.partner' % (base_url, action_providers.id) if action_providers else '%s/web#model=license.provider.partner' % base_url
        url_back = base_url + '/web'

        values = {
            'total_licenses': total_licenses,
            'total_used': total_used,
            'total_assignments': total_assignments,
            'total_providers': total_providers,
            'by_category': by_category,
            'max_cat_used': max_cat_used,
            'expiring_30': expiring_30,
            'expiring_60': expiring_60,
            'expiring_90': expiring_90,
            'expiring_list': expiring_list,
            'top_providers': top_providers,
            'url_back': url_back,
            'url_list': url_list,
            'url_assignments': url_assignments,
            'url_providers': url_providers,
        }
        return request.render('subscription_licenses.dashboard_page', values)
