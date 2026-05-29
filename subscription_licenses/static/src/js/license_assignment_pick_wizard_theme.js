/** Tema azul pastel: wizard «Agregar Asignación» y alertas de cupo/licencias (Odoo 19). */
(function () {
    'use strict';

    var DIALOG_MARK = 'o_license_assignment_pick_wizard_dialog';
    var FORM_MARK = 'o_license_assignment_pick_wizard';
    var CAPACITY_ALERT_MARK = 'o_license_capacity_alert_dialog';

    function isLicenseCapacityAlert(dialogEl) {
        if (!dialogEl || dialogEl.querySelector('.' + FORM_MARK)) {
            return false;
        }
        var text = (dialogEl.textContent || '').replace(/\s+/g, ' ').trim();
        if (!text) {
            return false;
        }
        if (text.indexOf('No hay licencias disponibles') !== -1) {
            return true;
        }
        if (text.indexOf('Sin licencias disponibles') !== -1) {
            return true;
        }
        return (
            text.indexOf('Contratadas:') !== -1 &&
            text.indexOf('En uso:') !== -1 &&
            text.indexOf('Disponibles:') !== -1 &&
            (text.indexOf('Licencia:') !== -1 || text.indexOf('Cliente:') !== -1)
        );
    }

    function enhanceCapacityAlert(dialog) {
        if (dialog.dataset.licenseCapacityStyled === '1') {
            return;
        }
        var body = dialog.querySelector(
            '.modal-body, .o_dialog_body, main, .o_content'
        );
        if (body) {
            body.classList.add('o_license_capacity_alert_body');
        }
        dialog.dataset.licenseCapacityStyled = '1';
    }

    function markPickWizardDialogs() {
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
                delete dialog.dataset.licenseCapacityStyled;
            }
        });
    }

    function markCapacityAlertDialogs() {
        document
            .querySelectorAll(
                '.o_dialog, .modal, [class*="Dialog"], [class*="dialog"]'
            )
            .forEach(function (dialog) {
                if (isLicenseCapacityAlert(dialog)) {
                    dialog.classList.add(CAPACITY_ALERT_MARK);
                    enhanceCapacityAlert(dialog);
                } else if (dialog.classList.contains(CAPACITY_ALERT_MARK)) {
                    dialog.classList.remove(CAPACITY_ALERT_MARK);
                    delete dialog.dataset.licenseCapacityStyled;
                }
            });
    }

    function markDialogs() {
        markPickWizardDialogs();
        markCapacityAlertDialogs();
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
