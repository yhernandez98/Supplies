# 💰 Explicación: Tasas de Interés

## ¿Qué es una Tasa de Interés?

La **tasa de interés** es el **costo del dinero** o el **precio que se paga por pedir dinero prestado**. Es un porcentaje que se aplica sobre el capital (dinero prestado) para calcular cuánto adicional debes pagar.

### Concepto Básico

```
Si pides prestado: $1,000,000 COP
Con tasa de interés: 21% anual
Al final del año debes: $1,000,000 + $210,000 = $1,210,000 COP
```

El interés ($210,000) es el "costo" de haber usado ese dinero durante un año.

---

## Tipos de Tasas en la Calculadora

La calculadora maneja **tres tipos de tasas** que están relacionadas entre sí:

### 1. 📊 Tasa Nominal (%)

**¿Qué es?**
- Es la tasa de interés **anual** que se ingresa manualmente
- Se expresa como un porcentaje (ej: 21%, 18%, 24%)
- Es la tasa "base" que usas para todos los cálculos

**Ejemplo:**
```
Tasa Nominal = 21%
```

**Características:**
- ✅ Se ingresa manualmente en la calculadora
- ✅ Es una tasa anual (por 12 meses)
- ✅ No considera la capitalización (reinversión de intereses)
- ✅ Es la tasa que normalmente te ofrece el banco o entidad financiera

---

### 2. 📅 Tasa Mensual (%)

**¿Qué es?**
- Es la tasa de interés **mensual** calculada automáticamente
- Se obtiene dividiendo la tasa nominal entre 12 meses
- Se usa para calcular los pagos mensuales

**Fórmula:**
```
Tasa Mensual = Tasa Nominal / 12
```

**Ejemplo:**
```
Tasa Nominal = 21%
Tasa Mensual = 21 / 12 = 1.75% mensual
```

**¿Por qué se calcula?**
- Los pagos se hacen **mensualmente**
- Necesitas saber cuánto interés se cobra **cada mes**
- Se usa en la fórmula PMT para calcular el pago mensual

**Características:**
- ✅ Se calcula automáticamente
- ✅ Es solo para referencia (no se ingresa manualmente)
- ✅ Es la tasa que realmente se aplica cada mes

---

### 3. 📈 Tasa Efectiva Anual (%)

**¿Qué es?**
- Es la tasa de interés **real** que pagas considerando la capitalización mensual
- Es **mayor** que la tasa nominal porque considera que los intereses se reinvierten
- Es la tasa que realmente pagas al final del año

**Fórmula:**
```
Tasa Mensual Decimal = (Tasa Nominal / 100) / 12
Tasa Efectiva Anual = ((1 + Tasa Mensual Decimal)^12 - 1) × 100
```

**Ejemplo:**
```
Tasa Nominal = 21%
Tasa Mensual Decimal = (21 / 100) / 12 = 0.0175
Tasa Efectiva = ((1 + 0.0175)^12 - 1) × 100
Tasa Efectiva = (1.2314 - 1) × 100 = 23.14%
```

**¿Por qué es mayor?**
- Los intereses se capitalizan (se suman al capital) cada mes
- En el segundo mes, pagas intereses sobre el capital + intereses del primer mes
- Esto hace que el interés total sea mayor que simplemente 21%

**Características:**
- ✅ Se calcula automáticamente
- ✅ Es la tasa "real" que pagas
- ✅ Es útil para comparar diferentes opciones de financiamiento
- ✅ Siempre es mayor o igual que la tasa nominal

---

## Comparación de las Tres Tasas

| Tasa | Valor (ejemplo) | ¿Cuándo se usa? |
|------|----------------|-----------------|
| **Nominal** | 21% | Se ingresa manualmente, es la tasa base |
| **Mensual** | 1.75% | Se usa para calcular pagos mensuales |
| **Efectiva Anual** | 23.14% | Muestra el costo real del crédito |

---

## ¿Cómo se Usan en la Calculadora?

### 1. Para Calcular el Pago Mensual

La calculadora usa la **tasa mensual** (convertida a decimal) para calcular el pago mensual con la fórmula PMT:

**Fórmula PMT:**
```
Tasa Mensual Decimal = (Tasa Nominal / 100) / 12
Factor = (1 + Tasa Mensual Decimal)^Plazo
Pago Mensual = (Capital × Tasa Mensual Decimal × Factor) / (Factor - 1)
```

**Ejemplo:**
```
Capital: $2,760,000 COP
Tasa Nominal: 21%
Plazo: 24 meses

Tasa Mensual Decimal = (21 / 100) / 12 = 0.0175
Factor = (1 + 0.0175)^24 = 1.5196
Pago Mensual = (2,760,000 × 0.0175 × 1.5196) / (1.5196 - 1)
Pago Mensual = 73,380 / 0.5196 = 141,230 COP/mes
```

### 2. Para Mostrar el Costo Real

La **tasa efectiva anual** muestra el costo real del crédito, útil para:
- Comparar diferentes opciones de financiamiento
- Entender cuánto realmente pagas de intereses
- Cumplir con regulaciones financieras

---

## Ejemplo Completo

