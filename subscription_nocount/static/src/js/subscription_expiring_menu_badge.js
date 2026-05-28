/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";

/** Menús donde se muestra el badge: raíz «Suscripciones» (visible sin desplegar) e ítem «Suscripciones a Vencer». */
const MENU_XMLIDS = [
    "subscription_nocount.menu_subscription_root",
    "subscription_nocount.menu_subscription_expiring",
];
const BADGE_CLASS = "subscription-expiring-menu-badge";
const REFRESH_MS = 60000;

function findExpiringMenuNodes() {
    const nodes = new Set();
    for (const xmlid of MENU_XMLIDS) {
        const leaf = xmlid.split(".").pop();
        document
            .querySelectorAll(
                `[data-menu-xmlid="${xmlid}"], [data-menu-xmlid$=".${leaf}"]`
            )
            .forEach((el) => nodes.add(el));
    }
    if (nodes.size) {
        return Array.from(nodes);
    }

    return Array.from(document.querySelectorAll("a, span, div")).filter((el) => {
        const text = (el.textContent || "").trim();
        return text === "Suscripciones a Vencer";
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

async function fetchExpiringCount() {
    try {
        return await rpc("/web/dataset/call_kw/subscription.subscription/subscription_expiring_count", {
            model: "subscription.subscription",
            method: "subscription_expiring_count",
            args: [],
            kwargs: {},
        });
    } catch (error) {
        return 0;
    }
}

async function updateMenuBadge() {
    const count = await fetchExpiringCount();
    const menuNodes = findExpiringMenuNodes();
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
