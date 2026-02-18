# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
import base64
from datetime import datetime, timedelta
from collections import defaultdict
from dateutil.relativedelta import relativedelta
from io import BytesIO

_logger = logging.getLogger(__name__)

try:
    import xlsxwriter
    XLSXWRITER_AVAILABLE = True
except ImportError:
    XLSXWRITER_AVAILABLE = False
    _logger.warning("xlsxwriter no está disponible. La exportación a Excel no funcionará.")


class MaintenanceDashboard(models.TransientModel):
    """Dashboard con métricas de mantenimientos."""
    _name = 'maintenance.dashboard'
    _description = 'Dashboard de Mantenimientos'
    
    name = fields.Char(
        string='Nombre',
        compute='_compute_name',
        store=False,
        readonly=True,
        default='Dashboard de Mantenimientos'
    )
    
    # Campo para almacenar el tipo de vista actual
    dashboard_type = fields.Selection([
        ('general', 'Dashboard General'),
        ('visits', 'Métricas de Visitas'),
        ('maintenance', 'Métricas de Mantenimientos'),
        ('technicians', 'Estadísticas de Técnicos'),
    ], string='Tipo de Dashboard', default='general', required=True)
    
    # Filtros de fecha
    date_from = fields.Date(
        string='Fecha Desde',
        default=lambda self: fields.Date.today().replace(day=1),
        help='Filtrar mantenimientos desde esta fecha'
    )
    date_to = fields.Date(
        string='Fecha Hasta',
        default=fields.Date.today,
        help='Filtrar mantenimientos hasta esta fecha'
    )
    
    # Filtro por técnico
    technician_id = fields.Many2one(
        'res.users',
        string='Técnico',
        help='Filtrar mantenimientos por técnico específico'
    )
    
    @api.depends('technician_id')
    def _compute_name(self):
        """Calcular el nombre del dashboard."""
        for record in self:
            if record.technician_id:
                record.name = f'Dashboard - {record.technician_id.name}'
            else:
                record.name = 'Dashboard de Mantenimientos'
    
    def name_get(self):
        """Personalizar el nombre mostrado del dashboard."""
        result = []
        for record in self:
            if record.technician_id:
                name = f'Dashboard - {record.technician_id.name}'
            else:
                name = 'Dashboard de Mantenimientos'
            result.append((record.id, name))
        return result
    
    # Métricas computadas
    total_maintenances = fields.Integer(string='Total Mantenimientos', compute='_compute_metrics')
    pending_maintenances = fields.Integer(string='Pendientes', compute='_compute_metrics')
    completed_maintenances = fields.Integer(string='Completados', compute='_compute_metrics')
    overdue_maintenances = fields.Integer(string='Vencidos', compute='_compute_metrics')
    total_repairs = fields.Integer(string='Total Reparaciones', compute='_compute_metrics')
    active_repairs = fields.Integer(string='Reparaciones Activas', compute='_compute_metrics')
    total_tickets = fields.Integer(string='Total Tickets', compute='_compute_metrics')
    open_tickets = fields.Integer(string='Tickets Abiertos', compute='_compute_metrics')
    
    # Métricas de órdenes (visitas programadas)
    total_orders = fields.Integer(string='Total Órdenes', compute='_compute_metrics')
    scheduled_orders = fields.Integer(string='Órdenes Programadas', compute='_compute_metrics')
    completed_orders = fields.Integer(string='Órdenes Completadas', compute='_compute_metrics')
    visit_orders = fields.Integer(string='Visitas Programadas', compute='_compute_metrics')
    
    # Métricas por técnico
    technician_performance_ids = fields.One2many(
        'maintenance.technician.performance',
        'dashboard_id',
        string='Rendimiento por Técnico',
        readonly=True,
    )
    
    # Métricas por cliente
    client_maintenance_ids = fields.One2many(
        'maintenance.client.summary',
        'dashboard_id',
        string='Mantenimientos por Cliente',
        readonly=True,
    )
    
    # ========== PUNTO 5.2: MÉTRICAS ADICIONALES ==========
    
    # Tiempo promedio de resolución por tipo
    avg_resolution_time_ids = fields.One2many(
        'maintenance.avg.resolution.time',
        'dashboard_id',
        string='Tiempo Promedio de Resolución',
        readonly=True,
    )
    
    # Equipos más problemáticos
    problematic_equipment_ids = fields.One2many(
        'maintenance.problematic.equipment',
        'dashboard_id',
        string='Equipos Más Problemáticos',
        readonly=True,
    )
    
    # ========== PUNTO 5.1: GRÁFICOS VISUALES ==========
    # Datos para gráficos (almacenados como JSON o One2many)
    
    # Gráfico de tendencia mensual
    monthly_trend_ids = fields.One2many(
        'maintenance.monthly.trend',
        'dashboard_id',
        string='Tendencia Mensual',
        readonly=True,
    )
    
    # Gráfico de distribución por tipo
    type_distribution_ids = fields.One2many(
        'maintenance.type.distribution',
        'dashboard_id',
        string='Distribución por Tipo',
        readonly=True,
    )
    
    # Gráfico de actividad por día de semana
    weekday_activity_ids = fields.One2many(
        'maintenance.weekday.activity',
        'dashboard_id',
        string='Actividad por Día',
        readonly=True,
    )
    
    # Campos computed para generar datos JSON para gráficos
    monthly_trend_json = fields.Text(
        string='Datos JSON Tendencia Mensual',
        compute='_compute_chart_data_json',
        store=False
    )
    
    type_distribution_json = fields.Text(
        string='Datos JSON Distribución por Tipo',
        compute='_compute_chart_data_json',
        store=False
    )
    
    weekday_activity_json = fields.Text(
        string='Datos JSON Actividad por Día',
        compute='_compute_chart_data_json',
        store=False
    )
    
    technician_performance_json = fields.Text(
        string='Datos JSON Rendimiento por Técnico',
        compute='_compute_chart_data_json',
        store=False
    )
    
    # ========== CAMPOS PARA GRÁFICAS DE VISITAS PROGRAMADAS ==========
    
    # Datos para gráficas de visitas
    visit_by_technician_ids = fields.One2many(
        'maintenance.visit.by.technician',
        'dashboard_id',
        string='Visitas por Técnico',
        readonly=True,
    )
    
    visit_by_type_ids = fields.One2many(
        'maintenance.visit.by.type',
        'dashboard_id',
        string='Visitas por Tipo',
        readonly=True,
    )
    
    visit_monthly_trend_ids = fields.One2many(
        'maintenance.visit.monthly.trend',
        'dashboard_id',
        string='Tendencia Mensual de Visitas',
        readonly=True,
    )
    
    # Campos JSON para gráficas de visitas
    visit_by_technician_json = fields.Text(
        string='Datos JSON Visitas por Técnico',
        compute='_compute_visit_chart_data_json',
        store=False
    )
    
    visit_by_type_json = fields.Text(
        string='Datos JSON Visitas por Tipo',
        compute='_compute_visit_chart_data_json',
        store=False
    )
    
    visit_monthly_trend_json = fields.Text(
        string='Datos JSON Tendencia Mensual de Visitas',
        compute='_compute_visit_chart_data_json',
        store=False
    )
    
    visit_compliance_json = fields.Text(
        string='Datos JSON Cumplimiento de Visitas',
        compute='_compute_visit_chart_data_json',
        store=False
    )
    
    @api.depends('monthly_trend_ids', 'type_distribution_ids', 'weekday_activity_ids', 'technician_performance_ids')
    def _compute_chart_data_json(self):
        """Calcular datos en formato JSON para los gráficos."""
        import json
        for record in self:
            # Gráfico de tendencia mensual (líneas)
            monthly_data = {
                'labels': [],
                'datasets': [
                    {'label': 'Total', 'data': [], 'borderColor': '#667eea', 'backgroundColor': 'rgba(102, 126, 234, 0.1)'},
                    {'label': 'Completados', 'data': [], 'borderColor': '#4facfe', 'backgroundColor': 'rgba(79, 172, 254, 0.1)'},
                    {'label': 'Pendientes', 'data': [], 'borderColor': '#f5576c', 'backgroundColor': 'rgba(245, 87, 108, 0.1)'}
                ]
            }
            for trend in record.monthly_trend_ids.sorted('month'):
                monthly_data['labels'].append(trend.month)
                monthly_data['datasets'][0]['data'].append(trend.total_maintenances)
                monthly_data['datasets'][1]['data'].append(trend.completed_maintenances)
                monthly_data['datasets'][2]['data'].append(trend.pending_maintenances)
            record.monthly_trend_json = json.dumps(monthly_data) if monthly_data['labels'] else '{}'
            
            # Gráfico de distribución por tipo (circular/pie)
            type_data = {
                'labels': [],
                'data': [],
                'backgroundColor': [
                    '#667eea', '#764ba2', '#f093fb', '#f5576c',
                    '#4facfe', '#00f2fe', '#43e97b', '#38f9d7',
                    '#ff9a9e', '#fecfef', '#ffecd2', '#fcb69f',
                    '#a8edea', '#fed6e3', '#ffeaa7'
                ]
            }
            for dist in record.type_distribution_ids.sorted('count', reverse=True):
                type_data['labels'].append(dist.type_label)
                type_data['data'].append(dist.count)
            record.type_distribution_json = json.dumps(type_data) if type_data['labels'] else '{}'
            
            # Gráfico de actividad por día (barras)
            weekday_data = {
                'labels': [],
                'data': [],
                'backgroundColor': '#667eea'
            }
            for activity in record.weekday_activity_ids.sorted('weekday'):
                weekday_data['labels'].append(activity.weekday_label)
                weekday_data['data'].append(activity.count)
            record.weekday_activity_json = json.dumps(weekday_data) if weekday_data['labels'] else '{}'
            
            # Gráfico de rendimiento por técnico (barras)
            tech_data = {
                'labels': [],
                'datasets': [
                    {'label': 'Completados', 'data': [], 'backgroundColor': '#4facfe'},
                    {'label': 'Pendientes', 'data': [], 'backgroundColor': '#f5576c'}
                ]
            }
            for perf in record.technician_performance_ids.sorted('completion_rate', reverse=True):
                tech_data['labels'].append(perf.technician_id.name or 'Sin nombre')
                tech_data['datasets'][0]['data'].append(perf.completed_maintenances)
                tech_data['datasets'][1]['data'].append(perf.total_maintenances - perf.completed_maintenances)
            record.technician_performance_json = json.dumps(tech_data) if tech_data['labels'] else '{}'
    
    @api.model_create_multi
    def create(self, vals_list):
        """Crear dashboard y calcular métricas."""
        # Normalizar entrada: convertir dict a lista si es necesario
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        elif not vals_list:
            vals_list = [{}]
        
        # Preparar valores por defecto para cada registro
        for vals in vals_list:
            # Inicializar fechas si no están en vals
            if 'date_from' not in vals:
                vals['date_from'] = fields.Date.today().replace(day=1)
            if 'date_to' not in vals:
                vals['date_to'] = fields.Date.today()
            # Asegurar que dashboard_type esté definido
            if 'dashboard_type' not in vals:
                vals['dashboard_type'] = 'general'
        
        dashboards = super().create(vals_list)
        
        # Para cada dashboard, calcular todas las métricas
        for dashboard in dashboards:
            # Calcular todas las métricas después de crear
            dashboard._compute_metrics()
            # Crear registros de rendimiento por técnico
            dashboard._load_technician_performance()
            # Crear registros de resumen por cliente
            dashboard._load_client_summary()
            # PUNTO 5.1: Cargar datos para gráficos
            dashboard._load_monthly_trend()
            dashboard._load_type_distribution()
            dashboard._load_weekday_activity()
            # PUNTO 5.2: Cargar métricas adicionales
            dashboard._load_avg_resolution_time()
            dashboard._load_problematic_equipment()
            # Calcular datos JSON para gráficos
            dashboard._compute_chart_data_json()
            # ✅ Cargar datos para gráficas de visitas programadas
            dashboard._load_visit_data()
            # Calcular datos JSON para gráficas de visitas
            dashboard._compute_visit_chart_data_json()
        
        # Retornar el resultado correcto según la entrada
        if isinstance(vals_list, dict) or len(vals_list) == 1:
            return dashboards[0] if dashboards else dashboards
        return dashboards
    
    
    @api.onchange('date_from', 'date_to', 'technician_id')
    def _onchange_filters(self):
        """Actualizar automáticamente cuando cambian los filtros.
        
        Nota: Este método solo se ejecuta en modo edición, no cuando se aplican filtros desde el botón.
        Para actualización completa, usar action_refresh_dashboard.
        """
        # No hacer nada aquí para evitar problemas de rendimiento
        # El botón "Aplicar Filtros" llamará a action_refresh_dashboard que recargará todo
        pass
    
    @api.depends('date_from', 'date_to', 'technician_id')
    def _compute_metrics(self):
        """Calcular métricas principales. Se ejecuta automáticamente cuando cambian las fechas."""
        for record in self:
            # Construir dominio de fecha
            date_domain = []
            if record.date_from:
                # Convertir Date a inicio del día en formato Datetime
                date_from_str = record.date_from.strftime('%Y-%m-%d 00:00:00')
                date_domain.append(('maintenance_date', '>=', date_from_str))
            if record.date_to:
                # Convertir Date a final del día en formato Datetime
                date_to_str = record.date_to.strftime('%Y-%m-%d 23:59:59')
                date_domain.append(('maintenance_date', '<=', date_to_str))
            
            # Agregar filtro por técnico si está seleccionado
            if record.technician_id:
                date_domain.append('|')
                date_domain.append(('technician_id', '=', record.technician_id.id))
                date_domain.append(('technician_ids', 'in', [record.technician_id.id]))
            
            # Mantenimientos con filtro de fecha y técnico
            all_maintenances = self.env['stock.lot.maintenance'].search(date_domain)
            record.total_maintenances = len(all_maintenances)
            record.pending_maintenances = len(all_maintenances.filtered(lambda m: m.status in ('draft', 'pending', 'scheduled', 'in_progress')))
            record.completed_maintenances = len(all_maintenances.filtered(lambda m: m.status == 'completed'))
            
            # Mantenimientos vencidos
            today = fields.Datetime.now()
            overdue = all_maintenances.filtered(
                lambda m: m.next_maintenance_date and 
                (fields.Datetime.from_string(m.next_maintenance_date) if isinstance(m.next_maintenance_date, str) else m.next_maintenance_date) < today and
                m.status != 'completed'
            )
            record.overdue_maintenances = len(overdue)
            
            # Reparaciones (solo si el modelo existe)
            try:
                all_repairs = self.env['repair.order'].search([])
                record.total_repairs = len(all_repairs)
                record.active_repairs = len(all_repairs.filtered(lambda r: r.state in ('draft', 'in_progress', 'waiting_parts')))
            except Exception:
                record.total_repairs = 0
                record.active_repairs = 0
            
            # Tickets (solo si el modelo existe)
            try:
                all_tickets = self.env['helpdesk.ticket'].search([])
                record.total_tickets = len(all_tickets)
                # Intentar filtrar tickets abiertos
                try:
                    record.open_tickets = len(all_tickets.filtered(lambda t: t.stage_id and not t.stage_id.closed))
                except Exception:
                    # Si no hay stage_id o closed, contar todos como abiertos
                    record.open_tickets = len(all_tickets)
            except Exception:
                record.total_tickets = 0
                record.open_tickets = 0
            
            # ✅ Órdenes de Mantenimiento (Visitas Programadas)
            try:
                order_domain = []
                if record.date_from:
                    order_domain.append(('scheduled_date', '>=', record.date_from.strftime('%Y-%m-%d 00:00:00')))
                if record.date_to:
                    order_domain.append(('scheduled_date', '<=', record.date_to.strftime('%Y-%m-%d 23:59:59')))
                
                if record.technician_id:
                    order_domain.append(('technician_ids', 'in', [record.technician_id.id]))
                
                all_orders = self.env['maintenance.order'].search(order_domain)
                record.total_orders = len(all_orders)
                record.scheduled_orders = len(all_orders.filtered(lambda o: o.state == 'scheduled'))
                record.completed_orders = len(all_orders.filtered(lambda o: o.state == 'completed'))
                record.visit_orders = len(all_orders.filtered(lambda o: o.activity_type == 'visit'))
            except Exception:
                record.total_orders = 0
                record.scheduled_orders = 0
                record.completed_orders = 0
                record.visit_orders = 0
    
    def _load_technician_performance(self):
        """Cargar rendimiento por técnico creando registros hijos."""
        self.ensure_one()
        # Primero eliminar registros existentes si los hay
        if self.technician_performance_ids:
            self.technician_performance_ids.unlink()
        
        # Construir dominio de fecha
        date_domain = []
        if self.date_from:
            date_from_str = self.date_from.strftime('%Y-%m-%d 00:00:00')
            date_domain.append(('maintenance_date', '>=', date_from_str))
        if self.date_to:
            date_to_str = self.date_to.strftime('%Y-%m-%d 23:59:59')
            date_domain.append(('maintenance_date', '<=', date_to_str))
        
        # Agregar filtro por técnico si está seleccionado
        if self.technician_id:
            date_domain.append('|')
            date_domain.append(('technician_id', '=', self.technician_id.id))
            date_domain.append(('technician_ids', 'in', [self.technician_id.id]))
        
        # Obtener todos los técnicos que tienen mantenimientos asignados (con filtro de fecha y técnico)
        all_maintenances = self.env['stock.lot.maintenance'].search(date_domain)
        
        # Si hay filtro por técnico, solo mostrar ese técnico en la tabla
        if self.technician_id:
            technician_ids = self.technician_id
        else:
            # Si no hay filtro, mostrar todos los técnicos que tienen mantenimientos
            technician_ids = all_maintenances.mapped('technician_id').filtered(lambda t: t)
            
            # Si no hay técnicos asignados directamente, buscar en technician_ids (Many2many)
            if not technician_ids:
                technician_ids = all_maintenances.mapped('technician_ids').filtered(lambda t: t)
            
            # Si aún no hay técnicos, buscar todos los usuarios con mantenimientos
            if not technician_ids:
                for maintenance in all_maintenances:
                    if maintenance.technician_ids:
                        technician_ids |= maintenance.technician_ids
                    elif maintenance.technician_id:
                        technician_ids |= maintenance.technician_id
        
        # Asegurarse de que technician_ids sea un recordset iterable
        if not technician_ids:
            return
        
        for tech in technician_ids:
            # Buscar mantenimientos por technician_id
            maintenances = all_maintenances.filtered(lambda m: m.technician_id.id == tech.id)
            # También incluir si está en technician_ids
            maintenances |= all_maintenances.filtered(lambda m: tech.id in m.technician_ids.ids)
            
            if not maintenances:
                continue
            
            completed = len(maintenances.filtered(lambda m: m.status == 'completed'))
            total = len(maintenances)
            # El widget percentage espera un valor entre 0 y 1 (0.8491 = 84.91%)
            completion_rate = (completed / total) if total > 0 else 0.0
            
            self.env['maintenance.technician.performance'].create({
                'dashboard_id': self.id,
                'technician_id': tech.id,
                'total_maintenances': total,
                'completed_maintenances': completed,
                'completion_rate': completion_rate,
            })
    
    def _load_client_summary(self):
        """Cargar resumen por cliente creando registros hijos."""
        self.ensure_one()
        # Primero eliminar registros existentes si los hay
        if self.client_maintenance_ids:
            self.client_maintenance_ids.unlink()
        
        # Construir dominio de fecha
        date_domain = []
        if self.date_from:
            date_from_str = self.date_from.strftime('%Y-%m-%d 00:00:00')
            date_domain.append(('maintenance_date', '>=', date_from_str))
        if self.date_to:
            date_to_str = self.date_to.strftime('%Y-%m-%d 23:59:59')
            date_domain.append(('maintenance_date', '<=', date_to_str))
        
        # Agregar filtro por técnico si está seleccionado
        if self.technician_id:
            date_domain.append('|')
            date_domain.append(('technician_id', '=', self.technician_id.id))
            date_domain.append(('technician_ids', 'in', [self.technician_id.id]))
        
        # Obtener todos los mantenimientos y extraer los clientes únicos (con filtro de fecha y técnico)
        all_maintenances = self.env['stock.lot.maintenance'].search(date_domain)
        client_ids = all_maintenances.mapped('customer_id').filtered(lambda c: c)
        
        # Si no hay clientes, buscar en los lotes asociados
        if not client_ids:
            lot_ids = all_maintenances.mapped('lot_id').filtered(lambda l: l)
            for lot in lot_ids:
                if hasattr(lot, 'customer_id') and lot.customer_id:
                    client_ids |= lot.customer_id
        
        for client in client_ids:
            # Buscar mantenimientos por customer_id
            maintenances = all_maintenances.filtered(lambda m: m.customer_id and m.customer_id.id == client.id)
            
            # También buscar por lot_id.customer_id
            maintenances |= all_maintenances.filtered(
                lambda m: m.lot_id and hasattr(m.lot_id, 'customer_id') and 
                m.lot_id.customer_id and m.lot_id.customer_id.id == client.id
            )
            
            if not maintenances:
                continue
            
            pending = len(maintenances.filtered(lambda m: m.status in ('draft', 'pending', 'scheduled', 'in_progress')))
            completed = len(maintenances.filtered(lambda m: m.status == 'completed'))
            
            self.env['maintenance.client.summary'].create({
                'dashboard_id': self.id,
                'partner_id': client.id,
                'total_maintenances': len(maintenances),
                'pending_maintenances': pending,
                'completed_maintenances': completed,
            })
    
    @api.model
    def _clean_old_dashboards(self):
        """Limpiar dashboards antiguos para evitar acumulación de registros."""
        try:
            # Eliminar TODOS los dashboards antiguos excepto los más recientes (últimos 5)
            # Esto mantiene solo los dashboards activos y elimina el resto
            all_dashboards = self.search([], order='create_date desc')
            
            # Mantener solo los 5 más recientes y eliminar el resto
            if len(all_dashboards) > 5:
                old_dashboards = all_dashboards[5:]
                old_dashboards.unlink()
                _logger.info(f"Eliminados {len(old_dashboards)} dashboards antiguos (manteniendo los 5 más recientes)")
        except Exception as e:
            _logger.warning(f"Error al limpiar dashboards antiguos: {str(e)}")
    
    @api.model
    def open_dashboard(self, dashboard_type='general'):
        """Crear y abrir el dashboard.
        
        Args:
            dashboard_type: 'general', 'visits', 'maintenance', o 'technicians'
        """
        # Limpiar dashboards antiguos antes de crear uno nuevo
        self._clean_old_dashboards()
        
        dashboard = self.create({'dashboard_type': dashboard_type})
        # Calcular el nombre para mostrarlo correctamente
        dashboard._compute_name()
        
        # Determinar qué vista usar según el tipo
        view_mode_map = {
            'general': 'view_maintenance_dashboard_general',
            'visits': 'view_maintenance_dashboard_visits',
            'maintenance': 'view_maintenance_dashboard_maintenance',
            'technicians': 'view_maintenance_dashboard_technicians',
        }
        
        view_id = self.env.ref(f'mesa_ayuda_inventario.{view_mode_map.get(dashboard_type, "view_maintenance_dashboard_general")}', raise_if_not_found=False)
        
        action = {
            'name': dashboard.name or _('Dashboard de Mantenimientos'),
            'type': 'ir.actions.act_window',
            'res_model': 'maintenance.dashboard',
            'view_mode': 'form',
            'target': 'current',
            'res_id': dashboard.id,
        }
        
        if view_id:
            action['view_id'] = view_id.id
        
        return action
    
    @api.model
    def open_general_dashboard(self):
        """Abrir dashboard general (overview)."""
        return self.open_dashboard(dashboard_type='general')
    
    @api.model
    def open_visits_dashboard(self):
        """Abrir dashboard de métricas de visitas."""
        return self.open_dashboard(dashboard_type='visits')
    
    @api.model
    def open_maintenance_dashboard(self):
        """Abrir dashboard de métricas de mantenimientos."""
        return self.open_dashboard(dashboard_type='maintenance')
    
    @api.model
    def open_technicians_dashboard(self):
        """Abrir dashboard de estadísticas de técnicos."""
        return self.open_dashboard(dashboard_type='technicians')
    
    def _load_monthly_trend(self):
        """Cargar datos de tendencia mensual para gráfico de líneas."""
        self.ensure_one()
        # Eliminar datos existentes
        if self.monthly_trend_ids:
            self.monthly_trend_ids.unlink()
        
        # Construir dominio
        date_domain = []
        if self.date_from:
            date_from_str = self.date_from.strftime('%Y-%m-%d 00:00:00')
            date_domain.append(('maintenance_date', '>=', date_from_str))
        if self.date_to:
            date_to_str = self.date_to.strftime('%Y-%m-%d 23:59:59')
            date_domain.append(('maintenance_date', '<=', date_to_str))
        if self.technician_id:
            date_domain.append('|')
            date_domain.append(('technician_id', '=', self.technician_id.id))
            date_domain.append(('technician_ids', 'in', [self.technician_id.id]))
        
        all_maintenances = self.env['stock.lot.maintenance'].search(date_domain)
        
        # Agrupar por mes
        monthly_data = defaultdict(lambda: {'total': 0, 'completed': 0, 'pending': 0})
        for maint in all_maintenances:
            if maint.maintenance_date:
                # Convertir a datetime si es string
                if isinstance(maint.maintenance_date, str):
                    maint_date = fields.Datetime.from_string(maint.maintenance_date)
                else:
                    maint_date = maint.maintenance_date
                month_key = maint_date.strftime('%Y-%m')
                monthly_data[month_key]['total'] += 1
                if maint.status == 'completed':
                    monthly_data[month_key]['completed'] += 1
                elif maint.status in ('draft', 'pending', 'scheduled', 'in_progress'):
                    monthly_data[month_key]['pending'] += 1
        
        # Crear registros ordenados por mes
        for month_key in sorted(monthly_data.keys()):
            data = monthly_data[month_key]
            self.env['maintenance.monthly.trend'].create({
                'dashboard_id': self.id,
                'month': month_key,
                'total_maintenances': data['total'],
                'completed_maintenances': data['completed'],
                'pending_maintenances': data['pending'],
            })
    
    def _load_type_distribution(self):
        """Cargar distribución por tipo de mantenimiento para gráfico circular."""
        self.ensure_one()
        # Eliminar datos existentes
        if self.type_distribution_ids:
            self.type_distribution_ids.unlink()
        
        # Construir dominio
        date_domain = []
        if self.date_from:
            date_from_str = self.date_from.strftime('%Y-%m-%d 00:00:00')
            date_domain.append(('maintenance_date', '>=', date_from_str))
        if self.date_to:
            date_to_str = self.date_to.strftime('%Y-%m-%d 23:59:59')
            date_domain.append(('maintenance_date', '<=', date_to_str))
        if self.technician_id:
            date_domain.append('|')
            date_domain.append(('technician_id', '=', self.technician_id.id))
            date_domain.append(('technician_ids', 'in', [self.technician_id.id]))
        
        all_maintenances = self.env['stock.lot.maintenance'].search(date_domain)
        
        # Agrupar por tipo
        type_data = defaultdict(int)
        type_labels = {
            'preventive': 'Preventivo',
            'corrective': 'Correctivo',
            'remote_support': 'Soporte Remoto',
            'onsite_support': 'Soporte en Sitio',
            'diagnosis': 'Diagnóstico',
            'installation': 'Instalación',
            'server_implementation': 'Implementación Servidores',
            'server_migration': 'Migración Servidores',
            'backup_recovery': 'Backup y Recuperación',
            'firewall_vpn': 'Firewall/VPN',
            'licensing_m365': 'Licenciamiento M365',
            'admin_m365': 'Admin M365',
            'upgrade': 'Actualización',
            'other': 'Otro',
        }
        
        for maint in all_maintenances:
            maint_type = maint.maintenance_type or 'other'
            type_data[maint_type] += 1
        
        # Crear registros
        for maint_type, count in type_data.items():
            self.env['maintenance.type.distribution'].create({
                'dashboard_id': self.id,
                'maintenance_type': maint_type,
                'type_label': type_labels.get(maint_type, maint_type),
                'count': count,
            })
    
    def _load_weekday_activity(self):
        """Cargar actividad por día de semana para gráfico de calor."""
        self.ensure_one()
        # Eliminar datos existentes
        if self.weekday_activity_ids:
            self.weekday_activity_ids.unlink()
        
        # Construir dominio
        date_domain = []
        if self.date_from:
            date_from_str = self.date_from.strftime('%Y-%m-%d 00:00:00')
            date_domain.append(('maintenance_date', '>=', date_from_str))
        if self.date_to:
            date_to_str = self.date_to.strftime('%Y-%m-%d 23:59:59')
            date_domain.append(('maintenance_date', '<=', date_to_str))
        if self.technician_id:
            date_domain.append('|')
            date_domain.append(('technician_id', '=', self.technician_id.id))
            date_domain.append(('technician_ids', 'in', [self.technician_id.id]))
        
        all_maintenances = self.env['stock.lot.maintenance'].search(date_domain)
        
        # Agrupar por día de semana
        weekday_data = defaultdict(int)
        weekday_labels = {
            0: 'Lunes',
            1: 'Martes',
            2: 'Miércoles',
            3: 'Jueves',
            4: 'Viernes',
            5: 'Sábado',
            6: 'Domingo',
        }
        
        for maint in all_maintenances:
            if maint.maintenance_date:
                # Convertir a datetime si es string
                if isinstance(maint.maintenance_date, str):
                    maint_date = fields.Datetime.from_string(maint.maintenance_date)
                else:
                    maint_date = maint.maintenance_date
                weekday = maint_date.weekday()
                weekday_data[weekday] += 1
        
        # Crear registros ordenados por día
        for weekday in sorted(weekday_data.keys()):
            self.env['maintenance.weekday.activity'].create({
                'dashboard_id': self.id,
                'weekday': weekday,
                'weekday_label': weekday_labels[weekday],
                'count': weekday_data[weekday],
            })
    
    # ========== PUNTO 5.2: MÉTODOS PARA MÉTRICAS ADICIONALES ==========
    
    def _load_avg_resolution_time(self):
        """Cargar tiempo promedio de resolución por tipo de mantenimiento."""
        self.ensure_one()
        # Eliminar datos existentes
        if self.avg_resolution_time_ids:
            self.avg_resolution_time_ids.unlink()
        
        # Construir dominio
        date_domain = []
        if self.date_from:
            date_from_str = self.date_from.strftime('%Y-%m-%d 00:00:00')
            date_domain.append(('maintenance_date', '>=', date_from_str))
        if self.date_to:
            date_to_str = self.date_to.strftime('%Y-%m-%d 23:59:59')
            date_domain.append(('maintenance_date', '<=', date_to_str))
        if self.technician_id:
            date_domain.append('|')
            date_domain.append(('technician_id', '=', self.technician_id.id))
            date_domain.append(('technician_ids', 'in', [self.technician_id.id]))
        
        # Solo mantenimientos completados tienen tiempo de resolución
        date_domain.append(('status', '=', 'completed'))
        
        completed_maintenances = self.env['stock.lot.maintenance'].search(date_domain)
        
        # Agrupar por tipo y calcular tiempo promedio
        type_resolution_times = defaultdict(lambda: {'total_time': 0, 'count': 0})
        type_labels = {
            'preventive': 'Preventivo',
            'corrective': 'Correctivo',
            'remote_support': 'Soporte Remoto',
            'onsite_support': 'Soporte en Sitio',
            'diagnosis': 'Diagnóstico',
            'installation': 'Instalación',
            'server_implementation': 'Implementación Servidores',
            'server_migration': 'Migración Servidores',
            'backup_recovery': 'Backup y Recuperación',
            'firewall_vpn': 'Firewall/VPN',
            'licensing_m365': 'Licenciamiento M365',
            'admin_m365': 'Admin M365',
            'upgrade': 'Actualización',
            'other': 'Otro',
        }
        
        for maint in completed_maintenances:
            # Calcular tiempo entre fecha de creación y fecha de completado
            if maint.create_date and maint.customer_signed_date:
                start_date = maint.create_date if isinstance(maint.create_date, datetime) else fields.Datetime.from_string(maint.create_date)
                end_date = maint.customer_signed_date if isinstance(maint.customer_signed_date, datetime) else fields.Datetime.from_string(maint.customer_signed_date)
                
                if end_date > start_date:
                    resolution_time = (end_date - start_date).total_seconds() / 3600  # En horas
                    maint_type = maint.maintenance_type or 'other'
                    type_resolution_times[maint_type]['total_time'] += resolution_time
                    type_resolution_times[maint_type]['count'] += 1
        
        # Crear registros
        for maint_type, data in type_resolution_times.items():
            avg_hours = data['total_time'] / data['count'] if data['count'] > 0 else 0
            self.env['maintenance.avg.resolution.time'].create({
                'dashboard_id': self.id,
                'maintenance_type': maint_type,
                'type_label': type_labels.get(maint_type, maint_type),
                'avg_hours': avg_hours,
                'count': data['count'],
            })
    
    def _load_problematic_equipment(self):
        """Cargar equipos más problemáticos (con más mantenimientos)."""
        self.ensure_one()
        # Eliminar datos existentes
        if self.problematic_equipment_ids:
            self.problematic_equipment_ids.unlink()
        
        # Construir dominio
        date_domain = []
        if self.date_from:
            date_from_str = self.date_from.strftime('%Y-%m-%d 00:00:00')
            date_domain.append(('maintenance_date', '>=', date_from_str))
        if self.date_to:
            date_to_str = self.date_to.strftime('%Y-%m-%d 23:59:59')
            date_domain.append(('maintenance_date', '<=', date_to_str))
        if self.technician_id:
            date_domain.append('|')
            date_domain.append(('technician_id', '=', self.technician_id.id))
            date_domain.append(('technician_ids', 'in', [self.technician_id.id]))
        
        all_maintenances = self.env['stock.lot.maintenance'].search(date_domain)
        
        # Agrupar por equipo
        equipment_counts = defaultdict(lambda: {
            'total': 0,
            'completed': 0,
            'pending': 0,
            'lot_id': None,
            'lot_name': '',
            'inventory_plate': ''
        })
        
        for maint in all_maintenances:
            if maint.lot_id:
                lot = maint.lot_id
                equipment_counts[lot.id]['lot_id'] = lot.id
                equipment_counts[lot.id]['lot_name'] = lot.name or ''
                equipment_counts[lot.id]['inventory_plate'] = getattr(lot, 'inventory_plate', '') or ''
                equipment_counts[lot.id]['total'] += 1
                
                if maint.status == 'completed':
                    equipment_counts[lot.id]['completed'] += 1
                elif maint.status in ('draft', 'pending', 'scheduled', 'in_progress'):
                    equipment_counts[lot.id]['pending'] += 1
        
        # Ordenar por cantidad de mantenimientos (más problemáticos primero)
        sorted_equipment = sorted(
            equipment_counts.items(),
            key=lambda x: x[1]['total'],
            reverse=True
        )[:10]  # Solo los 10 más problemáticos
        
        # Crear registros
        for lot_id, data in sorted_equipment:
            if data['total'] > 0:  # Solo equipos con al menos un mantenimiento
                self.env['maintenance.problematic.equipment'].create({
                    'dashboard_id': self.id,
                    'lot_id': data['lot_id'],
                    'equipment_name': data['lot_name'],
                    'inventory_plate': data['inventory_plate'],
                    'total_maintenances': data['total'],
                    'completed_maintenances': data['completed'],
                    'pending_maintenances': data['pending'],
                })
    
    # ========== MÉTODOS PARA GRÁFICAS DE VISITAS PROGRAMADAS ==========
    
    def _load_visit_data(self):
        """Cargar datos para gráficas de visitas programadas."""
        self.ensure_one()
        
        # Eliminar datos existentes
        if self.visit_by_technician_ids:
            self.visit_by_technician_ids.unlink()
        if self.visit_by_type_ids:
            self.visit_by_type_ids.unlink()
        if self.visit_monthly_trend_ids:
            self.visit_monthly_trend_ids.unlink()
        
        # Construir dominio de fecha
        order_domain = []
        if self.date_from:
            order_domain.append(('scheduled_date', '>=', self.date_from.strftime('%Y-%m-%d 00:00:00')))
        if self.date_to:
            order_domain.append(('scheduled_date', '<=', self.date_to.strftime('%Y-%m-%d 23:59:59')))
        
        if self.technician_id:
            order_domain.append(('technician_ids', 'in', [self.technician_id.id]))
        
        # Obtener todas las órdenes
        all_orders = self.env['maintenance.order'].search(order_domain)
        
        # 1. Visitas por Técnico
        tech_orders = defaultdict(lambda: {'total': 0, 'completed': 0, 'scheduled': 0})
        for order in all_orders:
            for tech in order.technician_ids:
                tech_orders[tech.id]['total'] += 1
                if order.state == 'completed':
                    tech_orders[tech.id]['completed'] += 1
                elif order.state == 'scheduled':
                    tech_orders[tech.id]['scheduled'] += 1
        
        for tech_id, data in tech_orders.items():
            tech = self.env['res.users'].browse(tech_id)
            if tech.exists():
                self.env['maintenance.visit.by.technician'].create({
                    'dashboard_id': self.id,
                    'technician_id': tech_id,
                    'total_orders': data['total'],
                    'completed_orders': data['completed'],
                    'scheduled_orders': data['scheduled'],
                })
        
        # 2. Visitas por Tipo de Actividad
        type_orders = defaultdict(lambda: {'total': 0, 'completed': 0})
        for order in all_orders:
            activity_type = order.activity_type or 'maintenance'
            type_orders[activity_type]['total'] += 1
            if order.state == 'completed':
                type_orders[activity_type]['completed'] += 1
        
        activity_labels = {
            'maintenance': 'Mantenimiento',
            'visit': 'Visita Programada',
            'inspection': 'Inspección',
            'repair': 'Reparación',
            'installation': 'Instalación',
        }
        
        for activity_type, data in type_orders.items():
            label = activity_labels.get(activity_type, activity_type.title())
            self.env['maintenance.visit.by.type'].create({
                'dashboard_id': self.id,
                'activity_type': activity_type,
                'type_label': label,
                'total_orders': data['total'],
                'completed_orders': data['completed'],
            })
        
        # 3. Tendencia Mensual de Visitas
        monthly_orders = defaultdict(lambda: {'total': 0, 'completed': 0, 'scheduled': 0})
        for order in all_orders:
            if order.scheduled_date:
                try:
                    if isinstance(order.scheduled_date, str):
                        order_date = fields.Datetime.from_string(order.scheduled_date)
                    else:
                        order_date = order.scheduled_date
                    
                    month_key = order_date.strftime('%Y-%m')
                    month_label = order_date.strftime('%B %Y').capitalize()
                    
                    monthly_orders[month_key]['month_label'] = month_label
                    monthly_orders[month_key]['total'] += 1
                    if order.state == 'completed':
                        monthly_orders[month_key]['completed'] += 1
                    elif order.state == 'scheduled':
                        monthly_orders[month_key]['scheduled'] += 1
                except Exception:
                    continue
        
        for month_key in sorted(monthly_orders.keys()):
            data = monthly_orders[month_key]
            self.env['maintenance.visit.monthly.trend'].create({
                'dashboard_id': self.id,
                'month': data['month_label'],
                'total_orders': data['total'],
                'completed_orders': data['completed'],
                'scheduled_orders': data['scheduled'],
            })
    
    @api.depends('visit_by_technician_ids', 'visit_by_type_ids', 'visit_monthly_trend_ids', 'completed_orders', 'total_orders')
    def _compute_visit_chart_data_json(self):
        """Calcular datos en formato JSON para las gráficas de visitas."""
        import json
        for record in self:
            # 1. Visitas por Técnico (Barras apiladas)
            tech_visit_data = {
                'labels': [],
                'datasets': [
                    {'label': 'Completadas', 'data': [], 'backgroundColor': '#4facfe'},
                    {'label': 'Programadas', 'data': [], 'backgroundColor': '#f5576c'},
                ]
            }
            for visit_tech in record.visit_by_technician_ids.sorted('total_orders', reverse=True):
                tech_visit_data['labels'].append(visit_tech.technician_id.name or 'Sin nombre')
                tech_visit_data['datasets'][0]['data'].append(visit_tech.completed_orders)
                tech_visit_data['datasets'][1]['data'].append(visit_tech.scheduled_orders)
            record.visit_by_technician_json = json.dumps(tech_visit_data) if tech_visit_data['labels'] else '{}'
            
            # 2. Visitas por Tipo (Circular/Pie)
            type_visit_data = {
                'labels': [],
                'data': [],
                'backgroundColor': ['#667eea', '#764ba2', '#f093fb', '#f5576c', '#4facfe']
            }
            for visit_type in record.visit_by_type_ids.sorted('total_orders', reverse=True):
                type_visit_data['labels'].append(visit_type.type_label)
                type_visit_data['data'].append(visit_type.total_orders)
            record.visit_by_type_json = json.dumps(type_visit_data) if type_visit_data['labels'] else '{}'
            
            # 3. Tendencia Mensual de Visitas (Líneas)
            monthly_visit_data = {
                'labels': [],
                'datasets': [
                    {'label': 'Total', 'data': [], 'borderColor': '#667eea', 'backgroundColor': 'rgba(102, 126, 234, 0.1)'},
                    {'label': 'Completadas', 'data': [], 'borderColor': '#4facfe', 'backgroundColor': 'rgba(79, 172, 254, 0.1)'},
                    {'label': 'Programadas', 'data': [], 'borderColor': '#f5576c', 'backgroundColor': 'rgba(245, 87, 108, 0.1)'}
                ]
            }
            for trend in record.visit_monthly_trend_ids.sorted('month'):
                monthly_visit_data['labels'].append(trend.month)
                monthly_visit_data['datasets'][0]['data'].append(trend.total_orders)
                monthly_visit_data['datasets'][1]['data'].append(trend.completed_orders)
                monthly_visit_data['datasets'][2]['data'].append(trend.scheduled_orders)
            record.visit_monthly_trend_json = json.dumps(monthly_visit_data) if monthly_visit_data['labels'] else '{}'
            
            # 4. Cumplimiento de Visitas (Gauge/Medidor)
            total_orders = record.total_orders or 1
            completed = record.completed_orders or 0
            compliance_percentage = (completed / total_orders * 100) if total_orders > 0 else 0
            
            compliance_data = {
                'value': round(compliance_percentage, 2),
                'max': 100,
                'total': total_orders,
                'completed': completed
            }
            record.visit_compliance_json = json.dumps(compliance_data)
    
    def action_refresh_dashboard(self):
        """Refrescar el dashboard actualizando las métricas."""
        self.ensure_one()
        # Forzar recálculo de todas las métricas
        self._compute_metrics()
        self._load_technician_performance()
        self._load_client_summary()
        # PUNTO 5.1: Refrescar gráficos
        self._load_monthly_trend()
        self._load_type_distribution()
        self._load_weekday_activity()
        # PUNTO 5.2: Refrescar métricas adicionales
        self._load_avg_resolution_time()
        self._load_problematic_equipment()
        # Calcular datos JSON para gráficos
        self._compute_chart_data_json()
        # ✅ Refrescar datos de visitas programadas
        self._load_visit_data()
        # Calcular datos JSON para gráficas de visitas
        self._compute_visit_chart_data_json()
        
        # Usar el tipo de dashboard almacenado para determinar qué vista usar
        view_mode_map = {
            'general': 'view_maintenance_dashboard_general',
            'visits': 'view_maintenance_dashboard_visits',
            'maintenance': 'view_maintenance_dashboard_maintenance',
            'technicians': 'view_maintenance_dashboard_technicians',
        }
        
        dashboard_type = self.dashboard_type or 'general'
        view_external_id = view_mode_map.get(dashboard_type, 'view_maintenance_dashboard_general')
        view_id = self.env.ref(f'mesa_ayuda_inventario.{view_external_id}', raise_if_not_found=False)
        
        # Retornar acción que recarga la vista preservando el tipo de vista actual
        action = {
            'type': 'ir.actions.act_window',
            'res_model': 'maintenance.dashboard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
        }
        
        if view_id:
            action['views'] = [(view_id.id, 'form')]
        else:
            action['views'] = [(False, 'form')]
        
        return action
    
    def action_view_metrics(self):
        """Abrir vista de métricas."""
        return {
            'name': _('Dashboard de Mantenimientos'),
            'type': 'ir.actions.act_window',
            'res_model': 'maintenance.dashboard',
            'view_mode': 'form',
            'target': 'new',
            'res_id': self.id,
        }
    
    def action_open_visits_dashboard(self):
        """Abrir dashboard de visitas desde el dashboard general."""
        self.ensure_one()
        return self.open_visits_dashboard()
    
    def action_open_maintenance_dashboard(self):
        """Abrir dashboard de mantenimientos desde el dashboard general."""
        self.ensure_one()
        return self.open_maintenance_dashboard()
    
    # ========== PUNTO 5.3: EXPORTACIÓN DE DATOS ==========
    
    def action_export_excel(self):
        """Exportar dashboard a Excel."""
        self.ensure_one()
        
        if not XLSXWRITER_AVAILABLE:
            raise UserError(_('El módulo xlsxwriter no está instalado. Por favor, instálelo para usar la exportación a Excel.'))
        
        # Crear archivo Excel en memoria
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        
        # Formato para encabezados
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#667eea',
            'font_color': 'white',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })
        
        # Formato para datos
        data_format = workbook.add_format({
            'border': 1,
            'align': 'left',
            'valign': 'vcenter'
        })
        
        # Formato para números
        number_format = workbook.add_format({
            'border': 1,
            'align': 'right',
            'valign': 'vcenter'
        })
        
        # Hoja 1: Resumen General
        worksheet = workbook.add_worksheet('Resumen General')
        row = 0
        col = 0
        
        worksheet.write(row, col, 'DASHBOARD DE MANTENIMIENTOS', workbook.add_format({'bold': True, 'font_size': 16}))
        row += 2
        
        worksheet.write(row, col, 'Fecha Desde:', header_format)
        worksheet.write(row, col + 1, self.date_from or '', data_format)
        row += 1
        
        worksheet.write(row, col, 'Fecha Hasta:', header_format)
        worksheet.write(row, col + 1, self.date_to or '', data_format)
        row += 2
        
        # Métricas principales
        worksheet.write(row, col, 'MÉTRICAS PRINCIPALES', workbook.add_format({'bold': True, 'font_size': 14}))
        row += 1
        
        metrics = [
            ('Total Mantenimientos', self.total_maintenances),
            ('Pendientes', self.pending_maintenances),
            ('Completados', self.completed_maintenances),
            ('Vencidos', self.overdue_maintenances),
            ('Total Tickets', self.total_tickets),
            ('Tickets Abiertos', self.open_tickets),
            ('Total Reparaciones', self.total_repairs),
            ('Reparaciones Activas', self.active_repairs),
        ]
        
        for metric_name, metric_value in metrics:
            worksheet.write(row, col, metric_name, header_format)
            worksheet.write(row, col + 1, metric_value, number_format)
            row += 1
        
        row += 2
        
        # Hoja 2: Rendimiento por Técnico
        worksheet2 = workbook.add_worksheet('Rendimiento por Técnico')
        row = 0
        headers = ['Técnico', 'Total', 'Completados', '% Completados']
        for i, header in enumerate(headers):
            worksheet2.write(row, i, header, header_format)
        row = 1
        
        for perf in self.technician_performance_ids:
            worksheet2.write(row, 0, perf.technician_id.name or '', data_format)
            worksheet2.write(row, 1, perf.total_maintenances, number_format)
            worksheet2.write(row, 2, perf.completed_maintenances, number_format)
            worksheet2.write(row, 3, f"{perf.completion_rate * 100:.2f}%", number_format)
            row += 1
        
        # Hoja 3: Mantenimientos por Cliente
        worksheet3 = workbook.add_worksheet('Mantenimientos por Cliente')
        row = 0
        headers = ['Cliente', 'Total', 'Pendientes', 'Completados']
        for i, header in enumerate(headers):
            worksheet3.write(row, i, header, header_format)
        row = 1
        
        for client in self.client_maintenance_ids:
            worksheet3.write(row, 0, client.partner_id.name or '', data_format)
            worksheet3.write(row, 1, client.total_maintenances, number_format)
            worksheet3.write(row, 2, client.pending_maintenances, number_format)
            worksheet3.write(row, 3, client.completed_maintenances, number_format)
            row += 1
        
        # Hoja 4: Tendencia Mensual
        worksheet4 = workbook.add_worksheet('Tendencia Mensual')
        row = 0
        headers = ['Mes', 'Total', 'Completados', 'Pendientes']
        for i, header in enumerate(headers):
            worksheet4.write(row, i, header, header_format)
        row = 1
        
        for trend in self.monthly_trend_ids:
            worksheet4.write(row, 0, trend.month or '', data_format)
            worksheet4.write(row, 1, trend.total_maintenances, number_format)
            worksheet4.write(row, 2, trend.completed_maintenances, number_format)
            worksheet4.write(row, 3, trend.pending_maintenances, number_format)
            row += 1
        
        # Hoja 5: Distribución por Tipo
        worksheet5 = workbook.add_worksheet('Distribución por Tipo')
        row = 0
        headers = ['Tipo de Mantenimiento', 'Cantidad']
        for i, header in enumerate(headers):
            worksheet5.write(row, i, header, header_format)
        row = 1
        
        for dist in self.type_distribution_ids:
            worksheet5.write(row, 0, dist.type_label or '', data_format)
            worksheet5.write(row, 1, dist.count, number_format)
            row += 1
        
        # Hoja 6: Equipos Problemáticos
        worksheet6 = workbook.add_worksheet('Equipos Problemáticos')
        row = 0
        headers = ['Equipo', 'Placa Inventario', 'Total', 'Completados', 'Pendientes']
        for i, header in enumerate(headers):
            worksheet6.write(row, i, header, header_format)
        row = 1
        
        for equip in self.problematic_equipment_ids:
            worksheet6.write(row, 0, equip.equipment_name or '', data_format)
            worksheet6.write(row, 1, equip.inventory_plate or '', data_format)
            worksheet6.write(row, 2, equip.total_maintenances, number_format)
            worksheet6.write(row, 3, equip.completed_maintenances, number_format)
            worksheet6.write(row, 4, equip.pending_maintenances, number_format)
            row += 1
        
        workbook.close()
        output.seek(0)
        
        # Crear attachment y devolver acción de descarga
        attachment = self.env['ir.attachment'].create({
            'name': f'Dashboard_Mantenimientos_{fields.Datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx',
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'res_model': 'maintenance.dashboard',
            'res_id': self.id,
        })
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
    
    def action_export_pdf(self):
        """Exportar dashboard a PDF."""
        self.ensure_one()
        return {
            'type': 'ir.actions.report',
            'report_name': 'mesa_ayuda_inventario.report_maintenance_dashboard',
            'report_type': 'qweb-pdf',
            'res_model': 'maintenance.dashboard',
            'res_ids': [self.id],
            'context': self.env.context,
        }
    
    def action_export_technicians_excel(self):
        """Exportar estadísticas de técnicos a Excel."""
        self.ensure_one()
        
        if not XLSXWRITER_AVAILABLE:
            raise UserError(_('El módulo xlsxwriter no está instalado. Por favor, instálelo para usar la exportación a Excel.'))
        
        # Asegurar que los datos estén actualizados
        self._load_technician_performance()
        self._load_visit_data()
        
        # Crear archivo Excel en memoria
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        
        # Formato para encabezados
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#f5576c',
            'font_color': 'white',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })
        
        # Formato para datos
        data_format = workbook.add_format({
            'border': 1,
            'align': 'left',
            'valign': 'vcenter'
        })
        
        # Formato para números
        number_format = workbook.add_format({
            'border': 1,
            'align': 'right',
            'valign': 'vcenter'
        })
        
        # Formato para porcentajes
        percent_format = workbook.add_format({
            'border': 1,
            'align': 'right',
            'valign': 'vcenter',
            'num_format': '0.00%'
        })
        
        # Hoja 1: Resumen General
        worksheet = workbook.add_worksheet('Resumen')
        row = 0
        
        worksheet.write(row, 0, 'ESTADÍSTICAS DE TÉCNICOS', workbook.add_format({'bold': True, 'font_size': 16}))
        row += 2
        
        worksheet.write(row, 0, 'Fecha Desde:', header_format)
        worksheet.write(row, 1, self.date_from.strftime('%Y-%m-%d') if self.date_from else '', data_format)
        row += 1
        
        worksheet.write(row, 0, 'Fecha Hasta:', header_format)
        worksheet.write(row, 1, self.date_to.strftime('%Y-%m-%d') if self.date_to else '', data_format)
        row += 2
        
        # Métricas generales
        worksheet.write(row, 0, 'Total Técnicos', header_format)
        worksheet.write(row, 1, len(self.technician_performance_ids), number_format)
        row += 1
        
        worksheet.write(row, 0, 'Total Mantenimientos', header_format)
        worksheet.write(row, 1, self.total_maintenances, number_format)
        row += 1
        
        worksheet.write(row, 0, 'Mantenimientos Completados', header_format)
        worksheet.write(row, 1, self.completed_maintenances, number_format)
        row += 1
        
        worksheet.write(row, 0, 'Total Órdenes/Visitas', header_format)
        worksheet.write(row, 1, self.total_orders, number_format)
        row += 2
        
        # Hoja 2: Rendimiento en Mantenimientos
        worksheet2 = workbook.add_worksheet('Mantenimientos')
        row = 0
        headers = ['Técnico', 'Total Mantenimientos', 'Completados', '% Completados']
        for i, header in enumerate(headers):
            worksheet2.write(row, i, header, header_format)
        row = 1
        
        for perf in self.technician_performance_ids.sorted('completion_rate', reverse=True):
            worksheet2.write(row, 0, perf.technician_id.name or '', data_format)
            worksheet2.write(row, 1, perf.total_maintenances, number_format)
            worksheet2.write(row, 2, perf.completed_maintenances, number_format)
            worksheet2.write(row, 3, perf.completion_rate, percent_format)
            row += 1
        
        # Hoja 3: Rendimiento en Visitas
        worksheet3 = workbook.add_worksheet('Visitas y Órdenes')
        row = 0
        headers = ['Técnico', 'Total Órdenes', 'Completadas', 'Programadas']
        for i, header in enumerate(headers):
            worksheet3.write(row, i, header, header_format)
        row = 1
        
        for visit_tech in self.visit_by_technician_ids.sorted('total_orders', reverse=True):
            worksheet3.write(row, 0, visit_tech.technician_id.name or '', data_format)
            worksheet3.write(row, 1, visit_tech.total_orders, number_format)
            worksheet3.write(row, 2, visit_tech.completed_orders, number_format)
            worksheet3.write(row, 3, visit_tech.scheduled_orders, number_format)
            row += 1
        
        workbook.close()
        output.seek(0)
        
        # Crear attachment y devolver acción de descarga
        attachment = self.env['ir.attachment'].create({
            'name': f'Estadisticas_Tecnicos_{fields.Datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx',
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'res_model': 'maintenance.dashboard',
            'res_id': self.id,
        })
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
    
    def action_export_technicians_pdf(self):
        """Exportar estadísticas de técnicos a PDF."""
        self.ensure_one()
        # Usar el mismo reporte que el dashboard general o crear uno específico
        # Por ahora usamos el mismo
        return {
            'type': 'ir.actions.report',
            'report_name': 'mesa_ayuda_inventario.report_maintenance_dashboard',
            'report_type': 'qweb-pdf',
            'res_model': 'maintenance.dashboard',
            'res_ids': [self.id],
            'context': self.env.context,
        }


