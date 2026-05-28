# Manual de uso: Integración CRM – Compras – Calculadora (`crm_cost_integration_bridge`)

Este módulo **no sustituye** a `crm_sales_supplies` ni a `calculadora_costos`: añade un **flujo opcional** que une la cotización de proveedor aprobada, la calculadora de costos, la propuesta al cliente y el ruteo automático (bodega o compra).

---

## 1. Requisitos previos

- Módulos instalados: **CRM Sales Supplies** (`crm_sales_supplies`) y **Calculadora de Costos** (`calculadora_costos`).
- Instalar **Integración CRM – Compras – Calculadora** (`crm_cost_integration_bridge`).
- Roles típicos:
  - **Ventas / CRM**: oportunidad, cotización venta, aprobación CRM de cotizaciones de compra, marcar ganadora, propuesta al cliente.
  - **Compras**: crear cotizaciones de proveedor desde la alerta (flujo ya existente).
  - **Inventario**: recibir actividades cuando hay reserva y alistamiento.

---

## 2. Dónde está en el menú

**CRM → Operación CRM → Integración calculadora**

- **Casos integración**: lista y formulario del caso que une alerta, PO ganadora, calculadora y propuesta.
- **Propuestas cliente**: propuestas enviadas / borrador con snapshot en COP.

También hay accesos desde:

- **Alerta por cotización** (formulario): botón **Caso integración**.
- **Orden de compra / cotización proveedor** (formulario): botón **Marcar cotización ganadora** (cuando aplique).
- **Oportunidad** y **Cotización de venta**: botón estadístico **Integración** (si ya existen casos vinculados).

---

## 3. Flujo paso a paso (recomendado)

### Paso A – Solicitud y cotizaciones de compra (igual que antes)

1. Desde la **oportunidad** o la **cotización de venta**, genere la **alerta por cotización** y el flujo de **compras** como lo hacen hoy (cotizaciones a proveedores, etc.).
2. Cuando existan una o más **órdenes de compra** (cotizaciones de proveedor) ligadas a esa alerta, el **jefe de CRM** debe **aprobar por CRM** la cotización que será la base del precio (`Aprobada por CRM` en la PO), según las reglas ya definidas en `crm_sales_supplies`.

### Paso B – Abrir o crear el caso de integración

1. Abra la **Alerta por cotización** relacionada.
2. Pulse **Caso integración**  
   - Si no existía caso, se **crea** uno vinculado a la alerta, lead y cotización de venta (si aplica).  
   - Si ya existía, se **abre** ese caso.

Estado inicial del caso: **Cotizaciones proveedor** (`awaiting_quotes`) o equivalente según creación manual.

### Paso C – Marcar la cotización ganadora

1. Abra la **orden de compra (cotización del proveedor)** que debe ser la **única fuente** de costos para esta operación.
2. Compruebe que está **Aprobada por CRM** (`approved_by_crm`).
3. Pulse **Marcar cotización ganadora**.

**Efecto:**

- Se asocia esa PO al caso como **ganadora**.
- Se crea o actualiza una **Calculadora de costos** (`calculadora.costos`) y se cargan **líneas de equipo** desde las líneas de la PO (productos almacenables/consumibles; no servicios en ese paso).
- El caso pasa a **Calculadora lista** (`calculator_ready`).

**Restricción:** no se puede marcar ganadora si la PO **no** está aprobada por CRM.

### Paso D – Ajustar la calculadora (IVA, seguro, TRM, etc.)

1. En el caso, use **Abrir calculadora** (o abra la calculadora desde el menú de calculadora y localice el registro vinculado al caso).
2. En el grupo **Integración CRM (IVA y seguro)**:
   - **Seguro manual (COP)**: valor fijo en pesos.
   - **Aplicar IVA** + **IVA (%)**: si aplica para el precio final al cliente.
3. Revise **TRM**, **utilidad** y el resto de pestañas de la calculadora como siempre (venta vs suscripción, servicio técnico, plazos, etc.).

