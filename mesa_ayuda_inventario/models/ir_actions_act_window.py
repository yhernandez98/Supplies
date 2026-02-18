# -*- coding: utf-8 -*-
"""Heredar ir.actions.act_window para inyectar dominio/contexto de inventario por cliente al recargar (F5)."""

from odoo import api, models
import logging

_logger = logging.getLogger(__name__)


class IrActionsActWindow(models.Model):
    _inherit = 'ir.actions.act_window'

    def read(self, fields=None, load='_classic_read'):
        result = super().read(fields=fields, load=load)
        self._inject_customer_inventory_scope(result)
        return result

    def _inject_customer_inventory_scope(self, result):
        """Si la acción es list/kanban de inventario de cliente y hay partner en sesión, inyectar domain y context."""
        try:
            from odoo.http import request
        except ImportError:
            return
        if not request or not getattr(request, 'session', None):
            return
        partner_id = request.session.get('customer_inventory_partner_id')
        if not partner_id:
            return
        partner = self.env['res.partner'].browse(partner_id)
        if not partner.exists():
            return
        action_list = self.env.ref(
            'mesa_ayuda_inventario.action_customer_inventory_list_only',
            raise_if_not_found=False,
        )
        action_kanban = self.env.ref(
            'mesa_ayuda_inventario.action_customer_inventory_kanban_only',
            raise_if_not_found=False,
        )
        target_ids = set()
        if action_list:
            target_ids.add(action_list.id)
        if action_kanban:
            target_ids.add(action_kanban.id)
        if not target_ids:
            return
        try:
            domain = partner._get_customer_inventory_domain()
        except Exception:
            return
        allowed_ids = []
        for d in domain:
            if isinstance(d, (list, tuple)) and len(d) >= 3 and d[0] == 'id' and d[1] == 'in':
                allowed_ids = list(d[2] or [])
                break
        from odoo.tools.safe_eval import safe_eval
        list_action_id = action_list.id if action_list else None
        for values in result:
            if values.get('id') not in target_ids:
                continue
            values['domain'] = domain
            raw_ctx = values.get('context')
            if isinstance(raw_ctx, str):
                try:
                    ctx = safe_eval(raw_ctx, {'uid': self.env.uid})
                except Exception:
                    ctx = {}
            else:
                ctx = dict(raw_ctx or {})
            ctx['default_customer_id'] = partner_id
            ctx['active_partner_id'] = partner_id
            ctx['customer_inventory_allowed_lot_ids'] = allowed_ids
            if values.get('id') == list_action_id:
                ctx.setdefault('group_by', ['customer_id', 'product_asset_category_id', 'product_asset_class_id'])
            values['context'] = ctx
        return
