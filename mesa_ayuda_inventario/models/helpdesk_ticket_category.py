# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HelpdeskTicketCategory(models.Model):
    """Categorías de ticket (jerárquicas), misma lógica que categorías de producto en inventario.
    La categoría define prioridad, SLA, control de tiempo registrado y si se crea orden de servicio."""
    _name = 'helpdesk.ticket.category'
    _description = 'Categoría de ticket'
    _rec_name = 'complete_name'  # En desplegables se ve la ruta completa (padre / hijo), no solo el nombre
    _parent_name = 'parent_id'
    _parent_store = True
    _order = 'complete_name'

    name = fields.Char(string='Categoría', required=True, translate=False)
    complete_name = fields.Char(string='Categoría', compute='_compute_complete_name', store=True, recursive=True)
    parent_id = fields.Many2one('helpdesk.ticket.category', string='Categoría principal', ondelete='cascade', index=True)
    parent_path = fields.Char(index=True, unaccent=False)
    level = fields.Integer(string='Nivel', default=1)

    # ---------- Configuración aplicada al ticket según categoría ----------
    # Prioridad = importancia general del ticket (orden, listados, SLA). Urgencia = cuán rápido debe atenderse. Impacto = gravedad si no se resuelve.
    default_priority = fields.Selection([
        ('0', 'Baja'),
        ('1', 'Normal'),
        ('2', 'Alta'),
        ('3', 'Muy alta'),
    ], string='Prioridad por defecto',
       help='Importancia general del ticket: orden en listas, filtros y acuerdos de nivel (SLA). Si la categoría lo define, el técnico no podrá cambiarlo.')
    default_urgency = fields.Selection([
        ('1', 'Baja'),
        ('2', 'Media'),
        ('3', 'Alta'),
        ('4', 'Crítica'),
    ], string='Urgencia por defecto',
       help='Cuán rápido debe atenderse el ticket (sensibilidad en el tiempo). Si la categoría lo define, el técnico no podrá cambiarlo.')
    default_impact = fields.Selection([
        ('1', 'Baja'),
        ('2', 'Media'),
        ('3', 'Alta'),
        ('4', 'Crítica'),
    ], string='Impacto por defecto',
       help='Gravedad o alcance si el problema no se resuelve (afectación al negocio o al usuario). Si la categoría lo define, el técnico no podrá cambiarlo.')
    # SLA como intervalo: días + horas desde la creación del ticket
    sla_response_days = fields.Integer(
        string='SLA Respuesta (días)',
        default=0,
        help='Días desde la creación del ticket para el compromiso de respuesta. Usar junto con las horas.'
    )
    sla_response_hours = fields.Float(
        string='SLA Respuesta (horas)',
        default=0,
        help='Horas adicionales para el compromiso de respuesta. Ej: 2 días + 4 horas.'
    )
    sla_resolution_days = fields.Integer(
        string='SLA Resolución (días)',
        default=0,
        help='Días desde la creación del ticket para el compromiso de resolución.'
    )
    sla_resolution_hours = fields.Float(
        string='SLA Resolución (horas)',
        default=0,
        help='Horas adicionales para el compromiso de resolución. Ej: 5 días + 0 horas.'
    )
    auto_create_maintenance_order = fields.Boolean(
        string='Crear orden de servicio automáticamente',
        default=False,
        help='Si está activo, al crear un ticket con esta categoría se crea una orden de mantenimiento enlazada.'
    )

    # ---------- Control del tiempo registrado (hojas de horas / temporizador) ----------
    control_tiempo_registro = fields.Selection([
        ('libre', 'Libre (el técnico puede editar el tiempo)'),
        ('exigir_tiempo_real', 'Usar tiempo real del cronómetro'),
        ('minimo_horas', 'Tiempo mínimo por registro'),
    ], string='Control tiempo registrado', default='libre',
       help='Define cómo se controla el tiempo en las hojas de horas de los tickets de esta categoría.')
    tiempo_minimo_horas = fields.Float(
        string='Mínimo horas por registro',
        default=0,
        help='Cuando "Control tiempo registrado" es "Tiempo mínimo por registro", cada línea de hoja de horas debe tener al menos estas horas (ej. 0.25 = 15 min).'
    )

    @api.constrains('control_tiempo_registro', 'tiempo_minimo_horas')
    def _check_tiempo_minimo(self):
        for cat in self:
            if cat.control_tiempo_registro == 'minimo_horas' and (cat.tiempo_minimo_horas or 0) < 0:
                raise ValidationError(_('El tiempo mínimo por registro no puede ser negativo.'))

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for cat in self:
            if cat.parent_id:
                cat.complete_name = '%s / %s' % (cat.parent_id.complete_name, cat.name or '')
            else:
                cat.complete_name = cat.name or ''

    def action_fix_parent_from_name(self):
        """
        Corrige Categoría principal después de importar desde Excel.
        Si el campo nombre tiene " / " (ej. "ALISTAMIENTOS / Alistamiento - AIO"),
        asigna el padre y deja solo el nombre final ("Alistamiento - AIO").
        """
        Category = self.env['helpdesk.ticket.category']
        all_cats = Category.search([], order='id')
        by_depth = sorted(all_cats, key=lambda c: (c.name or '').count(' / '))
        fixed = 0
        for cat in by_depth:
            name = (cat.name or '').strip()
            if ' / ' not in name:
                continue
            parts = [p.strip() for p in name.split(' / ') if p.strip()]
            if len(parts) < 2:
                continue
            parent_path = ' / '.join(parts[:-1])
            new_name = parts[-1]
            parent = Category.search([('complete_name', '=', parent_path)], limit=1)
            if not parent:
                parent = Category.search([('name', '=', parent_path)], limit=1)
            if parent and parent != cat:
                cat.write({'name': new_name, 'parent_id': parent.id})
                fixed += 1
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Jerarquía corregida',
                'message': 'Se actualizaron %s categorías (Categoría principal asignada).' % fixed,
                'type': 'success',
                'sticky': False,
            }
        }
