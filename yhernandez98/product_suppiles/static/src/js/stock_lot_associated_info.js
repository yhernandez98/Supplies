/** @odoo-module **/

// Función para aplicar estilo rojo y negrita a la pestaña "Información de Asociación"
(function() {
    'use strict';
    
    function styleAssociatedInfoTab() {
        // Buscar pestañas por atributo data-name
        const tabsByName = document.querySelectorAll('a[data-name="associated_element_info"]');
        tabsByName.forEach(function(tab) {
            tab.style.color = '#dc3545';
            tab.style.fontWeight = 'bold';
        });
        
        // Buscar pestañas por texto en todas las estructuras posibles
        const selectors = [
            '.nav-tabs a',
            '.o_notebook .nav-tabs a',
            '.o_form_view .nav-tabs a',
            '.o_form_view .o_notebook .nav-tabs a'
        ];
        
        selectors.forEach(function(selector) {
            const allTabs = document.querySelectorAll(selector);
            allTabs.forEach(function(tab) {
                const text = (tab.textContent || tab.innerText || '').trim();
                if (text === 'Información de Asociación') {
                    tab.style.color = '#dc3545';
                    tab.style.fontWeight = 'bold';
                }
            });
        });
    }
    
    // Ejecutar cuando el DOM esté listo
    function init() {
        styleAssociatedInfoTab();
        
        // Observar cambios en el DOM
        if (window.MutationObserver) {
            const observer = new MutationObserver(function() {
                styleAssociatedInfoTab();
            });
            
            if (document.body) {
                observer.observe(document.body, {
                    childList: true,
                    subtree: true
                });
            }
        }
        
        // Ejecutar con delays para asegurar que las pestañas estén renderizadas
        setTimeout(styleAssociatedInfoTab, 300);
        setTimeout(styleAssociatedInfoTab, 800);
        setTimeout(styleAssociatedInfoTab, 1500);
    }
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();

// Función para hacer seriales clickables en el campo Char
(function() {
    'use strict';
    
    function makeSerialsClickable() {
        // Buscar campos Char de seriales asociados en listas
        const serialDisplayFields = document.querySelectorAll('.o_list_view .o_field_char[name="associated_items_serials_display"]');
        serialDisplayFields.forEach(function(field) {
            // Verificar si ya se procesó (para evitar procesar múltiples veces)
            if (field.dataset.processed === 'true') {
                return;
            }
            
            // Obtener los seriales del texto
            const serialText = field.textContent.trim();
            if (!serialText) {
                field.dataset.processed = 'true';
                return;
            }
            
            const serials = serialText.split('\n').filter(s => s.trim());
            if (serials.length === 0) {
                field.dataset.processed = 'true';
                return;
            }
            
            // Buscar el campo Many2many invisible en la misma fila para obtener los IDs
            const row = field.closest('tr');
            if (!row) {
                field.dataset.processed = 'true';
                return;
            }
            
            // Buscar el campo Many2many (puede estar en una celda invisible)
            let lotIds = [];
            const many2manyField = row.querySelector('.o_field_many2many[name="associated_items_serials"]');
            if (many2manyField) {
                // Intentar obtener los IDs de los lotes desde el campo Many2many
                const links = many2manyField.querySelectorAll('a[href*="/web#id="]');
                links.forEach(function(link) {
                    const href = link.getAttribute('href');
                    const match = href.match(/id=(\d+)/);
                    if (match) {
                        lotIds.push({
                            id: match[1],
                            name: link.textContent.trim() || link.getAttribute('title') || ''
                        });
                    }
                });
            }
            
            // Crear contenedor para los links
            const container = document.createElement('div');
            container.style.whiteSpace = 'pre-line';
            container.style.lineHeight = '1.8';
            
            // Crear links para cada serial
            serials.forEach(function(serial, index) {
                const serialTrimmed = serial.trim();
                
                // Buscar el ID correspondiente en lotIds
                const lotInfo = lotIds.find(l => l.name === serialTrimmed);
                
                if (lotInfo && lotInfo.id) {
                    // Crear link con el ID del lote
                    const link = document.createElement('a');
                    link.href = '/web#id=' + lotInfo.id + '&model=stock.lot&view_type=form';
                    link.textContent = serialTrimmed;
                    link.style.color = '#007bff';
                    link.style.textDecoration = 'none';
                    link.style.display = 'block';
                    link.style.marginBottom = index < serials.length - 1 ? '2px' : '0';
                    link.onmouseover = function() { this.style.textDecoration = 'underline'; };
                    link.onmouseout = function() { this.style.textDecoration = 'none'; };
                    container.appendChild(link);
                } else {
                    // Si no encontramos el ID, crear un link que busque por nombre
                    const link = document.createElement('a');
                    link.href = '/web#model=stock.lot&view_type=list&domain=[["name","=","' + encodeURIComponent(serialTrimmed) + '"]]';
                    link.textContent = serialTrimmed;
                    link.style.color = '#007bff';
                    link.style.textDecoration = 'none';
                    link.style.display = 'block';
                    link.style.marginBottom = index < serials.length - 1 ? '2px' : '0';
                    link.onmouseover = function() { this.style.textDecoration = 'underline'; };
                    link.onmouseout = function() { this.style.textDecoration = 'none'; };
                    container.appendChild(link);
                }
            });
            
            // Reemplazar el contenido del campo
            field.innerHTML = '';
            field.appendChild(container);
            field.dataset.processed = 'true';
        });
    }
    
    function styleAssociatedSerials() {
        // Mantener compatibilidad con el código anterior si hay Many2many
        const serialFields = document.querySelectorAll('.o_list_view .o_field_many2many[name="associated_items_serials"]');
        serialFields.forEach(function(field) {
            field.style.whiteSpace = 'normal';
            field.style.lineHeight = '1.8';
            
            const containers = field.querySelectorAll('.o_field_many2many_list, .o_input_dropdown, .badge, span');
            containers.forEach(function(container) {
                const links = container.querySelectorAll('a');
                if (links.length > 1) {
                    container.style.display = 'flex';
                    container.style.flexDirection = 'column';
                    container.style.gap = '2px';
                    container.style.alignItems = 'flex-start';
                }
            });
            
            const links = field.querySelectorAll('a');
            links.forEach(function(link) {
                link.style.display = 'block';
                link.style.marginBottom = '2px';
            });
        });
        
        // Procesar los campos Char de seriales
        makeSerialsClickable();
    }
    
    function initSerials() {
        styleAssociatedSerials();
        
        // Observar cambios en el DOM
        if (window.MutationObserver) {
            const observer = new MutationObserver(function() {
                styleAssociatedSerials();
            });
            
            if (document.body) {
                observer.observe(document.body, {
                    childList: true,
                    subtree: true
                });
            }
        }
        
        // Ejecutar con delays para asegurar que los campos estén renderizados
        setTimeout(styleAssociatedSerials, 300);
        setTimeout(styleAssociatedSerials, 800);
        setTimeout(styleAssociatedSerials, 1500);
        setTimeout(makeSerialsClickable, 500);
        setTimeout(makeSerialsClickable, 1000);
        setTimeout(makeSerialsClickable, 2000);
    }
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initSerials);
    } else {
        initSerials();
    }
})();

