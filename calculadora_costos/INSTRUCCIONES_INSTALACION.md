# 📦 Instrucciones de Instalación - Calculadora de Costos

## Instalación Rápida

### Paso 1: Verificar Ubicación del Módulo

El módulo debe estar en:
```
custom_addons_Productiva/calculadora_costos/
```

### Paso 2: Actualizar Lista de Aplicaciones en Odoo

1. Iniciar sesión en Odoo como administrador
2. Ir a: **Aplicaciones** (Apps)
3. Clic en **Actualizar lista de aplicaciones** (Update Apps List)
4. Esperar a que termine la actualización

### Paso 3: Instalar el Módulo

1. En la barra de búsqueda de aplicaciones, escribir: **"Calculadora de Costos"**
2. Buscar el módulo: **"Calculadora de Costos y Renting"**
3. Clic en el botón **Instalar** (Install)
4. Esperar a que termine la instalación

### Paso 4: Verificar Instalación

1. Debe aparecer el menú **"Calculadora de Costos"** en el menú principal
2. Si no aparece, verificar que el módulo esté en modo desarrollador o actualizar la lista de aplicaciones

### Paso 5: Configuración Inicial

1. Ir a: **Calculadora de Costos** → **Configuración** → **Parámetros Financieros**
2. Verificar y ajustar los valores por defecto según sea necesario
3. Guardar

## ✅ Verificación de Instalación Correcta

Después de instalar, verifica que existan los siguientes menús:

- ✅ **Calculadora de Costos** (menú principal)
  - ✅ Calculadora de Equipos
  - ✅ Calculadora de Renting
  - ✅ APU - Servicios
  - ✅ Configuración
    - ✅ Parámetros Financieros

## 🔧 Solución de Problemas

### El módulo no aparece en la lista de aplicaciones

**Solución:**
1. Verificar que el módulo esté en la ruta correcta
2. Verificar permisos de lectura en la carpeta
3. Actualizar la lista de aplicaciones nuevamente
4. Si usas modo desarrollador, verificar que esté activado

### Error al instalar: "Module not found"

**Solución:**
1. Verificar que el archivo `__manifest__.py` exista
2. Verificar que el archivo `__init__.py` exista
3. Verificar la sintaxis de los archivos XML
4. Revisar los logs de Odoo para más detalles

### Error: "Missing dependencies"

**Solución:**
1. Verificar que los módulos `base`, `product`, `sale` estén instalados
2. Instalar las dependencias faltantes primero
3. Luego instalar este módulo

### Los menús no aparecen después de instalar

**Solución:**
1. Actualizar la lista de aplicaciones
2. Reiniciar el servidor de Odoo
3. Limpiar la caché del navegador
4. Verificar que el usuario tenga permisos adecuados

## 📝 Notas Importantes

- El módulo requiere Odoo 18.0 o superior
- Se recomienda hacer una copia de seguridad antes de instalar
- Los parámetros financieros se crean automáticamente con valores por defecto
- Puedes modificar los parámetros después de la instalación

## 🆘 Soporte

Si tienes problemas con la instalación:
1. Revisar los logs de Odoo
2. Verificar la documentación en `README.md`
3. Contactar al equipo de desarrollo

---

*Última actualización: [Fecha actual]*
