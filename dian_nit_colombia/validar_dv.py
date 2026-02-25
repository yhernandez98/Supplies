#!/usr/bin/env python3
# -*- coding: utf-8 -*-

weights = [41, 37, 29, 23, 19, 17, 13, 7, 3]

# Caso 1: 800073584 -> DV esperado: 4
nit1 = '800073584'
total1 = sum(int(nit1[i]) * weights[i] for i in range(len(nit1)))
remainder1 = total1 % 11
dv1 = '0' if remainder1 < 2 else str(11 - remainder1)

print('=== VALIDACIÓN ALGORITMO DIAN ===')
print(f'NIT: {nit1}')
print(f'DV Esperado: 4')
print(f'DV Calculado: {dv1}')
print(f'Total: {total1}, Residuo: {remainder1}')
print()

# Caso 2: 900877788 -> DV esperado: 3
nit2 = '900877788'
total2 = sum(int(nit2[i]) * weights[i] for i in range(len(nit2)))
remainder2 = total2 % 11
dv2 = '0' if remainder2 < 2 else str(11 - remainder2)

print(f'NIT: {nit2}')
print(f'DV Esperado: 3')
print(f'DV Calculado: {dv2}')
print(f'Total: {total2}, Residuo: {remainder2}')
print()

if dv1 == '4' and dv2 == '3':
    print('✅ Algoritmo corregido correctamente')
else:
    print('❌ Error en el algoritmo')

