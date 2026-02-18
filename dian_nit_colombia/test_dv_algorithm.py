#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de prueba para validar el algoritmo de cálculo del dígito de verificación DIAN
"""

def calcular_dv_dian(nit_number):
    """
    Calcula el dígito de verificación según el algoritmo oficial DIAN
    
    Algoritmo oficial DIAN:
    1. Se toman los 9 pesos: [41, 37, 29, 23, 19, 17, 13, 7, 3]
    2. Se aplican de IZQUIERDA A DERECHA (del primer dígito al último)
    3. Se multiplica cada dígito por su peso correspondiente
    4. Se suman todos los productos
    5. Se calcula el residuo de la división por 11
    6. Si el residuo es 0 o 1, el DV es 0
    7. Si el residuo es mayor que 1, el DV es 11 - residuo
    """
    if not nit_number or not nit_number.isdigit():
        return False
    
    # Algoritmo DIAN oficial: 9 pesos aplicados de IZQUIERDA A DERECHA
    weights = [41, 37, 29, 23, 19, 17, 13, 7, 3]
    
    # Aplicar pesos de izquierda a derecha (sin invertir)
    total = 0
    detalles = []
    for i, digit in enumerate(nit_number):
        if i < len(weights):
            producto = int(digit) * weights[i]
            total += producto
            detalles.append(f"{digit}×{weights[i]}={producto}")
    
    remainder = total % 11
    # Si el residuo es 0 o 1, el DV es 0 (no el residuo mismo)
    if remainder < 2:
        dv = '0'
    else:
        dv = str(11 - remainder)
    
    return {
        'nit': nit_number,
        'detalles': detalles,
        'total': total,
        'residuo': remainder,
        'dv': dv
    }


# Casos de prueba proporcionados por el usuario
casos_prueba = [
    {'nit': '800073584', 'dv_esperado': '4'},
    {'nit': '900877788', 'dv_esperado': '3'},
    # Casos adicionales para validación
    {'nit': '860013715', 'dv_esperado': '4'},  # Del ejemplo en el código
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

