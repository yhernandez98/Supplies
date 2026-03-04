# 📚 **EJEMPLOS DE USO - MÓDULO DIAN NIT COLOMBIA**

## 🎯 **CASOS PRÁCTICOS DE IMPLEMENTACIÓN**

### **Ejemplo 1: Creación de Empresa con NIT**

```python
# Crear empresa colombiana con NIT
partner_vals = {
    'name': 'Empresa Ejemplo S.A.S.',
    'company_type': 'company',
    'country_id': self.env.ref('base.co').id,  # Colombia
    'dian_nit_number': '900123456',
    'dian_tax_regime': 'simplified',
    'dian_responsibility_code': '1',
    'dian_commercial_name': 'Empresa Ejemplo',
    'dian_economic_activity': '6201',
}

partner = self.env['res.partner'].create(partner_vals)

# El sistema automáticamente:
# 1. Calcula el DV: 900123456 -> DV = 3
# 2. Sincroniza con VAT: 900123456-3
# 3. Valida según algoritmo DIAN
```

### **Ejemplo 2: Validación Manual de NIT**

```python
# Validar NIT existente
partner = self.env['res.partner'].browse(partner_id)

# Calcular DV manualmente
calculated_dv = partner._compute_digit_verification_dian('800123456')
print(f"DV calculado: {calculated_dv}")  # Output: 7

# Validar NIT completo
is_valid, message = partner._validate_dian_nit_complete('800123456', '7')
print(f"Validación: {is_valid}, Mensaje: {message}")
```

### **Ejemplo 3: Sincronización con VAT**

```python
# Sincronizar NIT con VAT para facturación
partner = self.env['res.partner'].browse(partner_id)

# Método automático
partner._sync_dian_nit_with_vat()

# Verificar sincronización
print(f"VAT sincronizado: {partner.dian_vat_synced}")
print(f"VAT actual: {partner.vat}")
```

### **Ejemplo 4: Búsqueda por Criterios DIAN**

```python
# Buscar empresas por régimen tributario
simplified_partners = self.env['res.partner'].search([
    ('dian_tax_regime', '=', 'simplified'),
    ('dian_is_colombia', '=', True)
])

# Buscar empresas con NIT validado
validated_partners = self.env['res.partner'].search([
    ('dian_nit_validated', '=', True),
    ('dian_is_colombia', '=', True)
])

# Buscar por código de responsabilidad
responsibility_partners = self.env['res.partner'].search([
    ('dian_responsibility_code', '=', '1'),
    ('dian_is_colombia', '=', True)
])
```

### **Ejemplo 5: Acciones desde Botones**

```python
# Ejecutar acciones desde código Python
partner = self.env['res.partner'].browse(partner_id)

# Calcular DV
result = partner.action_dian_calculate_dv()
# Retorna notificación con DV calculado

# Sincronizar con VAT
result = partner.action_dian_sync_with_vat()
# Retorna notificación de sincronización exitosa

# Validar NIT
result = partner.action_dian_validate_nit()
# Retorna notificación con resultado de validación

# Limpiar campos NIT
result = partner.action_dian_clear_nit()
# Retorna notificación de limpieza
```

---

## 🔧 **INTEGRACIÓN CON FACTURACIÓN**

### **Ejemplo 6: Crear Factura con NIT DIAN**

```python
# Crear factura usando NIT DIAN
partner = self.env['res.partner'].search([
    ('dian_nit_full', '=', '800123456-7')
], limit=1)

invoice_vals = {
    'partner_id': partner.id,
    'move_type': 'out_invoice',
    'invoice_line_ids': [(0, 0, {
        'name': 'Producto de prueba',
        'quantity': 1,
        'price_unit': 100000,
    })]
}

invoice = self.env['account.move'].create(invoice_vals)
# El VAT del partner se usa automáticamente en la factura
```

### **Ejemplo 7: Validar NIT antes de Facturar**

