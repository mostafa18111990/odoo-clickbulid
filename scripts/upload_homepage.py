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
    print(f'  uploaded: {path}')

def run(cmd, timeout=60):
    print(f'\n$ {cmd[:100]}')
    _, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode('utf-8', errors='replace').strip()
    err = e.read().decode('utf-8', errors='replace').strip()
    if out: print(out[:2000])
    if err and not out: print(f'[err] {err[:500]}')
    return out

# ─────────────────────────────────────────────────────────────────────────────
# PAGE 1: HOMEPAGE
# ─────────────────────────────────────────────────────────────────────────────
HOMEPAGE = '''import Link from "next/link";

export const metadata = {
  title: "ClickBuild — نظام التشغيل للمقاولات والصناعات | Industry OS",
  description: "منصة SaaS متخصصة للمقاولات والتجزئة والتصنيع مبنية على Odoo Enterprise مع دعم ZATCA",
};

const INDUSTRIES = [
  { icon: "🏗️", ar: "المقاولات",      en: "Construction",   key: "construction", color: "from-orange-500 to-amber-600", badge: "الأكثر طلباً" },
  { icon: "🛒", ar: "التجزئة",        en: "Retail",          key: "retail",        color: "from-blue-500 to-cyan-600",   badge: "" },
  { icon: "🏭", ar: "التصنيع",        en: "Manufacturing",   key: "manufacturing", color: "from-slate-600 to-gray-700",  badge: "" },
  { icon: "🏥", ar: "الرعاية الصحية", en: "Healthcare",      key: "healthcare",    color: "from-green-500 to-emerald-600", badge: "" },
  { icon: "🏢", ar: "العقارات",       en: "Real Estate",     key: "realestate",    color: "from-purple-500 to-violet-600", badge: "" },
  { icon: "🏨", ar: "الضيافة",        en: "Hospitality",     key: "hospitality",   color: "from-rose-500 to-pink-600",   badge: "" },
  { icon: "🚚", ar: "اللوجستيات",    en: "Logistics",        key: "logistics",     color: "from-yellow-500 to-orange-500", badge: "" },
  { icon: "💼", ar: "الخدمات",        en: "Services",        key: "services",      color: "from-teal-500 to-cyan-600",   badge: "" },
];

const CONSTRUCTION_FEATURES = [
  { icon: "📐", ar: "جداول الكميات BOQ",    en: "Bill of Quantities",   desc_ar: "استخراج BOQ بالذكاء الاصطناعي من ملفات المناقصات العربية", desc_en: "AI-powered BOQ extraction from Arabic tender docs" },
  { icon: "📋", ar: "المناقصات والتسعير",   en: "Tender Management",    desc_ar: "تحليل المناقصات وتسعير العروض باستخدام الذكاء الاصطناعي",    desc_en: "Analyze tenders and price offers with AI assistance" },
  { icon: "💰", ar: "مستخلصات الأعمال",     en: "Progress Billing",     desc_ar: "مستخلصات شهرية مع إدارة المستحقات والضمانات",                desc_en: "Monthly valuations with retention management" },
  { icon: "🏗️", ar: "إدارة المواقع",        en: "Site Operations",      desc_ar: "تقارير يومية وصور المواقع وإدارة العمالة والمعدات",          desc_en: "Daily reports, site photos, workforce & equipment" },
  { icon: "🤝", ar: "المقاولون الفرعيون",   en: "Subcontractors",       desc_ar: "تأهيل وإدارة وتسوية حسابات المقاولين الفرعيين",             desc_en: "Qualify, manage and settle subcontractors" },
  { icon: "📊", ar: "ربحية المشاريع",       en: "Project Profitability", desc_ar: "P&L لحظي لكل مشروع مع توقعات التكلفة والتدفق النقدي",    desc_en: "Real-time P&L per project with cost forecasting" },
];

export default async function HomePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  const isAr = locale === "ar";

  return (
    <main className="min-h-screen bg-white" dir={isAr ? "rtl" : "ltr"}>

      {/* Navbar */}
      <nav className="sticky top-0 z-50 bg-white/95 backdrop-blur-md border-b border-gray-100 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-gradient-to-br from-orange-500 to-amber-600 rounded-xl flex items-center justify-center">
              <span className="text-white font-black text-sm">CB</span>
            </div>
            <span className="text-xl font-black text-gray-900">ClickBuild</span>
            <span className="hidden sm:block text-xs bg-orange-100 text-orange-700 px-2 py-0.5 rounded-full font-semibold">
              {isAr ? "Industry OS" : "Industry OS"}
            </span>
          </div>
          <div className="hidden md:flex items-center gap-6 text-sm text-gray-600">
            <a href="#industries" className="hover:text-gray-900 transition">{isAr ? "الصناعات" : "Industries"}</a>
            <a href="#construction" className="hover:text-gray-900 transition">{isAr ? "المقاولات" : "Construction"}</a>
            <Link href={`/${locale}/pricing`} className="hover:text-gray-900 transition">{isAr ? "الأسعار" : "Pricing"}</Link>
          </div>
          <div className="flex gap-2">
            <Link href={`/${locale}/login`}
              className="text-gray-600 hover:text-gray-900 px-4 py-2 rounded-lg transition text-sm hidden sm:block">
              {isAr ? "دخول" : "Login"}
            </Link>
            <Link href={`/${locale}/onboarding`}
              className="bg-gradient-to-r from-orange-500 to-amber-600 text-white px-5 py-2 rounded-xl hover:opacity-90 transition text-sm font-bold shadow-lg shadow-orange-200">
              {isAr ? "🚀 ابدأ مجاناً" : "🚀 Start Free"}
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative overflow-hidden bg-gradient-to-br from-gray-950 via-gray-900 to-gray-800 text-white">
        <div className="absolute inset-0 opacity-5"
          style={{backgroundImage:"radial-gradient(circle at 25% 25%, #f97316 0%, transparent 50%), radial-gradient(circle at 75% 75%, #f59e0b 0%, transparent 50%)"}} />
        <div className="relative max-w-7xl mx-auto px-4 py-24 md:py-32">
          <div className="max-w-4xl mx-auto text-center">
            <div className="inline-flex items-center gap-2 bg-orange-500/20 border border-orange-500/30 text-orange-300 text-sm px-4 py-2 rounded-full mb-8">
              <span>🏗️</span>
              <span>{isAr ? "متخصص في المقاولات والصناعات السعودية" : "Specialized for Saudi Construction & Industries"}</span>
            </div>
            <h1 className="text-5xl md:text-7xl font-black mb-6 leading-tight">
              {isAr ? "نظام التشغيل " : "The Operating System "}
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-orange-400 to-amber-400">
                {isAr ? "لشركتك" : "for Your Industry"}
              </span>
            </h1>
            <p className="text-xl md:text-2xl text-gray-300 max-w-3xl mx-auto mb-6 leading-relaxed">
              {isAr
                ? "ليس ERP عاماً. منصة متخصصة لكل صناعة مبنية على Odoo Enterprise مع دعم ZATCA ونظام حماية الأجور والفاتورة العربية"
                : "Not generic ERP. A specialized platform per industry built on Odoo Enterprise with ZATCA, WPS, and full Arabic support"}
            </p>
            <div className="flex flex-wrap gap-2 justify-center mb-10 text-sm">
              {["✅ ZATCA & ضريبة القيمة المضافة","✅ واجهة عربية RTL","✅ نظام حماية الأجور WPS","✅ تجهيز في 5 دقائق"].map(t => (
                <span key={t} className="bg-white/10 text-gray-300 px-3 py-1 rounded-full">{t}</span>
              ))}
            </div>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link href={`/${locale}/onboarding`}
                className="bg-gradient-to-r from-orange-500 to-amber-500 text-white font-black px-10 py-5 rounded-2xl text-xl hover:opacity-90 transition shadow-2xl shadow-orange-500/30">
                {isAr ? "🏗️ اختر صناعتك وابدأ" : "🏗️ Choose Your Industry"}
              </Link>
              <a href="#construction"
                className="border border-white/20 text-white px-10 py-5 rounded-2xl text-xl hover:bg-white/10 transition">
                {isAr ? "عرض نظام المقاولات" : "See Construction OS"}
              </a>
            </div>
            <p className="text-gray-400 text-sm mt-4">
              {isAr ? "14 يوم تجريبي مجاني • لا يلزم بطاقة ائتمان • تجهيز فوري" : "14-day free trial • No credit card • Instant setup"}
            </p>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-6 max-w-3xl mx-auto mt-20 pt-10 border-t border-white/10">
            {[
              { v: "8", l: isAr ? "صناعة متخصصة" : "Industries",   icon: "🏭" },
              { v: "99.95%", l: isAr ? "ضمان التشغيل" : "Uptime",  icon: "⚡" },
              { v: isAr ? "٥ د" : "5 min", l: isAr ? "وقت التجهيز" : "Setup Time", icon: "🚀" },
              { v: "SAR", l: isAr ? "تسعير بالريال" : "Pricing",    icon: "🇸🇦" },
            ].map(s => (
              <div key={s.l} className="text-center">
                <div className="text-2xl mb-1">{s.icon}</div>
                <div className="text-2xl md:text-3xl font-black text-orange-400">{s.v}</div>
                <div className="text-gray-400 text-xs mt-1">{s.l}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Industries Grid */}
      <section id="industries" className="py-24 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4">
          <div className="text-center mb-16">
            <h2 className="text-4xl md:text-5xl font-black text-gray-900 mb-4">
              {isAr ? "اختر صناعتك" : "Choose Your Industry"}
            </h2>
            <p className="text-gray-500 text-xl max-w-2xl mx-auto">
              {isAr
                ? "كل صناعة لها نظام مخصص بالوحدات والأدوات والتقارير المناسبة لها تماماً"
                : "Each industry gets a dedicated system with the right modules, tools, and reports"}
            </p>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {INDUSTRIES.map(ind => (
              <Link key={ind.key} href={`/${locale}/onboarding?industry=${ind.key}`}
                className="group relative bg-white rounded-2xl p-6 border-2 border-gray-100 hover:border-orange-300 hover:shadow-xl hover:-translate-y-1 transition-all duration-200 text-center">
                {ind.badge && (
                  <span className="absolute -top-2 left-1/2 -translate-x-1/2 bg-orange-500 text-white text-xs px-2 py-0.5 rounded-full font-bold whitespace-nowrap">
                    {ind.badge}
                  </span>
                )}
                <div className={`w-14 h-14 rounded-2xl bg-gradient-to-br ${ind.color} flex items-center justify-center text-2xl mx-auto mb-4 shadow-lg group-hover:scale-110 transition-transform`}>
                  {ind.icon}
                </div>
                <h3 className="font-black text-gray-900 text-lg">{isAr ? ind.ar : ind.en}</h3>
                <p className="text-orange-600 text-xs mt-2 font-medium opacity-0 group-hover:opacity-100 transition-opacity">
                  {isAr ? "ابدأ الآن ←" : "Start Now →"}
                </p>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* Construction OS */}
      <section id="construction" className="py-24 bg-white">
        <div className="max-w-7xl mx-auto px-4">
          <div className="flex flex-col lg:flex-row gap-16 items-center">
            <div className="lg:w-1/2">
              <div className="inline-flex items-center gap-2 bg-orange-100 text-orange-700 text-sm px-4 py-2 rounded-full mb-6 font-semibold">
                🏗️ {isAr ? "Construction OS — نظام التشغيل للمقاولات" : "Construction OS"}
              </div>
              <h2 className="text-4xl md:text-5xl font-black text-gray-900 mb-6 leading-tight">
                {isAr ? "كل ما تحتاجه " : "Everything a "}
                <span className="text-orange-500">{isAr ? "شركة المقاولات" : "Construction Company"}</span>
                {isAr ? "" : " Needs"}
              </h2>
              <p className="text-gray-600 text-lg mb-8 leading-relaxed">
                {isAr
                  ? "من BOQ المناقصة إلى المستخلص الأخير — نظام متكامل مصمم خصيصاً لشركات المقاولات السعودية مع دعم ZATCA ونظام حماية الأجور"
                  : "From tender BOQ to final invoice — a complete system designed for Saudi construction companies with ZATCA and WPS support"}
              </p>
              <div className="flex flex-wrap gap-4">
                <Link href={`/${locale}/onboarding?industry=construction`}
                  className="bg-gradient-to-r from-orange-500 to-amber-600 text-white font-bold px-8 py-4 rounded-xl hover:opacity-90 transition shadow-lg shadow-orange-200">
                  {isAr ? "ابدأ Construction OS" : "Start Construction OS"}
                </Link>
                <Link href={`/${locale}/pricing`}
                  className="border-2 border-orange-500 text-orange-600 font-bold px-8 py-4 rounded-xl hover:bg-orange-50 transition">
                  {isAr ? "الأسعار" : "View Pricing"}
                </Link>
              </div>
            </div>
            <div className="lg:w-1/2 grid grid-cols-2 gap-4">
              {CONSTRUCTION_FEATURES.map(f => (
                <div key={f.en} className="bg-gradient-to-br from-orange-50 to-amber-50 border border-orange-100 rounded-2xl p-5 hover:shadow-md transition">
                  <div className="text-3xl mb-3">{f.icon}</div>
                  <h3 className="font-black text-gray-900 mb-1 text-sm">{isAr ? f.ar : f.en}</h3>
                  <p className="text-gray-500 text-xs">{isAr ? f.desc_ar : f.desc_en}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Why ClickBuild */}
      <section className="py-24 bg-gray-950 text-white">
        <div className="max-w-7xl mx-auto px-4">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-black mb-4">{isAr ? "لماذا ClickBuild؟" : "Why ClickBuild?"}</h2>
            <p className="text-gray-400 text-xl">{isAr ? "ليس مجرد Odoo — منصة صناعية متكاملة" : "Not just Odoo — a complete industry platform"}</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {[
              { icon:"🇸🇦", ar:"متوافق 100% مع السوق السعودي", en:"100% Saudi Compliant", d_ar:"ZATCA، ضريبة القيمة المضافة، نظام حماية الأجور، اللوائح العمالية", d_en:"ZATCA, VAT, WPS, Saudi labor regulations" },
              { icon:"🤖", ar:"ذكاء اصطناعي متكامل", en:"Native AI Built-in", d_ar:"تحليل المناقصات، OCR عربي، توقعات التكلفة، مساعد المحاسبة", d_en:"Tender analysis, Arabic OCR, cost forecasting, AI assistant" },
              { icon:"⚡", ar:"جاهز في 5 دقائق", en:"Ready in 5 Minutes", d_ar:"من التسجيل إلى نظام كامل مع كل الوحدات جاهزة للاستخدام", d_en:"From signup to a fully configured industry system" },
              { icon:"🔒", ar:"أمان مؤسسي", en:"Enterprise Security", d_ar:"عزل كامل للبيانات، تشفير، نسخ احتياطي، اتفاقية SLA 99.95%", d_en:"Full data isolation, encryption, backup, 99.95% SLA" },
            ].map(item => (
              <div key={item.en} className="bg-white/5 border border-white/10 rounded-2xl p-6 hover:bg-white/10 transition">
                <div className="text-4xl mb-4">{item.icon}</div>
                <h3 className="font-black text-white text-lg mb-2">{isAr ? item.ar : item.en}</h3>
                <p className="text-gray-400 text-sm leading-relaxed">{isAr ? item.d_ar : item.d_en}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing Teaser */}
      <section className="py-24 bg-white">
        <div className="max-w-5xl mx-auto px-4 text-center">
          <h2 className="text-4xl font-black text-gray-900 mb-4">
            {isAr ? "أسعار بالريال السعودي" : "Pricing in Saudi Riyal"}
          </h2>
          <p className="text-gray-500 text-xl mb-12">
            {isAr ? "لا رسوم مخفية • 14 يوم تجريبي مجاني • إلغاء في أي وقت" : "No hidden fees • 14-day free trial • Cancel anytime"}
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
            {[
              { name: isAr?"مبتدئ":"Starter",      price:"299",   users:isAr?"١٠ مستخدمين":"10 users",  popular:false },
              { name: isAr?"احترافي":"Professional", price:"899",   users:isAr?"٥٠ مستخدماً":"50 users",  popular:true  },
              { name: isAr?"مؤسسي":"Enterprise",    price:"2,499", users:isAr?"غير محدود":"Unlimited",  popular:false },
            ].map(p => (
              <div key={p.name} className={`relative border-2 rounded-2xl p-8 ${p.popular ? "border-orange-400 shadow-xl shadow-orange-100" : "border-gray-200"}`}>
                {p.popular && (
                  <span className="absolute -top-3 left-1/2 -translate-x-1/2 bg-orange-500 text-white text-xs px-4 py-1 rounded-full font-bold whitespace-nowrap">
                    {isAr ? "⭐ الأكثر شعبية" : "⭐ Most Popular"}
                  </span>
                )}
                <h3 className="text-xl font-black text-gray-900 mb-2">{p.name}</h3>
                <div className="text-4xl font-black text-orange-500 mb-1">
                  {p.price} <span className="text-lg text-gray-400 font-normal">{isAr?"ر.س/شهر":"SAR/mo"}</span>
                </div>
                <div className="text-gray-500 text-sm mb-6">👥 {p.users}</div>
                <Link href={`/${locale}/onboarding`}
                  className={`block w-full py-3 rounded-xl font-bold text-center transition ${
                    p.popular ? "bg-orange-500 text-white hover:bg-orange-600" : "border-2 border-gray-200 text-gray-700 hover:border-orange-300 hover:text-orange-600"
                  }`}>
                  {isAr ? "ابدأ الآن" : "Get Started"}
                </Link>
              </div>
            ))}
          </div>
          <Link href={`/${locale}/pricing`}
            className="inline-flex items-center gap-2 text-orange-600 font-bold hover:text-orange-700 transition">
            {isAr ? "مقارنة تفصيلية لجميع الباقات ←" : "Full detailed plan comparison →"}
          </Link>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24 bg-gradient-to-r from-orange-500 to-amber-600 text-white">
        <div className="max-w-3xl mx-auto px-4 text-center">
          <h2 className="text-4xl md:text-5xl font-black mb-6">
            {isAr ? "ابدأ اليوم مجاناً" : "Start Free Today"}
          </h2>
          <p className="text-orange-100 text-xl mb-10">
            {isAr
              ? "اختر صناعتك وسيتم تجهيز نظامك الكامل في أقل من 5 دقائق"
              : "Choose your industry and your complete system will be ready in under 5 minutes"}
          </p>
          <Link href={`/${locale}/onboarding`}
            className="inline-block bg-white text-orange-600 font-black px-12 py-5 rounded-2xl text-xl hover:bg-orange-50 transition shadow-2xl">
            {isAr ? "🏗️ اختر صناعتك الآن" : "🏗️ Choose Your Industry Now"}
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-gray-900 text-gray-400 py-12">
        <div className="max-w-7xl mx-auto px-4">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6 mb-8">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 bg-gradient-to-br from-orange-500 to-amber-600 rounded-xl flex items-center justify-center">
                <span className="text-white font-black text-sm">CB</span>
              </div>
              <span className="text-white font-black text-xl">ClickBuild</span>
            </div>
            <div className="flex gap-6 text-sm">
              <Link href={`/${locale}/pricing`} className="hover:text-white transition">{isAr ? "الأسعار" : "Pricing"}</Link>
              <Link href={`/${locale}/login`} className="hover:text-white transition">{isAr ? "دخول" : "Login"}</Link>
              <Link href={`/${locale}/register`} className="hover:text-white transition">{isAr ? "تسجيل" : "Register"}</Link>
            </div>
          </div>
          <div className="border-t border-white/10 pt-6 flex flex-col md:flex-row items-center justify-between gap-4 text-sm">
            <span>© 2025 ClickBuild. {isAr ? "جميع الحقوق محفوظة" : "All rights reserved."}</span>
            <div className="flex gap-4 text-xs">
              <span>🇸🇦 {isAr ? "متوافق مع ZATCA" : "ZATCA Compliant"}</span>
              <span>🔒 SOC2 Ready</span>
              <span>⚡ SLA 99.95%</span>
            </div>
          </div>
        </div>
      </footer>
    </main>
  );
}
'''

