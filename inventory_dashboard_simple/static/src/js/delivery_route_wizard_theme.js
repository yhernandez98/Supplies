/** Marca el diálogo del wizard «Procesar Ruta» para aplicar tema Aqua (Odoo 19). */
(function () {
    'use strict';

    var DIALOG_MARK = 'o_route_trigger_wizard_dialog';
    var FORM_MARK = 'o_route_trigger_wizard';

    function markDialogs() {
        document.querySelectorAll('.' + FORM_MARK).forEach(function (formRoot) {
            var dialog = formRoot.closest(
                '.o_dialog, .modal, [class*="Dialog"], [class*="dialog"]'
            );
            if (dialog) {
                dialog.classList.add(DIALOG_MARK);
            }
        });
        document.querySelectorAll('.' + DIALOG_MARK).forEach(function (dialog) {
            if (!dialog.querySelector('.' + FORM_MARK)) {
                dialog.classList.remove(DIALOG_MARK);
            }
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
