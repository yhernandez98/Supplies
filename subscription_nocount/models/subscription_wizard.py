from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SubscriptionUsageProformaWizard(models.TransientModel):
    _name = 'subscription.usage.proforma.wizard'
    _description = 'Asistente de proforma por uso'

    subscription_id = fields.Many2one('subscription.subscription', string='Suscripción', required=True)
    currency_id = fields.Many2one(related='subscription_id.currency_id', readonly=True)
    line_ids = fields.One2many('subscription.usage.proforma.wizard.line', 'wizard_id', string='Líneas')
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        subscription = self.env['subscription.subscription'].browse(
            self.env.context.get('active_id') or self.env.context.get('default_subscription_id')
        )
        if subscription:
            res['subscription_id'] = subscription.id
            lines = []
            pending_usages = subscription.mapped('line_ids.usage_ids').filtered(
                lambda u: not u.invoiced and u.date_end
            )
            for usage in pending_usages:
                lines.append((0, 0, {
                    'usage_id': usage.id,
                    'product_id': usage.line_id.product_id.id,
                    'date_start': usage.date_start,
                    'date_end': usage.date_end,
                    'quantity': usage.quantity,
                    'suggested_amount': usage.amount,
                    'amount': usage.amount,
                    'description': usage._get_description(),
                    'charge': True,
                }))
            res['line_ids'] = lines
        return res

    def action_confirm(self):
        self.ensure_one()
        charge_lines = self.line_ids.filtered(lambda l: l.usage_id and l.charge)
        if not charge_lines:
            raise UserError(_('Debe seleccionar al menos un retiro para cobrar.'))
        move = self.subscription_id._create_proforma_with_usages(charge_lines)
        for line in charge_lines:
            line.usage_id.write({'invoiced': True})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': move.id,
            'context': {'hide_account_column': True},
        }


class SubscriptionUsageProformaWizardLine(models.TransientModel):
    _name = 'subscription.usage.proforma.wizard.line'
    _description = 'Línea del asistente de proforma por uso'

    wizard_id = fields.Many2one('subscription.usage.proforma.wizard', required=True, ondelete='cascade')
    usage_id = fields.Many2one('subscription.subscription.usage', string='Uso', required=True)
    product_id = fields.Many2one('product.product', string='Producto', readonly=True)
    date_start = fields.Datetime(string='Inicio', readonly=True)
    date_end = fields.Datetime(string='Fin', readonly=True)
    quantity = fields.Float(string='Cantidad', readonly=True)
    description = fields.Char(string='Descripción', readonly=True)
    charge = fields.Boolean(string='Cobrar', default=True)
    suggested_amount = fields.Monetary(string='Importe sugerido', currency_field='currency_id', readonly=True)
    amount = fields.Monetary(string='Importe a facturar', currency_field='currency_id')
    currency_id = fields.Many2one(related='wizard_id.currency_id', readonly=True)

    @api.model
    def create(self, vals_list):
        single = isinstance(vals_list, dict)
        values = [vals_list] if single else vals_list
        records = self.browse()
        for vals in values:
            if not vals.get('usage_id'):
                continue
            records |= super().create(vals)
        if single:
            return records[:1]
        return records

    @api.constrains('amount')
    def _check_amount(self):
        for line in self:
            if line.amount < 0:
                raise UserError(_('El importe no puede ser negativo.'))

    def _prepare_invoice_line_vals(self):
        self.ensure_one()
        price_unit = self.amount if self.charge else 0.0
        return {
            'product_id': self.product_id.id,
            'name': self.description,
            'quantity': 1.0,
            'price_unit': price_unit,
            'tax_ids': [(6, 0, self.usage_id.line_id.product_id.taxes_id.ids)],
        }