// Función para mostrar/ocultar columnas de elementos asociados dinámicamente
(function() {
    'use strict';
    
    function toggleAssociatedColumns() {
        // Buscar la tabla de elementos asociados
        const listView = document.querySelector('.o_list_view');
        if (!listView) {
            return;
        }
        
        // Buscar las columnas "Tiene asociado" y "Serial" (de elementos asociados)
        // Intentar múltiples selectores porque Odoo puede usar diferentes atributos
        const summaryColumn = listView.querySelector('th[data-name="associated_items_summary"]') || 
                             listView.querySelector('th:has([name="associated_items_summary"])') ||
                             Array.from(listView.querySelectorAll('th')).find(th => {
                                 const field = th.querySelector('[name="associated_items_summary"]');
                                 return field !== null;
                             });
        
        const serialsColumn = listView.querySelector('th[data-name="associated_items_serials"]') ||
                             listView.querySelector('th:has([name="associated_items_serials"])') ||
                             Array.from(listView.querySelectorAll('th')).find(th => {
                                 const field = th.querySelector('[name="associated_items_serials"]');
                                 return field !== null;
                             });
        
        if (!summaryColumn || !serialsColumn) {
            // Si no encontramos las columnas, puede que aún no se hayan renderizado
            return;
        }
        
        // Buscar todas las filas de la tabla
        const rows = listView.querySelectorAll('tbody tr');
        let hasAnyAssociatedItems = false;
        
        // Verificar si alguna fila tiene elementos asociados
        rows.forEach(function(row) {
            const summaryCell = row.querySelector('td[data-name="associated_items_summary"]') ||
                              row.querySelector('td:has([name="associated_items_summary"])') ||
                              Array.from(row.querySelectorAll('td')).find(td => {
                                  const field = td.querySelector('[name="associated_items_summary"]');
                                  return field !== null;
                              });
            
            const serialsCell = row.querySelector('td[data-name="associated_items_serials"]') ||
                              row.querySelector('td:has([name="associated_items_serials"])') ||
                              Array.from(row.querySelectorAll('td')).find(td => {
                                  const field = td.querySelector('[name="associated_items_serials"]');
                                  return field !== null;
                              });
            
            if (summaryCell && (summaryCell.textContent.trim() || summaryCell.querySelector('a'))) {
                hasAnyAssociatedItems = true;
            }
            if (serialsCell && (serialsCell.textContent.trim() || serialsCell.querySelector('a'))) {
                hasAnyAssociatedItems = true;
            }
        });
        
        // Mostrar u ocultar columnas según si hay elementos asociados
        if (hasAnyAssociatedItems) {
            summaryColumn.style.display = '';
            serialsColumn.style.display = '';
            // Mostrar las celdas también
            rows.forEach(function(row) {
                const summaryCell = row.querySelector('td[data-name="associated_items_summary"]') ||
                                  row.querySelector('td:has([name="associated_items_summary"])');
                const serialsCell = row.querySelector('td[data-name="associated_items_serials"]') ||
                                  row.querySelector('td:has([name="associated_items_serials"])');
                if (summaryCell) summaryCell.style.display = '';
                if (serialsCell) serialsCell.style.display = '';
            });
        } else {
            // NO ocultar las columnas, solo dejarlas visibles pero vacías
            // summaryColumn.style.display = 'none';
            // serialsColumn.style.display = 'none';
        }
    }
    
    function initColumnToggle() {
        toggleAssociatedColumns();
        
        // Observar cambios en el DOM
        if (window.MutationObserver) {
            const observer = new MutationObserver(function() {
                toggleAssociatedColumns();
            });
            
            if (document.body) {
                observer.observe(document.body, {
                    childList: true,
                    subtree: true
                });
            }
        }
        
        // Ejecutar con delays para asegurar que la tabla esté renderizada
        setTimeout(toggleAssociatedColumns, 300);
        setTimeout(toggleAssociatedColumns, 800);
        setTimeout(toggleAssociatedColumns, 1500);
    }
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initColumnToggle);
    } else {
        initColumnToggle();
    }
})();
