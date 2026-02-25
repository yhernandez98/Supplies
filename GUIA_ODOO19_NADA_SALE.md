# Por qué “no sale nada” en Odoo 19 (y qué revisar)

Si en **Odoo 18** los módulos se ven bien y en **Odoo 19** no aparece nada (menús, vistas, apps), suele ser por una de estas causas.

---

## 1. El registro no carga (error al cargar un módulo)

Si **cualquier** módulo falla al cargar (por ejemplo un `NotImplementedError` o un `ImportError`), Odoo **no levanta el registro** de la base de datos y la instancia queda rota: no carga interfaz, no cargan menús, “no sale nada”.

**Qué hacer:**

- Revisar el **log de Odoo** al arrancar (y al abrir la base).
- Buscar líneas como:
  - `CRITICAL ... Couldn't load module ...`
  - `NotImplementedError`, `AttributeError`, `KeyError`, etc.
- Corregir el módulo que aparece en el traceback (por ejemplo el `@api.depends('id')` que ya se cambió a `@api.depends()`).
- Reiniciar Odoo y comprobar que ya **no** salga ese error.

Mientras haya un error que impida cargar un módulo, el resto (menús, vistas, tus cambios) no se verá.

---

## 2. Módulos no están en la ruta de addons de Odoo 19

En el log suele salir algo como:

```text
addons paths: ... '/home/odoo/src/user'
```

Tus módulos (por ejemplo `subscription_nocount`, `inventory_dashboard_simple`, `product_suppiles`) tienen que estar **dentro** de una de esas carpetas en el **servidor** donde corre Odoo 19.

**Qué hacer:**

- En el servidor, comprobar que existe la ruta (ej. `/home/odoo/src/user`).
- Comprobar que dentro están las carpetas de tus módulos (ej. `subscription_nocount`, `product_suppiles`, etc.).
- Si en 18 tenías otra ruta (por ejemplo otra carpeta de addons), en 19 esa ruta debe estar añadida en la configuración de Odoo (`addons_path` en el `.conf` o variable de entorno).

Si los módulos no están en ninguna ruta de addons, Odoo no los ve y “no sale nada” de esos módulos.

---

## 3. Lista de aplicaciones no actualizada o módulos no instalados

En Odoo 19, después de añadir o actualizar módulos en disco, la lista de “Apps” puede no reflejarlos hasta que la actualices. Y hasta que no los instales (o actualices), sus menús y vistas no aparecen.

**Qué hacer:**

1. Entrar en **Aplicaciones** (Apps).
2. Abrir el menú de filtros (o “Update Apps List” / “Actualizar lista de aplicaciones”) y pulsar **“Update Apps List”**.
3. Quitar el filtro **“Apps”** si lo tienes, para ver también módulos que no son “aplicación”.
4. Buscar por nombre (ej. “Dashboard”, “Product Supplies”, “Subscription”).
5. Si el módulo sale como **“Instalar”**, instalarlo.
6. Si sale como **“Upgrade”** (actualizar), actualizarlo y revisar el log por si falla algo al actualizar.

Si no actualizas la lista o no instalas/actualizas el módulo, sus menús no aparecen y parece que “no sale nada”.

---

## 4. Dónde se ven los menús (no siempre es un icono nuevo)

Muchos de tus módulos **no** añaden un icono nuevo en la barra de aplicaciones; añaden **submenús** dentro de menús que ya existen.

**Dónde mirar:**

- **Dashboard de inventario**:  
  **Inventario** (Stock) → **Dashboard** (o el primer menú dentro de Inventario). Ahí suelen estar “Dashboard”, “Inventario de Clientes”, “Configurar Grupos”, etc.
- **Product Supplies (líneas de negocio, etc.)**:  
  **Inventario** → **Configuración** → “Configuración Líneas de negocio” / “Lineas de negocio”.
- **Otros**: según cada módulo, revisar bajo **Inventario**, **Ventas**, **Compras**, etc.

Si buscas un icono nuevo tipo “Dashboard” en la barra superior y tu módulo solo añade submenús bajo Inventario, da la sensación de que “no sale nada” aunque los menús sí estén.

---

## 5. Cambios entre Odoo 18 y 19 que afectan a los módulos

Cosas que pueden hacer que “no funcione” o “no se vea” en 19:

| Qué | En 18 | En 19 |
|-----|--------|--------|
| `@api.depends('id')` | Permitido | **Prohibido** → `NotImplementedError` y registro no carga. |
| One2many en `@api.depends` sin “searchable” | Avisos | Avisos / posibles problemas si no se corrige. |
| Algunos nombres de modelos / campos | Existen | Pueden estar deprecados o renombrados. |
| Rutas HTTP `type='json'` | Válido | En 19 se prefiere/migra a `type='jsonrpc'`. |
| `_sql_constraints` | Soportado | Deprecado; se pide usar `model.Constraint`. |

Si tu código en el servidor de Odoo 19 sigue usando `@api.depends('id')` u otra cosa que en 19 ya no está permitida, el módulo puede fallar al cargar y entonces no se ve nada.

---

## 6. Checklist rápido (“no sale nada” en Odoo 19)

1. **Log al arrancar Odoo 19**  
   - ¿Aparece `Couldn't load module` o un `Traceback`?  
   - Si sí → corregir ese módulo (y reiniciar).

2. **Ruta de addons**  
   - ¿La carpeta donde están tus módulos está en `addons_path` en el servidor de Odoo 19?  
   - ¿Las carpetas de los módulos (con `__manifest__.py`) están dentro de esa ruta?

3. **Lista de aplicaciones**  
   - ¿Has hecho **“Update Apps List”** en Odoo 19?  
   - ¿Has **instalado** o **actualizado** los módulos que quieres usar?

4. **Dónde miras**  
   - ¿Estás mirando dentro de **Inventario** (y sus submenús) o solo en la barra de aplicaciones?

5. **Código desplegado**  
   - ¿El código que tienes en “Modulos Odoo 19” (con las correcciones, por ejemplo `@api.depends()` en lugar de `@api.depends('id')`) está **realmente desplegado** en el servidor donde corre Odoo 19?

Si quieres, el siguiente paso puede ser: pegar aquí la **salida del log de Odoo 19** desde que arranca hasta que abres la base (o el primer error que salga), y te digo exactamente qué está fallando y en qué módulo.
