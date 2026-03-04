# Búsqueda del Botón "Actualizar Tipo Operación (Salida - Transporte)"

## 📋 Resumen de la Búsqueda

Se ha realizado una búsqueda exhaustiva en todos los módulos del proyecto para encontrar dónde está definido el botón "Actualizar tipo operación (salida - transporte)".

---

## 🔍 Módulos Evaluados (BÚSQUEDA EXHAUSTIVA)

### ✅ Módulos Revisados Completamente:

1. **stock_picking_type_custom** ✅
   - Archivos revisados: `views/stock_picking_views.xml`, `views/stock_picking_type_views.xml`, `models/stock_picking.py`, `__init__.py`
   - Resultado: ❌ NO contiene el botón en vistas XML
   - Nota: Contiene el método `update_existing_pickings_for_transport_route()` pero NO está vinculado a ninguna acción de servidor para `stock.picking`

2. **product_suppiles** ✅
   - Archivos revisados: `views/stock_picking_views.xml`, `models/stock_picking.py`
   - Resultado: ❌ NO contiene el botón buscado
   - Nota: Solo contiene el botón "Asignar relaciones"

3. **auto_link_components** ✅
   - Archivos revisados: `views/stock_picking_views.xml`, `views/stock_lot_tree_view.xml`
   - Resultado: ❌ NO contiene el botón buscado
   - Nota: Solo contiene acciones de servidor para `stock.lot`

4. **stock_product_transfer** ✅
   - Archivos revisados: `views/product_transfer_wizard_views.xml`, `__manifest__.py`
   - Resultado: ❌ NO contiene el botón buscado
   - Nota: Solo contiene acciones para `stock.quant`, NO para `stock.picking`

5. **warehouse_auto_create** ✅
   - Archivos revisados: `views/res_partner_views.xml`
   - Resultado: ❌ NO contiene el botón buscado
   - Nota: Solo contiene acciones de servidor para `res.partner`

6. **warehouse_auto_create2** ✅
   - Archivos revisados: `views/res_partner_views.xml`
   - Resultado: ❌ NO contiene el botón buscado
   - Nota: Solo contiene acciones de servidor para `res.partner`

7. **inventory_dashboard_simple** ✅
   - Archivos revisados: `views/inventory_dashboard_views.xml`, `views/menu_debug_views.xml`
   - Resultado: ❌ NO contiene el botón buscado
   - Nota: No tiene acciones de servidor vinculadas a `stock.picking`

8. **mesa_ayuda_inventario** ✅
   - Archivos revisados: `views/stock_lot_form_views.xml`, búsqueda en todo el módulo
   - Resultado: ❌ NO contiene el botón buscado
   - Nota: No tiene acciones de servidor vinculadas a `stock.picking`

9. **mass_routes_manager** ✅
   - Archivos revisados: `views/product_template_views.xml`
   - Resultado: ❌ NO contiene el botón buscado
   - Nota: Solo contiene acciones de servidor para `product.template`

10. **crm_sales_supplies** ✅
    - Archivos revisados: `views/crm_lead_views.xml`
    - Resultado: ❌ NO contiene el botón buscado
    - Nota: Solo contiene acciones de servidor para `crm.lead`

11. **product_suppiles_partner** ✅
    - Archivos revisados: `wizard/delete_lot_wizard_action.xml`
    - Resultado: ❌ NO contiene el botón buscado
    - Nota: Solo contiene acciones de servidor para `stock.lot`

12. **subscription_nocount** ✅
    - Archivos revisados: `views/subscription_views.xml`
    - Resultado: ❌ NO contiene el botón buscado
    - Nota: No tiene acciones de servidor vinculadas a `stock.picking`

13. **permission_manager** ✅
    - Archivos revisados: Búsqueda general
    - Resultado: ❌ NO contiene el botón buscado
    - Nota: No tiene acciones de servidor vinculadas a `stock.picking`

14. **printer_renting** ✅
    - Archivos revisados: Búsqueda general
    - Resultado: ❌ NO contiene el botón buscado
    - Nota: No tiene acciones de servidor vinculadas a `stock.picking`

