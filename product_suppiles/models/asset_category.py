# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class ProductAssetCategory(models.Model):
    _name = "product.asset.category"
    _description = "Categoría de Activo"
    _order = "name"
    _rec_name = "name"
    _inherit = ['mail.thread', 'mail.activity.mixin'] 

    _asset_cat_code_uniq = models.Constraint(
        "unique(code)",
        "El código de la categoría de activo debe ser único.",
    )

    name = fields.Char("Nombre", required=True, translate=False)
    code = fields.Char("Código", required=True, help="Código único para referencia interna/reporte.")
    active = fields.Boolean(default=True)
    description = fields.Text("Descripción")

    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        default=lambda self: self.env.company,
        required=True,
        index=True,
    )
    _check_company_auto = True


class ProductAssetClass(models.Model):
    _name = "product.asset.class"
    _description = "Clase de Activo"
    _order = "name"
    _rec_name = "name"

    name = fields.Char("Nombre", required=True)
    code = fields.Char("Código", required=True, help="Código único dentro de la categoría/compañía.")
    active = fields.Boolean(default=True)
    description = fields.Text("Descripción")

    category_id = fields.Many2one(
        "product.asset.category",
        string="Categoría de Activo",
        required=True,
        ondelete="restrict",
        index=True,
    )

    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        default=lambda self: self.env.company,
        required=True,
        index=True,
    )

    _check_company_auto = True

    _asset_class_code_uniq = models.Constraint(
        "unique(code, company_id, category_id)",
        "El código de la clase de activo debe ser único dentro de la categoría y la compañía.",
    )

    @api.constrains("category_id", "company_id")
    def _check_company_alignment(self):
        for rec in self:
            if rec.category_id and rec.company_id and rec.category_id.company_id != rec.company_id:
                raise ValidationError(_("La clase y su categoría deben pertenecer a la misma compañía."))
class ProductBusinessLine(models.Model):
    _name = "product.business.line"
    _description = "Linea de negocio"
    _order = "name"
    _rec_name = "name"
    _inherit = ['mail.thread', 'mail.activity.mixin'] 

    name = fields.Char("Nombre", required=True, translate=False)
    code = fields.Char("Código", required=True, help="Codigo para la linea de negocio.")
    active = fields.Boolean(default=True)
    description = fields.Text("Descripción")

    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        default=lambda self: self.env.company,
        required=True,
        index=True,
    )
    _check_company_auto = True

