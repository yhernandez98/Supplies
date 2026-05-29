# -*- coding: utf-8 -*-
import json

from odoo import http, fields
from odoo.http import request
from urllib.parse import quote_plus


class InventoryLabHubController(http.Controller):

    @http.route('/inventory_dashboard_simple/lab_hub', type='http', auth='user', website=False)
    def lab_hub_dashboard(self, **kw):
        Assignment = request.env['component.lab.assignment']
        Acta = request.env['component.lab.acta']
        state_labels = dict(Assignment._fields['state'].selection)
        acta_type_labels = dict(Acta._fields['acta_type'].selection)

        def _state_label(value):
            return state_labels.get(value, value or '')

        def _acta_type_label(value):
            return acta_type_labels.get(value, value or '')

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
                    'state': rec.state,
                    'state_label': _state_label(rec.state),
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
                if acta_field == 'pending_request_acta_number':
                    technician = recs[0].requested_by_user_id.display_name if recs[0].requested_by_user_id else technician
                responsible = recs[0].responsible_user_id.display_name if recs[0].responsible_user_id else ''
                items = [{
                    'serial': r.lot_id.name or '',
                    'product': r.product_id.display_name or '',
                    'state': r.state,
                    'state_label': _state_label(r.state),
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
        inventory_rows_payload = []
        for rec in inventory_rows:
            inventory_rows_payload.append({
                'serial': rec.lot_id.name or '',
                'product': rec.product_id.display_name or '',
                'state': rec.state,
                'state_label': _state_label(rec.state),
                'responsible': rec.responsible_user_id.display_name or '',
                'technician': rec.technician_user_id.display_name or '',
                'expected_return_date': rec.expected_return_date or '',
            })

        acta_rows_payload = []
        for acta in acta_rows:
            acta_rows_payload.append({
                'id': acta.id,
                'name': acta.name or '',
                'event_date_display': acta.event_date.strftime('%d/%m/%Y') if acta.event_date else '',
                'acta_type': acta.acta_type,
                'acta_type_label': _acta_type_label(acta.acta_type),
                'serial': acta.assignment_id.lot_id.name or '',
                'product': acta.assignment_id.product_id.display_name or '',
                'responsible': acta.responsible_user_id.display_name or '',
                'technician': acta.technician_user_id.display_name or '',
                'created_by': acta.created_by_user_id.display_name or '',
                'technician_id': acta.technician_user_id.id if acta.technician_user_id else '',
                'event_date_filter': acta.event_date.strftime('%Y-%m-%d') if acta.event_date else '',
            })
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
                'state_label': _state_label(rec.state),
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
                'state_label': _state_label(rec.state),
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
            'inventory_rows': inventory_rows_payload,
            'acta_rows': acta_rows_payload,
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

    @http.route('/inventory_dashboard_simple/supplies_hub', type='http', auth='user', website=False)
    def supplies_hub_dashboard(self, **kw):
        Assignment = request.env['supplies.assignment']
        Reassignment = request.env['supplies.assignment.reassignment']
        Lot = request.env['stock.lot']
        Quant = request.env['stock.quant']
        Employee = request.env['hr.employee']

        base_url = request.httprequest.url_root.rstrip('/')
        url_back = base_url + '/web'
        url_backend = '%s/web#action=%s' % (
            base_url,
            request.env['ir.model.data']._xmlid_to_res_id(
                'inventory_dashboard_simple.action_supplies_assignment'
            ),
        )

        state_labels = dict(Assignment._fields['state'].selection)
        assigned = Assignment.search([('state', '=', 'assigned')], order='id desc')
        returned = Assignment.search([('state', '=', 'returned')], order='id desc', limit=100)
        assigned_users = assigned.mapped('employee_id')

        exist_loc = Assignment._find_exist_location()
        available_catalog = []
        available_products_map = {}
        if exist_loc:
            quants = Quant.search([
                ('location_id', 'child_of', exist_loc.id),
                ('quantity', '>', 0),
                ('lot_id', '!=', False),
                ('company_id', '=', request.env.company.id),
            ], order='id desc')
            assigned_lot_ids = set(assigned.mapped('lot_id').ids)
            seen = set()
            for q in quants:
                if not q.lot_id or q.lot_id.id in seen:
                    continue
                seen.add(q.lot_id.id)
                if q.lot_id.id in assigned_lot_ids:
                    continue
                available_catalog.append({
                    'product_id': q.product_id.id,
                    'lot_id': q.lot_id.id,
                    'serial': q.lot_id.name or '',
                    'product': q.product_id.display_name or '',
                    'qty': q.quantity,
                })
                if q.product_id.id not in available_products_map:
                    available_products_map[q.product_id.id] = {
                        'id': q.product_id.id,
                        'name': q.product_id.display_name or '',
                    }

        assigned_cards = []
        for rec in assigned[:300]:
            assignee_name = rec.employee_id.name or rec.user_id.display_name or ''
            associated_items = []
            supply_lines = rec.lot_id.lot_supply_line_ids if rec.lot_id else request.env['stock.lot.supply.line']
            for line in supply_lines:
                item_name = line.product_id.display_name or ''
                item_serial = line.related_lot_id.name or ''
                item_qty = line.quantity or 0.0
                if not item_name and not item_serial:
                    continue
                associated_items.append({
                    'name': item_name,
                    'serial': item_serial,
                    'qty': item_qty,
                })
            assigned_cards.append({
                'id': rec.id,
                'user_id': rec.employee_id.id if rec.employee_id else 0,
                'ref': rec.name or '',
                'user': assignee_name,
                'user_key': assignee_name.lower(),
                'product': rec.product_id.display_name or '',
                'serial': rec.lot_id.name or '',
                'qty': rec.quantity,
                'assigned_date': rec.assignment_date.strftime('%d/%m/%Y %H:%M') if rec.assignment_date else '',
                'availability': rec.availability_display or '',
                'state_label': state_labels.get(rec.state, rec.state or ''),
                'associated_items': associated_items,
                'signature_state': rec.signature_state or 'pending',
                'signature_state_label': 'Firmada' if rec.signature_state == 'signed' else 'Pendiente firmas',
                'sign_url': '%s/web#id=%s&model=supplies.assignment&view_type=form' % (base_url, rec.id),
            })

        history_records = Assignment.search(
            [('state', 'in', ('assigned', 'returned'))],
            order='id desc',
            limit=2000,
        )
        history_by_user = {}
        for rec in history_records:
            uid = rec.employee_id.id if rec.employee_id else 0
            if uid not in history_by_user:
                history_by_user[uid] = []
            dt = rec.return_date if rec.state == 'returned' else rec.assignment_date
            history_by_user[uid].append({
                'ref': rec.name or '',
                'product': rec.product_id.display_name or '',
                'serial': rec.lot_id.name or '',
                'state': rec.state,
                'state_label': state_labels.get(rec.state, rec.state or ''),
                'date': dt.strftime('%d/%m/%Y %H:%M') if dt else '',
            })

        grouped_by_user = {}
        for c in assigned_cards:
            key = c['user_id'] or c['user']
            if key not in grouped_by_user:
                grouped_by_user[key] = {
                    'user_id': c['user_id'],
                    'user': c['user'],
                    'user_key': (c['user'] or '').lower(),
                    'assigned_count': 0,
                    'items': [],
                    'timeline': [],
                }
            grouped_by_user[key]['assigned_count'] += 1
            grouped_by_user[key]['items'].append(c)

        for _key, payload in grouped_by_user.items():
            payload['timeline'] = (history_by_user.get(payload.get('user_id') or 0, []) or [])[:15]

        user_cards = sorted(grouped_by_user.values(), key=lambda x: x['user_key'])

        returned_rows = [{
            'ref': rec.name or '',
            'id': rec.id,
            'user': rec.employee_id.name or rec.user_id.display_name or '',
            'product': rec.product_id.display_name or '',
            'serial': rec.lot_id.name or '',
            'qty': rec.quantity,
            'return_date': rec.return_date.strftime('%d/%m/%Y %H:%M') if rec.return_date else '',
        } for rec in returned]
        delivery_rows = [{
            'id': rec.id,
            'ref': rec.name or '',
            'user': rec.employee_id.name or rec.user_id.display_name or '',
            'product': rec.product_id.display_name or '',
            'serial': rec.lot_id.name or '',
            'assignment_date': rec.assignment_date.strftime('%d/%m/%Y %H:%M') if rec.assignment_date else '',
            'signature_state': rec.signature_state or 'pending',
            'signature_state_label': 'Firmada' if (rec.signature_state or 'pending') == 'signed' else 'Pendiente firmas',
        } for rec in Assignment.search([('assignment_date', '!=', False)], order='assignment_date desc, id desc', limit=300)]
        return_pick_rows = [{
            'id': rec.id,
            'ref': rec.name or '',
            'user': rec.employee_id.name or rec.user_id.display_name or '',
            'product': rec.product_id.display_name or '',
            'serial': rec.lot_id.name or '',
            'assigned_date': rec.assignment_date.strftime('%d/%m/%Y %H:%M') if rec.assignment_date else '',
        } for rec in assigned]

        pending_signature_rows = [{
            'id': rec.id,
            'ref': rec.name or '',
            'user': rec.employee_id.name or rec.user_id.display_name or '',
            'product': rec.product_id.display_name or '',
            'serial': rec.lot_id.name or '',
            'assigned_date': rec.assignment_date.strftime('%d/%m/%Y %H:%M') if rec.assignment_date else '',
            'act_type': 'Entrega',
            'sign_url': '%s/web#id=%s&model=supplies.assignment&view_type=form' % (base_url, rec.id),
        } for rec in assigned.filtered(lambda r: (r.signature_state or 'pending') != 'signed')]
        pending_signature_rows += [{
            'id': rec.id,
            'ref': rec.name or '',
            'user': rec.employee_id.name or rec.user_id.display_name or '',
            'product': rec.product_id.display_name or '',
            'serial': rec.lot_id.name or '',
            'assigned_date': rec.return_signature_request_date.strftime('%d/%m/%Y %H:%M') if rec.return_signature_request_date else (rec.assignment_date.strftime('%d/%m/%Y %H:%M') if rec.assignment_date else ''),
            'act_type': 'Devolucion',
            'sign_url': '%s/web#id=%s&model=supplies.assignment&view_type=form' % (base_url, rec.id),
        } for rec in assigned.filtered(lambda r: r.return_pending_signature and (r.return_signature_state or 'pending') != 'signed')]
        reassignment_rows = [{
            'id': rec.id,
            'acta': rec.name or '',
            'date': rec.date.strftime('%d/%m/%Y %H:%M') if rec.date else '',
            'user': rec.employee_id.name or rec.user_id.display_name or '',
            'old_product': rec.old_product_id.display_name or '',
            'old_serial': rec.old_lot_id.name or '',
            'new_product': rec.new_product_id.display_name or '',
            'new_serial': rec.new_lot_id.name or '',
        } for rec in Reassignment.search([], order='id desc', limit=200)]

        values = {
            'notice': kw.get('notice', ''),
            'notice_type': kw.get('notice_type', ''),
            'url_back': url_back,
            'url_backend': url_backend,
            'csrf_token': request.csrf_token(),
            'kpi_assigned_total': len(assigned),
            'kpi_users_with_assignments': len(assigned_users),
            'kpi_available_exist': len(available_catalog),
            'kpi_returned_total': Assignment.search_count([('state', '=', 'returned')]),
            'kpi_pending_signatures': len(pending_signature_rows),
            'assigned_cards': assigned_cards,
            'user_cards': user_cards,
            'available_catalog': available_catalog,
            'available_products': sorted(available_products_map.values(), key=lambda p: (p.get('name') or '').lower()),
            'returned_rows': returned_rows,
            'delivery_rows': delivery_rows,
            'return_pick_rows': return_pick_rows,
            'pending_signature_rows': pending_signature_rows,
            'reassignment_rows': reassignment_rows,
            'employees': Employee.search([], order='name asc'),
        }
        return request.render('inventory_dashboard_simple.supplies_hub_dashboard_page', values)

    @http.route('/inventory_dashboard_simple/supplies_hub/action', type='http', auth='user', methods=['POST'], website=False)
    def supplies_hub_action(self, **post):
        Assignment = request.env['supplies.assignment']
        Lot = request.env['stock.lot']
        base = '/inventory_dashboard_simple/supplies_hub'
        action = (post.get('action') or '').strip()
        raw_ids = (post.get('assignment_ids') or '').strip()
        user_id = int(post.get('user_id') or 0)
        employee_id = int(post.get('employee_id') or 0)
        lot_id = int(post.get('lot_id') or 0)
        qty = float(post.get('quantity') or 1.0)
        note = (post.get('note') or '').strip()
        return_assignment_id = int(post.get('return_assignment_id') or 0)
        return_mode = (post.get('return_mode') or '').strip()

        assignment_ids = []
        if raw_ids:
            for part in raw_ids.split(','):
                part = part.strip()
                if part.isdigit():
                    assignment_ids.append(int(part))

        try:
            if action == 'assign':
                employee_id = employee_id or user_id
                if not employee_id:
                    raise ValueError('Debe seleccionar el empleado a asignar.')
                if not lot_id:
                    raise ValueError('Debe seleccionar un serial disponible.')
                lot = Lot.browse(lot_id).exists()
                if not lot:
                    raise ValueError('El serial seleccionado no existe.')
                rec = Assignment.create({
                    'employee_id': employee_id,
                    'delivery_user_id': request.env.user.id,
                    'lot_id': lot.id,
                    'product_id': lot.product_id.id,
                    'quantity': qty if qty > 0 else 1.0,
                    'note': note,
                })
                result = rec.action_confirm_assignment()
                if isinstance(result, dict) and result.get('type') and result.get('type') != 'ir.actions.client':
                    return result
                msg = 'Asignación creada y trasladada fuera de Existencias.'
            elif action == 'return':
                target_id = return_assignment_id or (assignment_ids[:1][0] if assignment_ids else 0)
                if not target_id:
                    raise ValueError('Seleccione una asignación activa para devolución.')
                rec = Assignment.browse(target_id).exists()
                if not rec or rec.state != 'assigned':
                    raise ValueError('La asignación seleccionada no es válida o no está activa.')
                if return_mode == 'save_pending':
                    rec.write({
                        'return_pending_signature': True,
                        'return_signature_request_date': fields.Datetime.now(),
                    })
                    msg = 'Acta de devolución guardada pendiente por firmas.'
                else:
                    result = rec.action_return_assignment()
                    if isinstance(result, dict) and result.get('type') and result.get('type') != 'ir.actions.client':
                        return result
                    msg = 'Devolución registrada. El producto vuelve a Existencias.'
            elif action == 'replace':
                Reassignment = request.env['supplies.assignment.reassignment']
                if not assignment_ids:
                    raise ValueError('Debe seleccionar la asignación a reemplazar.')
                rec = Assignment.browse(assignment_ids[:1]).exists()
                if not rec or rec.state != 'assigned':
                    raise ValueError('La asignación a reemplazar no es válida o no está activa.')
                if not lot_id:
                    raise ValueError('Debe seleccionar el nuevo serial.')
                lot = Lot.browse(lot_id).exists()
                if not lot:
                    raise ValueError('El nuevo serial seleccionado no existe.')
                if lot.id == rec.lot_id.id:
                    raise ValueError('El nuevo serial debe ser diferente al actual.')

                # 1) devolver equipo actual a existencias
                ret = rec.action_return_assignment()
                if isinstance(ret, dict) and ret.get('type') and ret.get('type') != 'ir.actions.client':
                    return ret

                # 2) crear nueva asignación con el nuevo equipo al mismo usuario
                new_note = note or ''
                trace = 'Cambio desde %s (%s)' % (rec.product_id.display_name or '', rec.lot_id.name or '')
                new_note = (new_note + '\n' + trace).strip() if new_note else trace
                new_rec = Assignment.create({
                    'employee_id': rec.employee_id.id,
                    'delivery_user_id': request.env.user.id,
                    'lot_id': lot.id,
                    'product_id': lot.product_id.id,
                    'quantity': 1.0,
                    'note': new_note,
                })
                res_assign = new_rec.action_confirm_assignment()
                if isinstance(res_assign, dict) and res_assign.get('type') and res_assign.get('type') != 'ir.actions.client':
                    return res_assign
                Reassignment.create({
                    'employee_id': rec.employee_id.id,
                    'old_assignment_id': rec.id,
                    'new_assignment_id': new_rec.id,
                    'note': note or '',
                })
                msg = 'Equipo reemplazado correctamente: se devolvió el anterior y se asignó el nuevo.'
            else:
                raise ValueError('Acción no válida.')

            return request.redirect('%s?notice_type=success&notice=%s' % (base, quote_plus(msg)))
        except Exception as e:
            err = str(getattr(e, 'name', '') or str(e))
            return request.redirect('%s?notice_type=error&notice=%s' % (base, quote_plus(err)))

