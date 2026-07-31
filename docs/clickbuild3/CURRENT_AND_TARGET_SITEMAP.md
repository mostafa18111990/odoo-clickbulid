# خريطة الموقع الحالية والمستهدفة

## الخريطة الحالية الفعلية

### صفحات عامة

- `/` — الصفحة الرئيسية.
- `/features` — نظرة عامة للمميزات والتطبيقات.
- `/apps` — فهرس التطبيقات.
- `/apps/{slug}` — 14 صفحة تطبيق: accounting, sales, crm, purchase, inventory, point-of-sale, ecommerce, projects, employees, manufacturing, maintenance, quality, helpdesk, marketing, sign, subscriptions.
- `/industries` — فهرس القطاعات.
- `/industries/{slug}` — 11 صفحة قطاع: construction, trading-distribution, retail, restaurants-cafes, manufacturing, professional-services, real-estate, ecommerce, field-services, education, startups-smes.
- `/services` — الخدمات.
- `/pricing` — التسعير.
- `/faq` — الأسئلة الشائعة.
- `/contact` — نموذج التواصل المخصص.
- `/about` — من نحن.
- `/demo/request` — طلب ديمو Enterprise.
- `/get-started` و`/get-started/{plan}` — التسجيل وطلب إنشاء منصة.
- `/help` و`/help/{slug}` — مركز المساعدة العام.

### صفحات قانونية

- `/terms`, `/privacy`, `/dpa`, `/sla`.

### صفحات مكررة أو تقنية

- `/contactus` — نموذج Odoo القياسي، مكرر مع `/contact`.
- `/contactus-thank-you` — صفحة نجاح النموذج القياسي.
- `/website/info` — صفحة معلومات Odoo التقنية.
- `/error` — صفحة مخصصة لكنها تعيد HTTP 500.
- `/get-started/success` و`/demo/request/success` — صفحات حالة وبيانات.
- `/web/database/manager` و`/web/database/selector` — يجب حجبهما.
- `/metrics`, `/healthz`, `/readyz`, `/saas/status/api` — نقاط تشغيل لا تدخل Sitemap العام.

### النسخة الإنجليزية

Odoo يولد نسخ `/en/...` للصفحات العامة. اتجاه LTR صحيح، لكن ترجمة `/en/services` والعناوين الإنجليزية تحتاج إصلاحًا.

## مشكلة Sitemap الحالية

Sitemap المنشور يضم 19 رابطًا فقط وبصيغة HTTP. لا يضم صفحات التطبيقات والقطاعات الديناميكية، ويضم `/error` و`/website/info` وصفحات ليست مناسبة للفهرسة.

## الخريطة المستهدفة ClickBuild 3

```text
/
├── /solutions
│   ├── /solutions/finance
│   ├── /solutions/sales-crm
│   ├── /solutions/operations
│   ├── /solutions/human-resources
│   ├── /solutions/commerce
│   ├── /solutions/analytics
│   └── /solutions/{solution-slug}
├── /industries
│   ├── /industries/restaurants-cafes
│   ├── /industries/clinics-dental
│   ├── /industries/construction
│   ├── /industries/retail-pos
│   ├── /industries/manufacturing
│   ├── /industries/warehousing-distribution
│   ├── /industries/professional-services
│   ├── /industries/real-estate
│   ├── /industries/maintenance-field-service
│   ├── /industries/ecommerce
│   ├── /industries/education
│   └── /industries/transport-fleet
├── /apps
│   ├── /apps/finance/{app-slug}
│   ├── /apps/sales-service/{app-slug}
│   ├── /apps/operations/{app-slug}
│   ├── /apps/hr/{app-slug}
│   └── /apps/commerce-marketing/{app-slug}
├── /demos
│   └── /demos/{sector-slug}
├── /pricing
│   ├── /pricing/configurator
│   └── /pricing/compare
├── /solution-advisor
├── /comparisons
│   └── /comparisons/{comparison-slug}
├── /knowledge
│   ├── /knowledge/{category}
│   ├── /knowledge/{category}/{article-slug}
│   ├── /guides/{slug}
│   ├── /templates/{slug}
│   └── /videos/{slug}
├── /tools
│   └── /tools/{tool-slug}
├── /success-stories/{slug}
├── /examples/{slug}
├── /services/{service-slug}
├── /company/about
├── /company/methodology
├── /contact
├── /book-consultation
├── /request-quote
├── /faq
└── /legal/{terms|privacy|dpa|sla}
```

كل مسار عام قابل للفهرسة يملك نسخة `/en/...` مترجمة فعليًا وHreflang متبادلًا.

## مصفوفة الاحتفاظ والترحيل

| المسار الحالي | القرار | المسار المستهدف | ملاحظات |
|---|---|---|---|
| `/` | إعادة بناء | `/` | الاحتفاظ بالرابط والبيانات، تغيير ترتيب الأقسام والرسالة. |
| `/features` | دمج + 301 لاحقًا | `/solutions` | يمكن إبقاؤه مؤقتًا أثناء الترحيل. |
| `/apps` | تعديل | `/apps` | تقسيم حسب الإدارات مع Models قابلة للإدارة. |
| `/apps/{slug}` | الاحتفاظ/تحسين | نفس الرابط قدر الإمكان | الحفاظ على Slugs يمنع فقد SEO. |
| `/industries` | تعديل | `/industries` | فهرس جديد بفلترة وديمو. |
| صفحات القطاعات الحالية | إعادة بناء | نفس Slug قدر الإمكان | توسيع القالب إلى 14 قسمًا. |
| `/services` | تعديل | `/services` | نقل البيانات من Python إلى Model. |
| `/pricing` | إعادة بناء | `/pricing` | الحفاظ على محرك الأسعار السنوي الحالي. |
| `/faq` | تعديل | `/faq` | توسيع الأسئلة وإضافة FAQ Schema. |
| `/contact` | تعديل | `/contact` | ربط CRM وUTM وConsent وCaptcha. |
| `/contactus` | دمج | `/contact` | 301 بعد التحقق من الاعتمادات. |
| `/contactus-thank-you` | دمج | `/contact/thanks` | Noindex. |
| `/about` | نقل مع 301 | `/company/about` | أو إبقاء الرابط الحالي إن كان أفضل لـSEO. |
| `/demo/request` | تعديل | `/demos` أو `/demos/{sector}` | إعادة استخدام محرك الطلب الحالي. |
| `/get-started` | الاحتفاظ | `/get-started` | رحلة اشتراك، لا بديل لمستشار الحلول. |
| `/help` | فصل | `/knowledge` أو Portal Help | فصل المحتوى التسويقي عن دعم العملاء. |
| الصفحات القانونية | الاحتفاظ | الروابط الحالية أو `/legal/...` | الروابط الحالية أقل مخاطرة. |
| `/website/info` | حذف من الفهرسة | — | حجب أو Noindex. |
| `/error` | إصلاح | داخلي فقط | Sitemap=False وNoindex وحالات HTTP صحيحة. |

## قواعد URL

- العربية افتراضية بلا Prefix؛ الإنجليزية `/en`.
- Slugs ثابتة وقصيرة لتجنب مشاكل الترميز.
- لا يتغير Slug منشور دون 301 مسجل مركزيًا.
- صفحات النجاح والحالة والبحث والحساب وPortal وAPI تكون Noindex.
- Sitemap يستخدم HTTPS فقط ويشمل الصفحات الديناميكية المنشورة.
