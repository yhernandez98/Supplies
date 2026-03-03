# Vista formulario Número de serie/lote (stock.lot) – dependencias

Vista base: **product_suppiles.view_production_lot_form_inherit_supplies**  
Hereda de: `stock.view_production_lot_form`.

Para que **ningún módulo** que herede esta vista tenga error de validación (“no se puede localizar en la vista principal”), la vista de product_suppiles debe definir **todos** los nodos/campos que esos módulos usan en sus xpath.

## Módulos que heredan de esta vista

| Módulo | XPath que usa | Qué debe existir en la vista supplies |
|--------|----------------|---------------------------------------|
| **product_suppiles_partner** | `//field[@name='entry_date']` position="before" | Campo `entry_date` en el formulario |
| **subscription_nocount** | `//sheet` before; `//field[@name='location_id']` after | `sheet` y campo `location_id` (vista base stock) |
| **mesa_ayuda_inventario** | `//field[@name='location_id']` before; `//sheet/notebook` inside | `location_id` (base); **notebook** dentro de `sheet` |
| **subscription_licenses** | `//page[@name='info_group']/notebook` inside | Página `info_group` con un **notebook** dentro |
| **auto_link_components** | `//page[@name='supplies_components']` inside | Página `supplies_components` |

## Contenido actual de la vista (product_suppiles)

- **Campos** (después de `ref`): `inventory_plate`, `entry_date`.
- **Estructura** (dentro de `//sheet`):
  - Un **notebook** con:
    - Página `info_group` (Información) con un notebook vacío (para subscription_licenses).
    - Página `supplies_components` (Elementos Asociados) vacía (para auto_link_components y futuras extensiones).

Con esto se evita el error de validación en todos los módulos listados.

## Módulo que hereda de la vista base (no de supplies)

- **inventory_dashboard_simple**: hereda de `stock.view_production_lot_form` y solo usa `//field[@name='ref']` (replace). No depende de la vista supplies.

## Si añades más herencias

Al crear una vista que herede de `view_production_lot_form_inherit_supplies`, usa solo xpath sobre:

- Campos que ya están en la vista: `ref`, `inventory_plate`, `entry_date`, y los de la vista base (`name`, `product_id`, `location_id`, etc.).
- Nodos que ya existen: `//sheet`, `//sheet/notebook`, `//page[@name='info_group']`, `//page[@name='info_group']/notebook`, `//page[@name='supplies_components']`.

Si necesitas un nuevo nodo (p. ej. otra página o campo), añádelo primero en `stock_lot_form_supplies_inherit.xml` y luego úsalo en el módulo que hereda.
