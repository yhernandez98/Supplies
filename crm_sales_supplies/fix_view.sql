-- Script SQL para eliminar la vista problemática manualmente
-- Ejecutar este script en la base de datos de Odoo ANTES de actualizar el módulo

-- Eliminar la vista problemática
DELETE FROM ir_ui_view 
WHERE name = 'stock.quant.supplies.form' 
AND model = 'stock.quant';

-- Eliminar el registro de ir_model_data si existe
DELETE FROM ir_model_data 
WHERE module = 'crm_sales_supplies' 
AND name = 'view_supplies_stock_quant_form';

