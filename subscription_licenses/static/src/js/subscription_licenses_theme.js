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
        /* Módulo Suscripciones (subscription_nocount): mismo tema visual */
        'subscription.subscription',
        'subscription.monthly.billable',
        'subscription.equipment.change.wizard',
        'subscription.cancel.wizard',
        'subscription.usage.proforma.wizard',
        'subscription.monthly.billable.wizard',
        'subscription.equipment.cost.detail.wizard',
        'subscription.subscription.usage',
        'subscription.equipment.change.history',
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

    /** Barra de desplazamiento horizontal también arriba en lista Consolidado (Proveedor). */
    function findScrollable(el) {
        if (!el || el.nodeType !== 1) return null;
        var style = window.getComputedStyle(el);
        var ox = style.overflowX || style.overflow;
        if ((ox === 'auto' || ox === 'scroll') && el.scrollWidth > el.clientWidth) {
            return el;
        }
        for (var i = 0; i < el.children.length; i++) {
            var found = findScrollable(el.children[i]);
            if (found) return found;
        }
        return null;
    }

    function setupTopScrollbar() {
        var listRoot = document.querySelector('.o_list_consolidado_top_scroll, .o_list_view.o_list_consolidado_top_scroll');
        if (!listRoot) {
            var tab = document.querySelector('[data-tab-name="report_consolidated_page"], .tab-pane[id*="report_consolidated"]');
            if (tab) listRoot = tab.querySelector('.o_list_view');
        }
        if (!listRoot) {
            var subForm = document.querySelector('form.o_license_module_form');
            if (subForm) listRoot = subForm.querySelector('.o_list_view');
        }
        if (!listRoot || listRoot.dataset.topScrollbar === '1') return;
        var scrollable = findScrollable(listRoot);
        if (!scrollable) return;
        var topBar = document.createElement('div');
        topBar.className = 'o_list_consolidado_top_scroll_bar';
        topBar.setAttribute('aria-hidden', 'true');
        topBar.style.cssText = 'overflow-x: auto; overflow-y: hidden; height: 12px; margin-bottom: 4px; max-width: 100%;';
        var inner = document.createElement('div');
        inner.style.height = '1px';
        inner.style.width = scrollable.scrollWidth + 'px';
        topBar.appendChild(inner);
        scrollable.parentNode.insertBefore(topBar, scrollable);
        listRoot.dataset.topScrollbar = '1';

        function syncFromTable() {
            topBar.scrollLeft = scrollable.scrollLeft;
        }
        function syncFromTop() {
            scrollable.scrollLeft = topBar.scrollLeft;
        }
        scrollable.addEventListener('scroll', syncFromTable);
        topBar.addEventListener('scroll', syncFromTop);
        var ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(function () {
            inner.style.width = (scrollable.scrollWidth) + 'px';
            topBar.scrollLeft = scrollable.scrollLeft;
        }) : null;
        if (ro) ro.observe(scrollable);
        syncFromTable();
    }

    function runTopScrollbar() {
        setupTopScrollbar();
        setTimeout(setupTopScrollbar, 500);
        setTimeout(setupTopScrollbar, 1500);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', run);
    } else {
        run();
    }

    document.addEventListener('DOMContentLoaded', function () {
        runTopScrollbar();
        var mo = window.MutationObserver && new MutationObserver(function () {
            runTopScrollbar();
        });
        if (mo) {
            mo.observe(document.body, { childList: true, subtree: true });
        }
    });
})();