### Datos de Entrada:
- **Equipo**: 500 USD
- **Garantía**: 100 USD
- **Total USD**: 600 USD
- **Utilidad**: 15%
- **Costo con Utilidad**: 690 USD
- **TRM**: 4,000
- **Costo Equipo COP**: 2,760,000 COP
- **Tasa Nominal**: 21%
- **Plazo**: 24 meses

### Cálculo de Tasas:

**1. Tasa Mensual:**
```
Tasa Mensual = 21% / 12 = 1.75% mensual
```

**2. Tasa Mensual Decimal (para cálculos):**
```
Tasa Mensual Decimal = 1.75% / 100 = 0.0175
```

**3. Tasa Efectiva Anual:**
```
Tasa Mensual Decimal = 0.0175
Tasa Efectiva = ((1 + 0.0175)^12 - 1) × 100
Tasa Efectiva = 23.14%
```

### Cálculo del Pago Mensual:

**Usando la fórmula PMT:**
```
Factor = (1 + 0.0175)^24 = 1.5196
Pago Base = (2,760,000 × 0.0175 × 1.5196) / (1.5196 - 1)
Pago Base = 141,230 COP/mes
```

**Si hay servicios:**
```
Servicio Mensual = 50,000 COP
Pago Mensual Total = 141,230 + 50,000 = 191,230 COP/mes
```

---

## ¿Por qué Importa la Tasa de Interés?

### 1. **Afecta el Pago Mensual**
- Mayor tasa = Mayor pago mensual
- Menor tasa = Menor pago mensual

**Ejemplo:**
```
Capital: $2,760,000
Plazo: 24 meses

Tasa 18% → Pago Mensual: ~135,000 COP
Tasa 21% → Pago Mensual: ~141,000 COP
Tasa 24% → Pago Mensual: ~147,000 COP
```

### 2. **Afecta el Total a Pagar**
- Mayor tasa = Más intereses = Más dinero total
- Menor tasa = Menos intereses = Menos dinero total

**Ejemplo:**
```
Capital: $2,760,000
Plazo: 24 meses

Tasa 18% → Total: ~3,240,000 COP
Tasa 21% → Total: ~3,384,000 COP
Tasa 24% → Total: ~3,528,000 COP
```

### 3. **Afecta la Competitividad**
- Tasas más bajas = Ofertas más atractivas
- Tasas más altas = Ofertas menos competitivas

---

## Preguntas Frecuentes

### ¿Por qué la Tasa Efectiva es Mayor que la Nominal?

Porque considera la **capitalización** (reinversión de intereses). Cada mes pagas intereses, y esos intereses se suman al capital para calcular los intereses del siguiente mes.

**Ejemplo simplificado:**
```
Mes 1: Capital $1,000,000, Interés 1.75% = $17,500
Mes 2: Capital $1,017,500, Interés 1.75% = $17,806
...
Al final del año: Tasa efectiva = 23.14% (no 21%)
```

### ¿Qué Tasa Debo Usar para Comparar?

Usa la **Tasa Efectiva Anual** porque:
- Muestra el costo real del crédito
- Permite comparar diferentes opciones
- Es la tasa que realmente pagas

### ¿Puedo Cambiar la Tasa Nominal?

Sí, puedes cambiarla en cualquier momento. La calculadora recalculará automáticamente:
- Tasa Mensual
- Tasa Efectiva Anual
- Pago Mensual
- Total a Pagar

### ¿Qué Tasa Usa el Banco?

Los bancos generalmente te ofrecen la **Tasa Nominal**. La calculadora te muestra también la **Tasa Efectiva** para que sepas el costo real.

---

## Fórmulas Matemáticas Detalladas

### Conversión de Tasa Nominal a Mensual

```
Tasa Mensual (%) = Tasa Nominal (%) / 12
Tasa Mensual Decimal = Tasa Mensual (%) / 100
```

### Conversión de Tasa Nominal a Efectiva Anual

```
Tasa Mensual Decimal = (Tasa Nominal / 100) / 12
Tasa Efectiva Decimal = (1 + Tasa Mensual Decimal)^12 - 1
Tasa Efectiva (%) = Tasa Efectiva Decimal × 100
```

### Cálculo del Pago Mensual (PMT)

```
Tasa Mensual Decimal = (Tasa Nominal / 100) / 12
Factor = (1 + Tasa Mensual Decimal)^Plazo
Pago Mensual = (Capital × Tasa Mensual Decimal × Factor) / (Factor - 1)
```

---

## Tabla de Referencia Rápida

| Tasa Nominal | Tasa Mensual | Tasa Efectiva Anual |
|--------------|--------------|---------------------|
| 15% | 1.25% | 16.08% |
| 18% | 1.50% | 19.56% |
| 21% | 1.75% | 23.14% |
| 24% | 2.00% | 26.82% |
| 27% | 2.25% | 30.60% |
| 30% | 2.50% | 34.49% |

---

## Resumen

1. **Tasa Nominal**: La que ingresas (21%)
2. **Tasa Mensual**: Se calcula automáticamente (1.75%)
3. **Tasa Efectiva**: Muestra el costo real (23.14%)
4. **Uso Principal**: Calcular el pago mensual con la fórmula PMT
5. **Importancia**: Afecta directamente cuánto pagas cada mes y en total

---

*Documento actualizado: [Fecha actual]*
