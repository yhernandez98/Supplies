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

Equivalente al formulario de Odoo 18 (todos los campos y pestañas):

- **Antes de `product_id`:** `inventory_plate`, `security_plate`, `hostname`.
- **Después de `ref`:** `model_name`, `billing_code`, `entry_date`, `entry_date_display` (invisible), `exit_date`, `exit_date_display` (invisible).  
  *(product_suppiles_partner inserta "Usuario" antes de `entry_date`.)_
- **Después de `location_id`:** `reining_plazo`, `reining_plazo_custom_months`.
- **Dentro de `//sheet`:** un **notebook** con:
  - Página `info_group` (Información) con notebook vacío (subscription_licenses añade Licenciamiento).
  - Página `supplies_components` (Elementos Asociados) para auto_link_components y listas de componentes.
- **mesa_ayuda_inventario** añade: bloque **foto** (campo `lot_image`) + botón "Generar Hoja de Vida" antes de `location_id`, y las pestañas "Mantenimientos y Revisiones" e "Historial de Componentes" dentro de `//sheet/notebook`. El campo `lot_image` lo define mesa_ayuda en su extensión de `stock.lot`.

**Diseño visual:** La vista aplica la clase `o_stock_lot_pastel_form` al formulario y `o_stock_lot_left_col` / `o_stock_lot_right_col` a las columnas; el CSS `stock_lot_form_pastel.css` del módulo da el estilo tipo Odoo 18.

Con esto se evita el error de validación y el formulario queda como en Odoo 18 (campos, pestañas completas, diseño pastel; la foto depende de tener instalado mesa_ayuda_inventario).

## Módulo que hereda de la vista base (no de supplies)

- **inventory_dashboard_simple**: hereda de `stock.view_production_lot_form` y solo usa `//field[@name='ref']` (replace). No depende de la vista supplies.

## Si añades más herencias

Al crear una vista que herede de `view_production_lot_form_inherit_supplies`, usa solo xpath sobre:

- Campos que ya están en la vista: `ref`, `inventory_plate`, `entry_date`, y los de la vista base (`name`, `product_id`, `location_id`, etc.).
- Nodos que ya existen: `//sheet`, `//sheet/notebook`, `//page[@name='info_group']`, `//page[@name='info_group']/notebook`, `//page[@name='supplies_components']`.

Si necesitas un nuevo nodo (p. ej. otra página o campo), añádelo primero en `stock_lot_form_supplies_inherit.xml` y luego úsalo en el módulo que hereda.