class MaintenanceTechnicianPerformance(models.TransientModel):
    """Rendimiento por técnico."""
    _name = 'maintenance.technician.performance'
    _description = 'Rendimiento de Técnico'
    _order = 'completion_rate desc, total_maintenances desc'
    
    dashboard_id = fields.Many2one('maintenance.dashboard', ondelete='cascade')
    technician_id = fields.Many2one('res.users', string='Técnico', required=True)
    total_maintenances = fields.Integer(string='Total')
    completed_maintenances = fields.Integer(string='Completados')
    completion_rate = fields.Float(string='% Completados', digits=(16, 2))


class MaintenanceClientSummary(models.TransientModel):
    """Resumen por cliente."""
    _name = 'maintenance.client.summary'
    _description = 'Resumen de Cliente'
    
    dashboard_id = fields.Many2one('maintenance.dashboard', ondelete='cascade')
    partner_id = fields.Many2one('res.partner', string='Cliente', required=True)
    total_maintenances = fields.Integer(string='Total')
    pending_maintenances = fields.Integer(string='Pendientes')
    completed_maintenances = fields.Integer(string='Completados')


# ========== PUNTO 5.1: MODELOS PARA GRÁFICOS ==========

class MaintenanceMonthlyTrend(models.TransientModel):
    """Tendencia mensual de mantenimientos."""
    _name = 'maintenance.monthly.trend'
    _description = 'Tendencia Mensual'
    _order = 'month'
    
    dashboard_id = fields.Many2one('maintenance.dashboard', ondelete='cascade')
    month = fields.Char(string='Mes', required=True)
    total_maintenances = fields.Integer(string='Total')
    completed_maintenances = fields.Integer(string='Completados')
    pending_maintenances = fields.Integer(string='Pendientes')


