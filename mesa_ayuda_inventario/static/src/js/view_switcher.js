// Script para agregar botones de cambio de vista en el Control Panel (Odoo 18)
// JavaScript vanilla - similar a dashboard_charts.js

(function() {
    'use strict';
    
    /**
     * Botones de cambio de vista en el Control Panel (Odoo 18).
     *
     * Objetivo:
     * - Botones SIEMPRE visibles (en el panel superior), no en "Acciones" y no por fila.
     * - "Agrupar por" solo debe afectar la vista Lista. En Kanban, si detectamos agrupaciones,
     *   las removemos automáticamente (solo las de Cliente/Categoría/Clase).
     *
     * Nota: evitamos dependencias OWL/patch para maximizar compatibilidad.
     */

    function isCustomerInventoryScreen() {
    // Detecta por breadcrumbs/título visibles (más robusto que depender de action id)
    const title = document.querySelector(".o_control_panel .breadcrumb, .o_control_panel .o_breadcrumb, .o_control_panel .o_cp_top .breadcrumb")?.textContent || "";
    const subTitle = document.querySelector(".o_control_panel .o_cp_top")?.textContent || "";
    const full = (title + " " + subTitle).toLowerCase();
    return full.includes("cliente supplies") || full.includes("inventario kanban") || full.includes("inventario lista");
}

function getCurrentViewType() {
    // Intenta detectar el tipo de vista actual por clases del body/contenedor
    if (document.querySelector(".o_kanban_view")) return "kanban";
    if (document.querySelector(".o_list_view")) return "list";
    return null;
}

function clickNativeSwitcher(targetType) {
    // Odoo suele renderizar el switcher con data-view-type
    const btn = document.querySelector(`.o_control_panel .o_cp_switch_buttons button[data-view-type="${targetType}"]`)
        || document.querySelector(`.o_control_panel .o_cp_switch_buttons button[data-mode="${targetType}"]`);
    if (btn) {
        btn.click();
        return true;
    }
    return false;
}

// Funciones de limpieza/aplicación de agrupación removidas - dejamos todo natural

function ensureControlPanelButtons() {
    if (!isCustomerInventoryScreen()) return;

    const cpRight = document.querySelector(".o_control_panel .o_cp_right");
    if (!cpRight) return;

    // Evitar duplicados
    if (cpRight.querySelector(".mei_view_switcher")) return;

    const wrapper = document.createElement("div");
    wrapper.className = "mei_view_switcher";
    wrapper.style.display = "flex";
    wrapper.style.gap = "8px";
    wrapper.style.alignItems = "center";

    const btnKanban = document.createElement("button");
    btnKanban.type = "button";
    btnKanban.className = "btn btn-secondary";
    btnKanban.textContent = "📋 Kanban";
    btnKanban.addEventListener("click", () => {
        clickNativeSwitcher("kanban");
    });

    const btnList = document.createElement("button");
    btnList.type = "button";
    btnList.className = "btn btn-primary";
    btnList.textContent = "📊 Lista";
    btnList.addEventListener("click", () => {
        clickNativeSwitcher("list");
    });

    wrapper.appendChild(btnKanban);
    wrapper.appendChild(btnList);

    // Insertar antes del switcher nativo (si existe)
    const native = cpRight.querySelector(".o_cp_switch_buttons");
    if (native) {
        cpRight.insertBefore(wrapper, native);
    } else {
        cpRight.prepend(wrapper);
    }
}

function boot() {
    // Solo inyectar botones cuando aparezca el control panel (sin forzar agrupaciones)
    const tick = () => {
        try {
            ensureControlPanelButtons();
        } catch (e) {
            // no romper el webclient por errores puntuales
            // eslint-disable-next-line no-console
            console.warn("mesa_ayuda_inventario view_switcher error:", e);
        }
    };

    // intentos iniciales
    setTimeout(tick, 500);
    setTimeout(tick, 1500);

    // observar cambios
    if (window.MutationObserver) {
        const obs = new MutationObserver(() => tick());
        obs.observe(document.body, { childList: true, subtree: true });
    } else {
        setInterval(tick, 1500);
    }
}

    // Inicializar cuando el DOM esté listo
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }
    
})();