upload('/opt/clickbuild/frontend/src/app/[locale]/page.tsx', HOMEPAGE)
print('✅ Homepage uploaded')

# ─────────────────────────────────────────────────────────────────────────────
# PAGE 2: ONBOARDING — 6-step Industry Wizard
# ─────────────────────────────────────────────────────────────────────────────
ONBOARDING = '''"use client";
import { useState, useEffect } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useAuthStore } from "@/store/auth";
import { api } from "@/lib/api";

const INDUSTRIES = [
  { key:"construction",  icon:"🏗️", ar:"المقاولات",       en:"Construction",   color:"from-orange-500 to-amber-600",  desc_ar:"مقاولات عامة، مقاولات فرعية، صيانة",    desc_en:"General contractor, subcontractor, maintenance" },
  { key:"retail",        icon:"🛒", ar:"التجزئة",         en:"Retail",          color:"from-blue-500 to-cyan-600",     desc_ar:"محلات، سوبر ماركت، متاجر إلكترونية",    desc_en:"Stores, supermarkets, eCommerce" },
  { key:"manufacturing", icon:"🏭", ar:"التصنيع",         en:"Manufacturing",   color:"from-slate-600 to-gray-700",    desc_ar:"تصنيع، إنتاج، تجميع",                    desc_en:"Manufacturing, production, assembly" },
  { key:"healthcare",    icon:"🏥", ar:"الرعاية الصحية",  en:"Healthcare",      color:"from-green-500 to-emerald-600", desc_ar:"عيادات، مستشفيات، مراكز طبية",          desc_en:"Clinics, hospitals, medical centers" },
  { key:"realestate",    icon:"🏢", ar:"العقارات",        en:"Real Estate",     color:"from-purple-500 to-violet-600", desc_ar:"تطوير عقاري، إدارة وحدات، وساطة",       desc_en:"Development, property management, brokerage" },
  { key:"hospitality",   icon:"🏨", ar:"الضيافة",         en:"Hospitality",     color:"from-rose-500 to-pink-600",     desc_ar:"فنادق، منتجعات، شقق مفروشة",            desc_en:"Hotels, resorts, serviced apartments" },
  { key:"logistics",     icon:"🚚", ar:"اللوجستيات",     en:"Logistics",        color:"from-yellow-500 to-orange-500", desc_ar:"نقل، شحن، توزيع، مستودعات",             desc_en:"Transport, freight, distribution, warehousing" },
  { key:"services",      icon:"💼", ar:"الخدمات المهنية", en:"Professional Svc",color:"from-teal-500 to-cyan-600",     desc_ar:"استشارات، محاسبة، قانون، تقنية",        desc_en:"Consulting, accounting, legal, IT" },
];

const BUSINESS_TYPES = {
  construction: [
    { key:"general_contractor", ar:"مقاول عام",          en:"General Contractor" },
    { key:"subcontractor",      ar:"مقاول فرعي",          en:"Subcontractor" },
    { key:"maintenance",        ar:"شركة صيانة",          en:"Maintenance Company" },
    { key:"interior_design",    ar:"تصميم داخلي",         en:"Interior Design" },
    { key:"infrastructure",     ar:"مقاول بنية تحتية",   en:"Infrastructure Contractor" },
    { key:"real_estate_dev",    ar:"مقاول تطوير عقاري",  en:"Real Estate Developer" },
  ],
  retail: [
    { key:"store",          ar:"متجر",              en:"Retail Store" },
    { key:"supermarket",    ar:"سوبر ماركت",        en:"Supermarket" },
    { key:"ecommerce",      ar:"تجارة إلكترونية",   en:"eCommerce" },
    { key:"franchise",      ar:"امتياز تجاري",       en:"Franchise" },
  ],
  manufacturing: [
    { key:"light_mfg",   ar:"تصنيع خفيف",        en:"Light Manufacturing" },
    { key:"heavy_mfg",   ar:"تصنيع ثقيل",        en:"Heavy Manufacturing" },
    { key:"food_mfg",    ar:"تصنيع غذائي",       en:"Food Manufacturing" },
    { key:"assembly",    ar:"تجميع",              en:"Assembly" },
  ],
  healthcare: [
    { key:"clinic",       ar:"عيادة",             en:"Clinic" },
    { key:"hospital",     ar:"مستشفى",            en:"Hospital" },
    { key:"lab",          ar:"مختبر",             en:"Medical Lab" },
    { key:"pharmacy",     ar:"صيدلية",            en:"Pharmacy" },
  ],
  realestate: [
    { key:"developer",    ar:"مطور عقاري",        en:"Developer" },
    { key:"management",   ar:"إدارة عقارات",      en:"Property Management" },
    { key:"brokerage",    ar:"وساطة عقارية",      en:"Brokerage" },
  ],
  hospitality: [
    { key:"hotel",        ar:"فندق",              en:"Hotel" },
    { key:"resort",       ar:"منتجع",             en:"Resort" },
    { key:"apartments",   ar:"شقق مفروشة",        en:"Serviced Apartments" },
  ],
  logistics: [
    { key:"transport",    ar:"نقل وشحن",          en:"Transport & Freight" },
    { key:"warehouse",    ar:"مستودعات",          en:"Warehousing" },
    { key:"courier",      ar:"توصيل",             en:"Last-Mile Delivery" },
  ],
  services: [
    { key:"consulting",   ar:"استشارات",          en:"Consulting" },
    { key:"accounting",   ar:"محاسبة وتدقيق",    en:"Accounting & Audit" },
    { key:"it_services",  ar:"خدمات تقنية",       en:"IT Services" },
    { key:"legal",        ar:"خدمات قانونية",     en:"Legal Services" },
  ],
};

const PACKAGES = {
  construction: [
    {
      tier:"starter", price:299,
      ar:"مبتدئ", en:"Starter",
      users:10, storage:"20GB",
      modules_ar:["المحاسبة","المبيعات","المشتريات","المخزون","ZATCA","ضريبة القيمة المضافة","BOQ أساسي"],
      modules_en:["Accounting","Sales","Purchase","Inventory","ZATCA","VAT","Basic BOQ"],
    },
    {
      tier:"professional", price:899, popular:true,
      ar:"احترافي", en:"Professional",
      users:50, storage:"100GB",
      modules_ar:["كل وحدات المبتدئ","BOQ متقدم","المناقصات","مستخلصات الأعمال","المقاولون الفرعيون","إدارة المواقع","المعدات","الموارد البشرية","تطبيق الجوال","ذكاء اصطناعي"],
      modules_en:["All Starter","Advanced BOQ","Tenders","Progress Billing","Subcontractors","Site Ops","Equipment","HR","Mobile App","AI Analysis"],
    },
    {
      tier:"enterprise", price:2499,
      ar:"مؤسسي", en:"Enterprise",
      users:-1, storage:"500GB",
      modules_ar:["كل شيء في الاحترافي","خوادم مخصصة","تكامل BIM","إدارة المشاريع المتعددة","خدمة حساب مدير","SLA 99.99%"],
      modules_en:["All Professional","Dedicated Server","BIM Integration","Multi-project","Dedicated CSM","99.99% SLA"],
    },
  ],
  retail: [
    { tier:"starter", price:199, ar:"مبتدئ", en:"Starter", users:5, storage:"10GB", modules_ar:["المحاسبة","نقاط البيع","المخزون","ZATCA"], modules_en:["Accounting","POS","Inventory","ZATCA"] },
    { tier:"professional", price:699, popular:true, ar:"احترافي", en:"Professional", users:25, storage:"50GB", modules_ar:["كل المبتدئ","ولاء العملاء","التجارة الإلكترونية","التسويق","الباركود"], modules_en:["All Starter","Loyalty","eCommerce","Marketing","Barcode"] },
    { tier:"enterprise", price:1999, ar:"مؤسسي", en:"Enterprise", users:-1, storage:"200GB", modules_ar:["كل الاحترافي","فروع متعددة","تكامل مع المورّدين","خوادم مخصصة"], modules_en:["All Professional","Multi-branch","Supplier Integration","Dedicated Server"] },
  ],
};

function getPackages(industry: string) {
  return PACKAGES[industry as keyof typeof PACKAGES] || PACKAGES.construction;
}

const SIZES = [
  { key:"startup",    ar:"شركة ناشئة",   en:"Startup",      desc_ar:"1-10 موظفين",   desc_en:"1-10 employees",   icon:"🌱" },
  { key:"small",      ar:"صغيرة",         en:"Small",         desc_ar:"11-50 موظفاً",  desc_en:"11-50 employees",  icon:"🏢" },
  { key:"medium",     ar:"متوسطة",        en:"Medium",        desc_ar:"51-200 موظف",   desc_en:"51-200 employees", icon:"🏗️" },
  { key:"enterprise", ar:"مؤسسة كبيرة",  en:"Enterprise",    desc_ar:"200+ موظف",     desc_en:"200+ employees",   icon:"🏭" },
];

export default function OnboardingPage() {
  const { locale } = useParams() as { locale: string };
  const isAr = locale === "ar";
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user } = useAuthStore();

  const [step, setStep] = useState(1);
  const [industry, setIndustry] = useState(searchParams.get("industry") || "");
  const [businessType, setBusinessType] = useState("");
  const [companySize, setCompanySize] = useState("");
  const [selectedPkg, setSelectedPkg] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [subdomain, setSubdomain] = useState("");
  const [checkResult, setCheckResult] = useState<{available:boolean} | null>(null);
  const [checking, setChecking] = useState(false);
  const [creating, setCreating] = useState(false);
  const [instanceId, setInstanceId] = useState("");
  const [instanceStatus, setInstanceStatus] = useState("provisioning");
  const [error, setError] = useState("");

  // Auto-advance if industry pre-selected from URL
  useEffect(() => {
    if (industry && step === 1) setStep(2);
  }, []);

  const totalSteps = 6;
  const progress = Math.round((step / totalSteps) * 100);

  async function checkSubdomain(sub: string) {
    if (!sub || sub.length < 3) return;
    setChecking(true);
    try {
      const r = await api.get(`/instances/check-subdomain/${sub}`);
      setCheckResult(r.data);
    } catch {
      setCheckResult({ available: false });
    } finally {
      setChecking(false);
    }
  }

  async function handleCreate() {
    if (!user) {
      router.push(`/${locale}/register?redirect=onboarding&industry=${industry}&package=${selectedPkg}`);
      return;
    }
    setCreating(true);
    setError("");
    try {
      const pkgs = getPackages(industry);
      const pkg = pkgs.find(p => p.tier === selectedPkg) || pkgs[1];
      const modules = (isAr ? pkg.modules_ar : pkg.modules_en).join(",");
      const r = await api.post("/instances/", {
        name: companyName || subdomain,
        subdomain,
        plan: selectedPkg,
        industry,
        business_type: businessType,
        company_size: companySize,
        modules,
      });
      setInstanceId(r.data.id);
      setStep(6);
      pollStatus(r.data.id);
    } catch (e: any) {
      setError(e.response?.data?.detail || (isAr ? "حدث خطأ. حاول مرة أخرى." : "An error occurred. Please try again."));
      setCreating(false);
    }
  }

  function pollStatus(id: string) {
    const interval = setInterval(async () => {
      try {
        const r = await api.get(`/instances/${id}`);
        setInstanceStatus(r.data.status);
        if (r.data.status === "running" || r.data.status === "RUNNING") {
          clearInterval(interval);
          setCreating(false);
        }
      } catch {}
    }, 5000);
    setTimeout(() => clearInterval(interval), 600000);
  }

  function IndustryIcon({ ind }: { ind: typeof INDUSTRIES[0] }) {
    return (
      <button
        onClick={() => { setIndustry(ind.key); setStep(2); }}
        className={`group relative bg-white rounded-2xl p-5 border-2 text-center transition-all duration-200 hover:shadow-lg hover:-translate-y-0.5
          ${industry === ind.key ? "border-orange-400 shadow-lg shadow-orange-100 bg-orange-50" : "border-gray-200 hover:border-orange-300"}`}>
        <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${ind.color} flex items-center justify-center text-xl mx-auto mb-3 shadow group-hover:scale-110 transition-transform`}>
          {ind.icon}
        </div>
        <h3 className="font-black text-gray-900 text-sm">{isAr ? ind.ar : ind.en}</h3>
        <p className="text-gray-400 text-xs mt-1">{isAr ? ind.desc_ar : ind.desc_en}</p>
      </button>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50" dir={isAr ? "rtl" : "ltr"}>
      {/* Header */}
      <div className="bg-white border-b border-gray-100 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-gradient-to-br from-orange-500 to-amber-600 rounded-lg flex items-center justify-center">
            <span className="text-white font-black text-xs">CB</span>
          </div>
          <span className="font-black text-gray-900">ClickBuild</span>
        </div>
        <div className="text-sm text-gray-500">
          {isAr ? `الخطوة ${step} من ${totalSteps}` : `Step ${step} of ${totalSteps}`}
        </div>
      </div>

      {/* Progress Bar */}
      <div className="h-1 bg-gray-200">
        <div
          className="h-full bg-gradient-to-r from-orange-500 to-amber-500 transition-all duration-500"
          style={{ width: `${progress}%` }}
        />
      </div>

      <div className="max-w-4xl mx-auto px-4 py-10">

        {/* STEP 1: Industry */}
        {step === 1 && (
          <div>
            <div className="text-center mb-10">
              <h1 className="text-3xl md:text-4xl font-black text-gray-900 mb-3">
                {isAr ? "ما هي صناعتك؟" : "What is your industry?"}
              </h1>
              <p className="text-gray-500 text-lg">
                {isAr ? "سنختار لك النظام المناسب تماماً" : "We will configure the perfect system for you"}
              </p>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {INDUSTRIES.map(ind => <IndustryIcon key={ind.key} ind={ind} />)}
            </div>
          </div>
        )}

        {/* STEP 2: Business Type */}
        {step === 2 && (
          <div>
            <button onClick={() => setStep(1)} className="mb-6 text-gray-400 hover:text-gray-600 flex items-center gap-2 text-sm">
              ← {isAr ? "رجوع" : "Back"}
            </button>
            <div className="text-center mb-10">
              <div className={`w-14 h-14 rounded-2xl bg-gradient-to-br ${INDUSTRIES.find(i=>i.key===industry)?.color || "from-orange-500 to-amber-600"} flex items-center justify-center text-2xl mx-auto mb-4`}>
                {INDUSTRIES.find(i=>i.key===industry)?.icon}
              </div>
              <h1 className="text-3xl font-black text-gray-900 mb-3">
                {isAr ? "ما نوع نشاطك التجاري؟" : "What type of business?"}
              </h1>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              {(BUSINESS_TYPES[industry as keyof typeof BUSINESS_TYPES] || []).map(bt => (
                <button key={bt.key}
                  onClick={() => { setBusinessType(bt.key); setStep(3); }}
                  className={`p-5 rounded-2xl border-2 text-center transition-all hover:shadow-md hover:-translate-y-0.5
                    ${businessType===bt.key ? "border-orange-400 bg-orange-50" : "border-gray-200 bg-white hover:border-orange-200"}`}>
                  <h3 className="font-bold text-gray-900">{isAr ? bt.ar : bt.en}</h3>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* STEP 3: Company Size */}
        {step === 3 && (
          <div>
            <button onClick={() => setStep(2)} className="mb-6 text-gray-400 hover:text-gray-600 flex items-center gap-2 text-sm">
              ← {isAr ? "رجوع" : "Back"}
            </button>
            <div className="text-center mb-10">
              <h1 className="text-3xl font-black text-gray-900 mb-3">
                {isAr ? "ما حجم شركتك؟" : "What is your company size?"}
              </h1>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {SIZES.map(sz => (
                <button key={sz.key}
                  onClick={() => { setCompanySize(sz.key); setStep(4); }}
                  className={`p-6 rounded-2xl border-2 text-center transition-all hover:shadow-md hover:-translate-y-0.5
                    ${companySize===sz.key ? "border-orange-400 bg-orange-50" : "border-gray-200 bg-white hover:border-orange-200"}`}>
                  <div className="text-4xl mb-3">{sz.icon}</div>
                  <h3 className="font-black text-gray-900">{isAr ? sz.ar : sz.en}</h3>
                  <p className="text-gray-400 text-xs mt-1">{isAr ? sz.desc_ar : sz.desc_en}</p>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* STEP 4: AI Recommendation + Package Selection */}
        {step === 4 && (
          <div>
            <button onClick={() => setStep(3)} className="mb-6 text-gray-400 hover:text-gray-600 flex items-center gap-2 text-sm">
              ← {isAr ? "رجوع" : "Back"}
            </button>
            <div className="text-center mb-6">
              <div className="inline-flex items-center gap-2 bg-orange-100 text-orange-700 px-4 py-2 rounded-full text-sm font-semibold mb-4">
                🤖 {isAr ? "توصية الذكاء الاصطناعي" : "AI Recommendation"}
              </div>
              <h1 className="text-3xl font-black text-gray-900 mb-3">
                {isAr ? "اختر الباقة المناسبة" : "Choose Your Package"}
              </h1>
              <p className="text-gray-500">
                {isAr
                  ? `بناءً على: ${INDUSTRIES.find(i=>i.key===industry)?.ar} • ${SIZES.find(s=>s.key===companySize)?.ar}`
                  : `Based on: ${INDUSTRIES.find(i=>i.key===industry)?.en} • ${SIZES.find(s=>s.key===companySize)?.en}`}
              </p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {getPackages(industry).map(pkg => (
                <div key={pkg.tier}
                  className={`relative rounded-2xl border-2 p-6 transition-all cursor-pointer hover:shadow-lg hover:-translate-y-0.5
                    ${selectedPkg===pkg.tier ? "border-orange-400 shadow-xl shadow-orange-100 bg-orange-50" : pkg.popular ? "border-orange-300 shadow-md" : "border-gray-200 bg-white"}`}
                  onClick={() => setSelectedPkg(pkg.tier)}>
                  {pkg.popular && (
                    <span className="absolute -top-3 left-1/2 -translate-x-1/2 bg-orange-500 text-white text-xs px-3 py-1 rounded-full font-bold whitespace-nowrap">
                      {isAr ? "⭐ موصى به" : "⭐ Recommended"}
                    </span>
                  )}
                  <h3 className="font-black text-gray-900 text-xl mb-1">{isAr ? pkg.ar : pkg.en}</h3>
                  <div className="text-3xl font-black text-orange-500 mb-1">
                    {pkg.price} <span className="text-sm text-gray-400 font-normal">{isAr ? "ر.س/شهر" : "SAR/mo"}</span>
                  </div>
                  <div className="text-gray-500 text-sm mb-4">
                    👥 {pkg.users === -1 ? (isAr ? "غير محدود" : "Unlimited") : `${pkg.users} ${isAr ? "مستخدم" : "users"}`}
                    &nbsp;•&nbsp;💾 {pkg.storage}
                  </div>
                  <ul className="space-y-1">
                    {(isAr ? pkg.modules_ar : pkg.modules_en).slice(0,5).map(m => (
                      <li key={m} className="text-sm text-gray-600 flex items-center gap-2">
                        <span className="text-green-500 text-xs">✓</span> {m}
                      </li>
                    ))}
                    {(isAr ? pkg.modules_ar : pkg.modules_en).length > 5 && (
                      <li className="text-xs text-orange-600 font-medium">
                        +{(isAr ? pkg.modules_ar : pkg.modules_en).length - 5} {isAr ? "وحدة أخرى" : "more modules"}
                      </li>
                    )}
                  </ul>
                  <div className={`mt-4 py-2 rounded-xl text-center text-sm font-bold transition
                    ${selectedPkg===pkg.tier ? "bg-orange-500 text-white" : "border border-gray-200 text-gray-600"}`}>
                    {selectedPkg===pkg.tier ? (isAr ? "✓ تم الاختيار" : "✓ Selected") : (isAr ? "اختر" : "Select")}
                  </div>
                </div>
              ))}
            </div>
            {selectedPkg && (
              <div className="text-center mt-8">
                <button onClick={() => setStep(5)}
                  className="bg-gradient-to-r from-orange-500 to-amber-600 text-white font-black px-12 py-4 rounded-2xl text-lg hover:opacity-90 transition shadow-xl shadow-orange-200">
                  {isAr ? "التالي: تفاصيل شركتك ←" : "Next: Your Company Details →"}
                </button>
              </div>
            )}
          </div>
        )}

        {/* STEP 5: Company Details + Subdomain */}
        {step === 5 && (
          <div className="max-w-xl mx-auto">
            <button onClick={() => setStep(4)} className="mb-6 text-gray-400 hover:text-gray-600 flex items-center gap-2 text-sm">
              ← {isAr ? "رجوع" : "Back"}
            </button>
            <div className="text-center mb-8">
              <h1 className="text-3xl font-black text-gray-900 mb-3">
                {isAr ? "بيانات شركتك" : "Your Company Details"}
              </h1>
              <p className="text-gray-500">{isAr ? "خطوة أخيرة قبل التشغيل" : "One last step before launch"}</p>
            </div>
            <div className="bg-white rounded-2xl border border-gray-200 p-8 space-y-6">
              <div>
                <label className="block text-sm font-bold text-gray-700 mb-2">
                  {isAr ? "اسم الشركة" : "Company Name"}
                </label>
                <input
                  value={companyName}
                  onChange={e => setCompanyName(e.target.value)}
                  placeholder={isAr ? "مثال: شركة العمران للمقاولات" : "e.g. Al Umran Contracting"}
                  className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-400"
                />
              </div>
              <div>
                <label className="block text-sm font-bold text-gray-700 mb-2">
                  {isAr ? "اسم النطاق الفرعي (الرابط)" : "Subdomain (URL)"}
                </label>
                <div className="flex items-center gap-2">
                  <input
                    value={subdomain}
                    onChange={e => {
                      const v = e.target.value.toLowerCase().replace(/[^a-z0-9-]/g,"");
                      setSubdomain(v);
                      setCheckResult(null);
                      if (v.length >= 3) checkSubdomain(v);
                    }}
                    placeholder="yourcompany"
                    className="flex-1 px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-400 font-mono"
                  />
                  <span className="text-gray-400 text-sm whitespace-nowrap">.odoo.clickbulid.com</span>
                </div>
                {checking && <p className="text-sm text-gray-400 mt-1">{isAr ? "جاري التحقق..." : "Checking..."}</p>}
                {checkResult && (
                  <p className={`text-sm mt-1 font-medium ${checkResult.available ? "text-green-600" : "text-red-500"}`}>
                    {checkResult.available
                      ? (isAr ? "✅ متاح" : "✅ Available")
                      : (isAr ? "❌ مستخدم بالفعل" : "❌ Already taken")}
                  </p>
                )}
              </div>
              {error && <p className="text-red-500 text-sm bg-red-50 px-4 py-3 rounded-xl">{error}</p>}
              <button
                onClick={handleCreate}
                disabled={!subdomain || !companyName || creating || (checkResult !== null && !checkResult.available)}
                className="w-full bg-gradient-to-r from-orange-500 to-amber-600 text-white font-black py-4 rounded-xl text-lg hover:opacity-90 transition shadow-lg disabled:opacity-50 disabled:cursor-not-allowed">
                {creating
                  ? (isAr ? "⏳ جاري الإنشاء..." : "⏳ Creating...")
                  : (isAr ? "🚀 إنشاء النظام الآن" : "🚀 Create System Now")}
              </button>
              <p className="text-center text-xs text-gray-400">
                {isAr ? "بالنقر فوق إنشاء، أنت توافق على شروط الاستخدام" : "By clicking Create, you agree to our Terms of Service"}
              </p>
            </div>
          </div>
        )}

        {/* STEP 6: Provisioning */}
        {step === 6 && (
          <div className="max-w-xl mx-auto text-center">
            <div className="mb-8">
              {instanceStatus === "running" || instanceStatus === "RUNNING" ? (
                <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6">
                  <span className="text-4xl">✅</span>
                </div>
              ) : (
                <div className="w-20 h-20 bg-orange-100 rounded-full flex items-center justify-center mx-auto mb-6 animate-pulse">
                  <span className="text-4xl">🚀</span>
                </div>
              )}
              <h1 className="text-3xl font-black text-gray-900 mb-3">
                {instanceStatus === "running" || instanceStatus === "RUNNING"
                  ? (isAr ? "🎉 نظامك جاهز!" : "🎉 Your System is Ready!")
                  : (isAr ? "جاري إنشاء نظامك..." : "Creating your system...")}
              </h1>
              <p className="text-gray-500">
                {instanceStatus === "running" || instanceStatus === "RUNNING"
                  ? (isAr ? "تم تجهيز نظامك بالكامل" : "Your system has been fully configured")
                  : (isAr ? "هذا يستغرق 3-5 دقائق. جميع الوحدات يتم تثبيتها..." : "This takes 3-5 minutes. All modules are being installed...")}
              </p>
            </div>

            {instanceStatus !== "running" && instanceStatus !== "RUNNING" && (
              <div className="bg-white rounded-2xl border border-gray-200 p-6 text-start space-y-3 mb-6">
                {[
                  { done: true,  ar: "تسجيل النطاق الفرعي",        en: "Subdomain registered" },
                  { done: true,  ar: "إصدار شهادة SSL",             en: "SSL certificate issued" },
                  { done: true,  ar: "إنشاء قاعدة البيانات",         en: "Database created" },
                  { done: false, ar: "تثبيت وحدات الصناعة",         en: "Installing industry modules" },
                  { done: false, ar: "تطبيق قالب الصناعة",           en: "Applying industry template" },
                  { done: false, ar: "إعداد ZATCA وضريبة القيمة المضافة", en: "Configuring ZATCA & VAT" },
                  { done: false, ar: "إنشاء حساب المدير",            en: "Creating admin account" },
                ].map((item, i) => (
                  <div key={i} className="flex items-center gap-3">
                    <span className={`text-sm ${item.done ? "text-green-500" : "text-orange-400 animate-pulse"}`}>
                      {item.done ? "✅" : "⏳"}
                    </span>
                    <span className={`text-sm ${item.done ? "text-gray-600" : "text-gray-400"}`}>
                      {isAr ? item.ar : item.en}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {(instanceStatus === "running" || instanceStatus === "RUNNING") && (
              <div className="space-y-4">
                <a href={`https://${subdomain}.odoo.clickbulid.com`} target="_blank"
                  className="block w-full bg-gradient-to-r from-orange-500 to-amber-600 text-white font-black py-5 rounded-2xl text-xl hover:opacity-90 transition shadow-xl">
                  🏗️ {isAr ? "افتح نظامك الآن" : "Open Your System Now"}
                </a>
                <p className="text-sm text-gray-500">
                  🔗 https://{subdomain}.odoo.clickbulid.com
                </p>
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  );
}
'''

