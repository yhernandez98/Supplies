-- Script SQL para forzar actualización del icono
-- Ejecuta estos comandos en orden en tu base de datos PostgreSQL

-- 1. Limpiar caché de assets relacionados
DELETE FROM ir_attachment 
WHERE res_model = 'ir.module.module' 
AND res_id = (SELECT id FROM ir_module_module WHERE name = 'mesa_ayuda_inventario');

-- 2. Forzar actualización del módulo con timestamp
UPDATE ir_module_module 
SET icon = 'static/description/icon.png',
    write_date = NOW(),
    state = 'installed'
WHERE name = 'mesa_ayuda_inventario';

-- 3. Verificar que se actualizó
SELECT name, icon, write_date, state 
FROM ir_module_module 
WHERE name = 'mesa_ayuda_inventario';

-- 4. Limpiar caché de vistas (opcional pero recomendado)
DELETE FROM ir_attachment WHERE res_model = 'ir.ui.view';

