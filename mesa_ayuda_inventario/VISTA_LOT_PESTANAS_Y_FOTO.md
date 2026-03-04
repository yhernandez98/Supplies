# Pestañas "Mantenimientos y Revisiones" e "Historial de Componentes" + Foto y "Generar Hoja de Vida"

Estos elementos **pertenecen a este módulo** (Mesa de Ayuda - Inventario). Se añaden en la vista `view_production_lot_form_inherit_maintenance` (archivo `views/stock_lot_form_views.xml`).

## Qué aporta esta vista

- **Bloque de foto:** campo `lot_image` y botón **"Generar Hoja de Vida"** (antes del campo Ubicación en el formulario de Número de serie/lote).
- **Pestaña "Mantenimientos y Revisiones":** lista de mantenimientos del equipo (`maintenance_ids`).
- **Pestaña "Historial de Componentes":** texto informativo y botón "Ver Historial Completo de Cambios de Componentes".

## Si no ves las pestañas ni la foto

1. **Comprobar que el módulo está instalado**  
   Aplicaciones → buscar "Mesa de Ayuda" o "Inventario de Clientes" → debe estar instalado.

2. **Actualizar módulos en el orden correcto**  
   - Primero **Product Supplies** (para que exista el notebook en el formulario).  
   - Luego **Mesa de Ayuda - Inventario de Clientes** (para que se añadan las pestañas y el bloque de foto).

3. **Comprobar que la vista está activa**  
   - Ir a **Ajustes → Técnico → Vistas**.  
   - Buscar por nombre de vista: `production.lot.form.maintenance.inherit`  
     o por ID externo: `mesa_ayuda_inventario.view_production_lot_form_inherit_maintenance`.  
   - Si la vista está **inactiva** (toggle en rojo), activarla.  
   - Si al activar aparece un **error de validación**, anotar el mensaje (por ejemplo, "no se puede localizar...") y corregir la vista o sus dependencias.

4. **Limpiar caché del navegador**  
   Después de activar la vista o actualizar el módulo, recargar con Ctrl+F5 o vaciar caché.

## Dependencia

La vista hereda de `product_suppiles.view_production_lot_form_inherit_supplies`.  
Esa vista debe definir `//sheet/notebook` para que esta pueda añadir las dos pestañas dentro del notebook. Si Product Supplies está actualizado con la última versión de la vista, el notebook existe y esta vista puede aplicarse sin error.
