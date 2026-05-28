/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";

/** Menús con badge: Dashboard total, Pendientes y Series en varias ubicaciones. */
const MENU_MAP = {
    dashboard_total: ["inventory_dashboard_simple.menu_inventory_dashboard_simple"],
    excess_quantity: ["inventory_dashboard_simple.menu_stock_quant_excess_quantity"],
    pending_info: ["inventory_dashboard_simple.menu_stock_lot_incomplete_fields"],
    serial_multi_location: ["inventory_dashboard_simple.menu_stock_lot_serial_multi_location"],
    delivery_billing: ["inventory_dashboard_simple.menu_delivery_route_billing"],
};
const FALLBACK_TEXT = {
    dashboard_total: "Dashboard",
    excess_quantity: "Productos con cantidad > 1",
    pending_info: "Productos Pendientes de Información",
    serial_multi_location: "Series en varias ubicaciones",
    delivery_billing: "Facturación",
};
const BADGE_CLASS = "inv-pending-info-menu-badge";
/** Intervalo de refresco del número en menú (5 min). */
const REFRESH_MS = 300000;
/** Tras cambiar de pantalla (SPA). */
const HASH_DEBOUNCE_MS = 800;
/** Reintentos: el menú a veces monta después del primer paint (sin observar todo el body). */
const RETRY_DELAYS_MS = [200, 600, 1200, 2500, 5000];
/** Debounce solo sobre la barra superior (pocas mutaciones vs. lista agrupada). */
const NAV_DEBOUNCE_MS = 400;

let _pendingRpc = null;
let _lastRpcAt = 0;
const MIN_RPC_GAP_MS = 15000;

function findMenuNodes(xmlids, fallbackText) {
    const nodes = new Set();
    const nav =
        document.querySelector(".o_main_navbar") ||
        document.querySelector("header.o_navbar") ||
        document.querySelector("nav.o_navbar") ||
        document.querySelector("header");
    if (!nav) {
        return [];
    }
    const roots = [
        nav,
        ...Array.from(
            document.querySelectorAll(
                ".o-dropdown--menu, .dropdown-menu, .o_menu_sections, .o_navbar_apps_menu"
            )
        ),
    ];
    const uniqRoots = roots.filter((root, idx) => root && roots.indexOf(root) === idx);

    const normalizeMenuNode = (el) => {
        if (!el) {
            return null;
        }
        if (el.closest(".o_content, .o_control_panel")) {
            return null;
        }
        return (
            el.closest("a") ||
            el.closest("button") ||
            el.closest(".dropdown-item") ||
            el
        );
    };

    for (const xmlid of xmlids) {
        const leaf = xmlid.split(".").pop();
        uniqRoots.forEach((root) => {
            root
                .querySelectorAll(
                    `a[data-menu-xmlid="${xmlid}"], a[data-menu-xmlid$=".${leaf}"], button[data-menu-xmlid="${xmlid}"], button[data-menu-xmlid$=".${leaf}"], .dropdown-item[data-menu-xmlid="${xmlid}"], .dropdown-item[data-menu-xmlid$=".${leaf}"]`
                )
                .forEach((el) => {
                    const normalized = normalizeMenuNode(el);
                    if (normalized) {
                        nodes.add(normalized);
                    }
                });
        });
    }
    if (nodes.size) {
        return Array.from(nodes);
    }
    const fallbackNodes = [];
    uniqRoots.forEach((root) => {
        fallbackNodes.push(...Array.from(root.querySelectorAll("a, button, .dropdown-item")));
    });
    return fallbackNodes
        .filter((el) => {
            const text = (el.textContent || "").trim();
            return text === fallbackText || text.startsWith(`${fallbackText} `);
        })
        .map((el) => normalizeMenuNode(el))
        .filter((el, idx, arr) => el && arr.indexOf(el) === idx);
}

