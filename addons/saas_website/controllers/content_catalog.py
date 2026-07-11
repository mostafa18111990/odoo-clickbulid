"""Verified, reusable marketing content for ClickBuild solution pages.

Keep claims practical and implementation-focused. Product capability names are
aligned with Odoo 19's official application and documentation taxonomy; actual
availability still depends on edition, enabled applications, and configuration.
"""


def _app(slug, ar, en, ar_summary, en_summary, capabilities, outcomes, related):
    return {
        "slug": slug, "kind": "app", "title_ar": ar, "title_en": en,
        "summary_ar": ar_summary, "summary_en": en_summary,
        "capabilities": capabilities, "outcomes": outcomes, "related": related,
    }


APPLICATIONS = {
    item["slug"]: item for item in [
        _app("accounting", "المحاسبة والفوترة", "Accounting & Invoicing",
             "نظّم الفواتير والقيود والتحصيل والتقارير المالية في دورة عمل مترابطة.",
             "Connect invoices, journal entries, collections, and financial reporting.",
             ["فواتير العملاء والموردين", "القيود والتسويات البنكية", "الضرائب والتقارير المالية"],
             ["تقليل الإدخال المتكرر", "رؤية أوضح للتدفقات النقدية", "إقفال مالي أكثر تنظيمًا"],
             ["sales", "purchase", "inventory"]),
        _app("sales", "المبيعات", "Sales",
             "حوّل عروض الأسعار إلى طلبات وفواتير مع متابعة واضحة لكل مرحلة.",
             "Move quotations through orders and invoicing with a visible workflow.",
             ["عروض الأسعار وقوالب المنتجات", "طلبات البيع والتسعير", "التوقيع والدفع عند تهيئتهما"],
             ["إعداد أسرع للعروض", "تقليل فقدان المعلومات", "تنسيق أفضل مع المخزون والمحاسبة"],
             ["crm", "accounting", "inventory"]),
        _app("crm", "إدارة علاقات العملاء CRM", "CRM",
             "تابع العملاء المحتملين والفرص والأنشطة حتى إغلاق الصفقة.",
             "Track leads, opportunities, and activities through the sales pipeline.",
             ["مسار فرص مرئي", "أنشطة ومواعيد متابعة", "تقارير أداء المبيعات"],
             ["متابعة منهجية للفرص", "وضوح أولويات الفريق", "توقع أفضل للمبيعات"],
             ["sales", "marketing", "projects"]),
        _app("purchase", "المشتريات", "Purchase",
             "أدر طلبات الأسعار وأوامر الشراء والموردين ضمن دورة توريد متصلة.",
             "Manage RFQs, purchase orders, and vendors in a connected procurement flow.",
             ["طلبات عروض الأسعار", "أوامر واتفاقيات الشراء", "قوائم أسعار الموردين"],
             ["مقارنة أسهل للعروض", "ضبط أفضل للشراء", "ربط الاستلام بالفوترة"],
             ["inventory", "accounting", "manufacturing"]),
        _app("inventory", "إدارة المخزون", "Inventory",
             "راقب الكميات والحركات والمستودعات والتتبع من شاشة واحدة.",
             "Control stock, movements, warehouses, and traceability from one system.",
             ["مستودعات ومواقع متعددة", "قواعد إعادة الطلب", "الدفعات والأرقام التسلسلية والباركود"],
             ["رؤية أدق للمخزون", "تقليل النقص والتكدس", "تسريع الاستلام والتسليم"],
             ["purchase", "sales", "manufacturing"]),
        _app("point-of-sale", "نقاط البيع", "Point of Sale",
             "اربط عمليات الكاشير بالمنتجات والمخزون والمحاسبة حسب إعداد الحل.",
             "Connect checkout operations with products, inventory, and accounting.",
             ["جلسات وفواتير نقاط البيع", "منتجات وأسعار ووسائل دفع", "تكامل المخزون والمحاسبة"],
             ["خدمة أسرع عند نقطة البيع", "تحديث مركزي للبيانات", "متابعة أوضح للفروع"],
             ["inventory", "accounting", "ecommerce"]),
        _app("ecommerce", "التجارة الإلكترونية", "eCommerce",
             "أنشئ متجرًا مرتبطًا بالمنتجات والطلبات والمخزون وبيانات العملاء.",
             "Run an online store connected to products, orders, stock, and customers.",
             ["كتالوج وصفحات منتجات", "سلة وطلبات إلكترونية", "بوابات دفع وشحن عند التكامل"],
             ["قناة بيع مترابطة", "تقليل مزامنة البيانات يدويًا", "تجربة شراء موحدة"],
             ["sales", "inventory", "marketing"]),
        _app("projects", "المشاريع والمهام", "Project & Tasks",
             "خطط الأعمال ووزّع المهام وتابع الوقت والتقدم والتسليمات.",
             "Plan work, assign tasks, and track time, progress, and deliverables.",
             ["لوحات Kanban ومراحل", "مهام ومواعيد ومسؤوليات", "سجلات وقت وربط بالفوترة عند الحاجة"],
             ["وضوح المسؤوليات", "متابعة أفضل للتسليم", "ربط الجهد بالتكلفة والإيراد"],
             ["sales", "helpdesk", "employees"]),
        _app("employees", "الموارد البشرية", "Employees & HR",
             "اجمع بيانات الموظفين والإجازات والحضور والعمليات الداخلية في مكان منظم.",
             "Organize employee records, time off, attendance, and HR workflows.",
             ["ملفات الموظفين والهيكل التنظيمي", "الإجازات والحضور", "التوظيف والتقييمات بحسب التطبيقات المفعلة"],
             ["تقليل الملفات المتفرقة", "تسريع الموافقات", "رؤية أوضح لبيانات الفريق"],
             ["projects", "sign", "helpdesk"]),
        _app("manufacturing", "التصنيع", "Manufacturing",
             "خطط أوامر التصنيع والمواد ومراكز العمل واربط الإنتاج بالمخزون والجودة.",
             "Plan manufacturing orders, materials, and work centers with stock integration.",
             ["قوائم المواد وأوامر التصنيع", "مراكز العمل والتخطيط", "التكامل مع الجودة والصيانة والمخزون"],
             ["رؤية أفضل للاحتياجات", "تتبع تكلفة وتقدم الإنتاج", "تنسيق المواد والعمليات"],
             ["inventory", "quality", "maintenance"]),
        _app("maintenance", "الصيانة", "Maintenance",
             "نظّم طلبات الصيانة الوقائية والتصحيحية للمعدات ومراكز العمل.",
             "Organize preventive and corrective maintenance for equipment and work centers.",
             ["معدات وفرق صيانة", "طلبات ومراحل صيانة", "جدولة وقائية ومؤشرات"],
             ["تقليل التوقف غير المخطط", "سجل موحد للأعطال", "تنسيق أفضل لفريق الصيانة"],
             ["manufacturing", "quality", "projects"]),
        _app("quality", "الجودة", "Quality",
             "أضف نقاط فحص وتنبيهات جودة داخل عمليات التصنيع والمخزون.",
             "Add quality checks and alerts to manufacturing and inventory operations.",
             ["نقاط وضوابط فحص", "تنبيهات وإجراءات جودة", "فرق وتقارير متابعة"],
             ["اكتشاف المشكلات مبكرًا", "توثيق نتائج الفحص", "تحسين اتساق الإجراءات"],
             ["manufacturing", "inventory", "maintenance"]),
        _app("helpdesk", "خدمة العملاء", "Helpdesk",
             "استقبل طلبات العملاء ووزّعها وتابع زمن المعالجة واتفاقيات الخدمة المهيأة.",
             "Receive, assign, and track customer tickets and configured service targets.",
             ["فرق ومراحل تذاكر", "قنوات استقبال متعددة", "قاعدة معرفة واتفاقيات خدمة حسب الإعداد"],
             ["توزيع أسرع للطلبات", "رؤية أوضح للتراكم", "تواصل منظم مع العملاء"],
             ["projects", "crm", "marketing"]),
        _app("marketing", "التسويق", "Marketing",
             "خطط الحملات وتابع التفاعل واربط النتائج ببيانات العملاء والفرص.",
             "Plan campaigns, track engagement, and connect results to customers and leads.",
             ["تسويق بريدي وأتمتة بحسب التطبيقات", "شرائح وقوائم جمهور", "تتبع الحملات والروابط"],
             ["رسائل أكثر استهدافًا", "متابعة قابلة للقياس", "ربط التسويق بالمبيعات"],
             ["crm", "ecommerce", "sales"]),
        _app("sign", "التوقيع الإلكتروني", "Sign",
             "أرسل المستندات للتوقيع وتابع حالتها ضمن مسار رقمي منظم.",
             "Send documents for signature and track their status in a digital workflow.",
             ["قوالب وحقول توقيع", "طلبات وتذكيرات", "سجل للمستندات الموقعة"],
             ["تقليل تداول الورق", "تسريع الاعتمادات", "حفظ مركزي للمستندات"],
             ["sales", "employees", "projects"]),
        _app("subscriptions", "الاشتراكات والتأجير", "Subscriptions & Rental",
             "أدر الإيرادات المتكررة أو حجوزات الأصول عندما يناسب ذلك نموذج عملك.",
             "Manage recurring revenue or rentable products when they fit your business model.",
             ["خطط وعقود متكررة", "فواتير وتجديدات دورية", "جداول تأجير وتوفر بحسب التطبيق"],
             ["متابعة أوضح للإيراد المتكرر", "تقليل أعمال التجديد اليدوية", "تنظيم توفر الأصول"],
             ["sales", "accounting", "ecommerce"]),
    ]
}


