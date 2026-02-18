# -*- coding: utf-8 -*-

from odoo import api, fields, models
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class IrAttachment(models.Model):
    """Extender ir.attachment para agregar limpieza automática de PDFs temporales."""
    _inherit = 'ir.attachment'

    @api.model
    def cleanup_temp_life_sheet_pdfs(self, days_old=7):
        """Limpiar attachments temporales de hojas de vida más antiguos que X días.
        
        :param days_old: Días de antigüedad para considerar un attachment como eliminable (default: 7)
        :return: Número de attachments eliminados
        """
        cutoff_date = fields.Datetime.now() - timedelta(days=days_old)
        
        # Buscar attachments de hojas de vida PDFs temporales
        domain = [
            ('res_model', '=', 'res.partner'),
            ('name', 'ilike', 'Hojas_de_Vida_'),
            ('mimetype', '=', 'application/pdf'),
            ('create_date', '<', cutoff_date),
        ]
        
        old_attachments = self.search(domain)
        count = len(old_attachments)
        
        if count > 0:
            _logger.info("Limpiando %d attachments temporales de hojas de vida (más antiguos de %d días)", count, days_old)
            old_attachments.unlink()
            _logger.info("Se eliminaron %d attachments temporales", count)
        else:
            _logger.info("No hay attachments temporales de hojas de vida para limpiar")
        
        return count

