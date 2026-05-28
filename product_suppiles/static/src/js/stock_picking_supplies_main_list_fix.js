/** @odoo-module **/

/**
 * En la pestaña «Productos principales» del albarán, Odoo a veces desplaza
 * horizontalmente el contenedor de la lista al enfocar celdas o botones
 * (scrollIntoView). Eso se percibe como que la tabla «salta» hacia la izquierda.
 * Forzamos scrollLeft = 0 en los contenedores relevantes tras interacción.
 */
function _resetHorizontalScroll(scope) {
    if (!scope) {
        return;
    }
    const selectors = [
        ".o_list_table_wrapper",
        ".o_list_container",
        ".o_list_renderer",
        ".table-responsive",
    ];
    for (const sel of selectors) {
        scope.querySelectorAll(sel).forEach((el) => {
            if (el.scrollLeft) {
                el.scrollLeft = 0;
            }
        });
    }
    const form = scope.closest(".o_form_view");
    if (form) {
        form.querySelectorAll(".o_form_sheet, .o_content").forEach((el) => {
            if (el.scrollLeft) {
                el.scrollLeft = 0;
            }
        });
    }
}

function _onInteract(ev) {
    try {
        const page = ev.target && ev.target.closest && ev.target.closest(".supplies-main-products-page");
        if (!page) {
            return;
        }
        requestAnimationFrame(() => _resetHorizontalScroll(page));
    } catch (_err) {
        // Never block Odoo webclient startup/interactions for this UX fix.
    }
}

function start() {
    document.addEventListener("focusin", _onInteract, true);
    document.addEventListener("click", _onInteract, true);
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
} else {
    start();
}
