# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
import traceback
import sys
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class DebugLog(models.TransientModel):
    """Modelo temporal para mostrar información de debug y logs."""
    _name = 'mesa_ayuda.debug.log'
    _description = 'Debug Log Viewer'
    
    log_info = fields.Html(
        string='Información del Sistema',
        readonly=True,
    )
    
    def action_show_logs(self):
        """Mostrar información de debug y logs recientes."""
        self.ensure_one()
        
        info_lines = []
        info_lines.append("<h2>🔍 Información del Sistema - Mesa de Ayuda</h2>")
        info_lines.append("<hr/>")
        
        # Información del usuario
        info_lines.append("<h3>👤 Usuario Actual</h3>")
        info_lines.append(f"<p><strong>Usuario:</strong> {self.env.user.name} (ID: {self.env.user.id})</p>")
        info_lines.append(f"<p><strong>Compañía:</strong> {self.env.company.name} (ID: {self.env.company.id})</p>")
        info_lines.append(f"<p><strong>Fecha/Hora:</strong> {fields.Datetime.now()}</p>")
        
        # Información de módulos
        info_lines.append("<hr/>")
        info_lines.append("<h3>📦 Módulos Instalados</h3>")
        try:
            helpdesk_module = self.env['ir.module.module'].search([('name', '=', 'helpdesk')], limit=1)
            if helpdesk_module:
                info_lines.append(f"<p><strong>Módulo Helpdesk:</strong> {'✅ Instalado' if helpdesk_module.state == 'installed' else '❌ No instalado'} ({helpdesk_module.state})</p>")
            else:
                info_lines.append("<p><strong>Módulo Helpdesk:</strong> ❌ No encontrado</p>")
        except Exception as e:
            info_lines.append(f"<p><strong>Error al verificar módulos:</strong> {str(e)}</p>")
        
        # Verificar modelos
        info_lines.append("<hr/>")
        info_lines.append("<h3>🔧 Estado de Modelos</h3>")
        models_to_check = [
            ('helpdesk.ticket', 'Tickets (Módulo Nativo)', True),
            ('repair.order', 'Órdenes de Reparación', False),
            ('maintenance.order', 'Órdenes de Mantenimiento', False),
            ('stock.lot.maintenance', 'Mantenimientos', False),
        ]
        
        for model_name, description, is_native in models_to_check:
            try:
                # Verificar si el modelo está en el registro
                if model_name in self.env.registry:
                    try:
                        model = self.env[model_name]
                        count = model.search_count([])
                        info_lines.append(f"<p><strong>{description}:</strong> ✅ <span style='color: green;'>ACTIVO</span> ({count} registros)</p>")
                    except Exception as e:
                        info_lines.append(f"<p><strong>{description}:</strong> ⚠️ <span style='color: orange;'>Error al acceder: {str(e)[:100]}</span></p>")
                else:
                    if is_native:
                        info_lines.append(f"<p><strong>{description}:</strong> ❌ <span style='color: red;'>No encontrado</span> (módulo helpdesk instalado pero modelo no disponible)</p>")
                    else:
                        info_lines.append(f"<p><strong>{description}:</strong> ⏸️ <span style='color: gray;'>DESACTIVADO</span> (comentado en models/__init__.py - listo para reactivar)</p>")
            except Exception as e:
                info_lines.append(f"<p><strong>{description}:</strong> ❌ <span style='color: red;'>Error: {str(e)[:100]}</span></p>")
        
        # Información de campos en mantenimientos
        info_lines.append("<hr/>")
        info_lines.append("<h3>📋 Estado de Campos en Mantenimientos</h3>")
        try:
            if 'stock.lot.maintenance' in self.env.registry:
                maintenance_model = self.env['stock.lot.maintenance']
                fields_to_check = [
                    ('ticket_id', 'helpdesk.ticket', 'Integración con Tickets'),
                    ('repair_order_id', 'repair.order', 'Integración con Reparaciones'),
                    ('component_change_ids', 'maintenance.component.change', 'Cambios de Componentes'),
                ]
                for field_name, related_model, field_desc in fields_to_check:
                    if hasattr(maintenance_model, field_name):
                        # Verificar si el modelo relacionado existe
                        if related_model in self.env.registry:
                            info_lines.append(f"<p><strong>{field_desc} ({field_name}):</strong> ✅ <span style='color: green;'>ACTIVO</span></p>")
                        else:
                            info_lines.append(f"<p><strong>{field_desc} ({field_name}):</strong> ⚠️ <span style='color: orange;'>Campo existe pero modelo relacionado desactivado</span></p>")
                    else:
                        info_lines.append(f"<p><strong>{field_desc} ({field_name}):</strong> ⏸️ <span style='color: gray;'>DESACTIVADO</span> (comentado en código)</p>")
            else:
                info_lines.append("<p>⚠️ Modelo stock.lot.maintenance no está disponible para verificar</p>")
        except Exception as e:
            info_lines.append(f"<p><strong>Error al verificar campos:</strong> {str(e)}</p>")
        
        # Estado de los archivos
        info_lines.append("<hr/>")
        info_lines.append("<h3>📁 Estado de Archivos del Módulo</h3>")
        info_lines.append("<p><em>Los siguientes archivos están <strong>temporalmente desactivados</strong> para evitar errores:</em></p>")
        info_lines.append("<ul>")
        info_lines.append("<li>⏸️ <code>models/helpdesk_ticket.py</code> - Desactivado en <code>__init__.py</code></li>")
        info_lines.append("<li>⏸️ <code>models/repair_order.py</code> - Desactivado en <code>__init__.py</code></li>")
        info_lines.append("<li>⏸️ <code>models/component_change.py</code> - Desactivado en <code>__init__.py</code></li>")
        info_lines.append("<li>⏸️ <code>views/helpdesk_ticket_views.xml</code> - Desactivado en <code>__manifest__.py</code></li>")
        info_lines.append("<li>⏸️ <code>views/repair_order_views.xml</code> - Desactivado en <code>__manifest__.py</code></li>")
        info_lines.append("</ul>")
        info_lines.append("<p><strong style='color: orange;'>⚠️ Razón:</strong> Estos archivos causaron errores al actualizar el módulo. Están listos para reactivarse cuando se resuelva el problema.</p>")
        
        # Información sobre logs del servidor
        info_lines.append("<hr/>")
        info_lines.append("<h3>📝 Cómo Ver Logs del Servidor</h3>")
        info_lines.append("<p><strong>Ubicación típica de logs en Odoo:</strong></p>")
        info_lines.append("<ul>")
        info_lines.append("<li><code>/var/log/odoo/odoo-server.log</code> (Linux)</li>")
        info_lines.append("<li><code>C:\\Program Files\\Odoo\\log\\odoo-server.log</code> (Windows)</li>")
        info_lines.append("<li>O donde esté configurado el parámetro <code>--logfile</code> en la configuración de Odoo</li>")
        info_lines.append("</ul>")
        
        info_lines.append("<p><strong style='color: red;'>🔍 COMANDOS MÁS ÚTILES PARA ENCONTRAR EL ERROR:</strong></p>")
        info_lines.append("<pre style='background: #fff3cd; padding: 10px; border-radius: 4px; border-left: 4px solid orange;'>")
        info_lines.append("# 1. Ver errores de los últimos 30 minutos:\n")
        info_lines.append("grep -i 'error\\|exception\\|traceback' /var/log/odoo/odoo-server.log | tail -50\n\n")
        info_lines.append("# 2. Buscar errores del módulo específico:\n")
        info_lines.append("grep -i 'mesa_ayuda_inventario' /var/log/odoo/odoo-server.log | tail -30\n\n")
        info_lines.append("# 3. Buscar errores al cargar módulos:\n")
        info_lines.append("grep -E 'loading|module.*mesa_ayuda|External ID|model.*helpdesk|model.*repair' /var/log/odoo/odoo-server.log | tail -30\n\n")
        info_lines.append("# 4. Ver traceback completo de errores:\n")
        info_lines.append("grep -A 30 'Traceback' /var/log/odoo/odoo-server.log | tail -100")
        info_lines.append("</pre>")
        
        info_lines.append("<p><strong>⚠️ Errores comunes que buscar:</strong></p>")
        info_lines.append("<ul>")
        info_lines.append("<li><code>External ID not found</code> - Vista o modelo no encontrado</li>")
        info_lines.append("<li><code>Invalid field</code> - Campo no existe o referencia incorrecta</li>")
        info_lines.append("<li><code>model_helpdesk_ticket</code> - Error relacionado con tickets</li>")
        info_lines.append("<li><code>model_repair_order</code> - Error relacionado con reparaciones</li>")
        info_lines.append("<li><code>ir.sequence</code> - Error de secuencia</li>")
        info_lines.append("</ul>")
        
        info_lines.append("<p><strong style='color: blue;'>💡 TIP:</strong> Copia el error completo desde 'Traceback' hasta el final y compártelo para una solución rápida.</p>")
        
        # Información de Python y Odoo
        info_lines.append("<hr/>")
        info_lines.append("<h3>🐍 Información Técnica</h3>")
        info_lines.append(f"<p><strong>Versión de Python:</strong> {sys.version.split()[0]}</p>")
        info_lines.append(f"<p><strong>Ruta de Python:</strong> {sys.executable}</p>")
        try:
            version_info = self.env['ir.module.module'].sudo().search([('name', '=', 'base')], limit=1)
            if version_info:
                info_lines.append(f"<p><strong>Versión de Odoo:</strong> {version_info.latest_version or 'Desconocida'}</p>")
        except:
            pass
        
        self.log_info = '\n'.join(info_lines)
        
        return {
            'name': _('Logs y Debug - Mesa de Ayuda'),
            'type': 'ir.actions.act_window',
            'res_model': 'mesa_ayuda.debug.log',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
    
    @api.model
    def action_open_debug_log(self):
        """Abrir ventana de debug logs."""
        record = self.create({})
        return record.action_show_logs()
