-- Script SQL para borrar los datos del campo name antes de la migración
-- Ejecutar esto directamente en la base de datos si quieres borrar los datos

-- Opción 1: Poner NULL en el campo name (recomendado si quieres conservar los registros)
UPDATE license_template SET name = NULL WHERE name IS NOT NULL;

-- Opción 2: Si quieres borrar completamente los registros que tienen name (CUIDADO: esto borra registros completos)
-- DELETE FROM license_template WHERE name IS NOT NULL;

-- Verificar que quedó vacío
SELECT COUNT(*) FROM license_template WHERE name IS NOT NULL;
