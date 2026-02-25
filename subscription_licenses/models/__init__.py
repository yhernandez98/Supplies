# -*- coding: utf-8 -*-

from . import trm
from . import license_category
from . import license_template
from . import license_assignment
from . import license_equipment
from . import res_config_settings
# from . import license_trm_wizard  # Eliminado - ya no se usa Recalcular TRM
from . import license_report_wizard
# Modelos adicionales para funcionalidad extendida
from . import exchange_rate_monthly
from . import product_license_type
from . import subscription_product_grouped  # Añade license_type_id a subscription.product.grouped
from . import stock_lot  # Extender stock.lot para mostrar licencias
from . import license_provider_stock  # Paso 1: Modelo básico activado ✓
from . import product_product  # Restringir selector de producto a licencias del módulo
# from . import res_partner  # DESACTIVADO: al activarlo el servidor cae (conflicto o carga de res.partner)
from . import license_provider_partner  # Lista de proveedores (contactos elegidos)
from . import license_provider_report_line  # Líneas de reporte/facturación del proveedor (unifica reportes Excel)
from . import license_provider_report_group  # Agrupación por cliente (un registro por cliente para vista resumida)
from . import license_provider_delete_wizard  # Wizard de confirmación para eliminar proveedores
# from . import subscription_license_assignment  # Desactivado: ya no se usa
# from . import subscription_subscription  # Desactivado: ya no se usa

