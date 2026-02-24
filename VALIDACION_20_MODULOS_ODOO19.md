# Validación de los 20 módulos para Odoo 19

Resumen de la revisión de **todos** los módulos en la carpeta "Modulos Odoo 19".

---

## 1. calculadora_costos
- **Versión:** 19.0.1.0.2
- **Revisión:** Vistas de búsqueda con `<separator string="Agrupar por"/>` + `<group>` (sin `expand="0"`). Dominios de `asset_class_id` usan `category_id` de `product.asset.class`, no de uom → OK.
- **Estado:** ✅ Compatible Odoo 19.

---

## 2. subscription_nocount
- **Revisión:** Uso de `sale.subscription.pricing` protegido con `if 'sale.subscription.pricing' in self.env`. Modelo `subscription_pricing` no cargado en `__init__.py`; vista `pricelist_views.xml` comentada en manifest. Search views con `<separator>`.
- **Estado:** ✅ Compatible Odoo 19.

---

## 3. product_suppiles
- **Revisión:** 
  - `stock_picking`: helpers `_get_moves_without_package()` y `_get_move_lines_without_package()`; vistas con xpath para `move_ids_without_package` y `move_ids`.
  - `stock_move_line` y `sale`: uso de `getattr(picking, 'move_ids_without_package', None) or picking.move_ids`.
  - UoM: dominios sin `category_id` en uom.uom.
- **Estado:** ✅ Compatible Odoo 19 (corregido en sesión anterior).

---

## 4. auto_link_components
- **Revisión:** Uso de `getattr(self, 'move_ids_without_package', None) or self.move_ids` en `stock_picking.py`.
- **Estado:** ✅ Compatible Odoo 19 (corregido).

---

## 5. report_xlsx
- **Versión:** 19.0.1.0.1
- **Revisión:** Módulo base OCA; solo `__init__.py`, models, report, controllers. Sin referencias a move_ids_without_package, search views ni _search.
- **Estado:** ✅ Compatible Odoo 19.

---

## 6. subscription_licenses
- **Revisión:** Uso de `sale.subscription.pricing` con `if 'sale.subscription.pricing' in self.env`. `license_type_id` en herencia de `subscription.product.grouped`. Search views con `<separator>`.
- **Estado:** ✅ Compatible Odoo 19.

---

## 7. warehouse_auto_create
- **Versión:** 19.0.1.0.5
- **Revisión:** Solo hereda `res.partner` y crea `stock.warehouse`. Sin move_ids_without_package, sin vistas de búsqueda problemáticas.
- **Estado:** ✅ Compatible Odoo 19.

---

## 8. partner_relationship_report
- **Versión:** 19.0.0.0.1
- **Revisión:** Reporte Excel (report_xlsx), wizard, vistas de menú. Sin stock.picking ni search views con expand.
- **Estado:** ✅ Compatible Odoo 19.

---

## 9. lot_location_report
- **Versión:** 19.0.0.0.1
- **Revisión:** Wizard `lot.location.report.wizard`, vistas. Usa `stock.location`, `product.product`, `stock.lot`. Sin move_ids_without_package ni _search override.
- **Estado:** ✅ Compatible Odoo 19.

---

## 10. dian_nit_colombia
- **Versión:** 19.0.1.0.0
- **Revisión:** Hereda `res.partner` para NIT/DIAN. Sin stock, sin vistas de búsqueda con group expand.
- **Estado:** ✅ Compatible Odoo 19.

---

## 11. inventory_dashboard_simple
- **Versión:** 19.0.0.0.2
- **Revisión:** Kanban con `t-name="card"`; search views con `<separator>`. pre_init_hook y post_init_hook compatibles. Depende de product_suppiles y mesa_ayuda_inventario.
- **Estado:** ✅ Compatible Odoo 19.

---

## 12. custom_u
- **Versión:** 19.0.3.1
- **Revisión:** Descripción actualizada de "Odoo 18.0" a "Odoo 19.0". Contactos y productos; sin stock.picking ni search views problemáticas.
- **Estado:** ✅ Compatible Odoo 19 (descripción actualizada).

---

## 13. easy_permissions_manager
- **Versión:** 19.0.1.0.0
- **Revisión:** Permisos y grupos; usa `res.users.groups_id` (campo estándar). Sin move_ids ni _search override.
- **Estado:** ✅ Compatible Odoo 19.

---

## 14. select_all_routes
- **Revisión:** Vista heredada de `product.product_template_form_view` con botones de rutas. Sin move_ids_without_package.
- **Estado:** ✅ Compatible Odoo 19.

---

## 15. stock_product_transfer
- **Revisión:** Wizard usa `getattr(picking, 'move_line_ids_without_package', None) or picking.move_line_ids` (y análogo para picking_in/picking_out) en todos los puntos donde se validan move lines.
- **Estado:** ✅ Compatible Odoo 19 (corregido).

---

## 16. crm_sales_supplies
- **Revisión:** 
  - `stock_picking`: helper para move_ids_without_package.
  - `stock_quant`: `_search` con `**kwargs`.
  - `purchase_alert`: `_search` con `**kwargs`.
  - Vista de picking con leasing comentada (si se descomenta, en Odoo 19 podría necesitar xpath para `move_ids`).
