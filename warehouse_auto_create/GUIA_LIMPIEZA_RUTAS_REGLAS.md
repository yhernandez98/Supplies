# Guía: Limpieza de Rutas, Reglas y Tipos de Operación No Utilizados

## ⚠️ ADVERTENCIAS IMPORTANTES

**ANTES DE ELIMINAR CUALQUIER DATO:**

1. **Haz un backup completo de la base de datos**
2. **Verifica qué está en uso** antes de eliminar
3. **Elimina primero las reglas**, luego las rutas, y por último los tipos de operación
4. **Nunca elimines tipos de operación** que estén asociados a almacenes activos
5. **Prueba en un ambiente de desarrollo** primero

## 📋 Estrategia Recomendada

### Opción 1: Limpieza Manual (Recomendada para empezar)

#### Paso 1: Identificar Rutas No Utilizadas

1. Ve a: **Inventario → Configuración → Rutas**
2. Filtra por: `name like 'SUPP_ALISTAMIENTO_SALIDA_TRANSPORTE_%'`
3. Para cada ruta, verifica:
   - ¿Tiene reglas asociadas?
   - ¿Está asignada a algún producto?
   - ¿Está en alguna orden de venta?

#### Paso 2: Eliminar Reglas de Rutas No Utilizadas

1. Ve a: **Inventario → Configuración → Reglas de Reabastecimiento**
2. Filtra por rutas que quieres eliminar
3. Elimina las reglas una por una (o en lote si estás seguro)

#### Paso 3: Eliminar Rutas

1. Después de eliminar las reglas, elimina las rutas
2. Verifica que no haya referencias pendientes

#### Paso 4: Verificar Tipos de Operación

1. Ve a: **Inventario → Configuración → Tipos de Operación**
2. Para cada tipo, verifica:
   - ¿Está asociado a algún almacén?
   - ¿Tiene movimientos de stock asociados?
   - ¿Está en uso en algún picking?

### Opción 2: Limpieza Automática con Wizard (Más Segura)

Usa el wizard que se creará en el módulo para hacer la limpieza de forma segura.

## 🔍 Qué Verificar Antes de Eliminar

### Para Rutas:
- ✅ No debe estar asignada a ningún producto (`product.route_ids`)
- ✅ No debe estar en ninguna orden de venta (`sale.order.route_id`)
- ✅ No debe tener reglas activas (o las reglas deben eliminarse primero)
- ✅ No debe estar asociada a ningún almacén (`stock.warehouse.route_ids`)

### Para Reglas:
- ✅ No debe tener movimientos de stock pendientes
- ✅ No debe estar en ninguna orden de compra
- ✅ La ruta asociada debe estar marcada para eliminación

### Para Tipos de Operación:
- ✅ No debe estar asociado a ningún almacén (`warehouse.in_type_id`, `warehouse.out_type_id`, etc.)
- ✅ No debe tener pickings activos o en proceso
- ✅ No debe tener movimientos de stock asociados

## 🛠️ Script SQL para Identificar (Solo Consulta)

```sql
-- Rutas sin reglas
SELECT r.id, r.name, r.company_id
FROM stock_route r
LEFT JOIN stock_rule sr ON sr.route_id = r.id
WHERE r.name LIKE 'SUPP_ALISTAMIENTO_SALIDA_TRANSPORTE_%'
AND sr.id IS NULL;

-- Rutas sin productos asignados
SELECT r.id, r.name
FROM stock_route r
LEFT JOIN product_route_rel prr ON prr.route_id = r.id
WHERE r.name LIKE 'SUPP_ALISTAMIENTO_SALIDA_TRANSPORTE_%'
AND prr.product_template_id IS NULL;

-- Tipos de operación sin almacenes asociados
SELECT pt.id, pt.name, pt.company_id
FROM stock_picking_type pt
LEFT JOIN stock_warehouse w1 ON w1.in_type_id = pt.id
LEFT JOIN stock_warehouse w2 ON w2.out_type_id = pt.id
LEFT JOIN stock_warehouse w3 ON w3.pick_type_id = pt.id
LEFT JOIN stock_warehouse w4 ON w4.pack_type_id = pt.id
WHERE pt.company_id = 1
AND w1.id IS NULL
AND w2.id IS NULL
AND w3.id IS NULL
AND w4.id IS NULL;
```

## ⚡ Mejores Prácticas

1. **Elimina en orden inverso a la creación:**
   - Primero: Reglas de stock
   - Segundo: Rutas
   - Tercero: Tipos de operación (solo si no están en uso)

2. **Usa el modo de prueba primero:**
   - Marca como inactivo (`active = False`) antes de eliminar
   - Espera unos días para verificar que no hay problemas
   - Luego elimina definitivamente

3. **Documenta lo que eliminas:**
   - Guarda una lista de IDs eliminados
   - Anota la fecha y razón de eliminación

4. **No elimines tipos de operación del sistema:**
   - Los tipos estándar de Odoo deben mantenerse
   - Solo elimina tipos personalizados que creaste

## 🚨 Qué NO Eliminar

- ❌ Tipos de operación asociados a almacenes activos
- ❌ Rutas que están en órdenes de venta pendientes
- ❌ Reglas que tienen movimientos de stock asociados
- ❌ Tipos de operación del almacén principal
- ❌ Rutas que están en productos activos

## 📝 Checklist Antes de Eliminar

- [ ] Backup de base de datos realizado
- [ ] Verificado que las rutas no están en uso
- [ ] Verificado que las reglas no tienen movimientos pendientes
- [ ] Verificado que los tipos de operación no están en almacenes
- [ ] Probado en ambiente de desarrollo
- [ ] Documentado qué se va a eliminar
- [ ] Tiempo de espera después de marcar como inactivo

