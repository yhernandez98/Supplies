/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { Many2XAutocomplete } from "@web/views/fields/relational_utils";

const _addSearchMoreSuggestion = Many2XAutocomplete.prototype.addSearchMoreSuggestion;
const _onSearchMore = Many2XAutocomplete.prototype.onSearchMore;

function isDeliveryRouteWizardContext(context) {
    return Boolean(context && context.delivery_route_wizard_id);
}

patch(Many2XAutocomplete.prototype, {
    addSearchMoreSuggestion(params) {
        if (isDeliveryRouteWizardContext(this.props.context)) {
            return false;
        }
        return _addSearchMoreSuggestion.call(this, params);
    },
    async onSearchMore(request) {
        if (isDeliveryRouteWizardContext(this.props.context)) {
            this.env.services.notification.add(
                _t(
                    "Escriba en el campo para buscar. En Procesar Ruta no se usa el listado completo de productos."
                ),
                { type: "info" }
            );
            return;
        }
        return _onSearchMore.call(this, request);
    },
});
