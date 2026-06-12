# خطة إضافة Odoo 19 Enterprise إلى منصة ClickBuild

> **الحالة:** خطة فقط — لا تنفيذ بعد.
> **آخر تحديث:** 2026-06-11
> **التقدير الإجمالي:** 4-6 أسابيع (يعتمد على الحصول على Partner Agreement)
> **Baseline snapshot:** `clickbuild-snapshot-20260611-182929`

---

## 1. الملخّص التنفيذي

نسمح للعملاء باختيار **Community** (الحالي، مجاني الترخيص) أو **Enterprise** (تجاري، رسوم/مستخدم لـ Odoo SA + هامش لنا) أثناء التسجيل. كل tenant يعمل على binary مناسب لإصداره، مع routing تلقائي عبر nginx ولا تغيير في الـ subdomain pattern للعميل.

**المخرجات الرئيسية:**
1. حقل `edition` على `saas.plan` و `saas.tenant`
2. خطط Premium جديدة (Enterprise tier) في الـ pricing
3. Container ثاني `odoo_saas_enterprise` بـ image الـ Enterprise
4. provisioner ذكي يختار الـ image حسب الـ edition
5. nginx routing مزدوج
6. UI: edition selector + badge + license management
7. تكامل فاتورة Odoo SA (manual في البداية، automated لاحقاً)

---

## 2. المتطلبات القانونية والتجارية (Pre-flight)

### 2.1 الاتفاق مع Odoo SA

أحد المسارين فقط — تختار واحد:

| المسار | الوصف | المناسب لـ |
|---|---|---|
| **Hosting Provider Agreement** | Odoo يبيع للعميل مباشرة، أنت بس تشغّل الـ hosting | ابتداء سريع، لا cash flow risk، هامش أقل |
| **Standard Partner (Silver/Gold)** | أنت تبيع باسمك، تدفع لـ Odoo بعد خصم Partner (15-25%) | تحكّم كامل، فواتيرك، هامش أعلى |

**الإجراءات:**
- تواصل مع `partners@odoo.com` (الإقليم Middle East)
- توقّع الاتفاق (~2-4 أسابيع عادة)
- استلم الـ Partner credentials + Enterprise binary access

### 2.2 الحصول على Enterprise binary

بعد الاتفاق، 3 طرق للحصول على الكود:

1. **Docker Hub رسمي (إن أتاحه Odoo لشركتك):** `odoo/odoo:19-enterprise`
2. **Build من المصدر:** Clone الـ private repo `github.com/odoo/enterprise` + Community + بناء image داخلي
3. **PyPI / wheels:** أقل شيوعاً

**التوصية:** Build داخلي → docker image باسمك (`clickbuild/odoo-enterprise:19`) — يحمي مصدر الـ binary ويسمح بـ customization.

### 2.3 ZATCA Phase 2 على Enterprise

- Community يستعمل `l10n_sa_edi` (community + OCA)
- Enterprise يستعمل `l10n_sa_edi` + `l10n_sa_edi_phase_2` (proprietary)
- يجب التحقق من `enterprise/l10n_sa_*` متاح وخالٍ من bugs في الإصدار اللي راح نستعمله

---

## 3. قرارات معمارية (Architecture Decisions)

### ADR-001: One container per edition

**القرار:** نشغّل container منفصل لكل edition:
- `odoo_saas_app` (Community، موجود حالياً)
- `odoo_saas_enterprise_app` (جديد)

**البدائل المرفوضة:**
- ❌ نفس الـ container مع addons_path يجمع الاثنين → خطر licensing (كل DB يقدر يثبّت enterprise modules)
- ❌ container لكل tenant → استهلاك موارد غير قابل للتطوير

**التبعات:**
- ✅ فصل قانوني واضح (Community DBs ما تشوفش enterprise binary)
- ✅ شهادات SSL ما تتغيرش (نفس الـ subdomain)
- ⚠️ نحتاج ~+1.5 GB RAM إضافية للـ enterprise container
- ⚠️ كل cron يعمل مرتين (cron لكل container) — مش مشكلة لو الـ DBs مفصولة

### ADR-002: nginx upstreams مزدوجة

**القرار:** نضيف upstream ثاني وروتنغ بناءً على tenant.edition.

```nginx
upstream odoo_community  { server odoo:8069; }
upstream odoo_enterprise { server odoo_ent:8069; }

map $http_host $odoo_backend {
    ~^(?<sub>[^.]+)\.odoo\.clickbulid\.com$  odoo_community;  # سيكون lookup ديناميكي
    default                                  odoo_community;
}
```

