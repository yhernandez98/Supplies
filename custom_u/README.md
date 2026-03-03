# Módulo Unificado Personalizado - custom_u

## Descripción
Módulo unificado para Odoo 18.0 que combina todas las funcionalidades personalizadas de contactos, productos y creación automática en un solo módulo optimizado y fácil de mantener.

## 🚀 Funcionalidades Unificadas

### 📋 **FUNCIONALIDADES DE CONTACTOS**
- **Campo tipo_contacto**: Proveedor, Cliente, Proveedor y Cliente
- **Integración automática**: Con customer_rank y supplier_rank nativos
- **Validaciones robustas**: Constraints para mantener consistencia
- **Interfaz mejorada**: Widget radio horizontal con estilos personalizados

### 🏭 **FUNCIONALIDADES DE PRODUCTOS**
- **Campo tipo_producto**: Con opciones en español (Bienes, Servicio, Producto Facturable)
- **Sincronización bidireccional**: Con el campo nativo 'type' de Odoo
- **Sincronización automática**: Bidireccional entre campos personalizados y nativos
- **Validaciones de consistencia**: Para mantener integridad de datos

### 👥 **FUNCIONALIDADES DE CREACIÓN AUTOMÁTICA**
- **Creación automática**: De contactos individuales para empresas
- **Plantillas personalizables**: Para nombres y emails de contactos
- **Generación inteligente**: De emails con variables dinámicas
- **Validaciones robustas**: Y creación optimizada en lote

## 📊 Mapeo de Campos

### Contactos (res.partner)
| Campo Personalizado | Campo Nativo | Descripción |
|-------------------|--------------|-------------|
| tipo_contacto = "proveedor" | supplier_rank = 1, customer_rank = 0 | Proveedor |
| tipo_contacto = "cliente" | supplier_rank = 0, customer_rank = 1 | Cliente |
| tipo_contacto = "ambos" | supplier_rank = 1, customer_rank = 1 | Proveedor y Cliente |

### Productos (product.template)
| Campo Personalizado | Campo Nativo | Descripción |
|-------------------|--------------|-------------|
| tipo_producto = "Bienes" | type = "consu" | Consumible |
| tipo_producto = "Servicio" | type = "service" | Servicio |
| tipo_producto = "Producto Facturable" | type = "product" | Almacenable |

## 🛠️ Instalación

### Requisitos
- Odoo 18.0 o superior
- Módulos base: `base`, `contacts`, `product`

### Pasos de Instalación
1. **Copiar el módulo** a la carpeta de addons de Odoo
2. **Reiniciar el servidor** de Odoo
3. **Actualizar la lista** de módulos
4. **Instalar** "Módulo Unificado Personalizado"
5. **Configurar** según necesidades

## 📖 Guía de Uso

### Configuración de Contactos

#### 1. Crear una Empresa
```
1. Ir a Contactos > Crear
2. Marcar "Es una empresa"
3. Llenar datos básicos
4. Seleccionar "Tipo de Contacto"
5. Configurar creación automática (opcional)
```

#### 2. Configurar Contacto Automático
```
1. En la pestaña "Contacto Automático"
2. Activar "Crear contacto automático"
3. Configurar plantillas:
   - Nombre: "Contacto {company_name}"
   - Email: "contacto@{domain}"
4. El contacto se crea automáticamente
```

#### 3. Variables de Plantilla
- `{company_name}`: Nombre de la empresa
- `{domain}`: Dominio generado automáticamente
- `{contact_name}`: Nombre del contacto generado

### Configuración de Productos

#### 1. Crear un Producto
```
1. Ir a Inventario > Productos > Crear
2. Llenar datos básicos
3. Seleccionar "Tipo de Producto" en español
4. El campo nativo se sincroniza automáticamente
```

#### 2. Sincronización Automática
```
1. Al crear o editar un producto
2. Seleccionar "Tipo de Producto" en español
3. El campo nativo se sincroniza automáticamente
4. Los cambios se reflejan en ambas direcciones
```

## 🔧 Funcionalidades Técnicas

### Sincronización Automática
- **Bidireccional**: Cambios en un campo actualizan el otro
- **En tiempo real**: Con `@api.onchange` en formularios
- **En base de datos**: Con overrides de `create` y `write`
- **Validaciones**: Con `@api.constrains` para consistencia

### Sincronización Automática
- **Bidireccional**: Cambios en un campo actualizan el otro
- **En tiempo real**: Con `@api.onchange` en formularios
- **En base de datos**: Con overrides de `create` y `write`
- **Validaciones**: Con `@api.constrains` para consistencia

