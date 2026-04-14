/** Clase en body para vistas del hub laboratorio (control panel, mismos modelos que el tema pastel). */
(function () {
    'use strict';

    var LAB_HUB_MODELS = [
        'component.lab.assignment',
        'component.lab.assign.tech.wizard',
        'component.lab.tech.return.wizard',
        'component.lab.responsible.return.wizard',
        'component.transfer.wizard',
    ];

    function getHashParams() {
        var hash = window.location.hash.slice(1) || '';
        var params = {};
        hash.split('&').forEach(function (part) {
            var pair = part.split('=');
            if (pair[0]) {
                params[pair[0]] = decodeURIComponent((pair[1] || '').replace(/\+/g, ' '));
            }
        });
        return params;
    }

    function updateBodyClass() {
        var params = getHashParams();
        var model = params.model || '';
        var isLabHub = LAB_HUB_MODELS.indexOf(model) !== -1;
        if (isLabHub) {
            document.body.classList.add('o_inventory_lab_hub_view');
        } else {
            document.body.classList.remove('o_inventory_lab_hub_view');
        }
    }

    function run() {
        updateBodyClass();
        window.addEventListener('hashchange', updateBodyClass);
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