class MaintenanceTypeDistribution(models.TransientModel):
    """Distribución por tipo de mantenimiento."""
    _name = 'maintenance.type.distribution'
    _description = 'Distribución por Tipo'
    _order = 'count desc'
    
    dashboard_id = fields.Many2one('maintenance.dashboard', ondelete='cascade')
    maintenance_type = fields.Char(string='Tipo', required=True)
    type_label = fields.Char(string='Etiqueta', required=True)
    count = fields.Integer(string='Cantidad')


class MaintenanceWeekdayActivity(models.TransientModel):
    """Actividad por día de semana."""
    _name = 'maintenance.weekday.activity'
    _description = 'Actividad por Día'
    _order = 'weekday'
    
    dashboard_id = fields.Many2one('maintenance.dashboard', ondelete='cascade')
    weekday = fields.Integer(string='Día', required=True)
    weekday_label = fields.Char(string='Día de la Semana', required=True)
    count = fields.Integer(string='Cantidad')


# ========== PUNTO 5.2: MODELOS PARA MÉTRICAS ADICIONALES ==========

class MaintenanceAvgResolutionTime(models.TransientModel):
    """Tiempo promedio de resolución por tipo."""
    _name = 'maintenance.avg.resolution.time'
    _description = 'Tiempo Promedio de Resolución'
    _order = 'avg_hours desc'
    
    dashboard_id = fields.Many2one('maintenance.dashboard', ondelete='cascade')
    maintenance_type = fields.Char(string='Tipo', required=True)
    type_label = fields.Char(string='Etiqueta', required=True)
    avg_hours = fields.Float(string='Promedio (Horas)', digits=(16, 2))
    count = fields.Integer(string='Cantidad')


