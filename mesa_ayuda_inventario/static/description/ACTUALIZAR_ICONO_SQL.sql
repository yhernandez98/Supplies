-- Script SQL para actualizar el icono directamente en la base de datos
-- Ejecuta esto en la base de datos de Odoo

-- 1. Verificar el estado actual del módulo
SELECT 
    name, 
    state, 
    icon, 
    latest_version,
    application
FROM ir_module_module 
WHERE name = 'mesa_ayuda_inventario';

-- 2. Actualizar el icono directamente
UPDATE ir_module_module 
SET icon = 'static/description/icon.png'
WHERE name = 'mesa_ayuda_inventario';

-- 3. Verificar que se actualizó
SELECT 
    name, 
    icon 
FROM ir_module_module 
WHERE name = 'mesa_ayuda_inventario';

-- 4. Limpiar caché de módulos (opcional pero recomendado)
DELETE FROM ir_module_module_dependency WHERE name = 'mesa_ayuda_inventario';