function ensureBadgeNode(menuNode) {
    let badge = menuNode.querySelector(`.${BADGE_CLASS}`);
    if (!badge) {
        badge = document.createElement("span");
        badge.className = BADGE_CLASS;
        badge.textContent = "0";
        menuNode.appendChild(badge);
    }
    return badge;
}

async function fetchBadgeCounts() {
    try {
        const result = await rpc("/web/dataset/call_kw/stock.lot/dashboard_queries_badge_counts", {
            model: "stock.lot",
            method: "dashboard_queries_badge_counts",
            args: [],
            kwargs: {},
        });
        return {
            pending_info: Number(result?.pending_info || 0),
            serial_multi_location: Number(result?.serial_multi_location || 0),
            excess_quantity: Number(result?.excess_quantity || 0),
            delivery_billing: Number(result?.delivery_billing || 0),
            dashboard_total: Number(result?.dashboard_total || 0),
        };
    } catch (error) {
        return {
            pending_info: 0,
            serial_multi_location: 0,
            excess_quantity: 0,
            delivery_billing: 0,
            dashboard_total: 0,
        };
    }
}

async function updateMenuBadge(force = false) {
    if (_pendingRpc) {
        return _pendingRpc;
    }
    const now = Date.now();
    if (!force && _lastRpcAt && now - _lastRpcAt < MIN_RPC_GAP_MS) {
        return;
    }
    _lastRpcAt = now;
    _pendingRpc = (async () => {
        try {
            const counts = await fetchBadgeCounts();
            Object.entries(MENU_MAP).forEach(([key, xmlids]) => {
                const count = Number(counts[key] || 0);
                const menuNodes = findMenuNodes(xmlids, FALLBACK_TEXT[key]);
                menuNodes.forEach((menuNode) => {
                    const badge = ensureBadgeNode(menuNode);
                    badge.textContent = String(count);
                    badge.style.display = count > 0 ? "inline-flex" : "none";
                });
            });
        } finally {
            _pendingRpc = null;
        }
    })();
    return _pendingRpc;
}

function setupHashRefresh() {
    let t = null;
    const schedule = () => {
        if (t) {
            clearTimeout(t);
        }
        t = setTimeout(() => updateMenuBadge(true), HASH_DEBOUNCE_MS);
    };
    window.addEventListener("hashchange", schedule);
}

/**
 * Observa solo la barra de navegación: cuando aparece el menú, pinta el badge.
 * No usar observer sobre document.body (las listas agrupadas mutan sin parar y disparaban RPC).
 */
function setupNavbarBadgeHook() {
    let debounceTimer = null;
    const debouncedUpdate = () => {
        if (debounceTimer) {
            clearTimeout(debounceTimer);
        }
        debounceTimer = setTimeout(() => updateMenuBadge(true), NAV_DEBOUNCE_MS);
    };

    const tryAttach = () => {
        const nav =
            document.querySelector(".o_main_navbar") ||
            document.querySelector("header.o_navbar") ||
            document.querySelector("nav.o_navbar") ||
            document.querySelector("header");
        if (!nav || nav.dataset.invPendingBadgeBound === "1") {
            return !!nav;
        }
        nav.dataset.invPendingBadgeBound = "1";
        const obs = new MutationObserver(debouncedUpdate);
        obs.observe(nav, { childList: true, subtree: true });
        debouncedUpdate();
        return true;
    };

    if (!tryAttach()) {
        const poll = setInterval(() => {
            if (tryAttach()) {
                clearInterval(poll);
            }
        }, 400);
        setTimeout(() => clearInterval(poll), 20000);
    }
}

function start() {
    updateMenuBadge(true);
    RETRY_DELAYS_MS.forEach((ms) => setTimeout(() => updateMenuBadge(true), ms));
    setupHashRefresh();
    setupNavbarBadgeHook();
    setInterval(() => updateMenuBadge(true), REFRESH_MS);
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
} else {
    start();
}
