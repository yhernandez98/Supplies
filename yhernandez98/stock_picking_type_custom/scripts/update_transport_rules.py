#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para actualizar todas las reglas "Salida - Transporte" 
con picking_type_id = 43

Uso:
    python3 update_transport_rules.py
    o desde la consola de Odoo:
    odoo-bin shell -d nombre_base_datos -u stock_picking_type_custom
    >>> env['stock.rule'].update_transport_rules_picking_type()
"""

import sys
import os

# Agregar el directorio del módulo al path si es necesario
# sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def update_transport_rules():
    """
    Función que puede ser llamada desde la consola de Odoo
    para actualizar todas las reglas "Salida - Transporte"
    """
    print("Iniciando actualización de reglas 'Salida - Transporte'...")
    
    # Buscar todas las reglas con nombre "Salida - Transporte"
    transport_rules = env['stock.rule'].search([
        ('name', '=', 'Salida - Transporte'),
    ])
    
    if not transport_rules:
        print("No se encontraron reglas 'Salida - Transporte' para actualizar.")
        return
    
    print(f"Se encontraron {len(transport_rules)} reglas 'Salida - Transporte'")
    
    # Verificar que el tipo de operación 43 existe
    picking_type_43 = env['stock.picking.type'].browse(43)
    if not picking_type_43.exists():
        print("ERROR: El tipo de operación con ID 43 no existe.")
        return
    
    print(f"Tipo de operación 43 encontrado: {picking_type_43.name}")
    
    # Actualizar las reglas
    updated_count = 0
    already_updated_count = 0
    errors = []
    
    for rule in transport_rules:
        try:
            if rule.picking_type_id.id == 43:
                already_updated_count += 1
                print(f"  ✓ Regla '{rule.name}' (ID: {rule.id}) ya tiene picking_type_id = 43")
            else:
                old_picking_type = rule.picking_type_id.name if rule.picking_type_id else 'Sin tipo'
                rule.write({'picking_type_id': 43})
                updated_count += 1
                print(f"  ✓ Regla '{rule.name}' (ID: {rule.id}) actualizada: {old_picking_type} → {picking_type_43.name}")
        except Exception as e:
            error_msg = str(e)
            errors.append(f"Regla '{rule.name}' (ID: {rule.id}): {error_msg}")
            print(f"  ✗ Error al actualizar regla '{rule.name}' (ID: {rule.id}): {error_msg}")
    
    # Resumen
    print("\n" + "="*60)
    print("RESUMEN DE ACTUALIZACIÓN")
    print("="*60)
    print(f"✅ Reglas actualizadas exitosamente: {updated_count}")
    print(f"ℹ️  Reglas que ya tenían picking_type_id = 43: {already_updated_count}")
    if errors:
        print(f"❌ Errores encontrados: {len(errors)}")
        for error in errors:
            print(f"   - {error}")
    print("="*60)
    
    return {
        'updated': updated_count,
        'already_updated': already_updated_count,
        'errors': len(errors),
    }

if __name__ == '__main__':
    print("Este script debe ejecutarse desde la consola de Odoo:")
    print("  odoo-bin shell -d nombre_base_datos")
    print("  >>> env['stock.rule'].update_transport_rules_picking_type()")
    print("\nO usar la acción de servidor desde la interfaz de Odoo.")

