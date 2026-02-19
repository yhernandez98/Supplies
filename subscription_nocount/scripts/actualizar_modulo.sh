#!/bin/bash
# =============================================================================
# Actualizar el módulo subscription_nocount SIN usar la interfaz de Aplicaciones.
# Ejecutar en el servidor donde corre Odoo.
# =============================================================================
# Uso: ./actualizar_modulo.sh NOMBRE_BASE_DATOS
# Ejemplo: ./actualizar_modulo.sh odoo_produccion
# =============================================================================

BASE_DATOS="${1:-}"
if [ -z "$BASE_DATOS" ]; then
    echo "Uso: $0 NOMBRE_BASE_DATOS"
    echo "Ejemplo: $0 odoo_produccion"
    exit 1
fi

# Ruta típica del ejecutable de Odoo (ajustar si es distinta)
ODOO_BIN="odoo"
if [ -f /usr/bin/odoo ]; then
    ODOO_BIN="/usr/bin/odoo"
elif [ -f /opt/odoo/odoo-bin ]; then
    ODOO_BIN="/opt/odoo/odoo-bin"
fi

echo "Actualizando módulo subscription_nocount en base: $BASE_DATOS"
$ODOO_BIN -u subscription_nocount -d "$BASE_DATOS" --stop-after-init

echo "Listo. Reinicia Odoo con normalidad (sin --stop-after-init) y entra por Ventas > Suscripciones."
