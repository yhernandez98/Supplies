-- Script SQL para eliminar la vista problemática manualmente
-- Ejecutar este script en la base de datos de Odoo ANTES de actualizar el módulo subscription_licenses

-- Eliminar la vista problemática con xpath obsoleto
DELETE FROM ir_ui_view 
WHERE name = 'subscription.subscription.form.license.integration' 
AND model = 'subscription.subscription';

-- Eliminar el registro de ir_model_data si existe
DELETE FROM ir_model_data 
WHERE module = 'subscription_licenses' 
AND name = 'view_subscription_subscription_form_license_integration';
