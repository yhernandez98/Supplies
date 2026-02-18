# 🔄 Diferencias entre Calculadora de Equipos y Calculadora de Renting

## Resumen Ejecutivo

Ambas calculadoras comparten la misma base de cálculo, pero están diseñadas para **diferentes propósitos comerciales**:

- **Calculadora de Equipos**: Para calcular costos de **venta directa** de equipos con financiamiento
- **Calculadora de Renting**: Para calcular costos de **contratos de renting** con comparación de plazos

---

## 📊 Comparación Lado a Lado

| Característica | Calculadora de Equipos | Calculadora de Renting |
|----------------|------------------------|------------------------|
| **Propósito** | Venta directa con financiamiento | Contratos de renting |
| **Plazo por Defecto** | 24 meses | 48 meses |
| **Cálculo de Servicios** | Margen sobre costo (suma %) | Factor de margen (división) |
| **Comparación de Plazos** | ❌ No | ✅ Sí (24, 36, 48 meses) |
| **Opción de Compra por Defecto** | 20% | 0% |
| **Campos Únicos** | `total_pagar` | `valor_24_meses`, `valor_36_meses`, `valor_48_meses` |

---

## 🔍 Diferencias Detalladas

### 1. Propósito y Uso

#### Calculadora de Equipos
- **Uso**: Calcular el costo de venta de un equipo con financiamiento
- **Escenario típico**: 
  - Cliente quiere comprar un equipo
  - Se ofrece financiamiento a 24 meses
  - Incluye opción de compra del 20%
  - Se calcula el pago mensual y el total a pagar

#### Calculadora de Renting
- **Uso**: Calcular costos para contratos de renting
- **Escenario típico**: 
  - Cliente quiere alquilar un equipo
  - Se ofrecen diferentes plazos (24, 36, 48 meses)
  - Se compara cuál plazo es más conveniente
  - Generalmente sin opción de compra (0% por defecto)

---

### 2. Plazo por Defecto

#### Calculadora de Equipos
- **Plazo por defecto**: **24 meses**
- **Razón**: Los financiamientos de venta directa suelen ser a 24 meses

#### Calculadora de Renting
- **Plazo por defecto**: **48 meses**
- **Razón**: Los contratos de renting suelen ser más largos (36-48 meses)

---

### 3. Cálculo de Servicios (Diferencia Importante)

Esta es la **diferencia más significativa** entre ambas calculadoras:

#### Calculadora de Equipos
**Campo**: `margen_servicio` (Porcentaje)
- **Tipo**: Porcentaje (ej: 15%)
- **Cálculo**: `Servicio con Margen = Costo Servicios × (1 + Margen/100)`
- **Ejemplo**: 
  - Costo Servicios: $100,000
  - Margen: 15%
  - Resultado: $100,000 × 1.15 = **$115,000**

#### Calculadora de Renting
**Campo**: `porcentaje_margen_servicio` (Porcentaje)
- **Tipo**: Porcentaje (ej: 25%)
- **Cálculo**: `Servicio con Margen = Costo Servicios × (1 + Margen/100)`
- **Ejemplo**: 
  - Costo Servicios: $100,000
  - Margen: 25%
  - Resultado: $100,000 × 1.25 = **$125,000**

**Nota**: Ambas calculadoras ahora usan el mismo formato (porcentaje), lo que facilita su uso y comprensión.

---

### 4. Comparación de Plazos

#### Calculadora de Equipos
- ❌ **No calcula** diferentes plazos automáticamente
- Solo calcula el pago mensual para el plazo especificado
- Si quieres comparar, debes crear registros separados

#### Calculadora de Renting
- ✅ **Calcula automáticamente** tres plazos:
  - `valor_24_meses`: Pago mensual a 24 meses
  - `valor_36_meses`: Pago mensual a 36 meses
  - `valor_48_meses`: Pago mensual a 48 meses
- Permite comparar fácilmente cuál plazo es más conveniente
- Todos los cálculos se hacen con los mismos datos del equipo

---

### 5. Opción de Compra

#### Calculadora de Equipos
- **Porcentaje por defecto**: **20%**
- **Razón**: En ventas con financiamiento, es común ofrecer opción de compra del 20%

#### Calculadora de Renting
- **Porcentaje por defecto**: **0%**
- **Razón**: En renting puro, generalmente no hay opción de compra (o es muy baja)

---

### 6. Campos Únicos

#### Calculadora de Equipos
**Campo único**: `total_pagar`
- Calcula el total a pagar durante todo el plazo
- Fórmula: `(Pago Mensual × Plazo) + Opción de Compra`
- Útil para saber cuánto pagará el cliente en total

#### Calculadora de Renting
**Campos únicos**: `valor_24_meses`, `valor_36_meses`, `valor_48_meses`
- Calcula automáticamente los pagos para tres plazos diferentes
- Permite comparación rápida
- Útil para presentar opciones al cliente

---

## 📋 Ejemplo Práctico: Mismo Equipo, Diferentes Resultados

### Datos del Equipo
- Valor USD: 1,000
- Garantía USD: 50
- Porcentaje Utilidad: 10%
- TRM: 4,000
- Costo Servicios: 100,000
- Tasa Nominal: 21%

### Calculadora de Equipos

**Configuración:**
- Plazo: 24 meses
- Margen Servicio: 15%
- Opción de Compra: 20%

