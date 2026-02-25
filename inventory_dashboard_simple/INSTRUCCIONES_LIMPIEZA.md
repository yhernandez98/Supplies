# Instrucciones para Limpiar Referencias Internas Huérfanas

Este documento explica cómo eliminar las referencias internas que quedaron guardadas de manera general (sin producto asociado) antes de implementar el filtrado por producto.

## Opción 1: Desde la Interfaz de Odoo (Recomendado)

1. **Actualizar el módulo** `inventory_dashboard_simple` en Odoo
2. Ir a **Inventario > Configuración > Referencias Internas** (o buscar "Referencias Internas" en el menú)
3. En la vista de lista, hacer clic en el menú **"Acción"** (botón de tres puntos o menú contextual)
4. Seleccionar **"Limpiar Referencias Internas Huérfanas"**
5. Se mostrará una notificación indicando cuántas referencias se eliminaron

## Opción 2: Desde la Base de Datos (SQL)

Si prefieres hacerlo directamente desde la base de datos:

1. **Hacer un respaldo de la base de datos** antes de ejecutar cualquier comando
2. Abrir pgAdmin o psql
3. Ejecutar el script `clean_orphaned_references.sql` que está en la carpeta del módulo

### Pasos del Script SQL:

1. **PASO 1**: Verificar cuántas referencias huérfanas hay (solo lectura)
2. **PASO 2**: Ver las referencias que se van a eliminar (opcional, para revisar)
3. **PASO 3**: **ELIMINAR** las referencias huérfanas (⚠️ IRREVERSIBLE)
4. **PASO 4**: Verificar que se eliminaron correctamente

## ¿Qué se considera una referencia huérfana?

- Referencias internas que **no tienen producto asociado** (`product_id IS NULL`)
- Referencias internas cuyo **producto ya no existe** en la base de datos

## Notas Importantes

- ⚠️ **Esta operación es IRREVERSIBLE**. Asegúrate de hacer un respaldo antes.
- Las referencias que tienen un producto válido **NO se eliminarán**
- Después de la limpieza, todas las nuevas referencias internas se asociarán automáticamente al producto correspondiente

## Verificación Post-Limpieza

Después de ejecutar la limpieza, puedes verificar que todo esté correcto:

```sql
-- Ver todas las referencias internas restantes
SELECT 
    ir.id,
    ir.name as referencia,
    pp.name as producto
FROM internal_reference ir
JOIN product_product pp ON pp.id = ir.product_id
ORDER BY pp.name, ir.name;
```

Todas las referencias deberían tener un producto asociado válido.

