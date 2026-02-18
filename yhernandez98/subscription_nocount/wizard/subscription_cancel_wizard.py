# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import UserError


class SubscriptionCancelWizard(models.TransientModel):
    _name = 'subscription.cancel.wizard'
    _description = 'Confirmar cancelación de suscripción'

    subscription_id = fields.Many2one(
        'subscription.subscription',
        string='Suscripción',
        required=True,
        readonly=True,
    )
    reason = fields.Text(
        string='Motivo (opcional)',
        help='Puede indicar el motivo de la cancelación para referencia futura.',
    )

    def action_confirm_cancel(self):
        self.ensure_one()
        if self.subscription_id.state not in ('draft', 'active'):
            raise UserError(_('Solo puede cancelar suscripciones en borrador o activas.'))
        self.subscription_id.action_cancel()
        return {'type': 'ir.actions.act_window_close'}
