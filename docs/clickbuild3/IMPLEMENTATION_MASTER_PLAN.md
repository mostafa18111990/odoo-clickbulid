# الخطة التنفيذية الرئيسية — ClickBuild 3

## بوابات الحوكمة

1. لا تعديل إنتاج قبل Backup خاص بالمرحلة ونجاح QA على Staging.
2. كل مرحلة لها Branch/Tag/Backup/Restore check وموافقة.
3. لا بيانات إنتاج شخصية في Staging؛ تستخدم نسخة Neutralized.
4. لا DNS أو مفاتيح Analytics/Payments/WhatsApp قبل موافقة منفصلة.
5. لا قصص أو أرقام أو شعارات غير موثقة.

## المرحلة 0 — الأمان وStaging (P0)

المدة التقديرية: 2–4 أيام عمل.

- حجب Database Manager/Selector وMetrics عن الإنترنت.
- إصلاح `/error` وNoindex للصفحات التقنية.
- مراجعة plaintext credentials وUpgrade shell commands ووضع خطة ترحيل آمنة.
- إنشاء Staging مطابق من قاعدة Neutralized وFilestore منفصل.
- تعطيل البريد والمدفوعات والرسائل الخارجية وCron المؤثر في Staging.
- تفعيل Basic Auth أو IP allowlist للمراجعة قبل العرض العام.

معيار الخروج: اختبار أمني سلبي، لا تأثير على Provisioning، وStaging يعرض الصفحة العامة عبر HTTPS.

## المرحلة 1 — الأساس والواجهة

المدة التقديرية: 2–3 أسابيع.

- `clickbuild_website_core` و`clickbuild_content`.
- Design System وMega Menu وHomepage.
- ترحيل Apps/Industries/Services من Python إلى Models.
- إعادة بناء Pricing حسب الاحتياج مع سياسة سنوية فقط وبلا خصم.
- تثبيت CRM وبناء Bridge للنماذج وUTM/Consent.
- SEO تقني أساسي: Metadata، Schema، Sitemap، Robots، Hreflang، Redirects.
- تحسين Mobile وAssets وLCP.

معيار الخروج: الصفحة الرئيسية والأسعار والقائمة والنماذج تعمل بالعربية والإنجليزية على Staging، والحسابات تطابق قاعدة البيانات.

## المرحلة 2 — القطاعات الأساسية

المدة التقديرية: 2–3 أسابيع.

بالترتيب:

1. المطاعم والمقاهي.
2. العيادات والأسنان.
3. المقاولات.
4. التجزئة ونقاط البيع.
5. التصنيع.
6. المستودعات والتوزيع.
7. شركات الخدمات.

ثم العقارات والصيانة والتجارة الإلكترونية والتعليم والنقل.

معيار الخروج لكل قطاع: قالب 14 قسمًا، تطبيقات ودورة عمل وتقارير وتكاملات بحالات صادقة، ديمو Enterprise واختبارات SEO/RTL/LTR.

## المرحلة 3 — أدوات البيع

المدة التقديرية: 2–3 أسابيع.

- Pricing Configurator.
- Business Solution Builder.
- Demo Hub والفلاتر.
- Booking وRequest Quote.
- CRM Automation والمتابعة بعد الديمو والعرض.
- WhatsApp/Email sharing بعد تفعيل Consent وTemplates المعتمدة.

معيار الخروج: كل نتيجة قابلة لإعادة الحساب من Rules الإدارة، وكل إرسال معتمد يصل إلى CRM بمصدره وUTM.

## المرحلة 4 — المعرفة والمقارنات والأدوات

المدة التقديرية: 2–3 أسابيع لأول دفعة.

- Knowledge Hub وArticle schema.
- المقارنات الست بعد بحث وتوثيق وتاريخ تحديث.
- Guides/Templates/Videos.
- أدوات ERP cost، ROI، readiness، digital maturity ومتطلبات ERP.
- Case Study template وExamples الافتراضية منفصلة.

معيار الخروج: لا محتوى آلي ضعيف أو ادعاء غير موثق، وروابط داخلية وCTA لكل صفحة.

## المرحلة 5 — Marketplace والتحليلات

المدة التقديرية: 1–2 أسبوعين.

- الحزم والتكاملات والإضافات والقوالب ولوحات المؤشرات والخدمات.
- GA/GSC/Clarity بعد استلام الصلاحيات والموافقة على سياسة Consent.
- Dashboard داخل Odoo لمؤشرات Leads/UTM/Demos/Quotes.

## خطة SEO

### Technical