```python
def validate_partner_for_invoicing(self, partner_id):
    """Validar que el partner esté listo para facturación"""
    partner = self.env['res.partner'].browse(partner_id)
    
    if not partner.dian_is_colombia:
        return False, "Partner no es de Colombia"
    
    if not partner.dian_nit_validated:
        return False, "NIT no validado según DIAN"
    
    if not partner.dian_vat_synced:
        return False, "VAT no sincronizado con NIT"
    
    return True, "Partner listo para facturación"

# Uso
is_ready, message = validate_partner_for_invoicing(partner_id)
```

---

## 📊 **REPORTES Y CONSULTAS**

### **Ejemplo 8: Reporte de Empresas por Régimen**

```python
# Generar reporte de empresas por régimen tributario
def generate_tax_regime_report(self):
    """Generar reporte de empresas por régimen tributario"""
    
    regimes = ['simplified', 'common', 'special', 'large_taxpayer']
    report_data = {}
    
    for regime in regimes:
        partners = self.env['res.partner'].search([
            ('dian_tax_regime', '=', regime),
            ('dian_is_colombia', '=', True),
            ('company_type', '=', 'company')
        ])
        
        report_data[regime] = {
            'count': len(partners),
            'partners': partners.mapped('name'),
            'nits': partners.mapped('dian_nit_full')
        }
    
    return report_data

# Uso
report = generate_tax_regime_report()
print(f"Regimen Simplificado: {report['simplified']['count']} empresas")
```

### **Ejemplo 9: Validación Masiva de NITs**

```python
def validate_all_nits(self):
    """Validar todos los NITs de empresas colombianas"""
    
    partners = self.env['res.partner'].search([
        ('dian_is_colombia', '=', True),
        ('dian_nit_number', '!=', False),
        ('company_type', '=', 'company')
    ])
    
    validation_results = []
    
    for partner in partners:
        is_valid, message = partner._validate_dian_nit_complete(
            partner.dian_nit_number, 
            partner.dian_nit_dv
        )
        
        validation_results.append({
            'partner': partner.name,
            'nit': partner.dian_nit_full,
            'valid': is_valid,
            'message': message
        })
    
    return validation_results

# Uso
results = validate_all_nits()
for result in results:
    status = "✅" if result['valid'] else "❌"
    print(f"{status} {result['partner']}: {result['nit']} - {result['message']}")
```

---

## 🎨 **PERSONALIZACIÓN DE VISTAS**

### **Ejemplo 10: Vista Personalizada para DIAN**

```xml
<!-- Vista personalizada para mostrar solo información DIAN -->
<record id="view_partner_dian_only" model="ir.ui.view">
    <field name="name">res.partner.dian.only</field>
    <field name="model">res.partner</field>
    <field name="arch" type="xml">
        <form string="Información DIAN">
            <group>
                <group>
                    <field name="name"/>
                    <field name="dian_nit_full"/>
                    <field name="dian_tax_regime"/>
                </group>
                <group>
                    <field name="dian_responsibility_code"/>
                    <field name="dian_commercial_name"/>
                    <field name="dian_economic_activity"/>
                </group>
            </group>
            <div class="oe_button_box" name="button_box">
                <button name="action_dian_validate_nit" 
                        type="object" 
                        class="oe_stat_button" 
                        icon="fa-check-circle">
                    <field name="dian_nit_validated" widget="statinfo" string="Validado"/>
                </button>
            </div>
        </form>
    </field>
</record>
```

### **Ejemplo 11: Acción de Ventana Personalizada**

```xml
<!-- Acción para mostrar vista DIAN personalizada -->
<record id="action_partner_dian_view" model="ir.actions.act_window">
    <field name="name">Vista DIAN</field>
    <field name="res_model">res.partner</field>
    <field name="view_mode">form</field>
    <field name="view_id" ref="view_partner_dian_only"/>
    <field name="target">current</field>
    <field name="context">{'default_dian_is_colombia': True}</field>
</record>
```

