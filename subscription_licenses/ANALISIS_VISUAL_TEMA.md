# Análisis visual del módulo Subscription Licenses

Resumen de cómo está construido el tema visual del módulo para que se vea “bonito” y coherente en Odoo.

---

## 1. Archivos que definen el tema

| Archivo | Uso |
|---------|-----|
| `static/src/css/subscription_licenses_theme.css` | Tema principal: colores pastel, botones, formularios, listas |
| `static/src/css/list_group_visible.css` | Texto en negro en filas de agrupación de listas |
| `static/src/js/subscription_licenses_theme.js` | Clase en `body` para vistas del módulo + barra de scroll arriba en Consolidado |
| `views/license_dashboard_templates.xml` | Dashboard HTML con estilos inline (KPI, tablas, barras) |

Los CSS y el JS se cargan en **backend** vía `__manifest__.py` → `assets` → `web.assets_backend`.

---

## 2. Paleta de colores

### Azul pastel (licencias / formularios genéricos)

- **Variables CSS** (en modales): `--pastel-blue-50` (#e8f4f8) hasta `--pastel-blue-600` (#3a8fb5).
- **Uso**: botones primarios, chatter, enlaces, bordes, sombras, fondos de grupos y listas.
- **Efectos**: gradientes lineales (180deg), `box-shadow` con tono azul suave, `inset` para reflejo.

### Verde/teal (Proveedores)

- **Proveedores**: tonos tipo teal (#0f766e, #0d9488, #ccfbf1, #f0fdfa).
- **Uso**: formulario de proveedor (`o_license_provider_form`), lista de proveedores (`o_license_provider_list`), alertas y pestañas activas en esa vista.
- **Diferenciación**: el resto del módulo usa azul; solo “Proveedores” usa esta paleta verde para identificarlo rápido.

### Dashboard (página HTML)

- **Fondo**: gradiente `#f0f9ff` → `#e0f2fe` → `#f8fafc`.
- **Header**: gradiente `#1e3a5f` → `#2563eb`.
- **KPI**: tarjetas con gradientes (primary #2563eb, success #10b981, accent #0ea5e9, orange #f59e0b).
- **Barras y mini-cards**: bordes izquierdos de color (gris, warn, danger) y fondos blancos con sombra ligera.

---

## 3. Botones

- **Primarios** (Activar, Añadir, etc.):
  - Gradiente azul pastel, texto blanco, borde, `border-radius: 6px`, sombra y reflejo (`inset`).
  - **Hover**: gradiente más oscuro, sombra más marcada, `transform: translateY(-1px)`.
  - Efecto de “brillo” al pasar el ratón (`::after` con gradiente que se desplaza).

- **Secundarios** (Desactivar, Cancelar, etc.):
  - Fondo más claro (azul muy suave), texto azul oscuro, mismo radio y tipo de sombra.

- **Chatter y modales**: mismos estilos pastel para que botones de Enviar mensaje, Registrar nota y pies de wizard sigan el mismo lenguaje visual.

- **Control panel** (Nuevo, filtros): cuando la vista es del módulo, `body.o_subscription_licenses_view` aplica el mismo estilo de botones primarios/secundarios en `.o_control_panel`. La clase en `body` la pone el JS según el modelo actual (lista de modelos en `subscription_licenses_theme.js`).

---

## 4. Formularios

- **Clase común**: `o_subscription_form` en todos los formularios del módulo (licencias, asignaciones, proveedor, categorías, TRM, etc.).
- **Formularios “tipo dashboard”**:
  - **`.o_license_module_form`** (licencias, asignaciones, categorías, equipos, etc.):
    - Sheet con fondo `linear-gradient(#f0f9ff → #f8fafc)`.
    - Grupos (`.o_group`) como “tarjetas”: fondo blanco, `border-radius: 12px`, sombra suave, borde azul muy tenue.
    - **Button box**: botones estadísticos (oe_stat_button) con fondo blanco, borde y sombra pastel, hover con ligero gradiente y `translateY(-2px)`.
    - **Pestañas**: sin borde clásico; activa con gradiente azul y texto blanco; inactivas gris, hover azul suave.
    - **Contenido del notebook**: fondo blanco, bordes redondeados, sombra y padding generoso.
    - **Listas embebidas**: bordes redondeados, cabecera con gradiente suave, títulos de columna en azul y negrita.
  - **`.o_license_provider_form`** (Proveedor):
    - Mismo esquema pero con paleta **verde/teal**: fondo sheet (#f0fdfa), alertas y bloques `.bg-light` en tonos teal, stat buttons y pestañas en verde.
    - Título (h1) en color oscuro teal (#134e4a).
    - Alert info con gradiente verde (#ccfbf1 → #99f6e4).

- **Espaciado**: `padding` y `margin` amplios (1.25rem–1.75rem), `max-width: 1100px` y contenido centrado para no estirar en pantallas grandes.

---

## 5. Listas (vistas lista)

- **Clases por tipo**:
  - `o_license_module_list`: licencias, categorías, equipos, stock por proveedor, TRM.
  - `o_license_provider_list`: proveedores.
  - `o_license_assignment_list`: asignaciones.

- **Estilo “tarjeta”**:
  - Fondo del área de contenido: gradiente suave (#f0f9ff → #f8fafc).
  - Tabla: fondo blanco, `border-radius: 12px`, sombra y borde suave.
  - Cabecera: gradiente (azul pastel o, en proveedores, verde/teal).
  - Títulos de columna: negrita y color de acento (azul o teal).
  - Filas: hover con fondo muy suave (rgba del color de acento).
  - Enlaces: color de acento, subrayado en hover.

- **Asignaciones**: mismo estilo de tarjeta pero texto y enlaces en negro (#1f1f1f) para buena legibilidad.

- **Decoraciones por estado** (en XML):
  - `decoration-muted`, `decoration-success`, `decoration-warning`, `decoration-danger`, `decoration-info` según estado (activo, cancelado, vencido, etc.).
  - Campo estado con `widget="badge"` para chips de color.

---

## 6. Detalles de UX en vistas

- **Alertas y bloques de ayuda**: `alert alert-info` o `div.mb-3.p-2.bg-light.rounded` con `border-radius: 8px` y texto explicativo junto a botones (Traer licencias, Exportar Excel, Actualizar lista de clientes).
- **Botones de acción**: mezcla de `btn-primary`, `btn-secondary`, `btn-link` con iconos FontAwesome (`fa-refresh`, `fa-file-excel-o`, `fa-external-link`, etc.).
- **Sin contenido**: mensajes con clase `o_view_nocontent_smiling_face` para estado vacío.
- **Consolidado (tabla ancha)**:
  - Lista con clase `o_list_consolidado_top_scroll`.
  - JS clona el scroll horizontal en una barra arriba de la tabla (`.o_list_consolidado_top_scroll_bar`) y la sincroniza; el CSS estiliza esa barra (altura, color teal suave, scrollbar webkit).

---

## 7. Dashboard (página aparte)

- **Ruta**: `/subscription_licenses/dashboard` (action `ir.actions.act_url`).
- **HTML + estilos inline** en `license_dashboard_templates.xml`:
  - Header fijo con gradiente oscuro y enlaces (Volver, Ver listado, Asignaciones, Proveedores).
  - Grid de KPI (`.ld_kpi_card`): 4 tarjetas con gradientes (primary, success, accent, orange), hover con `translateY(-2px)` y más sombra.
  - Secciones (`.ld_section`): fondo blanco, bordes redondeados, sombra.
  - Tablas (`.ld_table`): cabeceras grises, filas con hover gris muy suave.
  - Mini-cards (`.ld_mini_card`) con borde izquierdo de color (normal, warn, danger).
  - Barras de progreso (`.ld_bar`, `.ld_bar_fill`) con gradientes (azul, naranja, verde).
  - Botones CTA (`.ld_cta`): azul sólido, redondeados, hover más oscuro.

---

## 8. Resumen de clases CSS clave

| Clase | Dónde se usa | Efecto visual |
|-------|----------------|----------------|
| `o_subscription_form` | Todos los forms del módulo | Activa el tema pastel (botones, chatter, modales) |
| `o_license_module_form` | Forms de licencias, categorías, asignaciones, equipos, TRM | Fondo azul suave, grupos tipo tarjeta, stat buttons y pestañas azules |
| `o_license_provider_form` | Form de proveedor | Igual que el anterior pero paleta verde/teal |
| `o_license_module_list` | Listas de licencias, categorías, equipos, stock | Lista tipo tarjeta, cabecera y enlaces azules |
| `o_license_provider_list` | Lista de proveedores | Mismo estilo con verde/teal |
| `o_license_assignment_list` | Lista de asignaciones | Tarjeta + texto negro para legibilidad |
| `o_list_consolidado_top_scroll` | Lista Consolidado en proveedor | Tabla con scroll horizontal duplicado arriba |
| `o_subscription_statusbar` | Barra de estado en asignaciones | Coherencia con el tema (opcional) |
| `o_subscription_licenses_view` (en `body`) | Puesta por JS en vistas del módulo | Aplica tema a botones del control panel |

---

## 9. Cómo replicar el “look” en otro módulo

1. **Incluir** el mismo (o similar) `subscription_licenses_theme.css` y reutilizar las variables `--pastel-blue-*` y las clases `o_subscription_form` / `o_license_module_form` en tus formularios y listas.
2. **En las vistas XML**: añadir `class="o_subscription_form o_license_module_form"` en `<form>` y `class="o_license_module_list"` en `<list>` (o la variante provider/assignment si aplica).
3. **Botones**: usar `btn-primary` y `btn-secondary`; el CSS los estiliza si están dentro de un form con `o_subscription_form`.
4. **Control panel**: si quieres el mismo estilo fuera del módulo de licencias, añadir la clase en `body` (como hace `subscription_licenses_theme.js`) cuando estés en las acciones de tu módulo.
5. **Dashboard**: si haces una página HTML propia, usar la misma estructura de header, `.ld_kpi_card`, `.ld_section`, `.ld_table` y `.ld_cta` con los mismos colores y sombras.

Con esto el módulo de licencias queda con un tema visual unificado (azul pastel + verde para proveedores), botones y tarjetas con relieve y hover, y un dashboard con KPIs y barras claras y legibles.
