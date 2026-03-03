from odoo import _, api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    x_is_proforma = fields.Boolean(string='Es proforma', default=False)
    x_apply_iva = fields.Boolean(
        string='Aplicar IVA',
        default=True,
        help='Si está desmarcado, las líneas de la proforma no llevan IVA; el total se calcula sin impuestos.',
    )
    subscription_id = fields.Many2one('subscription.subscription', string='Suscripción')

    @api.onchange('x_apply_iva')
    def _onchange_x_apply_iva(self):
        """Al desmarcar Aplicar IVA, quitar impuestos de todas las líneas para que el total sea sin IVA."""
        if not self.x_apply_iva and self.invoice_line_ids:
            for line in self.invoice_line_ids:
                if line.display_type not in ('line_section', 'line_subsection', 'line_note'):
                    line.tax_ids = [(5, 0, 0)]

    def write(self, vals):
        res = super().write(vals)
        if 'x_apply_iva' in vals and not vals.get('x_apply_iva'):
            for move in self:
                if move.x_is_proforma and move.invoice_line_ids:
                    for line in move.invoice_line_ids.filtered(
                        lambda l: l.display_type not in ('line_section', 'line_subsection', 'line_note')
                    ):
                        line.tax_ids = [(5, 0, 0)]
        return res

    def action_print_proforma_detailed(self):
        """Abre el informe PDF detallado de la proforma (líneas + detalle por grupo/serial)."""
        self.ensure_one()
        if not self.x_is_proforma:
            return
        return self.env.ref('subscription_nocount.action_report_proforma_detailed').report_action(self)

    def unlink(self):
        """Registrar en el chatter de la suscripción cuando se elimina una proforma."""
        subs_to_log = {}
        for move in self:
            if move.subscription_id and move.subscription_id.exists():
                sub = move.subscription_id
                if sub.id not in subs_to_log:
                    subs_to_log[sub.id] = []
                subs_to_log[sub.id].append(move.name or move.display_name or _('Proforma'))
        res = super().unlink()
        for sub_id, names in subs_to_log.items():
            sub = self.env['subscription.subscription'].browse(sub_id)
            if sub.exists():
                body = _('Proforma(s) eliminada(s): %s.') % ', '.join(names)
                sub.message_post(body=body, message_type='notification', subtype_xmlid='mail.mt_note')
        return res
