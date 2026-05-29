/** Tema Aqua — Procesar Ruta, albaranes E1–E4, wizard validación y Facturación (Odoo 19).
 *  El modal del serial mantiene el tema pastel de product_suppiles. */
(function () {
    'use strict';

    var FORM_MARKS = [
        'o_route_trigger_wizard',
        'o_delivery_route_picking',
        'o_delivery_route_validation_wizard',
    ];
    var DIALOG_SUFFIX = '_dialog';

    function markDialogs() {
        FORM_MARKS.forEach(function (formMark) {
            document.querySelectorAll('.' + formMark).forEach(function (formRoot) {
                var dialog = formRoot.closest(
                    '.o_dialog, .modal, [class*="Dialog"], [class*="dialog"]'
                );
                if (dialog) {
                    dialog.classList.add(formMark + DIALOG_SUFFIX);
                    dialog.classList.add('o_route_trigger_wizard_dialog');
                }
                var formView = formRoot.closest('.o_form_view');
                if (formView && formMark === 'o_delivery_route_picking') {
                    formView.classList.add('o_delivery_route_picking');
                }
            });
        });
        document.querySelectorAll('.o_list_view.o_delivery_route_billing_list').forEach(function (list) {
            var controller = list.closest('.o_action_manager, .o_view_controller');
            if (controller) {
                controller.classList.add('o_delivery_route_billing_action');
            }
        });
        FORM_MARKS.forEach(function (formMark) {
            document.querySelectorAll('.' + formMark + DIALOG_SUFFIX).forEach(function (dialog) {
                if (!dialog.querySelector('.' + formMark)) {
                    dialog.classList.remove(formMark + DIALOG_SUFFIX);
                }
            });
        });
    }

    function run() {
        markDialogs();
        if (window.MutationObserver) {
            var obs = new MutationObserver(markDialogs);
            obs.observe(document.body, { childList: true, subtree: true });
        }
        setInterval(markDialogs, 800);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', run);
    } else {
        run();
    }
})();
