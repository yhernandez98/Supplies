# 🔍 Diferencia entre Tasa Efectiva en Excel y Odoo

## Problema Reportado

**Usuario reporta:**
- Excel calcula: **23.26%** de tasa efectiva anual
- Odoo calcula: **23.14%** de tasa efectiva anual
- Tasa nominal: **21%** (igual en ambos)
- Tasa mensual: **1.75%** (igual en ambos)

**Diferencia:** 0.12 puntos porcentuales

---

## Análisis del Cálculo

### Fórmula Estándar (Correcta)

La fórmula para calcular la tasa efectiva anual con capitalización mensual es:

```
Tasa Efectiva = ((1 + Tasa Nominal/12)^12 - 1) × 100
```

### Cálculo con Tasa Nominal 21%

**Paso a paso:**
1. Tasa Nominal: 21%
2. Tasa Mensual: 21% / 12 = 1.75% = 0.0175
3. Factor: (1 + 0.0175) = 1.0175
4. Factor elevado a 12: (1.0175)^12 = 1.2314393149
5. Tasa Efectiva: (1.2314393149 - 1) × 100 = **23.1439%**

**Resultado correcto:** 23.14% (redondeado a 2 decimales)

---

## ¿Por qué Excel muestra 23.26%?

Hay varias posibles razones para esta diferencia:

### 1. **Precisión Numérica de Excel**

Excel puede estar usando:
- Más decimales internamente en los cálculos intermedios
- Redondeo diferente en cada paso
- Precisión de punto flotante diferente

**Ejemplo:**
- Si Excel redondea la tasa mensual a 1.75% pero internamente usa más decimales
- O si Excel redondea el factor (1.0175)^12 en algún paso intermedio

### 2. **Función EFFECT de Excel**

Excel tiene la función `EFFECT(nominal_rate, npery)` que calcula la tasa efectiva.

**Sintaxis:**
```
=EFFECT(0.21, 12)
```

**Posibles diferencias:**
- Excel puede estar usando una precisión diferente
- Excel puede estar redondeando de manera diferente
- La celda en Excel puede tener formato que redondea el resultado

### 3. **Tasa Nominal Diferente (No Visible)**

Es posible que en Excel estés usando una tasa nominal ligeramente diferente sin darte cuenta:

**Cálculo inverso:**
- Si Excel da 23.26% efectiva, la tasa nominal necesaria sería:
  - Tasa Mensual: (1.2326^(1/12) - 1) = 0.0176 = 1.76%
  - Tasa Nominal: 1.76% × 12 = **21.12%**

**Conclusión:** Si Excel muestra 23.26%, podría estar usando 21.12% como tasa nominal (no 21% exacto).

### 4. **Capitalización Diferente**

Excel podría estar usando:
- Capitalización diaria (365 períodos) en lugar de mensual (12 períodos)
- Capitalización continua
- Otro período de capitalización

**Comparación:**
```
Capitalización Mensual (12 períodos): 23.14%
Capitalización Diaria (365 períodos): 23.25%
Capitalización Continua: 23.34%
```

Si Excel usa capitalización diaria, daría aproximadamente 23.25%, que está más cerca de 23.26%.

---

## Verificación del Cálculo en Odoo

### Código Actual

```python
tasa_mensual_decimal = (record.tasa_nominal / 100.0) / 12.0
tasa_efectiva = ((1 + tasa_mensual_decimal) ** 12) - 1
record.tasa_efectiva_anual = tasa_efectiva * 100.0
```

### Cálculo con Precisión Mejorada

El código ha sido actualizado para usar `Decimal` con mayor precisión:

```python
tasa_nominal_decimal = Decimal(str(record.tasa_nominal)) / Decimal('100')
tasa_mensual_decimal = tasa_nominal_decimal / Decimal('12')
uno_mas_tasa = Decimal('1') + tasa_mensual_decimal
factor = uno_mas_tasa ** 12
tasa_efectiva_decimal = factor - Decimal('1')
record.tasa_efectiva_anual = float(tasa_efectiva_decimal * Decimal('100'))
```

**Resultado:** 23.1439% (correcto según la fórmula estándar)

---

## Recomendaciones

### 1. **Verificar la Tasa Nominal en Excel**

Asegúrate de que en Excel estés usando exactamente **21%** (no 21.12% o cualquier otro valor).

**Cómo verificar:**
1. Abre la celda donde ingresas la tasa nominal
2. Verifica que el valor sea exactamente `21` o `0.21` (dependiendo del formato)
3. Revisa si hay fórmulas que modifiquen este valor

### 2. **Verificar la Función EFFECT en Excel**

Si estás usando la función `EFFECT`, verifica:

```
=EFFECT(0.21, 12)
```

**Parámetros:**
- Primer parámetro: Tasa nominal en **decimal** (0.21 para 21%)
- Segundo parámetro: Número de períodos de capitalización (12 para mensual)

**Si usas porcentaje:**
```
=EFFECT(21%, 12)  ❌ Incorrecto (Excel puede interpretarlo mal)
=EFFECT(0.21, 12) ✅ Correcto
```

### 3. **Verificar el Formato de la Celda**

El formato de la celda en Excel puede estar redondeando el resultado:

1. Selecciona la celda con la tasa efectiva
2. Click derecho → "Formato de celdas"
3. Verifica cuántos decimales muestra
4. Aumenta los decimales para ver el valor exacto

### 4. **Comparar Cálculo Manual**

Haz el cálculo manualmente en Excel:

```
Celda A1: 21 (tasa nominal)
Celda A2: =A1/12 (tasa mensual)
Celda A3: =1+A2/100 (1 + tasa mensual decimal)
Celda A4: =A3^12 (factor elevado a 12)
Celda A5: =(A4-1)*100 (tasa efectiva)
```

Esto te mostrará el valor exacto en cada paso.

---

## Tabla de Comparación

| Tasa Nominal | Capitalización | Tasa Efectiva (Fórmula Estándar) | Posible Excel |
|--------------|----------------|-----------------------------------|---------------|
| 21% | Mensual (12) | 23.14% | 23.26% |
| 21.12% | Mensual (12) | 23.26% | 23.26% |
| 21% | Diaria (365) | 23.25% | 23.26% |

---

## Conclusión

El cálculo en **Odoo es correcto** según la fórmula estándar de tasa efectiva anual con capitalización mensual:

**Resultado correcto:** 23.14% (o 23.1439% con más decimales)

**Si Excel muestra 23.26%, las posibles causas son:**

1. ✅ **Tasa nominal diferente** (21.12% en lugar de 21%)
2. ✅ **Capitalización diferente** (diaria en lugar de mensual)
3. ✅ **Redondeo o precisión** en los cálculos intermedios de Excel
4. ✅ **Formato de celda** que redondea el resultado mostrado

**Recomendación:** Verifica en Excel:
- El valor exacto de la tasa nominal
- La función o fórmula que estás usando
- El formato de la celda del resultado
- Si estás usando capitalización mensual o diaria

---

## Fórmula de Referencia

### Tasa Efectiva Anual (Capitalización Mensual)

```
TEA = ((1 + TN/12)^12 - 1) × 100

Donde:
- TEA = Tasa Efectiva Anual (%)
- TN = Tasa Nominal Anual (%)
- 12 = Número de períodos de capitalización por año (mensual)
```

### Ejemplo con 21% Nominal

```
TEA = ((1 + 21/12/100)^12 - 1) × 100
TEA = ((1 + 0.0175)^12 - 1) × 100
TEA = (1.2314393149 - 1) × 100
TEA = 23.1439%
```

---

*Documento actualizado: [Fecha actual]*
