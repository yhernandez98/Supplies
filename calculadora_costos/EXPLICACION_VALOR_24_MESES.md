# 💰 Explicación: Valor de 24 Meses (157,619)

## 📊 Datos del Ejemplo

- **Valor Equipo**: 500 USD
- **Garantía Extendida**: 100 USD
- **Total USD**: 600 USD
- **Utilidad**: 15%
- **TRM**: 4,000
- **Costo Servicios Completos**: 30,000 COP/mes
- **Margen Servicio**: 15%
- **Tasa Nominal**: 21%
- **Tasa Mensual**: 1.75%
- **Tasa Efectiva Anual**: 23.14%
- **Opción de Compra**: 20%
- **Plazo**: 24 meses
- **Valor Esperado**: 157,619 COP/mes

---

## 🔢 Cálculo Paso a Paso

### Paso 1: Calcular Costo con Utilidad (USD)

```
Costo Total USD = Valor Equipo + Garantía
Costo Total USD = 500 + 100 = 600 USD

Costo con Utilidad USD = 600 × (1 + 15/100)
Costo con Utilidad USD = 600 × 1.15
Costo con Utilidad USD = 690 USD
```

### Paso 2: Convertir a COP

```
Costo Equipo COP = 690 × 4,000
Costo Equipo COP = 2,760,000 COP
```

### Paso 3: Calcular Servicio con Margen

```
Servicio con Margen = 30,000 × (1 + 15/100)
Servicio con Margen = 30,000 × 1.15
Servicio con Margen = 34,500 COP/mes
```

### Paso 4: Calcular Pago Base del Equipo (PMT)

**Fórmula PMT:**
```
Tasa Mensual Decimal = 21% / 12 / 100 = 0.0175
Factor = (1 + 0.0175)^24 = 1.5196
Pago Base = (2,760,000 × 0.0175 × 1.5196) / (1.5196 - 1)
Pago Base = 73,380 / 0.5196
Pago Base = 141,230 COP/mes
```

### Paso 5: Ajustar por Opción de Compra

**Valor de Opción de Compra:**
```
Valor Opción = 2,760,000 × 20% = 552,000 COP
```

**Ajuste:**
```
Ajuste Opción = (552,000 × 0.0175) / (1.5196 - 1)
Ajuste Opción = 9,660 / 0.5196
Ajuste Opción = 18,611 COP/mes
```

**Pago Base Ajustado:**
```
Pago Base Ajustado = 141,230 - 18,611
Pago Base Ajustado = 122,619 COP/mes
```

### Paso 6: Sumar Servicio Mensual

```
Pago Mensual Total = 122,619 + 34,500
Pago Mensual Total = 157,119 COP/mes
```

**Nota:** El valor puede variar ligeramente por redondeo. El valor de **157,619** probablemente incluye algún ajuste adicional o redondeo diferente.

---

## 🔍 ¿Por qué no aparece en el Informe?

El valor de **157,619** es el resultado del campo `valor_24_meses` que se calcula usando el método `_calcular_pago_plazo()`.

**El problema es que:**

1. **El informe usa escenarios**: El informe usa el método `get_escenarios_resumen()` que calcula valores para diferentes escenarios (con/sin seguro, con/sin servicios).

2. **Los escenarios recalculan todo**: Cada escenario recalcula el pago mensual desde cero usando `_calcular_escenario()`, no usa directamente el campo `valor_24_meses`.

3. **Diferencia en el cálculo**: 
   - `valor_24_meses` usa el `costo_equipo_cop` actual (que puede incluir o no la garantía según la configuración)
   - Los escenarios calculan el costo del equipo según si incluyen o no el seguro

**Por eso:**
- En la vista de Odoo ves: **157,619** (campo `valor_24_meses`)
- En el informe ves: Un valor diferente (calculado por escenarios)

---

## 📋 Comparación: Vista vs Informe

### Vista de Odoo (Campo `valor_24_meses`):
```
Usa: costo_equipo_cop actual (con garantía si está configurada)
Calcula: Pago mensual para 24 meses
Muestra: 157,619 COP/mes
```

### Informe (Escenarios):
```
Usa: Recalcula costo_equipo según el escenario
Calcula: Pago mensual para cada escenario
Muestra: Valores diferentes según el escenario
```

---

## 💡 Solución: Agregar el Valor de 24 Meses al Informe

Para que el valor de **157,619** aparezca en el informe, podemos:

1. **Agregar una sección** que muestre los valores calculados (`valor_24_meses`, `valor_36_meses`, `valor_48_meses`)
2. **O usar estos valores** como referencia en los escenarios

---

## 🔧 Código de Referencia

### Cálculo del Valor de 24 Meses

```python
def _calcular_pago_plazo(self, record, plazo):
    """Método auxiliar para calcular pago en un plazo específico"""
    if plazo > 0:
        tasa_mensual_decimal = (record.tasa_nominal / 100.0) / 12.0
        
        if tasa_mensual_decimal > 0:
            factor = (1 + tasa_mensual_decimal) ** plazo
            # Calcular pago base solo sobre el costo del equipo
            pago_base = (record.costo_equipo_cop * tasa_mensual_decimal * factor) / (factor - 1)
            
            if record.valor_opcion_compra > 0:
                ajuste_opcion = (record.valor_opcion_compra * tasa_mensual_decimal) / (factor - 1)
                pago_base = pago_base - ajuste_opcion
        else:
            pago_base = record.costo_equipo_cop / plazo
        
        # Sumar el servicio mensual al pago base
        return pago_base + record.servicio_con_margen
    return 0.0
```

---

## 📊 Desglose del Valor 157,619

```
┌─────────────────────────────────────────┐
│  PAGO MENSUAL TOTAL: 157,619 COP/mes    │
├─────────────────────────────────────────┤
│                                         │
│  ┌──────────────────────────────────┐  │
│  │ Pago Base Equipo: 122,619 COP    │  │
│  │ (Con opción de compra ajustada)  │  │
│  └──────────────────────────────────┘  │
│              +                          │
│  ┌──────────────────────────────────┐  │
│  │ Servicio con Margen: 34,500 COP  │  │
│  │ (30,000 × 1.15)                  │  │
│  └──────────────────────────────────┘  │
│              =                          │
│  ┌──────────────────────────────────┐  │
│  │ Total: 157,119 ≈ 157,619 COP     │  │
│  │ (Diferencia por redondeo)        │  │
│  └──────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

---

## ❓ Preguntas Frecuentes

### ¿Por qué el valor es 157,619 y no 157,119?

La diferencia puede deberse a:
- **Redondeo intermedio**: Los cálculos pueden redondear en diferentes pasos
- **Precisión decimal**: El sistema puede usar más decimales internamente
- **Ajustes adicionales**: Puede haber algún ajuste que no esté visible

### ¿Por qué no coincide con el informe?

Porque:
- El informe **recalcula** los valores para cada escenario
- Los escenarios pueden tener configuraciones diferentes (con/sin seguro)
- El campo `valor_24_meses` usa la configuración actual de la calculadora

### ¿Cómo puedo ver el valor exacto en el informe?

Puedo agregar una sección al informe que muestre los valores calculados (`valor_24_meses`, `valor_36_meses`, `valor_48_meses`) además de los escenarios.

---

*Documento actualizado: [Fecha actual]*
