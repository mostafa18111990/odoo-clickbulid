/** @odoo-module **/

import { registry } from "@web/core/registry";

const APP_XMLID = "trailer_inspection_saso.menu_trailer_root";
const APP_CLASS = "ti-app";

/**
 * Flags the document while the inspection app is the active one, so the
 * chrome around it (navbar, breadcrumbs) can carry the system's own colours
 * instead of the generic Odoo theme. Every other app is left untouched.
 */
export const trailerAppThemeService = {
    dependencies: ["menu"],
    start(env, { menu }) {
        const apply = () => {
            const app = menu.getCurrentApp();
            document.body.classList.toggle(APP_CLASS, app?.xmlid === APP_XMLID);
        };
        env.bus.addEventListener("ACTION_MANAGER:UI-UPDATED", apply);
        env.bus.addEventListener("MENUS:APP-CHANGED", apply);
        apply();
        return {};
    },
};

registry.category("services").add("trailer_app_theme", trailerAppThemeService);
