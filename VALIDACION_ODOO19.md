# Validación: Módulos Odoo 19 vs 18 y Enterprise 19

Este documento resume la comparación entre:
- **Referencia (funciona bien):** `Modulos Odoo` (v18)
- **Objetivo:** `Modulos Odoo 19` (v19) — que todo funcione igual (vistas, tema, XML, funcionalidades, campos, reportes)
- **Nativos/Enterprise:** `enterprise-19.0` para dependencias y compatibilidad

---

## 1. Resumen de módulos

| Módulo | v18 | v19 | Notas |
|--------|-----|-----|-------|
| report_xlsx | ✓ | ✓ | Estructura igual; v19 sin carpeta readme/ (no afecta funcionalidad) |
| product_suppiles | ✓ | ✓ | v19 con dependencia `uom` (igual que v18). Vistas adaptadas a Odoo 19 (notebook, inventory_group). |
| product_suppiles_partner | ✓ | ✓ | Alineado |
| subscription_nocount | ✓ | ✓ | v19 tiene `pricelist_views.xml` comentado (modelo sale.subscription.pricing no existe en enterprise 19). |
| subscription_licenses | ✓ | ✓ | Constraints y manifest ya migrados |
| calculadora_costos | ✓ | ✓ | Alineado |
| auto_link_components | ✓ | ✓ | Alineado |
| custom_u | ✓ | ✓ | **Corregido:** añadida regla de acceso para `lot.location.report.wizard` |
| mesa_ayuda_inventario | ✓ | ✓ | Requiere **Enterprise**: helpdesk, sign; repair puede ser community. |
| crm_sales_supplies | ✓ | ✓ | **Corregido:** `_compute_has_sale_order` para evitar ValueError en purchase.order. |
| inventory_dashboard_simple | ✓ | ✓ | Alineado; depende de mesa_ayuda_inventario |
| warehouse_auto_create | ✓ | ✓ | Alineado |
| lot_location_report | ✓ | ✓ | Alineado |
| partner_relationship_report | ✓ | ✓ | Alineado |
| dian_nit_colombia | ✓ | ✓ | Alineado |
| easy_permissions_manager | ✓ | ✓ | Alineado |
| select_all_routes | ✓ | ✓ | Alineado |
| stock_product_transfer | ✓ | ✓ | Alineado |
| mass_routes_manager | ✓ | ✓ | Alineado |
| stock_picking_type_custom | ✓ | ✓ | Alineado |

---

## 2. Dependencias de módulos nativos (Enterprise 19)

Para que los custom funcionen igual que en 18, en la instancia Odoo 19 deben estar instalados:

| Módulo custom | Dependencias que suelen venir de **Enterprise** |
|---------------|---------------------------------------------------|
| mesa_ayuda_inventario | **helpdesk**, **sign** (repair puede estar en community según versión) |
| subscription_nocount / subscription_licenses | **sale_subscription** |

En `enterprise-19.0` existen:
- `helpdesk` (y variantes helpdesk_repair, helpdesk_sale, etc.)
- `sign`
- `sale_subscription`

Asegúrate de tener la ruta de addons de **enterprise-19.0** en la configuración de Odoo 19 y de instalar esos módulos cuando uses mesa_ayuda_inventario y suscripciones.

---

## 3. Cambios ya aplicados en v19

- **Constraints:** Migración de `_sql_constraints` a `models.Constraint` (y en un caso a `@api.constrains`) en los módulos que lo tenían.
- **crm_sales_supplies:** Sobrescritura de `_compute_has_sale_order` para que siempre asigne valor y no falle `web_read` en purchase.order.
- **custom_u:** Regla en `security/ir.model.access.csv` para el modelo `lot.location.report.wizard`.
- **subscription_nocount:** `pricelist_views.xml` desactivado en manifest porque el modelo de pricing no existe en sale_subscription 19 como en 18.
- **product_suppiles (vistas):** Herencia desde `stock.view_production_lot_form`; xpath para crear `notebook` si no existe y para `inventory_group` (Odoo 19).

---

## 4. Recomendaciones para que todo funcione igual que en 18

1. **Orden de actualización:** Actualizar los módulos en este orden (según dependencias):  
   report_xlsx → product_suppiles → … → inventory_dashboard_simple (ver lista completa en conversaciones anteriores).

2. **Enterprise:** Tener **enterprise-19.0** en addons path e instalar: `helpdesk`, `sign`, `sale_subscription` (y `repair` si no está en community).

3. **Caché y assets:** Tras actualizar, reiniciar workers HTTP (`odoosh-restart http` en Odoo.sh) y, si algo no se ve igual, limpiar caché del navegador o regenerar assets.

4. **Traducciones:** Los avisos "no translation for language es_CO" son informativos; opcional añadir traducciones en `i18n/` si quieres etiquetas en es_CO.

5. **Warnings "Two fields have the same label":** Opcional; se pueden reducir cambiando el `string` de uno de los dos campos en los módulos indicados en los logs (subscription_licenses, subscription_nocount, mesa_ayuda_inventario).

6. **Studio:** Los mensajes "Model studio.* is declared but cannot be loaded" son restos en base de datos; no afectan a estos módulos. Se pueden ignorar o limpiar en BD si ya no usas Studio.

---

## 5. Checklist rápida (vistas, tema, reportes)

- [ ] **Vistas:** Formularios de stock.lot, purchase.order, sale.order, helpdesk, etc. se abren sin error y muestran los mismos campos que en 18.
- [ ] **Tema/estilos:** CSS en `web.assets_backend` (product_suppiles, crm_sales_supplies, mesa_ayuda_inventario, inventory_dashboard_simple, subscription_nocount) cargan; si no, revisar ruta de assets y reiniciar.
- [ ] **Reportes:** Reportes en QWeb/PDF y Excel (report_xlsx, lot_location_report, custom_u, mesa_ayuda_inventario) se generan correctamente.
- [ ] **Menús y acciones:** Menús y botones (Inventario Kanban, Compras, CRM, Mesa de Ayuda, etc.) llevan a las vistas correctas.
- [ ] **Campos computados y permisos:** No aparecen "Compute method failed to assign" ni errores de acceso a modelos (ir.model.access cubierto para wizards/transient que uses).

Si algo concreto no se ve o no funciona como en 18, indica módulo y pantalla y se puede revisar el XML o el modelo correspondiente.
