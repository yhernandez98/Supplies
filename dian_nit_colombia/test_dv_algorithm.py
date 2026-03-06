#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de prueba para validar el algoritmo de cálculo del dígito de verificación DIAN
"""

def calcular_dv_dian(nit_number):
    """
    Calcula el dígito de verificación según el algoritmo oficial DIAN.
    Soporta NIT empresa (9 dígitos) y cédula persona natural (hasta 15 dígitos).
    
    Algoritmo oficial DIAN:
    1. Coeficientes: [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]
    2. Se aplican de DERECHA A IZQUIERDA
    3. Residuo % 11; si > 1: DV = 11 - residuo; si no: DV = residuo
    """
    if not nit_number or not nit_number.isdigit():
        return False
    
    coeficientes = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]
    nit_reversed = nit_number[::-1]
    
    total = 0
    detalles = []
    for i, digit in enumerate(nit_reversed):
        if i < len(coeficientes):
            producto = int(digit) * coeficientes[i]
            total += producto
            detalles.append(f"{digit}×{coeficientes[i]}={producto}")
    
    remainder = total % 11
    if remainder > 1:
        dv = str(11 - remainder)
    else:
        dv = str(remainder)
    
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

