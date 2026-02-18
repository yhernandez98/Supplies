/** Añade clase a body en vistas de subscription_licenses para aplicar tema al control panel (Nuevo, filtros). */
(function () {
    'use strict';

    var LICENSING_MODELS = [
        'license.assignment',
        'license.template',
        'license.category',
        'license.equipment',
        'license.provider.partner',
        'license.provider.stock',
        'license.trm',
        'trm.config',
        'license.report.wizard',
        'license.quantity.warning.wizard',
        'license.equipment.delete.warning.wizard',
        'license.add.multiple.warning.wizard',
        'license.equipment.add.multiple.wizard',
        'license.provider.delete.wizard',
    ];

    function getHashParams() {
        var hash = window.location.hash.slice(1) || '';
        var params = {};
        hash.split('&').forEach(function (part) {
            var pair = part.split('=');
            if (pair[0]) params[pair[0]] = decodeURIComponent((pair[1] || '').replace(/\+/g, ' '));
        });
        return params;
    }

    function updateBodyClass() {
        var params = getHashParams();
        var model = params.model || '';
        var isLicensing = LICENSING_MODELS.indexOf(model) !== -1;
        if (isLicensing) {
            document.body.classList.add('o_subscription_licenses_view');
        } else {
            document.body.classList.remove('o_subscription_licenses_view');
        }
    }

    function run() {
        updateBodyClass();
        window.addEventListener('hashchange', updateBodyClass);
        // Odoo puede cambiar la URL sin hashchange
        if (window.MutationObserver) {
            var obs = new MutationObserver(updateBodyClass);
            obs.observe(document.body, { childList: true, subtree: true });
        }
        setInterval(updateBodyClass, 1500);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', run);
    } else {
        run();
    }
})();
