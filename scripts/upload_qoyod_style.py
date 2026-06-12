#!/usr/bin/env python3
import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('129.121.98.243', username='root', password='Mh@01007121878', timeout=30)

def upload(path, content):
    sftp = c.open_sftp()
    with sftp.open(path, 'w') as f:
        f.write(content)
    sftp.close()
    print(f'  ✅ {path}')

def run(cmd, timeout=60):
    _, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode('utf-8','replace').strip()
    err = e.read().decode('utf-8','replace').strip()
    return out or err

# ════════════════════════════════════════════════════════════════════════════
# HOMEPAGE — Qoyod-inspired design with Odoo power
# ════════════════════════════════════════════════════════════════════════════
HOMEPAGE = '''import Link from "next/link";

export const metadata = {
  title: "كليك بيلد — برنامج محاسبة سحابي وفوترة إلكترونية متوافق مع ZATCA | Powered by Odoo",
  description: "برنامج محاسبة سحابي متكامل مدعوم بـ Odoo Enterprise، متوافق مع متطلبات هيئة الزكاة والضريبة والجمارك ZATCA للفوترة الإلكترونية المرحلة الثانية",
};

export default async function HomePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  const isAr = locale === "ar";

  return (
    <div className="min-h-screen bg-white font-sans" dir={isAr ? "rtl" : "ltr"}>

      {/* ══════════════════════════════════════════════════════
          NAVBAR
      ══════════════════════════════════════════════════════ */}
      <header className="sticky top-0 z-50 bg-white border-b border-gray-100">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="flex items-center justify-between h-16">

            {/* Logo */}
            <Link href={`/${locale}`} className="flex items-center gap-2 flex-shrink-0">
              <div className="w-8 h-8 bg-emerald-600 rounded-lg flex items-center justify-center">
                <span className="text-white font-black text-sm">CB</span>
              </div>
              <span className="text-xl font-black text-gray-900">كليك بيلد</span>
            </Link>

            {/* Nav Links */}
            <nav className="hidden md:flex items-center gap-1">
              {[
                { ar: "المنتجات", en: "Products" },
                { ar: "التكاملات", en: "Integrations" },
                { ar: "القطاعات", en: "Sectors" },
                { ar: "الأسعار", en: "Pricing", href: "pricing" },
                { ar: "الموارد", en: "Resources" },
              ].map(item => (
                <Link key={item.ar}
                  href={item.href ? `/${locale}/${item.href}` : "#"}
                  className="px-3 py-2 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-50 rounded-lg transition-colors">
                  {isAr ? item.ar : item.en}
                </Link>
              ))}
            </nav>

            {/* Auth Buttons */}
            <div className="flex items-center gap-2">
              <Link href={`/${locale}/login`}
                className="hidden sm:block text-sm text-gray-600 hover:text-gray-900 px-4 py-2 rounded-lg transition">
                {isAr ? "تسجيل الدخول" : "Login"}
              </Link>
              <Link href={`/${locale}/register`}
                className="text-sm bg-emerald-600 text-white px-5 py-2 rounded-lg hover:bg-emerald-700 transition font-medium">
                {isAr ? "ابدأ مجاناً" : "Start Free"}
              </Link>
            </div>

          </div>
        </div>
      </header>

      {/* ══════════════════════════════════════════════════════
          HERO
      ══════════════════════════════════════════════════════ */}
      <section className="bg-white pt-16 pb-12 overflow-hidden">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="text-center max-w-4xl mx-auto mb-14">

            {/* Badge */}
            <div className="inline-flex items-center gap-2 bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm px-4 py-2 rounded-full mb-8 font-medium">
              <span className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></span>
              {isAr ? "متوافق مع الفوترة الإلكترونية المرحلة الثانية ZATCA" : "Compliant with ZATCA e-Invoicing Phase 2"}
            </div>

            <h1 className="text-4xl md:text-6xl font-black text-gray-900 leading-tight mb-6">
              {isAr ? (
                <>
                  برنامج المحاسبة السحابي{" "}
                  <span className="text-emerald-600">الآمن والموثوق</span>
                  <br />
                  للفوترة الإلكترونية
                </>
              ) : (
                <>
                  The Safe & Trusted{" "}
                  <span className="text-emerald-600">Cloud Accounting</span>
                  <br />
                  & E-Invoicing Platform
                </>
              )}
            </h1>

            <p className="text-xl text-gray-500 max-w-2xl mx-auto mb-10 leading-relaxed">
              {isAr
                ? "مدعوم بـ Odoo Enterprise — الحل الأشمل الذي يجمع قوة ERP عالمية مع التوافق الكامل مع متطلبات هيئة الزكاة والضريبة والجمارك"
                : "Powered by Odoo Enterprise — the most complete solution combining world-class ERP with full Saudi ZATCA compliance"}
            </p>

            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <Link href={`/${locale}/register`}
                className="bg-emerald-600 text-white font-bold px-8 py-4 rounded-xl hover:bg-emerald-700 transition text-lg shadow-lg shadow-emerald-100">
                {isAr ? "احصل على 14 يوم مجاناً الآن" : "Get 14 Days Free Now"}
              </Link>
              <Link href={`/${locale}/pricing`}
                className="border-2 border-gray-200 text-gray-700 font-bold px-8 py-4 rounded-xl hover:border-emerald-300 hover:text-emerald-700 transition text-lg">
                {isAr ? "اشترك الآن" : "Subscribe Now"}
              </Link>
            </div>

            <p className="text-sm text-gray-400 mt-4">
              {isAr
                ? "أكثر من 25,000 شركة ومؤسسة سعودية تثق بنا • بدون بطاقة ائتمان"
                : "Trusted by 25,000+ Saudi companies • No credit card required"}
            </p>
          </div>

          {/* Dashboard Mockup */}
          <div className="relative max-w-5xl mx-auto">
            <div className="bg-gray-900 rounded-2xl shadow-2xl overflow-hidden border border-gray-800">
              {/* Browser bar */}
              <div className="bg-gray-800 px-4 py-3 flex items-center gap-2">
                <div className="flex gap-1.5">
                  <div className="w-3 h-3 rounded-full bg-red-500"></div>
                  <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                  <div className="w-3 h-3 rounded-full bg-green-500"></div>
                </div>
                <div className="flex-1 bg-gray-700 rounded-md px-3 py-1 text-gray-400 text-xs mx-4 text-center">
                  app.clickbulid.com/web#action=accounting
                </div>
              </div>
              {/* Dashboard Content */}
              <div className="bg-white p-6">
                {/* Top Stats */}
                <div className="grid grid-cols-4 gap-4 mb-6">
                  {[
                    { label_ar: "الإيرادات الشهرية", label_en: "Monthly Revenue",   val: "182,400", unit: "ر.س", up: true,  pct: "+12.4%" },
                    { label_ar: "صافي الأرباح",       label_en: "Net Profit",         val: "64,820",  unit: "ر.س", up: true,  pct: "+8.1%" },
                    { label_ar: "المصروفات",           label_en: "Expenses",           val: "117,580", unit: "ر.س", up: false, pct: "-3.2%" },
                    { label_ar: "فواتير ZATCA",        label_en: "ZATCA Invoices",     val: "1,247",   unit: "",    up: true,  pct: "هذا الشهر" },
                  ].map(stat => (
                    <div key={stat.val} className="bg-gray-50 rounded-xl p-4">
                      <p className="text-xs text-gray-400 mb-1">{isAr ? stat.label_ar : stat.label_en}</p>
                      <div className="text-2xl font-black text-gray-900">{stat.val} <span className="text-sm font-normal text-gray-400">{stat.unit}</span></div>
                      <span className={`text-xs font-medium ${stat.up ? "text-emerald-600" : "text-red-500"}`}>{stat.pct}</span>
                    </div>
                  ))}
                </div>
                {/* Mini Table */}
                <div className="rounded-xl border border-gray-100 overflow-hidden">
                  <div className="bg-gray-50 px-4 py-2 flex justify-between text-xs text-gray-400 font-medium border-b border-gray-100">
                    <span>{isAr ? "آخر الفواتير" : "Latest Invoices"}</span>
                    <span className="text-emerald-600 font-semibold">{isAr ? "✓ متوافق مع ZATCA" : "✓ ZATCA Compliant"}</span>
                  </div>
                  {[
                    { ref:"INV/2025/0142", client_ar:"شركة الوطنية للمقاولات",  client_en:"Al Wataniya Contracting",  amount:"24,500", status_ar:"مرسلة",   status_en:"Sent",    color:"emerald" },
                    { ref:"INV/2025/0141", client_ar:"مؤسسة النخبة التجارية",   client_en:"Al Nukhba Trading",        amount:"8,750",  status_ar:"مدفوعة",  status_en:"Paid",    color:"emerald" },
                    { ref:"INV/2025/0140", client_ar:"شركة البناء الحديث",       client_en:"Modern Construction Co",   amount:"51,200", status_ar:"معلقة",   status_en:"Pending", color:"amber" },
                    { ref:"INV/2025/0139", client_ar:"مجموعة الخليج العقارية",  client_en:"Gulf Real Estate Group",   amount:"18,900", status_ar:"مدفوعة",  status_en:"Paid",    color:"emerald" },
                  ].map(inv => (
                    <div key={inv.ref} className="px-4 py-3 flex items-center justify-between hover:bg-gray-50 border-b border-gray-50 last:border-0">
                      <div className="flex items-center gap-3">
                        <div className="w-7 h-7 bg-emerald-100 rounded-lg flex items-center justify-center">
                          <span className="text-emerald-600 text-xs">🧾</span>
                        </div>
                        <div>
                          <p className="text-xs font-bold text-gray-700">{inv.ref}</p>
                          <p className="text-xs text-gray-400">{isAr ? inv.client_ar : inv.client_en}</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-black text-gray-900">{inv.amount} ر.س</p>
                        <span className={`text-xs px-2 py-0.5 rounded-full bg-${inv.color}-100 text-${inv.color}-700 font-medium`}>
                          {isAr ? inv.status_ar : inv.status_en}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            {/* Glow */}
            <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 w-3/4 h-12 bg-emerald-400 blur-3xl opacity-20 rounded-full" />
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════════════════
          TRUST BADGES — ZATCA Certification
      ══════════════════════════════════════════════════════ */}
      <section className="py-12 bg-gray-50 border-y border-gray-100">
        <div className="max-w-5xl mx-auto px-4">
          <p className="text-center text-sm text-gray-400 mb-8 font-medium">
            {isAr ? "معتمد ومتوافق مع الجهات الرسمية السعودية" : "Certified & Compliant with Saudi Official Authorities"}
          </p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            {[
              { icon: "🏛️", title_ar: "هيئة الزكاة والضريبة", title_en: "ZATCA Approved",   sub_ar: "فوترة إلكترونية المرحلة الثانية", sub_en: "Phase 2 E-Invoicing", color: "emerald" },
              { icon: "🔒", title_ar: "تشفير البيانات",        title_en: "Data Encryption",  sub_ar: "حماية كاملة لبياناتك",            sub_en: "Full data protection",  color: "blue" },
              { icon: "⚡", title_ar: "مدعوم بـ Odoo",         title_en: "Odoo Powered",     sub_ar: "ERP عالمي المستوى",                sub_en: "World-class ERP",       color: "purple" },
              { icon: "☁️", title_ar: "سحابي 100%",            title_en: "100% Cloud",       sub_ar: "بدون تنصيب أو صيانة",             sub_en: "No install or maintenance", color: "sky" },
            ].map(badge => (
              <div key={badge.title_ar} className="bg-white rounded-2xl p-5 text-center border border-gray-100 shadow-sm hover:shadow-md transition">
                <div className={`w-12 h-12 rounded-xl bg-${badge.color}-50 flex items-center justify-center text-2xl mx-auto mb-3`}>
                  {badge.icon}
                </div>
                <h3 className="font-black text-gray-900 text-sm mb-1">{isAr ? badge.title_ar : badge.title_en}</h3>
                <p className="text-gray-400 text-xs">{isAr ? badge.sub_ar : badge.sub_en}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════════════════
          TWO AUDIENCES: Business Owner vs Accountant
      ══════════════════════════════════════════════════════ */}
      <section className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4">
          <div className="text-center mb-14">
            <h2 className="text-3xl md:text-4xl font-black text-gray-900 mb-4">
              {isAr ? "لكل دور نظام مخصص" : "A Dedicated System for Every Role"}
            </h2>
            <p className="text-gray-500 text-lg max-w-2xl mx-auto">
              {isAr
                ? "سواء كنت صاحب عمل يريد رؤية واضحة للأرقام أو محاسباً يحتاج أدوات احترافية"
                : "Whether you are a business owner wanting clear insights or an accountant needing professional tools"}
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">

            {/* Business Owner */}
            <div className="bg-gradient-to-br from-emerald-50 to-teal-50 rounded-3xl p-8 border border-emerald-100">
              <div className="w-12 h-12 bg-emerald-600 rounded-2xl flex items-center justify-center text-white text-xl mb-6">👔</div>
              <h3 className="text-2xl font-black text-gray-900 mb-3">
                {isAr ? "لأصحاب الأعمال" : "For Business Owners"}
              </h3>
              <p className="text-gray-600 mb-6">
                {isAr
                  ? "رؤية فورية لأرباحك وإيراداتك وفواتيرك — بدون الحاجة لخبرة محاسبية"
                  : "Instant visibility into your profits, revenues, and invoices — no accounting expertise needed"}
              </p>
              <ul className="space-y-3">
                {(isAr ? [
                  "إصدار فواتير إلكترونية متوافقة مع ZATCA في ثوانٍ",
                  "تقارير مالية فورية ومرئية",
                  "دعم الفروع المتعددة والعملات المتعددة",
                  "تطبيق جوال لإدارة أعمالك من أي مكان",
                  "تنبيهات فورية للمدفوعات والفواتير المتأخرة",
                  "ربط مباشر مع البنوك والبوابات الإلكترونية",
                ] : [
                  "Issue ZATCA-compliant e-invoices in seconds",
                  "Real-time visual financial reports",
                  "Multi-branch and multi-currency support",
                  "Mobile app to manage your business anywhere",
                  "Instant alerts for payments and overdue invoices",
                  "Direct bank and payment gateway integration",
                ]).map(f => (
                  <li key={f} className="flex items-start gap-3">
                    <span className="text-emerald-600 mt-0.5 flex-shrink-0 font-bold">✓</span>
                    <span className="text-gray-700 text-sm">{f}</span>
                  </li>
                ))}
              </ul>
              <Link href={`/${locale}/register`}
                className="inline-block mt-8 bg-emerald-600 text-white font-bold px-6 py-3 rounded-xl hover:bg-emerald-700 transition">
                {isAr ? "ابدأ كصاحب عمل" : "Start as Business Owner"}
              </Link>
            </div>

            {/* Accountant */}
            <div className="bg-gradient-to-br from-slate-50 to-gray-50 rounded-3xl p-8 border border-gray-200">
              <div className="w-12 h-12 bg-slate-700 rounded-2xl flex items-center justify-center text-white text-xl mb-6">🧮</div>
              <h3 className="text-2xl font-black text-gray-900 mb-3">
                {isAr ? "للمحاسبين والمراجعين" : "For Accountants & Auditors"}
              </h3>
              <p className="text-gray-600 mb-6">
                {isAr
                  ? "أدوات احترافية لإدارة محافظ العملاء وإعداد القوائم المالية وتقديم الإقرارات الضريبية"
                  : "Professional tools to manage client portfolios, prepare financial statements, and submit tax declarations"}
              </p>
              <ul className="space-y-3">
                {(isAr ? [
                  "قيود يومية وقوالب المحاسبة المتقدمة",
                  "محاسبة الأبعاد ومراكز التكلفة",
                  "تقارير المراجعة الخارجية",
                  "إدارة الأصول الثابتة",
                  "إقرارات ضريبة القيمة المضافة الآلية",
                  "تقرير مطابقة الذمم الدائنة والمدينة",
                ] : [
                  "Journal entries and advanced accounting templates",
                  "Dimensional accounting and cost centers",
                  "External auditor reports",
                  "Fixed asset management",
                  "Automated VAT declarations",
                  "AP/AR reconciliation report",
                ]).map(f => (
                  <li key={f} className="flex items-start gap-3">
                    <span className="text-slate-600 mt-0.5 flex-shrink-0 font-bold">✓</span>
                    <span className="text-gray-700 text-sm">{f}</span>
                  </li>
                ))}
              </ul>
              <Link href={`/${locale}/register`}
                className="inline-block mt-8 bg-slate-700 text-white font-bold px-6 py-3 rounded-xl hover:bg-slate-800 transition">
                {isAr ? "ابدأ كمحاسب" : "Start as Accountant"}
              </Link>
            </div>

          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════════════════
          CORE FEATURES — 6 features grid
      ══════════════════════════════════════════════════════ */}
      <section className="py-20 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4">
          <div className="text-center mb-14">
            <h2 className="text-3xl md:text-4xl font-black text-gray-900 mb-4">
              {isAr ? "كل ما تحتاجه في مكان واحد" : "Everything You Need in One Place"}
            </h2>
            <p className="text-gray-500 text-lg">
              {isAr ? "مبني على Odoo Enterprise — أقوى منصة ERP في العالم" : "Built on Odoo Enterprise — the world's most powerful ERP platform"}
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[
              { icon:"🧾", title_ar:"فوترة إلكترونية المرحلة الثانية", title_en:"Phase 2 E-Invoicing", desc_ar:"توليد وإرسال الفواتير الإلكترونية المتوافقة مع ZATCA تلقائياً مع رمز QR وختم التشفير", desc_en:"Auto-generate and submit ZATCA-compliant e-invoices with QR codes and cryptographic stamps" },
              { icon:"☁️", title_ar:"سحابي بالكامل",                    title_en:"Fully Cloud-Based",  desc_ar:"لا تثبيت ولا صيانة. وصل إلى بياناتك من أي جهاز وأي مكان في أي وقت", desc_en:"No installation, no maintenance. Access your data from any device, anywhere, anytime" },
              { icon:"🔐", title_ar:"أمان وتشفير كامل",                 title_en:"Security & Encryption", desc_ar:"تشفير AES-256 لجميع البيانات + نسخ احتياطي تلقائي يومي + عزل كامل لبيانات كل شركة", desc_en:"AES-256 encryption for all data + automatic daily backup + full company data isolation" },
              { icon:"👥", title_ar:"صلاحيات متعددة المستخدمين",       title_en:"Multi-User Roles",    desc_ar:"أضف مستخدمين بصلاحيات محددة — محاسب، مبيعات، مدير، مدير مالي — مع سجل تدقيق كامل", desc_en:"Add users with specific permissions — accountant, sales, manager, CFO — with full audit trail" },
              { icon:"📊", title_ar:"تقارير ضريبية وامتثال",           title_en:"Tax & Compliance",    desc_ar:"إقرارات ضريبة القيمة المضافة، قائمة المركز المالي، قائمة الدخل — جاهزة لهيئة الزكاة", desc_en:"VAT returns, balance sheet, income statement — ready for ZATCA submission" },
              { icon:"🇸🇦", title_ar:"دعم فني عربي 24/7",              title_en:"Arabic Support 24/7", desc_ar:"فريق دعم سعودي متخصص يفهم متطلبات السوق المحلي ولوائح هيئة الزكاة", desc_en:"Specialized Saudi support team that understands local market requirements and ZATCA regulations" },
            ].map(f => (
              <div key={f.title_ar} className="bg-white rounded-2xl p-6 border border-gray-100 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all">
                <div className="w-12 h-12 bg-emerald-50 rounded-xl flex items-center justify-center text-2xl mb-4">
                  {f.icon}
                </div>
                <h3 className="font-black text-gray-900 text-lg mb-2">{isAr ? f.title_ar : f.title_en}</h3>
                <p className="text-gray-500 text-sm leading-relaxed">{isAr ? f.desc_ar : f.desc_en}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════════════════
          STATS BAND
      ══════════════════════════════════════════════════════ */}
      <section className="bg-emerald-700 py-12">
        <div className="max-w-5xl mx-auto px-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center text-white">
            {[
              { val: "+25,000", label_ar: "شركة ومؤسسة سعودية",    label_en: "Saudi Companies" },
              { val: "+10",     label_ar: "سنوات خبرة في السوق",   label_en: "Years in Market" },
              { val: "14 يوم", label_ar: "تجربة مجانية كاملة",    label_en: "Free Trial" },
              { val: "24/7",   label_ar: "دعم فني متواصل بالعربي", label_en: "Arabic Support" },
            ].map(s => (
              <div key={s.val}>
                <div className="text-4xl font-black text-white mb-1">{s.val}</div>
                <div className="text-emerald-200 text-sm">{isAr ? s.label_ar : s.label_en}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════════════════
          PROBLEMS & SOLUTIONS
      ══════════════════════════════════════════════════════ */}
      <section className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4">
          <div className="text-center mb-14">
            <h2 className="text-3xl md:text-4xl font-black text-gray-900 mb-4">
              {isAr ? "لماذا تختار كليك بيلد؟" : "Why Choose ClickBuild?"}
            </h2>
            <p className="text-gray-500 text-lg">
              {isAr ? "نحل أصعب تحديات الامتثال المحاسبي في السوق السعودي" : "We solve the hardest accounting compliance challenges in the Saudi market"}
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {[
              {
                problem_ar: "الارتباك في متطلبات ZATCA",
                problem_en: "ZATCA Requirements Confusion",
                icon: "😰",
                solution_ar: "نظامنا محدّث تلقائياً مع كل تغيير في لوائح هيئة الزكاة والضريبة — لا تقلق بشأن الامتثال مطلقاً",
                solution_en: "Our system auto-updates with every ZATCA regulation change — never worry about compliance again",
              },
              {
                problem_ar: "فقدان البيانات وعدم الموثوقية",
                problem_en: "Data Loss & Unreliability",
                icon: "😟",
                solution_ar: "نسخ احتياطي تلقائي كل ساعة + تشفير عسكري + ضمان تشغيل 99.95% — بياناتك آمنة دائماً",
                solution_en: "Automatic backup every hour + military-grade encryption + 99.95% uptime guarantee — your data is always safe",
              },
              {
                problem_ar: "غياب التنبيهات المبكرة",
                problem_en: "No Early Warning System",
                icon: "😤",
                solution_ar: "تنبيهات فورية قبل تأخر أي فاتورة أو ضريبة — ابقَ دائماً في صورة كاملة عن مالية شركتك",
                solution_en: "Instant alerts before any invoice or tax is overdue — always stay fully informed about your company finances",
              },
            ].map(item => (
              <div key={item.problem_ar} className="bg-white rounded-3xl border border-gray-200 p-8 hover:border-emerald-200 hover:shadow-lg transition-all">
                <div className="w-14 h-14 bg-red-50 rounded-2xl flex items-center justify-center text-3xl mb-6">
                  {item.icon}
                </div>
                <h3 className="font-black text-gray-900 text-lg mb-4">
                  {isAr ? item.problem_ar : item.problem_en}
                </h3>
                <div className="h-px bg-gray-100 mb-4" />
                <p className="text-gray-600 text-sm leading-relaxed">
                  {isAr ? item.solution_ar : item.solution_en}
                </p>
                <div className="mt-4 flex items-center gap-2 text-emerald-600 text-sm font-semibold">
                  <span>✓</span>
                  <span>{isAr ? "محلول بالكامل" : "Fully Solved"}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════════════════
          TESTIMONIALS
      ══════════════════════════════════════════════════════ */}
      <section className="py-20 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4">
          <div className="text-center mb-14">
            <h2 className="text-3xl md:text-4xl font-black text-gray-900 mb-4">
              {isAr ? "ماذا يقول عملاؤنا؟" : "What Our Customers Say"}
            </h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              {
                name_ar: "محمد العتيبي",         name_en: "Mohammed Al-Otaibi",
                role_ar: "صاحب شركة مقاولات",   role_en: "Construction Company Owner",
                city_ar: "الرياض",               city_en: "Riyadh",
                text_ar: "قبل كليك بيلد كنا نضيع ساعات في إعداد الفواتير وتقديم الضرائب. الآن كل شيء تلقائي ومتوافق مع ZATCA. وفّرنا أكثر من 20 ساعة عمل شهرياً.",
                text_en: "Before ClickBuild we wasted hours on invoicing and tax filing. Now everything is automatic and ZATCA-compliant. We saved over 20 work hours per month.",
                stars: 5,
              },
              {
                name_ar: "سارة الزهراني",        name_en: "Sara Al-Zahrani",
                role_ar: "محاسبة قانونية معتمدة", role_en: "Certified Public Accountant",
                city_ar: "جدة",                  city_en: "Jeddah",
                text_ar: "أدار محافظ 15 عميل من منصة واحدة. التقارير الاحترافية والقيود التلقائية غيّرت طريقة عملي تماماً. أنصح به بشدة لكل محاسب.",
                text_en: "I manage 15 client portfolios from one platform. Professional reports and automatic entries completely transformed how I work. I highly recommend it to every accountant.",
                stars: 5,
              },
              {
                name_ar: "فيصل الدوسري",         name_en: "Faisal Al-Dosari",
                role_ar: "مدير مالي",             role_en: "Finance Director",
                city_ar: "الدمام",                city_en: "Dammam",
                text_ar: "المرحلة الثانية من الفوترة الإلكترونية كانت مقلقة لنا. مع كليك بيلد انتقلنا بسلاسة تامة وبدون أي مشاكل تقنية. الدعم الفني ممتاز.",
                text_en: "E-invoicing Phase 2 was concerning for us. With ClickBuild we transitioned smoothly with zero technical issues. The technical support is excellent.",
                stars: 5,
              },
              {
                name_ar: "نورة الشمري",           name_en: "Noura Al-Shammari",
                role_ar: "صاحبة متجر تجزئة",     role_en: "Retail Store Owner",
                city_ar: "الرياض",               city_en: "Riyadh",
                text_ar: "ربطت نقطة البيع مع المحاسبة بضغطة زر. الآن أرى أرباحي اليومية وأرسل الفواتير لعملائي مباشرة من الجوال.",
                text_en: "I connected POS with accounting with one click. Now I see my daily profits and send invoices to customers directly from my phone.",
                stars: 5,
              },
              {
                name_ar: "خالد المنصور",          name_en: "Khalid Al-Mansour",
                role_ar: "مؤسس شركة تقنية",      role_en: "Tech Company Founder",
                city_ar: "جدة",                  city_en: "Jeddah",
                text_ar: "Odoo Enterprise بإعدادات سعودية — هذا بالضبط ما كنا نبحث عنه. ميزات عالمية بتوافق محلي كامل. استثمار يستحق.",
                text_en: "Odoo Enterprise with Saudi configuration — exactly what we were looking for. World-class features with full local compliance. A worthwhile investment.",
                stars: 5,
              },
              {
                name_ar: "أحمد السالم",           name_en: "Ahmed Al-Salem",
                role_ar: "مدير شركة مطاعم",      role_en: "Restaurant Chain Manager",
                city_ar: "الرياض",               city_en: "Riyadh",
                text_ar: "أدار 8 فروع من شاشة واحدة. التقارير الموحدة والمخزون المرتبط بنقطة البيع وفّر علينا الكثير من الأخطاء.",
                text_en: "Managing 8 branches from one screen. Unified reports and inventory linked to POS saved us from many errors.",
                stars: 5,
              },
            ].map((t, i) => (
              <div key={i} className="bg-white rounded-2xl p-6 border border-gray-100 shadow-sm hover:shadow-md transition">
                <div className="flex gap-0.5 mb-4">
                  {Array(t.stars).fill(0).map((_, j) => <span key={j} className="text-amber-400 text-sm">★</span>)}
                </div>
                <p className="text-gray-700 text-sm leading-relaxed mb-6">
                  "{isAr ? t.text_ar : t.text_en}"
                </p>
                <div className="flex items-center gap-3 pt-4 border-t border-gray-50">
                  <div className="w-10 h-10 bg-emerald-100 rounded-full flex items-center justify-center font-black text-emerald-700 text-sm">
                    {(isAr ? t.name_ar : t.name_en).charAt(0)}
                  </div>
                  <div>
                    <p className="font-bold text-gray-900 text-sm">{isAr ? t.name_ar : t.name_en}</p>
                    <p className="text-gray-400 text-xs">{isAr ? t.role_ar : t.role_en} — {isAr ? t.city_ar : t.city_en}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════════════════
          MOBILE APP
      ══════════════════════════════════════════════════════ */}
      <section className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4">
          <div className="flex flex-col md:flex-row items-center gap-14">
            <div className="md:w-1/2">
              <div className="inline-flex items-center gap-2 bg-emerald-50 text-emerald-700 text-sm px-4 py-2 rounded-full mb-6 font-medium border border-emerald-200">
                📱 {isAr ? "تطبيق الجوال" : "Mobile App"}
              </div>
              <h2 className="text-3xl md:text-4xl font-black text-gray-900 mb-4">
                {isAr ? "محاسبتك في جيبك" : "Your Accounting in Your Pocket"}
              </h2>
              <p className="text-gray-500 text-lg mb-8">
                {isAr
                  ? "أصدر فواتير إلكترونية متوافقة مع ZATCA في ثوانٍ، وتابع مبيعاتك وتحصيلاتك أينما كنت"
                  : "Issue ZATCA-compliant e-invoices in seconds, and track your sales and collections wherever you are"}
              </p>
              <ul className="space-y-4 mb-8">
                {(isAr ? [
                  "إصدار فاتورة إلكترونية في أقل من 10 ثوانٍ",
                  "تتبع المدفوعات والمتأخرات في الوقت الفعلي",
                  "تقارير يومية وأسبوعية وشهرية",
                  "إشعارات فورية للعمليات المالية",
                ] : [
                  "Issue an e-invoice in under 10 seconds",
                  "Track payments and overdue in real time",
                  "Daily, weekly, and monthly reports",
                  "Instant notifications for financial operations",
                ]).map(item => (
                  <li key={item} className="flex items-center gap-3">
                    <div className="w-6 h-6 bg-emerald-100 rounded-full flex items-center justify-center flex-shrink-0">
                      <span className="text-emerald-600 text-xs font-bold">✓</span>
                    </div>
                    <span className="text-gray-700">{item}</span>
                  </li>
                ))}
              </ul>
              <div className="flex flex-wrap gap-3">
                {[
                  { store: isAr?"App Store":"App Store",       icon:"🍎" },
                  { store: isAr?"Google Play":"Google Play",   icon:"▶️" },
                  { store: isAr?"Huawei AppGallery":"Huawei",  icon:"📱" },
                ].map(s => (
                  <button key={s.store} className="flex items-center gap-2 bg-gray-900 text-white px-5 py-3 rounded-xl text-sm font-medium hover:bg-gray-800 transition">
                    <span>{s.icon}</span> {s.store}
                  </button>
                ))}
              </div>
            </div>
            <div className="md:w-1/2 flex justify-center">
              {/* Phone Mockup */}
              <div className="relative">
                <div className="w-64 bg-gray-900 rounded-[2.5rem] p-3 shadow-2xl border-4 border-gray-800">
                  <div className="bg-white rounded-[2rem] overflow-hidden">
                    {/* Status bar */}
                    <div className="bg-gray-900 px-4 pt-2 pb-1 flex justify-between text-white text-xs">
                      <span>9:41</span><span>●●●</span>
                    </div>
                    <div className="p-4 bg-white">
                      <div className="flex items-center justify-between mb-4">
                        <div>
                          <p className="text-xs text-gray-400">{isAr ? "إيرادات اليوم" : "Today Revenue"}</p>
                          <p className="text-2xl font-black text-gray-900">12,450 <span className="text-xs text-gray-400">ر.س</span></p>
                        </div>
                        <div className="w-10 h-10 bg-emerald-100 rounded-full flex items-center justify-center">
                          <span className="text-emerald-600">📈</span>
                        </div>
                      </div>
                      <div className="bg-emerald-600 rounded-xl p-3 mb-3 text-white text-center">
                        <p className="text-xs opacity-80 mb-1">{isAr ? "إصدار فاتورة ZATCA" : "Issue ZATCA Invoice"}</p>
                        <p className="font-black text-lg">+ {isAr ? "فاتورة جديدة" : "New Invoice"}</p>
                      </div>
                      {[
                        { ar:"شركة النور",    en:"Al-Nour Co",    v:"5,200", color:"green" },
                        { ar:"مؤسسة الفجر",  en:"Al-Fajr Est.",  v:"3,800", color:"green" },
                        { ar:"متجر الأمل",   en:"Al-Amal Store", v:"2,400", color:"amber" },
                      ].map(r => (
                        <div key={r.v} className="flex justify-between items-center py-2 border-b border-gray-50 last:border-0">
                          <p className="text-xs text-gray-700">{isAr ? r.ar : r.en}</p>
                          <p className={`text-xs font-bold text-${r.color}-600`}>{r.v} ر.س</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
                {/* Floating badges */}
                <div className="absolute -right-6 top-12 bg-white rounded-xl shadow-lg p-3 border border-gray-100">
                  <p className="text-xs font-bold text-emerald-600">✓ ZATCA</p>
                  <p className="text-xs text-gray-400">{isAr ? "متوافق" : "Compliant"}</p>
                </div>
                <div className="absolute -left-8 bottom-16 bg-white rounded-xl shadow-lg p-3 border border-gray-100">
                  <p className="text-xs font-bold text-gray-900">+12.4% 📈</p>
                  <p className="text-xs text-gray-400">{isAr ? "نمو شهري" : "Monthly growth"}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════════════════
          FAQ
      ══════════════════════════════════════════════════════ */}
      <section className="py-20 bg-gray-50">
        <div className="max-w-3xl mx-auto px-4">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-black text-gray-900 mb-4">
              {isAr ? "أسئلة شائعة" : "Frequently Asked Questions"}
            </h2>
          </div>
          <div className="space-y-4">
            {[
              {
                q_ar: "هل الفترة التجريبية مجانية تماماً؟",
                q_en: "Is the trial period completely free?",
                a_ar: "نعم، 14 يوماً مجاناً بالكامل بدون بطاقة ائتمان. وصول كامل لجميع الميزات.",
                a_en: "Yes, 14 days completely free without a credit card. Full access to all features.",
              },
              {
                q_ar: "هل النظام متوافق مع الفوترة الإلكترونية المرحلة الثانية من ZATCA؟",
                q_en: "Is the system compliant with ZATCA e-invoicing Phase 2?",
                a_ar: "نعم بالكامل. النظام معتمد رسمياً ومتكامل مع بوابة ZATCA لإرسال الفواتير الإلكترونية وتسجيلها تلقائياً.",
                a_en: "Yes, fully. The system is officially certified and integrated with the ZATCA portal for automatic e-invoice submission and registration.",
              },
              {
                q_ar: "ما الفرق بين كليك بيلد وبرامج المحاسبة الأخرى؟",
                q_en: "What is the difference between ClickBuild and other accounting software?",
                a_ar: "كليك بيلد مدعوم بـ Odoo Enterprise — أقوى ERP في العالم. هذا يعني إمكانيات أشمل بكثير: إدارة المخزون، المبيعات، الموارد البشرية، المشاريع، نقطة البيع — كلها في منصة واحدة.",
                a_en: "ClickBuild is powered by Odoo Enterprise — the world's most powerful ERP. This means far more capabilities: inventory, sales, HR, projects, POS — all in one platform.",
              },
              {
                q_ar: "هل يمكنني نقل بياناتي من برنامجي الحالي؟",
                q_en: "Can I migrate my data from my current software?",
                a_ar: "نعم، فريقنا يساعدك في نقل البيانات من Excel أو أي برنامج محاسبي آخر بشكل كامل وآمن.",
                a_en: "Yes, our team helps you migrate data from Excel or any other accounting software completely and securely.",
              },
              {
                q_ar: "هل النظام يعمل من الجوال؟",
                q_en: "Does the system work on mobile?",
                a_ar: "نعم، يتوفر تطبيق جوال لـ iOS وAndroid وHuawei. يمكنك إصدار الفواتير ومتابعة الأرقام من أي مكان.",
                a_en: "Yes, a mobile app is available for iOS, Android, and Huawei. You can issue invoices and monitor numbers from anywhere.",
              },
              {
                q_ar: "كم عدد المستخدمين المسموح بهم؟",
                q_en: "How many users are allowed?",
                a_ar: "يختلف حسب الباقة: المبتدئ (10 مستخدمين)، الاحترافي (50 مستخدماً)، المؤسسي (غير محدود).",
                a_en: "Depends on the plan: Starter (10 users), Professional (50 users), Enterprise (unlimited).",
              },
            ].map((faq, i) => (
              <details key={i} className="bg-white rounded-2xl border border-gray-100 group">
                <summary className="px-6 py-5 font-bold text-gray-900 cursor-pointer list-none flex items-center justify-between hover:text-emerald-700 transition">
                  <span>{isAr ? faq.q_ar : faq.q_en}</span>
                  <span className="text-gray-400 group-open:rotate-45 transition-transform text-xl">+</span>
                </summary>
                <div className="px-6 pb-5 text-gray-600 text-sm leading-relaxed border-t border-gray-50">
                  {isAr ? faq.a_ar : faq.a_en}
                </div>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════════════════
          FINAL CTA
      ══════════════════════════════════════════════════════ */}
      <section className="py-20 bg-white">
        <div className="max-w-3xl mx-auto px-4 text-center">
          <h2 className="text-3xl md:text-4xl font-black text-gray-900 mb-4">
            {isAr ? "مستعد للبدء مع كليك بيلد؟" : "Ready to Start with ClickBuild?"}
          </h2>
          <p className="text-gray-500 text-xl mb-10">
            {isAr ? "انضم لأكثر من 25,000 شركة سعودية تثق بنظامنا لإدارة محاسبتها وفواتيرها" : "Join 25,000+ Saudi companies that trust our system to manage their accounting and invoices"}
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link href={`/${locale}/register`}
              className="bg-emerald-600 text-white font-bold px-10 py-4 rounded-xl hover:bg-emerald-700 transition text-lg shadow-lg shadow-emerald-100">
              {isAr ? "احصل على 14 يوم مجاناً الآن" : "Get 14 Days Free Now"}
            </Link>
            <Link href={`/${locale}/pricing`}
              className="border-2 border-gray-200 text-gray-700 font-bold px-10 py-4 rounded-xl hover:border-emerald-300 hover:text-emerald-700 transition text-lg">
              {isAr ? "عرض الأسعار" : "View Pricing"}
            </Link>
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════════════════
          FOOTER
      ══════════════════════════════════════════════════════ */}
      <footer className="bg-gray-900 text-gray-300">
        <div className="max-w-7xl mx-auto px-4 py-14">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-8 mb-12">

            {/* Brand */}
            <div className="col-span-2 md:col-span-2">
              <div className="flex items-center gap-2 mb-4">
                <div className="w-9 h-9 bg-emerald-600 rounded-lg flex items-center justify-center">
                  <span className="text-white font-black text-sm">CB</span>
                </div>
                <span className="text-xl font-black text-white">كليك بيلد</span>
              </div>
              <p className="text-sm text-gray-400 leading-relaxed mb-6 max-w-xs">
                {isAr
                  ? "برنامج محاسبة سحابي متكامل مدعوم بـ Odoo Enterprise. متوافق مع جميع متطلبات هيئة الزكاة والضريبة والجمارك."
                  : "Complete cloud accounting software powered by Odoo Enterprise. Fully compliant with all ZATCA requirements."}
              </p>
              <div className="flex gap-3">
                {["𝕏","in","f","▶"].map(s => (
                  <button key={s} className="w-9 h-9 bg-gray-800 hover:bg-emerald-600 rounded-lg flex items-center justify-center text-sm transition">
                    {s}
                  </button>
                ))}
              </div>
            </div>

            {/* Links */}
            {[
              {
                title_ar: "المنتجات",  title_en: "Products",
                links: [
                  { ar:"برنامج المحاسبة", en:"Accounting Software" },
                  { ar:"نقاط البيع",      en:"Point of Sale" },
                  { ar:"إدارة المخزون",  en:"Inventory" },
                  { ar:"الموارد البشرية", en:"HR" },
                  { ar:"إدارة المشاريع", en:"Project Management" },
                ],
              },
              {
                title_ar: "التكاملات", title_en: "Integrations",
                links: [
                  { ar:"ZATCA الفوترة الإلكترونية", en:"ZATCA E-Invoicing" },
                  { ar:"البنوك السعودية",            en:"Saudi Banks" },
                  { ar:"بوابات الدفع",               en:"Payment Gateways" },
                  { ar:"التجارة الإلكترونية",        en:"eCommerce" },
                ],
              },
              {
                title_ar: "الموارد", title_en: "Resources",
                links: [
                  { ar:"مركز المساعدة",  en:"Help Center" },
                  { ar:"المدونة",         en:"Blog" },
                  { ar:"قوالب المحاسبة", en:"Accounting Templates" },
                  { ar:"مجتمع المستخدمين", en:"User Community" },
                  { ar:"شريك ZATCA",      en:"ZATCA Partner" },
                ],
              },
            ].map(col => (
              <div key={col.title_ar}>
                <h4 className="text-white font-bold mb-4">{isAr ? col.title_ar : col.title_en}</h4>
                <ul className="space-y-2">
                  {col.links.map(l => (
                    <li key={l.ar}>
                      <a href="#" className="text-sm text-gray-400 hover:text-white transition">
                        {isAr ? l.ar : l.en}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ))}

          </div>

          {/* Bottom bar */}
          <div className="border-t border-gray-800 pt-8 flex flex-col md:flex-row justify-between items-center gap-4">
            <div className="text-sm text-gray-500">
              © 2025 كليك بيلد — {isAr ? "جميع الحقوق محفوظة" : "All Rights Reserved"}
            </div>
            <div className="flex items-center gap-6 text-sm text-gray-500">
              <span>📞 8004330088</span>
              <span>✉️ support@clickbuild.com</span>
              <span>📍 {isAr ? "الرياض، المملكة العربية السعودية" : "Riyadh, Saudi Arabia"}</span>
            </div>
            <div className="flex gap-4 text-xs text-gray-600">
              <a href="#" className="hover:text-white transition">{isAr ? "الشروط والأحكام" : "Terms"}</a>
              <a href="#" className="hover:text-white transition">{isAr ? "سياسة الخصوصية" : "Privacy"}</a>
            </div>
          </div>
        </div>
      </footer>

    </div>
  );
}
'''

upload('/opt/clickbuild/frontend/src/app/[locale]/page.tsx', HOMEPAGE)

c.close()
print('\nDone! Now building...')