**Resultados:**
- Costo Total COP: 4,620,000
- Servicio con Margen: 115,000 (100,000 × 1.15)
- Pago Mensual: ~240,000
- Total a Pagar: 5,760,000 + 924,000 = **6,684,000**

### Calculadora de Renting

**Configuración:**
- Plazo: 48 meses (por defecto)
- Porcentaje Margen Servicio: 25%
- Opción de Compra: 0%

**Resultados:**
- Costo Total COP: 4,620,000 (igual)
- Servicio con Margen: 125,000 (100,000 × 1.25)
- Pago Mensual (48 meses): ~180,000
- **Comparación de Plazos:**
  - 24 meses: ~240,000/mes
  - 36 meses: ~200,000/mes
  - 48 meses: ~180,000/mes

---

## 🎯 ¿Cuándo Usar Cada Una?

### Usa Calculadora de Equipos cuando:
- ✅ El cliente quiere **comprar** el equipo
- ✅ Ofreces **financiamiento directo**
- ✅ Plazos típicos de **24 meses**
- ✅ Incluyes **opción de compra** (20%)
- ✅ Quieres saber el **total a pagar** del cliente
- ✅ Aplicas margen de servicios **sobre el costo** (suma %)

### Usa Calculadora de Renting cuando:
- ✅ El cliente quiere **alquilar** el equipo
- ✅ Ofreces **contratos de renting**
- ✅ Plazos típicos de **36-48 meses**
- ✅ Generalmente **sin opción de compra** (0%)
- ✅ Necesitas **comparar diferentes plazos**
- ✅ Usas **factor de margen** para servicios (división)

---

## 📊 Tabla de Campos Comparativa

| Campo | Calculadora de Equipos | Calculadora de Renting |
|-------|------------------------|------------------------|
| `name` | ✅ Nombre del Equipo | ✅ Nombre del Contrato |
| `valor_usd` | ✅ | ✅ |
| `valor_garantia_usd` | ✅ | ✅ |
| `porcentaje_utilidad` | ✅ | ✅ |
| `trm` | ✅ | ✅ |
| `costo_total_cop` | ✅ | ✅ |
| `costo_servicios_completos` | ✅ | ✅ |
| `margen_servicio` | ✅ (Porcentaje) | ❌ |
| `porcentaje_margen_servicio` | ❌ | ✅ (Porcentaje) |
| `servicio_con_margen` | ✅ | ✅ |
| `tasa_nominal` | ✅ | ✅ |
| `tasa_efectiva_anual` | ✅ | ✅ |
| `plazo_meses` | ✅ (Default: 24) | ✅ (Default: 48) |
| `porcentaje_opcion_compra` | ✅ (Default: 20%) | ✅ (Default: 0%) |
| `valor_opcion_compra` | ✅ | ✅ |
| `pago_mensual` | ✅ | ✅ |
| `total_pagar` | ✅ | ❌ |
| `valor_24_meses` | ❌ | ✅ |
| `valor_36_meses` | ❌ | ✅ |
| `valor_48_meses` | ❌ | ✅ |

---

## 🔧 Fórmulas de Cálculo Comparadas

### Cálculo de Servicio con Margen

#### Calculadora de Equipos:
```python
servicio_con_margen = costo_servicios × (1 + margen_servicio / 100)
```

#### Calculadora de Renting:
```python
servicio_con_margen = costo_servicios × (1 + porcentaje_margen_servicio / 100)
```

### Cálculo de Pago Mensual

**Ambas usan la misma fórmula PMT:**
```python
tasa_mensual = tasa_nominal / 12 / 100
factor = (1 + tasa_mensual) ^ plazo_meses
pago_base = (costo_total_cop × tasa_mensual × factor) / (factor - 1)

# Ajustar por opción de compra
if valor_opcion_compra > 0:
    ajuste = (valor_opcion_compra × tasa_mensual) / (factor - 1)
    pago_base = pago_base - ajuste

pago_mensual = pago_base + servicio_con_margen
```

---

## 💡 Recomendaciones de Uso

### Para Ventas Directas
1. Usa **Calculadora de Equipos**
2. Configura plazo de 24 meses
3. Aplica margen de servicios del 15%
4. Incluye opción de compra del 20%

### Para Contratos de Renting
1. Usa **Calculadora de Renting**
2. Configura diferentes plazos (24, 36, 48 meses)
3. Usa porcentaje de margen de servicios (25% por defecto)
4. Generalmente sin opción de compra (0%)

### Para Comparar Opciones
1. Usa **Calculadora de Renting** para ver todos los plazos
2. Usa **Calculadora de Equipos** para ver el total a pagar

---

## ❓ Preguntas Frecuentes

### ¿Puedo usar ambas calculadoras para lo mismo?

Sí, pero cada una está optimizada para su propósito. La Calculadora de Renting es mejor si necesitas comparar plazos.

### ¿Por qué el cálculo de servicios es diferente?

Porque representan diferentes modelos de negocio:
- **Equipos**: Margen simple sobre costo
- **Renting**: Factor que representa el porcentaje del costo que se mantiene

### ¿Puedo cambiar el plazo por defecto?

Sí, puedes modificarlo en cada registro individual. Los valores por defecto son solo sugerencias.

### ¿Cuál es mejor para presentar al cliente?

- **Calculadora de Equipos**: Si el cliente quiere comprar
- **Calculadora de Renting**: Si el cliente quiere alquilar o comparar opciones

---

*Documento actualizado: [Fecha actual]*
