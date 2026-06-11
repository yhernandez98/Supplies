# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class DeliveryRouteTriggerWizard(models.TransientModel):
    """Wizard para procesar rutas de entrega y devolución por número de serie."""
    
    _name = 'delivery.route.trigger.wizard'
    _description = 'Wizard para Procesar Ruta de Entrega/Devolución'

    operation_type = fields.Selection(
        [
            ('delivery', 'Entrega'),
            ('return', 'Devolución'),
        ],
        string='Tipo de Operación',
        default='delivery',
        required=True,
        help='Tipo de operación: Entrega (desde Supp/Existencias al cliente) o Devolución (desde el cliente a Supp/Existencias)'
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        required=True,
        help='Cliente para la ruta'
    )

    route_id = fields.Many2one(
        'stock.route',
        string='Ruta',
        required=True,
        domain="[('id', 'in', available_route_ids)]",
        help='Ruta a procesar'
    )
    
    available_route_ids = fields.Many2many(
        'stock.route',
        string='Rutas Disponibles',
        compute='_compute_available_route_ids',
        store=False,
        help='Rutas disponibles para el cliente y tipo de operación seleccionados'
    )

    route_code = fields.Char(
        string='Código de Ruta',
        help='Código de la ruta de entrega'
    )

    line_ids = fields.One2many(
        'delivery.route.trigger.wizard.line',
        'wizard_id',
        string='Productos por Número de Serie'
    )

    route_available_lot_ids = fields.Many2many(
        'stock.lot',
        string='Seriales disponibles (ruta)',
        compute='_compute_route_available_catalog',
        store=False,
        help='Catálogo calculado una vez por wizard (Existencias o cliente).',
    )
    route_available_product_ids = fields.Many2many(
        'product.product',
        string='Productos disponibles (ruta)',
        compute='_compute_route_available_catalog',
        store=False,
    )

    def _get_route_location_ids(self):
        """Ubicaciones donde se busca stock según operación."""
        self.ensure_one()
        if self.operation_type == 'delivery':
            supplies_location = self.env['stock.location'].search([
                ('complete_name', 'ilike', 'Supp/Existencias'),
                ('usage', '=', 'internal'),
            ], limit=1)
            if not supplies_location:
                return []
            return self.env['stock.location'].search([
                ('id', 'child_of', supplies_location.id),
            ]).ids
        if self.operation_type == 'return' and self.partner_id:
            customer_location = self.partner_id.property_stock_customer
            if not customer_location:
                return []
            return self.env['stock.location'].search([
                ('id', 'child_of', customer_location.id),
            ]).ids
        return []

    @staticmethod
    def _read_group_m2o_ids(rows, field_name):
        ids = []
        for row in rows:
            val = row.get(field_name)
            if not val:
                continue
            ids.append(val[0] if isinstance(val, (list, tuple)) else val)
        return ids

    @api.depends('operation_type', 'partner_id')
    def _compute_route_available_catalog(self):
        """Una sola consulta agrupada por wizard (no por cada línea ni por Buscar más)."""
        Lot = self.env['stock.lot']
        Product = self.env['product.product']
        quant_model = self.env['stock.quant']
        for wizard in self:
            location_ids = wizard._get_route_location_ids()
            if not location_ids:
                wizard.route_available_lot_ids = Lot
                wizard.route_available_product_ids = Product
                continue
            quant_domain = [
                ('location_id', 'in', location_ids),
                ('quantity', '>', 0),
                ('lot_id', '!=', False),
            ]
            lot_rows = quant_model.read_group(
                quant_domain,
                ['lot_id'],
                ['lot_id'],
                lazy=False,
            )
            product_rows = quant_model.read_group(
                quant_domain,
                ['product_id'],
                ['product_id'],
                lazy=False,
            )
            lot_ids = wizard._read_group_m2o_ids(lot_rows, 'lot_id')
            product_ids = wizard._read_group_m2o_ids(product_rows, 'product_id')
            wizard.route_available_lot_ids = Lot.browse(lot_ids)
            wizard.route_available_product_ids = Product.browse(product_ids)

    @api.onchange('line_ids', 'line_ids.dup_plus', 'line_ids.dup_extra_count')
    def _onchange_line_ids_duplicate_helpers(self):
        """Duplicar filas sin botones object (Odoo exige guardar antes del RPC)."""
        new_commands = []
        warning_msg = None
        for line in self.line_ids:
            if line.dup_plus:
                line.dup_plus = False
                if not line.product_id:
                    warning_msg = _(
                        'Seleccione un producto antes de duplicar la línea.'
                    )
                    continue
                new_commands.append((0, 0, line._prepare_duplicate_line_vals()))
            extra = line.dup_extra_count or 0
            if extra:
                line.dup_extra_count = 0
                if extra < 1 or extra > 99:
                    warning_msg = _(
                        'Indique entre 1 y 99 líneas adicionales.'
                    )
                    continue
                if not line.product_id:
                    warning_msg = _(
                        'Seleccione un producto antes de agregar más líneas.'
                    )
                    continue
                vals = line._prepare_duplicate_line_vals()
                for _ in range(int(extra)):
                    new_commands.append((0, 0, vals))
        if not new_commands and not warning_msg:
            return
        result = {}
        if new_commands:
            result['value'] = {'line_ids': new_commands}
        if warning_msg:
            result['warning'] = {
                'title': _('Procesar Ruta'),
                'message': warning_msg,
            }
        return result

    def action_duplicate_last_line(self):
        """Duplica la última fila con producto (botón en cabecera de la lista)."""
        self.ensure_one()
        lines = self.line_ids.filtered('product_id')
        if not lines:
            raise UserError(_('Agregue al menos una línea con producto.'))
        self.env['delivery.route.trigger.wizard.line'].create(
            lines[-1]._prepare_duplicate_line_vals()
        )
        return False

    @api.depends('partner_id', 'operation_type')
    def _compute_available_route_ids(self):
        """Calcular rutas disponibles según el cliente y tipo de operación seleccionados."""
        for wizard in self:
            if not wizard.partner_id:
                wizard.available_route_ids = False
                continue
            
            # Obtener la ubicación del cliente
            customer_location = wizard.partner_id.property_stock_customer
            if not customer_location:
                wizard.available_route_ids = False
                _logger.warning("Cliente %s no tiene ubicación configurada", wizard.partner_id.name)
                continue
            
            # Buscar ubicación Supp/Existencias
            supplies_location = self.env['stock.location'].search([
                ('complete_name', 'ilike', 'Supp/Existencias'),
                ('usage', '=', 'internal'),
            ], limit=1)
            
            routes_by_location = self.env['stock.route']
            all_routes = self.env['stock.route'].search([])
            
            if wizard.operation_type == 'delivery':
                # ENTREGA: Buscar rutas que terminen en la ubicación del cliente
                # La ruta debe ir desde Supp/Existencias hacia el cliente
                for route in all_routes:
                    route_rules = self.env['stock.rule'].search([
                        ('route_id', '=', route.id)
                    ], order='sequence desc, id desc')
                    
                    if route_rules:
                        last_rule = route_rules[0]
                        rule_location_dest = last_rule.location_dest_id
                        if not rule_location_dest and last_rule.picking_type_id:
                            rule_location_dest = last_rule.picking_type_id.default_location_dest_id
                        
                        # Verificar que termine en la ubicación del cliente
                        if rule_location_dest == customer_location:
                            routes_by_location |= route
                            
                            # Verificar también que la primera regla empiece desde Supp/Existencias (opcional, pero mejor)
                            first_rule = route_rules[-1] if len(route_rules) > 1 else route_rules[0]
                            first_location_src = first_rule.location_src_id
                            if not first_location_src and first_rule.picking_type_id:
                                first_location_src = first_rule.picking_type_id.default_location_src_id
                            
                            # Si no verifica ubicación de origen, igual la incluimos
                            
            elif wizard.operation_type == 'return':
                # DEVOLUCIÓN: Buscar rutas que empiecen desde la ubicación del cliente
                # y terminen en Supp/Existencias
                _logger.info("DEVOLUCIÓN: Buscando rutas para cliente %s (Ubicación: %s, ID: %s)", 
                           wizard.partner_id.name, 
                           customer_location.complete_name if customer_location else 'None',
                           customer_location.id if customer_location else 'None')
                
                if supplies_location:
                    customer_location_ids = self.env['stock.location'].search([
                        ('id', 'child_of', customer_location.id)
                    ]).ids if customer_location else []
                    
                    _logger.info("DEVOLUCIÓN: Ubicaciones del cliente (incluye hijas): %s", customer_location_ids)
                    _logger.info("DEVOLUCIÓN: Revisando %d rutas totales", len(all_routes))
                    
                    for route in all_routes:
                        route_rules = self.env['stock.rule'].search([
                            ('route_id', '=', route.id)
                        ], order='sequence asc, id asc')
                        
                        if route_rules:
                            first_rule = route_rules[0]
                            first_location_src = first_rule.location_src_id
                            if not first_location_src and first_rule.picking_type_id:
                                first_location_src = first_rule.picking_type_id.default_location_src_id
                            
                            # Verificar que empiece desde la ubicación del cliente (o sus hijas)
                            # Usar comparación por ID para evitar problemas de comparación de objetos
                            first_location_src_id = first_location_src.id if first_location_src else False
                            if first_location_src_id and first_location_src_id in customer_location_ids:
                                _logger.debug("DEVOLUCIÓN: Ruta %s empieza en ubicación del cliente (%s)", 
                                            route.name, first_location_src.complete_name if first_location_src else 'None')
                                
                                # Verificar que termine en Supp/Existencias (o sus hijas)
                                last_rule = route_rules[-1] if len(route_rules) > 1 else route_rules[0]
                                last_location_dest = last_rule.location_dest_id
                                if not last_location_dest and last_rule.picking_type_id:
                                    last_location_dest = last_rule.picking_type_id.default_location_dest_id
                                
                                # Verificar si termina en Supp/Existencias o sus hijas
                                if last_location_dest:
                                    supplies_location_ids = self.env['stock.location'].search([
                                        ('id', 'child_of', supplies_location.id)
                                    ]).ids
                                    if last_location_dest.id in supplies_location_ids:
                                        _logger.info("DEVOLUCIÓN: ✓ Ruta %s válida (empieza en cliente, termina en Supp/Existencias)", route.name)
                                        routes_by_location |= route
                                    else:
                                        _logger.debug("DEVOLUCIÓN: ✗ Ruta %s no termina en Supp/Existencias (termina en %s)", 
                                                    route.name, last_location_dest.complete_name if last_location_dest else 'None')
                            else:
                                _logger.debug("DEVOLUCIÓN: ✗ Ruta %s no empieza en ubicación del cliente (empieza en %s, ID: %s)", 
                                            route.name, 
                                            first_location_src.complete_name if first_location_src else 'None',
                                            first_location_src_id)
            
            # Si no encontramos rutas por ubicación, buscar por nombre del cliente (fallback)
            if not routes_by_location:
                _logger.info("No se encontraron rutas por ubicación, usando fallback por nombre del cliente")
                partner_name = wizard.partner_id.name.strip().upper()
                
                # Intentar diferentes variantes del nombre (ej: "Blindex" puede estar como "BLINDEX", "Blindex", etc.)
                name_variants = [
                    partner_name,
                    partner_name.replace('.', ''),  # Quitar puntos
                    partner_name.replace(' S.A', ''),  # Quitar "S.A"
                    partner_name.replace(' SA', ''),   # Quitar "SA"
                    partner_name.split()[0] if partner_name.split() else partner_name,  # Primera palabra
                ]
                
                routes_by_name = self.env['stock.route']
                for variant in name_variants:
                    if variant:
                        found = self.env['stock.route'].search([
                            ('name', 'ilike', variant)
                        ])
                        routes_by_name |= found
                        if found:
                            _logger.info("Encontradas %d rutas con variante '%s'", len(found), variant)
                
                # Filtrar por tipo de operación si hay rutas por nombre
                if routes_by_name:
                    if wizard.operation_type == 'delivery':
                        # Para entregas, buscar rutas que no sean de devolución
                        routes_by_location = routes_by_name.filtered(
                            lambda r: 'devolución' not in r.name.lower() and 'devolucion' not in r.name.lower()
                        )
                        _logger.info("Filtradas %d rutas de entrega por nombre", len(routes_by_location))
                    elif wizard.operation_type == 'return':
                        # Para devoluciones, buscar solo rutas de devolución
                        routes_by_location = routes_by_name.filtered(
                            lambda r: 'devolución' in r.name.lower() or 'devolucion' in r.name.lower()
                        )
                        _logger.info("Filtradas %d rutas de devolución por nombre", len(routes_by_location))
                        
                        # Si no hay rutas con "devolución" en el nombre, intentar buscar por otras palabras clave
                        if not routes_by_location:
                            _logger.info("No se encontraron rutas con 'devolución', buscando por otras palabras clave...")
                            # Buscar rutas que puedan ser de devolución (ej: que tengan el nombre del cliente y alguna palabra relacionada)
                            routes_by_location = routes_by_name.filtered(
                                lambda r: any(keyword in r.name.lower() for keyword in ['ret', 'back', 'return', 'regreso'])
                            )
                            _logger.info("Encontradas %d rutas de devolución por palabras clave alternativas", len(routes_by_location))
            
            wizard.available_route_ids = routes_by_location
            _logger.debug("Rutas disponibles para cliente %s, tipo %s: %d", 
                         wizard.partner_id.name, wizard.operation_type, len(routes_by_location))

    def _pick_default_route_from_available(self):
        """Elige la ruta más adecuada según cliente y tipo de operación."""
        self.ensure_one()
        routes = self.available_route_ids
        if not routes:
            return self.env['stock.route']
        if len(routes) == 1:
            return routes[:1]

        partner = self.partner_id
        if partner:
            name_up = (partner.name or '').upper()
            tokens = [
                w for w in name_up.replace('.', ' ').replace(',', ' ').split()
                if len(w) >= 3
            ]
            for token in sorted(set(tokens), key=len, reverse=True):
                matched = routes.filtered(lambda r, t=token: t in (r.name or '').upper())
                if not matched:
                    continue
                if self.operation_type == 'delivery':
                    delivery_routes = matched.filtered(
                        lambda r: 'DEVOLUC' not in (r.name or '').upper()
                        and 'DEVOLUCI' not in (r.name or '').upper()
                    )
                    if delivery_routes:
                        matched = delivery_routes
                elif self.operation_type == 'return':
                    return_routes = matched.filtered(
                        lambda r: 'DEVOLUC' in (r.name or '').upper()
                        or 'DEVOLUCI' in (r.name or '').upper()
                    )
                    if return_routes:
                        matched = return_routes
                return matched.sorted(key=lambda r: r.name or '')[:1]

        return routes.sorted(key=lambda r: r.name or '')[:1]

    def _apply_auto_route_selection(self):
        """Asigna ruta y código automáticamente si hay opciones válidas."""
        for wizard in self:
            if not wizard.partner_id or not wizard.operation_type:
                wizard.route_id = False
                wizard.route_code = False
                continue
            wizard._compute_available_route_ids()
            routes = wizard.available_route_ids
            if wizard.route_id and wizard.route_id in routes:
                wizard.route_code = wizard.route_id.name
                continue
            picked = wizard._pick_default_route_from_available()
            wizard.route_id = picked
            wizard.route_code = picked.name if picked else False
    
    @api.onchange('partner_id', 'operation_type')
    def _onchange_partner_or_operation(self):
        """Recalcula rutas y asigna ruta/código según cliente y tipo de operación."""
        if self.partner_id:
            self._apply_auto_route_selection()
            self._compute_route_available_catalog()
            for line in self.line_ids:
                if line.lot_id and line.lot_id not in self.route_available_lot_ids:
                    line.lot_id = False
                if (
                    line.product_id
                    and line.product_id not in self.route_available_product_ids
                ):
                    line.product_id = False
        else:
            self.route_id = False
            self.route_code = False
            self.available_route_ids = False
            self.route_available_lot_ids = False
            self.route_available_product_ids = False
            for line in self.line_ids:
                line.product_id = False
                line.lot_id = False

    @api.onchange('route_code')
    def _onchange_route_code(self):
        """Buscar ruta por código dentro de las rutas disponibles para el cliente."""
        if self.route_code and self.partner_id:
            # Buscar dentro de las rutas disponibles
            route = self.env['stock.route'].search([
                ('name', '=', self.route_code),
                ('id', 'in', self.available_route_ids.ids)
            ], limit=1)
            if route:
                self.route_id = route.id
            else:
                self.route_id = False
        elif self.route_code:
            # Si no hay cliente seleccionado, buscar sin filtro (pero esto no debería pasar)
            route = self.env['stock.route'].search([
                ('name', '=', self.route_code)
            ], limit=1)
            if route:
                self.route_id = route.id
            else:
                self.route_id = False
        else:
            self.route_id = False

    @api.onchange('route_id')
    def _onchange_route_id(self):
        """Actualizar código de ruta cuando se selecciona la ruta."""
        if self.route_id:
            self.route_code = self.route_id.name
        else:
            self.route_code = False

    def _create_picking_safely(self, picking_vals):
        """
        Crea un picking de forma segura, asegurándose de que el nombre se genere correctamente
        antes de continuar para evitar conflictos de nombres duplicados.
        
        :param picking_vals: Diccionario con los valores para crear el picking
        :return: El picking creado con su nombre generado
        """
        # Obtener el cursor para poder hacer commit
        cr = self.env.cr
        
        # Usar with_context para forzar una nueva lectura de la secuencia
        # Esto asegura que cada picking obtenga un número único de la secuencia
        picking = self.env['stock.picking'].with_context(
            skip_name_sequence=False,
            force_name_generation=True
        ).create(picking_vals)
        
        # Forzar flush para guardar en la base de datos
        self.env.flush_all()
        
        # Hacer commit para forzar que la secuencia se actualice en la base de datos
        # Esto es crítico para evitar nombres duplicados cuando se crean múltiples pickings
        cr.commit()
        
        # Invalidar el cache y forzar la lectura del nombre desde la base de datos
        picking.invalidate_recordset(['name'])
        
        # Forzar la lectura del nombre para asegurar que se genere
        # Esto es crítico porque el nombre puede ser un campo computed
        picking_name = picking.name
        
        # Si el nombre no se ha generado, intentar forzarlo nuevamente
        if not picking_name:
            # Flush y commit nuevamente
            self.env.flush_all()
            cr.commit()
            # Invalidar y leer nuevamente
            picking.invalidate_recordset(['name'])
            picking_name = picking.name
        
        # Verificar que el nombre se haya generado correctamente
        if not picking_name:
            _logger.warning("El picking %d no tiene nombre después de la creación", picking.id)
        else:
            _logger.debug("Picking creado con nombre: %s", picking_name)
        
        return picking

    def _explode_related_products(self, principal_lot, quantity, picking, parent_move):
        """
        Explota los productos relacionados (componentes/periféricos/complementos) de un lote principal.
        
        :param principal_lot: Lote principal (stock.lot)
        :param quantity: Cantidad del producto principal
        :param picking: Picking donde se crearán los movimientos
        :param parent_move: Movimiento padre al que se vincularán los hijos
        :return: Lista de movimientos creados para productos relacionados
        """
        related_moves = []
        
        # Verificar si el lote tiene líneas de suministro (componentes relacionados)
        if not hasattr(principal_lot, 'lot_supply_line_ids') or not principal_lot.lot_supply_line_ids:
            _logger.debug("Lote %s no tiene productos relacionados", principal_lot.name)
            return related_moves
        
        # Obtener el template del producto principal
        product_tmpl = principal_lot.product_id.product_tmpl_id
        if not product_tmpl:
            return related_moves
        
        # Obtener las líneas de suministro que tienen lotes asignados
        supply_lines = principal_lot.lot_supply_line_ids.filtered(lambda sl: sl.related_lot_id)
        
        if not supply_lines:
            _logger.debug("Lote %s tiene líneas de suministro pero sin lotes asignados", principal_lot.name)
            return related_moves
        
        _logger.info("Explotando %d productos relacionados para lote principal %s", 
                    len(supply_lines), principal_lot.name)
        
        # Crear movimientos para cada producto relacionado
        for supply_line in supply_lines:
            related_lot = supply_line.related_lot_id
            if not related_lot:
                continue
            
            related_product = related_lot.product_id
            item_type = supply_line.item_type  # 'component', 'peripheral', 'complement'
            related_qty = supply_line.quantity * quantity  # Multiplicar por cantidad del principal
            
            # Mapear item_type a supply_kind
            supply_kind_map = {
                'component': 'component',
                'peripheral': 'peripheral',
                'complement': 'complement',
            }
            supply_kind = supply_kind_map.get(item_type, 'component')
            
            # Crear movimiento para el producto relacionado (Odoo 19: stock.move usa description_picking, no name)
            move_vals = {
                'description_picking': f"{related_product.display_name} ({supply_kind} de {principal_lot.product_id.display_name})",
                'product_id': related_product.id,
                'product_uom': related_product.uom_id.id,
                'product_uom_qty': related_qty,
                'picking_id': picking.id,
                'location_id': picking.location_id.id,
                'location_dest_id': picking.location_dest_id.id,
                'company_id': self.env.company.id,
                'supply_kind': supply_kind,
                'internal_parent_move_id': parent_move.id,
            }
            
            related_move = self.env['stock.move'].create(move_vals)
            related_moves.append(related_move)
            
            # Crear move line con el número de serie del componente
            move_line_vals = {
                'move_id': related_move.id,
                'product_id': related_product.id,
                'product_uom_id': related_product.uom_id.id,
                'quantity': related_qty,
                'picked': True,
                'lot_id': related_lot.id,
                'location_id': picking.location_id.id,
                'location_dest_id': picking.location_dest_id.id,
                'picking_id': picking.id,
            }
            
            self.env['stock.move.line'].create(move_line_vals)
            
            _logger.info("✓ Movimiento creado para %s (tipo: %s, lote: %s)", 
                        related_product.display_name, supply_kind, related_lot.name)
        
        return related_moves

    def action_trigger_route(self):
        """Procesar la ruta de entrega o devolución creando los pickings necesarios."""
        self.ensure_one()

        if not self.partner_id:
            raise UserError(_('Debe seleccionar un cliente.'))

        if not self.route_id:
            raise UserError(_('Debe seleccionar una ruta.'))

        if not self.line_ids:
            raise UserError(_('Debe agregar al menos una línea con producto y serial.'))

        incomplete = self.line_ids.filtered(
            lambda line: not line.product_id or not line.lot_id
        )
        if incomplete:
            raise UserError(_(
                'Cada línea debe tener producto y número de serie antes de procesar.'
            ))

        lot_ids = self.line_ids.mapped('lot_id').ids
        if len(lot_ids) != len(set(lot_ids)):
            raise UserError(_(
                'Hay números de serie repetidos en las líneas. '
                'Cada equipo debe tener un serial distinto.'
            ))

        _logger.info("Procesando ruta %s para cliente %s con %d productos (Tipo: %s)",
                    self.route_id.name, self.partner_id.name, len(self.line_ids), self.operation_type)

        # Obtener el almacén
        warehouse = self.env['stock.warehouse'].search([], limit=1)
        if not warehouse:
            raise UserError(_('No se encontró un almacén configurado.'))

        # Ubicación del cliente (destino final)
        location_dest_final = self.partner_id.property_stock_customer
        if not location_dest_final:
            raise UserError(_('El cliente no tiene una ubicación configurada. Por favor, configure la ubicación del cliente.'))

        # Obtener las reglas de la ruta ordenadas por secuencia
        route_rules = self.env['stock.rule'].search([
            ('route_id', '=', self.route_id.id)
        ], order='sequence, id')

        if not route_rules:
            raise UserError(_('La ruta seleccionada no tiene reglas configuradas.'))

        # Obtener la primera regla (donde debe empezar)
        first_rule = route_rules[0]

        if not first_rule.picking_type_id:
            raise UserError(_(
                'La primera regla de la ruta no tiene un tipo de operación configurado. '
                'Por favor, verifique la configuración de la ruta.'
            ))

        # Crear el picking en la PRIMERA etapa usando el picking_type de la primera regla
        picking_type = first_rule.picking_type_id

        # Obtener ubicaciones de la primera regla
        location_src = first_rule.location_src_id or picking_type.default_location_src_id
        location_dest_first = picking_type.default_location_dest_id

        if not location_src:
            raise UserError(_('No se pudo determinar la ubicación de origen para la primera etapa de la ruta.'))

        if not location_dest_first:
            raise UserError(_('No se pudo determinar la ubicación de destino para la primera etapa de la ruta. Por favor, verifique la configuración del tipo de operación.'))

        # Generar un origin base único usando timestamp y ID del wizard
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
        origin_base = 'Ruta-%s-%s-W%d' % (
            self.route_id.name[:25],
            timestamp,
            self.id
        )

        # Variable para rastrear los pickings creados
        created_pickings = []

        try:
            _logger.info("=== INICIO: Procesar Ruta de Entrega/Devolución ===")

            picking_vals = {
                'partner_id': self.partner_id.id,
                'picking_type_id': picking_type.id,
                'location_id': location_src.id,
                'location_dest_id': location_dest_first.id,
                'origin': '%s-E1' % origin_base,
                'company_id': self.env.company.id,
            }

            # Crear el picking de forma segura usando el método auxiliar
            picking = self._create_picking_safely(picking_vals)
            _logger.info("✓ Picking inicial creado - ID: %d, Nombre: %s", picking.id, picking.name or '(sin nombre)')

            # Crear movimientos para cada producto
            for line in self.line_ids:
                if not line.lot_id:
                    continue

                product = line.lot_id.product_id
                lot = line.lot_id

                # Determinar si es un producto principal (tiene componentes relacionados)
                is_principal = False
                if hasattr(lot, 'is_principal') and lot.is_principal:
                    is_principal = True
                elif hasattr(lot, 'lot_supply_line_ids') and lot.lot_supply_line_ids:
                    # Si tiene líneas de suministro con lotes asignados, es principal
                    if lot.lot_supply_line_ids.filtered(lambda sl: sl.related_lot_id):
                        is_principal = True

                # Determinar supply_kind: 'parent' si es principal, sino None (será calculado por product_suppiles)
                supply_kind = 'parent' if is_principal else False

                move_vals = {
                    'description_picking': product.display_name,
                    'product_id': product.id,
                    'product_uom': product.uom_id.id,
                    'product_uom_qty': line.quantity,
                    'picking_id': picking.id,
                    'location_id': picking.location_id.id,
                    'location_dest_id': picking.location_dest_id.id,
                    'company_id': self.env.company.id,
                }
                
                # Agregar supply_kind solo si es principal
                if supply_kind:
                    move_vals['supply_kind'] = supply_kind

                move = self.env['stock.move'].create(move_vals)

                # Crear move line con el número de serie solo para el primer picking
                move_line_vals = {
                    'move_id': move.id,
                    'product_id': product.id,
                    'product_uom_id': product.uom_id.id,
                    'quantity': line.quantity,
                    'picked': True,
                    'lot_id': lot.id,
                    'location_id': picking.location_id.id,
                    'location_dest_id': picking.location_dest_id.id,
                    'picking_id': picking.id,
                }

                self.env['stock.move.line'].create(move_line_vals)
                
                # Si es un producto principal, explotar sus componentes relacionados
                if is_principal:
                    _logger.info("Lote %s es principal, explotando productos relacionados...", lot.name)
                    related_moves = self._explode_related_products(
                        principal_lot=lot,
                        quantity=line.quantity,
                        picking=picking,
                        parent_move=move
                    )
                    _logger.info("✓ Creados %d movimientos para productos relacionados", len(related_moves))

            # Confirmar el primer picking
            picking.action_confirm()
            # Forzar flush después de confirmar para asegurar que todos los cambios se guarden
            self.env.flush_all()
            # Commit para asegurar que los cambios se guarden antes de continuar
            self.env.cr.commit()
            _logger.info("✓ Picking inicial confirmado - Estado: %s, Nombre: %s", picking.state, picking.name)

            created_pickings.append(picking)
            current_location = location_dest_first

            _logger.info("Creando %d pickings intermedios...", len(route_rules) - 1)

            # Crear los pickings intermedios para las siguientes etapas
            for rule_idx, rule in enumerate(route_rules[1:], start=1):
                _logger.info("Procesando regla %d de %d: %s", rule_idx + 1, len(route_rules), rule.name)

                if not rule.picking_type_id:
                    _logger.warning("Regla %s no tiene picking_type_id, saltando...", rule.name)
                    continue

                rule_picking_type = rule.picking_type_id
                rule_location_src = rule.location_src_id or rule_picking_type.default_location_src_id
                rule_location_dest = rule_picking_type.default_location_dest_id

                if not rule_location_src or not rule_location_dest:
                    _logger.warning("No se pudieron determinar ubicaciones para regla %s", rule.name)
                    continue

                # Verificar que la ubicación de origen coincida con el destino anterior
                if rule_location_src.id != current_location.id:
                    _logger.warning(
                        "La ubicación de origen de la regla %s (%s) no coincide con el destino anterior (%s). "
                        "Ajustando ubicación...",
                        rule.name, rule_location_src.name, current_location.name
                    )
                    rule_location_src = current_location

                intermediate_picking_vals = {
                    'partner_id': self.partner_id.id,
                    'picking_type_id': rule_picking_type.id,
                    'location_id': rule_location_src.id,
                    'location_dest_id': rule_location_dest.id,
                    'origin': '%s-E%d' % (origin_base, rule_idx + 1),
                    'company_id': self.env.company.id,
                }

                # Crear el picking intermedio de forma segura usando el método auxiliar
                intermediate_picking = self._create_picking_safely(intermediate_picking_vals)
                _logger.info("✓ Picking intermedio %d creado - ID: %d, Nombre: %s",
                           rule_idx + 1, intermediate_picking.id, intermediate_picking.name or '(sin nombre)')

                # Crear movimientos para este picking intermedio, vinculados con el anterior
                previous_picking = created_pickings[-1]
                
                # CORRECCIÓN CRÍTICA: Primero crear todos los movimientos principales
                # Luego crear los movimientos hijos, separando los agrupados
                parent_moves_map = {}  # Mapa de movimientos padres originales -> movimientos intermedios creados
                
                for prev_move in previous_picking.move_ids:
                    # Solo procesar movimientos principales primero
                    if hasattr(prev_move, 'supply_kind') and prev_move.supply_kind != 'parent':
                        continue
                    
                    # Odoo 19: stock.move no tiene 'name'; usar description_picking (o el del move anterior)
                    prev_desc = getattr(prev_move, 'description_picking', None) or (prev_move.product_id.display_name if prev_move.product_id else '')
                    move_vals = {
                        'description_picking': prev_desc,
                        'product_id': prev_move.product_id.id,
                        'product_uom': prev_move.product_uom.id,
                        'product_uom_qty': prev_move.product_uom_qty,
                        'picking_id': intermediate_picking.id,
                        'location_id': intermediate_picking.location_id.id,
                        'location_dest_id': intermediate_picking.location_dest_id.id,
                        'company_id': self.env.company.id,
                        'move_orig_ids': [(4, prev_move.id)],
                    }
                    
                    # Preservar supply_kind si existe
                    if hasattr(prev_move, 'supply_kind') and prev_move.supply_kind:
                        move_vals['supply_kind'] = prev_move.supply_kind
                    
                    intermediate_move = self.env['stock.move'].create(move_vals)
                    
                    # Si el movimiento anterior tiene múltiples move_orig_ids (está agrupado),
                    # mapear cada move_orig_id original al movimiento intermedio creado
                    if hasattr(prev_move, 'move_orig_ids') and prev_move.move_orig_ids and len(prev_move.move_orig_ids) > 1:
                        # Movimiento agrupado: mapear cada movimiento original al movimiento intermedio
                        for orig_move in prev_move.move_orig_ids:
                            if orig_move.id not in parent_moves_map:
                                parent_moves_map[orig_move.id] = []
                            parent_moves_map[orig_move.id].append(intermediate_move)
                    else:
                        # Movimiento no agrupado: mapear directamente
                        if prev_move.id not in parent_moves_map:
                            parent_moves_map[prev_move.id] = []
                        parent_moves_map[prev_move.id].append(intermediate_move)
                
                # CORRECCIÓN CRÍTICA: NO crear movimientos para elementos asociados en pickings intermedios
                # Los elementos asociados se moverán automáticamente cuando se valide el picking
                # a través del método _move_associated_lots_with_principal en stock_move_line.py
                # Esto evita errores de seriales duplicados cuando hay múltiples productos principales
                # con los mismos elementos asociados
                # 
                # SOLUCIÓN: Solo crear movimientos para productos principales en pickings intermedios
                # Los elementos asociados NO necesitan movimientos explícitos porque se moverán
                # automáticamente al validar el picking principal
                _logger.info("✓ Solo se crearon movimientos principales en picking intermedio %d. "
                           "Los elementos asociados se moverán automáticamente al validar.", rule_idx + 1)

                # Confirmar el picking intermedio
                intermediate_picking.action_confirm()
                # Forzar flush después de confirmar para asegurar que todos los cambios se guarden
                self.env.flush_all()
                # Commit para asegurar que los cambios se guarden antes de continuar
                self.env.cr.commit()
                _logger.info("✓ Picking intermedio %d confirmado - Estado: %s, Nombre: %s",
                           rule_idx + 1, intermediate_picking.state, intermediate_picking.name)

                created_pickings.append(intermediate_picking)
                current_location = rule_location_dest

            _logger.info("Total de pickings creados: %d", len(created_pickings))

            # Abrir vista del primer picking creado
            return {
                'type': 'ir.actions.act_window',
                'name': _('Ruta de Entrega Disparada'),
                'res_model': 'stock.picking',
                'res_id': picking.id,
                'view_mode': 'form',
                'target': 'current',
            }

        except Exception as e:
            error_msg = str(e)
            _logger.error("❌ Error al crear pickings: %s", error_msg)
            raise UserError(_(
                'Error al crear la ruta de entrega: %s\n'
                'Por favor, verifique la configuración de las reglas de la ruta y los productos seleccionados.'
            ) % error_msg)

