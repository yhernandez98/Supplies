# Flujo CRM -> Ventas -> Compras (Mapa Técnico)

## Objetivo

Documentar el flujo actual y los puntos seguros de extensión para mantener compatibilidad con `crm_sales_supplies`, `calculadora_costos` y módulos nativos de Odoo 19.

## Flujo operacional actual

1. `crm.lead` crea o reutiliza `sale.order`.
2. `sale.order` dispara creación de `purchase.alert` cuando detecta faltantes de stock.
3. `purchase.alert` genera cotizaciones proveedor (`purchase.order`) por wizard.
4. Una cotización proveedor aprobada por CRM se marca como ganadora.
5. `commercial.integration.case` sincroniza `calculadora.costos`.
6. La calculadora proyecta propuesta comercial.
7. El caso ejecuta operación (entrega o compra) según política.

## Puntos de extensión recomendados

- Proyección comercial a cliente:
  - `commercial.integration.case._sync_sale_order_from_calculadora()`
- Compuerta de ejecución:
  - `commercial.integration.case._can_execute_operations()`
- Selección multi-moneda de cotización proveedor:
  - `commercial.integration.case._normalized_price_company_currency(po_line)`

## Reglas de seguridad funcional

- No exponer en `sale.order` desglose de costos internos (`seguro`, `márgenes`, componentes internos).
- Toda comparación entre cotizaciones proveedor debe normalizarse a moneda de compañía.
- Evitar rutas operativas automáticas sin validar política de aprobación configurada por compañía.
