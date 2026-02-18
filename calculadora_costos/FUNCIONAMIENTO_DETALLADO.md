# 📊 Funcionamiento Detallado de la Calculadora de Costos

## Tabla de Contenidos

1. [Introducción](#introducción)
2. [Factor de Utilidad - Explicación Completa](#factor-de-utilidad)
3. [Calculadora de Equipos - Campos y Cálculos](#calculadora-de-equipos)
4. [Calculadora de Renting - Campos y Cálculos](#calculadora-de-renting)
5. [APU de Servicios - Campos y Cálculos](#apu-de-servicios)
6. [Flujo de Cálculos Completo](#flujo-de-cálculos-completo)
7. [Ejemplos Prácticos](#ejemplos-prácticos)

---

## Introducción

La Calculadora de Costos es un sistema que permite calcular el costo total de equipos informáticos, incluyendo garantías, servicios técnicos, intereses financieros y opciones de compra. Todos los cálculos se realizan automáticamente cuando ingresas los datos.

---

## Factor de Utilidad - Explicación Completa

### ¿Qué es el Factor de Utilidad?

El **Factor de Utilidad** es un porcentaje que representa la **margen de ganancia** que deseas obtener sobre el costo del equipo. Es un concepto inverso a lo que normalmente se piensa.

### Cómo Funciona

El factor de utilidad funciona de la siguiente manera:

**Fórmula:**
```
Costo con Utilidad = Costo Total USD / Factor de Utilidad
```

### Ejemplos Prácticos

#### Ejemplo 1: Factor de Utilidad 0.9 (90%)

**Escenario:**
- Costo del equipo: $500 USD
- Factor de Utilidad: 0.9 (90%)

**Cálculo:**
```
Costo con Utilidad = $500 / 0.9 = $555.56 USD
```

**Interpretación:**
- Si el costo es $500 USD y quieres un margen del 10% sobre el precio de venta
- El precio de venta será $555.56 USD
- Tu ganancia será: $555.56 - $500 = $55.56 USD (11.1% sobre el costo)

#### Ejemplo 2: Factor de Utilidad 0.8 (80%)

**Escenario:**
- Costo del equipo: $500 USD
- Factor de Utilidad: 0.8 (80%)

**Cálculo:**
```
Costo con Utilidad = $500 / 0.8 = $625.00 USD
```

**Interpretación:**
- Si el costo es $500 USD y quieres un margen del 20% sobre el precio de venta
- El precio de venta será $625.00 USD
- Tu ganancia será: $625 - $500 = $125 USD (25% sobre el costo)

#### Ejemplo 3: Factor de Utilidad 1.0 (100%)

**Escenario:**
- Costo del equipo: $500 USD
- Factor de Utilidad: 1.0 (100%)

**Cálculo:**
```
Costo con Utilidad = $500 / 1.0 = $500.00 USD
```

**Interpretación:**
- No hay margen de ganancia
- El precio de venta es igual al costo
- Utilidad: $0 USD

### Tabla de Referencia Rápida

| Factor | Porcentaje | Margen sobre Precio | Ejemplo: Costo $100 |
|--------|------------|-------------------|---------------------|
| 0.5    | 50%        | 50%               | Precio: $200        |
| 0.6    | 60%        | 40%               | Precio: $166.67     |
| 0.7    | 70%        | 30%               | Precio: $142.86     |
| 0.8    | 80%        | 20%               | Precio: $125.00     |
| **0.9**| **90%**    | **10%**           | **Precio: $111.11** |
| 0.95   | 95%        | 5%                | Precio: $105.26     |
| 1.0    | 100%       | 0%                | Precio: $100.00     |

### ¿Por qué se usa División en lugar de Multiplicación?

El factor de utilidad usa **división** porque representa el **porcentaje del costo** que quieres mantener como costo, y el resto será tu ganancia.

- **Factor 0.9** = Quieres mantener el 90% del costo, ganando el 10% restante
- **Factor 0.8** = Quieres mantener el 80% del costo, ganando el 20% restante

Si usáramos multiplicación (ej: costo × 1.1), estaríamos calculando un margen sobre el costo, no sobre el precio de venta.

### Valor por Defecto

El factor de utilidad por defecto es **0.9** (90%), lo que significa un margen del 10% sobre el precio de venta.

---

## Calculadora de Equipos - Campos y Cálculos

### Campos de Entrada (Datos que Tú Ingresas)

#### 1. **Nombre del Equipo** (`name`)
- **Tipo**: Texto
- **Requerido**: Sí
- **Descripción**: Nombre o descripción del equipo
- **Ejemplo**: "Equipo All in One HP", "Portátil Dell Latitude"

#### 2. **Valor en USD** (`valor_usd`)
- **Tipo**: Número decimal
- **Requerido**: Sí
- **Descripción**: Precio del equipo en dólares estadounidenses
- **Ejemplo**: 480, 1000, 2500
- **Valor por defecto**: 0.0

#### 3. **Valor Garantía Extendida (USD)** (`valor_garantia_usd`)
- **Tipo**: Número decimal
- **Requerido**: No
- **Descripción**: Costo adicional de garantía extendida en USD
- **Ejemplo**: 20, 50, 100
- **Valor por defecto**: 0.0

#### 4. **Factor de Utilidad** (`factor_utilidad`)
- **Tipo**: Número decimal
- **Requerido**: Sí
- **Descripción**: Factor de utilidad aplicado (0.9 = 90%, 1.0 = 100%)
- **Ejemplo**: 0.9, 0.8, 0.95
- **Valor por defecto**: 0.9
- **Ver sección anterior para explicación detallada**

#### 5. **TRM (COP/USD)** (`trm`)
- **Tipo**: Número decimal
- **Requerido**: Sí
- **Descripción**: Tasa Representativa del Mercado para conversión de USD a COP
- **Ejemplo**: 4000, 4200, 3800
- **Valor por defecto**: 4000.0
- **Nota**: Se carga automáticamente desde Parámetros Financieros

#### 6. **Costo Servicios Completos** (`costo_servicios_completos`)
- **Tipo**: Número decimal
- **Requerido**: No
- **Descripción**: Costo base de servicios técnicos completos
- **Ejemplo**: 0, 50000, 100000
- **Valor por defecto**: 0.0

#### 7. **Margen de Servicio (%)** (`margen_servicio`)
- **Tipo**: Número decimal
- **Requerido**: No
- **Descripción**: Porcentaje de margen aplicado a servicios técnicos
- **Ejemplo**: 15 (15%), 20 (20%), 10 (10%)
- **Valor por defecto**: 15.0
- **Cálculo**: `Servicio con Margen = Costo Servicios × (1 + Margen/100)`

#### 8. **Tasa Nominal (%)** (`tasa_nominal`)
- **Tipo**: Número decimal
- **Requerido**: Sí
- **Descripción**: Tasa de interés nominal anual en porcentaje
- **Ejemplo**: 21 (21%), 18 (18%), 24 (24%)
- **Valor por defecto**: 21.0
- **Nota**: Se carga automáticamente desde Parámetros Financieros

#### 9. **Plazo (Meses)** (`plazo_meses`)
- **Tipo**: Número entero
- **Requerido**: Sí
- **Descripción**: Plazo del financiamiento en meses
- **Ejemplo**: 24, 36, 48
- **Valor por defecto**: 24

#### 10. **Porcentaje Opción de Compra (%)** (`porcentaje_opcion_compra`)
- **Tipo**: Número decimal
- **Requerido**: No
- **Descripción**: Porcentaje del valor del equipo para opción de compra al final del plazo
- **Ejemplo**: 20 (20%), 10 (10%), 0 (0%)
- **Valor por defecto**: 20.0

### Campos Calculados (Se Calculan Automáticamente)

#### 1. **Costo Total USD** (`costo_total_usd`)
- **Fórmula**: `Valor USD + Valor Garantía USD`
- **Ejemplo**: Si Valor USD = 480 y Garantía = 20, entonces Costo Total USD = 500

#### 2. **Costo con Utilidad (USD)** (`costo_con_utilidad_usd`)
- **Fórmula**: `Costo Total USD / Factor de Utilidad`
- **Ejemplo**: Si Costo Total USD = 500 y Factor = 0.9, entonces Costo con Utilidad = 555.56

#### 3. **Costo Total (COP)** (`costo_total_cop`)
- **Fórmula**: `Costo con Utilidad USD × TRM`
- **Ejemplo**: Si Costo con Utilidad = 555.56 y TRM = 4000, entonces Costo Total COP = 2,222,222

#### 4. **Servicio con Margen** (`servicio_con_margen`)
- **Fórmula**: `Costo Servicios × (1 + Margen/100)`
- **Ejemplo**: Si Costo Servicios = 100,000 y Margen = 15%, entonces Servicio con Margen = 115,000

#### 5. **Tasa Mensual (%)** (`tasa_mensual`)
- **Fórmula**: `Tasa Nominal / 12`
- **Ejemplo**: Si Tasa Nominal = 21%, entonces Tasa Mensual = 1.75%

#### 6. **Tasa Efectiva Anual (%)** (`tasa_efectiva_anual`)
- **Fórmula**: `((1 + Tasa Mensual Decimal)^12 - 1) × 100`
- **Ejemplo**: Si Tasa Nominal = 21%, entonces Tasa Efectiva Anual ≈ 23.14%

#### 7. **Valor Opción de Compra (COP)** (`valor_opcion_compra`)
- **Fórmula**: `Costo Total COP × (Porcentaje Opción / 100)`
- **Ejemplo**: Si Costo Total COP = 2,222,222 y Porcentaje = 20%, entonces Opción de Compra = 444,444

#### 8. **Pago Mensual (COP)** (`pago_mensual`)
- **Fórmula**: Función PMT (Payment) + Servicio con Margen
- **Cálculo detallado**:
  ```
  Tasa Mensual Decimal = (Tasa Nominal / 100) / 12
  Factor = (1 + Tasa Mensual Decimal)^Plazo
  Pago Base = (Costo Total COP × Tasa Mensual Decimal × Factor) / (Factor - 1)
  
  Si hay Opción de Compra:
    Ajuste = (Opción de Compra × Tasa Mensual Decimal) / (Factor - 1)
    Pago Base = Pago Base - Ajuste
  
  Pago Mensual = Pago Base + Servicio con Margen
  ```
- **Ejemplo**: Ver sección de ejemplos prácticos

#### 9. **Total a Pagar** (`total_pagar`)
- **Fórmula**: `(Pago Mensual × Plazo) + Opción de Compra`
- **Ejemplo**: Si Pago Mensual = 120,000, Plazo = 24 meses, y Opción = 444,444, entonces Total = 3,324,444

---

## Calculadora de Renting - Campos y Cálculos

La Calculadora de Renting funciona de manera similar a la Calculadora de Equipos, pero con algunas diferencias:

### Diferencias Clave

#### 1. **Porcentaje Margen Servicio** (`porcentaje_margen_servicio`)
- **Tipo**: Porcentaje
- **Valor por defecto**: 25.0 (25%)
- **Cálculo**: `Servicio con Margen = Costo Servicios × (1 + Margen/100)`
- **Ejemplo**: Si Costo Servicios = 100,000 y Margen = 25%, entonces Servicio con Margen = 125,000

#### 2. **Valores para Diferentes Plazos**
La calculadora de renting calcula automáticamente los pagos mensuales para tres plazos diferentes:

- **Valor 24 Meses** (`valor_24_meses`)
- **Valor 36 Meses** (`valor_36_meses`)
- **Valor 48 Meses** (`valor_48_meses`)

Esto permite comparar fácilmente diferentes opciones de plazo.

### Campos Adicionales

Todos los demás campos son iguales a la Calculadora de Equipos, excepto que el **Plazo por defecto es 48 meses** en lugar de 24.

---

## APU de Servicios - Campos y Cálculos

El APU (Análisis de Precios Unitarios) calcula los costos por hora de diferentes recursos.

### Campos de Entrada

#### Parámetros de Vehículo

1. **Costo del Vehículo** (`costo_vehiculo`)
   - Valor por defecto: 35,000,000
   - Costo inicial del vehículo

2. **Años Depreciación Vehículo** (`años_depreciacion_vehiculo`)
   - Valor por defecto: 7
   - Años de vida útil para depreciación

3. **Costo Mantenimiento Vehículo/Mes** (`costo_mantenimiento_vehiculo`)
   - Valor por defecto: 350,000
   - Costo mensual de mantenimiento

4. **Salario Conductor** (`salario_conductor`)
   - Valor por defecto: 1,100,000
   - Salario mensual del conductor

5. **Factor Prestaciones Conductor** (`factor_prestaciones_conductor`)
   - Valor por defecto: 1.52
   - Factor de prestaciones sociales (incluye cesantías, primas, etc.)

#### Parámetros de Técnico

1. **Salario Técnico** (`salario_tecnico`)
   - Valor por defecto: 1,650,000
   - Salario mensual del técnico

2. **Factor Prestaciones Técnico** (`factor_prestaciones_tecnico`)
   - Valor por defecto: 1.55
   - Factor de prestaciones sociales

#### Parámetros de Internet

1. **Costo Internet Claro/Mes** (`costo_internet_claro`)
   - Valor por defecto: 340,000

2. **Costo Internet ETB/Mes** (`costo_internet_etb`)
   - Valor por defecto: 167,000

3. **Costo Infraestructura Total** (`costo_infraestructura_total`)
   - Valor por defecto: 3,200,000

#### Parámetros de Trabajo

1. **Horas de Trabajo por Mes** (`horas_trabajo_mes`)
   - Valor por defecto: 240
   - 30 días × 8 horas = 240 horas

2. **Días de Trabajo por Mes** (`dias_trabajo_mes`)
   - Valor por defecto: 30

3. **Horas de Trabajo por Día** (`horas_trabajo_dia`)
   - Valor por defecto: 8

### Campos Calculados

#### 1. **Costo Hora Vehículo** (`costo_hora_vehiculo`)

**Cálculo:**
```
Depreciación Anual = Costo Vehículo / Años Depreciación
Depreciación Diaria = Depreciación Anual / 365
Depreciación Hora = Depreciación Diaria / Horas Trabajo Día

Mantenimiento Diario = Costo Mantenimiento / Días Trabajo Mes
Mantenimiento Hora = Mantenimiento Diario / Horas Trabajo Día

Salario con Prestaciones = Salario Conductor × Factor Prestaciones
Conductor Hora = Salario con Prestaciones / Horas Trabajo Mes

Costo Hora Vehículo = Depreciación Hora + Mantenimiento Hora + Conductor Hora
```

**Ejemplo:**
- Costo Vehículo: 35,000,000
- Años Depreciación: 7
- Depreciación Anual: 5,000,000
- Depreciación Diaria: 13,698.63
- Depreciación Hora: 1,712.33

- Mantenimiento Mes: 350,000
- Mantenimiento Diario: 11,666.67
- Mantenimiento Hora: 1,458.33

- Salario: 1,100,000
- Factor Prestaciones: 1.52
- Salario con Prestaciones: 1,672,000
- Conductor Hora: 6,966.67

**Costo Hora Vehículo Total: 10,137.33 COP**

#### 2. **Costo Hora Técnico** (`costo_hora_tecnico`)

**Cálculo:**
```
Salario con Prestaciones = Salario Técnico × Factor Prestaciones
Costo Hora Técnico = (Salario con Prestaciones / Horas Trabajo Mes) × 3
```

**Ejemplo:**
- Salario: 1,650,000
- Factor Prestaciones: 1.55
- Salario con Prestaciones: 2,557,500
- Costo Hora Base: 10,656.25
- Costo Hora Técnico (×3): 31,968.75 COP

#### 3. **Costo Hora Internet** (`costo_hora_internet`)

**Cálculo:**
```
Costo Diario Claro = Costo Internet Claro / Días Trabajo Mes
Costo Hora Claro = Costo Diario Claro / Horas Trabajo Día

Costo Diario ETB = Costo Internet ETB / Días Trabajo Mes
Costo Hora ETB = Costo Diario ETB / Horas Trabajo Día

Horas Mes Totales = Días Trabajo Mes × Horas Trabajo Día
Costo Infra Hora = Costo Infraestructura / (Horas Mes Totales × 60) / 3

Costo Hora Internet = Costo Hora Claro + Costo Hora ETB + Costo Infra Hora
```

#### 4. **Costo Hora Soporte Remoto** (`costo_hora_remoto`)

**Cálculo:**
```
Costo Técnico Remoto = Costo Hora Técnico / 3
Otros Costos = Costo Hora Internet × 0.5

Costo Hora Remoto = Costo Técnico Remoto + Otros Costos
```

#### 5. **Costo Alistamiento** (`costo_alistamiento`)

**Cálculo:**
```
Horas Técnico = 3
Horas Internet = 36

Costo Técnico = (Costo Hora Técnico / 3) × Horas Técnico
Costo Internet = Costo Hora Internet × Horas Internet
Costos Fijos = 50,000 (estimado)

Costo Alistamiento = Costo Técnico + Costo Internet + Costos Fijos
```

#### 6. **Costo Instalación** (`costo_instalacion`)

**Cálculo:**
```
Horas Técnico = 3
Costo Técnico = (Costo Hora Técnico / 3) × Horas Técnico
Costo Fijo = 30,000 (estimado)

Costo Instalación = Costo Técnico + Costo Fijo
```

---

## Flujo de Cálculos Completo

### Ejemplo Completo: Calculadora de Equipos

**Datos de Entrada:**
- Nombre: "Equipo All in One"
- Valor USD: 480
- Garantía USD: 20
- Factor Utilidad: 0.9
- TRM: 4000
- Costo Servicios: 0
- Margen Servicio: 15%
- Tasa Nominal: 21%
- Plazo: 24 meses
- Opción de Compra: 20%

**Paso 1: Calcular Costo Total USD**
```
Costo Total USD = 480 + 20 = 500 USD
```

**Paso 2: Calcular Costo con Utilidad**
```
Costo con Utilidad = 500 / 0.9 = 555.56 USD
```

**Paso 3: Calcular Costo Total COP**
```
Costo Total COP = 555.56 × 4000 = 2,222,222 COP
```

**Paso 4: Calcular Servicio con Margen**
```
Servicio con Margen = 0 × (1 + 15/100) = 0 COP
```

**Paso 5: Calcular Tasa Mensual**
```
Tasa Mensual = 21 / 12 = 1.75%
```

**Paso 6: Calcular Tasa Efectiva Anual**
```
Tasa Mensual Decimal = 0.0175
Tasa Efectiva = ((1 + 0.0175)^12 - 1) × 100 = 23.14%
```

**Paso 7: Calcular Opción de Compra**
```
Opción de Compra = 2,222,222 × (20/100) = 444,444 COP
```

**Paso 8: Calcular Pago Mensual**
```
Tasa Mensual Decimal = 0.0175
Factor = (1 + 0.0175)^24 = 1.5164
Pago Base = (2,222,222 × 0.0175 × 1.5164) / (1.5164 - 1) = 114,000 COP

Ajuste Opción = (444,444 × 0.0175) / (1.5164 - 1) = 15,000 COP
Pago Base Ajustado = 114,000 - 15,000 = 99,000 COP

Pago Mensual = 99,000 + 0 = 99,000 COP
```

**Paso 9: Calcular Total a Pagar**
```
Total a Pagar = (99,000 × 24) + 444,444 = 2,376,000 + 444,444 = 2,820,444 COP
```

---

## Ejemplos Prácticos

### Ejemplo 1: Equipo Básico sin Servicios

**Datos:**
- Valor USD: 480
- Garantía: 20
- Factor Utilidad: 0.9
- TRM: 4000
- Tasa: 21%
- Plazo: 24 meses
- Opción Compra: 20%

**Resultados:**
- Costo Total COP: 2,222,222
- Pago Mensual: ~99,000
- Total a Pagar: ~2,820,444

### Ejemplo 2: Equipo con Servicios

**Datos:**
- Valor USD: 480
- Garantía: 20
- Factor Utilidad: 0.9
- TRM: 4000
- Costo Servicios: 100,000
- Margen Servicio: 15%
- Tasa: 21%
- Plazo: 24 meses
- Opción Compra: 20%

**Resultados:**
- Costo Total COP: 2,222,222
- Servicio con Margen: 115,000
- Pago Mensual: ~99,000 + 115,000 = 214,000
- Total a Pagar: (214,000 × 24) + 444,444 = 5,580,444

### Ejemplo 3: Comparación de Plazos (Renting)

**Datos:**
- Valor USD: 10,000
- Factor Utilidad: 0.9
- TRM: 4000
- Tasa: 21%

**Resultados:**
- 24 meses: ~450,000/mes
- 36 meses: ~350,000/mes
- 48 meses: ~300,000/mes

---

## Preguntas Frecuentes

### ¿Por qué el Factor de Utilidad usa división?

Porque representa el porcentaje del costo que quieres mantener, no un margen sobre el costo. Si quieres un margen del 10% sobre el precio de venta, usas factor 0.9.

### ¿Cómo cambio el margen de ganancia?

Ajusta el Factor de Utilidad:
- Margen 10% sobre precio → Factor 0.9
- Margen 20% sobre precio → Factor 0.8
- Margen 5% sobre precio → Factor 0.95

### ¿Qué pasa si pongo Factor de Utilidad = 1.0?

No habrá margen de ganancia. El precio de venta será igual al costo.

### ¿Los cálculos son exactos?

Sí, usan precisión decimal de 10 dígitos y fórmulas financieras estándar equivalentes a Excel.

---

*Documento actualizado: [Fecha actual]*
