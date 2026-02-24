# Análisis de los 20 módulos para Odoo 19

**Pregunta:** ¿Se analizaron todos los 20 módulos en base a la documentación para aplicar cambios y que funcionen?  
**Respuesta:** **Sí.** Cada módulo se revisó según la documentación oficial de Odoo 19 y el changelog; donde había patrones deprecados o incompatibles se aplicaron correcciones.

---

## Criterios de análisis (según documentación Odoo 19)

1. **Deprecaciones ORM:** `_context` → `env.context`; `expression.AND`/`OR` → `fields.Domain` y `&`/`|`.
2. **Vistas de búsqueda:** no usar `<group expand="0" string="...">`; usar `<separator>` + `<group>`.
3. **Método `_search`:** sin parámetro `access_rights_uid`; usar `**kwargs`.
4. **Campos computados:** mismo `store` y `compute_sudo` si comparten método; o métodos distintos / `related`.
5. **Modelos transientes:** `_order` solo con campos almacenados (o `id`).
6. **Stock:** compatibilidad `move_ids_without_package` / `move_line_ids` con `getattr` donde aplique.
7. **Vista formulario lote:** inserción de `<notebook>` para pestañas (xpath según estructura Odoo 19).

---

## Estado por módulo

| # | Módulo | ¿Analizado? | ¿Cambios aplicados? | Detalle |
|---|--------|-------------|---------------------|--------|
| 1 | **calculadora_costos** | Sí | Sí | Search views: `<separator>` + `<group>` (sin `expand="0"`). |
| 2 | **subscription_nocount** | Sí | Sí | `daily_rate` store=True; campos computados consistentes. |
| 3 | **product_suppiles** | Sí | Sí | `_context` → `env.context`; helpers move_ids; notebook en form lote (`//sheet/group[last()]`). |
| 4 | **auto_link_components** | Sí | Sí | `getattr` para move_ids_without_package / move_ids. |
| 5 | **report_xlsx** | Sí | No | Sin uso de _context, expression, _search, move_ids ni search expand. Compatible sin cambios. |
| 6 | **subscription_licenses** | Sí | Sí | `license_display_name` como related de `license_display_name_stored`. |
| 7 | **warehouse_auto_create** | Sí | No | Solo res.partner y stock.warehouse. Sin patrones a corregir. |
| 8 | **partner_relationship_report** | Sí | No | Reporte Excel y wizard. Sin patrones a corregir. |
| 9 | **lot_location_report** | Sí | No | Wizard y vistas. Sin _search, expression ni move_ids. |
| 10 | **dian_nit_colombia** | Sí | No | Hereda res.partner. Sin patrones a corregir. |
| 11 | **inventory_dashboard_simple** | Sí | Sí | display_location_id/display_contact_id store+compute_sudo; _order y default_order en product_relation_search. |
| 12 | **custom_u** | Sí | Sí | Manifest descripción "Odoo 19.0". |
| 13 | **easy_permissions_manager** | Sí | No | Permisos y grupos. Sin patrones a corregir. |
| 14 | **select_all_routes** | Sí | No | Vista heredada producto. Sin move_ids ni search expand. |
| 15 | **stock_product_transfer** | Sí | Sí | `getattr` para move_line_ids_without_package / move_line_ids. |
| 16 | **crm_sales_supplies** | Sí | Sí | `_search` sin access_rights_uid; `_context` → `env.context`; helper move_ids. |
| 17 | **mass_routes_manager** | Sí | No | Acciones sobre product.template. Sin patrones a corregir. |
| 18 | **stock_picking_type_custom** | Sí | Sí | Helper _get_moves_without_package() y uso en el módulo. |
| 19 | **product_suppiles_partner** | Sí | No | Hereda vistas de product_suppiles y base. Sin código a adaptar. |
| 20 | **mesa_ayuda_inventario** | Sí | Sí | `expression.AND` → `fields.Domain`; prioridad vista pestañas; xpath imagen/botón lote. |

---

## Resumen numérico

- **Analizados:** 20/20.
- **Con cambios aplicados (para que funcionen en 19):** 11 módulos.
- **Sin cambios necesarios (ya compatibles):** 9 módulos.

Las correcciones se basan en el [Changelog ORM 19.0](https://www.odoo.com/documentation/19.0/developer/reference/backend/orm/changelog.html), la documentación de [View architectures](https://www.odoo.com/documentation/19.0/developer/reference/user_interface/view_architectures.html) y buenas prácticas para search views y stock en Odoo 19.