Los campos **Base antes de IVA**, **Monto IVA** y **Precio final cliente (COP)** se calculan automáticamente según la lógica del módulo.

### Paso E – Generar y enviar la propuesta al cliente

1. En el **caso de integración**, pulse **Generar propuesta**.
2. Se crea (o reutiliza en borrador) una **Propuesta al cliente** con valores tomados de la calculadora en ese momento.
3. Abra la propuesta y pulse **Enviar (congelar snapshot)** cuando vaya a comunicar la oferta.

**Efecto:** la propuesta queda en estado **Enviada** y los importes quedan **congelados** (snapshot). El caso pasa a **Propuesta enviada**.

### Paso F – Respuesta del cliente

En el formulario de la **Propuesta al cliente**:

- **Cliente aprobó** → dispara el **ruteo operativo** (una sola vez):
  - Si hay **stock suficiente** en el almacén del caso: se crea una **entrega** (picking) hacia el cliente, se intenta **reservar** y se generan **actividades** para usuarios de inventario (alistamiento).
  - Si **falta stock**: se intenta crear una **orden de compra** automática con los faltantes (mismo proveedor en todas las líneas; si hay proveedores distintos, el sistema avisará con error y deberá crear la compra manualmente).
- **Cliente rechazó** → el caso queda en estado de rechazo; no se ejecuta ruteo.

---

## 4. Roles y permisos (resumen)

- **Vendedor / CRM** (`group_sale_salesman`): casos y propuestas (crear/editar; no borrar casos salvo permisos extra).
- **Responsable ventas** (`group_sale_manager`): incluye borrado de casos/propuestas si lo necesita.
- **Usuario compras** (`group_purchase_user`): casos y propuestas (lectura/edición acorde al acceso definido).
- **Usuario inventario** (`group_stock_user`): lectura del caso (para seguimiento); las tareas suelen ir sobre el **picking**.

Ajuste en **Ajustes → Usuarios y compañías → Grupos** si su política interna requiere más restricción.

---

## 5. Limitaciones y buenas prácticas

1. **Una misma PO ganadora** no puede estar en dos casos distintos (restricción de unicidad).
2. **PO automática por faltante:** todas las líneas deben poder resolverse con el **mismo proveedor** (`_select_seller`); si no, use compra manual.
3. **Líneas solo servicio** en la PO: no se replican como líneas de equipo en la calculadora para el cálculo de stock; valide productos físicos.
4. **Almacén del caso:** viene de la **alerta** al crear el caso; el chequeo de stock usa ese almacén. Si no hay almacén, el ruteo tras aprobación del cliente puede quedar limitado (mensaje en el chatter del caso).
5. **Histórico:** los registros antiguos **no** se migran; el flujo nuevo aplica a operaciones que usted dispare con este módulo.

---

## 6. Solución de problemas

| Síntoma | Qué revisar |
|--------|--------------|
| No aparece **Marcar cotización ganadora** | Que la PO tenga referencia de **alerta**, esté en **draft/sent** y **Aprobada por CRM**. |
| Error al marcar ganadora | PO no aprobada por CRM, o PO no vinculada a ninguna alerta. |
| No genera propuesta | Debe existir **cotización ganadora** y **calculadora** sincronizada. |
| Error al aprobar cliente (compra auto) | Proveedores distintos por producto, o producto sin proveedor en catálogo. |
| Vista de calculadora no muestra bloque CRM | Módulo puente actualizado; actualice la lista de aplicaciones y el módulo `crm_cost_integration_bridge`. |

---

## 7. Actualizaciones del código

Tras cambios en Python/XML de este módulo:

- **Actualizar** `crm_cost_integration_bridge` desde Aplicaciones (modo desarrollador) o con `-u crm_cost_integration_bridge` en el servicio Odoo.

---

*Documento alineado a la versión del módulo indicada en `__manifest__.py`.*
