# Calculadora de Costos y Renting - Manual de Usuario

## 📋 Tabla de Contenidos

1. [Introducción](#introducción)
2. [Instalación](#instalación)
3. [Configuración Inicial](#configuración-inicial)
4. [Uso de la Calculadora de Equipos](#uso-de-la-calculadora-de-equipos)
5. [Uso de la Calculadora de Renting](#uso-de-la-calculadora-de-renting)
6. [Uso del APU de Servicios](#uso-del-apu-de-servicios)
7. [Parámetros Financieros](#parámetros-financieros)
8. [Ejemplos Prácticos](#ejemplos-prácticos)
9. [Preguntas Frecuentes](#preguntas-frecuentes)

---

## Introducción

El módulo **Calculadora de Costos y Renting** es una herramienta completa para calcular costos de equipos informáticos, opciones de renting y análisis de precios unitarios (APU) para servicios técnicos.

### Características Principales

- ✅ Cálculo automático de costos en USD y COP
- ✅ Conversión de moneda usando TRM (Tasa Representativa del Mercado)
- ✅ Cálculo de tasas de interés (nominal, mensual, efectiva anual)
- ✅ Cálculo de pagos mensuales con función PMT
- ✅ Análisis de costos por hora de recursos (vehículos, técnicos, internet)
- ✅ Proyecciones de flujos de servicio hasta 48 meses
- ✅ Comparación de diferentes plazos de pago

---

## Instalación

### Requisitos Previos

- Odoo 18.0 o superior
- Módulos base: `base`, `product`, `sale`

### Pasos de Instalación

1. **Copiar el módulo** a la carpeta de addons personalizados:
   ```
   custom_addons_Productiva/calculadora_costos/
   ```

2. **Actualizar la lista de aplicaciones** en Odoo:
   - Ir a: **Aplicaciones** → **Actualizar lista de aplicaciones**

3. **Instalar el módulo**:
   - Buscar: "Calculadora de Costos y Renting"
   - Clic en **Instalar**

4. **Verificar la instalación**:
   - Debe aparecer el menú **"Calculadora de Costos"** en el menú principal

---

## Configuración Inicial

### 1. Configurar Parámetros Financieros

Antes de usar las calculadoras, es importante configurar los parámetros financieros globales:

1. Ir a: **Calculadora de Costos** → **Configuración** → **Parámetros Financieros**

2. Configurar los siguientes valores:

   | Campo | Descripción | Valor Recomendado |
   |-------|-------------|-------------------|
   | **TRM Actual** | Tasa Representativa del Mercado (COP/USD) | 4000.0 |
   | **Factor de Utilidad por Defecto** | Factor aplicado al costo (0.9 = 90%) | 0.9 |
   | **Tasa Nominal por Defecto (%)** | Tasa de interés nominal anual | 21.0 |
   | **Margen de Servicio por Defecto (%)** | Margen aplicado a servicios técnicos | 15.0 |
   | **Horas de Trabajo por Mes** | Horas laborales mensuales | 240 |
   | **Días de Trabajo por Mes** | Días laborales mensuales | 30 |
   | **Horas de Trabajo por Día** | Horas laborales diarias | 8 |
   | **Años de Depreciación Vehículo** | Vida útil para depreciación | 7 |

3. **Guardar** los cambios

> **Nota**: Estos valores se usarán como valores por defecto al crear nuevas calculadoras, pero pueden ser modificados en cada registro individual.

---

## Uso de la Calculadora de Equipos

La Calculadora de Equipos permite calcular el costo total y pagos mensuales de equipos informáticos incluyendo garantías, servicios técnicos, intereses y opciones de compra.

### Crear una Nueva Calculadora

1. Ir a: **Calculadora de Costos** → **Calculadora de Equipos**

2. Clic en **Crear**

3. **Completar la información básica**:
   - **Nombre del Equipo**: Ej: "Equipo All in One"
   - **Valor en USD**: Precio del equipo en dólares (ej: 480)
   - **Valor Garantía Extendida (USD)**: Costo adicional de garantía (ej: 20)

4. **Configurar conversión a COP** (pestaña "Costos del Equipo"):
   - **Factor de Utilidad**: Por defecto 0.9 (90%)
   - **TRM (COP/USD)**: Tasa de cambio actual (se carga automáticamente desde parámetros)

   > El sistema calculará automáticamente:
   - Costo Total USD
   - Costo con Utilidad (USD)
   - Costo Total (COP)

5. **Configurar Servicios Técnicos** (pestaña "Servicios Técnicos"):
   - **Costo Servicios Completos**: Costo base de servicios (ej: 0)
   - **Margen de Servicio (%)**: Por defecto 15%

   > El sistema calculará automáticamente el **Servicio con Margen**

6. **Configurar Parámetros Financieros** (pestaña "Parámetros Financieros"):
   - **Tasa Nominal (%)**: Por defecto 21%
   - **Plazo (Meses)**: 24, 36 o 48 meses

   > El sistema calculará automáticamente:
   - Tasa Mensual
   - Tasa Efectiva Anual

7. **Configurar Opción de Compra** (pestaña "Opción de Compra"):
   - **Porcentaje Opción de Compra (%)**: Ej: 20% (20% del valor del equipo)

   > El sistema calculará automáticamente el **Valor Opción de Compra**

8. **Ver Resumen** (pestaña "Resumen"):
   - Aquí se muestran todos los valores calculados:
     - Costo Total (COP)
     - Pago Mensual (COP)
     - Plazo (meses)
     - Total a Pagar

9. **Guardar** el registro

### Ejemplo de Cálculo

**Datos de entrada:**
- Valor en USD: 480
- Garantía Extendida: 20
- Factor de Utilidad: 0.9
- TRM: 4000
- Tasa Nominal: 21%
- Plazo: 24 meses
- Opción de Compra: 20%

**Resultados calculados:**
- Costo Total USD: 500
- Costo con Utilidad USD: 555.56
- Costo Total COP: 2,222,222
- Pago Mensual COP: ~120,000 (aproximado, depende de servicios)

---

## Uso de la Calculadora de Renting

La Calculadora de Renting permite calcular costos y pagos mensuales para contratos de renting con diferentes plazos.

### Crear una Nueva Calculadora de Renting

1. Ir a: **Calculadora de Costos** → **Calculadora de Renting**

2. Clic en **Crear**

3. **Completar información básica**:
   - **Nombre del Contrato**: Ej: "Renting Equipo All in One"
   - **Valor en USD**: Precio del equipo
   - **Valor Garantía Extendida (USD)**: Si aplica

4. **Configurar conversión** (pestaña "Costos del Equipo"):
   - Similar a la calculadora de equipos

5. **Configurar Servicios** (pestaña "Servicios Técnicos"):
   - **Costo Servicios Completos**: Costo base
   - **Factor Margen Servicio**: Por defecto 0.8 (80%)

6. **Configurar Parámetros Financieros** (pestaña "Parámetros Financieros"):
   - **Tasa Nominal (%)**: Por defecto 21%
   - **Plazo (Meses)**: 24, 36 o 48 meses

7. **Ver Comparación de Plazos** (pestaña "Comparación de Plazos"):
   - El sistema calcula automáticamente los valores para:
     - 24 Meses
     - 36 Meses
     - 48 Meses

   > Esto permite comparar fácilmente diferentes opciones de plazo

8. **Guardar** el registro

### Ventajas de la Comparación de Plazos

La calculadora de renting permite ver de un vistazo cómo varían los pagos mensuales según el plazo elegido, facilitando la toma de decisiones.

---

## Uso del APU de Servicios

El APU (Análisis de Precios Unitarios) de Servicios calcula los costos por hora de diferentes recursos técnicos.

### Crear un Nuevo APU de Servicio

1. Ir a: **Calculadora de Costos** → **APU - Servicios**

2. Clic en **Crear**

3. **Completar información básica**:
   - **Nombre del Servicio**: Ej: "Servicio Técnico General"

4. **Configurar Parámetros de Vehículo** (pestaña "Parámetros de Vehículo"):
   - **Costo del Vehículo**: Ej: 35,000,000
   - **Años Depreciación Vehículo**: Por defecto 7
   - **Costo Mantenimiento Vehículo/Mes**: Ej: 350,000
   - **Salario Conductor**: Ej: 1,100,000
   - **Factor Prestaciones Conductor**: Por defecto 1.52

   > El sistema calculará automáticamente el **Costo Hora Vehículo**

5. **Configurar Parámetros de Técnico** (pestaña "Parámetros de Técnico"):
   - **Salario Técnico**: Ej: 1,650,000
   - **Factor Prestaciones Técnico**: Por defecto 1.55

   > El sistema calculará automáticamente el **Costo Hora Técnico**

6. **Configurar Parámetros de Internet** (pestaña "Parámetros de Internet"):
   - **Costo Internet Claro/Mes**: Ej: 340,000
   - **Costo Internet ETB/Mes**: Ej: 167,000
   - **Costo Infraestructura Total**: Ej: 3,200,000

   > El sistema calculará automáticamente el **Costo Hora Internet**

7. **Configurar Parámetros de Trabajo** (pestaña "Parámetros de Trabajo"):
   - **Horas de Trabajo por Mes**: Por defecto 240
   - **Días de Trabajo por Mes**: Por defecto 30
   - **Horas de Trabajo por Día**: Por defecto 8

8. **Ver Costos Calculados** (pestaña "Costos Calculados"):
   - Aquí se muestran todos los costos calculados:
     - Costo Hora Vehículo
     - Costo Hora Técnico
     - Costo Hora Internet
     - Costo Hora Soporte Remoto
     - Costo Alistamiento
     - Costo Instalación

9. **Guardar** el registro

### Uso de los Costos Calculados

Los costos calculados en el APU pueden ser utilizados para:
- Cotizar servicios técnicos
- Calcular costos de proyectos
- Establecer precios de servicios
- Análisis de rentabilidad

---

## Parámetros Financieros

Los Parámetros Financieros son valores globales que se aplican por defecto a todas las calculadoras.

### Acceder a Parámetros Financieros

1. Ir a: **Calculadora de Costos** → **Configuración** → **Parámetros Financieros**

2. Solo existe **un registro** de parámetros (único en el sistema)

3. **Modificar los valores** según sea necesario

4. **Guardar** los cambios

> **Importante**: Los cambios en los parámetros financieros afectarán a las nuevas calculadoras creadas, pero NO a las calculadoras ya existentes.

### Actualizar TRM

La TRM (Tasa Representativa del Mercado) debe actualizarse periódicamente:

1. Consultar la TRM actual en el Banco de la República de Colombia
2. Ir a Parámetros Financieros
3. Actualizar el campo **TRM Actual**
4. Guardar

> **Sugerencia**: Se puede automatizar la actualización de TRM mediante integración con APIs externas (requiere desarrollo adicional).

---

## Ejemplos Prácticos

### Ejemplo 1: Calcular Costo de un Equipo Portátil

**Escenario**: Necesitas calcular el costo de un equipo portátil con las siguientes características:
- Precio: $480 USD
- Garantía extendida: $20 USD
- Plazo de pago: 24 meses
- Opción de compra: 20%

**Pasos**:

1. Crear nueva Calculadora de Equipos
2. Ingresar:
   - Nombre: "Portátil HP ProBook"
   - Valor en USD: 480
   - Valor Garantía: 20
   - Plazo: 24 meses
   - Porcentaje Opción de Compra: 20%

3. El sistema calculará automáticamente:
   - Costo Total COP
   - Pago Mensual
   - Total a Pagar

### Ejemplo 2: Comparar Opciones de Renting

**Escenario**: Necesitas comparar un equipo en renting a 24, 36 y 48 meses.

**Pasos**:

1. Crear nueva Calculadora de Renting
2. Ingresar los datos del equipo
3. Ir a la pestaña "Comparación de Plazos"
4. Ver los valores calculados para cada plazo
5. Comparar y decidir cuál opción es más conveniente

### Ejemplo 3: Calcular Costo de Servicio Técnico

**Escenario**: Necesitas saber cuánto cuesta una hora de servicio técnico.

**Pasos**:

1. Crear nuevo APU de Servicio
2. Configurar todos los parámetros (vehículo, técnico, internet, etc.)
3. Ir a la pestaña "Costos Calculados"
4. Ver el "Costo Hora Técnico"
5. Usar este valor para cotizar servicios

---

## Preguntas Frecuentes

### ¿Cómo se calcula el Pago Mensual?

El pago mensual se calcula usando la función PMT (Payment), que es equivalente a la función PMT de Excel:

```
PMT = (PV × r × (1 + r)^n) / ((1 + r)^n - 1) - (FV × r) / ((1 + r)^n - 1) + Servicio
```

Donde:
- PV = Valor Presente (Costo Total COP)
- r = Tasa Mensual (Tasa Nominal / 12)
- n = Número de Períodos (Plazo en meses)
- FV = Valor Futuro (Opción de Compra)
- Servicio = Servicio con Margen

### ¿Qué es el Factor de Utilidad?

El Factor de Utilidad es un porcentaje que se aplica al costo para obtener el precio de venta. Por ejemplo:
- Factor 0.9 (90%): Si el costo es $100, el precio será $111.11
- Factor 1.0 (100%): Si el costo es $100, el precio será $100

### ¿Puedo modificar los valores calculados?

No, los valores calculados son de solo lectura y se actualizan automáticamente cuando cambias los valores de entrada. Esto garantiza la precisión de los cálculos.

### ¿Cómo actualizo la TRM?

1. Ve a **Parámetros Financieros**
2. Actualiza el campo **TRM Actual**
3. Guarda los cambios

Los nuevos cálculos usarán la TRM actualizada.

### ¿Puedo exportar los resultados a Excel?

Sí, puedes exportar cualquier lista de calculadoras usando la función estándar de Odoo:
1. Ir a la lista de calculadoras
2. Clic en **Acción** → **Exportar**
3. Seleccionar los campos a exportar
4. Descargar el archivo Excel

### ¿Los cálculos son precisos?

Sí, los cálculos utilizan precisión decimal de 10 dígitos y siguen las fórmulas financieras estándar equivalentes a las funciones de Excel (PMT, EFFECT, etc.).

### ¿Puedo usar este módulo para cotizaciones?

Sí, los valores calculados pueden ser utilizados para crear cotizaciones. Se recomienda:
1. Calcular el costo en la calculadora
2. Usar los valores calculados para crear cotizaciones en el módulo de Ventas
3. Mantener la trazabilidad entre la calculadora y la cotización

---

## Soporte y Contacto

Para soporte técnico o consultas sobre el módulo:
- Revisar la documentación técnica en `ANALISIS_CALCULADORA2025.md`
- Contactar al equipo de desarrollo

---

## Changelog

### Versión 18.0.1.0.0
- Versión inicial del módulo
- Calculadora de Equipos
- Calculadora de Renting
- APU de Servicios
- Parámetros Financieros
- Vistas y menús completos
- Seguridad configurada

---

*Última actualización: [Fecha actual]*