**التحدي:** nginx ما يستطيعش يقرأ DB ليعرف edition الـ tenant. الحلول:
1. **Per-tenant nginx block:** الـ provisioner يكتب الـ tenant block مع upstream مناسب (موجود حالياً للـ SSL، نوسّعه)
2. **Lua / OpenResty:** lookup ديناميكي (overkill)

**اخترنا 1** — يتسق مع الـ pattern الحالي للـ per-tenant SSL.

### ADR-003: الـ DB لا تتغيّر — الإصدار ينعكس بس على الـ binary

**القرار:** نفس الـ PostgreSQL، نفس الـ schema، الفرق فقط في الـ Odoo image اللي يخدم الـ requests + الـ enterprise modules المثبّتة.

**التبعات:**
- ✅ مفيش double-tier للـ Postgres
- ✅ سهل ترقية Community → Enterprise (نفس الـ DB، تثبيت enterprise modules)
- ⚠️ لو عميل Community عمل أبستريد لـ Enterprise، الـ container الـ Community ما يقدرش يخدمه (لازم routing يتحدّث)

### ADR-004: الـ Provisioning يتم محلياً (لا FastAPI bridge بعد)

نستمر على نفس الـ pattern الحالي (sweeper + provision_tenant_cert.sh) ونوسّعه ليقبل edition argument.

---

## 4. خطة التنفيذ على مراحل

### Phase A — Scaffolding (يومان، بدون Enterprise binary)

**الهدف:** نبني كل الـ infrastructure (DB fields, UI, routing) بدون ما نشغّل Enterprise container فعلياً. لو الـ Partner Agreement اتأخر، المنصة لسه شغّالة.

| # | المهمة | الملف | وقت |
|---|---|---|---|
| A.1 | إضافة `edition` على `saas.plan` | `addons/saas_core/models/saas_plan.py` | 30 د |
| A.2 | إضافة `edition` على `saas.tenant` (related من plan) | `addons/saas_core/models/saas_tenant.py` | 20 د |
| A.3 | حقول config: `enterprise_image`, `enterprise_addons_path`, `enterprise_partner_code` | `addons/saas_core/models/saas_config.py` | 20 د |
| A.4 | Plans seed: Premium tiers جديدة (Starter EE, Business EE, Enterprise EE) | `addons/saas_core/data/saas_plan_data.xml` | 30 د |
| A.5 | UI: filter جديد "By Edition" في tenants list | `addons/saas_core/views/saas_tenant_views_extend.xml` | 20 د |
| A.6 | UI: badge على tenant form (Community / Enterprise) | نفس الـ file | 15 د |
| A.7 | Migration script: backfill existing tenants → `edition='community'` | `addons/saas_core/migrations/19.0.2.0.0/post-edition.py` | 30 د |
| A.8 | اختبار: signup عميل جديد، يختار خطة Community → kayfa الـ flow الحالي ينجح | manual | 30 د |

**التحقق:** كل الـ tests القديمة تنجح + الـ UI يعرض `Edition` على الـ tenants القديمة كـ "Community".

### Phase B — Pricing & Signup (يوم واحد)

**الهدف:** العميل في `/pricing` يشوف tab/toggle بين Community و Enterprise.

| # | المهمة | الملف |
|---|---|---|
| B.1 | Pricing page: toggle "Community / Enterprise" يصفّي الـ plans | `addons/saas_website/views/page_pricing.xml` |
| B.2 | Signup form: لو الـ plan = Enterprise → tooltip + استمارة "company size" إضافية | `addons/saas_website/views/page_signup.xml` |
| B.3 | Pricing FAQ تحدث: 2 سؤال جديد عن Enterprise | نفس الـ pricing page |
| B.4 | Homepage hero يضيف badge "Now with Enterprise" (اختياري) | `page_home.xml` |

### Phase C — Enterprise container (يوم، يتطلب Enterprise binary)

> ⛔ **توقّف هنا حتى يصلك الـ Enterprise binary من Odoo SA**

| # | المهمة | الملف |
|---|---|---|
| C.1 | إعداد private docker image: `clickbuild/odoo-enterprise:19` (Dockerfile) | `docker/enterprise/Dockerfile` |
| C.2 | docker-compose.yml يضيف service `odoo_ent` بنفس الـ Postgres + filestore منفصل | `/opt/odoo-saas/docker-compose.yml` |
| C.3 | enterprise odoo.conf — addons_path يجمع `community + enterprise + extra-addons` | `/opt/odoo-saas/config/odoo-enterprise.conf` |
| C.4 | Mount: `/opt/odoo-saas/addons` كـ `/mnt/extra-addons` لكلا الـ containers | نفس الـ compose |
| C.5 | تشغيل أول اختبار: `docker exec odoo_saas_enterprise_app odoo --list-addons \| grep -E 'helpdesk\|studio'` | بعد التشغيل |

