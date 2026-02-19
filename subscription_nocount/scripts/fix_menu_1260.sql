-- =============================================================================
-- Arreglo: "No podemos encontrar los registros con el ID 1260"
-- Ejecutar en la base de datos de Odoo (PostgreSQL) ANTES de actualizar el módulo.
-- Conectarse: psql -U odoo -d NOMBRE_BASE_DATOS
-- =============================================================================

-- 1) Ver menús huérfanos (parent_id apunta a un menú que ya no existe)
SELECT m.id, m.name, m.parent_id
FROM ir_ui_menu m
WHERE m.parent_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM ir_ui_menu p WHERE p.id = m.parent_id);

-- 2) Reasignar TODOS los huérfanos al menú Ventas (sale.menu_sale_root)
UPDATE ir_ui_menu m
SET parent_id = (SELECT im.id FROM ir_ui_menu im
                 JOIN ir_model_data md ON md.model = 'ir.ui.menu' AND md.res_id = im.id
                 WHERE md.module = 'sale' AND md.name = 'menu_sale_root'
                 LIMIT 1)
WHERE m.parent_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM ir_ui_menu p WHERE p.id = m.parent_id);

-- 3) Verificar: no debería devolver filas
SELECT m.id, m.name, m.parent_id
FROM ir_ui_menu m
WHERE m.parent_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM ir_ui_menu p WHERE p.id = m.parent_id);