def _industry(slug, ar, en, challenges, operations, apps):
    return {"slug": slug, "kind": "industry", "title_ar": ar, "title_en": en,
            "challenges": challenges, "operations": operations, "related": apps}


INDUSTRIES = {
    item["slug"]: item for item in [
        _industry("construction", "المقاولات", "Construction", ["تعدد المشاريع والمواقع", "ضبط التكاليف والمشتريات", "متابعة الإنجاز والمستخلصات"], ["الفرص والعقود", "المشاريع والمهام", "المشتريات والمخزون والمحاسبة"], ["projects", "purchase", "accounting"]),
        _industry("trading-distribution", "التجارة والتوزيع", "Trading & Distribution", ["تغير الطلب والأسعار", "تعدد المستودعات", "سرعة التوريد والتحصيل"], ["المبيعات والمشتريات", "المخزون وإعادة الطلب", "الفوترة والتحصيل"], ["sales", "purchase", "inventory"]),
        _industry("retail", "التجزئة", "Retail", ["تعدد الفروع", "دقة المخزون", "سرعة خدمة العميل"], ["نقاط البيع", "المخزون والتسعير", "المحاسبة والعملاء"], ["point-of-sale", "inventory", "accounting"]),
        _industry("restaurants-cafes", "المطاعم والمقاهي", "Restaurants & Cafes", ["سرعة الطلب والتحصيل", "إدارة الأصناف والفروع", "ربط المبيعات بالمخزون"], ["نقاط البيع", "المنتجات والمشتريات", "الفوترة والتقارير"], ["point-of-sale", "inventory", "purchase"]),
        _industry("manufacturing", "التصنيع", "Manufacturing", ["تخطيط المواد والطاقة", "تتبع أوامر الإنتاج", "الجودة والصيانة"], ["قوائم المواد والإنتاج", "المخزون والمشتريات", "الجودة والصيانة"], ["manufacturing", "quality", "maintenance"]),
        _industry("professional-services", "الخدمات المهنية", "Professional Services", ["توزيع وقت الفريق", "متابعة التسليمات", "ربط الجهد بالفوترة"], ["CRM والمبيعات", "المشاريع وسجلات الوقت", "الفوترة وخدمة العملاء"], ["crm", "projects", "accounting"]),
        _industry("real-estate", "العقارات وإدارة الأملاك", "Real Estate & Property Management", ["تعدد الوحدات والعقود", "متابعة العملاء والطلبات", "التحصيل والصيانة"], ["CRM والوثائق", "الفوترة والاشتراكات", "الصيانة والمهام"], ["crm", "subscriptions", "maintenance"]),
        _industry("ecommerce", "التجارة الإلكترونية", "eCommerce", ["تزامن المتجر والمخزون", "تعدد الطلبات والشحن", "خدمة العملاء والتحصيل"], ["المتجر والمبيعات", "المخزون والمشتريات", "الفوترة والتسويق"], ["ecommerce", "inventory", "marketing"]),
        _industry("field-services", "الصيانة والخدمات الميدانية", "Maintenance & Field Services", ["جدولة الفرق", "توثيق الزيارات", "قطع الغيار والفوترة"], ["المهام الميدانية", "المخزون والصيانة", "المبيعات والفوترة"], ["projects", "maintenance", "inventory"]),
        _industry("education", "التعليم والتدريب", "Education & Training", ["تنظيم البرامج والمواعيد", "متابعة التسجيل والمدفوعات", "التواصل مع المستفيدين"], ["الموقع والتسجيل", "المبيعات والفوترة", "المشاريع والتسويق"], ["ecommerce", "sales", "projects"]),
        _industry("startups-smes", "الشركات الناشئة والمنشآت الصغيرة والمتوسطة", "Startups & SMEs", ["موارد محدودة", "أنظمة متفرقة", "الحاجة إلى نمو تدريجي"], ["المبيعات والمحاسبة", "المخزون أو المشاريع", "التقارير والتعاون"], ["crm", "accounting", "projects"]),
    ]
}


