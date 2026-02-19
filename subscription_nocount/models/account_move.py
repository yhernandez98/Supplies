from odoo import _, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    x_is_proforma = fields.Boolean(string='Es proforma', default=False)
    subscription_id = fields.Many2one('subscription.subscription', string='Suscripción')

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
