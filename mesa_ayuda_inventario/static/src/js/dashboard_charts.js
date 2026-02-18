// Script para renderizar gráficos en el dashboard de mantenimientos
// JavaScript vanilla - lee datos directamente de las tablas renderizadas

(function() {
    'use strict';
    
    var chartsLoaded = false;
    
    // Función principal que se ejecuta cuando la página está lista
    function init() {
        console.log('Dashboard Charts: Script inicializado');
        
        // Múltiples intentos para asegurar que se ejecute
        var attempts = [3000, 5000, 7000];
        
        attempts.forEach(function(delay) {
            setTimeout(function() {
                console.log('Dashboard Charts: Intento de renderizado después de', delay, 'ms');
                checkAndRenderCharts();
            }, delay);
        });
        
        // También intentar cuando el DOM esté listo
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', function() {
                setTimeout(checkAndRenderCharts, 3000);
            });
        }
        
        // Observar cambios en el DOM para re-renderizar
        observeDashboardChanges();
    }
    
    function observeDashboardChanges() {
        if (!window.MutationObserver) return;
        
        var observer = new MutationObserver(function(mutations) {
            var shouldRerender = false;
            
            mutations.forEach(function(mutation) {
                if (mutation.addedNodes.length > 0) {
                    // Verificar si se agregaron elementos del dashboard
                    for (var i = 0; i < mutation.addedNodes.length; i++) {
                        var node = mutation.addedNodes[i];
                        if (node.nodeType === 1) { // Element node
                            // Verificar si se agregó un canvas o contenido del dashboard
                            if (node.querySelector && (
                                node.querySelector('#chartVisitByTechnician') ||
                                node.querySelector('#chartMonthlyTrend') ||
                                node.querySelector('#chartTechnicianPerformance') ||
                                node.textContent && (
                                    node.textContent.includes('Dashboard') ||
                                    node.textContent.includes('Métricas') ||
                                    node.textContent.includes('Visitas Programadas')
                                )
                            )) {
                                shouldRerender = true;
                                break;
                            }
                        }
                    }
                }
            });
            
            if (shouldRerender) {
                console.log('Dashboard Charts: Cambios detectados, re-renderizando gráficos...');
                chartsLoaded = false; // Permitir re-renderizado
                setTimeout(function() {
                    checkAndRenderCharts();
                }, 1500);
            }
        });
        
        var target = document.body || document.documentElement;
        if (target) {
            observer.observe(target, {
                childList: true,
                subtree: true,
                attributes: false
            });
        }
        
        // Escuchar eventos de cambio de URL/hash (cuando Odoo navega)
        var lastUrl = window.location.href;
        setInterval(function() {
            if (window.location.href !== lastUrl) {
                lastUrl = window.location.href;
                if (window.location.href.includes('maintenance.dashboard')) {
                    console.log('Dashboard Charts: URL cambió, verificando gráficos...');
                    chartsLoaded = false;
                    setTimeout(checkAndRenderCharts, 2000);
                }
            }
        }, 1000);
        
        // Forzar verificación periódica si estamos en el dashboard
        setInterval(function() {
            var canvas = document.getElementById('chartVisitByTechnician') || 
                        document.getElementById('chartMonthlyTrend') || 
                        document.getElementById('chartTechnicianPerformance') ||
                        document.getElementById('chartVisitByType') ||
                        document.getElementById('chartWeekdayActivity') ||
                        document.getElementById('chartTypeDistribution');
            if (canvas && !chartsLoaded) {
                console.log('Dashboard Charts: Canvas encontrado pero gráfico no cargado, reintentando...');
                chartsLoaded = false; // Resetear flag para permitir reintento
                checkAndRenderCharts();
            }
        }, 3000);
    }
    
    function checkAndRenderCharts() {
        console.log('Dashboard Charts: Verificando dashboard...');
        
        // Verificar si estamos en la página del dashboard - buscar cualquier canvas de gráficos
        var canvasMonthly = document.getElementById('chartMonthlyTrend');
        var canvasVisitTech = document.getElementById('chartVisitByTechnician');
        var canvasTechPerf = document.getElementById('chartTechnicianPerformance');
        var canvasVisitType = document.getElementById('chartVisitByType');
        var canvasWeekday = document.getElementById('chartWeekdayActivity');
        var canvasTypeDist = document.getElementById('chartTypeDistribution');
        
        var anyCanvas = canvasMonthly || canvasVisitTech || canvasTechPerf || canvasVisitType || canvasWeekday || canvasTypeDist;
        
        var dashboardTitle = document.querySelector('h1, h2');
        var hasDashboardContent = false;
        
        if (dashboardTitle) {
            hasDashboardContent = dashboardTitle.textContent.includes('Dashboard') ||
                                  dashboardTitle.textContent.includes('Métricas') ||
                                  dashboardTitle.textContent.includes('Estadísticas') ||
                                  dashboardTitle.textContent.includes('Visitas Programadas') ||
                                  document.body.textContent.includes('Tendencia Mensual') ||
                                  document.body.textContent.includes('Rendimiento por Técnico');
        }
        
        var dashboardExists = anyCanvas || hasDashboardContent;
        
        console.log('Dashboard Charts: Canvas encontrado:', !!anyCanvas);
        console.log('Dashboard Charts: Contenido del dashboard encontrado:', hasDashboardContent);
        
        if (!dashboardExists) {
            console.log('Dashboard Charts: Dashboard no encontrado, saliendo...');
            return; // No estamos en el dashboard
        }
        
        console.log('Dashboard Charts: Dashboard encontrado, cargando Chart.js...');
        
        // Cargar Chart.js y renderizar
        loadChartJS().then(function() {
            console.log('Dashboard Charts: Chart.js cargado correctamente');
            // Esperar un poco más para que las tablas se rendericen completamente
            setTimeout(function() {
                renderAllCharts();
                chartsLoaded = true;
            }, 1500);
        }).catch(function(err) {
            console.error('Dashboard Charts: Error cargando Chart.js:', err);
            // Mostrar mensaje de error visible
            showError('Error cargando la librería de gráficos. Por favor, recarga la página.');
        });
    }
    
    function showError(message) {
        var errorDiv = document.createElement('div');
        errorDiv.style.cssText = 'position: fixed; top: 20px; right: 20px; background: #f5576c; color: white; padding: 15px; border-radius: 5px; z-index: 10000; max-width: 400px;';
        errorDiv.textContent = message;
        document.body.appendChild(errorDiv);
        setTimeout(function() {
            errorDiv.remove();
        }, 5000);
    }
    
    function loadChartJS() {
        return new Promise(function(resolve, reject) {
            // Si ya está cargado
            if (typeof Chart !== 'undefined') {
                resolve();
                return;
            }
            
            // Verificar si ya está en proceso de carga
            var existingScript = document.querySelector('script[src*="chart.js"]');
            if (existingScript) {
                var checkInterval = setInterval(function() {
                    if (typeof Chart !== 'undefined') {
                        clearInterval(checkInterval);
                        resolve();
                    }
                }, 100);
                setTimeout(function() {
                    clearInterval(checkInterval);
                    if (typeof Chart === 'undefined') {
                        reject(new Error('Timeout cargando Chart.js'));
                    }
                }, 10000);
                return;
            }
            
            // Cargar Chart.js
            var script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js';
            script.async = true;
            script.onload = function() {
                if (typeof Chart !== 'undefined') {
                    resolve();
                } else {
                    reject(new Error('Chart.js no se inicializó correctamente'));
                }
            };
            script.onerror = function() {
                reject(new Error('Error cargando Chart.js desde CDN'));
            };
            document.head.appendChild(script);
        });
    }
    
    function renderAllCharts() {
        if (typeof Chart === 'undefined') {
            console.error('Chart.js no está disponible');
            return;
        }
        
        console.log('Iniciando renderizado de gráficos...');
        
        // Renderizar cada gráfico usando datos de las tablas
        renderMonthlyTrendChart();
        renderTypeDistributionChart();
        renderWeekdayActivityChart();
        renderTechnicianPerformanceChart();
        // ✅ Renderizar gráficas de visitas programadas
        renderVisitByTechnicianChart();
        renderVisitByTypeChart();
        renderVisitMonthlyTrendChart();
        renderVisitComplianceChart();
    }
    
    // ========== EXTRACCIÓN DE DATOS DESDE TABLAS ==========
    
    function extractMonthlyTrendData() {
        // Buscar la tabla directamente por su contexto (después del título "Tendencia Mensual")
        var allTables = document.querySelectorAll('table.o_list_table, table.o_list_view');
        var monthlyTrendTable = null;
        
        // Buscar la tabla que está después del h2 que contiene "Tendencia Mensual"
        var h2Elements = document.querySelectorAll('h2');
        for (var i = 0; i < h2Elements.length; i++) {
            if (h2Elements[i].textContent.includes('Tendencia Mensual')) {
                // Buscar la tabla más cercana después de este h2
                var nextElement = h2Elements[i].nextElementSibling;
                while (nextElement) {
                    monthlyTrendTable = nextElement.querySelector('table');
                    if (monthlyTrendTable) break;
                    nextElement = nextElement.nextElementSibling;
                }
                // Si no la encontramos, buscar en el contenedor padre
                if (!monthlyTrendTable) {
                    var parent = h2Elements[i].parentElement;
                    if (parent) {
                        monthlyTrendTable = parent.querySelector('table');
                    }
                }
                break;
            }
        }
        
        if (!monthlyTrendTable) {
            console.log('Tabla monthlyTrend no encontrada');
            return null;
        }
        
        var rows = monthlyTrendTable.querySelectorAll('tbody tr');
        if (rows.length === 0) {
            console.log('No hay filas en tabla monthlyTrend');
            return null;
        }
        
        var labels = [];
        var totals = [];
        var completed = [];
        var pending = [];
        
        rows.forEach(function(row) {
            var cells = row.querySelectorAll('td');
            if (cells.length >= 4) {
                var month = cells[0].textContent.trim();
                var total = parseInt(cells[1].textContent.trim()) || 0;
                var completedVal = parseInt(cells[2].textContent.trim()) || 0;
                var pendingVal = parseInt(cells[3].textContent.trim()) || 0;
                
                if (month && month !== '' && month !== 'False') {
                    labels.push(month);
                    totals.push(total);
                    completed.push(completedVal);
                    pending.push(pendingVal);
                }
            }
        });
        
        if (labels.length === 0) {
            console.log('No se pudieron extraer labels de monthlyTrend');
            return null;
        }
        
        console.log('Datos extraídos monthlyTrend:', labels, totals, completed, pending);
        
        return {
            labels: labels,
            datasets: [
                {label: 'Total', data: totals, borderColor: '#667eea', backgroundColor: 'rgba(102, 126, 234, 0.1)'},
                {label: 'Completados', data: completed, borderColor: '#4facfe', backgroundColor: 'rgba(79, 172, 254, 0.1)'},
                {label: 'Pendientes', data: pending, borderColor: '#f5576c', backgroundColor: 'rgba(245, 87, 108, 0.1)'}
            ]
        };
    }
    
    function extractTypeDistributionData() {
        // Buscar la tabla por su contexto
        var h2Elements = document.querySelectorAll('h2');
        var typeDistTable = null;
        
        for (var i = 0; i < h2Elements.length; i++) {
            if (h2Elements[i].textContent.includes('Distribución por Tipo')) {
                var nextElement = h2Elements[i].nextElementSibling;
                while (nextElement) {
                    typeDistTable = nextElement.querySelector('table');
                    if (typeDistTable) break;
                    nextElement = nextElement.nextElementSibling;
                }
                if (!typeDistTable) {
                    var parent = h2Elements[i].parentElement;
                    if (parent) {
                        typeDistTable = parent.querySelector('table');
                    }
                }
                break;
            }
        }
        
        if (!typeDistTable) {
            console.log('Tabla typeDistribution no encontrada');
            return null;
        }
        
        var rows = typeDistTable.querySelectorAll('tbody tr');
        if (rows.length === 0) {
            console.log('No hay filas en tabla typeDistribution');
            return null;
        }
        
        var labels = [];
        var data = [];
        
        rows.forEach(function(row) {
            var cells = row.querySelectorAll('td');
            if (cells.length >= 2) {
                var label = cells[0].textContent.trim();
                var value = parseInt(cells[1].textContent.trim()) || 0;
                if (label && label !== '' && label !== 'False') {
                    labels.push(label);
                    data.push(value);
                }
            }
        });
        
        if (labels.length === 0) {
            console.log('No se pudieron extraer labels de typeDistribution');
            return null;
        }
        
        var colors = ['#667eea', '#764ba2', '#f093fb', '#f5576c', '#4facfe', '#00f2fe', '#43e97b', '#38f9d7'];
        
        return {
            labels: labels,
            data: data,
            backgroundColor: colors.slice(0, data.length)
        };
    }
    
    function extractWeekdayActivityData() {
        var h2Elements = document.querySelectorAll('h2');
        var weekdayTable = null;
        
        for (var i = 0; i < h2Elements.length; i++) {
            if (h2Elements[i].textContent.includes('Actividad por Día')) {
                var nextElement = h2Elements[i].nextElementSibling;
                while (nextElement) {
                    weekdayTable = nextElement.querySelector('table');
                    if (weekdayTable) break;
                    nextElement = nextElement.nextElementSibling;
                }
                if (!weekdayTable) {
                    var parent = h2Elements[i].parentElement;
                    if (parent) {
                        weekdayTable = parent.querySelector('table');
                    }
                }
                break;
            }
        }
        
        if (!weekdayTable) {
            console.log('Tabla weekdayActivity no encontrada');
            return null;
        }
        
        var rows = weekdayTable.querySelectorAll('tbody tr');
        if (rows.length === 0) {
            console.log('No hay filas en tabla weekdayActivity');
            return null;
        }
        
        var labels = [];
        var data = [];
        
        rows.forEach(function(row) {
            var cells = row.querySelectorAll('td');
            if (cells.length >= 2) {
                var label = cells[0].textContent.trim();
                var value = parseInt(cells[1].textContent.trim()) || 0;
                if (label && label !== '' && label !== 'False') {
                    labels.push(label);
                    data.push(value);
                }
            }
        });
        
        if (labels.length === 0) {
            console.log('No se pudieron extraer labels de weekdayActivity');
            return null;
        }
        
        return {
            labels: labels,
            data: data,
            backgroundColor: '#667eea'
        };
    }
    
    function extractTechnicianPerformanceData() {
        var h2Elements = document.querySelectorAll('h2');
        var techTable = null;
        
        for (var i = 0; i < h2Elements.length; i++) {
            if (h2Elements[i].textContent.includes('Rendimiento por Técnico')) {
                var nextElement = h2Elements[i].nextElementSibling;
                while (nextElement) {
                    techTable = nextElement.querySelector('table');
                    if (techTable) break;
                    nextElement = nextElement.nextElementSibling;
                }
                if (!techTable) {
                    var parent = h2Elements[i].parentElement;
                    if (parent) {
                        techTable = parent.querySelector('table');
                    }
                }
                break;
            }
        }
        
        if (!techTable) {
            console.log('Tabla technician_performance no encontrada');
            return null;
        }
        
        var rows = techTable.querySelectorAll('tbody tr');
        if (rows.length === 0) {
            console.log('No hay filas en tabla technician_performance');
            return null;
        }
        
        var labels = [];
        var completed = [];
        var pending = [];
        
        rows.forEach(function(row) {
            var cells = row.querySelectorAll('td');
            if (cells.length >= 3) {
                var techName = cells[0].textContent.trim();
                if (techName && techName !== '' && techName !== 'False') {
                    labels.push(techName);
                    var total = parseInt(cells[1].textContent.trim()) || 0;
                    var completedCount = parseInt(cells[2].textContent.trim()) || 0;
                    completed.push(completedCount);
                    pending.push(Math.max(0, total - completedCount));
                }
            }
        });
        
        if (labels.length === 0) {
            console.log('No se pudieron extraer labels de technician_performance');
            return null;
        }
        
        console.log('Datos extraídos technician_performance:', labels, completed, pending);
        
        return {
            labels: labels,
            datasets: [
                {label: 'Completados', data: completed, backgroundColor: '#4facfe'},
                {label: 'Pendientes', data: pending, backgroundColor: '#f5576c'}
            ]
        };
    }
    
    // ========== RENDERIZADO DE GRÁFICOS ==========
    
    function renderMonthlyTrendChart() {
        var canvas = document.getElementById('chartMonthlyTrend');
        if (!canvas) {
            console.log('Canvas monthlyTrend no encontrado');
            return;
        }
        
        var chartData = extractMonthlyTrendData();
        if (!chartData) {
            console.log('No hay datos para monthlyTrend');
            return;
        }
        
        try {
            // Destruir gráfico anterior
            if (window.monthlyTrendChart) {
                window.monthlyTrendChart.destroy();
            }
            
            var ctx = canvas.getContext('2d');
            window.monthlyTrendChart = new Chart(ctx, {
                type: 'line',
                data: chartData,
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'top' },
                    },
                    scales: {
                        y: { beginAtZero: true }
                    }
                }
            });
            console.log('Gráfico monthlyTrend renderizado');
        } catch (e) {
            console.error('Error renderizando monthlyTrend:', e);
        }
    }
    
    function renderTypeDistributionChart() {
        var canvas = document.getElementById('chartTypeDistribution');
        if (!canvas) {
            console.log('Canvas typeDistribution no encontrado');
            return;
        }
        
        var chartData = extractTypeDistributionData();
        if (!chartData) {
            console.log('No hay datos para typeDistribution');
            return;
        }
        
        try {
            if (window.typeDistributionChart) {
                window.typeDistributionChart.destroy();
            }
            
            var ctx = canvas.getContext('2d');
            window.typeDistributionChart = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: chartData.labels,
                    datasets: [{
                        data: chartData.data,
                        backgroundColor: chartData.backgroundColor
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {
                        legend: { position: 'right' },
                    }
                }
            });
            console.log('Gráfico typeDistribution renderizado');
        } catch (e) {
            console.error('Error renderizando typeDistribution:', e);
        }
    }
    
    function renderWeekdayActivityChart() {
        var canvas = document.getElementById('chartWeekdayActivity');
        if (!canvas) {
            console.log('Canvas weekdayActivity no encontrado');
            return;
        }
        
        var chartData = extractWeekdayActivityData();
        if (!chartData) {
            console.log('No hay datos para weekdayActivity');
            return;
        }
        
        try {
            if (window.weekdayActivityChart) {
                window.weekdayActivityChart.destroy();
            }
            
            var ctx = canvas.getContext('2d');
            window.weekdayActivityChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: chartData.labels,
                    datasets: [{
                        label: 'Mantenimientos',
                        data: chartData.data,
                        backgroundColor: chartData.backgroundColor
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                    },
                    scales: {
                        y: { beginAtZero: true }
                    }
                }
            });
            console.log('Gráfico weekdayActivity renderizado');
        } catch (e) {
            console.error('Error renderizando weekdayActivity:', e);
        }
    }
    
    function renderTechnicianPerformanceChart() {
        var canvas = document.getElementById('chartTechnicianPerformance');
        if (!canvas) {
            console.log('Canvas technicianPerformance no encontrado');
            return;
        }
        
        var chartData = extractTechnicianPerformanceData();
        if (!chartData) {
            console.log('No hay datos para technicianPerformance');
            return;
        }
        
        try {
            if (window.technicianPerformanceChart) {
                window.technicianPerformanceChart.destroy();
            }
            
            var ctx = canvas.getContext('2d');
            window.technicianPerformanceChart = new Chart(ctx, {
                type: 'bar',
                data: chartData,
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'top' },
                    },
                    scales: {
                        x: { stacked: true },
                        y: { stacked: true, beginAtZero: true }
                    }
                }
            });
            console.log('Gráfico technicianPerformance renderizado');
        } catch (e) {
            console.error('Error renderizando technicianPerformance:', e);
        }
    }
    
    // ========== GRÁFICAS DE VISITAS PROGRAMADAS ==========
    
    function extractVisitByTechnicianData() {
        var h2Elements = document.querySelectorAll('h2');
        var visitTechTable = null;
        
        for (var i = 0; i < h2Elements.length; i++) {
            if (h2Elements[i].textContent.includes('Visitas Programadas por Técnico')) {
                var nextElement = h2Elements[i].nextElementSibling;
                while (nextElement) {
                    visitTechTable = nextElement.querySelector('table');
                    if (visitTechTable) break;
                    nextElement = nextElement.nextElementSibling;
                }
                if (!visitTechTable) {
                    var parent = h2Elements[i].parentElement;
                    if (parent) {
                        visitTechTable = parent.querySelector('table');
                    }
                }
                break;
            }
        }
        
        if (!visitTechTable) {
            console.log('Tabla visitByTechnician no encontrada');
            return null;
        }
        
        var rows = visitTechTable.querySelectorAll('tbody tr');
        if (rows.length === 0) {
            console.log('No hay filas en tabla visitByTechnician');
            return null;
        }
        
        var labels = [];
        var completed = [];
        var scheduled = [];
        
        rows.forEach(function(row) {
            var cells = row.querySelectorAll('td');
            if (cells.length >= 4) {
                var techName = cells[0].textContent.trim();
                var total = parseInt(cells[1].textContent.trim()) || 0;
                var completedCount = parseInt(cells[2].textContent.trim()) || 0;
                var scheduledCount = parseInt(cells[3].textContent.trim()) || 0;
                
                if (techName && techName !== '' && techName !== 'False') {
                    labels.push(techName);
                    completed.push(completedCount);
                    scheduled.push(scheduledCount);
                }
            }
        });
        
        if (labels.length === 0) {
            console.log('No se pudieron extraer labels de visitByTechnician');
            return null;
        }
        
        return {
            labels: labels,
            datasets: [
                {label: 'Completadas', data: completed, backgroundColor: '#4facfe'},
                {label: 'Programadas', data: scheduled, backgroundColor: '#f5576c'}
            ]
        };
    }
    
    function extractVisitByTypeData() {
        var h2Elements = document.querySelectorAll('h2');
        var visitTypeTable = null;
        
        for (var i = 0; i < h2Elements.length; i++) {
            if (h2Elements[i].textContent.includes('Visitas por Tipo de Actividad')) {
                var nextElement = h2Elements[i].nextElementSibling;
                while (nextElement) {
                    visitTypeTable = nextElement.querySelector('table');
                    if (visitTypeTable) break;
                    nextElement = nextElement.nextElementSibling;
                }
                if (!visitTypeTable) {
                    var parent = h2Elements[i].parentElement;
                    if (parent) {
                        visitTypeTable = parent.querySelector('table');
                    }
                }
                break;
            }
        }
        
        if (!visitTypeTable) {
            console.log('Tabla visitByType no encontrada');
            return null;
        }
        
        var rows = visitTypeTable.querySelectorAll('tbody tr');
        if (rows.length === 0) {
            console.log('No hay filas en tabla visitByType');
            return null;
        }
        
        var labels = [];
        var data = [];
        
        rows.forEach(function(row) {
            var cells = row.querySelectorAll('td');
            if (cells.length >= 2) {
                var label = cells[0].textContent.trim();
                var value = parseInt(cells[1].textContent.trim()) || 0;
                if (label && label !== '' && label !== 'False') {
                    labels.push(label);
                    data.push(value);
                }
            }
        });
        
        if (labels.length === 0) {
            console.log('No se pudieron extraer labels de visitByType');
            return null;
        }
        
        var colors = ['#667eea', '#764ba2', '#f093fb', '#f5576c', '#4facfe'];
        
        return {
            labels: labels,
            data: data,
            backgroundColor: colors.slice(0, data.length)
        };
    }
    
    function extractVisitMonthlyTrendData() {
        var h2Elements = document.querySelectorAll('h2');
        var visitTrendTable = null;
        
        for (var i = 0; i < h2Elements.length; i++) {
            if (h2Elements[i].textContent.includes('Tendencia Mensual de Visitas')) {
                var nextElement = h2Elements[i].nextElementSibling;
                while (nextElement) {
                    visitTrendTable = nextElement.querySelector('table');
                    if (visitTrendTable) break;
                    nextElement = nextElement.nextElementSibling;
                }
                if (!visitTrendTable) {
                    var parent = h2Elements[i].parentElement;
                    if (parent) {
                        visitTrendTable = parent.querySelector('table');
                    }
                }
                break;
            }
        }
        
        if (!visitTrendTable) {
            console.log('Tabla visitMonthlyTrend no encontrada');
            return null;
        }
        
        var rows = visitTrendTable.querySelectorAll('tbody tr');
        if (rows.length === 0) {
            console.log('No hay filas en tabla visitMonthlyTrend');
            return null;
        }
        
        var labels = [];
        var totals = [];
        var completed = [];
        var scheduled = [];
        
        rows.forEach(function(row) {
            var cells = row.querySelectorAll('td');
            if (cells.length >= 4) {
                var month = cells[0].textContent.trim();
                var total = parseInt(cells[1].textContent.trim()) || 0;
                var completedVal = parseInt(cells[2].textContent.trim()) || 0;
                var scheduledVal = parseInt(cells[3].textContent.trim()) || 0;
                
                if (month && month !== '' && month !== 'False') {
                    labels.push(month);
                    totals.push(total);
                    completed.push(completedVal);
                    scheduled.push(scheduledVal);
                }
            }
        });
        
        if (labels.length === 0) {
            console.log('No se pudieron extraer labels de visitMonthlyTrend');
            return null;
        }
        
        return {
            labels: labels,
            datasets: [
                {label: 'Total', data: totals, borderColor: '#667eea', backgroundColor: 'rgba(102, 126, 234, 0.1)'},
                {label: 'Completadas', data: completed, borderColor: '#4facfe', backgroundColor: 'rgba(79, 172, 254, 0.1)'},
                {label: 'Programadas', data: scheduled, borderColor: '#f5576c', backgroundColor: 'rgba(245, 87, 108, 0.1)'}
            ]
        };
    }
    
    function renderVisitByTechnicianChart() {
        var canvas = document.getElementById('chartVisitByTechnician');
        if (!canvas) {
            console.log('Canvas visitByTechnician no encontrado');
            return;
        }
        
        var chartData = extractVisitByTechnicianData();
        if (!chartData) {
            console.log('No hay datos para visitByTechnician');
            return;
        }
        
        try {
            if (window.visitByTechnicianChart) {
                window.visitByTechnicianChart.destroy();
            }
            
            var ctx = canvas.getContext('2d');
            window.visitByTechnicianChart = new Chart(ctx, {
                type: 'bar',
                data: chartData,
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'top' },
                    },
                    scales: {
                        x: { stacked: true },
                        y: { stacked: true, beginAtZero: true }
                    }
                }
            });
            console.log('Gráfico visitByTechnician renderizado');
        } catch (e) {
            console.error('Error renderizando visitByTechnician:', e);
        }
    }
    
    function renderVisitByTypeChart() {
        var canvas = document.getElementById('chartVisitByType');
        if (!canvas) {
            console.log('Canvas visitByType no encontrado');
            return;
        }
        
        var chartData = extractVisitByTypeData();
        if (!chartData) {
            console.log('No hay datos para visitByType');
            return;
        }
        
        try {
            if (window.visitByTypeChart) {
                window.visitByTypeChart.destroy();
            }
            
            var ctx = canvas.getContext('2d');
            window.visitByTypeChart = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: chartData.labels,
                    datasets: [{
                        data: chartData.data,
                        backgroundColor: chartData.backgroundColor
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    aspectRatio: 1.5,
                    plugins: {
                        legend: { position: 'right' },
                    }
                }
            });
            console.log('Gráfico visitByType renderizado');
        } catch (e) {
            console.error('Error renderizando visitByType:', e);
        }
    }
    
    function renderVisitMonthlyTrendChart() {
        var canvas = document.getElementById('chartVisitMonthlyTrend');
        if (!canvas) {
            console.log('Canvas visitMonthlyTrend no encontrado');
            return;
        }
        
        var chartData = extractVisitMonthlyTrendData();
        if (!chartData) {
            console.log('No hay datos para visitMonthlyTrend');
            return;
        }
        
        try {
            if (window.visitMonthlyTrendChart) {
                window.visitMonthlyTrendChart.destroy();
            }
            
            var ctx = canvas.getContext('2d');
            window.visitMonthlyTrendChart = new Chart(ctx, {
                type: 'line',
                data: chartData,
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'top' },
                    },
                    scales: {
                        y: { beginAtZero: true }
                    }
                }
            });
            console.log('Gráfico visitMonthlyTrend renderizado');
        } catch (e) {
            console.error('Error renderizando visitMonthlyTrend:', e);
        }
    }
    
    function renderVisitComplianceChart() {
        var canvas = document.getElementById('chartVisitCompliance');
        if (!canvas) {
            console.log('Canvas visitCompliance no encontrado');
            return;
        }
        
        // Buscar datos en las tarjetas de métricas
        var totalOrders = 0;
        var completedOrders = 0;
        
        try {
            // Buscar campo total_orders
            var totalField = document.querySelector('field[name="total_orders"]');
            if (totalField) {
                totalOrders = parseInt(totalField.textContent.trim()) || 0;
            }
            
            // Buscar campo completed_orders
            var completedField = document.querySelector('field[name="completed_orders"]');
            if (completedField) {
                completedOrders = parseInt(completedField.textContent.trim()) || 0;
            }
        } catch (e) {
            console.log('Error extrayendo métricas de cumplimiento:', e);
        }
        
        if (totalOrders === 0) {
            console.log('No hay datos para visitCompliance');
            return;
        }
        
        var compliancePercentage = (completedOrders / totalOrders * 100) || 0;
        var color = compliancePercentage >= 90 ? '#43e97b' : (compliancePercentage >= 70 ? '#ffd93d' : '#f5576c');
        
        try {
            if (window.visitComplianceChart) {
                window.visitComplianceChart.destroy();
            }
            
            var ctx = canvas.getContext('2d');
            window.visitComplianceChart = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    datasets: [{
                        data: [compliancePercentage, 100 - compliancePercentage],
                        backgroundColor: [color, '#e0e0e0'],
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    cutout: '75%',
                    plugins: {
                        legend: { display: false },
                        tooltip: { enabled: false },
                        title: {
                            display: true,
                            text: 'Cumplimiento: ' + compliancePercentage.toFixed(1) + '%',
                            font: { size: 18, weight: 'bold' },
                            color: color
                        }
                    }
                },
                plugins: [{
                    id: 'centerText',
                    beforeDraw: function(chart) {
                        var ctx = chart.ctx;
                        var centerX = chart.chartArea.left + (chart.chartArea.right - chart.chartArea.left) / 2;
                        var centerY = chart.chartArea.top + (chart.chartArea.bottom - chart.chartArea.top) / 2;
                        ctx.save();
                        ctx.font = 'bold 48px Arial';
                        ctx.fillStyle = color;
                        ctx.textAlign = 'center';
                        ctx.textBaseline = 'middle';
                        ctx.fillText(compliancePercentage.toFixed(1) + '%', centerX, centerY);
                        ctx.restore();
                    }
                }]
            });
            console.log('Gráfico visitCompliance renderizado');
        } catch (e) {
            console.error('Error renderizando visitCompliance:', e);
        }
    }
    
    // Inicializar
    init();
    
})();
