/* ClickBuild — frontend behaviors
 * Scroll-reveal + pricing monthly/yearly toggle. Plain DOM, no Odoo bundles.
 */
(function () {
    'use strict';

    // ---- Scroll reveal -----------------------------------------------------
    function initReveal() {
        var els = document.querySelectorAll('[data-cb-reveal]');
        if (!els.length || !window.IntersectionObserver) {
            els.forEach(function (e) { e.classList.add('is-visible'); });
            return;
        }
        var io = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.add('is-visible');
                    io.unobserve(entry.target);
                }
            });
        }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
        els.forEach(function (e) { io.observe(e); });
    }

    // ---- Pricing billing toggle (monthly <-> yearly) -----------------------
    // Markup contract:
    //   <div class="cb-billing-toggle">
    //     <button data-billing="monthly" class="active">شهري</button>
    //     <button data-billing="yearly">سنوي <span class="save-badge">-15%</span></button>
    //   </div>
    //   <span class="js-price" data-monthly="299" data-yearly="2999">299</span>
    //   <span class="js-price-suffix" data-monthly-text="ريال/شهر" data-yearly-text="ريال/سنة"/>
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

    // ---- Boot --------------------------------------------------------------
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            initReveal();
            initBillingToggle();
        });
    } else {
        initReveal();
        initBillingToggle();
    }
})();
