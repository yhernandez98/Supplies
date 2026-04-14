# Plan Tecnico - Solucion Comercial Flexible en CRM

## Objetivo
Permitir que el equipo comercial arme, desde cada oportunidad (`crm.lead`), una solucion libre de:
- equipos/productos,
- licencias,
- servicios,
con validacion de disponibilidad, calculo de costo/precio y ejecucion operativa al aprobar.

## Alcance funcional
1. Configuracion libre por oportunidad (sin paquetes fijos).
2. Parametrizacion de reglas de pricing por tipo de linea.
3. Validacion de disponibilidad:
   - Stock para productos (interno).
   - Faltantes para generar alertas de cotizacion (`purchase.alert`).
4. Aprobacion que dispare:
   - actualizacion/creacion de suscripcion (`subscription.subscription`),
   - entrega (`stock.picking`) para lo disponible,
   - alertas de compra para faltantes.
5. Versionado simple por oportunidad (nueva revision).

## Diseno de datos
### 1) Cabecera de propuesta: `crm.solution.quote`
- `lead_id`, `partner_id`, `location_id`, `warehouse_id`, `subscription_id`
- `state`: `draft`, `review`, `approved`, `cancelled`
- `version`, `is_current`
- Totales: `total_cost`, `total_price`, `margin_amount`, `margin_percent`
- Relaciones operativas:
  - `line_ids`
  - `purchase_alert_ids`
  - `picking_ids`

### 2) Lineas: `crm.solution.quote.line`
- `line_type`: `equipment`, `license`, `service`
- `product_id`, `description`, `quantity`
- Pricing: `pricing_rule_id`, `cost_unit`, `price_unit`, `cost_total`, `price_total`
- Disponibilidad: `available_qty`, `missing_qty`, `fulfillment_state`
- Flags operativos: `requires_purchase_alert`, `to_subscription`, `to_delivery`
- Trazabilidad: `purchase_alert_id`

### 3) Parametrizacion de pricing: `crm.solution.pricing.rule`
- `applies_to`: `equipment`, `license`, `service`, `all`
- `method`: `fixed`, `cost_plus_pct`, `manual_with_floor`
- `fixed_price`, `markup_percent`, `min_margin_percent`, `active`

### 4) Parametrizacion de licencias: `crm.solution.license.param`
- `product_categ_id`
- `default_rule_id`
- `currency_mode`: `cop`, `usd_trm`
- `min_margin_percent`, `active`

## Integraciones clave
### CRM (`crm_sales_supplies`)
- Extender `crm.lead` con:
  - `solution_quote_ids`, `solution_quote_count`, `current_solution_quote_id`
  - acciones: abrir wizard, ver propuestas, aprobar propuesta actual

### Alertas de cotizacion (`purchase.alert`)
- Reuso del flujo existente:
  - crear alerta por linea faltante con `alert_line_ids`.

### Suscripciones (`subscription_nocount`)
- En aprobacion:
  - usar `ensure_subscription(...)`
  - pasar lineas marcadas `to_subscription`.

### Inventario/entrega (`stock`)
- En aprobacion:
  - crear `stock.picking` saliente con lineas disponibles (`to_delivery`).

## Flujo operativo
1. Comercial abre wizard desde oportunidad y arma lineas libres.
2. Guarda propuesta (`draft`) y valida disponibilidad/precios (`review`).
3. Al aprobar:
   - se calculan faltantes y alertas,
   - se crea/actualiza suscripcion,
   - se crea entrega para disponibles,
   - estado pasa a `approved`.

## Reglas de evolucion
- No se pisa historico: cambios posteriores se hacen por nueva version.
- Una sola propuesta `is_current=True` por oportunidad.

## Implementacion tecnica (fase inicial)
1. Modelos nuevos y seguridad.
2. Wizard de creacion de propuesta desde `crm.lead`.
3. Vistas de propuesta, reglas y parametros.
4. Integracion basica de aprobacion (alertas + suscripcion + picking).
5. Ajustes iterativos segun validacion de negocio.
