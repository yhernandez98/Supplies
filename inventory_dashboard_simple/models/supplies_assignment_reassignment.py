# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class SuppliesAssignmentReassignment(models.Model):
    _name = 'supplies.assignment.reassignment'
    _description = 'Acta de reasignacion de equipos'
    _order = 'id desc'

    name = fields.Char(
        string='Acta',
        required=True,
        copy=False,
        default=lambda self: _('Nuevo'),
    )
    date = fields.Datetime(string='Fecha', default=fields.Datetime.now, required=True)
    employee_id = fields.Many2one('hr.employee', string='Empleado', index=True)
    user_id = fields.Many2one('res.users', string='Usuario Odoo', related='employee_id.user_id', store=True, readonly=True)
    old_assignment_id = fields.Many2one('supplies.assignment', string='Asignacion anterior', required=True)
    new_assignment_id = fields.Many2one('supplies.assignment', string='Nueva asignacion', required=True)
    old_product_id = fields.Many2one('product.product', string='Producto anterior', related='old_assignment_id.product_id', store=True)
    old_lot_id = fields.Many2one('stock.lot', string='Serial anterior', related='old_assignment_id.lot_id', store=True)
    new_product_id = fields.Many2one('product.product', string='Nuevo producto', related='new_assignment_id.product_id', store=True)
    new_lot_id = fields.Many2one('stock.lot', string='Nuevo serial', related='new_assignment_id.lot_id', store=True)
    note = fields.Text(string='Observacion')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nuevo')) == _('Nuevo'):
                vals['name'] = self.env['ir.sequence'].next_by_code('supplies.assignment.reassignment') or _('Nuevo')
        return super().create(vals_list)

    def _normalize_report_text(self, value):
        """Corrige texto con mojibake comun (ej: AdministraciÃ³n)."""
        txt = value or ''
        if not txt:
            return ''
        txt = str(txt)
        # Intentamos reparar varias capas de codificacion incorrecta sin perder caracteres.
        for _i in range(3):
            changed = False
            for enc in ('latin1', 'cp1252'):
                try:
                    repaired = txt.encode(enc).decode('utf-8')
                except Exception:
                    continue
                if repaired and repaired != txt:
                    txt = repaired
                    changed = True
            if not changed:
                break

        replacements = {
            'Ã¡': 'á', 'Ã©': 'é', 'Ã­': 'í', 'Ã³': 'ó', 'Ãº': 'ú',
            'Ã': 'Á', 'Ã‰': 'É', 'Ã': 'Í', 'Ã“': 'Ó', 'Ãš': 'Ú',
            'Ã±': 'ñ', 'Ã‘': 'Ñ', 'Ã¼': 'ü', 'Ãœ': 'Ü',
            'Â¿': '¿', 'Â¡': '¡', 'Â': '',
            'A±o': 'Año', 'a±o': 'año', '±': 'ñ',
            '\ufffd': '',
        }
        for bad, good in replacements.items():
            txt = txt.replace(bad, good)
        return txt
