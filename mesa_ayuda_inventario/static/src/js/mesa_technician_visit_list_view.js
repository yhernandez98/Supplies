/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";

/**
 * Lista de visitas asignadas (panel técnico): sin barra de búsqueda ni menús de
 * filtros / favoritos. El alcance lo define solo el domain de la acción.
 */
export const mesaTechnicianVisitListView = {
    ...listView,
    display: {
        controlPanel: false,
    },
};

registry.category("views").add("mesa_technician_visit_list", mesaTechnicianVisitListView);