class MaintenanceProblematicEquipment(models.TransientModel):
    """Equipos más problemáticos."""
    _name = 'maintenance.problematic.equipment'
    _description = 'Equipos Más Problemáticos'
    _order = 'total_maintenances desc'
    
    dashboard_id = fields.Many2one('maintenance.dashboard', ondelete='cascade')
    lot_id = fields.Many2one('stock.lot', string='Equipo', required=True)
    equipment_name = fields.Char(string='Nombre del Equipo')
    inventory_plate = fields.Char(string='Placa de Inventario')
    total_maintenances = fields.Integer(string='Total Mantenimientos')
    completed_maintenances = fields.Integer(string='Completados')
    pending_maintenances = fields.Integer(string='Pendientes')


# ========== MODELOS PARA GRÁFICAS DE VISITAS PROGRAMADAS ==========

class MaintenanceVisitByTechnician(models.TransientModel):
    """Visitas programadas por técnico."""
    _name = 'maintenance.visit.by.technician'
    _description = 'Visitas por Técnico'
    _order = 'total_orders desc'
    
    dashboard_id = fields.Many2one('maintenance.dashboard', ondelete='cascade')
    technician_id = fields.Many2one('res.users', string='Técnico', required=True)
    total_orders = fields.Integer(string='Total Órdenes')
    completed_orders = fields.Integer(string='Completadas')
    scheduled_orders = fields.Integer(string='Programadas')


class MaintenanceVisitByType(models.TransientModel):
    """Visitas programadas por tipo de actividad."""
    _name = 'maintenance.visit.by.type'
    _description = 'Visitas por Tipo'
    _order = 'total_orders desc'
    
    dashboard_id = fields.Many2one('maintenance.dashboard', ondelete='cascade')
    activity_type = fields.Char(string='Tipo', required=True)
    type_label = fields.Char(string='Etiqueta', required=True)
    total_orders = fields.Integer(string='Total Órdenes')
    completed_orders = fields.Integer(string='Completadas')


class MaintenanceVisitMonthlyTrend(models.TransientModel):
    """Tendencia mensual de visitas programadas."""
    _name = 'maintenance.visit.monthly.trend'
    _description = 'Tendencia Mensual de Visitas'
    _order = 'month'
    
    dashboard_id = fields.Many2one('maintenance.dashboard', ondelete='cascade')
    month = fields.Char(string='Mes', required=True)
    total_orders = fields.Integer(string='Total')
    completed_orders = fields.Integer(string='Completadas')
    scheduled_orders = fields.Integer(string='Programadas')

