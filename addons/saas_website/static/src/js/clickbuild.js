/* ClickBuild — frontend behaviors
 * Scroll reveal and annual-only pricing. Plain DOM, no Odoo bundles.
 */
(function () {
    'use strict';

    document.documentElement.classList.add('cb-has-reveal');

    // ---- Scroll reveal -----------------------------------------------------
    function revealAll(els) {
        els.forEach(function (e) { e.classList.add('is-visible'); });
    }
    function initReveal() {
        var els = document.querySelectorAll('[data-cb-reveal]');
        if (!els.length) { return; }
        // Belt-and-suspenders: if anything below throws, or IntersectionObserver
        // is unavailable, just show everything. Content must never stay hidden.
        if (!window.IntersectionObserver) { revealAll(els); return; }
        try {
            var io = new IntersectionObserver(function (entries) {
                entries.forEach(function (entry) {
                    if (entry.isIntersecting) {
                        entry.target.classList.add('is-visible');
                        io.unobserve(entry.target);
                    }
                });
            }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
            els.forEach(function (e) { io.observe(e); });
        } catch (err) {
            revealAll(els);
        }
        // Final safety net: whatever happens, ensure nothing is left hidden
        // shortly after load (mirrors the CSS @keyframes failsafe).
        window.addEventListener('load', function () {
            setTimeout(function () { revealAll(els); }, 1600);
        });
    }

    // Legacy toggle support remains for old cached markup. Current pricing
    // pages expose annual billing only and do not render these controls.
    function initBillingToggle() {
        var toggles = document.querySelectorAll('.cb-billing-toggle');
        if (!toggles.length) return;
        toggles.forEach(function (group) {
            var buttons = group.querySelectorAll('button[data-billing]');
            buttons.forEach(function (btn) {
                btn.addEventListener('click', function () {
                    var mode = btn.getAttribute('data-billing');
                    buttons.forEach(function (b) { b.classList.toggle('active', b === btn); });
                    applyBilling(mode);
                });
            });
        });

        function applyBilling(mode) {
            document.querySelectorAll('.js-price').forEach(function (el) {
                var v = el.getAttribute('data-' + mode);
                if (v != null) el.textContent = v;
            });
            document.querySelectorAll('.js-price-suffix').forEach(function (el) {
                var t = el.getAttribute('data-' + mode + '-text');
                if (t != null) el.textContent = t;
            });
            document.querySelectorAll('.js-yearly-note').forEach(function (el) {
                el.style.display = (mode === 'yearly') ? '' : 'none';
            });
        }
    }

    function initTierPricing() {
        var root = document.querySelector('[data-tier-calculator]');
        if (!root) return;
        var users = root.querySelector('#pricingUserCount');
        var edition = 'community';
        function format(value) {
            return Number(value).toLocaleString(document.documentElement.lang.indexOf('ar') === 0 ? 'ar-SA' : 'en-US', {
                minimumFractionDigits: Number.isInteger(value) ? 0 : 2,
                maximumFractionDigits: 2
            });
        }
        function update() {
            var count = Math.max(1, Math.min(500, parseInt(users.value || '1', 10)));
            users.value = count;
            var tier = count === 1 ? 1 : (count === 2 ? 2 : 3);
            var rates = edition === 'enterprise' ? {1: 399, 2: 349, 3: 299} : {1: 299, 2: 249, 3: 199};
            var unit = rates[tier];
            var monthly = count * unit;
            // Annual-only billing: the customer sees the monthly price and is
            // invoiced once a year for exactly 12 x monthly.
            var annual = monthly * 12;
            root.querySelector('[data-tier-unit]').textContent = format(unit);
            root.querySelector('[data-tier-monthly]').textContent = format(monthly);
            root.querySelector('[data-tier-total]').textContent = format(annual);
            root.querySelector('[data-tier-cta]').href = '/get-started?edition=' + edition + '&users=' + count + '&billing=yearly';
        }
        root.querySelectorAll('[data-tier-edition]').forEach(function(btn) { btn.addEventListener('click', function() { edition = btn.dataset.tierEdition; root.querySelectorAll('[data-tier-edition]').forEach(function(b) { b.classList.toggle('active', b === btn); }); update(); }); });
        root.querySelector('[data-tier-minus]').addEventListener('click', function() { users.value = Math.max(1, parseInt(users.value || '1', 10) - 1); update(); });
        root.querySelector('[data-tier-plus]').addEventListener('click', function() { users.value = Math.min(500, parseInt(users.value || '1', 10) + 1); update(); });
        users.addEventListener('input', update);
        update();
    }

    function initSignupTierPricing() {
        var form = document.getElementById('signupForm');
        if (!form) return;
        var users = document.getElementById('userCountInput');
        var editionInput = document.getElementById('signupEdition');
        var cycleInput = document.getElementById('signupBilling');
        var select = document.getElementById('plan_id_select');
        var box = document.getElementById('seatPriceBox');
        function update() {
            var count = Math.max(1, Math.min(500, parseInt(users.value || '1', 10)));
            users.value = count;
            var tier = count === 1 ? 1 : (count === 2 ? 2 : 3);
            var enterprise = editionInput.value === 'enterprise';
            var rates = enterprise ? {1:399,2:349,3:299} : {1:299,2:249,3:199};
            var codes = enterprise ? {1:'starter_ee',2:'business_ee',3:'enterprise_ee'} : {1:'starter',2:'business',3:'enterprise'};
            Array.from(select.options).forEach(function(opt) { if ((opt.dataset.code || '').toLowerCase() === codes[tier]) opt.selected = true; });
            var monthly = count * rates[tier];
            // Annual-only billing: monthly price shown, invoiced 12 x monthly.
            var yearly = monthly * 12;
            if (cycleInput) cycleInput.value = 'yearly';
            var isAr = (document.documentElement.lang || '').indexOf('ar') === 0;
            var fmt = function (n) { return n.toLocaleString(isAr ? 'ar-SA' : 'en-US', {maximumFractionDigits: 2}); };
            box.textContent = isAr
                ? (fmt(monthly) + ' ريال/شهر — تُفوتر سنوياً: ' + fmt(yearly) + ' ريال')
                : (fmt(monthly) + ' SAR/month — billed annually: ' + fmt(yearly) + ' SAR');
        }
        form.querySelectorAll('.signup-edition-card').forEach(function(card) { card.addEventListener('click', function() { editionInput.value = card.dataset.edition; setTimeout(update, 0); }); });
        users.addEventListener('input', function() { setTimeout(update, 0); });
        form.addEventListener('submit', update);
        // The inline signup compatibility script may calculate the legacy
        // monthly summary after DOMContentLoaded. Re-apply the canonical quote
        // once the page is fully loaded so a preselected yearly cycle is shown
        // correctly without requiring another click.
        window.addEventListener('load', update, { once: true });
        setTimeout(update, 250);
    }

    // ---- Boot --------------------------------------------------------------
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            initReveal();
            initBillingToggle();
            initTierPricing();
            initSignupTierPricing();
        });
    } else {
        initReveal();
        initBillingToggle();
        initTierPricing();
        initSignupTierPricing();
    }
})();