SERVICES = [
    ("تحليل الأعمال والاستشارات", "فهم العمليات والأهداف وتحديد نطاق واضح ومراحل قابلة للقياس."),
    ("تطبيق وتهيئة Odoo", "إعداد التطبيقات والصلاحيات ومسارات العمل بما يلائم العمليات المتفق عليها."),
    ("التطوير والتخصيص", "تنفيذ إضافات مدروسة عندما لا تغطي الوظائف القياسية الاحتياج."),
    ("نقل وتنظيف البيانات", "تجهيز البيانات والتحقق منها وتجربة ترحيلها قبل النقل النهائي."),
    ("التكامل مع الأنظمة", "ربط Odoo بالخدمات الخارجية عبر واجهات وتدفقات محددة وآمنة."),
    ("التقارير ولوحات المعلومات", "تحويل مؤشرات العمل إلى تقارير عملية تساعد على المتابعة واتخاذ القرار."),
    ("التدريب وإدارة التغيير", "تدريب المستخدمين بحسب أدوارهم وتوثيق إجراءات التشغيل الأساسية."),
    ("الدعم والتحسين المستمر", "معالجة الطلبات ومراجعة الاستخدام وتطوير النظام على مراحل بعد الإطلاق."),
    ("ترقية الإصدارات", "تقييم الإضافات والبيانات واختبار الترقية في بيئة منفصلة قبل الانتقال."),
]