class DeliveryRouteTriggerWizardLine(models.TransientModel):
    """Líneas del wizard: primero producto, luego serial."""
    _name = 'delivery.route.trigger.wizard.line'
    _description = 'Línea de Producto por Número de Serie'

    wizard_id = fields.Many2one(
        'delivery.route.trigger.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade'
    )

    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        domain="[('id', 'in', available_product_ids)]",
        help='Productos con stock disponible en la ubicación de la operación.',
    )

    lot_id = fields.Many2one(
        'stock.lot',
        string='Número de Serie',
        domain="[('id', 'in', available_lot_ids)]",
        help='Seriales del producto elegido en la ubicación correspondiente.',
    )

    available_product_ids = fields.Many2many(
        'product.product',
        related='wizard_id.route_available_product_ids',
        readonly=True,
    )

    available_lot_ids = fields.Many2many(
        'stock.lot',
        string='Lotes disponibles',
        compute='_compute_available_lot_ids',
        store=False,
    )

    @api.depends('product_id', 'wizard_id.route_available_lot_ids')
    def _compute_available_lot_ids(self):
        for line in self:
            lots = line.wizard_id.route_available_lot_ids
            if line.product_id:
                lots = lots.filtered(
                    lambda lot: lot.product_id == line.product_id
                )
            line.available_lot_ids = lots

    quantity = fields.Float(
        string='Cantidad',
        default=1.0,
        required=True,
        help='Cantidad a entregar'
    )

    product_uom_id = fields.Many2one(
        'uom.uom',
        string='Unidad de Medida',
        related='lot_id.product_id.uom_id',
        readonly=True
    )

    dup_plus = fields.Boolean(
        string='+',
        default=False,
        help='Marque para copiar esta fila (mismo producto, serial vacío).',
    )
    dup_extra_count = fields.Integer(
        string='+N',
        default=0,
        help='Escriba cuántas filas más del mismo producto (ej. 9 para completar 10).',
    )

    @api.onchange('wizard_id')
    def _onchange_wizard_id(self):
        if self.wizard_id:
            self._compute_available_lot_ids()

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.lot_id and (
            not self.product_id
            or self.lot_id.product_id != self.product_id
        ):
            self.lot_id = False

    @api.onchange('lot_id')
    def _onchange_lot_id(self):
        if self.lot_id:
            self.product_id = self.lot_id.product_id
            if not self.quantity:
                self.quantity = 1.0

    def _prepare_duplicate_line_vals(self):
        self.ensure_one()
        return {
            'wizard_id': self.wizard_id.id,
            'product_id': self.product_id.id,
            'quantity': self.quantity,
            'lot_id': False,
        }

