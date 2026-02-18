# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def create_partner_warehouse(self):
        """
        Crea un almacén (stock.warehouse) para el contacto actual.
        
        Reglas:
        - Solo funciona si el contacto es empresa (is_company = True)
        - Solo funciona si tipo_contacto == "cliente" o "ambos"
        - Valida si ya existe un almacén para este contacto
        - Crea el almacén con configuración predeterminada
        - Asigna la compañía "Supplies de Colombia" (ID=1)
        """
        self.ensure_one()
        
        # Validar que el contacto sea empresa
        if not self.is_company:
            raise UserError(_(
                'Solo se pueden crear almacenes para contactos que sean empresas (is_company = True).'
            ))
        
        # Validar que el contacto sea tipo "cliente" o "ambos"
        if self.tipo_contacto not in ('cliente', 'ambos'):
            raise UserError(_(
                'Solo se pueden crear almacenes para contactos con tipo_contacto = "cliente" o "ambos".'
            ))
        
        # Validar que el contacto tenga nombre
        if not self.name:
            raise UserError(_(
                'El contacto debe tener un nombre para crear el almacén.'
            ))
        
        # Validar si ya existe un almacén para este contacto
        existing_warehouse = self.env['stock.warehouse'].search([
            ('partner_id', '=', self.id)
        ], limit=1)
        
        if existing_warehouse:
            raise UserError(_(
                'Ya existe un almacén para este contacto: %s\n'
                'Almacén: %s (Código: %s)'
            ) % (self.name, existing_warehouse.name, existing_warehouse.code))
        
        # Obtener la compañía "Supplies de Colombia" (ID=1)
        company = self.env['res.company'].browse(1)
        if not company.exists():
            raise UserError(_(
                'No se encontró la compañía "Supplies de Colombia" (ID=1).'
            ))
        
        # Obtener el almacén principal de la compañía para resupply_wh_ids
        main_warehouse = self.env['stock.warehouse'].search([
            ('company_id', '=', company.id)
        ], limit=1)
        
        if not main_warehouse:
            raise UserError(_(
                'No se encontró un almacén principal para la compañía "Supplies de Colombia".'
            ))
        
        # Generar el código del almacén (primeros 5 caracteres en mayúsculas)
        warehouse_code = self.name[:5].upper().strip()
        
        # Validar que el código no esté vacío
        if not warehouse_code:
            raise UserError(_(
                'No se pudo generar un código válido para el almacén. '
                'El nombre del contacto debe tener al menos un carácter.'
            ))
        
        # Validar que el código no esté duplicado
        existing_code = self.env['stock.warehouse'].search([
            ('code', '=', warehouse_code),
            ('company_id', '=', company.id)
        ], limit=1)
        
        if existing_code:
            # Si el código está duplicado, agregar un sufijo numérico
            counter = 1
            base_code = warehouse_code
            while existing_code:
                warehouse_code = f"{base_code[:4]}{counter}"
                existing_code = self.env['stock.warehouse'].search([
                    ('code', '=', warehouse_code),
                    ('company_id', '=', company.id)
                ], limit=1)
                counter += 1
                if counter > 99:  # Límite de seguridad
                    raise UserError(_(
                        'No se pudo generar un código único para el almacén.'
                    ))
        
        try:
            # Crear el almacén
            warehouse_vals = {
                'name': self.name,
                'code': warehouse_code,
                'company_id': company.id,
                'partner_id': self.id,
                'reception_steps': 'one_step',
                'delivery_steps': 'ship_only',
                'buy_to_resupply': False,
                'resupply_wh_ids': [(6, 0, [main_warehouse.id])],
            }
            
            warehouse = self.env['stock.warehouse'].create(warehouse_vals)
            
            # NO crear la ruta automáticamente al crear el almacén
            # La ruta se debe crear manualmente usando el botón "Crear Todas las Rutas y Reglas"
            
            # Mensaje de confirmación con efecto visual
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Almacén Creado Exitosamente'),
                    'message': _(
                        'Se ha creado el almacén "%s" con código "%s" para el contacto "%s".\n'
                        'Para crear la ruta y las reglas, use el botón "Crear Todas las Rutas y Reglas".'
                    ) % (warehouse.name, warehouse.code, self.name),
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            raise UserError(_(
                'Error al crear el almacén: %s\n\n'
                'Por favor, verifique los datos del contacto e intente nuevamente.'
            ) % str(e))
    
    def _create_client_route(self, warehouse):
        """
        Crea una ruta (stock.route) para el cliente con la estructura especificada.
        
        Parámetros de la ruta:
        - name: SUPP_ALISTAMIENTO_SALIDA_TRANSPORTE_[CODIGO_ALMACEN]
        - sequence: incrementar en 1, empezar en 5
        - company_id: Supplies de Colombia (ID=1)
        - product_categ_selectable: False
        - product_selectable: True
        - packaging_selectable: False
        - warehouse_selectable: False
        - sale_selectable: True
        """
        _logger.info("=" * 80)
        _logger.info(f"INICIO _create_client_route - Almacén: {warehouse.name} (ID: {warehouse.id}, Código: {warehouse.code})")
        _logger.info("=" * 80)
        
        try:
            # Obtener la compañía "Supplies de Colombia" (ID=1)
            company = self.env['res.company'].browse(1)
            if not company.exists():
                _logger.error("ERROR: No se encontró la compañía 'Supplies de Colombia' (ID=1)")
                raise UserError(_('No se encontró la compañía "Supplies de Colombia" (ID=1).'))
            _logger.info(f"Compañía encontrada: {company.name} (ID: {company.id})")
            
            # Obtener el código del almacén y limpiarlo
            warehouse_code = warehouse.code or ''
            _logger.info(f"Código del almacén original: '{warehouse_code}'")
            warehouse_code_upper = warehouse_code.strip().upper().replace(' ', '_').rstrip('_')
            
            if not warehouse_code_upper:
                # Si no hay código, usar el nombre del almacén
                warehouse_code_upper = warehouse.name.strip().upper().replace(' ', '_').rstrip('_')[:10]
                _logger.warning(f"No había código, usando nombre del almacén: '{warehouse_code_upper}'")
            
            # Construir el nombre de la ruta
            route_name = f'SUPP_ALISTAMIENTO_SALIDA_TRANSPORTE_{warehouse_code_upper}'
            _logger.info(f"Nombre de ruta generado: '{route_name}'")
            
            # Verificar si ya existe una ruta con este nombre
            # Usar sudo() para asegurar que se busque correctamente
            _logger.info(f"Buscando ruta existente con nombre: '{route_name}'")
            existing_route = self.env['stock.route'].sudo().search([
                ('name', '=', route_name),
                ('company_id', '=', company.id)
            ], limit=1)
            
            if existing_route:
                _logger.info(f"Ruta '{route_name}' ya existe (ID: {existing_route.id}), retornando sin crear")
                return existing_route
            
            # Obtener el siguiente número de secuencia (empezar en 5)
            # Buscar la última ruta creada para obtener el siguiente número
            # Usar sudo() para asegurar que se busque correctamente
            _logger.info("Buscando última ruta para obtener secuencia")
            last_route = self.env['stock.route'].sudo().search([
                ('company_id', '=', company.id)
            ], order='sequence desc', limit=1)
            
            if last_route and last_route.sequence >= 5:
                next_sequence = last_route.sequence + 1
                _logger.info(f"Última secuencia encontrada: {last_route.sequence}, siguiente: {next_sequence}")
            else:
                next_sequence = 5
                _logger.info(f"No se encontró ruta con secuencia >= 5, usando secuencia inicial: {next_sequence}")
            
            # Crear la ruta
            route_vals = {
                'name': route_name,
                'sequence': next_sequence,
                'company_id': company.id,
                'product_categ_selectable': False,
                'product_selectable': True,
                'packaging_selectable': False,
                'warehouse_selectable': False,
                'sale_selectable': True,
                'active': True,
            }
            
            # Crear la ruta con sudo() para asegurar permisos
            _logger.info(f"Creando ruta con valores: {route_vals}")
            try:
                route = self.env['stock.route'].sudo().create(route_vals)
                _logger.info(f"Ruta creada exitosamente: {route} (ID: {route.id if route else 'None'})")
            except Exception as create_error:
                _logger.error(f"ERROR al crear la ruta '{route_name}': {str(create_error)}", exc_info=True)
                raise
            
            # Verificar que la ruta se creó correctamente
            if not route or not route.id:
                _logger.error(f"Fallo al crear la ruta: {route_name}. El objeto route es nulo o no tiene ID.")
                raise UserError(_('Error: No se pudo crear la ruta "%s".') % route_name)
            
            # Crear las 4 reglas de stock asociadas a la ruta
            _logger.info(f"Iniciando creación de reglas de stock para la ruta '{route_name}' (ID: {route.id})")
            try:
                self._create_route_rules(route, warehouse, company)
                _logger.info(f"Reglas de stock creadas exitosamente para la ruta '{route_name}'")
            except Exception as rules_error:
                # Si hay error al crear las reglas, eliminar la ruta creada y relanzar el error
                _logger.error(f"ERROR al crear las reglas de stock para la ruta '{route_name}': {str(rules_error)}", exc_info=True)
                _logger.error(f"Eliminando ruta '{route_name}' (ID: {route.id}) debido a error en reglas")
                try:
                    route.sudo().unlink()
                    _logger.info(f"Ruta '{route_name}' eliminada correctamente")
                except Exception as unlink_error:
                    _logger.error(f"ERROR al eliminar la ruta '{route_name}': {str(unlink_error)}")
                raise UserError(_(
                    'Error al crear las reglas de stock para la ruta "%s": %s\n'
                    'La ruta no se creó. Por favor, verifique los tipos de operación necesarios.'
                ) % (route_name, str(rules_error)))
            
            # Invalidar caché para asegurar que la ruta se muestre
            self.env.invalidate_all()
            _logger.info(f"Caché invalidada después de crear la ruta '{route_name}' (ID: {route.id})")
            _logger.info(f"FIN _create_client_route - Ruta creada exitosamente: '{route_name}' (ID: {route.id})")
            _logger.info("=" * 80)
            
            return route
        except Exception as e:
            _logger.error(f"ERROR CRÍTICO en _create_client_route para almacén {warehouse.name}: {str(e)}", exc_info=True)
            raise
    
    def _create_route_rules(self, route, warehouse, company):
        """
        Crea las 4 reglas de stock (stock.rule) asociadas a la ruta.
        
        Reglas:
        1. Existencias - Alistamiento (make_to_stock)
           - location_src_id: Supp/Existencias
           - location_dest_id: Supp/Alistamiento
        2. Alistamiento - Salida (make_to_order)
           - location_src_id: Supp/Alistamiento
           - location_dest_id: Supp/Salida
        3. Salida - Transporte (make_to_order)
           - location_src_id: Supp/Salida
           - location_dest_id: Supp/Transporte
        4. Transporte - [CODIGO_ALMACEN] (make_to_order)
           - location_src_id: Supp/Transporte
           - location_dest_id: almacén de existencias del almacén (lot_stock_id)
        """
        _logger.info("=" * 80)
        _logger.info(f"INICIO _create_route_rules - Ruta: {route.name} (ID: {route.id}), Almacén: {warehouse.name}")
        _logger.info("=" * 80)
        
        try:
            # Buscar los tipos de operación necesarios
            _logger.info("Buscando tipos de operación necesarios...")
            picking_types = self._get_picking_types_for_rules(company)
            _logger.info(f"Tipos de operación encontrados: Alistamiento={picking_types['alistamiento'].id if picking_types['alistamiento'] else 'NO ENCONTRADO'}, Salida={picking_types['salida'].id if picking_types['salida'] else 'NO ENCONTRADO'}, Transporte={picking_types['transporte'].id if picking_types['transporte'] else 'NO ENCONTRADO'}")
            
            if not all(picking_types.values()):
                missing = [k for k, v in picking_types.items() if not v]
                missing_names = {
                    'alistamiento': 'SUPPLIES DE COLOMBIA SAS: Alistamiento',
                    'salida': 'SUPPLIES DE COLOMBIA SAS: Salida',
                    'transporte': 'SUPPLIES DE COLOMBIA SAS: Transporte'
                }
                missing_list = [missing_names.get(k, k) for k in missing]
                _logger.error(f"ERROR: No se encontraron los siguientes tipos de operación: {', '.join(missing_list)}")
                raise UserError(_(
                    'No se encontraron los siguientes tipos de operación: %s\n'
                    'Por favor, verifique que existan en el sistema con estos nombres exactos.'
                ) % ', '.join(missing_list))
        
            # Obtener el código del almacén para la cuarta regla
            warehouse_code = warehouse.code or ''
            warehouse_code_upper = warehouse_code.strip().upper().replace(' ', '_').rstrip('_')
            
            if not warehouse_code_upper:
                warehouse_code_upper = warehouse.name.strip().upper().replace(' ', '_').rstrip('_')[:10]
            
            _logger.info(f"Código del almacén para regla 4: '{warehouse_code_upper}'")
            
            # Obtener el tipo de operación de entrega del almacén (out_type_id)
            _logger.info("Buscando tipo de operación de entrega del almacén (out_type_id)...")
            warehouse_out_type = warehouse.out_type_id
            if not warehouse_out_type:
                _logger.error(f"ERROR: No se encontró el tipo de operación de entrega para el almacén '{warehouse.name}' (ID: {warehouse.id})")
                raise UserError(_(
                    'No se encontró el tipo de operación de entrega para el almacén "%s".'
                ) % warehouse.name)
            _logger.info(f"Tipo de operación de entrega encontrado: {warehouse_out_type.name} (ID: {warehouse_out_type.id})")
            
            # Obtener la ubicación de existencias del almacén (lot_stock_id)
            _logger.info("Buscando ubicación de existencias del almacén (lot_stock_id)...")
            stock_location = warehouse.lot_stock_id
            if not stock_location:
                _logger.error(f"ERROR: No se encontró la ubicación de existencias (lot_stock_id) para el almacén '{warehouse.name}' (ID: {warehouse.id})")
                raise UserError(_(
                    'No se encontró la ubicación de existencias (lot_stock_id) para el almacén "%s".'
                ) % warehouse.name)
            _logger.info(f"Ubicación de existencias encontrada: {stock_location.complete_name} (ID: {stock_location.id})")
            
            # Buscar las ubicaciones por su nombre completo (complete_name)
            # Usar sudo() para asegurar permisos y evitar errores de transacción
            _logger.info("Buscando ubicaciones del sistema (Supp/Existencias, Supp/Alistamiento, Supp/Salida, Supp/Transporte)...")
            try:
                location_existencias = self.env['stock.location'].sudo().search([
                    ('complete_name', '=', 'Supp/Existencias'),
                    ('company_id', '=', company.id)
                ], limit=1)
                _logger.info(f"Ubicación Existencias: {'ENCONTRADA' if location_existencias else 'NO ENCONTRADA'} - {location_existencias.complete_name if location_existencias else 'N/A'}")
                
                location_alistamiento = self.env['stock.location'].sudo().search([
                    ('complete_name', '=', 'Supp/Alistamiento'),
                    ('company_id', '=', company.id)
                ], limit=1)
                _logger.info(f"Ubicación Alistamiento: {'ENCONTRADA' if location_alistamiento else 'NO ENCONTRADA'} - {location_alistamiento.complete_name if location_alistamiento else 'N/A'}")
                
                location_salida = self.env['stock.location'].sudo().search([
                    ('complete_name', '=', 'Supp/Salida'),
                    ('company_id', '=', company.id)
                ], limit=1)
                _logger.info(f"Ubicación Salida: {'ENCONTRADA' if location_salida else 'NO ENCONTRADA'} - {location_salida.complete_name if location_salida else 'N/A'}")
                
                location_transporte = self.env['stock.location'].sudo().search([
                    ('complete_name', '=', 'Supp/Transporte'),
                    ('company_id', '=', company.id)
                ], limit=1)
                _logger.info(f"Ubicación Transporte: {'ENCONTRADA' if location_transporte else 'NO ENCONTRADA'} - {location_transporte.complete_name if location_transporte else 'N/A'}")
            except Exception as e:
                _logger.error(f"ERROR al buscar ubicaciones: {str(e)}", exc_info=True)
                raise UserError(_('Error al buscar ubicaciones: %s') % str(e))
            
            # Validar que todas las ubicaciones existan
            if not location_existencias:
                _logger.error("ERROR: No se encontró la ubicación 'Supp/Existencias'")
                raise UserError(_('No se encontró la ubicación "Supp/Existencias".'))
            if not location_alistamiento:
                _logger.error("ERROR: No se encontró la ubicación 'Supp/Alistamiento'")
                raise UserError(_('No se encontró la ubicación "Supp/Alistamiento".'))
            if not location_salida:
                _logger.error("ERROR: No se encontró la ubicación 'Supp/Salida'")
                raise UserError(_('No se encontró la ubicación "Supp/Salida".'))
            if not location_transporte:
                _logger.error("ERROR: No se encontró la ubicación 'Supp/Transporte'")
                raise UserError(_('No se encontró la ubicación "Supp/Transporte".'))
            
            _logger.info(f"Todas las ubicaciones encontradas correctamente:")
            _logger.info(f"  - Existencias: {location_existencias.complete_name} (ID: {location_existencias.id})")
            _logger.info(f"  - Alistamiento: {location_alistamiento.complete_name} (ID: {location_alistamiento.id})")
            _logger.info(f"  - Salida: {location_salida.complete_name} (ID: {location_salida.id})")
            _logger.info(f"  - Transporte: {location_transporte.complete_name} (ID: {location_transporte.id})")
            _logger.info(f"  - Stock Almacén: {stock_location.complete_name} (ID: {stock_location.id})")
        
            # Regla 1: Existencias - Alistamiento
            _logger.info("Creando Regla 1: Existencias - Alistamiento")
            rule1_vals = {
                'name': 'Existencias - Alistamiento',
                'action': 'pull',
                'picking_type_id': picking_types['alistamiento'].id,
                'location_src_id': location_existencias.id,
                'location_dest_id': location_alistamiento.id,
                'procure_method': 'make_to_stock',
                'company_id': company.id,
                'route_id': route.id,
                'active': True,
            }
            _logger.info(f"Valores Regla 1: {rule1_vals}")
            try:
                rule1 = self.env['stock.rule'].sudo().create(rule1_vals)
                _logger.info(f"Regla 1 creada exitosamente (ID: {rule1.id})")
            except Exception as e:
                _logger.error(f"ERROR al crear Regla 1: {str(e)}", exc_info=True)
                raise
            
            # Regla 2: Alistamiento - Salida
            _logger.info("Creando Regla 2: Alistamiento - Salida")
            rule2_vals = {
                'name': 'Alistamiento - Salida',
                'action': 'pull',
                'picking_type_id': picking_types['salida'].id,
                'location_src_id': location_alistamiento.id,
                'location_dest_id': location_salida.id,
                'procure_method': 'make_to_order',
                'company_id': company.id,
                'route_id': route.id,
                'active': True,
            }
            _logger.info(f"Valores Regla 2: {rule2_vals}")
            try:
                rule2 = self.env['stock.rule'].sudo().create(rule2_vals)
                _logger.info(f"Regla 2 creada exitosamente (ID: {rule2.id})")
            except Exception as e:
                _logger.error(f"ERROR al crear Regla 2: {str(e)}", exc_info=True)
                raise
            
            # Regla 3: Salida - Transporte
            _logger.info("Creando Regla 3: Salida - Transporte")
            rule3_vals = {
                'name': 'Salida - Transporte',
                'action': 'pull',
                'picking_type_id': picking_types['transporte'].id,
                'location_src_id': location_salida.id,
                'location_dest_id': location_transporte.id,
                'procure_method': 'make_to_order',
                'company_id': company.id,
                'route_id': route.id,
                'active': True,
            }
            _logger.info(f"Valores Regla 3: {rule3_vals}")
            try:
                rule3 = self.env['stock.rule'].sudo().create(rule3_vals)
                _logger.info(f"Regla 3 creada exitosamente (ID: {rule3.id})")
            except Exception as e:
                _logger.error(f"ERROR al crear Regla 3: {str(e)}", exc_info=True)
                raise
            
            # Regla 4: Transporte - [CODIGO_ALMACEN]
            _logger.info(f"Creando Regla 4: Transporte - {warehouse_code_upper}")
            rule4_vals = {
                'name': f'Transporte - {warehouse_code_upper}',
                'action': 'pull',
                'picking_type_id': warehouse_out_type.id,
                'location_src_id': location_transporte.id,
                'location_dest_id': stock_location.id,  # Ubicación de existencias del almacén
                'procure_method': 'make_to_order',
                'company_id': company.id,
                'route_id': route.id,
                'active': True,
            }
            _logger.info(f"Valores Regla 4: {rule4_vals}")
            try:
                rule4 = self.env['stock.rule'].sudo().create(rule4_vals)
                _logger.info(f"Regla 4 creada exitosamente (ID: {rule4.id})")
            except Exception as e:
                _logger.error(f"ERROR al crear Regla 4: {str(e)}", exc_info=True)
                raise
            
            _logger.info(f"Todas las reglas de stock creadas exitosamente para la ruta {route.name} (ID: {route.id})")
            _logger.info("=" * 80)
            _logger.info(f"FIN _create_route_rules - 4 reglas creadas exitosamente")
            _logger.info("=" * 80)
        except Exception as e:
            _logger.error(f"ERROR CRÍTICO en _create_route_rules para ruta {route.name}: {str(e)}", exc_info=True)
            raise
    
    def _get_picking_types_for_rules(self, company):
        """
        Busca los tipos de operación necesarios para las reglas.
        
        Retorna un diccionario con:
        - 'alistamiento': tipo de operación "SUPPLIES DE COLOMBIA SAS: Alistamiento"
        - 'salida': tipo de operación "SUPPLIES DE COLOMBIA SAS: Salida"
        - 'transporte': tipo de operación "SUPPLIES DE COLOMBIA SAS: Transporte"
        """
        _logger.info(f"Buscando tipos de operación para compañía: {company.name} (ID: {company.id})")
        picking_types = {
            'alistamiento': False,
            'salida': False,
            'transporte': False,
        }
        
        # Buscar tipo de operación "Alistamiento"
        _logger.info("Buscando tipo de operación 'Alistamiento'...")
        # Primero intentar con el nombre completo exacto
        alistamiento_type = self.env['stock.picking.type'].search([
            ('name', '=', 'SUPPLIES DE COLOMBIA SAS: Alistamiento'),
            ('company_id', '=', company.id)
        ], limit=1)
        
        if not alistamiento_type:
            _logger.warning("No se encontró 'SUPPLIES DE COLOMBIA SAS: Alistamiento', buscando con ilike...")
            # Si no se encuentra, buscar con ilike
            alistamiento_type = self.env['stock.picking.type'].search([
                ('name', 'ilike', 'Alistamiento'),
                ('company_id', '=', company.id)
            ], limit=1)
        
        if alistamiento_type:
            _logger.info(f"Tipo de operación Alistamiento encontrado: {alistamiento_type.name} (ID: {alistamiento_type.id})")
        else:
            _logger.error("ERROR: No se encontró tipo de operación 'Alistamiento'")
            # Listar todos los tipos de operación disponibles para debugging
            all_picking_types = self.env['stock.picking.type'].search([
                ('company_id', '=', company.id)
            ])
            _logger.error(f"Tipos de operación disponibles en la compañía {company.name}: {[pt.name for pt in all_picking_types[:10]]}")
        
        picking_types['alistamiento'] = alistamiento_type
        
        # Buscar tipo de operación "Salida"
        _logger.info("Buscando tipo de operación 'Salida'...")
        # Primero intentar con el nombre completo exacto
        salida_type = self.env['stock.picking.type'].search([
            ('name', '=', 'SUPPLIES DE COLOMBIA SAS: Salida'),
            ('company_id', '=', company.id)
        ], limit=1)
        
        if not salida_type:
            _logger.warning("No se encontró 'SUPPLIES DE COLOMBIA SAS: Salida', buscando con ilike...")
            # Si no se encuentra, buscar con ilike
            salida_type = self.env['stock.picking.type'].search([
                ('name', 'ilike', 'Salida'),
                ('company_id', '=', company.id)
            ], limit=1)
        
        if salida_type:
            _logger.info(f"Tipo de operación Salida encontrado: {salida_type.name} (ID: {salida_type.id})")
        else:
            _logger.error("ERROR: No se encontró tipo de operación 'Salida'")
        
        picking_types['salida'] = salida_type
        
        # Buscar tipo de operación "Transporte"
        _logger.info("Buscando tipo de operación 'Transporte'...")
        # Primero intentar con el nombre completo exacto
        transporte_type = self.env['stock.picking.type'].search([
            ('name', '=', 'SUPPLIES DE COLOMBIA SAS: Transporte'),
            ('company_id', '=', company.id)
        ], limit=1)
        
        if not transporte_type:
            _logger.warning("No se encontró 'SUPPLIES DE COLOMBIA SAS: Transporte', buscando con ilike...")
            # Si no se encuentra, buscar con ilike
            transporte_type = self.env['stock.picking.type'].search([
                ('name', 'ilike', 'Transporte'),
                ('company_id', '=', company.id)
            ], limit=1)
        
        if transporte_type:
            _logger.info(f"Tipo de operación Transporte encontrado: {transporte_type.name} (ID: {transporte_type.id})")
        else:
            _logger.error("ERROR: No se encontró tipo de operación 'Transporte'")
        
        picking_types['transporte'] = transporte_type
        
        _logger.info(f"Resumen tipos de operación: Alistamiento={'OK' if picking_types['alistamiento'] else 'FALTA'}, Salida={'OK' if picking_types['salida'] else 'FALTA'}, Transporte={'OK' if picking_types['transporte'] else 'FALTA'}")
        
        return picking_types
    
    def _get_client_return_picking_type(self, warehouse):
        """
        Devuelve el tipo de operación de devolución del cliente si ya existe.
        """
        if not warehouse:
            return self.env['stock.picking.type']
        pt = self.env['stock.picking.type'].sudo().search([
            ('warehouse_id', '=', warehouse.id),
            ('name', 'ilike', 'Devolución'),
        ], limit=1)
        if not pt:
            pt = self.env['stock.picking.type'].sudo().search([
                ('warehouse_id', '=', warehouse.id),
                ('name', 'ilike', 'Devoluciones'),
            ], limit=1)
        return pt
    
    def _get_or_create_client_return_picking_type(self, warehouse, company, location_src, location_dest):
        """
        Crea si no existe el tipo de operación de DEVOLUCIÓN propio del cliente
        (ej. "Blindex: Devoluciones Blindex"), con origen cliente → Supp/Transporte.
        Así la primera regla de la ruta de devolución no usa Órdenes de entrega.
        """
        if not warehouse:
            return self.env['stock.picking.type']
        pt = self._get_client_return_picking_type(warehouse)
        if pt:
            return pt
        warehouse_name = (warehouse.name or '').strip()
        warehouse_code = (warehouse.code or warehouse.name or '')[:10].strip().upper().replace(' ', '_').rstrip('_') or 'DEV'
        type_name = _('%s: Devoluciones %s') % (warehouse_name, warehouse_name)
        seq_code = 'stock.picking.devolucion.%s' % warehouse_code
        sequence = self.env['ir.sequence'].sudo().search([
            ('code', '=', seq_code),
            ('company_id', 'in', [False, company.id]),
        ], limit=1)
        if not sequence:
            sequence = self.env['ir.sequence'].sudo().create({
                'name': _('Devoluciones %s') % warehouse_name,
                'code': seq_code,
                'prefix': 'DEV_%s/' % warehouse_code,
                'padding': 5,
                'number_next': 1,
                'number_increment': 1,
                'company_id': company.id,
            })
        # code en stock.picking.type es Selection (incoming/outgoing/internal); no admite 'devolucion'
        pt = self.env['stock.picking.type'].sudo().create({
            'name': type_name,
            'warehouse_id': warehouse.id,
            'sequence_id': sequence.id,
            'default_location_src_id': location_src.id,
            'default_location_dest_id': location_dest.id,
            'code': 'internal',
            'sequence_code': 'DEV_%s' % warehouse_code,
            'company_id': company.id,
        })
        _logger.info('Creado tipo de operación de devolución: %s (ID: %s)', type_name, pt.id)
        return pt
    
    def _get_main_supp_warehouse(self, company):
        """
        Almacén principal de Supp (sin partner_id), donde están Supp/Transporte,
        Supp/Devolución, Supp/Verificación. Evita usar tipos de almacenes de clientes (B&S, etc.).
        """
        wh = self.env['stock.warehouse'].sudo().search([
            ('company_id', '=', company.id),
            ('partner_id', '=', False),
        ], limit=1)
        if not wh:
            wh = self.env['stock.warehouse'].sudo().search([
                ('company_id', '=', company.id),
                ('name', 'ilike', 'SUPPLIES'),
            ], limit=1)
        if not wh:
            wh = self.env['stock.warehouse'].sudo().search([
                ('company_id', '=', company.id),
            ], limit=1)
        return wh
    
    def _get_picking_types_for_return_rules(self, company):
        """
        Busca los tipos de operación de la ruta de devolución solo del almacén
        principal Supp (SUPPLIES DE COLOMBIA SAS), no de B&S ni otros clientes.
        Retorna: transporte, devoluciones_transporte (para regla Transporte→Devolución),
                 devolucion, verificacion.
        """
        main_wh = self._get_main_supp_warehouse(company)
        if not main_wh:
            raise UserError(_('No se encontró el almacén principal de Supp (sin partner).'))
        _logger.info(f"Tipos de operación para ruta de devolución: solo almacén Supp '%s' (ID: %s)", main_wh.name, main_wh.id)
        result = {'transporte': False, 'devoluciones_transporte': False, 'devolucion': False, 'verificacion': False}
        for key, term in [
            ('transporte', 'Transporte'),
            ('devoluciones_transporte', 'Devoluciones en Transporte'),
            ('devolucion', 'Devolución'),
            ('verificacion', 'Verificación'),
        ]:
            pt = self.env['stock.picking.type'].sudo().search([
                ('company_id', '=', company.id),
                ('warehouse_id', '=', main_wh.id),
                ('name', 'ilike', term),
            ], limit=1)
            result[key] = pt
            _logger.info(f"Tipo '{term}': {'OK' if pt else 'NO ENCONTRADO'} - {pt.name if pt else 'N/A'}")
        # Fallback: si no existe "Devoluciones en Transporte", usar "Transporte" para la 2ª regla
        if not result['devoluciones_transporte'] and result['transporte']:
            result['devoluciones_transporte'] = result['transporte']
            _logger.info("Usando tipo 'Transporte' como fallback para regla Transporte - Devolución")
        return result
    
    def _create_client_return_route(self, warehouse, company):
        """
        Crea la ruta de devolución (cliente → Supp): desde almacén del cliente
        hasta Supp/Existencias pasando por Transporte → Devolución → Verificación.
        Nombre: SUPP_DEVOLUCION_[CODIGO_ALMACEN].
        """
        warehouse_code = (warehouse.code or warehouse.name or '')[:10]
        warehouse_code_upper = warehouse_code.strip().upper().replace(' ', '_').rstrip('_') or 'DEV'
        route_name = f'SUPP_DEVOLUCION_{warehouse_code_upper}'
        _logger.info(f"Creando ruta de devolución: {route_name}")
        existing = self.env['stock.route'].sudo().search([
            ('name', '=', route_name),
            ('company_id', '=', company.id),
        ], limit=1)
        if existing:
            _logger.info(f"Ruta de devolución '{route_name}' ya existe (ID: {existing.id})")
            return existing
        last_route = self.env['stock.route'].sudo().search(
            [('company_id', '=', company.id)],
            order='sequence desc', limit=1
        )
        next_seq = (last_route.sequence + 1) if last_route and last_route.sequence >= 5 else 5
        route_vals = {
            'name': route_name,
            'sequence': next_seq,
            'company_id': company.id,
            'product_categ_selectable': False,
            'product_selectable': True,
            'packaging_selectable': False,
            'warehouse_selectable': False,
            'sale_selectable': False,
            'active': True,
        }
        route = self.env['stock.route'].sudo().create(route_vals)
        try:
            self._create_return_route_rules(route, warehouse, company)
        except Exception as e:
            _logger.error(f"Error al crear reglas de devolución: {e}", exc_info=True)
            try:
                route.sudo().unlink()
            except Exception:
                pass
            raise UserError(_('Error al crear reglas de la ruta de devolución "%s": %s') % (route_name, str(e)))
        self.env.invalidate_all()
        _logger.info(f"Ruta de devolución creada: {route_name} (ID: {route.id})")
        return route
    
    def _create_return_route_rules(self, route, warehouse, company):
        """
        Crea las 4 reglas de la ruta de devolución (como el ejemplo Devolución Blindex):
        1. [Almacén cliente] → Supp/Transporte   (pull)
        2. Supp/Transporte → Supp/Devolución      (pull)
        3. Supp/Devolución → Supp/Verificación    (pull)
        4. Supp/Verificación → Supp/Existencias   (pull)
        """
        stock_location = warehouse.lot_stock_id
        if not stock_location:
            raise UserError(_('No se encontró la ubicación de existencias del almacén "%s".') % warehouse.name)
        locs = {}
        for name in ('Supp/Transporte', 'Supp/Devolución', 'Supp/Verificación', 'Supp/Existencias'):
            loc = self.env['stock.location'].sudo().search([
                ('complete_name', '=', name),
                ('company_id', '=', company.id),
            ], limit=1)
            if not loc:
                # Fallback: buscar por nombre del segmento (p. ej. sin tilde: Devolucion)
                segment = name.split('/')[-1]
                loc = self.env['stock.location'].sudo().search([
                    ('company_id', '=', company.id),
                    ('complete_name', 'ilike', segment),
                ], limit=1)
            if not loc:
                raise UserError(_('No se encontró la ubicación "%s". Créela en Inventario → Configuración → Ubicaciones.') % name)
            locs[name] = loc
        transport, devol, verif, exist = locs['Supp/Transporte'], locs['Supp/Devolución'], locs['Supp/Verificación'], locs['Supp/Existencias']
        pts = self._get_picking_types_for_return_rules(company)
        # Regla 2 (Transporte → Devolución) usa "Devoluciones en Transporte" si existe, si no "Transporte"
        pt_transporte_devolucion = pts.get('devoluciones_transporte') or pts['transporte']
        if not pt_transporte_devolucion:
            raise UserError(_('No se encontró un tipo de operación "Devoluciones en Transporte" ni "Transporte" para la ruta de devolución.'))
        if not pts['devolucion']:
            raise UserError(_('No se encontró un tipo de operación que contenga "Devolución". Créelo en Inventario → Tipos de operación.'))
        if not pts['verificacion']:
            raise UserError(_('No se encontró un tipo de operación que contenga "Verificación". Créelo en Inventario → Tipos de operación.'))
        # Regla 1: crear o usar tipo de operación de DEVOLUCIÓN propio del cliente (no Órdenes de entrega)
        # Ej.: "Blindex: Devoluciones Blindex" con origen cliente → Supp/Transporte
        client_return_type = self._get_or_create_client_return_picking_type(
            warehouse, company, stock_location, transport
        )
        rules_data = [
            (_('Cliente - Transporte'), stock_location.id, transport.id, client_return_type.id),
            (_('Transporte - Devolución'), transport.id, devol.id, pt_transporte_devolucion.id),
            (_('Devolución - Verificación'), devol.id, verif.id, pts['devolucion'].id),
            (_('Verificación - Existencias'), verif.id, exist.id, pts['verificacion'].id),
        ]
        for name, src_id, dest_id, picking_type_id in rules_data:
            self.env['stock.rule'].sudo().create({
                'name': name,
                'action': 'pull',
                'picking_type_id': picking_type_id,
                'location_src_id': src_id,
                'location_dest_id': dest_id,
                'procure_method': 'make_to_order',
                'company_id': company.id,
                'route_id': route.id,
                'active': True,
            })
        _logger.info("Reglas de ruta de devolución creadas correctamente.")
    
    def action_view_warehouse(self):
        """
        Abre la vista del almacén asociado a este contacto.
        """
        self.ensure_one()
        
        warehouse = self.env['stock.warehouse'].search([
            ('partner_id', '=', self.id)
        ], limit=1)
        
        if not warehouse:
            raise UserError(_(
                'No se encontró un almacén asociado a este contacto.'
            ))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Almacén'),
            'res_model': 'stock.warehouse',
            'res_id': warehouse.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_create_routes_from_form(self):
        """
        Botón "Crear Rutas" en formulario: ejecuta la misma lógica que
        "Crear Todas las Rutas y Reglas" (acción masiva).
        """
        return self.env['res.partner'].action_create_all_routes()
    
    @api.model
    def action_fix_return_route_operation_types(self):
        """
        Corrige el tipo de operación de las reglas de cada ruta SUPP_DEVOLUCION_*:
        - Regla 1 "Cliente - Transporte": tipo de operación de DEVOLUCIÓN del cliente
          (ej. "Blindex: Devoluciones Blindex"), no Órdenes de entrega.
        - Reglas 2, 3, 4: tipos del almacén principal Supp (Transporte, Devolución, Verificación).
        """
        company = self.env['res.company'].browse(1)
        if not company.exists():
            raise UserError(_('No se encontró la compañía (ID=1).'))
        partner = self.env['res.partner'].browse(1)
        main_wh = partner._get_main_supp_warehouse(company)
        if not main_wh:
            raise UserError(_('No se encontró el almacén principal Supp (sin partner).'))
        pts = partner._get_picking_types_for_return_rules(company)
        pt_transporte_devolucion = pts.get('devoluciones_transporte') or pts['transporte']
        if not pt_transporte_devolucion or not pts.get('devolucion') or not pts.get('verificacion'):
            raise UserError(_(
                'Faltan tipos de operación del almacén Supp (Devoluciones en Transporte o Transporte, Devolución, Verificación). '
                'Verifique en Inventario → Tipos de operación que existan para SUPPLIES DE COLOMBIA SAS.'
            ))
        routes = self.env['stock.route'].sudo().search([
            ('name', 'like', 'SUPP_DEVOLUCION_%'),
            ('company_id', '=', company.id),
        ])
        updated = 0
        errors = []
        rule_names_to_supp_type = [
            ('Transporte - Devolución', pt_transporte_devolucion.id),
            ('Devolución - Verificación', pts['devolucion'].id),
            ('Verificación - Existencias', pts['verificacion'].id),
        ]
        for route in routes:
            # Regla 1: Cliente - Transporte -> tipo de operación de DEVOLUCIÓN del cliente (no Órdenes de entrega)
            first_rule = self.env['stock.rule'].sudo().search([
                ('route_id', '=', route.id),
                ('name', '=', 'Cliente - Transporte'),
            ], limit=1)
            if first_rule:
                src_loc = first_rule.location_src_id
                warehouse = self.env['stock.warehouse'].sudo().search([
                    ('lot_stock_id', '=', src_loc.id),
                ], limit=1)
                if warehouse:
                    # Crear tipo "X: Devoluciones X" si no existe y asignarlo
                    client_return_type = partner._get_or_create_client_return_picking_type(
                        warehouse, company,
                        first_rule.location_src_id,
                        first_rule.location_dest_id,
                    )
                    if client_return_type and first_rule.picking_type_id.id != client_return_type.id:
                        first_rule.sudo().write({'picking_type_id': client_return_type.id})
                        updated += 1
                        _logger.info('Ruta %s: regla Cliente-Transporte → %s (devolución)', route.name, client_return_type.name)
                else:
                    errors.append(_('Ruta %s: no se encontró almacén con lot_stock_id = %s') % (route.name, src_loc.complete_name))
            # Reglas 2, 3, 4: tipos del almacén Supp (no B&S)
            for rule_name, correct_picking_type_id in rule_names_to_supp_type:
                rule = self.env['stock.rule'].sudo().search([
                    ('route_id', '=', route.id),
                    ('name', '=', rule_name),
                ], limit=1)
                if rule and rule.picking_type_id.id != correct_picking_type_id:
                    rule.sudo().write({'picking_type_id': correct_picking_type_id})
                    updated += 1
                    _logger.info('Ruta %s: regla %s → tipo Supp', route.name, rule_name)
        msg = [_('Proceso completado.'), _('✅ Reglas corregidas: %s') % updated]
        if errors:
            msg.append(_('⚠️ Advertencias: %s') % len(errors))
            for e in errors[:5]:
                msg.append(str(e))
            if len(errors) > 5:
                msg.append(_('... y %s más') % (len(errors) - 5))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Corregir tipo de operación en rutas de devolución'),
                'message': '\n'.join(msg),
                'type': 'success' if updated else 'info',
                'sticky': True,
            }
        }
    
    def action_update_location(self):
        """
        Actualiza las ubicaciones de stock del contacto:
        - property_stock_customer: se actualiza a la ubicación del almacén creado
        - property_stock_supplier: se actualiza a la ubicación con ID 7 (formato {"1": 7})
        """
        self.ensure_one()
        
        # Validar que el contacto sea empresa
        if not self.is_company:
            raise UserError(_(
                'Solo se pueden actualizar ubicaciones para contactos que sean empresas (is_company = True).'
            ))
        
        # Validar que el contacto sea tipo "cliente" o "ambos"
        if self.tipo_contacto not in ('cliente', 'ambos'):
            raise UserError(_(
                'Solo se pueden actualizar ubicaciones para contactos con tipo_contacto = "cliente" o "ambos".'
            ))
        
        # Buscar el almacén asociado a este contacto
        warehouse = self.env['stock.warehouse'].search([
            ('partner_id', '=', self.id)
        ], limit=1)
        
        if not warehouse:
            raise UserError(_(
                'No se encontró un almacén asociado a este contacto. '
                'Por favor, cree el almacén primero usando el botón "Crear Almacén".'
            ))
        
        try:
            # Obtener la ubicación del almacén (lot_stock_id es la ubicación principal del almacén)
            customer_location = warehouse.lot_stock_id
            
            if not customer_location:
                raise UserError(_(
                    'No se encontró la ubicación del almacén "%s".'
                ) % warehouse.name)
            
            # Obtener la compañía "Supplies de Colombia" (ID=1)
            company = self.env['res.company'].browse(1)
            if not company.exists():
                raise UserError(_(
                    'No se encontró la compañía "Supplies de Colombia" (ID=1).'
                ))
            
            # Actualizar property_stock_supplier con la ubicación ID 7
            # El formato {"1": 7} significa ubicación ID 7 para la compañía ID 1
            supplier_location = self.env['stock.location'].browse(7)
            
            if not supplier_location.exists():
                raise UserError(_(
                    'No se encontró la ubicación del proveedor con ID 7. '
                    'Por favor, verifique que la ubicación existe en el sistema.'
                ))
            
            # Actualizar las propiedades usando write() con el contexto de la compañía
            # Esto asegura que las propiedades se guarden correctamente por compañía
            self.with_context(allowed_company_ids=[company.id]).write({
                'property_stock_customer': customer_location.id,
                'property_stock_supplier': supplier_location.id,
            })
            
            # Mensaje de confirmación
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Ubicaciones Actualizadas Exitosamente'),
                    'message': _(
                        'Se han actualizado las ubicaciones para el contacto "%s":\n'
                        '- Ubicación Cliente: %s (ID: %s)\n'
                        '- Ubicación Proveedor: %s (ID: 7)'
                    ) % (self.name, customer_location.complete_name, customer_location.id, supplier_location.complete_name),
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            raise UserError(_(
                'Error al actualizar las ubicaciones: %s\n\n'
                'Por favor, verifique los datos e intente nuevamente.'
            ) % str(e))
    
    @api.model
    def action_create_all_warehouses(self):
        """
        Crea almacenes para todos los clientes de tipo "cliente" o "ambos" 
        que sean empresas y que no tengan almacén creado.
        
        Retorna un resumen con el número de almacenes creados exitosamente
        y los errores encontrados.
        """
        # Buscar todos los contactos que cumplan las condiciones:
        # - is_company = True
        # - tipo_contacto in ('cliente', 'ambos')
        # - No tengan almacén asociado
        partners = self.env['res.partner'].search([
            ('is_company', '=', True),
            ('tipo_contacto', 'in', ['cliente', 'ambos']),
        ])
        
        # Filtrar los que no tienen almacén
        partners_without_warehouse = partners.filtered(
            lambda p: not self.env['stock.warehouse'].search([
                ('partner_id', '=', p.id)
            ], limit=1)
        )
        
        if not partners_without_warehouse:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No hay contactos para procesar'),
                    'message': _(
                        'Todos los clientes de tipo "cliente" o "ambos" ya tienen almacén creado.'
                    ),
                    'type': 'info',
                    'sticky': False,
                }
            }
        
        # Obtener la compañía "Supplies de Colombia" (ID=1)
        company = self.env['res.company'].browse(1)
        if not company.exists():
            raise UserError(_(
                'No se encontró la compañía "Supplies de Colombia" (ID=1).'
            ))
        
        # Obtener el almacén principal de la compañía para resupply_wh_ids
        main_warehouse = self.env['stock.warehouse'].search([
            ('company_id', '=', company.id)
        ], limit=1)
        
        if not main_warehouse:
            raise UserError(_(
                'No se encontró un almacén principal para la compañía "Supplies de Colombia".'
            ))
        
        # Contadores
        created_count = 0
        error_count = 0
        errors = []
        
        # Crear almacenes para cada contacto
        for partner in partners_without_warehouse:
            try:
                # Validar que el contacto tenga nombre
                if not partner.name:
                    errors.append(_('Contacto sin nombre (ID: %s)') % partner.id)
                    error_count += 1
                    continue
                
                # Generar el código del almacén (primeros 5 caracteres en mayúsculas)
                warehouse_code = partner.name[:5].upper().strip()
                
                # Validar que el código no esté vacío
                if not warehouse_code:
                    errors.append(_('Contacto "%s" (ID: %s): No se pudo generar código válido') % (partner.name, partner.id))
                    error_count += 1
                    continue
                
                # Validar que el código no esté duplicado
                existing_code = self.env['stock.warehouse'].search([
                    ('code', '=', warehouse_code),
                    ('company_id', '=', company.id)
                ], limit=1)
                
                if existing_code:
                    # Si el código está duplicado, agregar un sufijo numérico
                    counter = 1
                    base_code = warehouse_code
                    while existing_code:
                        warehouse_code = f"{base_code[:4]}{counter}"
                        existing_code = self.env['stock.warehouse'].search([
                            ('code', '=', warehouse_code),
                            ('company_id', '=', company.id)
                        ], limit=1)
                        counter += 1
                        if counter > 99:  # Límite de seguridad
                            errors.append(_('Contacto "%s" (ID: %s): No se pudo generar código único') % (partner.name, partner.id))
                            error_count += 1
                            continue
                
                # Crear el almacén
                warehouse_vals = {
                    'name': partner.name,
                    'code': warehouse_code,
                    'company_id': company.id,
                    'partner_id': partner.id,
                    'reception_steps': 'one_step',
                    'delivery_steps': 'ship_only',
                    'buy_to_resupply': False,
                    'resupply_wh_ids': [(6, 0, [main_warehouse.id])],
                }
                
                warehouse = self.env['stock.warehouse'].create(warehouse_vals)
                
                # NO crear la ruta automáticamente al crear el almacén
                # La ruta se debe crear manualmente usando el botón "Crear Todas las Rutas y Reglas"
                
                created_count += 1
                
            except Exception as e:
                error_count += 1
                error_msg = str(e)
                if partner.name:
                    errors.append(_('Contacto "%s" (ID: %s): %s') % (partner.name, partner.id, error_msg))
                else:
                    errors.append(_('Contacto (ID: %s): %s') % (partner.id, error_msg))
        
        # Preparar mensaje de resultado
        message_parts = []
        message_parts.append(_('Proceso completado:\n'))
        message_parts.append(_('✅ Almacenes creados exitosamente: %s') % created_count)
        message_parts.append(_('ℹ️ Para crear las rutas y reglas, use el botón "Crear Todas las Rutas y Reglas".'))
        
        if error_count > 0:
            message_parts.append(_('\n❌ Errores encontrados: %s') % error_count)
            if errors:
                message_parts.append(_('\n\nErrores detallados:'))
                for error in errors[:10]:  # Mostrar máximo 10 errores
                    message_parts.append(f'\n- {error}')
                if len(errors) > 10:
                    message_parts.append(_('\n... y %s errores más') % (len(errors) - 10))
        
        # Determinar el tipo de notificación
        notification_type = 'success' if error_count == 0 else 'warning' if created_count > 0 else 'danger'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Creación Masiva de Almacenes'),
                'message': '\n'.join(message_parts),
                'type': notification_type,
                'sticky': True,
            }
        }
    
    @api.model
    def action_create_all_routes(self):
        """
        Crea rutas y reglas para todos los clientes que tengan almacén
        pero que no tengan ruta creada.
        
        Retorna un resumen con el número de rutas creadas exitosamente
        y los errores encontrados.
        """
        # Log inmediato al inicio del método para verificar que se ejecuta
        # Usar print también para asegurar que se vea en la consola
        print("=" * 80)
        print("=== INICIO: action_create_all_routes ===")
        print("=" * 80)
        _logger.info("=" * 80)
        _logger.info("=== INICIO: action_create_all_routes ===")
        _logger.info("=" * 80)
        try:
            # Buscar todos los contactos que cumplan las condiciones:
            # - is_company = True
            # - tipo_contacto in ('cliente', 'ambos')
            partners = self.env['res.partner'].search([
                ('is_company', '=', True),
                ('tipo_contacto', 'in', ['cliente', 'ambos']),
            ])
            _logger.info(f"Contactos encontrados: {len(partners)}")
            
            if not partners:
                _logger.warning("No se encontraron contactos de tipo 'cliente' o 'ambos'")
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('No hay contactos para procesar'),
                        'message': _(
                            'No se encontraron contactos de tipo "cliente" o "ambos".'
                        ),
                        'type': 'info',
                        'sticky': False,
                    }
                }
            
            # Buscar todos los almacenes con partner_id
            warehouses = self.env['stock.warehouse'].search([
                ('partner_id', 'in', partners.ids)
            ])
            _logger.info(f"Almacenes encontrados: {len(warehouses)}")
            
            # Obtener los IDs de los partners que tienen almacén
            partners_with_warehouse_ids = warehouses.mapped('partner_id').ids
            
            # Filtrar los partners que tienen almacén
            partners_with_warehouse = partners.filtered(lambda p: p.id in partners_with_warehouse_ids)
            _logger.info(f"Contactos con almacén: {len(partners_with_warehouse)}")
            
            if not partners_with_warehouse:
                _logger.warning("No se encontraron contactos con almacén asociado")
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('No hay contactos para procesar'),
                        'message': _(
                            'No se encontraron contactos con almacén asociado.'
                        ),
                        'type': 'info',
                        'sticky': False,
                    }
                }
            
            # Obtener la compañía "Supplies de Colombia" (ID=1)
            company = self.env['res.company'].browse(1)
            if not company.exists():
                raise UserError(_(
                    'No se encontró la compañía "Supplies de Colombia" (ID=1).'
                ))
            
            # Contadores
            routes_created_count = 0
            routes_existing_count = 0
            return_routes_created_count = 0
            return_routes_existing_count = 0
            error_count = 0
            errors = []
            
            # Crear un diccionario para mapear partner_id -> warehouse
            partner_warehouse_map = {w.partner_id.id: w for w in warehouses}
            
            # Crear rutas para cada contacto
            _logger.info(f"Iniciando creación de rutas para {len(partners_with_warehouse)} contactos")
            for partner in partners_with_warehouse:
                # Limpiar cualquier transacción abortada antes de procesar el siguiente contacto
                try:
                    if self.env.cr.closed:
                        _logger.warning(f"Cursor cerrado para contacto {partner.id}, saltando...")
                        continue
                    # Verificar si hay una transacción abortada y hacer rollback si es necesario
                    self.env.cr.execute("SELECT 1")
                except Exception as cleanup_error:
                    _logger.warning(f"Error al verificar transacción para contacto {partner.id}: {str(cleanup_error)}")
                    try:
                        self.env.cr.rollback()
                        self.env.clear()
                    except:
                        pass
                
                # Crear un savepoint para cada contacto para poder hacer rollback si hay error
                savepoint = self.env.cr.savepoint()
                try:
                    # Obtener el almacén del diccionario
                    warehouse = partner_warehouse_map.get(partner.id)
                    
                    if not warehouse:
                        _logger.warning(f"Partner {partner.id} no tiene almacén en el mapa")
                        continue
                    
                    # Verificar si ya existe una ruta para este almacén
                    warehouse_code = warehouse.code or ''
                    warehouse_code_upper = warehouse_code.strip().upper().replace(' ', '_').rstrip('_')
                    
                    if not warehouse_code_upper:
                        warehouse_code_upper = warehouse.name.strip().upper().replace(' ', '_').rstrip('_')[:10]
                    
                    route_name = f'SUPP_ALISTAMIENTO_SALIDA_TRANSPORTE_{warehouse_code_upper}'
                    _logger.info(f"Procesando contacto {partner.id} ({partner.name}): ruta '{route_name}'")
                    
                    # Buscar si ya existe una ruta para este almacén
                    # Usar sudo() para asegurar que se busque correctamente
                    # Hacer flush antes de buscar para evitar problemas de transacción
                    try:
                        self.env.cr.flush()
                        existing_route = self.env['stock.route'].sudo().search([
                            ('name', '=', route_name),
                            ('company_id', '=', company.id)
                        ], limit=1)
                    except Exception as e:
                        _logger.error(f"Error al buscar ruta existente para contacto {partner.id}: {str(e)}")
                        # Hacer rollback y continuar
                        savepoint.rollback()
                        error_count += 1
                        partner_name = getattr(partner, 'name', False) or f'ID: {partner.id}'
                        errors.append(_('Contacto "%s" (ID: %s): Error al buscar ruta existente: %s') % (partner_name, partner.id, str(e)))
                        continue
                    
                    if existing_route:
                        _logger.info(f"Ruta '{route_name}' ya existe (ID: {existing_route.id})")
                        routes_existing_count += 1
                        # Intentar crear ruta de devolución si no existe
                        return_route_name = f'SUPP_DEVOLUCION_{warehouse_code_upper}'
                        existing_return = self.env['stock.route'].sudo().search([
                            ('name', '=', return_route_name),
                            ('company_id', '=', company.id),
                        ], limit=1)
                        if existing_return:
                            return_routes_existing_count += 1
                        else:
                            try:
                                partner.sudo()._create_client_return_route(warehouse, company)
                                return_routes_created_count += 1
                                self.env.invalidate_all()
                            except Exception as ret_e:
                                _logger.warning(f"Ruta de devolución para {partner.name}: {ret_e}")
                                errors.append(_('Contacto "%s": Ruta de devolución: %s') % (partner.name, str(ret_e)))
                                error_count += 1
                        continue
                    
                    # Crear la ruta y las reglas
                    try:
                        _logger.info(f"Creando ruta '{route_name}' para contacto {partner.id}")
                        # Usar sudo() para crear la ruta con permisos completos
                        route = partner.sudo()._create_client_route(warehouse)
                        if route:
                            _logger.info(f"Ruta '{route_name}' creada exitosamente (ID: {route.id})")
                            routes_created_count += 1
                            self.env.invalidate_all()
                            # Crear ruta de devolución (cliente → Supp) si no existe
                            return_route_name = f'SUPP_DEVOLUCION_{warehouse_code_upper}'
                            existing_return = self.env['stock.route'].sudo().search([
                                ('name', '=', return_route_name),
                                ('company_id', '=', company.id),
                            ], limit=1)
                            if existing_return:
                                return_routes_existing_count += 1
                            else:
                                try:
                                    partner.sudo()._create_client_return_route(warehouse, company)
                                    return_routes_created_count += 1
                                    self.env.invalidate_all()
                                except Exception as ret_e:
                                    _logger.warning(f"Ruta de devolución para {partner.name}: {ret_e}")
                                    errors.append(_('Contacto "%s": Ruta de devolución: %s') % (partner.name, str(ret_e)))
                                    error_count += 1
                        else:
                            _logger.error(f"Ruta '{route_name}' no se creó (retornó None)")
                            # Hacer rollback del savepoint si no se creó la ruta
                            savepoint.rollback()
                            error_count += 1
                            partner_name = getattr(partner, 'name', False) or f'ID: {partner.id}'
                            errors.append(_('Contacto "%s" (ID: %s): La ruta no se creó (retornó None)') % (partner_name, partner.id))
                    except UserError as ue:
                        # Si es un UserError, hacer rollback del savepoint y continuar
                        try:
                            savepoint.rollback()
                        except:
                            # Si el savepoint falla, intentar rollback de la transacción completa
                            try:
                                self.env.cr.rollback()
                            except:
                                pass
                        error_count += 1
                        error_msg = str(ue)
                        partner_name = getattr(partner, 'name', False) or f'ID: {partner.id}'
                        _logger.error(f"UserError al crear ruta para contacto {partner.id}: {error_msg}")
                        errors.append(_('Contacto "%s" (ID: %s): %s') % (partner_name, partner.id, error_msg))
                        # Limpiar el entorno para evitar problemas de caché
                        self.env.clear()
                        # Continuar con el siguiente partner
                        continue
                    except Exception as e:
                        # Capturar otros errores y hacer rollback del savepoint
                        try:
                            savepoint.rollback()
                        except:
                            # Si el savepoint falla, intentar rollback de la transacción completa
                            try:
                                self.env.cr.rollback()
                            except:
                                pass
                        error_count += 1
                        error_msg = str(e)
                        partner_name = getattr(partner, 'name', False) or f'ID: {partner.id}'
                        _logger.error(f"Error inesperado al crear ruta para contacto {partner.id}: {error_msg}", exc_info=True)
                        errors.append(_('Contacto "%s" (ID: %s): Error inesperado: %s') % (partner_name, partner.id, error_msg))
                        # Limpiar el entorno para evitar problemas de caché
                        self.env.clear()
                        # Continuar con el siguiente partner
                        continue
                    
                except Exception as e:
                    # Capturar el error y hacer rollback del savepoint
                    try:
                        savepoint.rollback()
                    except:
                        # Si el savepoint falla, intentar rollback de la transacción completa
                        try:
                            self.env.cr.rollback()
                        except:
                            pass
                    error_count += 1
                    error_msg = str(e)
                    partner_name = getattr(partner, 'name', False) or f'ID: {partner.id}'
                    _logger.error(f"Error general al procesar contacto {partner.id}: {error_msg}", exc_info=True)
                    errors.append(_('Contacto "%s" (ID: %s): Error general: %s') % (partner_name, partner.id, error_msg))
                    # Limpiar el entorno para evitar problemas de caché
                    self.env.clear()
                    # Continuar con el siguiente partner
                    continue
            
            # Preparar mensaje de resultado
            message_parts = []
            message_parts.append(_('Proceso completado:\n'))
            
            # Intentar verificar cuántas rutas hay en el sistema (solo si no hay errores críticos)
            try:
                all_supp_routes = self.env['stock.route'].sudo().search([
                    ('name', 'like', 'SUPP_ALISTAMIENTO_SALIDA_TRANSPORTE_%'),
                    ('company_id', '=', company.id)
                ])
                total_routes_in_db = len(all_supp_routes)
                message_parts.append(_('📊 Total de rutas SUPP en el sistema: %s') % total_routes_in_db)
            except Exception:
                # Si hay error al contar, simplemente omitir esta información
                pass
            
            if routes_created_count > 0:
                message_parts.append(_('✅ Rutas de entrega creadas: %s') % routes_created_count)
                message_parts.append(_('✅ Reglas de stock (entrega): %s (4 reglas por ruta)') % (routes_created_count * 4))
            else:
                message_parts.append(_('⚠️ No se crearon nuevas rutas de entrega.'))
                if routes_existing_count == 0 and error_count == 0:
                    message_parts.append(_('No se encontraron contactos con almacenes para procesar.'))
            
            if routes_existing_count > 0:
                message_parts.append(_('ℹ️ Rutas de entrega ya existentes: %s') % routes_existing_count)
            
            if return_routes_created_count > 0:
                message_parts.append(_('✅ Rutas de devolución creadas: %s') % return_routes_created_count)
                message_parts.append(_('✅ Reglas de devolución: %s (4 reglas por ruta)') % (return_routes_created_count * 4))
            if return_routes_existing_count > 0:
                message_parts.append(_('ℹ️ Rutas de devolución ya existentes: %s') % return_routes_existing_count)
            
            if error_count > 0:
                message_parts.append(_('\n❌ Errores encontrados: %s') % error_count)
                if errors:
                    message_parts.append(_('\n\nErrores detallados (primeros 10):'))
                    for error in errors[:10]:  # Mostrar máximo 10 errores
                        message_parts.append(f'\n- {error}')
                    if len(errors) > 10:
                        message_parts.append(_('\n... y %s errores más') % (len(errors) - 10))
            
            # Asegurar que siempre haya un mensaje
            if len(message_parts) == 1:  # Solo "Proceso completado:"
                message_parts.append(_('No se procesó ningún contacto.'))
            
            # Determinar el tipo de notificación
            if routes_created_count > 0 and error_count == 0:
                notification_type = 'success'
            elif routes_created_count > 0 or routes_existing_count > 0:
                notification_type = 'warning'
            else:
                notification_type = 'info'
            
            _logger.info(f"=== FIN: action_create_all_routes - Rutas creadas: {routes_created_count}, Existentes: {routes_existing_count}, Errores: {error_count} ===")
            _logger.info(f"Mensaje a mostrar: {message_parts}")
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Creación Masiva de Rutas y Reglas'),
                    'message': '\n'.join(message_parts),
                    'type': notification_type,
                    'sticky': True,
                }
            }
        except Exception as e:
            # Capturar cualquier error inesperado y mostrar un mensaje
            import traceback
            error_trace = traceback.format_exc()
            _logger.error(f"=== ERROR CRÍTICO en action_create_all_routes: {str(e)} ===", exc_info=True)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error en Creación de Rutas'),
                    'message': _(
                        'Ocurrió un error inesperado al crear las rutas:\n%s\n\n'
                        'Por favor, contacte al administrador del sistema.'
                    ) % str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }
    
    @api.model
    def action_update_all_locations(self):
        """
        Actualiza las ubicaciones de stock para todos los contactos que:
        - Sean empresas (is_company = True)
        - Tengan tipo_contacto = "cliente" o "ambos"
        - Tengan un almacén asociado
        
        Actualiza:
        - property_stock_customer: ubicación del almacén creado
        - property_stock_supplier: ubicación con ID 7
        """
        # Buscar todos los contactos que cumplan las condiciones:
        # - is_company = True
        # - tipo_contacto in ('cliente', 'ambos')
        # - Tengan almacén asociado
        partners = self.env['res.partner'].search([
            ('is_company', '=', True),
            ('tipo_contacto', 'in', ['cliente', 'ambos']),
        ])
        
        # Filtrar los que tienen almacén
        partners_with_warehouse = partners.filtered(
            lambda p: self.env['stock.warehouse'].search([
                ('partner_id', '=', p.id)
            ], limit=1)
        )
        
        if not partners_with_warehouse:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No hay contactos para procesar'),
                    'message': _(
                        'No se encontraron contactos con almacén asociado para actualizar ubicaciones.'
                    ),
                    'type': 'info',
                    'sticky': False,
                }
            }
        
        # Obtener la compañía "Supplies de Colombia" (ID=1)
        company = self.env['res.company'].browse(1)
        if not company.exists():
            raise UserError(_(
                'No se encontró la compañía "Supplies de Colombia" (ID=1).'
            ))
        
        # Obtener la ubicación del proveedor (ID 7)
        supplier_location = self.env['stock.location'].browse(7)
        if not supplier_location.exists():
            raise UserError(_(
                'No se encontró la ubicación del proveedor con ID 7. '
                'Por favor, verifique que la ubicación existe en el sistema.'
            ))
        
        # Contadores
        updated_count = 0
        error_count = 0
        errors = []
        
        # Actualizar ubicaciones para cada contacto
        for partner in partners_with_warehouse:
            try:
                # Buscar el almacén asociado
                warehouse = self.env['stock.warehouse'].search([
                    ('partner_id', '=', partner.id)
                ], limit=1)
                
                if not warehouse:
                    errors.append(_('Contacto "%s" (ID: %s): No se encontró almacén asociado') % (partner.name, partner.id))
                    error_count += 1
                    continue
                
                # Obtener la ubicación del almacén
                customer_location = warehouse.lot_stock_id
                
                if not customer_location:
                    errors.append(_('Contacto "%s" (ID: %s): No se encontró la ubicación del almacén "%s"') % (partner.name, partner.id, warehouse.name))
                    error_count += 1
                    continue
                
                # Actualizar las propiedades usando write() con el contexto de la compañía
                partner.with_context(allowed_company_ids=[company.id]).write({
                    'property_stock_customer': customer_location.id,
                    'property_stock_supplier': supplier_location.id,
                })
                
                updated_count += 1
                
            except Exception as e:
                error_count += 1
                error_msg = str(e)
                if partner.name:
                    errors.append(_('Contacto "%s" (ID: %s): %s') % (partner.name, partner.id, error_msg))
                else:
                    errors.append(_('Contacto (ID: %s): %s') % (partner.id, error_msg))
        
        # Preparar mensaje de resultado
        message_parts = []
        message_parts.append(_('Proceso completado:\n'))
        message_parts.append(_('✅ Ubicaciones actualizadas exitosamente: %s') % updated_count)
        
        if error_count > 0:
            message_parts.append(_('\n❌ Errores encontrados: %s') % error_count)
            if errors:
                message_parts.append(_('\n\nErrores detallados:'))
                for error in errors[:10]:  # Mostrar máximo 10 errores
                    message_parts.append(f'\n- {error}')
                if len(errors) > 10:
                    message_parts.append(_('\n... y %s errores más') % (len(errors) - 10))
        
        # Determinar el tipo de notificación
        notification_type = 'success' if error_count == 0 else 'warning' if updated_count > 0 else 'danger'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Actualización Masiva de Ubicaciones'),
                'message': '\n'.join(message_parts),
                'type': notification_type,
                'sticky': True,
            }
        }

