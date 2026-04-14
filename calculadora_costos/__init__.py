from . import models
from . import wizard


def post_init_hook(cr, registry):
    """Migración de datos y limpieza tras eliminar parámetros globales."""
    from odoo import api

    cr.execute(
        """
        UPDATE calculadora_costos
        SET tipo_operacion = %s
        WHERE tipo_operacion = %s
        """,
        ('suscripcion', 'renting'),
    )
    env = api.Environment(cr, 2, {})
    rule = env.ref('calculadora_costos.parametros_financieros_rule', raise_if_not_found=False)
    if rule:
        rule.unlink()