- **Estado:** ✅ Compatible Odoo 19 (corregido).

---

## 17. mass_routes_manager
- **Revisión:** Acciones servidor sobre `product.template`; `pre_init_hook` vacío. Sin move_ids ni vistas de búsqueda con expand.
- **Estado:** ✅ Compatible Odoo 19.

---

## 18. stock_picking_type_custom
- **Revisión:** `_get_moves_without_package()` y uso en toda la lógica de transporte (write, update_existing_pickings, etc.).
- **Estado:** ✅ Compatible Odoo 19 (corregido).

---

## 19. product_suppiles_partner
- **Versión:** 19.0.1.0.0
- **Revisión:** Hereda vista de `product_suppiles.view_production_lot_form_inherit_supplies` y `base.view_partner_form`. Reportes y wizard. Sin move_ids_without_package.
- **Estado:** ✅ Compatible Odoo 19.

---

## 20. mesa_ayuda_inventario
- **Revisión:** 
  - Formulario de lote: xpath por `//group[.//field[@name='quantity']]` y vista fallback para notebook en Odoo 19.
  - Kanban: `t-name="card"`; sin `kanban_image`.
  - `customer_inventory_lot`: `_search` con `**kwargs`.
  - Search views con `<separator>`; sin `groups_id` en acciones.
- **Estado:** ✅ Compatible Odoo 19 (corregido en sesiones anteriores).

---

## Resumen de correcciones aplicadas en esta validación

| # | Módulo | Corrección |
|---|--------|------------|
| 4 | auto_link_components | Uso de getattr/or para move_ids en stock_picking |
| 15 | stock_product_transfer | Uso de getattr/or para move_line_ids en wizard (varios puntos) |
| 18 | stock_picking_type_custom | _get_moves_without_package() y uso en todo el módulo |
| 3 | product_suppiles | stock_move_line y sale.py con getattr; vista con xpath move_ids |
| 16 | crm_sales_supplies | purchase_alert._search con **kwargs |
| 12 | custom_u | Descripción manifest "Odoo 18.0" → "Odoo 19.0" |

---

## Nota sobre calculadora_costos y expand="0"

En la ruta **"Modulos Odoo 19"** las vistas de búsqueda de calculadora_costos ya tienen `<separator string="Agrupar por"/>` y `<group>` (sin `expand="0"`). Si en otra carpeta (por ejemplo "Modulos Odoo" sin "19") aún aparece `expand="0"`, conviene aplicar allí el mismo cambio: reemplazar  
`<group expand="0" string="Agrupar por">`  
por  
`<separator string="Agrupar por"/>` + `<group>`.

---

**Fecha de validación:** 2025  
**Módulos revisados:** 20/20

---

## Comparación completa v18 vs v19 (todos los módulos)

Se comparó la estructura de los 20 módulos entre:
- **v18:** `C:\Users\yhernandez.SUPPLIESDC\Music\Modulos Odoo`
- **v19:** `C:\Users\yhernandez.SUPPLIESDC\Music\Modulos Odoo 19`

### Resultado de la comparación
- **Manifests (data, depends):** Iguales en los 20 módulos salvo diferencias ya aplicadas (uom en product_suppiles, subscription_pricing/pricelist en subscription_nocount, subscription_product_grouped en subscription_licenses).
- **models/__init__.py:** Misma lista de modelos en todos; v19 tiene subscription_pricing comentado en subscription_nocount y añade subscription_product_grouped en subscription_licenses.
- **Vistas y funcionalidad:** Las mismas vistas y datos existen en v19. Las diferencias son de **compatibilidad con la estructura de vistas de Odoo 19**, no de contenido faltante.

### Ajustes aplicados para igualar funcionalidad en v19

1. **mesa_ayuda_inventario (formulario de lote)**  
   - Imagen del lote y botón "Generar Hoja de Vida" no se mostraban porque en Odoo 19 la vista base usa `product_qty` en lugar de `quantity`.  
   - **Cambio:** xpath actualizados a `//group[.//field[@name='quantity'] or .//field[@name='product_qty']]` para la columna derecha y el bloque de imagen/botón.

2. **product_suppiles (formulario de lote)**  
   - En Odoo 19 la vista estándar de lote no incluye `<notebook>`, por lo que el xpath `//sheet/notebook` no aplicaba y no se veían las pestañas Información, Elementos Asociados, etc.  
   - **Cambio:** Añadido xpath `//sheet[not(notebook)]` que inserta `<notebook/>` cuando no existe, para que el siguiente xpath `//sheet/notebook` inserte las pestañas de product_suppiles. Añadido también xpath de respaldo para `//group[@name='inventory_group']` (clase columna derecha).

Con estos cambios, el formulario de número de serie/lote en v19 debe mostrar las mismas funcionalidades y campos que en v18: imagen del lote, botón "Generar Hoja de Vida", pestañas de product_suppiles (Información, Elementos Asociados, etc.) y pestañas de mesa_ayuda (Mantenimientos y Revisiones, Historial de Componentes).
