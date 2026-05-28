# -*- coding: utf-8 -*-

import re
import logging

_logger = logging.getLogger(__name__)


def _mesa_pre_init_clean_helpdesk_ticket_views(cr):
    """Limpia vistas helpdesk.ticket rotas (v.124–130). Se ejecuta solo en -u del módulo."""
    patterns = [
    