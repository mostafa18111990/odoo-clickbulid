/** @odoo-module **/

const TEXT = {
    ar: {
        received: ['تم استلام طلب الديمو', 'بانتظار مراجعة الإدارة.'],
        pending_review: ['الطلب قيد المراجعة', 'ستبدأ عملية التجهيز تلقائيًا بعد الموافقة.'],
        needs_info: ['نحتاج معلومات إضافية', 'سيتواصل معك فريقنا لاستكمال البيانات المطلوبة.'],
        approved: ['تمت الموافقة', 'يتم الآن وضع الديمو في قائمة التجهيز.'],
        queued: ['تمت الموافقة', 'تم إدراج بيئة Enterprise في قائمة التجهيز.'],
        provisioning: ['جارٍ تجهيز منصة أعمالك', 'نجهز قاعدة Enterprise والتطبيقات المناسبة لقطاعك.'],
        checking: ['الفحص النهائي', 'تم إنشاء القاعدة ونجري فحص HTTPS والحماية قبل عرض البيانات.'],
        ready: ['منصة أعمالك التجريبية جاهزة', 'احفظ بيانات الدخول ثم افتح الديمو من الزر أدناه.'],
        rejected: ['تعذر قبول الطلب', 'يمكنك التواصل معنا لمعرفة التفاصيل أو تقديم طلب جديد.'],
        failed: ['تعذر إكمال التجهيز', 'تم تسجيل المشكلة وسيراجعها فريق الإدارة.'],
        expired: ['انتهت صلاحية الديمو', 'تواصل معنا إذا كنت تحتاج إلى تمديد الفترة التجريبية.'],
        converted: ['تم تحويل الديمو', 'تم تحويل الطلب إلى اشتراك.'],
        processing: ['جارٍ معالجة الطلب', 'يتم تحديث حالة الطلب تلقائيًا.'],
    },
    en: {
        received: ['Demo request received', 'Waiting for administration review.'],
        pending_review: ['Request under review', 'Preparation will start automatically after approval.'],
        needs_info: ['More information needed', 'Our team will contact you for the required details.'],
        approved: ['Request approved', 'Your demo is being added to the preparation queue.'],
        queued: ['Request approved', 'Your Enterprise environment is queued for preparation.'],
        provisioning: ['Preparing your business platform', 'We are configuring Enterprise and your industry applications.'],
        checking: ['Final readiness check', 'The database is ready; HTTPS and sandbox protection are being verified.'],
        ready: ['Your demo business platform is ready', 'Save the credentials and open your demo below.'],
        rejected: ['Request not approved', 'Contact us for details or submit a new request.'],
        failed: ['Preparation could not be completed', 'The issue was recorded for administration review.'],
        expired: ['Demo expired', 'Contact us if you need an extension.'],
        converted: ['Demo converted', 'This request was converted to a subscription.'],
        processing: ['Processing request', 'The request status updates automatically.'],
    },
};

function startDemoStatus() {
    const root = document.querySelector('[data-demo-status-endpoint]');
    if (!root) {
        return;
    }
    const endpoint = root.dataset.demoStatusEndpoint;
    const lang = root.dataset.demoLang === 'en' ? 'en' : 'ar';
    const title = root.querySelector('[data-demo-status-title]');
    const message = root.querySelector('[data-demo-status-message]');
    const progress = root.querySelector('[data-demo-progress]');
    const icon = root.querySelector('[data-demo-status-icon]');
    const credentialBox = root.querySelector('[data-demo-credentials]');
    let stopped = false;

    function setText(statusCode) {
        const value = TEXT[lang][statusCode] || TEXT[lang].processing;
        title.textContent = value[0];
        message.textContent = value[1];
    }

    function revealCredentials(credentials) {
        const url = credentialBox.querySelector('[data-demo-credential="url"]');
        url.href = credentials.url;
        url.textContent = credentials.url;
        credentialBox.querySelector('[data-demo-credential="username"]').textContent = credentials.username;
        credentialBox.querySelector('[data-demo-credential="password"]').textContent = credentials.password;
        credentialBox.querySelector('[data-demo-credential="expires_at"]').textContent = credentials.expires_at || '—';
        credentialBox.querySelector('[data-demo-login]').href = credentials.url;
        credentialBox.classList.remove('d-none');
        icon.innerHTML = '<i class="fa fa-check"></i>';
    }

    async function refresh() {
        if (stopped) {
            return;
        }
        try {
            const response = await fetch(endpoint, {
                credentials: 'same-origin',
                cache: 'no-store',
                headers: {'Accept': 'application/json'},
            });
            if (!response.ok) {
                stopped = response.status === 404;
                return;
            }
            const data = await response.json();
            setText(data.status_code);
            const percent = Math.max(0, Math.min(Number(data.progress) || 0, 100));
            progress.style.width = `${percent}%`;
            progress.textContent = `${percent}%`;
            if (data.ready && data.credentials) {
                revealCredentials(data.credentials);
                stopped = true;
            } else if (data.terminal) {
                stopped = true;
            }
        } catch {
            // Transient network failures are retried without exposing details.
        }
        if (!stopped) {
            window.setTimeout(refresh, 4000);
        }
    }
    refresh();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', startDemoStatus, {once: true});
} else {
    startDemoStatus();
}
