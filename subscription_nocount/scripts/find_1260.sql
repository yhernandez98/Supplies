-- =============================================================================
-- Descubrir QUÉ es el registro con ID 1260 (o qué lo referencia)
-- Ejecutar en la base de datos de Odoo (PostgreSQL).
-- =============================================================================

-- 1) ¿Existe un menú con id 1260?
SELECT 'ir_ui_menu' AS tabla, id, name, parent_id FROM ir_ui_menu WHERE id = 1260;

-- 2) ¿Existe un módulo (aplicación) con id 1260?
SELECT 'ir_module_module' AS tabla, id, name, state FROM ir_module_module WHERE id = 1260;

-- 3) ¿Existe una acción con id 1260?
SELECT 'ir_actions_act_window' AS tabla, id, name FROM ir_actions_act_window WHERE id = 1260;

-- 4) ¿Algún menú tiene parent_id = 1260?
SELECT id, name, parent_id FROM ir_ui_menu WHERE parent_id = 1260;

-- 5) ¿Alguna acción de ventana referencia 1260?
SELECT id, name, res_id FROM ir_actions_act_window WHERE id = 1260 OR res_id = 1260;

-- 6) Favoritos / accesos directos de usuarios (buscar 1260 en datos serializados)
SELECT id, login, name FROM res_users WHERE id IN (
    SELECT user_id FROM ir_model_data WHERE res_id = 1260
) OR id IN (SELECT uid FROM res_groups WHERE id = 1260);

-- 7) ir_model_data: ¿qué XML ID tiene el recurso 1260?
SELECT model, module, name, res_id FROM ir_model_data WHERE res_id = 1260;
