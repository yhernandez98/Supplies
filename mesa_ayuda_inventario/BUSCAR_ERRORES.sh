#!/bin/bash
# Script para buscar errores relacionados con mesa_ayuda_inventario

echo "=========================================="
echo "🔍 BUSCANDO ERRORES - Mesa de Ayuda"
echo "=========================================="
echo ""

LOG_FILE="/var/log/odoo/odoo-server.log"

# Verificar si el archivo existe
if [ ! -f "$LOG_FILE" ]; then
    echo "⚠️ Archivo no encontrado: $LOG_FILE"
    echo "Buscando archivo de log..."
    
    # Buscar archivos de log comunes
    POSSIBLE_LOGS=(
        "/var/log/odoo/odoo.log"
        "/opt/odoo/log/odoo-server.log"
        "/opt/odoo/log/odoo.log"
        "/var/log/odoo-server.log"
    )
    
    for log in "${POSSIBLE_LOGS[@]}"; do
        if [ -f "$log" ]; then
            LOG_FILE="$log"
            echo "✅ Encontrado: $LOG_FILE"
            break
        fi
    done
    
    if [ ! -f "$LOG_FILE" ]; then
        echo "❌ No se encontró archivo de log. Buscando procesos de Odoo..."
        ps aux | grep odoo | grep -v grep | head -3
        echo ""
        echo "Por favor, ejecuta manualmente:"
        echo "sudo find /var/log -name '*odoo*.log' 2>/dev/null"
        echo "sudo find /opt -name '*odoo*.log' 2>/dev/null"
        exit 1
    fi
fi

echo "📁 Archivo de log: $LOG_FILE"
echo ""

echo "=========================================="
echo "1️⃣ ÚLTIMOS ERRORES GENERALES (últimos 30)"
echo "=========================================="
sudo grep -i "error\|exception\|traceback" "$LOG_FILE" | tail -30
echo ""

echo "=========================================="
echo "2️⃣ ERRORES DEL MÓDULO mesa_ayuda_inventario"
echo "=========================================="
sudo grep -i "mesa_ayuda" "$LOG_FILE" | tail -30
echo ""

echo "=========================================="
echo "3️⃣ ERRORES AL CARGAR MÓDULOS"
echo "=========================================="
sudo grep -iE "Module loading|module.*mesa_ayuda|External ID.*mesa_ayuda|model.*mesa_ayuda" "$LOG_FILE" | tail -30
echo ""

echo "=========================================="
echo "4️⃣ ERRORES RELACIONADOS CON HELPDESK/REPAIR"
echo "=========================================="
sudo grep -iE "helpdesk\.ticket|repair\.order|model_helpdesk|model_repair|External ID.*helpdesk|External ID.*repair" "$LOG_FILE" | tail -30
echo ""

echo "=========================================="
echo "5️⃣ ÚLTIMO TRACEBACK COMPLETO"
echo "=========================================="
sudo grep -B 3 -A 50 "Traceback" "$LOG_FILE" | tail -60
echo ""

echo "=========================================="
echo "6️⃣ ERRORES DE VISTAS O ARCHIVOS XML"
echo "=========================================="
sudo grep -iE "External ID not found|Invalid field|XML|view.*not found" "$LOG_FILE" | grep -i "mesa_ayuda\|helpdesk\|repair" | tail -20
echo ""

echo "=========================================="
echo "✅ BÚSQUEDA COMPLETADA"
echo "=========================================="
echo ""
echo "💡 TIP: Copia las secciones con errores y compártelas para análisis"

