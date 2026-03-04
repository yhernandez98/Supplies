# Cómo ver los logs de Odoo

## Opción 1: Logs en la consola/terminal donde corre Odoo

Si estás ejecutando Odoo desde la terminal, verás los mensajes directamente ahí.

## Opción 2: Logs en el archivo de configuración

Si Odoo está configurado para escribir logs en archivo, revisa el archivo de log configurado.

## Opción 3: Ver logs desde Odoo (modo desarrollador)

1. Activa el **Modo Desarrollador**:
   - Ve a Configuración → Activar modo desarrollador
   - O agrega `?debug=1` al final de la URL

2. Ve a Configuración → Técnico → Logging → Ver registros

3. Busca mensajes que empiecen con:
   - `=== INICIANDO VERIFICACIÓN DE STOCK PARA ORDEN`
   - `>>> Línea`
   - `>>> MENSAJE FINAL`

## Opción 4: Activar logs de depuración

Edita el archivo de configuración de Odoo (`odoo.conf`) y agrega:

```ini
[options]
log_level = debug
log_handler = :DEBUG
```

Luego reinicia Odoo.

## Qué buscar en los logs

Cuando veas la orden de venta, deberías ver mensajes como:

```
=== INICIANDO VERIFICACIÓN DE STOCK PARA ORDEN S00005 ===
Orden S00005 tiene 1 líneas con productos
>>> Línea 123 - Producto: Equipo1 (ID: 456) - Tipo DESDE TEMPLATE: product
>>> ✓ Línea 123 clasificada como PRODUCTO ALMACENABLE (type='product')
=== RESUMEN ORDEN S00005 ===
>>> Productos tipo 'product' (almacenables): 1
>>> Productos tipo 'consu' (consumibles): 0
>>> MENSAJE FINAL: ✓ Stock disponible
```

Si ves `type='consu'` cuando debería ser `type='product'`, entonces el problema está en cómo se está leyendo el tipo desde la base de datos.