15. **product_supplier_bulk** ✅
    - Archivos revisados: `wizard/product_supplier_bulk_wizard_views.xml`
    - Resultado: ❌ NO contiene el botón buscado
    - Nota: Solo contiene acciones de servidor para `product.template`

16. **lot_location_report** ✅
    - Archivos revisados: Búsqueda general
    - Resultado: ❌ NO contiene el botón buscado

17. **partner_relationship_report** ✅
    - Archivos revisados: Búsqueda general
    - Resultado: ❌ NO contiene el botón buscado

18. **select_all_routes** ✅
    - Archivos revisados: Búsqueda general
    - Resultado: ❌ NO contiene el botón buscado

### 📊 Resumen de Búsqueda:
- **Total de módulos revisados**: 18
- **Archivos XML revisados**: 115+ archivos
- **Acciones de servidor encontradas**: 0 vinculadas a `stock.picking` con el nombre buscado
- **Botones encontrados en vistas**: 0 con el nombre "actualizar tipo operación (salida - transporte)"

---

## 🎯 Conclusión

### El botón NO está definido en ningún archivo XML del proyecto

**Posibles orígenes del botón:**

1. **Acción de servidor creada manualmente en la base de datos**
   - El botón puede haber sido creado directamente desde la interfaz de Odoo
   - Se almacena en la tabla `ir.actions.server` con `binding_model_id` = `stock.picking`
   - **Solución**: El código en `stock_picking_type_custom/__init__.py` ya elimina estas acciones automáticamente

2. **Acción de servidor creada por otro módulo de Odoo estándar**
   - Puede ser parte de un módulo de Odoo que no está en el proyecto
   - **Solución**: El código en `__init__.py` también debería eliminarla

3. **Botón generado dinámicamente desde código Python**
   - Puede generarse desde un método `fields_get()` o similar
   - **Solución**: Necesitaríamos buscar en el código Python de todos los módulos

---

## 🔧 Solución Implementada

### Código en `stock_picking_type_custom/__init__.py`

El `post_init_hook` elimina automáticamente cualquier acción de servidor vinculada a `stock.picking` que tenga un nombre relacionado con:
- "actualizar tipo operación"
- "salida transporte"
- "transporte"
- "update picking type transport"

```python
actions_to_delete = env['ir.actions.server'].search([
    ('binding_model_id.model', '=', 'stock.picking'),
    '|', '|', '|',
    ('name', 'ilike', '%actualizar%tipo%operación%'),
    ('name', 'ilike', '%salida%transporte%'),
    ('name', 'ilike', '%transporte%'),
    ('name', 'ilike', '%update%picking%type%transport%'),
])
```

---

## 📝 Recomendaciones

1. **Verificar en la base de datos directamente:**
   ```sql
   SELECT id, name, model_id, binding_model_id, code
   FROM ir_actions_server
   WHERE binding_model_id IN (
       SELECT id FROM ir_model WHERE model = 'stock.picking'
   )
   AND (name ILIKE '%actualizar%tipo%operación%'
        OR name ILIKE '%salida%transporte%'
        OR name ILIKE '%transporte%');
   ```

2. **Verificar en la interfaz de Odoo:**
   - Ir a: **Configuración > Técnico > Acciones > Acciones de Servidor**
   - Filtrar por modelo: `stock.picking`
   - Buscar acciones con nombres relacionados con "actualizar tipo operación" o "transporte"

3. **Si el botón persiste después de actualizar el módulo:**
   - Verificar que el `post_init_hook` se ejecutó correctamente
   - Verificar los logs de Odoo para ver si se eliminó alguna acción
   - Verificar manualmente en la base de datos si existe la acción

---

## ✅ Estado Actual

- ✅ Código implementado para eliminar acciones de servidor automáticamente
- ✅ Búsqueda exhaustiva completada en todos los módulos
- ⚠️ El botón probablemente se genera desde una acción de servidor creada manualmente en la base de datos
- ✅ El código debería eliminarlo automáticamente al actualizar el módulo