---

## 🔍 **DEBUGGING Y TROUBLESHOOTING**

### **Ejemplo 12: Debug de Cálculo de DV**

```python
def debug_dv_calculation(self, nit_number):
    """Debug del cálculo de dígito de verificación"""
    
    print(f"NIT a calcular: {nit_number}")
    
    weights = [71, 67, 59, 53, 47, 43, 41, 37, 29, 23, 19, 17, 13, 7, 3]
    nit_reversed = nit_number[::-1]
    
    print(f"NIT invertido: {nit_reversed}")
    
    total = 0
    for i, digit in enumerate(nit_reversed):
        if i < len(weights):
            weight = weights[i]
            product = int(digit) * weight
            total += product
            print(f"Posición {i}: {digit} × {weight} = {product}")
    
    print(f"Total: {total}")
    
    remainder = total % 11
    print(f"Resto: {remainder}")
    
    if remainder < 2:
        dv = str(remainder)
    else:
        dv = str(11 - remainder)
    
    print(f"DV calculado: {dv}")
    return dv

# Uso
dv = debug_dv_calculation("800123456")
```

### **Ejemplo 13: Validación de Constraints**

```python
def test_constraints(self):
    """Probar constraints del modelo"""
    
    # Test NIT inválido
    try:
        partner = self.env['res.partner'].create({
            'name': 'Test Partner',
            'dian_nit_number': '123',  # Muy corto
            'country_id': self.env.ref('base.co').id
        })
    except ValidationError as e:
        print(f"Constraint funcionando: {e}")
    
    # Test DV inválido
    try:
        partner = self.env['res.partner'].create({
            'name': 'Test Partner 2',
            'dian_nit_number': '800123456',
            'dian_nit_dv': '99',  # DV incorrecto
            'country_id': self.env.ref('base.co').id
        })
    except ValidationError as e:
        print(f"Validación DV funcionando: {e}")
```

---

## 📈 **MÉTRICAS Y ESTADÍSTICAS**

### **Ejemplo 14: Estadísticas del Módulo**

```python
def get_module_statistics(self):
    """Obtener estadísticas del módulo DIAN"""
    
    total_partners = self.env['res.partner'].search_count([
        ('dian_is_colombia', '=', True)
    ])
    
    with_nit = self.env['res.partner'].search_count([
        ('dian_is_colombia', '=', True),
        ('dian_nit_number', '!=', False)
    ])
    
    validated_nits = self.env['res.partner'].search_count([
        ('dian_is_colombia', '=', True),
        ('dian_nit_validated', '=', True)
    ])
    
    synced_vat = self.env['res.partner'].search_count([
        ('dian_is_colombia', '=', True),
        ('dian_vat_synced', '=', True)
    ])
    
    statistics = {
        'total_colombian_partners': total_partners,
        'partners_with_nit': with_nit,
        'validated_nits': validated_nits,
        'synced_vat': synced_vat,
        'validation_rate': (validated_nits / with_nit * 100) if with_nit > 0 else 0,
        'sync_rate': (synced_vat / with_nit * 100) if with_nit > 0 else 0
    }
    
    return statistics

# Uso
stats = get_module_statistics()
print(f"Partners colombianos: {stats['total_colombian_partners']}")
print(f"Con NIT: {stats['partners_with_nit']}")
print(f"NITs validados: {stats['validated_nits']}")
print(f"Tasa de validación: {stats['validation_rate']:.2f}%")
```

---

## 🎉 **CONCLUSIÓN**

Estos ejemplos muestran la versatilidad y potencia del módulo `dian_nit_colombia`. Desde operaciones básicas hasta integraciones avanzadas, el módulo proporciona todas las herramientas necesarias para una gestión completa del NIT colombiano con cumplimiento DIAN.

**¡El módulo está listo para implementar en cualquier escenario de negocio colombiano!** 🚀

