# خطة الموديولات وقاعدة البيانات

## مبدأ التنفيذ

نحافظ على محرك SaaS والتجهيز والاشتراكات والديموهات الحالي، ونضيف طبقة ClickBuild 3 مستقلة تدريجيًا. لا يُعاد بناء Core provisioning أثناء إعادة تصميم الموقع إلا لإصلاح عيب موثق ومختبر.

## الموديولات الحالية التي تبقى

- `saas_core`, `saas_subscription`, `saas_billing`, `saas_payment`.
- `saas_tenant_manager`, `saas_portal`, `saas_external_server`.
- `saas_demo_management`, `saas_demo_seed`, `saas_restaurant_demo`.
- `saas_monitoring`, `saas_security`, `saas_notifications`, `saas_reporting`.
- `saas_knowledge`, `saas_marketplace`, `saas_marketing` بعد توسعتها.
- `saas_website` يبقى أثناء الترحيل ثم تُنقل مسؤولياته إلى طبقة واجهة ومحتوى أوضح.

## الموديولات المقترحة

### `clickbuild_website_core`

- Design tokens وLayout وMega Menu وCTA وSEO hooks.
- إدارة ترتيب أقسام الصفحة الرئيسية وحالات النشر.

### `clickbuild_content`

Models مترجمة وقابلة للإدارة:

- `clickbuild.solution`
- `clickbuild.industry` و`clickbuild.industry.challenge`
- `clickbuild.application` و`clickbuild.application.group`
- `clickbuild.service`
- `clickbuild.integration` وحالة التكامل.
- `clickbuild.faq`, `clickbuild.content.block`, `clickbuild.cta`, `clickbuild.media`.

العلاقات الأساسية:

- Sector ↔ Applications: Many2many.
- Sector ↔ Demo Template: Many2one/Many2many.
- Sector ↔ Packages: Many2many.
- Solution ↔ Applications/Industries: Many2many.
- Integration ↔ Industries/Applications: Many2many.

### `clickbuild_sales_tools`

- Pricing Configurator، Business Solution Builder وأدوات ROI/Readiness/Requirements.
- Rules قابلة للإدارة بدل أسعار مكتوبة في JavaScript.
- حفظ Draft محليًا، وإنشاء Lead فقط بعد Consent صريح.

Models:

- `clickbuild.assessment`, `clickbuild.assessment.answer`.
- `clickbuild.recommendation.rule`, `clickbuild.pricing.rule`.
- `clickbuild.implementation.estimate.rule`.
- `clickbuild.tool.definition`, `clickbuild.tool.submission`.

### `clickbuild_crm_bridge`

- يعتمد على `crm`, `utm`, `calendar`, `mail`.
- يربط `saas.website.lead` وطلبات الديمو بـ`crm.lead` دون حذف السجلات الأصلية.
- Pipeline: New → Qualified → Demo Requested → Demo Delivered → Quotation → Negotiation → Won/Lost.
- Automations ورسائل تأكيد ومهام متابعة، مع Opt-in وUnsubscribe.

### `clickbuild_demo_hub`

- يوسع `saas_demo_management` ولا يكرر منطق التجهيز.
- Catalog عام للديموهات، صور وفيديو وتطبيقات وفلترة.
- فصل بيانات العرض العامة عن الطلبات وبيانات الدخول.

### `clickbuild_knowledge_seo`

- يوسع `saas_knowledge` بمحتوى SEO وTOC وFAQ وكاتب ووقت قراءة وتاريخ تحديث وروابط داخلية.
- Models للمقارنات، Case Studies، Examples، Guides، Templates وVideos.
- JSON-LD، Sitemap ديناميكي وRedirect Registry.

### `clickbuild_analytics`

- Event taxonomy وConsent وUTM attribution.
- استيراد/عرض المؤشرات بعد تزويد بيانات GA/GSC/Clarity.
- لا تُخزن المفاتيح داخل Git.

## توسيع البيانات الحالية

### الباقات

يظل `saas.plan` مصدر السعر والفوترة. نضيف `clickbuild.package` كطبقة تسويقية تربط عدة Plans بدل تغيير الأكواد المستخدمة في الاشتراكات.

الحقول:

- الاسم التسويقي: البداية، النمو، الأعمال، المؤسسات.
- الجمهور، الحد الأدنى، التطبيقات، التنفيذ، التدريب، الدعم والاستضافة.
- روابط Plans الداخلية Community/Enterprise.
- ترتيب، نشر، Badge، CTA ومصفوفة مقارنة.

سياسة الفوترة المعتمدة: **سنوية فقط، بلا خصم؛ السنوي = الشهري × 12**.

### Leads وCRM

خطة ترحيل بلا فقدان:

1. تثبيت CRM في Staging.
2. إضافة `crm_lead_id` إلى `saas.website.lead` و`saas.demo.request`.
3. Backfill idempotent بالبريد/الهاتف والمصدر والتاريخ.
4. حفظ UTM Source/Medium/Campaign/Term/Content وLanding/Referrer وFirst/Last touch.
5. اختبار الصلاحيات وعدم كشف البيانات للمستخدم العام.
6. عدم حذف سجلات Leads القديمة بعد الربط.

### المحتوى المكتوب في Python

يُنقل `APPLICATIONS`, `INDUSTRIES`, `SERVICES` من `content_catalog.py` إلى Models عبر Migration idempotent:

- يحافظ على Slug الحالي.
- يضيف External ID ثابتًا.
- لا يستبدل محتوى عدله المدير لاحقًا عند Upgrade.
- يدعم ترجمة الحقول داخل Odoo.

## فهارس مقترحة

- Unique على Slug + Website.
- Index على `active`, `published`, `sequence`, `category_id`.
- Index مركب على Lead source + create_date وUTM + create_date.
- Index على Assessment token + state + expiry.
- Index على Demo sector + state + create_date.
- Index على Redirect old_path.

لا تُضاف الفهارس قبل `EXPLAIN ANALYZE` على Staging بحجم قريب من الإنتاج.

## التكاملات

| التكامل | الحالة الحالية | قرار العرض |
|---|---|---|
| Telegram Demo Approval | موجود | الحفاظ والاختبار. |
| WhatsApp Demo Delivery | الكود موجود والإعداد مؤجل | لا يدّعى أنه متاح قبل Meta Approval واختبار Template. |
| SMTP | موجود | مراجعة SPF/DKIM/DMARC والتتبع. |
| بوابات الدفع | Providers القياسية Disabled | لا تعرض وسيلة كمتاحة قبل تفعيلها واختبارها. |
| ZATCA | Localization موجودة | صياغة دقيقة بلا ادعاء اعتماد رسمي. |
| HungerStation/Jahez/Noon Food | غير مثبتة كتكامل عام | «تحت الدراسة» أو «تكامل مخصص». |
| GA/Search Console/Clarity | غير مربوط | ينتظر البيانات وConsent. |
| Booking | رحلة عامة غير موجودة | استخدام Appointments أو تكامل معتمد. |

## حماية الأسرار

- لا توكنات أو كلمات مرور في XML/Python/Git.
- مفاتيح `ir.config_parameter` الحساسة لصلاحية Super Admin مع تشفير/Vault عند الإمكان.
- كشف كلمة مرور عميل يكون لمرة واحدة ويسجل Audit.
- Staging يستخدم مفاتيح Sandbox مختلفة عن الإنتاج.
