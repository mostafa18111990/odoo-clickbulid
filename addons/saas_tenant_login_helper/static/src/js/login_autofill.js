/**
 * SaaS tenant login pre-fill.
 *
 * The signup success page on clickbulid.com sends new customers here with:
 *   - URL hash:   #login=<email>            (clear, never reaches server)
 *   - clipboard:  <password>                (auto-copied right before redirect)
 *
 * On /web/login we:
 *   1. Parse the hash, fill the email field.
 *   2. Drop the hash from the URL so it doesn't linger in browser history.
 *   3. Show a "password already copied — just paste" banner next to the
 *      password field for ~10 seconds, then fade out.
 */
(function () {
    'use strict';

    function init() {
        // Only act on the login page so we don't interfere with /web normal flow.
        var path = window.location.pathname || '';
        if (path.indexOf('/web/login') !== 0 && path !== '/web') return;

        var hash = window.location.hash || '';
        if (!hash || hash.indexOf('login=') === -1) return;

        // Parse "login=<email>" out of the hash.
        var params = {};
        hash.replace(/^#/, '').split('&').forEach(function (kv) {
            var idx = kv.indexOf('=');
            if (idx === -1) return;
            params[kv.slice(0, idx)] = decodeURIComponent(kv.slice(idx + 1));
        });
        var email = params.login;
        if (!email) return;

        var loginField = document.querySelector('input[name="login"]');
        if (loginField) {
            loginField.value = email;
            loginField.dispatchEvent(new Event('input', {bubbles: true}));
            var pwdField = document.querySelector('input[name="password"]');
            if (pwdField) pwdField.focus();
        }

        try {
            history.replaceState(null, '', path + window.location.search);
        } catch (e) {}

        showPasteBanner();
    }

    function showPasteBanner() {
        var pwdField = document.querySelector('input[name="password"]');
        if (!pwdField) return;
        var banner = document.createElement('div');
        banner.className = 'cb-login-paste-banner';
        var isAr = /ar/i.test(document.documentElement.lang || '') ||
                   document.dir === 'rtl';
        banner.innerHTML = isAr
            ? '<i class="fa fa-clipboard"></i>' +
              ' كلمة المرور موجودة في الحافظة — اضغط <kbd>Ctrl+V</kbd> داخل الحقل أعلاه.'
            : '<i class="fa fa-clipboard"></i>' +
              ' Password is in your clipboard — paste it (<kbd>Ctrl+V</kbd>) above.';
        var parent = pwdField.closest('.form-group') || pwdField.parentNode;
        if (parent) {
            parent.appendChild(banner);
            setTimeout(function () {
                banner.classList.add('cb-fading');
                setTimeout(function () { banner.remove(); }, 800);
            }, 10000);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
