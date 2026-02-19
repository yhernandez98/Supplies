# Solución: Módulo no se actualiza correctamente

## Problemas Comunes y Soluciones

### 1. ✅ Versión del Módulo Actualizada
- **Cambio realizado**: Versión actualizada de `18.0.1.0.0` a `18.0.1.0.1`
- **Archivo**: `__manifest__.py`

### 2. Pasos para Actualizar Correctamente

#### Opción A: Desde la Interfaz Web (Recomendado)
1. **Activar Modo Desarrollador**:
   - Presiona `Alt + Shift + D` o ve a Configuración → Activar Modo Desarrollador

2. **Actualizar el Módulo**:
   - Ve a **Aplicaciones**
   - Busca "Creación Automática de Almacenes"
   - Haz clic en **Actualizar** (no "Actualizar Lista")

3. **Limpiar Caché del Navegador**:
   - Presiona `Ctrl + Shift + R` (o `Ctrl + F5`) para recargar sin caché

#### Opción B: Desde la Terminal (Servidor)
```bash
# Reiniciar el servidor Odoo
sudo systemctl restart odoo

# O si usas el comando directo:
./odoo-bin -u warehouse_auto_create -d nombre_base_datos
```

### 3. Verificar que los Cambios se Aplicaron

#### Verificar Vista XML:
1. Ve a **Técnico → Interfaz de Usuario → Vistas**
2. Busca: `res.partner.form.warehouse.auto.create`
3. Verifica que la vista tenga los botones

#### Verificar Métodos Python:
1. Ve a **Técnico → Base de Datos → Modelos**
2. Busca: `res.partner`
3. Verifica que existan los métodos:
   - `create_partner_warehouse`
   - `action_view_warehouse`

### 4. Problemas Específicos y Soluciones

#### ❌ Los botones no aparecen en el formulario
**Causa**: La vista no se está heredando correctamente

**Solución**:
1. Verifica que el campo `category_id` exista en la vista base
2. Prueba cambiar el XPath a otro campo que exista:
   ```xml
   <xpath expr="//field[@name='name']" position="after">
   ```

#### ❌ Error al hacer clic en el botón
**Causa**: El método no se está cargando

**Solución**:
1. Reinicia el servidor Odoo
2. Verifica que `models/__init__.py` importe `res_partner`
3. Verifica que `__init__.py` importe `models`

#### ❌ El módulo no aparece en la lista
**Causa**: El módulo no está en la ruta correcta

**Solución**:
1. Verifica que el módulo esté en la carpeta de addons personalizados
2. Actualiza la lista de aplicaciones: **Aplicaciones → Actualizar Lista de Aplicaciones**

### 5. Comandos Útiles para Diagnóstico

#### Ver logs del servidor:
```bash
tail -f /var/log/odoo/odoo-server.log
```

#### Verificar errores de Python:
```bash
python3 -m py_compile warehouse_auto_create/models/res_partner.py
```

#### Verificar errores de XML:
```bash
xmllint --noout warehouse_auto_create/views/res_partner_views.xml
```

### 6. Estructura del Módulo (Verificar)

```
warehouse_auto_create/
├── __init__.py                    ✅
├── __manifest__.py                ✅ (versión 18.0.1.0.1)
├── models/
│   ├── __init__.py                ✅
│   └── res_partner.py             ✅
├── views/
│   └── res_partner_views.xml      ✅
└── security/
    └── ir.model.access.csv        ✅
```

### 7. Forzar Reinstalación (Último Recurso)

Si nada funciona:
1. **Desinstalar** el módulo
2. **Reiniciar** el servidor Odoo
3. **Instalar** el módulo nuevamente

### 8. Verificar Dependencias

Asegúrate de que estos módulos estén instalados:
- ✅ `base`
- ✅ `contacts`
- ✅ `stock`
- ✅ `custom_u` (para el campo `tipo_contacto`)

## Checklist de Verificación

- [ ] Versión del módulo actualizada
- [ ] Servidor Odoo reiniciado
- [ ] Módulo actualizado desde la interfaz
- [ ] Caché del navegador limpiada
- [ ] Dependencias instaladas
- [ ] Sin errores en los logs
- [ ] Vista heredada correctamente
- [ ] Métodos Python cargados

## Contacto

Si el problema persiste, verifica:
1. Los logs del servidor para errores específicos
2. Que el módulo `custom_u` esté instalado y funcional
3. Que el campo `tipo_contacto` exista en `res.partner`