**التحقق:**
- Container واحد إضافي up & running
- يجاوب على `nginx -> odoo_ent:8069` بـ HTTP 200
- يحتوي modules: `studio`, `helpdesk`, `field_service`, `subscriptions`, `marketing_automation`, `documents`, `sign`, `mrp_plm`, `quality`, etc.

### Phase D — Provisioning logic (يومان)

**الهدف:** العميل الجديد يختار خطة Enterprise → الـ sweeper يعمل DB + يثبّت modules صحيحة + nginx routing.

| # | المهمة | الملف |
|---|---|---|
| D.1 | `_queue_local_provision` يضيف `edition` في الـ JSON payload | `addons/saas_core/services/provisioning_bridge.py` |
| D.2 | `saas-tenant-provisioner.sh` يستخدم env var `SAAS_EDITION` ويختار الـ container | `scripts/install_tenant_provisioner.sh` |
| D.3 | الـ provisioner ينقل ملف `enterprise.lock` للـ filestore الخاص بالـ tenant عند Enterprise | نفس الـ script |
| D.4 | nginx tenant template: `proxy_pass` ديناميكي بناءً على flag | `scripts/nginx_tenant_template.conf` (نضيف placeholder `__BACKEND__`) |
| D.5 | `provision_tenant_cert.sh` يعمل sed على `__BACKEND__` بقيمة `odoo_backend` أو `odoo_ent_backend` | `scripts/provision_tenant_cert.sh` |
| D.6 | اختبار E2E: signup tenant بـ Enterprise plan → DB created → modules studio + helpdesk مثبّتة → login ينجح | manual |

### Phase E — Billing & License tracking (3 أيام)

**الهدف:** نتتبّع رسوم Odoo SA لكل tenant Enterprise ونحدّث الـ pricing الفعلية.

| # | المهمة | الملف |
|---|---|---|
| E.1 | حقل `enterprise_license_cost_per_user` على الـ plan | `saas_core/models/saas_plan.py` |
| E.2 | حقل `enterprise_license_key` على الـ tenant (encrypted) | `saas_core/models/saas_tenant.py` |
| E.3 | الـ invoice يحسب: `(plan_price + license_cost_per_user × users) × edition_multiplier` | `addons/saas_billing/services/invoice_service.py` |
| E.4 | تقرير شهري: Enterprise tenants count × users × license cost = ما يجب دفعه لـ Odoo SA | `addons/saas_billing/reports/enterprise_license_report.py` |
| E.5 | UI: Portal يعرض "Your Edition: Enterprise" + Renewal date + License count | `addons/saas_portal/views/portal_subscription.xml` |

### Phase F — Migration path (يوم)

**الهدف:** عميل Community حالي يقدر يترقّى لـ Enterprise بدون فقدان بيانات.

| # | المهمة | الملف |
|---|---|---|
| F.1 | UI: زر "Upgrade to Enterprise" على portal subscription page | `addons/saas_portal/...` |
| F.2 | Service: `SubscriptionService.upgrade_to_enterprise(tenant)` | `addons/saas_subscription/services/subscription_service.py` |
| F.3 | Sweeper command جديد: `migrate_tenant_to_enterprise.sh` يعمل:<br/>1) Update tenant.edition = enterprise<br/>2) `nginx-tenants/<sub>.conf` يحدّث upstream<br/>3) `docker exec odoo_saas_enterprise_app odoo -d <sub> -i studio,helpdesk,...` | `scripts/migrate_tenant_to_enterprise.sh` |
| F.4 | اختبار: tenant `tahaqoq` (Community) → upgrade → يخدم من enterprise container | manual |

### Phase G — Monitoring + Docs (يوم)

| # | المهمة |
|---|---|
| G.1 | Health check للـ enterprise container (`saas_monitoring`) |
| G.2 | Metrics: عدد Community vs Enterprise tenants, total monthly Enterprise license cost |
| G.3 | Internal runbook: كيف نضيف tenant Enterprise يدوياً (Emergency) |
| G.4 | Customer docs: ترقية، الفرق، الميزات الإضافية في Enterprise |

