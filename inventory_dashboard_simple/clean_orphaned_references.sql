-- Script SQL para eliminar referencias internas huérfanas (sin producto válido)
-- Ejecutar desde pgAdmin o psql después de hacer un respaldo

-- PASO 1: Verificar cuántas referencias huérfanas hay
SELECT 
    COUNT(*) as total_orphaned,
    COUNT(CASE WHEN product_id IS NULL THEN 1 END) as sin_producto,
    COUNT(CASE WHEN product_id IS NOT NULL THEN 1 END) as con_producto_invalido
FROM internal_reference ir
WHERE ir.product_id IS NULL 
   OR NOT EXISTS (
       SELECT 1 FROM product_product pp 
       WHERE pp.id = ir.product_id
   );

-- PASO 2: Ver las referencias que se van a eliminar (OPCIONAL - para revisar antes de eliminar)
SELECT 
    ir.id,
    ir.name as referencia,
    ir.product_id,
    pp.name as producto_nombre
FROM internal_reference ir
LEFT JOIN product_product pp ON pp.id = ir.product_id
WHERE ir.product_id IS NULL 
   OR pp.id IS NULL;

-- PASO 3: ELIMINAR las referencias huérfanas (EJECUTAR SOLO DESPUÉS DE VERIFICAR)
-- ⚠️ ADVERTENCIA: Esta operación es IRREVERSIBLE. Hacer respaldo antes de ejecutar.
DELETE FROM internal_reference
WHERE product_id IS NULL 
   OR NOT EXISTS (
       SELECT 1 FROM product_product pp 
       WHERE pp.id = internal_reference.product_id
   );

-- PASO 4: Verificar que se eliminaron correctamente
SELECT COUNT(*) as referencias_restantes
FROM internal_reference;