- HTTPS ثابت لكل Canonical/OG/Hreflang/Sitemap/Robots.
- Sitemap indexes حسب النوع واللغة، مع مولد Slugs الديناميكية.
- Robots يستبعد account, portal, API, status, success, search, database manager.
- Metadata models قابلة للإدارة مع Defaults صحيحة.
- Schema: Organization, SoftwareApplication, Product/Offer عند صحة السعر، FAQ, Article, Video, Breadcrumb وLocalBusiness عند توفر عنوان فعلي موثق.
- Redirect Registry مع فحص chains/loops.
- 404 monitor وواجهة 404 مفيدة تعيد 404 فعلية.

### Content

- Cluster لكل قطاع: Pillar + Applications + Demo + FAQ + Guide + Comparison/Tool.
- لا تكرار نصوص القطاعات؛ لكل صفحة تحديات ودورة عمل وتقارير مختلفة.
- الكاتب والمراجع وتاريخ التحديث للمحتوى الحساس.
- لا Product Schema على باقة لا يمكن شراؤها فعليًا أو سعرها تقديري.

## خطة المحتوى الأولية

أولوية أول 20 أصل محتوى:

- 7 صفحات قطاعات أساسية.
- 5 صفحات حلول إدارية.
- دليل اختيار ERP في السعودية.
- دليل تنفيذ Odoo.
- دليل الفاتورة الإلكترونية وOdoo بصياغة غير قانونية/اعتمادية.
- مقارنة موضوعية أولى بعد التحقق من المصادر.
- 2 أداة: حاسبة التكلفة واختبار الجاهزية.
- صفحة منهجية التنفيذ.
- صفحة ملكية البيانات والأمان.

## خطة الاختبار

### Automated

- Odoo Savepoint/HttpCase للموديلات والصلاحيات والمحاسبات.
- Unit tests لـPricing/Recommendation Rules.
- Route tests للعربية والإنجليزية وCanonical/Hreflang/Schema.
- Contract tests لتكامل CRM وديمو وTelegram/WhatsApp Sandbox.
- Migration tests على نسخة anonymized.
- Broken links وSitemap وRedirect tests.

### Security

- ACL/Record Rules للمحتوى وCRM والديمو.
- CSRF/Captcha/Rate limit/Upload validation.
- منع IDOR في Status/Portal/API.
- منع Database Manager/Metrics خارجيًا.
- Secret scan وDependency scan وSecurity headers.

### Visual/Accessibility

- 360×800، 390×844، 430×932، Tablet، 1366×768، 1920×1080.
- Arabic RTL وEnglish LTR.
- Keyboard, focus, screen-reader landmarks, contrast و44px targets.
- Visual regression للصفحة الرئيسية والأسعار والقطاع والنماذج.

### Performance budgets

- Hero ≤250KB modern format قدر الإمكان.
- لا JavaScript خاص بالصفحة يُحمّل عالميًا دون حاجة.
- LCP/INP/CLS تقاس على أجهزة Mobile حقيقية أو محاكاة ثابتة.
- Cache headers وBrotli/Gzip وDB query counts.

## خطة الإطلاق

1. Backup كامل قبل النقل + checksum.
2. Freeze محتوى قصير وتصدير فرق البيانات.
3. Upgrade dry-run على Clone جديد من الإنتاج.
4. Smoke/Regression/SEO crawl/Visual approval.
5. موافقة كتابية.
6. نشر Blue/Green أو تبديل إصدار قابل للعكس، لا تعديل يدوي متناثر.
7. مراقبة 2–4 ساعات: 5xx، latency، forms، SMTP، CRM، provisioning.
8. مراقبة 24–72 ساعة للفهرسة والتحويلات والسجلات.

## قرار Rollback

Rollback فوري إذا حدث أحد الآتي:

- فشل Login أو Provisioning أو Pricing.
- فقد بيانات أو اختلاف غير مقبول في Leads/Plans/Tenants.
- ارتفاع 5xx أو أخطاء JavaScript مؤثرة.
- تعطل Forms/CRM/Email.
- خطأ Canonical/Robots يمنع الفهرسة أو يفهرس صفحات حساسة.

المرجع: `ROLLBACK_PLAN.md` والنسخة `clickbuild-production-before-redesign-2026-07-31-0843` والـTag `production-before-clickbuild-3`.

## التسليمات التشغيلية النهائية

- توثيق Architecture وModels وRoutes.
- دليل إدارة المحتوى والأسعار والقطاعات والديموهات والمقارنات.
- Runbooks للنسخ والاستعادة والنشر وRollback.
- Test report وSecurity/SEO/Performance report.
- Change log وRedirect map وData migration report.
