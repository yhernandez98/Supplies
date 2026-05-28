/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";

const MENU_XMLID = "crm_sales_supplies.menu_purchase_alert";
const BADGE_CLASS = "crm-purchase-alert-badge";
const REFRESH_MS = 60000;

function findPurchaseAlertMenuNodes() {
    const byXmlId = document.querySelectorAll(
        `[data-menu-xmlid="${MENU_XMLID}"], [data-menu-xmlid$=".menu_purchase_alert"]`
    );
    if (byXmlId.length) {
        return Array.from(byXmlId);
    }

    return Array.from(document.querySelectorAll("a, span, div")).filter((el) => {
        const text = (el.textContent || "").trim();
        return text === "Alertas Por Cotización";
    });
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

async function fetchPendingAlertsCount() {
    try {
        return await rpc("/web/dataset/call_kw/purchase.alert/search_count", {
            model: "purchase.alert",
            method: "search_count",
            args: [[["state", "in", ["pending", "purchase_created"]]]],
            kwargs: {},
        });
    } catch (error) {
        return 0;
    }
}

async function updateMenuBadge() {
    const count = await fetchPendingAlertsCount();
    const menuNodes = findPurchaseAlertMenuNodes();
    if (!menuNodes.length) {
        return;
    }

    menuNodes.forEach((menuNode) => {
        const badge = ensureBadgeNode(menuNode);
        badge.textContent = String(count);
        badge.style.display = count > 0 ? "inline-flex" : "none";
    });
}

function setupObserver() {
    const observer = new MutationObserver(() => {
        updateMenuBadge();
    });
    observer.observe(document.body, {
        childList: true,
        subtree: true,
    });
}

function start() {
    updateMenuBadge();
    setupObserver();
    setInterval(updateMenuBadge, REFRESH_MS);
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
} else {
    start();
}

