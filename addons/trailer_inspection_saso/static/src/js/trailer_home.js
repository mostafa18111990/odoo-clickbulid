/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Landing screen for the inspection app. It carries the operator's own
 * company name and logo so the workspace reads as their system, not as a
 * generic Odoo app, and every tile opens the matching filtered list.
 */
export class TrailerHome extends Component {
    static template = "trailer_inspection_saso.TrailerHome";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ loaded: false, company: {}, kpi: {}, standard: "" });

        onWillStart(async () => {
            const data = await this.orm.call("trailer.inspection", "get_home_overview", []);
            Object.assign(this.state, data, { loaded: true });
        });
    }

    get logoUrl() {
        const id = this.state.company.id;
        return id ? `/web/image/res.company/${id}/logo/120x120` : null;
    }

    openInspections(domain, name) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: name || _t("Inspections"),
            res_model: "trailer.inspection",
            views: [
                [false, "kanban"],
                [false, "list"],
                [false, "form"],
            ],
            domain: domain || [],
            target: "current",
        });
    }

    openAction(xmlId) {
        this.action.doAction(xmlId);
    }

    newInspection() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("New Inspection"),
            res_model: "trailer.inspection",
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("trailer_inspection_home", TrailerHome);
