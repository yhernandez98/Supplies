#!/usr/bin/env python3
# -*- coding: utf-8 -*-

weights = [41, 37, 29, 23, 19, 17, 13, 7, 3]

# NIT a probar
nit = '900419513'

print('=' * 60)
print('VALIDACIÓN NIT 900419513')
print('=' * 60)
print(f'\nNIT: {nit}\n')
print('Cálculo detallado:')
print('-' * 60)

total = 0
for i, digit in enumerate(nit):
    peso = weights[i]
    producto = int(digit) * peso
    total += producto
    print(f'  Dígito {i+1}: {digit} × {peso:2d} = {producto:4d}')

print('-' * 60)
print(f'Suma total: {total}')
remainder = total % 11
print(f'Residuo ({total} % 11): {remainder}')

if remainder < 2:
    dv = '0'
else:
    dv = str(11 - remainder)

print(f'\nDígito de Verificación: {dv}')
print('=' * 60)
print(f'\n✅ NIT Completo: {nit}-{dv}')
print('=' * 60)

