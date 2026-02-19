# Resumen: Sistema de Limpieza de Rutas y Reglas

## 📦 Lo que se ha creado

### 1. **Wizard de Limpieza** (`cleanup_routes_wizard.py`)
Un wizard interactivo que permite:
- ✅ Analizar rutas, reglas y tipos de operación no utilizados
- ✅ Verificar uso en productos, ventas y almacenes
- ✅ Desactivar o eliminar elementos no utilizados
- ✅ Generar logs detallados de todas las operaciones

### 2. **Guía Completa** (`GUIA_LIMPIEZA_RUTAS_REGLAS.md`)
Documentación con:
- ✅ Advertencias y mejores prácticas
- ✅ Checklist de seguridad
- ✅ Scripts SQL para análisis
- ✅ Qué hacer y qué NO hacer

## 🚀 Cómo Usar el Wizard

### Paso 1: Acceder al Wizard
1. Ve a: **Inventario → Configuración → Limpieza de Rutas y Reglas**
2. O busca la acción desde el menú

### Paso 2: Configurar Filtros
- **Patrón de Nombre**: `SUPP_ALISTAMIENTO_SALIDA_TRANSPORTE_%` (o el que necesites)
- **Compañía**: Selecciona la compañía
- **Solo Inactivos**: Marca si solo quieres ver elementos inactivos

### Paso 3: Configurar Verificaciones
Marca las verificaciones que quieres hacer:
- ✅ Verificar Uso en Productos
- ✅ Verificar Uso en Ventas
- ✅ Verificar Uso en Almacenes

### Paso 4: Analizar
1. Haz clic en **"Analizar"**
2. Revisa los resultados en las pestañas:
   - **Rutas**: Rutas no utilizadas encontradas
   - **Reglas**: Reglas asociadas a esas rutas
   - **Tipos de Operación**: Tipos no utilizados

### Paso 5: Ejecutar Limpieza
1. Selecciona el **Modo de Acción**:
   - **Solo Analizar**: Solo muestra resultados (por defecto)
   - **Desactivar**: Marca como inactivo (recomendado primero)
   - **Eliminar Definitivamente**: Elimina permanentemente (¡cuidado!)

2. Haz clic en **"Ejecutar Limpieza"**

## ⚠️ Recomendación de Uso

### Flujo Recomendado:

1. **Primera vez:**
   - Modo: **"Solo Analizar"**
   - Revisa los resultados
   - Verifica manualmente algunos elementos

2. **Segunda vez (después de verificar):**
   - Modo: **"Desactivar"**
   - Desactiva los elementos
   - Espera unos días para verificar que no hay problemas

3. **Tercera vez (si todo está bien):**
   - Modo: **"Eliminar Definitivamente"**
   - Elimina permanentemente

## 🔍 Qué Verifica el Wizard

### Para Rutas:
- ✅ No está asignada a productos
- ✅ No está en órdenes de venta
- ✅ No está asociada a almacenes

### Para Reglas:
- ✅ Se eliminan automáticamente si su ruta está marcada para eliminación

### Para Tipos de Operación:
- ✅ No está asociado a ningún almacén
- ✅ No tiene pickings activos o en proceso

## 📊 Logs Generados

El wizard genera logs detallados en `odoo-server.log`:
- Análisis de cada elemento
- Razones por las que se marca como no utilizado
- Resultados de la limpieza
- Errores si los hay

## 🛡️ Seguridad

- ✅ **No elimina tipos de operación** directamente (solo desactiva)
- ✅ **Verifica uso** antes de marcar para eliminación
- ✅ **Genera logs** de todas las operaciones
- ✅ **Permisos**: Solo usuarios con `stock.group_stock_manager`

## 📝 Notas Importantes

1. **Siempre haz backup** antes de eliminar
2. **Prueba primero con "Desactivar"** antes de eliminar
3. **Revisa los logs** después de cada operación
4. **No elimines tipos de operación** que puedan estar en uso indirectamente

## 🔧 Personalización

Si necesitas ajustar los criterios de "no utilizado", edita el método `action_analyze()` en `cleanup_routes_wizard.py`.

