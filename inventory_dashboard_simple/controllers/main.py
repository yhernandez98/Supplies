# -*- coding: utf-8 -*-
import json

from odoo import http
from odoo.http import request
from urllib.parse import quote_plus


class InventoryLabHubController(http.Controller):

    @http.route('/inventory_dashboard_simple/lab_hub', type='http', auth='user', website=False)
    def lab_hub_dashboard(self, **kw):
        Assignment = request.env['component.lab.assignment']
        Acta = request.env['component.lab.acta']
        domain_active = [('state', '!=', 'returned_to_exist')]
        all_active = Assignment.search(domain_active, order='id desc')

        by_state = {
            'in_lab_pool': all_active.filtered(lambda r: r.state in ('in_lab_pool', 'returned_to_responsible')),
            'tech_request_pending_approval': all_active.filtered(lambda r: r.state == 'tech_request_pending_approval'),
            'with_technician': all_active.filtered(lambda r: r.state == 'with_technician'),
            'tech_return_pending_approval': all_active.filtered(lambda r: r.state == 'tech_return_pending_approval'),
            'returned_to_responsible': all_active.filtered(lambda r: r.state == 'returned_to_responsible'),
        }
        returned = Assignment.search([('state', '=', 'returned_to_exist')], order='id desc', limit=20)

        def _card_data(records, limit=8):
            data = []
            for rec in records[:limit]:
                data.append({
                    'id': rec.id,
                    'product': rec.product_id.display_name or '',
                    'serial': rec.lot_id.name or '',
                    'responsible': rec.responsible_user_id.display_name or '',
                    'technician': rec.technician_user_id.display_name or '',
                    'availability': rec.availability_display or '',
                    'expected_return_date': rec.expected_return_date,
                    'remaining_days': rec.remaining_days,
                    'is_overdue': rec.is_overdue,
                    'extension_request_state': rec.extension_request_state,
                    'extension_request_date': rec.extension_request_date,
                    'extension_request_reason': rec.extension_request_reason or '',
                })
            return data

        def _group_by_acta(records, acta_field):
            groups = {}
            for rec in records:
                key = (getattr(rec, acta_field) or '').strip()
                if not key:
                    key = 'SIN_ACTA'
                groups.setdefault(key, []).append(rec)
            payload = []
            for acta_number, recs in groups.items():
                technician = recs[0].technician_user_id.display_name if recs[0].technician_user_id else ''
                responsible = recs[0].responsible_user_id.display_name if recs[0].responsible_user_id else ''
                items = [{
                    'serial': r.lot_id.name or '',
                    'product': r.product_id.display_name or '',
                    'state': r.state,
                } for r in recs]
                dates = sorted({r.expected_return_date for r in recs if r.expected_return_date})
                if not dates:
                    expected_return_display = ''
                elif len(dates) == 1:
                    expected_return_display = dates[0].strftime('%d/%m/%Y')
                else:
                    expected_return_display = '%s – %s' % (
                        dates[0].strftime('%d/%m/%Y'),
                        dates[-1].strftime('%d/%m/%Y'),
                    )
                payload.append({
                    'acta_number': acta_number,
                    'count': len(recs),
                    'technician': technician,
                    'responsible': responsible,
                    'expected_return_display': expected_return_display,
                    'items': items,
                    'items_json': json.dumps(items),
                })
            payload.sort(key=lambda x: x['acta_number'], reverse=True)
            return payload

        # URLs de acciones existentes
        base_url = request.httprequest.url_root.rstrip('/')
        ref = request.env.ref
        url_back = base_url + '/web'
        url_asignar = '%s/web#action=%s' % (
            base_url,
            ref('inventory_dashboard_simple.action_component_lab_assign_tech_wizard').id,
        )
        url_dev_tech = '%s/web#action=%s' % (
            base_url,
            ref('inventory_dashboard_simple.action_component_lab_tech_return_wizard').id,
        )
        url_dev_resp = '%s/web#action=%s' % (
            base_url,
            ref('inventory_dashboard_simple.action_component_lab_responsible_return_wizard').id,
        )
        report_ids = Assignment.search([]).ids
        report_ids_str = ','.join(str(i) for i in report_ids) if report_ids else '0'
        url_report_pdf = '%s/report/pdf/inventory_dashboard_simple.report_component_lab_assignment_pdf/%s' % (
            base_url,
            report_ids_str,
        )
        technicians = request.env['res.users'].search([('share', '=', False)])
        inventory_rows = Assignment.search([('state', '!=', 'returned_to_exist')], order='state, id desc', limit=200)
        acta_rows = Acta.search([], order='id desc', limit=300)
        acta_filter_technicians = []
        acta_tech_seen = set()
        for acta_rec in acta_rows:
            if acta_rec.technician_user_id and acta_rec.technician_user_id.id not in acta_tech_seen:
                acta_tech_seen.add(acta_rec.technician_user_id.id)
                acta_filter_technicians.append({
                    'id': acta_rec.technician_user_id.id,
                    'name': acta_rec.technician_user_id.display_name,
                })
        acta_filter_technicians.sort(key=lambda x: (x.get('name') or '').lower())
        tech_actas = _group_by_acta(by_state['with_technician'], 'current_assign_acta_number')
        pending_actas = _group_by_acta(by_state['tech_return_pending_approval'], 'pending_return_acta_number')
        request_pending_actas = _group_by_acta(by_state['tech_request_pending_approval'], 'pending_request_acta_number')
        extension_pending_actas = _group_by_acta(
            by_state['with_technician'].filtered(lambda r: r.extension_request_state == 'pending'),
            'current_assign_acta_number'
        )
        my_tech_records = by_state['with_technician'].filtered(lambda r: r.technician_user_id == request.env.user)
        my_tech_actas = _group_by_acta(my_tech_records, 'current_assign_acta_number')
        request_catalog = []
        for rec in all_active:
            is_available = rec.state == 'in_lab_pool'
            request_catalog.append({
                'id': rec.id,
                'serial': rec.lot_id.name or '',
                'product': rec.product_id.display_name or '',
                'state': rec.state,
                'is_available': is_available,
                'status_text': 'Disponible' if is_available else 'No disponible',
            })
        pool_return_catalog = []
        for rec in by_state['in_lab_pool']:
            pool_return_catalog.append({
                'id': rec.id,
                'serial': rec.lot_id.name or '',
                'product': rec.product_id.display_name or '',
                'state': rec.state,
            })

        values = {
            'notice': kw.get('notice', ''),
            'notice_type': kw.get('notice_type', ''),
            'kpi_total_activos': len(all_active),
            'kpi_pool': len(by_state['in_lab_pool']),
            'kpi_tech': len(by_state['with_technician']),
            'kpi_resp': len(by_state['returned_to_responsible']),
            'kpi_pending_return_approval': len(by_state['tech_return_pending_approval']),
            'kpi_pending_request_approval': len(by_state['tech_request_pending_approval']),
            'kpi_pending_extension_approval': len(
                by_state['with_technician'].filtered(lambda r: r.extension_request_state == 'pending')
            ),
            'kpi_devueltos': len(returned),
            'cards_pool': _card_data(by_state['in_lab_pool']),
            'cards_tech': _card_data(by_state['with_technician']),
            'cards_pending': _card_data(by_state['tech_return_pending_approval']),
            'cards_resp': _card_data(by_state['returned_to_responsible']),
            'tech_actas': tech_actas,
            'pending_actas': pending_actas,
            'request_pending_actas': request_pending_actas,
            'extension_pending_actas': extension_pending_actas,
            'my_tech_actas': my_tech_actas,
            'request_catalog': request_catalog,
            'pool_return_catalog': pool_return_catalog,
            'url_back': url_back,
            'url_asignar': url_asignar,
            'url_dev_tech': url_dev_tech,
            'url_dev_resp': url_dev_resp,
            'url_report_pdf': url_report_pdf,
            'technicians': technicians,
            'inventory_rows': inventory_rows,
            'acta_rows': acta_rows,
            'acta_filter_technicians': acta_filter_technicians,
            'hub_base_url': base_url,
            'csrf_token': request.csrf_token(),
        }
        return request.render('inventory_dashboard_simple.lab_hub_dashboard_page', values)

    @http.route('/inventory_dashboard_simple/lab_hub/action', type='http', auth='user', methods=['POST'], website=False)
    def lab_hub_action(self, **post):
        raw_ids = (post.get('assignment_ids') or '').strip()
        raw_acta_numbers = (post.get('acta_numbers') or '').strip()
        pending_kind = (post.get('pending_kind') or '').strip()
        action = post.get('action')
        technician_id = int(post.get('technician_id') or 0)
        reject_reason = post.get('reject_reason') or ''
        expected_return_date = post.get('expected_return_date') or ''
        base = '/inventory_dashboard_simple/lab_hub'

        id_list = []
        if raw_ids:
            for part in raw_ids.split(','):
                part = part.strip()
                if part.isdigit():
                    id_list.append(int(part))
        acta_numbers = [a.strip() for a in raw_acta_numbers.split(',') if a.strip()] if raw_acta_numbers else []
        Assignment = request.env['component.lab.assignment']
        assignments = Assignment.browse(id_list).exists() if id_list else Assignment.browse()
        if action in (
            'tech_return',
            'resolve_tech_return',
            'resolve_tech_request',
            'request_extension',
            'resolve_responsible_pending',
        ) and not acta_numbers:
            return request.redirect(base + '?notice_type=error&notice=' + quote_plus('Seleccione al menos un acta.'))
        if action not in (
            'tech_return',
            'resolve_tech_return',
            'resolve_tech_request',
            'request_extension',
            'resolve_responsible_pending',
        ) and not id_list:
            return request.redirect(base + '?notice_type=error&notice=' + quote_plus('Seleccione al menos un activo.'))
        if action == 'tech_return' and acta_numbers:
            assignments = Assignment.search([
                ('state', '=', 'with_technician'),
                ('current_assign_acta_number', 'in', acta_numbers),
            ])
        if action == 'resolve_tech_return' and acta_numbers:
            assignments = Assignment.search([
                ('state', '=', 'tech_return_pending_approval'),
                ('pending_return_acta_number', 'in', acta_numbers),
            ])
        if action == 'resolve_tech_request' and acta_numbers:
            assignments = Assignment.search([
                ('state', '=', 'tech_request_pending_approval'),
                ('pending_request_acta_number', 'in', acta_numbers),
            ])
        if action == 'request_extension' and acta_numbers:
            assignments = Assignment.search([
                ('state', '=', 'with_technician'),
                ('current_assign_acta_number', 'in', acta_numbers),
            ])
        if action == 'resolve_responsible_pending' and acta_numbers:
            if pending_kind == 'return':
                assignments = Assignment.search([
                    ('state', '=', 'tech_return_pending_approval'),
                    ('pending_return_acta_number', 'in', acta_numbers),
                ])
            elif pending_kind == 'request':
                assignments = Assignment.search([
                    ('state', '=', 'tech_request_pending_approval'),
                    ('pending_request_acta_number', 'in', acta_numbers),
                ])
            elif pending_kind == 'extension':
                assignments = Assignment.search([
                    ('state', '=', 'with_technician'),
                    ('extension_request_state', '=', 'pending'),
                    ('current_assign_acta_number', 'in', acta_numbers),
                ])
            else:
                assignments = Assignment.browse()
        if not assignments:
            return request.redirect(base + '?notice_type=error&notice=' + quote_plus('No hay activos válidos para la operación.'))

        try:
            if action == 'assign_tech':
                if not technician_id:
                    raise ValueError('Debe seleccionar técnico.')
                if not expected_return_date:
                    raise ValueError('Debe indicar fecha estimada de devolución.')
                tech = request.env['res.users'].browse(technician_id).exists()
                if not tech:
                    raise ValueError('El técnico seleccionado no existe.')
                assignments.action_assign_technician(tech, expected_return_date)
                msg = 'Activos asignados a técnico.'
            elif action == 'tech_return':
                assignments.action_return_from_technician()
                msg = 'Solicitud de devolución técnico registrada.'
            elif action == 'responsible_return':
                wiz = request.env['component.lab.responsible.return.wizard'].create({
                    'line_ids': [(0, 0, {'assignment_id': ass.id, 'quantity': 1.0}) for ass in assignments],
                })
                wiz.action_process()
                msg = 'Devolución a existencias procesada y validada.'
            elif action == 'mark_available':
                assignments.action_mark_available_in_pool()
                msg = 'Activos marcados como disponibles en laboratorio.'
            elif action == 'request_extension':
                new_date = post.get('extension_date')
                reason = post.get('extension_reason') or ''
                assignments.action_request_extension(new_date, reason)
                msg = 'Solicitud de prórroga enviada al responsable.'
            elif action == 'approve_extension':
                assignments.action_approve_extension()
                msg = 'Prórroga aprobada y fecha estimada actualizada.'
            elif action == 'approve_tech_return':
                assignments.action_approve_technician_return()
                msg = 'Devolución del técnico aprobada.'
            elif action == 'reject_tech_return':
                assignments.action_reject_technician_return(reject_reason)
                msg = 'Devolución del técnico rechazada.'
            elif action == 'resolve_tech_return':
                decision = post.get('return_decision')
                if decision == 'approve':
                    assignments.action_approve_technician_return()
                    msg = 'Devolución del técnico aprobada.'
                elif decision == 'reject':
                    assignments.action_reject_technician_return(reject_reason)
                    msg = 'Devolución del técnico rechazada.'
                else:
                    raise ValueError('Debe escoger aprobar o rechazar.')
            elif action == 'tech_request':
                assignments.action_request_from_technician()
                msg = 'Solicitud registrada para %s activo(s) disponibles.' % len(assignments)
            elif action == 'resolve_tech_request':
                decision = post.get('return_decision')
                if decision == 'approve':
                    assignments.action_approve_tech_request(post.get('expected_return_date') or False)
                    msg = 'Solicitud de técnico aprobada.'
                elif decision == 'reject':
                    assignments.action_reject_tech_request(reject_reason)
                    msg = 'Solicitud de técnico rechazada.'
                else:
                    raise ValueError('Debe escoger aprobar o rechazar.')
            elif action == 'resolve_responsible_pending':
                decision = post.get('return_decision')
                if pending_kind == 'extension':
                    if decision == 'approve':
                        assignments.action_approve_extension()
                        msg = 'Prórroga(s) aprobada(s).'
                    elif decision == 'reject':
                        assignments.action_reject_extension(reject_reason)
                        msg = 'Prórroga(s) rechazada(s).'
                    else:
                        raise ValueError('Debe escoger aprobar o rechazar.')
                elif pending_kind == 'request':
                    if decision == 'approve':
                        assignments.action_approve_tech_request(post.get('expected_return_date') or False)
                        msg = 'Solicitud(es) de técnico aprobada(s).'
                    elif decision == 'reject':
                        assignments.action_reject_tech_request(reject_reason)
                        msg = 'Solicitud(es) de técnico rechazada(s).'
                    else:
                        raise ValueError('Debe escoger aprobar o rechazar.')
                elif pending_kind == 'return':
                    if decision == 'approve':
                        assignments.action_approve_technician_return()
                        msg = 'Devolución(es) del técnico aprobada(s).'
                    elif decision == 'reject':
                        assignments.action_reject_technician_return(reject_reason)
                        msg = 'Devolución(es) del técnico rechazada(s).'
                    else:
                        raise ValueError('Debe escoger aprobar o rechazar.')
                else:
                    raise ValueError('Tipo de pendiente no válido.')
            else:
                raise ValueError('Acción no válida.')
            url = '%s?notice_type=success&notice=%s' % (base, quote_plus(msg))
            return request.redirect(url)
        except Exception as e:
            err = str(getattr(e, 'name', '') or str(e))
            url = '%s?notice_type=error&notice=%s' % (base, quote_plus(err))
            return request.redirect(url)

