/** @odoo-module **/

// Script para agregar clase CSS específica SOLO a la vista de inventario de CRM
// Detecta la vista por la combinación única de columnas: "Hardware Asociado" + "Placa de Inventario"

(function() {
    'use strict';
    
    function addInventoryViewClass() {
        // Buscar todas las vistas de lista de stock.quant
        const stockQuantActions = document.querySelectorAll('.o_action_manager .o_action[data-res-model="stock.quant"]');
        
        stockQuantActions.forEach(action => {
            const listView = action.querySelector('.o_list_view');
            if (!listView) return;
            
            // Obtener todos los headers de la tabla
            const headers = Array.from(listView.querySelectorAll('thead th'));
            const headerTexts = headers.map(th => th.textContent.trim().toLowerCase());
            
            // Verificar que tenga AMBAS columnas específicas de nuestra vista
            const hasHardwareField = headerTexts.some(text => text.includes('hardware asociado'));
            const hasInventoryPlate = headerTexts.some(text => text.includes('placa de inventario'));
            
            // Esta combinación es única de nuestra vista
            if (hasHardwareField && hasInventoryPlate) {
                const actionContainer = action.closest('.o_action_manager');
                if (actionContainer) {
                    actionContainer.classList.add('crm-inventory-view');
                    // También agregar a la acción misma por si acaso
                    action.classList.add('crm-inventory-view');
                }
            } else {
                // Remover la clase si no cumple
                const actionContainer = action.closest('.o_action_manager');
                if (actionContainer) {
                    actionContainer.classList.remove('crm-inventory-view');
                }
                action.classList.remove('crm-inventory-view');
            }
        });
    }
    
    // Función para ejecutar cuando sea necesario
    function checkAndApply() {
        setTimeout(addInventoryViewClass, 100);
        setTimeout(addInventoryViewClass, 500);
        setTimeout(addInventoryViewClass, 1000);
        setTimeout(addInventoryViewClass, 2000);
    }
    
    // Ejecutar cuando el DOM esté listo
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', checkAndApply);
    } else {
        checkAndApply();
    }
    
    // Usar MutationObserver para detectar cambios dinámicos en el DOM
    let observer = null;
    
    function startObserver() {
        if (observer) return;
        
        observer = new MutationObserver(function(mutations) {
            let shouldCheck = false;
            mutations.forEach(function(mutation) {
                if (mutation.addedNodes.length > 0 || mutation.type === 'attributes') {
                    shouldCheck = true;
                }
            });
            if (shouldCheck) {
                setTimeout(addInventoryViewClass, 300);
            }
        });
        
        if (document.body) {
            observer.observe(document.body, {
                childList: true,
                subtree: true,
                attributes: true,
                attributeFilter: ['class']
            });
        }
    }
    
    if (document.body) {
        startObserver();
    } else {
        document.addEventListener('DOMContentLoaded', startObserver);
    }
    
    // También ejecutar periódicamente
    setInterval(addInventoryViewClass, 2000);
})();

