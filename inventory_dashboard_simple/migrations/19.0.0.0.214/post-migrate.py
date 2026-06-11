# -*- coding: utf-8 -*-
"""Registrar grupo PreBaja en dashboard y vincular tipo de operación."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    env['inventory.dashboard.group'].init_groups()
    _logger.info('Migracion 19.0.0.0.214: grupos dashboard (PreBaja) sincronizados.')