---

## 5. جرد التغييرات حسب الملف (Change Inventory)

### ملفات جديدة تماماً

```
docker/enterprise/Dockerfile                                 # build the EE image
docker/enterprise/.dockerignore
addons/saas_core/migrations/19.0.2.0.0/post-edition.py        # backfill existing tenants
addons/saas_billing/reports/enterprise_license_report.py
addons/saas_billing/views/enterprise_license_report_views.xml
scripts/migrate_tenant_to_enterprise.sh
docs/ENTERPRISE_ROLLOUT_PLAN.md                              # هذا الملف
docs/ENTERPRISE_RUNBOOK.md                                   # كيف نشغّل/نوقف الـ EE container
docs/CUSTOMER_UPGRADE_GUIDE.md                               # دليل العميل
```

### ملفات يتم تعديلها

```
addons/saas_core/__manifest__.py                              # version bump 19.0.2.0.0
addons/saas_core/models/saas_plan.py                          # +edition, +license_cost_per_user
addons/saas_core/models/saas_tenant.py                        # +edition (related from plan)
addons/saas_core/models/saas_config.py                        # +enterprise_image, +partner_code
addons/saas_core/services/provisioning_bridge.py              # edition in payload
addons/saas_core/views/saas_tenant_views_extend.xml           # +Edition filter, +badge
addons/saas_core/data/saas_plan_data.xml                      # +3 Enterprise plans
addons/saas_website/views/page_pricing.xml                    # +toggle Community/Enterprise
addons/saas_website/views/page_signup.xml                     # +Enterprise tooltip
addons/saas_subscription/services/subscription_service.py     # +upgrade_to_enterprise
addons/saas_billing/services/invoice_service.py               # +license cost calc
addons/saas_portal/views/portal_subscription_templates.xml    # +edition badge + upgrade button
scripts/install_tenant_provisioner.sh                         # SAAS_EDITION env var
scripts/provision_tenant_cert.sh                              # __BACKEND__ placeholder
scripts/nginx_tenant_template.conf                            # __BACKEND__ placeholder

/opt/odoo-saas/docker-compose.yml                             # +odoo_ent service
/opt/odoo-saas/config/odoo-enterprise.conf                    # جديد
```

---

## 6. سجل المخاطر (Risk Register)

| # | المخاطرة | الاحتمالية | الأثر | التخفيف |
|---|---|---|---|---|
| R1 | Partner Agreement يتأخر >6 أسابيع | متوسطة | عالٍ | نكمل Phase A+B بدون الـ binary، نضع `enterprise` plans كـ "Coming soon" |
| R2 | Enterprise binary حجمه ~3 GB يبطّئ deploys | عالية | متوسط | Image داخلي + cache layer + multi-stage build |
| R3 | tenant Community يثبّت enterprise module بالغلط | منخفضة | عالٍ | record rules + Odoo licensing check يرفضها تلقائياً |
| R4 | Migration Community→Enterprise يكسر بيانات | منخفضة | عالٍ | snapshot قبل الـ migration + dry-run في staging |
| R5 | حساب license cost خاطئ → خسارة مالية | متوسطة | عالٍ | تقرير يومي تلقائي يقارن users فعلياً مع invoice |
| R6 | EE container يستهلك RAM أكتر من اللازم | متوسطة | متوسط | limits على docker + monitoring + autoscale لاحقاً |
| R7 | عميل يلغي Enterprise، نحتاج downgrade | متوسطة | متوسط | sweeper جديد لإلغاء installation الـ EE modules + routing رجوع |
| R8 | شركات منافسة تنسخ الـ pricing | منخفضة | منخفض | (مش technical) |

---

## 7. تقدير التكلفة

### تكلفة لمرة واحدة

| البند | المبلغ |
|---|---|
| Partner Agreement (deposit/setup) | تختلف، عادة $0-5000 |
| Build & test time (4-6 أسابيع × عملي) | استثمار وقتك |
| **الإجمالي:** | يعتمد على الـ Agreement |

### تكلفة شهرية متكررة

| البند | المبلغ |
|---|---|
| EE container RAM (1.5 GB) | يندمج مع السيرفر الحالي |
| Odoo SA license لكل tenant (~$31.10/user × users) | يُحمَّل على العميل |
| Margin: 15-25% (لو Standard Partner) | إيراد لك |

### مثال: 10 عملاء Enterprise بـ 5 مستخدمين كل واحد

```
Odoo SA license: 10 × 5 × $31.10 = $1,555/شهر
Your retail price (40% markup):    $2,177/شهر
Your margin:                       $622/شهر
```

