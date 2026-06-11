# -*- coding: utf-8 -*-
from odoo import api, models

from .helpdesk_ticket_return_e4_item import RETURN_E4_LINE_ROLE_LABELS
from .stock_picking_return_e4 import RETURN_E4_DESTINATION_LABELS


class ReportHelpdeskTicketReturnE4Verification(models.AbstractModel):
    _name = 'report.inventory_dashboard_simple.report_return_e4_ticket_review'
    _description = 'Informe verificación E4 (ticket)'
    _table = 'report_invdash_rpt_e4_ticket_review'

    @api.model
    def _get_report_values(self, docids, data=None):
        tickets = self.env['helpdesk.ticket'].browse(docids).exists()
        report_rows = {}
        report_item_details = {}
        for ticket in tickets:
            rows = []
            details = []
            for item in ticket._return_e4_report_selected_items():
                lot = item.lot_id
                role = RETURN_E4_LINE_ROLE_LABELS.get(
                    item.line_role, item.line_role or '',
                )
                serial = lot.name or lot.display_name or ''
                rows.append({
                    'role': role,
                    'serial': serial,
                    'product': item.product_id.display_name or '',
                    'inventory_plate': getattr(lot, 'inventory_plate', '') or '',
                    'security_plate': getattr(lot, 'security_plate', '') or '',
                    'destination': RETURN_E4_DESTINATION_LABELS.get(
                        item.destination, item.destination or '',
                    ) or '—',
                    'state': item.state_label or '',
                    'note': item.line_note or '',
                    'review_note': item._report_informe_plaintext(),
                })
            for anchor in ticket._return_e4_report_informe_anchors():
                details.append({
                    'title': anchor._return_e4_informe_detail_title(),
                    'informe_html': anchor.report_informe_html or '',
                })
            report_rows[ticket.id] = rows
            report_item_details[ticket.id] = details
        return {
            'doc_ids': docids,
            'doc_model': 'helpdesk.ticket',
            'docs': tickets,
            'report_rows': report_rows,
            'report_item_details': report_item_details,
        }
