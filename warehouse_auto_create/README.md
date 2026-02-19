# Módulo de Creación Automática de Almacenes

## Descripción

Este módulo permite crear automáticamente un almacén (`stock.warehouse`) desde el formulario de contactos (`res.partner`) cuando el contacto tiene el campo `tipo_contacto` con valor "cliente" o "ambos".

## Características

- ✅ Botón "Crear Almacén" visible solo para contactos tipo "cliente" o "ambos"
- ✅ Creación automática de almacén con configuración predeterminada
- ✅ Validación de duplicados (no permite crear almacenes duplicados)
- ✅ Asignación automática de compañía "Supplies de Colombia" (ID=1)
- ✅ Generación automática de código de almacén (primeros 5 caracteres del nombre)
- ✅ Manejo de errores y mensajes informativos
- ✅ Botón adicional para ver el almacén existente

## Requisitos

- Odoo 18.0
- Módulos base: `base`, `contacts`, `stock`
- Módulo `custom_u` (para el campo `tipo_contacto`)

## Instalación

1. Copiar el módulo a la carpeta de addons personalizados
2. Actualizar la lista de aplicaciones en Odoo
3. Instalar el módulo "Creación Automática de Almacenes"

## Uso

### Crear un Almacén

1. Ir a **Contactos** → Seleccionar un contacto
2. Verificar que el campo `tipo_contacto` sea "Cliente" o "Proveedor y Cliente"
3. Hacer clic en el botón **"Crear Almacén"** en el header del formulario
4. El sistema creará automáticamente el almacén con la configuración predeterminada

### Ver Almacén Existente

1. Si el contacto ya tiene un almacén asociado, aparecerá el botón **"Ver Almacén"**
2. Hacer clic en el botón para abrir el formulario del almacén

## Configuración del Almacén Creado

Cuando se crea un almacén automáticamente, se aplican los siguientes valores:

| Campo | Valor | Descripción |
|-------|-------|-------------|
| `name` | Nombre del contacto | Nombre completo del contacto |
| `code` | Primeros 5 caracteres (mayúsculas) | Código único del almacén |
| `company_id` | Supplies de Colombia (ID=1) | Compañía asignada |
| `partner_id` | ID del contacto actual | Partner asociado |
| `reception_steps` | `one_step` | Recepción en un solo paso |
| `delivery_steps` | `ship_only` | Envío directo |
| `buy_to_resupply` | `False` | No comprar para reabastecer |
| `resupply_wh_ids` | Almacén principal de la compañía | Almacén de reabastecimiento |

## Validaciones

El módulo realiza las siguientes validaciones:

- ✅ Verifica que el contacto tenga `tipo_contacto = "cliente"` o `"ambos"`
- ✅ Verifica que el contacto tenga un nombre
- ✅ Verifica que no exista ya un almacén para ese contacto
- ✅ Verifica que exista la compañía "Supplies de Colombia" (ID=1)
- ✅ Verifica que exista un almacén principal para la compañía
- ✅ Genera código único si hay duplicados (agrega sufijo numérico)

## Manejo de Errores

El módulo muestra mensajes de error claros en los siguientes casos:

- Contacto no es tipo "cliente" o "ambos"
- Contacto no tiene nombre
- Ya existe un almacén para ese contacto
- No se encuentra la compañía "Supplies de Colombia"
- No se encuentra un almacén principal
- Error al crear el almacén

## Estructura del Módulo

```
warehouse_auto_create/
├── __init__.py
├── __manifest__.py
├── README.md
├── models/
│   ├── __init__.py
│   └── res_partner.py
├── views/
│   └── res_partner_views.xml
└── security/
    └── ir.model.access.csv
```

## Permisos

El módulo requiere los siguientes permisos:

- **Usuarios**: Pueden crear almacenes desde contactos
- **Gestores de Inventario**: Pueden ver el botón "Ver Almacén"

## Notas Técnicas

- El código del almacén se genera automáticamente tomando los primeros 5 caracteres del nombre del contacto en mayúsculas
- Si el código está duplicado, se agrega un sufijo numérico (ej: "NOMB1", "NOMB2")
- El almacén se crea con la configuración mínima necesaria para funcionar
- Se asigna automáticamente el almacén principal de la compañía como fuente de reabastecimiento

## Autor

Supplies de Colombia

## Licencia

LGPL-3

