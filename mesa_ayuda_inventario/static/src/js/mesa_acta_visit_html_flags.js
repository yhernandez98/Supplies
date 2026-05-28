/** @odoo-module **/

import { registry } from "@web/core/registry";

const FLAG_ACTIVE_STYLE =
    "display:inline-block;margin:0 6px 6px 0;padding:6px 12px;border-radius:999px;" +
    "border:1px solid #3da572;background:#d8f0e3;color:#1a4d32;font-size:0.82rem;" +
    "font-weight:700;cursor:pointer;user-select:none;";
const FLAG_IDLE_STYLE =
    "display:inline-block;margin:0 6px 6px 0;padding:6px 12px;border-radius:999px;" +
    "border:1px solid #b8e5cc;background:#ffffff;color:#2d7d57;font-size:0.82rem;" +
    "font-weight:600;cursor:pointer;user-select:none;";

function mesaActaSyncFlagButtonStyle(btn) {
    const active = btn.getAttribute("data-mesa-acta-flag-active") === "1";
    btn.classList.toggle("mesa-acta-flag-btn--active", active);
    btn.setAttribute("aria-pressed", active ? "true" : "false");
    btn.style.cssText = active ? FLAG_ACTIVE_STYLE : FLAG_IDLE_STYLE;
}

function mesaActaBindFlagButtons(root) {
    if (!root || root.dataset.mesaActaFlagsBound === "1") {
        return;
    }
    const host =
        root.closest(".mesa_visit_acta_tab") ||
        root.closest(".o_field_html") ||
        root.closest(".o_field_widget");
    if (!host) {
        return;
    }
    root.dataset.mesaActaFlagsBound = "1";
    const onClick = (ev) => {
        const btn = ev.target.closest(".mesa-acta-flag-btn[data-mesa-acta-flag]");
        if (!btn || !root.contains(btn)) {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        const next = btn.getAttribute("data-mesa-acta-flag-active") === "1" ? "0" : "1";
        btn.setAttribute("data-mesa-acta-flag-active", next);
        mesaActaSyncFlagButtonStyle(btn);
    };
    root.addEventListener("click", onClick);
    root.addEventListener("keydown", (ev) => {
        if (ev.key !== "Enter" && ev.key !== " ") {
            return;
        }
        const btn = ev.target.closest(".mesa-acta-flag-btn[data-mesa-acta-flag]");
        if (!btn || !root.contains(btn)) {
            return;
        }
        ev.preventDefault();
        btn.click();
    });
    root.querySelectorAll(".mesa-acta-flag-btn[data-mesa-acta-flag]").forEach(mesaActaSyncFlagButtonStyle);
}

function mesaActaScanFlagContainers(doc) {
    doc.querySelectorAll(".mesa-acta-realizado-flags[data-mesa-acta-flags]").forEach(mesaActaBindFlagButtons);
}

function mesaActaVisitHtmlFlagsSetup() {
    const run = () => mesaActaScanFlagContainers(document);
    run();
    const observer = new MutationObserver(() => run());
    observer.observe(document.body, { childList: true, subtree: true });
}

registry.category("services").add("mesa_acta_visit_html_flags", {
    start() {
        mesaActaVisitHtmlFlagsSetup();
    },
});
