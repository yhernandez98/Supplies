# Cómo hacer que aparezcan imagen y pestañas en el formulario de lote (Odoo 19)

## Importante: no editar la vista base

La pantalla que viste es la **vista estándar** `stock.production.lot.form` (Vista base). Odoo avisa que **no se debe editar** esa vista: los cambios se pierden en actualizaciones.  
Toda la personalización (imagen, botón "Generar Hoja de Vida", pestañas) está en **vistas heredadas** en los módulos **product_suppiles** y **mesa_ayuda_inventario**. No hace falta tocar la vista base.

---

## Pasos para que vuelva a salir todo

### 1. Subir / desplegar el código actualizado

Asegúrate de que en el servidor Odoo (o Odoo.sh) esté el código de la carpeta **Modulos Odoo 19** con los últimos cambios en:

- `mesa_ayuda_inventario/views/stock_lot_form_views.xml`
- `product_suppiles/views/stock_lot_views.xml`

### 2. Actualizar los módulos en Odoo

Sin actualizar, Odoo sigue usando la versión antigua de las vistas.

1. Activa el **modo desarrollador** (Ajustes → Activar modo desarrollador).
2. Ve a **Aplicaciones**.
3. Quita el filtro "Aplicaciones" para ver también los módulos técnicos.
4. Busca **"Mesa de Ayuda - Inventario de Clientes"** (mesa_ayuda_inventario).
5. Abre el módulo y pulsa **Actualizar**.
6. Busca **"Product Supplies"** (product_suppiles) y pulsa **Actualizar**.
7. Si te pide recargar la lista de aplicaciones, acepta.

### 3. Comprobar que las vistas existen

1. Ve a **Ajustes → Técnico → Vistas**.
2. Filtra por **Modelo** = "Número de serie/lote" (stock.lot).
3. Deberías ver, entre otras:
   - `production.lot.form.maintenance.inherit` (mesa_ayuda_inventario)
   - `production.lot.form.maintenance.notebook.fallback` (mesa_ayuda_inventario)
   - `production.lot.form.supplies.inherit` (product_suppiles)

Si no aparecen, en el menú de Aplicaciones revisa que **mesa_ayuda_inventario** y **product_suppiles** estén instalados y sin errores.

### 4. Revisar errores al cargar vistas

Si después de actualizar sigue sin verse nada:

1. Revisa el **log del servidor** (terminal o logs de Odoo.sh) al abrir un lote/serial.
2. Busca líneas con "Error", "View", "inherit" o "xpath". Un error en una vista heredada puede hacer que no se aplique.
3. Si tienes **stock_account** instalado, la vista `stock_account.view_production_lot_form_stock_account` debe existir; si no, puede fallar la herencia de product_suppiles que la usa.

### 5. Caché del navegador

Después de actualizar los módulos:

- Haz **Ctrl+F5** (o Cmd+Shift+R en Mac) en la pantalla del lote, o  
- Prueba en una ventana de **incógnito**.

---

## Qué se ha dejado en el XML (resumen)

- **mesa_ayuda_inventario:**  
  - La imagen del lote y el botón "Generar Hoja de Vida" se insertan con un xpath que usa el grupo **`inventory_group`** de la vista base que compartiste (Odoo 19).
- **product_suppiles:**  
  - Si la vista base no tiene `<notebook>`, se crea uno y luego se añaden las pestañas (Información, Elementos Asociados, etc.).

Si tras seguir estos pasos sigue sin salir nada, indica si al actualizar los módulos ves algún error en pantalla o en el log del servidor y lo revisamos.
