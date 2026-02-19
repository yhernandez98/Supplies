# -*- coding: utf-8 -*-
"""
Elimina el campo provider_cut_off_day de ir.model.fields por SQL para evitar
KeyError en mail al actualizar (mail intenta acceder al campo al desvincular el registro).
La fecha de corte del proveedor es la misma que las condiciones del cliente.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # Eliminar ir.model.data que apunten al campo (evita FK y que process_end intente unlink)
    cr.execute("""
        DELETE FROM ir_model_data
        WHERE model = 'ir.model.fields'
          AND res_id IN (
              SELECT id FROM ir_model_fields
              WHERE model = 'license.assignment' AND name = 'provider_cut_off_day'
          )
    """)
    # Eliminar el registro del campo para que mail no lo desvincule por ORM
    cr.execute("""
        DELETE FROM ir_model_fields
        WHERE model = 'license.assignment' AND name = 'provider_cut_off_day'
    """)
    if cr.rowcount:
        _logger.info("subscription_licenses: removed ir.model.fields provider_cut_off_day (date de corte = condiciones cliente)")