### Interfaz de Usuario
- **Widgets personalizados**: Radio buttons horizontales
- **Estilos CSS**: Para mejor experiencia visual
- **Interfaz limpia**: Sin botones innecesarios
- **Responsive**: Adaptable a diferentes pantallas

## 📁 Estructura del Módulo

```
custom_u/
├── __init__.py
├── __manifest__.py
├── README.md
├── models/
│   ├── __init__.py
│   ├── res_partner.py
│   └── product_template.py
├── views/
│   ├── res_partner_views.xml
│   └── product_template_views.xml
├── security/
│   └── ir.model.access.csv
└── static/
    └── src/
        └── css/
            └── radio_styles.css
```

## 🎯 Casos de Uso

### Caso 1: Empresa con Contacto Automático
```
1. Crear empresa "ACME Corp"
2. Tipo de contacto: "Proveedor"
3. Activar creación automática
4. Resultado:
   - Contacto: "Contacto ACME Corp"
   - Email: "contacto@acme.corp.com"
   - Tipo: Proveedor (supplier_rank = 1)
```

### Caso 2: Producto con Sincronización
```
1. Crear producto "Laptop Dell"
2. Tipo de producto: "Bienes"
3. Resultado automático:
   - tipo_producto = "Bienes"
   - type = "consu"
   - Sincronización bidireccional activa
```

### Caso 3: Migración de Datos
```
1. Instalar módulo en sistema existente
2. Crear o editar productos existentes
3. La sincronización se realiza automáticamente
4. Resultado: Todos los datos sincronizados automáticamente
```

## ⚙️ Configuración Avanzada

### Personalización de Plantillas
```python
# Plantilla de nombre personalizada
contact_name_template = "Representante de {company_name}"

# Plantilla de email personalizada
contact_email_template = "ventas@{domain}"
```

### Variables Disponibles
- `{company_name}`: Nombre de la empresa
- `{domain}`: Dominio generado automáticamente
- `{contact_name}`: Nombre del contacto generado

## 🔍 Solución de Problemas

### Problema: Productos no sincronizados
**Solución**: Editar el producto y cambiar el tipo, la sincronización es automática

### Problema: Datos inconsistentes
**Solución**: Los datos se sincronizan automáticamente al editar

### Problema: Contacto automático no se crea
**Solución**: Verificar que la empresa tenga `is_company = True` y `auto_create_contact = True`

### Problema: Error de validación
**Solución**: Verificar que los campos personalizados y nativos sean consistentes

## 📈 Beneficios del Módulo Unificado

### 🚀 **Eficiencia**
- **Un solo módulo**: En lugar de tres módulos separados
- **Instalación simple**: Una sola instalación
- **Mantenimiento fácil**: Código unificado y organizado

### 🎯 **Funcionalidad**
- **Integración completa**: Entre contactos, productos y creación automática
- **Sincronización robusta**: Bidireccional y automática
- **Validaciones**: Para mantener integridad de datos

### 🔧 **Técnico**
- **Código optimizado**: Sin duplicaciones
- **Compatibilidad**: Con Odoo 18.0
- **Escalabilidad**: Fácil de extender

### 👥 **Usuario**
- **Interfaz unificada**: Consistente en toda la aplicación
- **Herramientas de utilidad**: Para mantenimiento fácil
- **Documentación completa**: Con ejemplos y casos de uso

## 🔄 Migración desde Módulos Separados

### Antes (3 módulos separados)
- `custom_contac_auto`: Creación automática de contactos
- `custom_partner`: Tipo de contacto personalizado
- `custom_template`: Tipo de producto personalizado

### Después (1 módulo unificado)
- `custom_u`: Todas las funcionalidades en un solo módulo

### Proceso de Migración
1. **Desinstalar** módulos separados
2. **Instalar** módulo unificado
3. **Verificar** que todas las funcionalidades estén activas
4. **La sincronización** se realiza automáticamente

## 📞 Soporte

Para soporte técnico o reportar problemas:
- **Autor**: Felipe Valbuena
- **Versión**: 18.0.3.0
- **Licencia**: LGPL-3

## 🎉 Conclusión

El módulo unificado `custom_u` proporciona una solución completa y optimizada que combina todas las funcionalidades personalizadas en un solo paquete fácil de instalar, configurar y mantener. Con sincronización automática, validaciones robustas y herramientas de utilidad, es la solución ideal para personalizar Odoo 18.0 según las necesidades específicas del negocio.

---

**¡El módulo está listo para ser instalado y usado en producción!**
