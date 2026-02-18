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
    
    @api.onchange('partner_id', 'operation_type')
    def _onchange_partner_or_operation(self):
        """Limpiar ruta seleccionada cuando cambia el cliente o el tipo de operación."""
        _logger.info("=== _onchange_partner_or_operation ===")
        _logger.info("Partner: %s, Operation Type: %s", 
                    self.partner_id.name if self.partner_id else 'None', 
                    self.operation_type)
        
        if self.partner_id:
            # Forzar recálculo de rutas disponibles
            self._compute_available_route_ids()
            # Limpiar la ruta seleccionada si no está en las disponibles
            if self.route_id and self.route_id not in self.available_route_ids:
                self.route_id = False
                self.route_code = False
            
            # Forzar recálculo de lotes disponibles en las líneas
            _logger.info("Forzando recálculo de lotes para %d líneas", len(self.line_ids))
            for line in self.line_ids:
                # Invalidar el campo computed para forzar su recálculo
                line._compute_available_lot_ids()
                if line.lot_id and line.lot_id not in line.available_lot_ids:
                    line.lot_id = False
        else:
            self.route_id = False
            self.route_code = False
            self.available_route_ids = False
            # Limpiar lotes disponibles en las líneas
            for line in self.line_ids:
                line.available_lot_ids = False
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
        # Si se indica only_related_lot_ids (ej. devolución con selección), filtrar solo esos
        only_related_lot_ids = self.env.context.get('only_related_lot_ids') or []
        if only_related_lot_ids:
            supply_lines = supply_lines.filtered(lambda sl: sl.related_lot_id.id in only_related_lot_ids)
        
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
            
            # Crear movimiento para el producto relacionado
            move_vals = {
                'name': f"{related_product.display_name} ({supply_kind} de {principal_lot.product_id.display_name})",
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
                'qty_done': related_qty,
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
            raise UserError(_('Debe agregar al menos un producto por número de serie.'))

        # DEVOLUCIÓN: validar fechas de finalización antes de continuar
        if self.operation_type == 'return' and not self.env.context.get('skip_return_date_validation'):
            today = fields.Date.context_today(self)
            lots_with_early_return = []
            for line in self.line_ids:
                if not line.lot_id:
                    continue
                lot = line.lot_id
                exit_date = getattr(lot, 'exit_date', None) or getattr(lot, 'last_exit_date_display', None)
                if exit_date and exit_date > today:
                    lots_with_early_return.append((lot, exit_date))
            if lots_with_early_return:
                return self._action_open_return_date_warning_wizard(lots_with_early_return)

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
                    'name': product.display_name,
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
                    'qty_done': line.quantity,
                    'lot_id': lot.id,
                    'location_id': picking.location_id.id,
                    'location_dest_id': picking.location_dest_id.id,
                    'picking_id': picking.id,
                }

                self.env['stock.move.line'].create(move_line_vals)
                
                # Si es un producto principal, explotar sus componentes relacionados
                if is_principal:
                    only_ids = []
                    if self.operation_type == 'return' and line.related_lot_ids_to_return:
                        only_ids = line.related_lot_ids_to_return.ids
                    _logger.info("Lote %s es principal, explotando productos relacionados... (solo_ids=%s)", lot.name, only_ids or 'todos')
                    related_moves = self.with_context(only_related_lot_ids=only_ids)._explode_related_products(
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
                    'origin': '%s-E%d' % (origin_base, rule_idx + 2),
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
                    
                    move_vals = {
                        'name': prev_move.name,
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

    def _action_open_return_date_warning_wizard(self, lots_with_early_return):
        """Abre el wizard de aviso cuando hay devoluciones con fecha de finalización no cumplida."""
        self.ensure_one()
        ReturnDateWizard = self.env['return.date.warning.wizard']
        def _to_date(d):
            return d.date() if hasattr(d, 'date') and callable(getattr(d, 'date')) else d
        line_vals = [
            (0, 0, {'lot_id': lot.id, 'exit_date': _to_date(exit_date)})
            for lot, exit_date in lots_with_early_return
        ]
        wiz = ReturnDateWizard.create({
            'delivery_wizard_id': self.id,
            'line_ids': line_vals,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Devolución: fecha de finalización no cumplida'),
            'res_model': 'return.date.warning.wizard',
            'res_id': wiz.id,
            'view_mode': 'form',
            'target': 'new',
        }


class DeliveryRouteTriggerWizardLine(models.TransientModel):
    """Líneas del wizard para productos por número de serie."""
    _name = 'delivery.route.trigger.wizard.line'
    _description = 'Línea de Producto por Número de Serie'

    wizard_id = fields.Many2one(
        'delivery.route.trigger.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade'
    )

    lot_id = fields.Many2one(
        'stock.lot',
        string='Número de Serie / Placa de Inventario',
        required=True,
        domain="[('id', 'in', available_lot_ids)]",
        help='Seleccione el número de serie o busque por placa de inventario. Los lotes disponibles dependen del tipo de operación seleccionado.'
    )
    
    available_lot_ids = fields.Many2many(
        'stock.lot',
        string='Lotes Disponibles',
        compute='_compute_available_lot_ids',
        store=False,
        help='Lotes disponibles en Supp/Existencias'
    )
    
    @api.depends('wizard_id', 'wizard_id.operation_type', 'wizard_id.partner_id')
    def _compute_available_lot_ids(self):
        """Calcular lotes disponibles según el tipo de operación."""
        _logger.info("=== _compute_available_lot_ids ===")
        _logger.info("Procesando %d líneas", len(self))
        
        for line in self:
            # Verificar si wizard_id existe de forma segura
            if not line.wizard_id:
                _logger.debug("Línea sin wizard_id, disponible_lot_ids = False")
                line.available_lot_ids = False
                continue
            
            wizard = line.wizard_id
            if not wizard.exists():
                _logger.debug("Wizard no existe, available_lot_ids = False")
                line.available_lot_ids = False
                continue
            
            # Acceder a los campos del wizard directamente
            # Si no existen, usar valores por defecto
            operation_type = getattr(wizard, 'operation_type', False)
            partner = getattr(wizard, 'partner_id', False)
            
            _logger.info("Línea - Operación: %s, Cliente: %s", 
                        operation_type, partner.name if partner else 'None')
            
            if not operation_type:
                _logger.debug("Sin tipo de operación, available_lot_ids = False")
                line.available_lot_ids = False
                continue
            
            # Determinar la ubicación según el tipo de operación
            if operation_type == 'delivery':
                # ENTREGA: Buscar lotes en Supp/Existencias
                supplies_location = self.env['stock.location'].search([
                    ('complete_name', 'ilike', 'Supp/Existencias'),
                    ('usage', '=', 'internal'),
                ], limit=1)
                
                if not supplies_location:
                    _logger.warning("No se encontró la ubicación Supp/Existencias")
                    line.available_lot_ids = False
                    continue
                
                # Obtener todas las ubicaciones hijas
                location_ids = self.env['stock.location'].search([
                    ('id', 'child_of', supplies_location.id)
                ]).ids
                
            elif operation_type == 'return':
                # DEVOLUCIÓN: Buscar lotes en la ubicación del cliente
                if not partner:
                    _logger.warning("DEVOLUCIÓN: No hay cliente seleccionado en el wizard")
                    line.available_lot_ids = False
                    continue
                
                # Acceder a la ubicación del cliente
                customer_location = partner.property_stock_customer
                if not customer_location:
                    _logger.warning("DEVOLUCIÓN: Cliente %s (ID: %s) no tiene ubicación configurada (property_stock_customer)", 
                                  partner.name, partner.id)
                    line.available_lot_ids = False
                    continue
                
                _logger.info("DEVOLUCIÓN: Buscando lotes en ubicación del cliente: %s (ID: %s)", 
                           customer_location.complete_name, customer_location.id)
                
                # Obtener todas las ubicaciones hijas del cliente
                location_ids = self.env['stock.location'].search([
                    ('id', 'child_of', customer_location.id)
                ]).ids
                
                _logger.debug("DEVOLUCIÓN: Ubicaciones incluidas (hijas): %s", location_ids)
            else:
                line.available_lot_ids = False
                continue
            
            # Buscar quants en la ubicación correspondiente con cantidad > 0
            quants = self.env['stock.quant'].search([
                ('location_id', 'in', location_ids),
                ('quantity', '>', 0),
                ('lot_id', '!=', False),
            ])
            
            _logger.debug("%s: Quants encontrados: %d en ubicaciones %s", 
                         operation_type.upper(), len(quants), location_ids[:5] if location_ids else [])
            
            # Obtener IDs únicos de lotes disponibles
            lot_ids = quants.mapped('lot_id')
            line.available_lot_ids = lot_ids
            
            _logger.info("Lotes disponibles para línea (operación: %s, cliente: %s): %d lotes", 
                         operation_type or 'N/A', partner.name if partner else 'N/A', len(lot_ids))

    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        related='lot_id.product_id',
        readonly=True,
        store=False
    )

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

    # Para DEVOLUCIÓN: elementos asociados que se incluirán en la devolución (el usuario puede quitar alguno)
    related_lot_ids_to_return = fields.Many2many(
        'stock.lot',
        'delivery_route_trigger_line_related_lot_rel',
        'wizard_line_id',
        'lot_id',
        string='Elementos asociados a devolver',
        help='En devolución: componentes/periféricos/complementos que se devuelven con este producto. Por defecto todos; puede quitar los que no devuelva.'
    )

    @api.onchange('lot_id')
    def _onchange_lot_id(self):
        """Actualizar cantidad por defecto cuando se selecciona un lote."""
        if self.lot_id and self.lot_id.product_id and not self.quantity:
            self.quantity = 1.0
        # En devolución: pre-llenar elementos asociados a devolver
        if self.lot_id and self.wizard_id and self.wizard_id.operation_type == 'return':
            if hasattr(self.lot_id, 'lot_supply_line_ids') and self.lot_id.lot_supply_line_ids:
                related = self.lot_id.lot_supply_line_ids.mapped('related_lot_id').filtered(lambda r: r)
                self.related_lot_ids_to_return = [(6, 0, related.ids)]
            else:
                self.related_lot_ids_to_return = [(5, 0, 0)]

    @api.model_create_multi
    def create(self, vals_list):
        """Forzar cálculo de available_lot_ids al crear líneas."""
        lines = super().create(vals_list)
        # Forzar recálculo del campo computed después de crear
        for line in lines:
            if line.wizard_id:
                line._compute_available_lot_ids()
        return lines
    
    @api.onchange('wizard_id')
    def _onchange_wizard_id(self):
        """Recalcular lotes disponibles cuando se asigna el wizard."""
        if self.wizard_id:
            self._compute_available_lot_ids()


class ReturnDateWarningWizardLine(models.TransientModel):
    _name = 'return.date.warning.wizard.line'
    _description = 'Línea del wizard de aviso de fecha de devolución'

    wizard_id = fields.Many2one('return.date.warning.wizard', required=True, ondelete='cascade')
    lot_id = fields.Many2one('stock.lot', string='Lote/Serie', required=True, ondelete='cascade')
    exit_date = fields.Date(string='Fecha de finalización')


class ReturnDateWarningWizard(models.TransientModel):
    _name = 'return.date.warning.wizard'
    _description = 'Aviso: devolución con fecha de finalización no cumplida'

    delivery_wizard_id = fields.Many2one(
        'delivery.route.trigger.wizard',
        string='Wizard de ruta',
        required=True,
        ondelete='cascade'
    )
    line_ids = fields.One2many(
        'return.date.warning.wizard.line',
        'wizard_id',
        string='Productos con fecha no cumplida'
    )

    def action_cancel_return(self):
        """No devolver: cerrar wizard y mostrar mensaje."""
        self.ensure_one()
        return {'type': 'ir.actions.act_window_close'}

    def action_continue_with_penalty(self):
        """Continuar asumiendo la penalización."""
        self.ensure_one()
        return self.delivery_wizard_id.with_context(
            skip_return_date_validation=True,
            return_with_penalty=True
        ).action_trigger_route()

    def action_continue_without_penalty(self):
        """Continuar sin penalización."""
        self.ensure_one()
        return self.delivery_wizard_id.with_context(
            skip_return_date_validation=True,
            return_with_penalty=False
        ).action_trigger_route()

