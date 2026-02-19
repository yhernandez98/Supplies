# Guía: Cómo Revisar los Logs de Errores

## 📋 Resumen

Este módulo ahora genera logs detallados en cada paso del proceso de creación de rutas y reglas. Los logs te ayudarán a identificar exactamente dónde está fallando el proceso.

## 🔍 Dónde Ver los Logs

### Opción 1: Logs de Odoo (Recomendado)

1. **Ubicación del archivo de log:**
   - Windows: `C:\Program Files\Odoo\odoo-server.log` (o la ruta donde esté instalado Odoo)
   - Linux: `/var/log/odoo/odoo-server.log` o donde esté configurado

2. **Ver logs en tiempo real:**
   ```bash
   # Windows PowerShell
   Get-Content odoo-server.log -Wait -Tail 50
   
   # Linux
   tail -f /var/log/odoo/odoo-server.log
   ```

### Opción 2: Consola de Odoo

Si ejecutas Odoo desde la consola, los logs aparecerán directamente en la terminal.

## 📊 Qué Buscar en los Logs

### 1. Inicio del Proceso

Busca estas líneas al ejecutar "Crear Todas las Rutas y Reglas":

```
================================================================================
=== INICIO: action_create_all_routes ===
================================================================================
```

### 2. Información de Contactos y Almacenes

```
Contactos encontrados: X
Almacenes encontrados: X
Contactos con almacén: X
```

### 3. Proceso de Creación de Ruta

Para cada contacto, verás:

```
================================================================================
INICIO _create_client_route - Almacén: [NOMBRE] (ID: X, Código: XXX)
================================================================================
Compañía encontrada: [NOMBRE] (ID: X)
Nombre de ruta generado: 'SUPP_ALISTAMIENTO_SALIDA_TRANSPORTE_XXX'
```

### 4. Búsqueda de Tipos de Operación

```
Buscando tipos de operación para compañía: [NOMBRE]
Buscando tipo de operación 'Alistamiento'...
Tipo de operación Alistamiento encontrado: [NOMBRE] (ID: X)
```

**⚠️ Si ves esto, hay un problema:**
```
ERROR: No se encontró tipo de operación 'Alistamiento'
Tipos de operación disponibles en la compañía: [...]
```

### 5. Búsqueda de Ubicaciones

```
Buscando ubicaciones del sistema...
Ubicación Existencias: ENCONTRADA - Supp/Existencias
Ubicación Alistamiento: ENCONTRADA - Supp/Alistamiento
Ubicación Salida: ENCONTRADA - Supp/Salida
Ubicación Transporte: ENCONTRADA - Supp/Transporte
```

**⚠️ Si ves esto, hay un problema:**
```
ERROR: No se encontró la ubicación 'Supp/Existencias'
```

### 6. Creación de Reglas

Para cada regla verás:

```
Creando Regla 1: Existencias - Alistamiento
Valores Regla 1: {...}
Regla 1 creada exitosamente (ID: X)
```

**⚠️ Si hay error:**
```
ERROR al crear Regla 1: [MENSAJE DE ERROR]
```

## 🚨 Errores Comunes y Soluciones

### Error 1: "No se encontraron los siguientes tipos de operación"

**Síntoma en logs:**
```
ERROR: No se encontró tipo de operación 'Alistamiento'
ERROR: No se encontró tipo de operación 'Salida'
ERROR: No se encontró tipo de operación 'Transporte'
```

**Solución:**
1. Ve a: **Inventario → Configuración → Tipos de Operación**
2. Verifica que existan estos tipos con estos nombres exactos:
   - `SUPPLIES DE COLOMBIA SAS: Alistamiento`
   - `SUPPLIES DE COLOMBIA SAS: Salida`
   - `SUPPLIES DE COLOMBIA SAS: Transporte`
3. Si no existen, créalos o ajusta los nombres en el código

### Error 2: "No se encontró la ubicación 'Supp/Existencias'"

**Síntoma en logs:**
```
ERROR: No se encontró la ubicación 'Supp/Existencias'
```

**Solución:**
1. Ve a: **Inventario → Configuración → Ubicaciones**
2. Verifica que existan estas ubicaciones con estos nombres exactos:
   - `Supp/Existencias`
   - `Supp/Alistamiento`
   - `Supp/Salida`
   - `Supp/Transporte`
3. Si no existen, créalas o ajusta los nombres en el código

### Error 3: "No se encontró el tipo de operación de entrega para el almacén"

**Síntoma en logs:**
```
ERROR: No se encontró el tipo de operación de entrega para el almacén '[NOMBRE]'
```

**Solución:**
1. Ve al almacén: **Inventario → Configuración → Almacenes**
2. Verifica que el almacén tenga configurado el tipo de operación de entrega
3. Si no lo tiene, configúralo manualmente

### Error 4: "No se encontró la ubicación de existencias (lot_stock_id)"

