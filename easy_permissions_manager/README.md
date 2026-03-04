# Gestor Fácil de Permisos

Módulo para gestionar permisos de usuarios de forma más simple y visual en Odoo.

## Características

- **Vista de usuarios y permisos**: Ver fácilmente qué permisos tiene cada usuario
- **Roles predefinidos**: Asignar roles comunes rápidamente (ej: "Solo Lectura Inventario", "Sin Acceso Compras")
- **Wizard de permisos**: Interfaz simple para asignar permisos sin navegar por múltiples menús
- **Gestión por módulo**: Ver y gestionar permisos organizados por módulo

## Uso

### 1. Acceder al Gestor de Permisos

Hay dos formas de acceder:

**Opción A: Desde el menú**
- Ir a: **Configuración > Gestión de Permisos > Gestor de Permisos**

**Opción B: Desde un usuario**
- Abrir cualquier usuario en **Configuración > Usuarios y Compañías > Usuarios**
- Hacer clic en el botón **"Gestor de Permisos"** en el header

### 2. Crear Roles Predefinidos

1. Ir a: **Configuración > Gestión de Permisos > Roles Predefinidos**
2. Crear un nuevo rol (ej: "Solo Lectura Inventario")
3. Configurar:
   - **Grupos a Agregar**: Grupos que se agregarán al usuario
   - **Grupos a Remover**: Grupos que se removerán del usuario
   - **Módulos Afectados**: Módulos relacionados (información)

### 3. Asignar Permisos a un Usuario

1. Abrir el **Gestor de Permisos**
2. Seleccionar el usuario
3. Elegir un **Rol Predefinido** o configurar manualmente
4. Hacer clic en **"Aplicar Permisos"**

## Ejemplos de Roles

### Ejemplo 1: Bloquear Acceso a Compras
- **Nombre**: "Sin Acceso a Compras"
- **Grupos a Remover**: 
  - `purchase.group_purchase_user`
  - `purchase.group_purchase_manager`

### Ejemplo 2: Solo Lectura Inventario
- **Nombre**: "Solo Lectura Inventario"
- **Grupos a Agregar**: 
  - `stock.group_stock_user`
- **Grupos a Remover**: 
  - `stock.group_stock_manager`

### Ejemplo 3: Solo Lectura Productos
- **Nombre**: "Solo Lectura Productos"
- **Grupos a Agregar**: 
  - `stock.group_stock_user`
- **Grupos a Remover**: 
  - `product.group_product_manager`

## Notas Importantes

- Los cambios se aplican inmediatamente al hacer clic en "Aplicar Permisos"
- Los roles predefinidos se pueden reutilizar para múltiples usuarios
- Se pueden crear tantos roles como sea necesario
- Los grupos se pueden buscar por nombre en el selector

## Estructura del Módulo

```
easy_permissions_manager/
├── models/
│   ├── permission_manager.py    # Wizard para gestionar permisos
│   ├── permission_role.py        # Modelo de roles predefinidos
│   └── res_users.py              # Extensión de res.users
├── views/
│   ├── permission_views.xml      # Vistas del gestor y roles
│   └── menuitems.xml             # Menús
├── data/
│   └── permission_roles_data.xml # Roles predefinidos de ejemplo
└── security/
    └── ir.model.access.csv       # Permisos de acceso
```

## Próximas Mejoras

- Vista de permisos por módulo más detallada
- Exportar/importar configuraciones de permisos
- Historial de cambios de permisos
- Plantillas de permisos por departamento
