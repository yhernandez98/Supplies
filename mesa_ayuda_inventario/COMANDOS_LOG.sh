#!/bin/bash
# Script para buscar errores en los logs de Odoo

LOG_FILE="/var/log/odoo/odoo-server.log"

echo "=========================================="
echo "🔍 Buscando errores en logs de Odoo"
echo "=========================================="
echo ""

# Verificar si el archivo de log existe
if [ ! -f "$LOG_FILE" ]; then
    echo "⚠️ Archivo de log no encontrado en: $LOG_FILE"
    echo "Por favor, verifica la ruta del archivo de log."
    exit 1
fi

echo "📋 1. Últimos 20 errores generales:"
echo "-----------------------------------"
grep -i "error\|exception\|traceback" "$LOG_FILE" | tail -20
echo ""

echo "📋 2. Errores relacionados con mesa_ayuda_inventario:"
echo "-----------------------------------"
grep -i "mesa_ayuda_inventario" "$LOG_FILE" | tail -20
echo ""

echo "📋 3. Errores de carga de módulos:"
echo "-----------------------------------"
grep -E "loading.*mesa_ayuda|module.*mesa_ayuda|External ID.*mesa_ayuda" "$LOG_FILE" | tail -20
echo ""

echo "📋 4. Errores relacionados con helpdesk o repair:"
echo "-----------------------------------"
grep -E "helpdesk\.ticket|repair\.order|model_helpdesk|model_repair" "$LOG_FILE" | tail -20
echo ""

echo "📋 5. Último traceback completo:"
echo "-----------------------------------"
grep -A 50 "Traceback" "$LOG_FILE" | tail -60
echo ""

echo "✅ Búsqueda completada"
echo ""
echo "💡 TIP: Si encontraste un error, copia todo el traceback completo"

