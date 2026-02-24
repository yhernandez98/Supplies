# 💰 Explicación: Cálculo del Costo de Servicios en el Costo Total

## 📊 Resumen del Cálculo

El **Costo Total** incluye:
1. ✅ **Costo del Equipo** (con utilidad y garantía si aplica)
2. ✅ **Costo Total de Servicios** (servicio mensual × plazo en meses)

---

## 🔢 Paso a Paso del Cálculo

### Paso 1: Calcular el Servicio con Margen

Primero se calcula el **servicio mensual con margen** aplicado:

**Fórmula:**
```
Servicio con Margen = Costo Servicios Completos × (1 + Porcentaje Margen / 100)
```

**Ejemplo:**
```
Costo Servicios Completos: $100,000 COP/mes
Porcentaje Margen: 15%

Servicio con Margen = 100,000 × (1 + 15/100)
Servicio con Margen = 100,000 × 1.15
Servicio con Margen = $115,000 COP/mes
```

**Código:**
```python
margen = 1 + (porcentaje_margen_servicio / 100.0)
servicio_con_margen = costo_servicios_completos * margen
```

---

### Paso 2: Calcular el Costo Total de Servicios

Se multiplica el servicio mensual por el **número de meses** del plazo:

**Fórmula:**
```
Costo Total de Servicios = Servicio con Margen × Plazo (meses)
```

**Ejemplo:**
```
Servicio con Margen: $115,000 COP/mes
Plazo: 24 meses

Costo Total de Servicios = 115,000 × 24
Costo Total de Servicios = $2,760,000 COP
```

**Código:**
```python
costo_servicios_totales = servicio_con_margen * plazo_meses
```

---

### Paso 3: Calcular el Costo Total

Finalmente, se **suma** el costo del equipo y el costo total de servicios:

**Fórmula:**
```
Costo Total = Costo Equipo (COP) + Costo Total de Servicios
```

**Ejemplo:**
```
Costo Equipo: $2,760,000 COP
Costo Total de Servicios: $2,760,000 COP

Costo Total = 2,760,000 + 2,760,000
Costo Total = $5,520,000 COP
```

**Código:**
```python
costo_total_cop = costo_equipo_cop + costo_servicios_totales
```

---

## 📋 Ejemplo Completo

### Datos de Entrada:
- **Valor Equipo**: 500 USD
- **Garantía**: 100 USD
- **Total USD**: 600 USD
- **Utilidad**: 15%
- **Costo con Utilidad**: 690 USD
- **TRM**: 4,000
- **Costo Equipo COP**: 2,760,000 COP
- **Costo Servicios Completos**: 100,000 COP/mes
- **Porcentaje Margen Servicio**: 15%
- **Plazo**: 24 meses

### Cálculos:

**1. Servicio con Margen:**
```
Servicio con Margen = 100,000 × (1 + 15/100)
Servicio con Margen = 100,000 × 1.15
Servicio con Margen = $115,000 COP/mes
```

**2. Costo Total de Servicios:**
```
Costo Total de Servicios = 115,000 × 24
Costo Total de Servicios = $2,760,000 COP
```

**3. Costo Total:**
```
Costo Total = 2,760,000 + 2,760,000
Costo Total = $5,520,000 COP
```

---

## 🔍 Desglose Detallado

### Componentes del Costo Total:

| Componente | Cálculo | Valor (Ejemplo) |
|------------|---------|-----------------|
| **Costo Equipo** | Valor USD × (1 + Utilidad%) × TRM | $2,760,000 COP |
| **Servicio Mensual** | Costo Base × (1 + Margen%) | $115,000 COP/mes |
| **Costo Total Servicios** | Servicio Mensual × Plazo | $2,760,000 COP |
| **Costo Total** | Equipo + Servicios Totales | $5,520,000 COP |

---

## ⚠️ Importante: Diferencia con el Pago Mensual

### Costo Total vs Pago Mensual

El **Costo Total** es la suma de:
- Costo del equipo
- Costo total de servicios (servicio mensual × plazo)

El **Pago Mensual** es diferente:
- Se calcula el pago del equipo usando la fórmula PMT (con intereses)
- Se suma el servicio mensual a cada cuota

**Ejemplo:**
```
Costo Total: $5,520,000 COP
  - Equipo: $2,760,000 COP
  - Servicios (24 meses): $2,760,000 COP

Pago Mensual: ~$132,586 COP/mes
  - Pago Equipo (con intereses): ~$17,586 COP/mes
  - Servicio Mensual: $115,000 COP/mes
  - Total: $132,586 COP/mes

Total a Pagar (24 meses): 132,586 × 24 = $3,182,064 COP
```

**Nota:** El "Total a Pagar" es diferente al "Costo Total" porque:
- El "Costo Total" no incluye intereses
- El "Total a Pagar" incluye intereses del financiamiento

---

## 📊 Fórmulas Completas

### 1. Servicio con Margen
```
Servicio con Margen = Costo Servicios Completos × (1 + Porcentaje Margen / 100)
```

