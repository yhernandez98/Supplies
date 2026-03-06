#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de prueba para validar el algoritmo de cálculo del dígito de verificación DIAN
"""

def calcular_dv_dian(nit_number):
    """
    Algoritmo oficial DIAN (Oracle ORA_CO_NIT).
    NIT 9 dígitos: [41,37,29,23,19,17,13,7,3] IZQ→DER
    NIT 10-15 dígitos: rellenar a 15, [71,67,59,53,47,43,41,37,29,23,19,17,13,7,3] IZQ→DER
    """
    if not nit_number or not nit_number.isdigit():
        return False
    
    nit_len = len(nit_number)
    if nit_len <= 9:
        coef = [41, 37, 29, 23, 19, 17, 13, 7, 3]
        nit_pad = nit_number
    else:
        coef = [71, 67, 59, 53, 47, 43, 41, 37, 29, 23, 19, 17, 13, 7, 3]
        nit_pad = nit_number.zfill(15)[-15:]
    
    total = 0
    detalles = []
    for i, digit in enumerate(nit_pad):
        if i < len(coef):
            p = int(digit) * coef[i]
            total += p
            detalles.append(f"{digit}×{coef[i]}={p}")
    
    remainder = total % 11
    dv = str(remainder) if remainder < 2 else str(11 - remainder)
    
    return {
        'nit': nit_number,
        'detalles': detalles,
        'total': total,
        'residuo': remainder,
        'dv': dv
    }


# Casos de prueba: NIT empresa (9 dígitos) y cédula persona natural
casos_prueba = [
    {'nit': '800073584', 'dv_esperado': '4'},
    {'nit': '900877788', 'dv_esperado': '3'},
    {'nit': '860013715', 'dv_esperado': '4'},
    {'nit': '811026552', 'dv_esperado': '9'},   # Cédula persona natural
]

print("=" * 80)
print("VALIDACIÓN DEL ALGORITMO DE DÍGITO DE VERIFICACIÓN DIAN")
print("=" * 80)
print()

for caso in casos_prueba:
    resultado = calcular_dv_dian(caso['nit'])
    dv_correcto = resultado['dv'] == caso['dv_esperado']
    estado = "✅ CORRECTO" if dv_correcto else "❌ INCORRECTO"
    
    print(f"NIT: {caso['nit']}")
    print(f"DV Esperado: {caso['dv_esperado']}")
    print(f"DV Calculado: {resultado['dv']}")
    print(f"Estado: {estado}")
    print(f"Detalles del cálculo:")
    print(f"  {' + '.join(resultado['detalles'])}")
    print(f"  Total: {resultado['total']}")
    print(f"  Residuo: {resultado['residuo']} (de {resultado['total']} % 11)")
    print(f"  DV: {resultado['dv']}")
    print("-" * 80)
    print()

print("=" * 80)
print("RESUMEN")
print("=" * 80)
correctos = sum(1 for caso in casos_prueba if calcular_dv_dian(caso['nit'])['dv'] == caso['dv_esperado'])
total = len(casos_prueba)
print(f"Casos correctos: {correctos}/{total}")
if correctos == total:
    print("✅ Todos los casos de prueba pasaron correctamente")
else:
    print("❌ Algunos casos fallaron")

