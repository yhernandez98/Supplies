# 💼 Explicación: Costo Servicios Completos

## ¿Qué es el "Costo Servicios Completos"?

El **Costo Servicios Completos** es el **costo base mensual** de los servicios técnicos que se incluyen en el contrato de renting o financiamiento del equipo.

### Concepto

Este campo representa el costo real (sin margen de ganancia) de todos los servicios técnicos que se ofrecen junto con el equipo, tales como:

- ✅ **Mantenimiento técnico**: Revisiones, actualizaciones, reparaciones
- ✅ **Soporte técnico**: Asistencia remota o en sitio
- ✅ **Monitoreo**: Supervisión del equipo
- ✅ **Actualizaciones**: Software, firmware, parches de seguridad
- ✅ **Garantía de servicio**: Cobertura de servicios técnicos
- ✅ **Otros servicios**: Según el contrato

### Características

- **Es un costo mensual**: Se suma al pago mensual del equipo
- **Es el costo base**: Antes de aplicar el margen de ganancia
- **Puede ser cero**: Si no se incluyen servicios técnicos
- **Se calcula según el tiempo**: Depende de las horas de servicio requeridas

---

## ¿Cómo se Calcula el Costo Servicios Completos?

### Método 1: Cálculo Manual

Puedes calcularlo manualmente sumando todos los costos de servicios:

```
Costo Servicios Completos = 
    Costo Mantenimiento Mensual +
    Costo Soporte Mensual +
    Costo Monitoreo Mensual +
    Otros Costos de Servicio
```

### Método 2: Usando el APU de Servicios

El módulo incluye un **APU de Servicios** que calcula costos por hora de:
- Técnico
- Vehículo
- Internet
- Soporte remoto

Puedes usar estos valores para calcular el costo total de servicios:

```
Costo Servicios = 
    (Horas Técnico × Costo Hora Técnico) +
    (Horas Vehículo × Costo Hora Vehículo) +
    (Horas Internet × Costo Hora Internet) +
    (Horas Soporte Remoto × Costo Hora Remoto) +
    Costos Fijos (orden de servicio, etc.)
```

### Ejemplo Práctico

**Escenario**: Equipo que requiere 3 horas de técnico al mes

**Usando APU de Servicios:**
- Costo Hora Técnico: $31,969 COP
- Horas requeridas: 3 horas/mes
- Costo Técnico: 3 × $31,969 = $95,907 COP

**Otros costos:**
- Orden de servicio: $30,000 COP
- Internet (36 horas): 36 × $472 = $17,000 COP

**Costo Servicios Completos Total:**
```
$95,907 + $30,000 + $17,000 = $142,907 COP/mes
```

---

## ¿Cómo se Aplica el Margen?

Una vez que tienes el **Costo Servicios Completos**, se aplica un **margen de ganancia** para obtener el precio final que se cobra al cliente.

### Calculadora de Equipos

**Campo**: `margen_servicio` (Porcentaje, ej: 15%)

**Fórmula:**
```
Servicio con Margen = Costo Servicios × (1 + Margen/100)
```

**Ejemplo:**
- Costo Servicios: $100,000
- Margen: 15%
- Servicio con Margen: $100,000 × 1.15 = **$115,000**

### Calculadora de Renting

**Campo**: `porcentaje_margen_servicio` (Porcentaje, ej: 25%)

**Fórmula:**
```
Servicio con Margen = Costo Servicios × (1 + Margen/100)
```

**Ejemplo:**
- Costo Servicios: $100,000
- Margen: 25%
- Servicio con Margen: $100,000 × 1.25 = **$125,000**

---

## ¿Dónde se Usa el Servicio con Margen?

El **Servicio con Margen** se suma al **Pago Mensual** del equipo:

```
Pago Mensual Total = Pago Mensual del Equipo + Servicio con Margen
```

### Ejemplo Completo

**Datos:**
- Equipo: $2,222,222 COP
- Plazo: 24 meses
- Tasa: 21%
- Pago Mensual Equipo: $99,000 COP
- Costo Servicios: $100,000 COP
- Margen Servicio: 15%

**Cálculo:**
1. Servicio con Margen: $100,000 × 1.15 = $115,000
2. Pago Mensual Total: $99,000 + $115,000 = **$214,000 COP/mes**

---

## Diferencia entre Costo y Precio

### Costo Servicios Completos
- **Es el costo real** para la empresa
- **No incluye ganancia**
- **Se usa para calcular el margen**

### Servicio con Margen
- **Es el precio que se cobra** al cliente
- **Incluye la ganancia**
- **Se suma al pago mensual**

---

## Ejemplos Prácticos

### Ejemplo 1: Sin Servicios

**Configuración:**
- Costo Servicios Completos: $0
- Margen: 15%

**Resultado:**
- Servicio con Margen: $0
- Pago Mensual: Solo el pago del equipo

### Ejemplo 2: Con Servicios Básicos

**Configuración:**
- Costo Servicios Completos: $50,000
- Margen: 15%

**Resultado:**
- Servicio con Margen: $57,500
- Se suma al pago mensual del equipo

### Ejemplo 3: Con Servicios Completos

**Configuración:**
- Costo Servicios Completos: $200,000
- Margen: 20%

**Resultado:**
- Servicio con Margen: $240,000
- Incluye mantenimiento, soporte, monitoreo completo

---

## Preguntas Frecuentes

### ¿El Costo Servicios es obligatorio?

No, puede ser $0 si no se incluyen servicios técnicos en el contrato.

### ¿Cómo sé cuánto poner en Costo Servicios?

Puedes:
1. Calcular usando el APU de Servicios
2. Usar valores históricos de contratos similares
3. Consultar con el área de servicios técnicos

### ¿El margen es igual para todos los servicios?

No necesariamente. Puedes ajustar el margen según:
- Tipo de servicio
- Cliente
- Volumen
- Competencia

### ¿Se puede cambiar el Costo Servicios después?

Sí, puedes modificarlo en cualquier momento. El sistema recalculará automáticamente el Servicio con Margen y el Pago Mensual.

---

## Relación con el Pago Mensual

El flujo completo es:

```
1. Costo Servicios Completos (costo real)
   ↓
2. Aplicar Margen (%)
   ↓
3. Servicio con Margen (precio al cliente)
   ↓
4. Sumar al Pago Mensual del Equipo
   ↓
5. Pago Mensual Total
```

---

*Documento actualizado: [Fecha actual]*
