/**
 * Dedicated asset entry for pricing/signup releases.
 * Keeping this as a separate file changes the Odoo bundle definition, which
 * gives browsers a fresh asset URL after deployments instead of reusing an
 * older cached clickbuild.js bundle.
 */
(function () {
    'use strict';

    function refreshPreselectedBilling() {
        var form = document.getElementById('signupForm');
        var cycle = document.getElementById('signupBilling');
        if (!form || !cycle || cycle.value !== 'yearly') return;
        var yearly = form.querySelector('[data-signup-billing="yearly"]');
        if (yearly) yearly.click();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            setTimeout(refreshPreselectedBilling, 350);
        });
    } else {
        setTimeout(refreshPreselectedBilling, 350);
    }
})();
