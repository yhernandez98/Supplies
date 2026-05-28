-- =============================================================================
-- EMERGENCIA: Odoo no arranca con mesa_ayuda_inventario instalado
-- Ejecutar en PostgreSQL ANTES de iniciar Odoo (reemplaza NOMBRE_BASE):
--
--   psql -U odoo -d NOMBRE_BASE -f emergency_fix_mesa_registry.sql
--
-- Causa habitual: vistas en ir_ui_view referencian mesa_ticket_detail_html o
-- atributos de description de versiones 124-127, pero el Python ya no declara
-- el campo (o redefinió description).
-- =============================================================================

-- 1) Limpiar referencias rotas en vistas de helpdesk.ticket
UPDATE ir_ui_view
SET arch_db = regexp_replace(
    regexp_replace(
        regexp_replace(
            regexp_replace(arch_db::text,
                '<attribute\s+name="invisible">mesa_ticket_detail_html</attribute>', '', 'gi'),
            '<field[^>]*name="mesa_ticket_detail_html"[^>]*/>', '', 'gi'),
        '<group[^>]*string="Detalle del retiro"[^>]*>[\s\S]*?</group>', '', 'gi'),
    '<attribute\s+name="options">\{''style-inline'':\s*''true''\}</attribute>', '', 'gi'
)
WHERE model = 'helpdesk.ticket'
  AND arch_db IS NOT NULL
  AND arch_db::text ILIKE '%mesa_ticket_detail_html%';

-- 2) (Opcional) Si sigue caído: desactivar solo el módulo hasta subir código 131+
-- UPDATE ir_module_module SET state = 'to upgrade' WHERE name = 'mesa_ayuda_inventario';
-- COMMIT;
