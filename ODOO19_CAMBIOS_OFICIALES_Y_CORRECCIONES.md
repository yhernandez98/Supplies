# Odoo 19 – Cambios oficiales y correcciones en los 20 módulos

Documentación basada en la documentación oficial de Odoo 19 y el changelog del ORM.

---

## 1. Cambios oficiales Odoo 19 (documentación y changelog)

### 1.1 Deprecaciones ORM (Changelog 19.0)

| Antes (deprecado) | Usar en Odoo 19 |
|-------------------|------------------|
| `record._context` | `record.env.context` |
| `record._cr` | `record.env.cr` |
| `record._uid` | `record.env.uid` |
| `odoo.osv` (p. ej. `expression.AND`) | `odoo.fields.Domain` y operador `&` |

**Fuente:** [Changelog ORM 19.0](https://www.odoo.com/documentation/19.0/developer/reference/backend/orm/changelog.html) – Deprecated `record._cr`, `record._context`, `record._uid` (#193636); Deprecated `odoo.osv` (#217708).

### 1.2 Dominios (18.1 / 19)

- **Odoo 18.1:** Nueva API `odoo.domain` y `odoo.Domain` para manipulación de dominios.
- **Odoo 19:** En código Python usar `fields.Domain(dominio)` y `&` / `|` para combinar; evitar `from odoo.osv import expression` y `expression.AND()` / `expression.OR()`.

**Ejemplo:**

```python
# Antes (deprecado)
from odoo.osv import expression
domain = expression.AND([domain or [], scope])

# Odoo 19
domain = (fields.Domain(domain or []) & fields.Domain(scope))
```

### 1.3 Vistas de búsqueda (Search view)

- En Odoo 19 **no se recomienda** usar `<group expand="0" string="...">` en la vista de búsqueda.
- Usar `<separator string="Agrupar por"/>` seguido de `<group>` con los filtros de agrupación.

**Fuente:** Documentación y foros Odoo 19 sobre search view.

### 1.4 Método `_search`

- La firma de `_search` ya **no debe incluir** el parámetro `access_rights_uid`; usar `**kwargs` y pasarlos al `super()._search(...)`.

### 1.5 Vista de formulario (form)

- Estructura típica: `<form>` > `<sheet>` > (grupos, etc.) y, si hay pestañas, `<notebook>` > `<page>`.
- En la vista estándar de **stock.lot** en Odoo 19 **no hay** `<notebook>` en la vista base; el `<sheet>` tiene `<group name="main_group">` y `<group name="description">`.
- Para añadir pestañas hay que insertar un `<notebook>` (por ejemplo después del último `<group>` del `<sheet>`) y luego añadir `<page>` dentro.

### 1.6 Campos computados (store / compute_sudo)

- Si varios campos comparten el mismo método `compute` pero tienen distinto `store` o distinto `compute_sudo`, Odoo 19 puede mostrar avisos de inconsistencia.
- Solución: mismo `store` y `compute_sudo` para esos campos, o métodos `compute` distintos (o un campo `related` al almacenado).

### 1.7 Modelos transientes y `_order`

- No usar en `_order` campos que no estén almacenados (`store=False`), porque el orden se traduce a SQL.
- Usar solo campos almacenados o el campo `id`.

### 1.8 Stock: `move_ids` / `move_line_ids`

- En versiones recientes el modelo de stock puede exponer `move_ids` / `move_line_ids` en lugar de (o además de) `move_ids_without_package` / `move_line_ids_without_package`.
- En módulos que deban funcionar en 18 y 19 conviene usar algo como:  
  `getattr(picking, 'move_ids_without_package', None) or picking.move_ids`.

---

## 2. Correcciones ya aplicadas en tus 20 módulos

| Módulo | Cambio aplicado (según doc Odoo 19) |
|--------|--------------------------------------|
| **product_suppiles** | `self._context` → `self.env.context` (wizard, stock_lot_supply_line). Helpers para move_ids_without_package / move_ids. Notebook en formulario de lote: xpath `//sheet/group[last()]` position="after" para insertar `<notebook/>`. |
| **mesa_ayuda_inventario** | `expression.AND` → `fields.Domain` en read_group y _search (customer_inventory_lot). Eliminado import `odoo.osv.expression`. Prioridad 16 en vista que añade pestañas de mantenimiento. |
| **crm_sales_supplies** | `_search` sin `access_rights_uid`. `self._context` → `self.env.context` en stock_quant. Helper para move_ids_without_package. |
| **inventory_dashboard_simple** | display_location_id / display_contact_id: mismo store y compute_sudo. product.relation.search: _order='id' (campo almacenado). Vista product_relation_search: default_order="id". |
| **subscription_nocount** | daily_rate con store=True (consistente con days_open). |
| **subscription_licenses** | license_display_name como related de license_display_name_stored (mismo valor, sin inconsistencia store/compute_sudo). |
| **calculadora_costos** | Vistas de búsqueda: uso de `<separator string="Agrupar por"/>` y `<group>` (evitar expand="0" en group). |
| **auto_link_components** | getattr para move_ids_without_package / move_ids. |
| **stock_product_transfer** | getattr para move_line_ids_without_package / move_line_ids. |
| **stock_picking_type_custom** | Helper _get_moves_without_package() y uso consistente. |
| **custom_u** | Manifest actualizado a Odoo 19.0. |

---

## 3. Referencias oficiales

- [Changelog ORM 19.0](https://www.odoo.com/documentation/19.0/developer/reference/backend/orm/changelog.html)
- [View architectures 19.0](https://www.odoo.com/documentation/19.0/developer/reference/user_interface/view_architectures.html)
- [Upgrade Odoo 19](https://www.odoo.com/documentation/19.0/administration/upgrade.html)
- [Odoo 19 Release Notes](https://www.odoo.com/odoo-19-release-notes)

---

## 4. Si algo sigue fallando

1. **Actualizar módulos** con `-u nombre_modulo` (o desde Apps).
2. **Revisar el log** del servidor al cargar/actualizar por errores de vista (XML) o de modelo (campos, _order, compute).
3. **Vistas:** En Ajustes → Técnico → Vistas, comprobar que la vista heredada tenga en su “Arch” el resultado esperado (p. ej. que exista `<notebook>` con `<page>` si se añadieron pestañas).
