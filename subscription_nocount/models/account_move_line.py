# -*- coding: utf-8 -*-
# La FK account_move_line_subscription_id_fkey apunta a sale_order (no a subscription.subscription).
# No escribir id de subscription.subscription en las líneas; solo sale.order es válido.
from odoo import api, fields, models, _


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    subscription_billable_line_id = fields.Many2one(
        'subscription.monthly.billable.line',
        string='Línea facturable',
        ondelete='set null',
        help='Línea del facturable guardado desde la que se creó esta línea de factura (para Ver Detalles).',
    )
    subscription_business_line_id = fields.Many2one(
        'product.business.line',
        string='Línea de negocio',
        ondelete='set null',
        help='Línea de negocio (igual que en el facturable guardado).',
    )
    subscription_line_display_name = fields.Char(
        string='Producto',
        compute='_compute_subscription_line_display_name',
        help='En líneas de suscripción muestra la categoría (ej. MICROSOFT Y OFFICE 365); en el resto, producto o descripción.',
    )
    is_section_or_note_line = fields.Boolean(
        string='Es sección o nota',
        compute='_compute_is_section_or_note_line',
        help='True en líneas de tipo sección/nota para ocultar cantidad e importe en la vista (evita evaluar display_type en JS).',
    )

    @api.depends('display_type')
    def _compute_is_section_or_note_line(self):
        for line in self:
            line.is_section_or_note_line = (
                line.display_type in ('line_section', 'line_subsection', 'line_note')
                if line.display_type
                else False
            )

    @api.depends('subscription_billable_line_id', 'subscription_billable_line_id.product_display_name', 'product_id', 'name')
    def _compute_subscription_line_display_name(self):
        for line in self:
            if line.subscription_billable_line_id:
                line.subscription_line_display_name = (
                    line.subscription_billable_line_id.product_display_name or line.name or ''
                )
            else:
                line.subscription_line_display_name = (
                    line.product_id.display_name if line.product_id else (line.name or '')
                )

    @api.model_create_multi
    def create(self, vals_list):
        """subscription_id en account.move.line referencia sale_order; no escribir id de subscription.subscription."""
        for vals in vals_list:
            move_id = vals.get('move_id')
            if move_id:
                move = self.env['account.move'].browse(move_id)
                if move.exists() and getattr(move, 'subscription_id', None):
                    sub = move.subscription_id
                    # Solo asignar si es sale.order; si es subscription.subscription dejar False
                    if sub._name == 'sale.order':
                        vals['subscription_id'] = sub.id
                    else:
                        vals['subscription_id'] = False
        return super().create(vals_list)

    def action_view_billable_line_details(self):
        """Abre los detalles de la línea del facturable (seriales/tipos de licencia), igual que Ver Detalles en el facturable guardado."""
        self.ensure_one()
        if not self.subscription_billable_line_id:
            return {'type': 'ir.actions.act_window_close'}
        line = self.subscription_billable_line_id
        if line.is_license:
            view_id = self.env.ref('subscription_nocount.view_subscription_monthly_billable_line_detail_list').id
        else:
            view_id = self.env.ref('subscription_nocount.view_subscription_monthly_billable_line_detail_equipment_list').id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Detalles - %s') % (line.product_display_name or _('Línea')),
            'res_model': 'subscription.monthly.billable.line.detail',
            'view_mode': 'list',
            'views': [(view_id, 'list')],
            'domain': [('billable_line_id', '=', line.id)],
            'context': {'create': False, 'edit': False, 'delete': True},
        }