### 2. Costo Total de Servicios
```
Costo Total de Servicios = Servicio con Margen × Plazo (meses)
```

### 3. Costo Total
```
Costo Total = Costo Equipo (COP) + Costo Total de Servicios
```

### Fórmula Combinada
```
Costo Total = Costo Equipo + (Costo Servicios Completos × (1 + Margen/100) × Plazo)
```

---

## 🎯 Casos Especiales

### Sin Servicios
Si `Costo Servicios Completos = 0`:
```
Servicio con Margen = 0
Costo Total de Servicios = 0
Costo Total = Costo Equipo
```

### Sin Margen de Servicio
Si `Porcentaje Margen Servicio = 0`:
```
Servicio con Margen = Costo Servicios Completos
Costo Total de Servicios = Costo Servicios Completos × Plazo
```

### Plazo Cero
Si `Plazo = 0`:
```
Costo Total de Servicios = 0
Costo Total = Costo Equipo
```

---

## 💡 Preguntas Frecuentes

### ¿Por qué se multiplica el servicio por el plazo?

Porque el servicio técnico se paga **cada mes** durante todo el plazo del contrato. Si el contrato es de 24 meses, pagarás 24 veces el servicio mensual.

**Ejemplo:**
```
Servicio Mensual: $115,000 COP
Plazo: 24 meses
Total Servicios: 115,000 × 24 = $2,760,000 COP
```

### ¿El servicio se suma al costo total o al pago mensual?

**Ambos:**
- **Costo Total**: Incluye el costo total de servicios (servicio mensual × plazo)
- **Pago Mensual**: Incluye el servicio mensual en cada cuota

**Ejemplo:**
```
Costo Total: $5,520,000 COP
  - Equipo: $2,760,000
  - Servicios (24 meses): $2,760,000

Pago Mensual: $132,586 COP
  - Pago Equipo: $17,586
  - Servicio Mensual: $115,000
```

### ¿El margen de servicio se aplica al costo total?

No, el margen se aplica **solo al servicio mensual**, no al costo total. El costo total es simplemente la suma del equipo y los servicios totales.

**Ejemplo:**
```
Costo Servicios Base: $100,000
Margen: 15%
Servicio con Margen: $115,000

Costo Total Servicios (24 meses): 115,000 × 24 = $2,760,000
```

### ¿Cómo afecta el plazo al costo total?

El plazo afecta directamente el costo total de servicios:

**Ejemplo con Servicio Mensual de $115,000:**
```
Plazo 24 meses: 115,000 × 24 = $2,760,000
Plazo 36 meses: 115,000 × 36 = $4,140,000
Plazo 48 meses: 115,000 × 48 = $5,520,000
```

A mayor plazo, mayor costo total de servicios.

---

## 📈 Comparación Visual

### Escenario 1: Con Servicios
```
Costo Equipo:        $2,760,000 COP
Servicio Mensual:    $115,000 COP/mes
Plazo:               24 meses
─────────────────────────────────────
Costo Total Servicios: $2,760,000 COP
Costo Total:          $5,520,000 COP
```

### Escenario 2: Sin Servicios
```
Costo Equipo:        $2,760,000 COP
Servicio Mensual:    $0 COP/mes
Plazo:               24 meses
─────────────────────────────────────
Costo Total Servicios: $0 COP
Costo Total:          $2,760,000 COP
```

---

## 🔧 Código de Referencia

### Cálculo del Servicio con Margen
```python
@api.depends('costo_servicios_completos', 'porcentaje_margen_servicio')
def _compute_servicio_con_margen(self):
    """Calcula el servicio con margen aplicado"""
    for record in self:
        margen = 1 + (record.porcentaje_margen_servicio / 100.0)
        record.servicio_con_margen = record.costo_servicios_completos * margen
```

### Cálculo del Costo Total
```python
@api.depends('costo_equipo_cop', 'servicio_con_margen', 'plazo_meses')
def _compute_costo_total_cop(self):
    """Calcula el costo total en pesos colombianos (equipo + servicios totales)"""
    for record in self:
        # Costo total de servicios durante todo el plazo
        costo_servicios_totales = record.servicio_con_margen * record.plazo_meses if record.plazo_meses > 0 else 0
        # Costo total = equipo + servicios totales
        record.costo_total_cop = record.costo_equipo_cop + costo_servicios_totales
```

---

## 📝 Resumen

1. **Servicio con Margen**: Se calcula aplicando el porcentaje de margen al costo base
2. **Costo Total de Servicios**: Se multiplica el servicio mensual por el plazo
3. **Costo Total**: Se suma el costo del equipo y el costo total de servicios

**Fórmula Final:**
```
Costo Total = Costo Equipo + (Servicio Mensual × Plazo)
```

Donde:
- **Servicio Mensual** = Costo Base × (1 + Margen/100)
- **Costo Equipo** = Valor USD × (1 + Utilidad/100) × TRM

---

*Documento actualizado: [Fecha actual]*
