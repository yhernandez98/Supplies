# 📝 Resumen de Cambios: Factor a Porcentaje de Margen

## Cambio Realizado

Se cambió el campo **Factor Margen Servicio** a **Porcentaje Margen Servicio** en la Calculadora de Renting para que use el mismo formato que la Calculadora de Equipos.

---

## Antes y Después

### ANTES (Factor Margen Servicio)

**Campo**: `factor_margen_servicio`
- **Tipo**: Factor decimal (ej: 0.8)
- **Valor por defecto**: 0.8
- **Cálculo**: `Servicio con Margen = Costo Servicios / Factor`
- **Ejemplo**: 
  - Costo: $100,000
  - Factor: 0.8
  - Resultado: $100,000 / 0.8 = $125,000

### AHORA (Porcentaje Margen Servicio)

**Campo**: `porcentaje_margen_servicio`
- **Tipo**: Porcentaje (ej: 25%)
- **Valor por defecto**: 25.0
- **Cálculo**: `Servicio con Margen = Costo Servicios × (1 + Margen/100)`
- **Ejemplo**: 
  - Costo: $100,000
  - Margen: 25%
  - Resultado: $100,000 × 1.25 = $125,000

---

## Equivalencia de Valores

| Factor Anterior | Porcentaje Equivalente | Ejemplo: Costo $100,000 |
|-----------------|------------------------|-------------------------|
| 0.5             | 100%                   | Precio: $200,000        |
| 0.6             | 66.67%                 | Precio: $166,667        |
| 0.7             | 42.86%                 | Precio: $142,857        |
| **0.8**         | **25%**                | **Precio: $125,000**    |
| 0.9             | 11.11%                 | Precio: $111,111        |
| 0.95            | 5.26%                  | Precio: $105,263        |
| 1.0             | 0%                     | Precio: $100,000        |

**Fórmula de conversión:**
```
Porcentaje = ((1 / Factor) - 1) × 100
```

---

## Ventajas del Cambio

1. ✅ **Consistencia**: Ambas calculadoras usan el mismo formato (porcentaje)
2. ✅ **Intuitivo**: Es más fácil entender "25%" que "factor 0.8"
3. ✅ **Estándar**: El formato de porcentaje es más común en negocios
4. ✅ **Fácil de usar**: No necesitas calcular mentalmente qué significa el factor

---

## Archivos Modificados

1. **Modelo**: `calculadora_renting.py`
   - Campo `factor_margen_servicio` → `porcentaje_margen_servicio`
   - Método `_compute_servicio_con_margen()` actualizado

2. **Vista**: `calculadora_renting_views.xml`
   - Campo actualizado en la vista

3. **Documentación**: 
   - `DIFERENCIAS_CALCULADORAS.md` actualizado
   - `FUNCIONAMIENTO_DETALLADO.md` actualizado

---

## Nota Importante

El valor por defecto cambió de **0.8** (factor) a **25%** (porcentaje), que es equivalente:
- Factor 0.8 = Margen 25% sobre el costo
- Ambos producen el mismo resultado: $100,000 → $125,000

---

*Cambio realizado: [Fecha actual]*