upload('/opt/clickbuild/frontend/src/app/[locale]/onboarding/page.tsx', ONBOARDING)
print('✅ Onboarding wizard uploaded')

# ─────────────────────────────────────────────────────────────────────────────
# PAGE 3: PRICING — Industry-aware SAR pricing
# ─────────────────────────────────────────────────────────────────────────────
PRICING = '''"use client";
import { useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

const INDUSTRIES = [
  { key:"construction",  ar:"🏗️ المقاولات",       en:"🏗️ Construction" },
  { key:"retail",        ar:"🛒 التجزئة",          en:"🛒 Retail" },
  { key:"manufacturing", ar:"🏭 التصنيع",          en:"🏭 Manufacturing" },
  { key:"healthcare",    ar:"🏥 الرعاية الصحية",   en:"🏥 Healthcare" },
  { key:"realestate",    ar:"🏢 العقارات",         en:"🏢 Real Estate" },
  { key:"services",      ar:"💼 الخدمات",           en:"💼 Services" },
];

type PkgDef = {
  tier: string; price_monthly: number; price_annual: number; popular?: boolean;
  ar: string; en: string; users: number; storage: string;
  features_ar: string[]; features_en: string[];
  highlight_ar: string; highlight_en: string;
};

const PACKAGES: Record<string, PkgDef[]> = {
  construction: [
    {
      tier:"starter", price_monthly:299, price_annual:2990,
      ar:"مبتدئ", en:"Starter", users:10, storage:"20GB",
      highlight_ar:"للشركات الصغيرة والناشئة",
      highlight_en:"For small & startup companies",
      features_ar:["المحاسبة والفواتير","المبيعات والمشتريات","إدارة المخزون","BOQ أساسي","ضريبة القيمة المضافة والفاتورة الإلكترونية ZATCA","الموارد البشرية","3 مستخدمين مجاناً للتجربة","دعم عبر البريد الإلكتروني","SLA 99.9%","نسخ احتياطي يومي"],
      features_en:["Accounting & Invoicing","Sales & Purchase","Inventory Management","Basic BOQ","VAT & ZATCA e-invoicing","HR Module","3 users free trial","Email support","99.9% SLA","Daily backup"],
    },
    {
      tier:"professional", price_monthly:899, price_annual:8990, popular:true,
      ar:"احترافي", en:"Professional", users:50, storage:"100GB",
      highlight_ar:"للشركات المتنامية — الأكثر شعبية",
      highlight_en:"For growing companies — Most Popular",
      features_ar:["كل ما في المبتدئ","BOQ متقدم وتسعير المناقصات","مستخلصات الأعمال وإدارة الضمانات","إدارة المقاولين الفرعيين","إدارة المواقع والتقارير اليومية","تتبع المعدات والآليات","تحليل المناقصات بالذكاء الاصطناعي","تطبيق جوال للمواقع","ربحية المشاريع اللحظية","نظام حماية الأجور WPS","دعم أولوية","SLA 99.95%","بيئة تجريبية","نسخ احتياطي كل 6 ساعات"],
      features_en:["Everything in Starter","Advanced BOQ & Tender Pricing","Progress Billing & Retention","Subcontractor Management","Site Operations & Daily Reports","Equipment Tracking","AI Tender Analysis","Field Mobile App","Real-time Project P&L","WPS (Wage Protection System)","Priority support","99.95% SLA","Staging environment","6-hour backup"],
    },
    {
      tier:"enterprise", price_monthly:2499, price_annual:24990,
      ar:"مؤسسي", en:"Enterprise", users:-1, storage:"500GB",
      highlight_ar:"للمؤسسات الكبيرة والمتعددة المشاريع",
      highlight_en:"For large multi-project enterprises",
      features_ar:["كل ما في الاحترافي","خوادم مخصصة","تكامل BIM","مشاريع غير محدودة","محاسبة مُدارة (اختياري)","مدير حساب مخصص","تدريب وتأهيل فريقك","تكاملات مخصصة (API)","تقارير مخصصة","SLA 99.99%","نسخ احتياطي مستمر","دعم 24/7 مخصص"],
      features_en:["Everything in Professional","Dedicated servers","BIM Integration","Unlimited projects","Managed Accounting (optional)","Dedicated Account Manager","Team training & onboarding","Custom API integrations","Custom reports","99.99% SLA","Continuous backup","24/7 dedicated support"],
    },
  ],
  retail: [
    { tier:"starter", price_monthly:199, price_annual:1990, ar:"مبتدئ", en:"Starter", users:5, storage:"10GB", highlight_ar:"لمتاجر التجزئة الصغيرة", highlight_en:"For small retail stores",
      features_ar:["نقاط البيع POS","المحاسبة والفواتير","إدارة المخزون","ZATCA","ضريبة القيمة المضافة","دعم عبر البريد الإلكتروني"],
      features_en:["Point of Sale POS","Accounting & Invoicing","Inventory Management","ZATCA","VAT","Email support"] },
    { tier:"professional", price_monthly:699, price_annual:6990, popular:true, ar:"احترافي", en:"Professional", users:25, storage:"50GB", highlight_ar:"للمتاجر المتنامية", highlight_en:"For growing retail chains",
      features_ar:["كل المبتدئ","برنامج الولاء","التجارة الإلكترونية","الباركود والـ QR","التسويق والعروض","فروع متعددة","تقارير المبيعات المتقدمة","تطبيق جوال للبيع"],
      features_en:["All Starter","Loyalty Program","eCommerce","Barcode & QR","Marketing & Promotions","Multi-branch","Advanced Sales Reports","Mobile Sales App"] },
    { tier:"enterprise", price_monthly:1999, price_annual:19990, ar:"مؤسسي", en:"Enterprise", users:-1, storage:"200GB", highlight_ar:"لسلاسل التجزئة الكبيرة", highlight_en:"For large retail chains",
      features_ar:["كل الاحترافي","فروع غير محدودة","تكامل مع الموردين","خوادم مخصصة","مدير حساب مخصص"],
      features_en:["All Professional","Unlimited branches","Supplier Integration","Dedicated servers","Dedicated Account Manager"] },
  ],
  manufacturing: [
    { tier:"starter", price_monthly:399, price_annual:3990, ar:"مبتدئ", en:"Starter", users:10, storage:"20GB", highlight_ar:"للمصانع الصغيرة", highlight_en:"For small manufacturers",
      features_ar:["التصنيع والإنتاج MRP","إدارة المخزون","المشتريات","المحاسبة","ZATCA"],
      features_en:["Manufacturing & MRP","Inventory Management","Purchase","Accounting","ZATCA"] },
    { tier:"professional", price_monthly:999, price_annual:9990, popular:true, ar:"احترافي", en:"Professional", users:50, storage:"100GB", highlight_ar:"للمصانع المتوسطة", highlight_en:"For medium manufacturers",
      features_ar:["كل المبتدئ","الجودة والتفتيش","الصيانة الوقائية","تخطيط الإنتاج","ضبط التكاليف","الموارد البشرية"],
      features_en:["All Starter","Quality & Inspection","Preventive Maintenance","Production Planning","Cost Control","HR"] },
    { tier:"enterprise", price_monthly:2499, price_annual:24990, ar:"مؤسسي", en:"Enterprise", users:-1, storage:"500GB", highlight_ar:"للمصانع الكبيرة", highlight_en:"For large manufacturers",
      features_ar:["كل الاحترافي","IoT وأتمتة المصنع","تكامل MES","تحليلات متقدمة","خوادم مخصصة"],
      features_en:["All Professional","IoT & Factory Automation","MES Integration","Advanced Analytics","Dedicated Servers"] },
  ],
};

function getPackages(industry: string) {
  return PACKAGES[industry] || PACKAGES.construction;
}

export default function PricingPage() {
  const { locale } = useParams() as { locale: string };
  const isAr = locale === "ar";
  const router = useRouter();

  const [industry, setIndustry] = useState("construction");
  const [billing, setBilling] = useState<"monthly"|"annual">("monthly");

  const pkgs = getPackages(industry);

  return (
    <div className="min-h-screen bg-gray-50" dir={isAr ? "rtl" : "ltr"}>
      {/* Header */}
      <div className="bg-white border-b border-gray-100 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <Link href={`/${locale}`} className="flex items-center gap-3">
            <div className="w-8 h-8 bg-gradient-to-br from-orange-500 to-amber-600 rounded-xl flex items-center justify-center">
              <span className="text-white font-black text-xs">CB</span>
            </div>
            <span className="text-xl font-black text-gray-900">ClickBuild</span>
          </Link>
          <div className="flex gap-3">
            <Link href={`/${locale}/login`} className="text-gray-600 hover:text-gray-900 px-4 py-2 rounded-lg transition text-sm">
              {isAr ? "دخول" : "Login"}
            </Link>
            <Link href={`/${locale}/onboarding`} className="bg-gradient-to-r from-orange-500 to-amber-600 text-white px-5 py-2 rounded-xl font-bold text-sm hover:opacity-90 transition">
              {isAr ? "ابدأ مجاناً" : "Start Free"}
            </Link>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-16">
        {/* Title */}
        <div className="text-center mb-12">
          <h1 className="text-4xl md:text-5xl font-black text-gray-900 mb-4">
            {isAr ? "أسعار شفافة بالريال السعودي" : "Transparent SAR Pricing"}
          </h1>
          <p className="text-gray-500 text-xl">
            {isAr ? "لا رسوم مخفية • 14 يوم تجريبي مجاني • إلغاء في أي وقت" : "No hidden fees • 14-day free trial • Cancel anytime"}
          </p>
        </div>

        {/* Industry Selector */}
        <div className="flex flex-wrap gap-2 justify-center mb-8">
          {INDUSTRIES.map(ind => (
            <button key={ind.key}
              onClick={() => setIndustry(ind.key)}
              className={`px-5 py-2 rounded-xl text-sm font-bold transition ${
                industry === ind.key
                  ? "bg-orange-500 text-white shadow-md shadow-orange-200"
                  : "bg-white border border-gray-200 text-gray-600 hover:border-orange-300 hover:text-orange-600"
              }`}>
              {isAr ? ind.ar : ind.en}
            </button>
          ))}
        </div>

        {/* Billing Toggle */}
        <div className="flex items-center justify-center gap-4 mb-10">
          <span className={`text-sm font-medium ${billing==="monthly" ? "text-gray-900" : "text-gray-400"}`}>
            {isAr ? "شهري" : "Monthly"}
          </span>
          <button
            onClick={() => setBilling(b => b==="monthly" ? "annual" : "monthly")}
            className={`relative w-14 h-7 rounded-full transition-colors ${billing==="annual" ? "bg-orange-500" : "bg-gray-300"}`}>
            <div className={`absolute top-0.5 w-6 h-6 bg-white rounded-full shadow transition-transform ${billing==="annual" ? "translate-x-7" : "translate-x-0.5"}`} />
          </button>
          <span className={`text-sm font-medium ${billing==="annual" ? "text-gray-900" : "text-gray-400"}`}>
            {isAr ? "سنوي" : "Annual"}
            <span className="mr-2 bg-green-100 text-green-700 text-xs px-2 py-0.5 rounded-full font-bold">
              {isAr ? "وفر شهرين" : "Save 2 months"}
            </span>
          </span>
        </div>

        {/* Plans */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-16">
          {pkgs.map(pkg => {
            const price = billing === "annual" ? Math.round(pkg.price_annual / 12) : pkg.price_monthly;
            const features = isAr ? pkg.features_ar : pkg.features_en;
            return (
              <div key={pkg.tier}
                className={`relative bg-white rounded-3xl p-8 border-2 flex flex-col ${
                  pkg.popular ? "border-orange-400 shadow-2xl shadow-orange-100" : "border-gray-200 shadow-sm"
                }`}>
                {pkg.popular && (
                  <div className="absolute -top-4 left-1/2 -translate-x-1/2 bg-gradient-to-r from-orange-500 to-amber-500 text-white text-sm px-6 py-1.5 rounded-full font-black shadow-lg whitespace-nowrap">
                    ⭐ {isAr ? "الأكثر شعبية" : "Most Popular"}
                  </div>
                )}
                <div className="mb-6">
                  <h2 className="text-2xl font-black text-gray-900 mb-1">{isAr ? pkg.ar : pkg.en}</h2>
                  <p className="text-gray-400 text-sm">{isAr ? pkg.highlight_ar : pkg.highlight_en}</p>
                </div>
                <div className="mb-6">
                  <div className="flex items-end gap-1">
                    <span className="text-5xl font-black text-gray-900">{price.toLocaleString()}</span>
                    <span className="text-gray-400 mb-2">{isAr ? "ر.س/شهر" : "SAR/mo"}</span>
                  </div>
                  {billing === "annual" && (
                    <p className="text-green-600 text-sm font-medium">
                      {isAr ? `وفر ${(pkg.price_monthly*12 - pkg.price_annual).toLocaleString()} ر.س سنوياً` : `Save SAR ${(pkg.price_monthly*12 - pkg.price_annual).toLocaleString()} yearly`}
                    </p>
                  )}
                  <div className="flex gap-4 text-sm text-gray-500 mt-2">
                    <span>👥 {pkg.users === -1 ? (isAr?"غير محدود":"Unlimited") : pkg.users + (isAr?" مستخدم":" users")}</span>
                    <span>💾 {pkg.storage}</span>
                  </div>
                </div>
                <Link href={`/${locale}/onboarding?industry=${industry}&package=${pkg.tier}`}
                  className={`block w-full py-4 rounded-2xl font-black text-center text-lg transition mb-8 ${
                    pkg.popular
                      ? "bg-gradient-to-r from-orange-500 to-amber-600 text-white hover:opacity-90 shadow-lg shadow-orange-200"
                      : "border-2 border-gray-200 text-gray-700 hover:border-orange-400 hover:text-orange-600"
                  }`}>
                  {isAr ? "ابدأ مجاناً — 14 يوم" : "Start Free — 14 days"}
                </Link>
                <ul className="space-y-3 flex-1">
                  {features.map((f, i) => (
                    <li key={i} className="flex items-start gap-3 text-sm text-gray-600">
                      <span className="text-green-500 mt-0.5 flex-shrink-0">✓</span>
                      <span>{f}</span>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>

        {/* FAQ */}
        <div className="max-w-3xl mx-auto">
          <h2 className="text-2xl font-black text-gray-900 text-center mb-8">
            {isAr ? "أسئلة شائعة" : "Frequently Asked Questions"}
          </h2>
          <div className="space-y-4">
            {[
              { q_ar:"هل يشمل دعم ZATCA والفوترة الإلكترونية؟", q_en:"Does it include ZATCA e-invoicing?", a_ar:"نعم، جميع الباقات تشمل تكاملاً كاملاً مع ZATCA للفواتير الإلكترونية وضريبة القيمة المضافة السعودية.", a_en:"Yes, all plans include full ZATCA integration for e-invoicing and Saudi VAT compliance." },
              { q_ar:"هل يمكنني تغيير الباقة لاحقاً؟", q_en:"Can I change my plan later?", a_ar:"بالطبع، يمكنك الترقية أو تخفيض الباقة في أي وقت بدون غرامات.", a_en:"Yes, you can upgrade or downgrade at any time with no penalties." },
              { q_ar:"ماذا يحدث لبياناتي عند الإلغاء؟", q_en:"What happens to my data if I cancel?", a_ar:"بياناتك محفوظة لمدة 90 يوماً بعد الإلغاء ويمكنك تصديرها في أي وقت.", a_en:"Your data is retained for 90 days after cancellation and can be exported anytime." },
              { q_ar:"هل النظام متوافق مع اللغة العربية؟", q_en:"Is the system fully Arabic?", a_ar:"نعم، الواجهة الكاملة بالعربية مع دعم RTL، والتقارير والفواتير كلها بالعربية.", a_en:"Yes, full Arabic UI with RTL support, Arabic reports and invoices." },
            ].map((faq, i) => (
              <div key={i} className="bg-white rounded-2xl border border-gray-200 p-6">
                <h3 className="font-bold text-gray-900 mb-2">{isAr ? faq.q_ar : faq.q_en}</h3>
                <p className="text-gray-500 text-sm">{isAr ? faq.a_ar : faq.a_en}</p>
              </div>
            ))}
          </div>
        </div>

        {/* CTA */}
        <div className="text-center mt-16 bg-gradient-to-r from-orange-500 to-amber-600 rounded-3xl p-12 text-white">
          <h2 className="text-3xl font-black mb-4">{isAr ? "ابدأ تجربتك المجانية اليوم" : "Start Your Free Trial Today"}</h2>
          <p className="text-orange-100 text-lg mb-8">{isAr ? "14 يوماً مجاناً • لا يلزم بطاقة ائتمان • إلغاء في أي وقت" : "14 days free • No credit card • Cancel anytime"}</p>
          <Link href={`/${locale}/onboarding`}
            className="inline-block bg-white text-orange-600 font-black px-12 py-5 rounded-2xl text-xl hover:bg-orange-50 transition shadow-2xl">
            {isAr ? "🚀 ابدأ الآن" : "🚀 Start Now"}
          </Link>
        </div>
      </div>
    </div>
  );
}
'''

upload('/opt/clickbuild/frontend/src/app/[locale]/pricing/page.tsx', PRICING)
print('✅ Pricing page uploaded')

c.close()
print('\nAll pages uploaded successfully!')
