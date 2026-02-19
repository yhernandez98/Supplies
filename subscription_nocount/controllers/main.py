# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.tools.misc import formatLang


class SubscriptionDashboard(http.Controller):

    @http.route('/subscription_nocount/dashboard', type='http', auth='user', website=False)
    def dashboard(self, **kw):
        """Dashboard de suscripciones: KPIs por estado, recientes y top clientes. Todo en módulo de suscripciones."""
        Subscription = request.env['subscription.subscription'].with_context(active_test=False)
        all_subs = Subscription.search([])
        total_subscriptions = len(all_subs)
        total_active = len(all_subs.filtered(lambda s: s.state == 'active'))
        total_draft = len(all_subs.filtered(lambda s: s.state == 'draft'))
        total_cancelled = len(all_subs.filtered(lambda s: s.state == 'cancelled'))

        state_labels = {
            'active': 'Activas',
            'draft': 'Borrador',
            'cancelled': 'Canceladas',
        }
        by_state = []
        for state in ('active', 'draft', 'cancelled'):
            count = len(all_subs.filtered(lambda s: s.state == state))
            by_state.append({
                'name': state_labels.get(state, state),
                'count': count,
                'bar_style': 'width: %s%%' % min(100, int(count * 100.0 / max(1, total_subscriptions))),
                'bar_class': 'green' if state == 'active' else ('orange' if state == 'draft' else 'gray'),
            })
        max_state = max(1, max((c['count'] for c in by_state), default=1))
        for c in by_state:
            c['bar_style'] = 'width: %s%%' % min(100, int((c['count'] or 0) * 100.0 / max_state))

        recent = Subscription.search([], order='write_date desc', limit=15)
        recent_list = []
        for sub in recent:
            amount = sub.monthly_amount or 0
            amount_str = formatLang(request.env, amount, currency_obj=sub.currency_id, digits=0) if sub.currency_id else str(amount)
            recent_list.append({
                'name': sub.name or '',
                'partner': sub.partner_id.name or '',
                'state_label': state_labels.get(sub.state, sub.state or ''),
                'monthly_amount': amount_str,
            })

        partner_counts = {}
        for sub in all_subs:
            if sub.partner_id:
                name = sub.partner_id.name or 'Sin cliente'
                partner_counts[name] = partner_counts.get(name, 0) + 1
        top_partners_raw = sorted(partner_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        max_partner = max(1, max((q for _, q in top_partners_raw), default=1))
        top_partners = [
            {'name': n, 'count': q, 'bar_style': 'width: %s%%' % min(100, int(q * 100.0 / max_partner))}
            for n, q in top_partners_raw
        ]

        try:
            base_url = request.httprequest.url_root.rstrip('/')
        except Exception:
            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url', '').rstrip('/')
        if not base_url:
            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url', '').rstrip('/')
        action_subscription = request.env.ref('subscription_nocount.action_subscription_subscription', raise_if_not_found=False)
        url_list = '%s/web#action=%s&model=subscription.subscription&view_type=list' % (base_url, action_subscription.id) if action_subscription else '%s/web#model=subscription.subscription' % base_url
        url_back = base_url + '/web'

        values = {
            'total_subscriptions': total_subscriptions,
            'total_active': total_active,
            'total_draft': total_draft,
            'total_cancelled': total_cancelled,
            'by_state': by_state,
            'recent_list': recent_list,
            'top_partners': top_partners,
            'url_back': url_back,
            'url_list': url_list,
        }
        return request.render('subscription_nocount.subscription_dashboard_page', values)
