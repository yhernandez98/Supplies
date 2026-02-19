# -*- coding: utf-8 -*-
# from odoo import api, fields, models

# Modelo desactivado: Ya no se usa subscription.license.assignment
# Las licencias ahora se obtienen automáticamente desde license.assignment
# basándose en partner_id y location_id en la pestaña "Facturable"

# class SubscriptionSubscription(models.Model):
#     """Extender subscription.subscription para agregar relación con licencias."""
#     _inherit = 'subscription.subscription'
#
#     license_ids = fields.One2many(
#         'subscription.license.assignment',
#         'subscription_id',
#         string='Licencias Asignadas',
#         help='Licencias asignadas a esta suscripción'
#     )
#     license_count = fields.Integer(
#         string='Cantidad de Licencias',
#         compute='_compute_license_count',
#         store=False
#     )
#
#     @api.depends('license_ids', 'license_ids.active')
#     def _compute_license_count(self):
#         """Calcula la cantidad de licencias activas asignadas."""
#         for rec in self:
#             rec.license_count = len(rec.license_ids.filtered(lambda l: l.active))