**Síntoma en logs:**
```
ERROR: No se encontró la ubicación de existencias (lot_stock_id) para el almacén '[NOMBRE]'
```

**Solución:**
1. Esto indica que el almacén no se creó correctamente
2. Verifica que el almacén tenga todas sus ubicaciones creadas
3. Puede ser necesario recrear el almacén

### Error 5: "Error al crear Regla X"

**Síntoma en logs:**
```
ERROR al crear Regla 1: [MENSAJE DE ERROR ESPECÍFICO]
```

**Solución:**
1. Revisa el mensaje de error específico en los logs
2. Puede ser un problema de permisos, datos faltantes, o restricciones de base de datos
3. Verifica que todos los IDs referenciados existan

## 📝 Ejemplo de Log Exitoso

```
================================================================================
=== INICIO: action_create_all_routes ===
================================================================================
Contactos encontrados: 5
Almacenes encontrados: 5
Contactos con almacén: 5
Iniciando creación de rutas para 5 contactos
Procesando contacto 123 (EMPRESA ABC): ruta 'SUPP_ALISTAMIENTO_SALIDA_TRANSPORTE_EMPRE'
================================================================================
INICIO _create_client_route - Almacén: EMPRESA ABC (ID: 10, Código: EMPRE)
================================================================================
Compañía encontrada: Supplies de Colombia (ID: 1)
Nombre de ruta generado: 'SUPP_ALISTAMIENTO_SALIDA_TRANSPORTE_EMPRE'
Ruta creada exitosamente: stock.route(11) (ID: 11)
Iniciando creación de reglas de stock para la ruta 'SUPP_ALISTAMIENTO_SALIDA_TRANSPORTE_EMPRE' (ID: 11)
Buscando tipos de operación para compañía: Supplies de Colombia (ID: 1)
Tipo de operación Alistamiento encontrado: SUPPLIES DE COLOMBIA SAS: Alistamiento (ID: 5)
Tipo de operación Salida encontrado: SUPPLIES DE COLOMBIA SAS: Salida (ID: 6)
Tipo de operación Transporte encontrado: SUPPLIES DE COLOMBIA SAS: Transporte (ID: 7)
Ubicación Existencias: ENCONTRADA - Supp/Existencias
Ubicación Alistamiento: ENCONTRADA - Supp/Alistamiento
Ubicación Salida: ENCONTRADA - Supp/Salida
Ubicación Transporte: ENCONTRADA - Supp/Transporte
Creando Regla 1: Existencias - Alistamiento
Regla 1 creada exitosamente (ID: 50)
Creando Regla 2: Alistamiento - Salida
Regla 2 creada exitosamente (ID: 51)
Creando Regla 3: Salida - Transporte
Regla 3 creada exitosamente (ID: 52)
Creando Regla 4: Transporte - EMPRE
Regla 4 creada exitosamente (ID: 53)
Todas las reglas de stock creadas exitosamente para la ruta SUPP_ALISTAMIENTO_SALIDA_TRANSPORTE_EMPRE (ID: 11)
```

## 🔧 Filtros Útiles para Buscar en los Logs

### Buscar solo errores:
```bash
# Windows PowerShell
Select-String -Path odoo-server.log -Pattern "ERROR"

# Linux
grep "ERROR" odoo-server.log
```

### Buscar solo el proceso de creación de rutas:
```bash
# Windows PowerShell
Select-String -Path odoo-server.log -Pattern "action_create_all_routes|_create_client_route|_create_route_rules"

# Linux
grep -E "action_create_all_routes|_create_client_route|_create_route_rules" odoo-server.log
```

### Buscar un contacto específico:
```bash
# Windows PowerShell
Select-String -Path odoo-server.log -Pattern "Contacto.*123"

# Linux
grep "Contacto.*123" odoo-server.log
```

## 📞 Siguiente Paso

Si después de revisar los logs sigues teniendo problemas:

1. **Copia los logs completos** desde "INICIO: action_create_all_routes" hasta el final
2. **Identifica el primer ERROR** que aparece
3. **Revisa la sección de "Errores Comunes"** arriba para encontrar la solución
4. Si el error no está listado, comparte el log completo para análisis

## ✅ Verificación Rápida

Antes de ejecutar el proceso, verifica que existan:

- [ ] Compañía "Supplies de Colombia" (ID=1)
- [ ] Tipo de operación "SUPPLIES DE COLOMBIA SAS: Alistamiento"
- [ ] Tipo de operación "SUPPLIES DE COLOMBIA SAS: Salida"
- [ ] Tipo de operación "SUPPLIES DE COLOMBIA SAS: Transporte"
- [ ] Ubicación "Supp/Existencias"
- [ ] Ubicación "Supp/Alistamiento"
- [ ] Ubicación "Supp/Salida"
- [ ] Ubicación "Supp/Transporte"
- [ ] Al menos un almacén con partner_id configurado

