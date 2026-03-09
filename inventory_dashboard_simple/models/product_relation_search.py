# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProductRelationSearch(models.TransientModel):
    _name = 'product.relation.search'
    _description = 'Búsqueda de Relaciones de Productos'
    _order = 'main_product_name, element_type, element_name'

    # Campos de búsqueda
    search_plate = fields.Char(
        string='Placa de Inventario',
        help='Buscar por placa de inventario'
    )
    search_serial = fields.Char(
        string='Número de Serie',
        help='Buscar por número de serie'
    )
    search_product_name = fields.Char(
        string='Nombre del Producto',
        help='Buscar por nombre del producto'
    )

    # Campos de resultado
    element_lot_id = fields.Many2one(
        'stock.lot',
        string='Elemento (Lote/Serie)',
        readonly=True
    )
    element_name = fields.Char(
        string='Elemento',
        readonly=True,
        compute='_compute_element_info',
        store=True
    )
    element_product_id = fields.Many2one(
        'product.product',
        string='Producto del Elemento',
        readonly=True,
        related='element_lot_id.product_id',
        store=False
    )
    element_type = fields.Selection(
        [
            ('main', 'Producto Principal'),
            ('component', 'Componente'),
            ('peripheral', 'Periférico'),
            ('complement', 'Complemento'),
            ('monitor', 'Monitores'),
            ('ups', 'UPS'),
        ],
        string='Tipo de Elemento',
        readonly=True,
        compute='_compute_element_info',
        store=True
    )
    element_plate = fields.Char(
        string='Placa del Elemento',
        readonly=True,
        related='element_lot_id.inventory_plate',
        store=False
    )
    element_serial = fields.Char(
        string='Serial del Elemento',
        readonly=True,
        related='element_lot_id.name',
        store=False
    )

    # Información del producto principal
    main_lot_id = fields.Many2one(
        'stock.lot',
        string='Lote/Serie Principal',
        readonly=True,
        compute='_compute_main_product_info',
        store=False
    )
    main_product_id = fields.Many2one(
        'product.product',
        string='Producto Principal',
        readonly=True,
        compute='_compute_main_product_info',
        store=False
    )
    main_product_name = fields.Char(
        string='Nombre Producto Principal',
        readonly=True,
        compute='_compute_main_product_info',
        store=True
    )
    main_plate = fields.Char(
        string='Placa Principal',
        readonly=True,
        compute='_compute_main_product_info',
        store=False
    )
    main_serial = fields.Char(
        string='Serial Principal',
        readonly=True,
        compute='_compute_main_product_info',
        store=False
    )
    relation_type = fields.Char(
        string='Tipo de Relación',
        readonly=True,
        compute='_compute_main_product_info',
        store=True
    )

    @api.depends('element_lot_id')
    def _compute_element_info(self):
        """Calcular información del elemento."""
        for record in self:
            if record.element_lot_id:
                lot = record.element_lot_id
                record.element_name = lot.display_name or lot.name or f'Lote #{lot.id}'
                
                # Determinar tipo de elemento
                if lot.is_principal:
                    record.element_type = 'main'
                elif lot.principal_lot_id:
                    # Buscar en qué tipo de relación está
                    supply_line = self.env['stock.lot.supply.line'].search([
                        ('lot_id', '=', lot.principal_lot_id.id),
                        ('related_lot_id', '=', lot.id)
                    ], limit=1)
                    if supply_line:
                        record.element_type = supply_line.item_type
                    else:
                        record.element_type = 'component'  # Por defecto
                else:
                    # Buscar si este lote está relacionado como componente/periférico/complemento
                    # en alguna línea de suministro (caso inverso)
                    supply_line = self.env['stock.lot.supply.line'].search([
                        ('related_lot_id', '=', lot.id)
                    ], limit=1)
                    if supply_line:
                        record.element_type = supply_line.item_type
                    else:
                        record.element_type = False
            else:
                record.element_name = False
                record.element_type = False

    @api.depends('element_lot_id', 'element_type')
    def _compute_main_product_info(self):
        """Calcular información del producto principal."""
        for record in self:
            if not record.element_lot_id:
                record.main_lot_id = False
                record.main_product_id = False
                record.main_product_name = False
                record.main_plate = False
                record.main_serial = False
                record.relation_type = False
                continue

            lot = record.element_lot_id

            # Si el elemento es un producto principal
            if lot.is_principal:
                record.main_lot_id = lot
                record.main_product_id = lot.product_id
                record.main_product_name = lot.product_id.name if lot.product_id else False
                record.main_plate = lot.inventory_plate
                record.main_serial = lot.name
                record.relation_type = 'Producto Principal'
            # Si el elemento es un componente/periférico/complemento
            elif lot.principal_lot_id:
                main_lot = lot.principal_lot_id
                record.main_lot_id = main_lot
                record.main_product_id = main_lot.product_id
                record.main_product_name = main_lot.product_id.name if main_lot.product_id else False
                record.main_plate = main_lot.inventory_plate
                record.main_serial = main_lot.name
                
                # Obtener el tipo de relación desde supply_line
                supply_line = self.env['stock.lot.supply.line'].search([
                    ('lot_id', '=', main_lot.id),
                    ('related_lot_id', '=', lot.id)
                ], limit=1)
                
                if supply_line:
                    type_map = {
                        'component': 'Componente',
                        'peripheral': 'Periférico',
                        'complement': 'Complemento',
                        'monitor': 'Monitores',
                        'ups': 'UPS',
                    }
                    record.relation_type = type_map.get(supply_line.item_type, 'Desconocido')
                else:
                    record.relation_type = 'Relacionado'
            else:
                # Buscar si este lote está relacionado como componente/periférico/complemento
                # en alguna línea de suministro (caso inverso)
                supply_line = self.env['stock.lot.supply.line'].search([
                    ('related_lot_id', '=', lot.id)
                ], limit=1)
                
                if supply_line and supply_line.lot_id:
                    main_lot = supply_line.lot_id
                    record.main_lot_id = main_lot
                    record.main_product_id = main_lot.product_id
                    record.main_product_name = main_lot.product_id.name if main_lot.product_id else False
                    record.main_plate = main_lot.inventory_plate
                    record.main_serial = main_lot.name
                    
                    type_map = {
                        'component': 'Componente',
                        'peripheral': 'Periférico',
                        'complement': 'Complemento',
                        'monitor': 'Monitores',
                        'ups': 'UPS',
                    }
                    record.relation_type = type_map.get(supply_line.item_type, 'Desconocido')
                else:
                    # No tiene relación
                    record.main_lot_id = False
                    record.main_product_id = False
                    record.main_product_name = 'Sin producto principal'
                    record.main_plate = False
                    record.main_serial = False
                    record.relation_type = 'Sin relación'

    def action_search(self):
        """Realizar la búsqueda y mostrar resultados."""
        self.ensure_one()
        
        domain = []
        
        # Construir dominio de búsqueda
        if self.search_plate:
            domain.append(('inventory_plate', 'ilike', self.search_plate))
        if self.search_serial:
            domain.append(('name', 'ilike', self.search_serial))
        if self.search_product_name:
            domain.append(('product_id.name', 'ilike', self.search_product_name))
        
        if not domain:
            raise UserError(_('Debe ingresar al menos un criterio de búsqueda (Placa, Serial o Nombre del Producto).'))
        
        # Combinar condiciones con OR si hay múltiples criterios
        if len(domain) > 1:
            search_domain = ['|'] * (len(domain) - 1) + domain
        else:
            search_domain = domain
        
        # Buscar lotes que coincidan
        lots = self.env['stock.lot'].search(search_domain, limit=100)
        
        if not lots:
            raise UserError(_('No se encontraron elementos que coincidan con los criterios de búsqueda.'))
        
        # Crear registros de resultado
        result_ids = []
        for lot in lots:
            result = self.create({
                'element_lot_id': lot.id,
            })
            result_ids.append(result.id)
        
        # Abrir vista de resultados
        return {
            'type': 'ir.actions.act_window',
            'name': _('Resultados de Búsqueda - Relaciones de Productos'),
            'res_model': 'product.relation.search',
            'view_mode': 'list',
            'domain': [('id', 'in', result_ids)],
            'target': 'current',
            'context': {'search_default_group_by_main': 0},
        }

    def action_clear_search(self):
        """Limpiar los campos de búsqueda."""
        self.ensure_one()
        self.search_plate = False
        self.search_serial = False
        self.search_product_name = False
        return {
            'type': 'ir.actions.act_window',
            'name': _('Búsqueda de Relaciones de Productos'),
            'res_model': 'product.relation.search',
            'view_mode': 'form',
            'target': 'new',
            'res_id': self.id,
        }

    def action_open_main_lot(self):
        """Abrir el formulario del producto principal (stock.lot)."""
        self.ensure_one()
        if not self.main_lot_id:
            raise UserError(_('No hay un producto principal asociado para abrir.'))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Producto Principal'),
            'res_model': 'stock.lot',
            'res_id': self.main_lot_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_lot_from_line(self):
        """Abrir el formulario del producto principal cuando se hace clic en una línea."""
        self.ensure_one()
        # Forzar el cálculo de los campos computed
        self._compute_main_product_info()
        self._compute_element_info()
        
        # Si hay un producto principal, abrir ese
        if self.main_lot_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Producto Principal'),
                'res_model': 'stock.lot',
                'res_id': self.main_lot_id.id,
                'view_mode': 'form',
                'target': 'new',  # Abrir como wizard (modal)
            }
        # Si no hay producto principal pero hay elemento, abrir el elemento
        elif self.element_lot_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Elemento'),
                'res_model': 'stock.lot',
                'res_id': self.element_lot_id.id,
                'view_mode': 'form',
                'target': 'new',  # Abrir como wizard (modal)
            }
        else:
            raise UserError(_('No hay un producto asociado para abrir.'))

    def get_formview_action(self, access_uid=None):
        """Sobrescribir el comportamiento al hacer clic en una línea para abrir el producto principal."""
        try:
            return self.action_open_lot_from_line()
        except Exception:
            # Si falla, usar el comportamiento por defecto
            return super().get_formview_action(access_uid=access_uid)