---

## 8. خطة Rollback

في حال فشل Phase C-G وتحتاج ترجع للوضع الحالي:

```bash
# على السيرفر — استخدم snapshot الحالي:
cd /opt/backups/snapshots/20260611-182929
./restore.sh --yes-i-understand

# تأكيد:
docker ps | grep odoo_ent  # يجب أن يكون فارغاً
curl https://odoo.clickbulid.com/web/login -I  # 200
```

أو لو فشلت Phase A/B فقط (ما لمسناش الـ docker-compose):
```bash
cd "C:\Users\user\odoo sas"
git revert <last-commit>   # لو git
# أو يدوياً:
Expand-Archive backups/source-20260611-182929.zip -DestinationPath . -Force
```

---

## 9. معايير القبول (Acceptance Criteria)

نعتبر الـ rollout مكتمل لما:

- [ ] عميل جديد يقدر يختار Community أو Enterprise في `/pricing`
- [ ] `/get-started/enterprise-pro` يعمل signup ينتهي بـ Enterprise tenant
- [ ] الـ tenant Enterprise يخدم على `<sub>.odoo.clickbulid.com` من الـ EE container
- [ ] modules: `studio`, `helpdesk`, `field_service`, `subscriptions` مثبّتة وتعمل
- [ ] الفاتورة الشهرية تحسب license cost صحيح
- [ ] tenant Community يقدر يترقّى لـ Enterprise بـ click واحد + ما يفقدش بيانات
- [ ] tenant Enterprise يقدر ينزل لـ Community (مع warning لفقدان بيانات modules حصرية)
- [ ] reports/monitoring تعرض الفرق بين الـ editions
- [ ] التوثيق (3 markdown files) منشور
- [ ] snapshot جديد يُؤخذ بعد الـ rollout: `clickbuild-enterprise-launch-<date>.tar.gz`

---

## 10. أسئلة مفتوحة (تحتاج قرارك)

| # | السؤال | خياراتك | توصيتي |
|---|---|---|---|
| Q1 | Hosting Provider أم Standard Partner؟ | A أو B | **Hosting** للبداية، نحوّل لـ Standard لاحقاً |
| Q2 | نسعّر Enterprise بالـ markup الثابت أم cost-plus؟ | 25% markup vs $X لكل user | **25% markup** أبسط للعميل |
| Q3 | نسمح بـ trial Enterprise مجاني؟ | نعم (نتحمّل cost) / لا | **لا** — Enterprise مدفوع من اليوم الأول |
| Q4 | نخلّي Enterprise قابل للاختيار في `/get-started` أم بـ contact-sales فقط؟ | open signup vs sales-led | **Sales-led أولاً** — يضمن compliance |
| Q5 | الـ EE image: docker hub الرسمي أم نبنيه؟ | رسمي / داخلي | **داخلي** — لو Odoo سمح |
| Q6 | نضيف Enterprise على الـ master DB (`odoo`) برضو، أم Community بس؟ | نعم / لا | **لا** — ادمن المنصة لازم يستخدم Community |

---

## 11. الـ Timeline المقترَح

```
الأسبوع 1: التواصل مع Odoo Partner Team + توقيع
الأسبوع 2: Phase A (Scaffolding) + Phase B (Pricing UI)
الأسبوع 3-4: انتظار Partner Agreement يكتمل
الأسبوع 4: Phase C (EE container setup)
الأسبوع 5: Phase D (Provisioning) + Phase E (Billing)
الأسبوع 6: Phase F (Migration) + Phase G (Docs) + UAT
الأسبوع 7: Soft-launch لـ 2-3 عملاء beta
الأسبوع 8: Public launch
```

---

## 12. الخطوة التالية المباشرة

**لما تكون جاهز للبدء:**

1. أرسل لـ partners@odoo.com:
   > نحن ClickBuild، منصة SaaS عاملة على Odoo 19 Community في السعودية/الخليج. لدينا عملاء فعليين ونرغب في تقديم Enterprise tier. نريد مناقشة Hosting Provider Agreement.

2. بعد ما يردّوا، قلّي وأبدأ في تنفيذ Phase A + B (يومان عمل) — حتى لو Agreement لسه ما اكتمل.

3. لما يصل الـ Enterprise binary، أبدأ في Phase C-G.

---

> **ملاحظة:** هذه الخطة فقط. لا أبدأ تنفيذ أي phase حتى تقول "ابدأ Phase X".
