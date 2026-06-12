#!/usr/bin/env python3
"""
Platform Restructure Script
- Delete unnecessary pages
- Rebuild customer journey
- Rebuild admin panel
- Update DB plans to SAR
"""
import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('129.121.98.243', username='root', password='Mh@01007121878', timeout=30)

def upload(path, content):
    sftp = c.open_sftp()
    # ensure directory exists
    import posixpath
    d = posixpath.dirname(path)
    stdin, stdout, stderr = c.exec_command(f'mkdir -p "{d}"')
    stdout.read()
    with sftp.open(path, 'w') as f:
        f.write(content)
    sftp.close()
    print(f'  ✅ {path}')

def run(cmd, timeout=60):
    _, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode('utf-8', errors='replace').strip()
    err = e.read().decode('utf-8', errors='replace').strip()
    if out: print(out[:500])
    if err and not out: print(f'  ⚠ {err[:300]}')
    return out

# ─────────────────────────────────────────────────────────────────
# 0. CLEANUP — remove pages that have no place in the new structure
# ─────────────────────────────────────────────────────────────────
print('\n── Cleaning up old pages ──')
REMOVE = [
    '/opt/clickbuild/frontend/src/app/[locale]/admin/compliance',
    '/opt/clickbuild/frontend/src/app/[locale]/admin/ops',
    '/opt/clickbuild/frontend/src/app/[locale]/admin/sre',
    '/opt/clickbuild/frontend/src/app/[locale]/admin/support-queue',
    '/opt/clickbuild/frontend/src/app/[locale]/admin/users',
    '/opt/clickbuild/frontend/src/app/[locale]/billing',
    '/opt/clickbuild/frontend/src/app/[locale]/create',
    '/opt/clickbuild/frontend/src/app/[locale]/onboarding',
]
for p in REMOVE:
    run(f'rm -rf "{p}"')
    print(f'  🗑 {p}')

# ─────────────────────────────────────────────────────────────────
# 1. UPDATE DB — plans to SAR
# ─────────────────────────────────────────────────────────────────
print('\n── Updating plans to SAR ──')
run("""PGPASSWORD="CB_pg_S3cur3_2024!" psql -h 127.0.0.1 -U clickbuild clickbuild_platform -c "
UPDATE plans SET price_egp=299  WHERE name='STARTER';
UPDATE plans SET price_egp=899  WHERE name='BUSINESS';
UPDATE plans SET price_egp=2499 WHERE name='ENTERPRISE';
SELECT name, price_egp FROM plans ORDER BY price_egp;
" 2>/dev/null""")

# ═════════════════════════════════════════════════════════════════
# 2. PRICING PAGE
# ═════════════════════════════════════════════════════════════════
PRICING = '''"use client";
import { useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

const PLANS = [
  {
    id: "STARTER",
    ar: "مبتدئ",        en: "Starter",
    price_mo: 299,     price_yr: 2990,
    users: 10,         storage: "20 GB",
    highlight: false,
    features_ar: [
      "محاسبة وفواتير إلكترونية ZATCA",
      "مبيعات ومشتريات",
      "إدارة المخزون",
      "ضريبة القيمة المضافة 15%",
      "تقارير مالية أساسية",
      "تطبيق جوال",
      "دعم عبر البريد الإلكتروني",
      "SLA 99.9%",
      "نسخ احتياطي يومي",
    ],
    features_en: [
      "Accounting & ZATCA e-invoicing",
      "Sales & Purchase",
      "Inventory management",
      "15% VAT handling",
      "Basic financial reports",
      "Mobile app",
      "Email support",
      "99.9% SLA",
      "Daily backup",
    ],
    not_ar: ["موارد بشرية","إدارة مشاريع","نقطة البيع"],
    not_en: ["HR module","Project management","Point of Sale"],
  },
  {
    id: "BUSINESS",
    ar: "أعمال",         en: "Business",
    price_mo: 899,     price_yr: 8990,
    users: 50,         storage: "100 GB",
    highlight: true,
    features_ar: [
      "كل ما في مبتدئ",
      "موارد بشرية ومسير الرواتب",
      "إدارة المشاريع",
      "نقطة البيع POS",
      "إدارة المصاريف",
      "CRM وإدارة العملاء",
      "تكامل مع البنوك السعودية",
      "دعم أولوية",
      "SLA 99.95%",
      "نسخ احتياطي كل 6 ساعات",
      "بيئة تجريبية Staging",
    ],
    features_en: [
      "Everything in Starter",
      "HR & Payroll (Saudi WPS)",
      "Project management",
      "Point of Sale",
      "Expense management",
      "CRM",
      "Saudi bank integration",
      "Priority support",
      "99.95% SLA",
      "6-hour backup",
      "Staging environment",
    ],
    not_ar: [],
    not_en: [],
  },
  {
    id: "ENTERPRISE",
    ar: "مؤسسي",        en: "Enterprise",
    price_mo: 2499,    price_yr: 24990,
    users: -1,         storage: "500 GB",
    highlight: false,
    features_ar: [
      "كل ما في أعمال",
      "مستخدمون غير محدودون",
      "خادم مخصص",
      "شركات متعددة",
      "تكاملات مخصصة API",
      "تقارير مخصصة",
      "مدير حساب مخصص",
      "SLA 99.99%",
      "نسخ احتياطي مستمر",
      "دعم 24/7 مخصص",
      "تدريب الفريق",
    ],
    features_en: [
      "Everything in Business",
      "Unlimited users",
      "Dedicated server",
      "Multi-company",
      "Custom API integrations",
      "Custom reports",
      "Dedicated account manager",
      "99.99% SLA",
      "Continuous backup",
      "24/7 dedicated support",
      "Team training",
    ],
    not_ar: [],
    not_en: [],
  },
];

export default function PricingPage() {
  const { locale } = useParams() as { locale: string };
  const isAr = locale === "ar";
  const router = useRouter();
  const [billing, setBilling] = useState<"monthly" | "annual">("monthly");

  return (
    <div className="min-h-screen bg-gray-50" dir={isAr ? "rtl" : "ltr"}>

      {/* Nav */}
      <header className="bg-white border-b border-gray-100 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
          <Link href={`/${locale}`} className="flex items-center gap-2">
            <div className="w-8 h-8 bg-emerald-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-black text-xs">CB</span>
            </div>
            <span className="font-black text-gray-900 text-lg">كليك بيلد</span>
          </Link>
          <div className="flex gap-3">
            <Link href={`/${locale}/login`}
              className="text-gray-600 text-sm px-4 py-2 rounded-lg hover:bg-gray-50 transition">
              {isAr ? "تسجيل الدخول" : "Login"}
            </Link>
            <Link href={`/${locale}/register`}
              className="bg-emerald-600 text-white text-sm px-5 py-2 rounded-lg hover:bg-emerald-700 transition font-medium">
              {isAr ? "ابدأ مجاناً" : "Start Free"}
            </Link>
          </div>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-4 py-16">

        {/* Title */}
        <div className="text-center mb-12">
          <h1 className="text-4xl md:text-5xl font-black text-gray-900 mb-4">
            {isAr ? "اختر الباقة المناسبة لك" : "Choose the Right Plan"}
          </h1>
          <p className="text-gray-500 text-xl mb-8">
            {isAr ? "جميع الباقات تشمل 14 يوم تجريبي مجاني • بدون بطاقة ائتمان • إلغاء في أي وقت" : "All plans include 14-day free trial • No credit card • Cancel anytime"}
          </p>

          {/* Billing toggle */}
          <div className="inline-flex items-center gap-4 bg-white border border-gray-200 rounded-2xl p-1.5">
            <button
              onClick={() => setBilling("monthly")}
              className={`px-6 py-2.5 rounded-xl text-sm font-bold transition ${billing === "monthly" ? "bg-emerald-600 text-white shadow" : "text-gray-500 hover:text-gray-900"}`}>
              {isAr ? "شهري" : "Monthly"}
            </button>
            <button
              onClick={() => setBilling("annual")}
              className={`px-6 py-2.5 rounded-xl text-sm font-bold transition flex items-center gap-2 ${billing === "annual" ? "bg-emerald-600 text-white shadow" : "text-gray-500 hover:text-gray-900"}`}>
              {isAr ? "سنوي" : "Annual"}
              <span className={`text-xs px-2 py-0.5 rounded-full ${billing === "annual" ? "bg-white/20 text-white" : "bg-green-100 text-green-700"}`}>
                {isAr ? "وفر 17%" : "Save 17%"}
              </span>
            </button>
          </div>
        </div>

        {/* Plans */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-16">
          {PLANS.map(plan => {
            const price = billing === "annual"
              ? Math.round(plan.price_yr / 12)
              : plan.price_mo;
            return (
              <div key={plan.id}
                className={`relative bg-white rounded-3xl flex flex-col border-2 overflow-hidden transition-shadow hover:shadow-xl ${
                  plan.highlight
                    ? "border-emerald-500 shadow-2xl shadow-emerald-100"
                    : "border-gray-200 shadow-sm"
                }`}>

                {plan.highlight && (
                  <div className="bg-emerald-600 text-white text-center py-2.5 text-sm font-bold">
                    ⭐ {isAr ? "الأكثر شعبية" : "Most Popular"}
                  </div>
                )}

                <div className="p-8 flex-1 flex flex-col">
                  <div className="mb-6">
                    <h2 className="text-2xl font-black text-gray-900 mb-1">
                      {isAr ? plan.ar : plan.en}
                    </h2>
                    <div className="flex items-end gap-1 mt-3">
                      <span className="text-5xl font-black text-gray-900">{price.toLocaleString()}</span>
                      <div className="mb-1">
                        <span className="text-gray-400 text-sm block">{isAr ? "ر.س / شهر" : "SAR/mo"}</span>
                        {billing === "annual" && (
                          <span className="text-green-600 text-xs font-medium">
                            {isAr ? `${plan.price_yr.toLocaleString()} ر.س/سنة` : `SAR ${plan.price_yr.toLocaleString()}/yr`}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex gap-3 text-sm text-gray-400 mt-3">
                      <span>👥 {plan.users === -1 ? (isAr ? "غير محدود" : "Unlimited") : `${plan.users} ${isAr ? "مستخدم" : "users"}`}</span>
                      <span>💾 {plan.storage}</span>
                    </div>
                  </div>

                  <button
                    onClick={() => router.push(`/${locale}/register?plan=${plan.id}`)}
                    className={`w-full py-4 rounded-2xl font-black text-lg mb-8 transition ${
                      plan.highlight
                        ? "bg-emerald-600 text-white hover:bg-emerald-700 shadow-lg shadow-emerald-200"
                        : "border-2 border-gray-200 text-gray-800 hover:border-emerald-400 hover:text-emerald-700"
                    }`}>
                    {isAr ? "ابدأ مجاناً — 14 يوم" : "Start Free — 14 days"}
                  </button>

                  <ul className="space-y-2.5 flex-1">
                    {(isAr ? plan.features_ar : plan.features_en).map(f => (
                      <li key={f} className="flex items-start gap-2.5 text-sm text-gray-700">
                        <span className="text-emerald-500 flex-shrink-0 mt-0.5 font-bold">✓</span>
                        {f}
                      </li>
                    ))}
                    {(isAr ? plan.not_ar : plan.not_en).map(f => (
                      <li key={f} className="flex items-start gap-2.5 text-sm text-gray-300">
                        <span className="flex-shrink-0 mt-0.5">✕</span>
                        {f}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            );
          })}
        </div>

        {/* Compare note */}
        <div className="bg-white rounded-2xl border border-gray-100 p-8 text-center">
          <h3 className="text-xl font-black text-gray-900 mb-2">
            {isAr ? "جميع الباقات تشمل" : "All Plans Include"}
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6">
            {[
              { icon: "🇸🇦", ar: "متوافق ZATCA المرحلة الثانية", en: "ZATCA Phase 2 Compliant" },
              { icon: "🌐", ar: "واجهة عربية RTL كاملة",          en: "Full Arabic RTL UI" },
              { icon: "☁️", ar: "سحابي 100% — بدون تثبيت",       en: "100% Cloud — no install" },
              { icon: "🔒", ar: "تشفير وحماية كاملة للبيانات",   en: "Encrypted data protection" },
            ].map(item => (
              <div key={item.ar} className="flex flex-col items-center gap-2 p-4">
                <span className="text-3xl">{item.icon}</span>
                <span className="text-sm text-gray-600 font-medium text-center">{isAr ? item.ar : item.en}</span>
              </div>
            ))}
          </div>
        </div>

      </div>
    </div>
  );
}
'''

upload('/opt/clickbuild/frontend/src/app/[locale]/pricing/page.tsx', PRICING)

# ═════════════════════════════════════════════════════════════════
# 3. REGISTER PAGE
# ═════════════════════════════════════════════════════════════════
REGISTER = '''"use client";
import { useState } from "react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";

export default function RegisterPage() {
  const { locale } = useParams() as { locale: string };
  const isAr = locale === "ar";
  const router = useRouter();
  const params = useSearchParams();
  const planFromUrl = params.get("plan") || "BUSINESS";

  const [form, setForm] = useState({ name: "", email: "", password: "", phone: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const PLAN_NAMES: Record<string, { ar: string; en: string; price: number }> = {
    STARTER:    { ar: "مبتدئ",   en: "Starter",    price: 299 },
    BUSINESS:   { ar: "أعمال",   en: "Business",   price: 899 },
    ENTERPRISE: { ar: "مؤسسي",  en: "Enterprise", price: 2499 },
  };
  const plan = PLAN_NAMES[planFromUrl] || PLAN_NAMES.BUSINESS;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await api.post("/auth/register", {
        name: form.name,
        email: form.email,
        password: form.password,
        phone: form.phone,
        language: locale,
      });
      router.push(`/${locale}/verify?email=${encodeURIComponent(form.email)}&plan=${planFromUrl}`);
    } catch (err: any) {
      setError(err.response?.data?.detail || (isAr ? "حدث خطأ. حاول مرة أخرى." : "An error occurred."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col" dir={isAr ? "rtl" : "ltr"}>
      {/* Nav */}
      <header className="bg-white border-b border-gray-100 px-4 py-3 flex items-center justify-between">
        <Link href={`/${locale}`} className="flex items-center gap-2">
          <div className="w-8 h-8 bg-emerald-600 rounded-lg flex items-center justify-center">
            <span className="text-white font-black text-xs">CB</span>
          </div>
          <span className="font-black text-gray-900">كليك بيلد</span>
        </Link>
        <span className="text-sm text-gray-500">
          {isAr ? "لديك حساب؟" : "Have an account?"}{" "}
          <Link href={`/${locale}/login`} className="text-emerald-600 font-semibold hover:underline">
            {isAr ? "تسجيل الدخول" : "Login"}
          </Link>
        </span>
      </header>

      <div className="flex-1 flex items-center justify-center py-12 px-4">
        <div className="w-full max-w-md">

          {/* Plan badge */}
          <div className="bg-emerald-50 border border-emerald-200 rounded-2xl p-4 mb-6 flex items-center justify-between">
            <div>
              <p className="text-xs text-emerald-600 font-medium">{isAr ? "الباقة المختارة" : "Selected Plan"}</p>
              <p className="font-black text-gray-900">{isAr ? plan.ar : plan.en}</p>
            </div>
            <div className="text-right">
              <p className="text-2xl font-black text-emerald-700">{plan.price.toLocaleString()}</p>
              <p className="text-xs text-gray-400">{isAr ? "ر.س / شهر" : "SAR/mo"}</p>
            </div>
          </div>

          <div className="bg-white rounded-3xl shadow-sm border border-gray-100 p-8">
            <h1 className="text-2xl font-black text-gray-900 mb-2">
              {isAr ? "إنشاء حساب جديد" : "Create Your Account"}
            </h1>
            <p className="text-gray-400 text-sm mb-8">
              {isAr ? "14 يوم مجاناً • بدون بطاقة ائتمان" : "14 days free • No credit card"}
            </p>

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-xl mb-6">
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              {[
                { key: "name",     type: "text",     ar: "الاسم الكامل",   en: "Full Name",    placeholder_ar: "محمد العتيبي",           placeholder_en: "Mohammed Al-Otaibi" },
                { key: "email",    type: "email",    ar: "البريد الإلكتروني", en: "Email",     placeholder_ar: "you@company.com",         placeholder_en: "you@company.com" },
                { key: "phone",    type: "tel",      ar: "رقم الجوال",     en: "Phone",        placeholder_ar: "+966 5X XXX XXXX",        placeholder_en: "+966 5X XXX XXXX" },
                { key: "password", type: "password", ar: "كلمة المرور",    en: "Password",     placeholder_ar: "8 أحرف على الأقل",       placeholder_en: "At least 8 characters" },
              ].map(field => (
                <div key={field.key}>
                  <label className="block text-sm font-bold text-gray-700 mb-1.5">
                    {isAr ? field.ar : field.en}
                  </label>
                  <input
                    type={field.type}
                    required
                    value={form[field.key as keyof typeof form]}
                    onChange={e => setForm(f => ({ ...f, [field.key]: e.target.value }))}
                    placeholder={isAr ? field.placeholder_ar : field.placeholder_en}
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-400 focus:border-transparent text-sm"
                  />
                </div>
              ))}

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-emerald-600 text-white font-black py-4 rounded-2xl text-lg hover:bg-emerald-700 transition disabled:opacity-50 mt-2">
                {loading
                  ? (isAr ? "جاري الإنشاء..." : "Creating...")
                  : (isAr ? "إنشاء الحساب مجاناً ←" : "Create Free Account →")}
              </button>
            </form>

            <p className="text-xs text-gray-400 text-center mt-6">
              {isAr
                ? "بالتسجيل أنت توافق على شروط الاستخدام وسياسة الخصوصية"
                : "By registering you agree to our Terms of Service and Privacy Policy"}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
'''

upload('/opt/clickbuild/frontend/src/app/[locale]/register/page.tsx', REGISTER)

# ═════════════════════════════════════════════════════════════════
# 4. LOGIN PAGE
# ═════════════════════════════════════════════════════════════════
LOGIN = '''"use client";
import { useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth";

export default function LoginPage() {
  const { locale } = useParams() as { locale: string };
  const isAr = locale === "ar";
  const router = useRouter();
  const { setTokens } = useAuthStore();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const r = await api.post("/auth/login", { email, password });
      setTokens(r.data.access_token, r.data.refresh_token, r.data.user);
      if (r.data.user?.is_admin) {
        router.push(`/${locale}/admin`);
      } else {
        router.push(`/${locale}/dashboard`);
      }
    } catch (err: any) {
      setError(isAr
        ? "البريد الإلكتروني أو كلمة المرور غير صحيحة"
        : "Incorrect email or password");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col" dir={isAr ? "rtl" : "ltr"}>
      <header className="bg-white border-b border-gray-100 px-4 py-3 flex items-center justify-between">
        <Link href={`/${locale}`} className="flex items-center gap-2">
          <div className="w-8 h-8 bg-emerald-600 rounded-lg flex items-center justify-center">
            <span className="text-white font-black text-xs">CB</span>
          </div>
          <span className="font-black text-gray-900">كليك بيلد</span>
        </Link>
        <span className="text-sm text-gray-500">
          {isAr ? "ليس لديك حساب؟" : "No account?"}{" "}
          <Link href={`/${locale}/register`} className="text-emerald-600 font-semibold hover:underline">
            {isAr ? "سجّل مجاناً" : "Sign up free"}
          </Link>
        </span>
      </header>

      <div className="flex-1 flex items-center justify-center py-12 px-4">
        <div className="w-full max-w-sm">
          <div className="bg-white rounded-3xl shadow-sm border border-gray-100 p-8">
            <div className="text-center mb-8">
              <div className="w-14 h-14 bg-emerald-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
                <span className="text-2xl">🔐</span>
              </div>
              <h1 className="text-2xl font-black text-gray-900 mb-1">
                {isAr ? "مرحباً بعودتك" : "Welcome Back"}
              </h1>
              <p className="text-gray-400 text-sm">{isAr ? "سجّل دخولك إلى حسابك" : "Sign in to your account"}</p>
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-xl mb-6">
                ⚠ {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-bold text-gray-700 mb-1.5">
                  {isAr ? "البريد الإلكتروني" : "Email"}
                </label>
                <input
                  type="email" required autoFocus
                  value={email} onChange={e => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-400 text-sm"
                />
              </div>
              <div>
                <div className="flex justify-between items-center mb-1.5">
                  <label className="text-sm font-bold text-gray-700">
                    {isAr ? "كلمة المرور" : "Password"}
                  </label>
                  <Link href={`/${locale}/forgot-password`} className="text-xs text-emerald-600 hover:underline">
                    {isAr ? "نسيت كلمة المرور؟" : "Forgot password?"}
                  </Link>
                </div>
                <input
                  type="password" required
                  value={password} onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-400 text-sm"
                />
              </div>
              <button
                type="submit" disabled={loading}
                className="w-full bg-emerald-600 text-white font-black py-4 rounded-2xl text-lg hover:bg-emerald-700 transition disabled:opacity-50">
                {loading ? "..." : (isAr ? "تسجيل الدخول" : "Sign In")}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
'''

upload('/opt/clickbuild/frontend/src/app/[locale]/login/page.tsx', LOGIN)

# ═════════════════════════════════════════════════════════════════
# 5. CUSTOMER DASHBOARD
# ═════════════════════════════════════════════════════════════════
DASHBOARD = '''"use client";
import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth";

type Instance = {
  id: string; name: string; subdomain: string;
  status: string; odoo_port: number; odoo_version: string;
  plan?: string; created_at?: string; expires_at?: string;
};

const STATUS_CONFIG: Record<string, { label_ar: string; label_en: string; color: string; icon: string }> = {
  running:      { label_ar: "يعمل",       label_en: "Running",      color: "emerald", icon: "✅" },
  RUNNING:      { label_ar: "يعمل",       label_en: "Running",      color: "emerald", icon: "✅" },
  provisioning: { label_ar: "جاري الإنشاء", label_en: "Provisioning", color: "amber",   icon: "⏳" },
  PROVISIONING: { label_ar: "جاري الإنشاء", label_en: "Provisioning", color: "amber",   icon: "⏳" },
  stopped:      { label_ar: "متوقف",      label_en: "Stopped",      color: "gray",    icon: "⏸️" },
  STOPPED:      { label_ar: "متوقف",      label_en: "Stopped",      color: "gray",    icon: "⏸️" },
  error:        { label_ar: "خطأ",         label_en: "Error",        color: "red",     icon: "❌" },
  ERROR:        { label_ar: "خطأ",         label_en: "Error",        color: "red",     icon: "❌" },
};

export default function DashboardPage() {
  const { locale } = useParams() as { locale: string };
  const isAr = locale === "ar";
  const router = useRouter();
  const { user, accessToken, logout } = useAuthStore();

  const [instances, setInstances] = useState<Instance[]>([]);
  const [subscription, setSubscription] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [tickets, setTickets] = useState<any[]>([]);
  const [newTicket, setNewTicket] = useState({ subject: "", message: "" });
  const [submitting, setSubmitting] = useState(false);
  const [ticketDone, setTicketDone] = useState(false);

  useEffect(() => {
    if (!accessToken) { router.push(`/${locale}/login`); return; }
    Promise.all([
      api.get("/instances/").then(r => setInstances(r.data.instances || r.data)),
      api.get("/subscriptions/me").then(r => setSubscription(r.data)).catch(() => {}),
      api.get("/support/tickets").then(r => setTickets(r.data.tickets || [])).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, [accessToken]);

  const instance = instances[0];
  const st = instance ? (STATUS_CONFIG[instance.status] || STATUS_CONFIG.error) : null;
  const isRunning = instance?.status === "running" || instance?.status === "RUNNING";

  async function submitTicket(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await api.post("/support/tickets", { ...newTicket, category: "general", priority: "medium" });
      setTicketDone(true);
      setNewTicket({ subject: "", message: "" });
      const r = await api.get("/support/tickets");
      setTickets(r.data.tickets || []);
    } catch {}
    setSubmitting(false);
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center" dir={isAr ? "rtl" : "ltr"}>
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-emerald-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-500">{isAr ? "جاري التحميل..." : "Loading..."}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50" dir={isAr ? "rtl" : "ltr"}>

      {/* Sidebar + Main Layout */}
      <div className="flex">

        {/* Sidebar */}
        <aside className="w-56 min-h-screen bg-white border-e border-gray-100 flex-shrink-0 flex flex-col fixed top-0 bottom-0">
          <div className="p-4 border-b border-gray-100">
            <Link href={`/${locale}`} className="flex items-center gap-2">
              <div className="w-8 h-8 bg-emerald-600 rounded-lg flex items-center justify-center">
                <span className="text-white font-black text-xs">CB</span>
              </div>
              <span className="font-black text-gray-900">كليك بيلد</span>
            </Link>
          </div>

          <nav className="flex-1 p-3 space-y-1">
            {[
              { icon: "🏠", ar: "لوحة التحكم",   en: "Dashboard",  href: "dashboard",         active: true },
              { icon: "🌐", ar: "فتح Odoo",       en: "Open Odoo",  href: isRunning ? `https://${instance?.subdomain}.odoo.clickbulid.com` : "#", external: true },
              { icon: "📄", ar: "الفواتير",       en: "Invoices",   href: "billing" },
              { icon: "🎫", ar: "الدعم الفني",    en: "Support",    href: "support" },
            ].map(item => (
              item.external ? (
                <a key={item.ar}
                  href={item.href}
                  target="_blank"
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition ${
                    !isRunning ? "opacity-40 cursor-not-allowed" : "text-gray-600 hover:bg-emerald-50 hover:text-emerald-700"
                  }`}>
                  <span>{item.icon}</span>
                  <span>{isAr ? item.ar : item.en}</span>
                  {isRunning && <span className="ms-auto text-xs">↗</span>}
                </a>
              ) : (
                <Link key={item.ar}
                  href={`/${locale}/${item.href}`}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition ${
                    item.active
                      ? "bg-emerald-50 text-emerald-700"
                      : "text-gray-600 hover:bg-gray-50"
                  }`}>
                  <span>{item.icon}</span>
                  <span>{isAr ? item.ar : item.en}</span>
                </Link>
              )
            ))}
          </nav>

          <div className="p-3 border-t border-gray-100">
            <div className="px-3 py-2 mb-2">
              <p className="font-bold text-gray-900 text-sm truncate">{user?.name || user?.email}</p>
              <p className="text-gray-400 text-xs truncate">{user?.email}</p>
            </div>
            <button
              onClick={() => { logout(); router.push(`/${locale}/login`); }}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-xl transition">
              <span>🚪</span>
              <span>{isAr ? "تسجيل الخروج" : "Logout"}</span>
            </button>
          </div>
        </aside>

        {/* Main Content */}
        <main className="flex-1 ms-56 p-8">
          <div className="max-w-4xl mx-auto">

            {/* Header */}
            <div className="mb-8">
              <h1 className="text-2xl font-black text-gray-900">
                {isAr ? `مرحباً، ${user?.name?.split(" ")[0] || ""}` : `Welcome, ${user?.name?.split(" ")[0] || ""}`}
              </h1>
              <p className="text-gray-400 text-sm mt-1">
                {isAr ? "هذا هو نظامك على Odoo المُدار" : "This is your managed Odoo system"}
              </p>
            </div>

            {/* Instance Card — MAIN FOCUS */}
            {instance ? (
              <div className={`bg-white rounded-3xl border-2 p-8 mb-6 ${
                isRunning ? "border-emerald-200 shadow-lg shadow-emerald-50" : "border-gray-200"
              }`}>
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
                  <div>
                    <div className="flex items-center gap-3 mb-4">
                      <span className="text-3xl">{st?.icon}</span>
                      <div>
                        <h2 className="text-xl font-black text-gray-900">{instance.name}</h2>
                        <p className="text-gray-400 text-sm font-mono">{instance.subdomain}.odoo.clickbulid.com</p>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-3">
                      <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-bold bg-${st?.color}-100 text-${st?.color}-700`}>
                        <span className={`w-2 h-2 rounded-full bg-${st?.color}-500 ${isRunning ? "animate-pulse" : ""}`} />
                        {isAr ? st?.label_ar : st?.label_en}
                      </span>
                      <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm text-gray-600 bg-gray-100">
                        Odoo {instance.odoo_version || "17"}
                      </span>
                      {subscription && (
                        <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm text-purple-700 bg-purple-100 font-bold">
                          {subscription.plan_name || "Business"}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="flex flex-col gap-3">
                    <a
                      href={`https://${instance.subdomain}.odoo.clickbulid.com`}
                      target="_blank"
                      className={`flex items-center justify-center gap-2 px-8 py-4 rounded-2xl font-black text-lg transition ${
                        isRunning
                          ? "bg-emerald-600 text-white hover:bg-emerald-700 shadow-lg shadow-emerald-200"
                          : "bg-gray-100 text-gray-400 cursor-not-allowed"
                      }`}>
                      🌐 {isAr ? "فتح Odoo" : "Open Odoo"}
                    </a>
                    {!isRunning && (
                      <p className="text-xs text-center text-gray-400">
                        {isAr ? "النظام غير متاح حالياً" : "System not available yet"}
                      </p>
                    )}
                  </div>
                </div>

                {/* Quick Stats */}
                {isRunning && (
                  <div className="grid grid-cols-3 gap-4 mt-6 pt-6 border-t border-gray-100">
                    {[
                      { icon: "🔗", label_ar: "الرابط المباشر",     label_en: "Direct URL",      val: `${instance.subdomain}.odoo.clickbulid.com` },
                      { icon: "🛡️",  label_ar: "حالة SSL",           label_en: "SSL Status",      val: isAr ? "✅ فعّال" : "✅ Active" },
                      { icon: "💾",  label_ar: "آخر نسخ احتياطي",    label_en: "Last Backup",     val: isAr ? "اليوم" : "Today" },
                    ].map(s => (
                      <div key={s.label_ar} className="text-center p-3 bg-gray-50 rounded-xl">
                        <p className="text-lg mb-1">{s.icon}</p>
                        <p className="text-xs text-gray-400 mb-1">{isAr ? s.label_ar : s.label_en}</p>
                        <p className="text-sm font-bold text-gray-700 truncate">{s.val}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              /* No instance — prompt to create */
              <div className="bg-white rounded-3xl border-2 border-dashed border-emerald-200 p-12 mb-6 text-center">
                <div className="text-6xl mb-4">🚀</div>
                <h2 className="text-2xl font-black text-gray-900 mb-2">
                  {isAr ? "ابدأ الآن!" : "Get Started!"}
                </h2>
                <p className="text-gray-400 mb-8">
                  {isAr ? "اختر باقتك وسيتم إنشاء نظام Odoo الخاص بك في 5 دقائق" : "Choose your plan and your Odoo system will be ready in 5 minutes"}
                </p>
                <Link href={`/${locale}/pricing`}
                  className="inline-block bg-emerald-600 text-white font-black px-10 py-4 rounded-2xl text-lg hover:bg-emerald-700 transition">
                  {isAr ? "اختر باقتك" : "Choose Your Plan"}
                </Link>
              </div>
            )}

            {/* Subscription Info */}
            {subscription && (
              <div className="bg-white rounded-2xl border border-gray-100 p-6 mb-6">
                <h3 className="font-black text-gray-900 mb-4">{isAr ? "معلومات الاشتراك" : "Subscription Info"}</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {[
                    { label_ar: "الباقة",            label_en: "Plan",         val: subscription.plan_name },
                    { label_ar: "السعر الشهري",      label_en: "Monthly Price", val: `${Number(subscription.price_egp || 899).toLocaleString()} ر.س` },
                    { label_ar: "تاريخ الانتهاء",    label_en: "Expires",      val: subscription.end_date ? new Date(subscription.end_date).toLocaleDateString("ar-SA") : "—" },
                    { label_ar: "الحالة",            label_en: "Status",       val: subscription.status === "active" ? (isAr ? "✅ نشط" : "✅ Active") : subscription.status },
                  ].map(item => (
                    <div key={item.label_ar} className="text-center p-3 bg-gray-50 rounded-xl">
                      <p className="text-xs text-gray-400 mb-1">{isAr ? item.label_ar : item.label_en}</p>
                      <p className="font-bold text-gray-900 text-sm">{item.val}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Support Ticket */}
            <div className="bg-white rounded-2xl border border-gray-100 p-6">
              <h3 className="font-black text-gray-900 mb-1">{isAr ? "الدعم الفني" : "Support"}</h3>
              <p className="text-gray-400 text-sm mb-6">{isAr ? "هل تحتاج مساعدة؟ أرسل طلب دعم" : "Need help? Submit a support request"}</p>

              {ticketDone && (
                <div className="bg-emerald-50 text-emerald-700 px-4 py-3 rounded-xl text-sm mb-4 font-medium">
                  ✅ {isAr ? "تم إرسال طلبك بنجاح. سنرد في أقرب وقت." : "Request sent successfully. We'll respond shortly."}
                </div>
              )}

              <form onSubmit={submitTicket} className="space-y-4">
                <input
                  value={newTicket.subject}
                  onChange={e => setNewTicket(t => ({ ...t, subject: e.target.value }))}
                  placeholder={isAr ? "موضوع الطلب..." : "Subject..."}
                  required
                  className="w-full px-4 py-3 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-emerald-400"
                />
                <textarea
                  value={newTicket.message}
                  onChange={e => setNewTicket(t => ({ ...t, message: e.target.value }))}
                  placeholder={isAr ? "اكتب تفاصيل طلبك هنا..." : "Describe your issue..."}
                  required rows={3}
                  className="w-full px-4 py-3 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-emerald-400 resize-none"
                />
                <button type="submit" disabled={submitting}
                  className="bg-gray-900 text-white font-bold px-6 py-3 rounded-xl text-sm hover:bg-gray-800 transition disabled:opacity-50">
                  {submitting ? "..." : (isAr ? "إرسال الطلب" : "Submit Request")}
                </button>
              </form>

              {tickets.length > 0 && (
                <div className="mt-6 pt-6 border-t border-gray-100">
                  <p className="text-sm font-bold text-gray-700 mb-3">{isAr ? "طلباتك السابقة" : "Your Previous Tickets"}</p>
                  <div className="space-y-2">
                    {tickets.slice(0, 3).map((t: any) => (
                      <div key={t.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-xl text-sm">
                        <span className="text-gray-700 truncate">{t.subject}</span>
                        <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${
                          t.status === "open" ? "bg-amber-100 text-amber-700" :
                          t.status === "resolved" ? "bg-emerald-100 text-emerald-700" :
                          "bg-gray-200 text-gray-600"
                        }`}>{t.status}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

          </div>
        </main>
      </div>
    </div>
  );
}
'''

upload('/opt/clickbuild/frontend/src/app/[locale]/dashboard/page.tsx', DASHBOARD)

# ═════════════════════════════════════════════════════════════════
# 6. ADMIN DASHBOARD
# ═════════════════════════════════════════════════════════════════
ADMIN_LAYOUT = '''import Link from "next/link";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
'''
upload('/opt/clickbuild/frontend/src/app/[locale]/admin/layout.tsx', ADMIN_LAYOUT)

ADMIN_DASH = '''"use client";
import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth";

function AdminSidebar({ locale, isAr, active }: { locale: string; isAr: boolean; active: string }) {
  const { logout } = useAuthStore();
  const router = useRouter();
  const nav = [
    { icon: "📊", ar: "الإحصائيات",    en: "Dashboard",  href: "admin" },
    { icon: "👥", ar: "العملاء",        en: "Customers",  href: "admin/customers" },
    { icon: "🖥️", ar: "الأنظمة",        en: "Instances",  href: "admin/instances" },
    { icon: "💰", ar: "الإيرادات",      en: "Revenue",    href: "admin/billing" },
    { icon: "🎫", ar: "طلبات الدعم",   en: "Support",    href: "admin/support" },
  ];
  return (
    <aside className="w-56 min-h-screen bg-gray-900 text-gray-300 flex-shrink-0 flex flex-col fixed top-0 bottom-0">
      <div className="p-4 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-emerald-600 rounded-lg flex items-center justify-center">
            <span className="text-white font-black text-xs">CB</span>
          </div>
          <div>
            <p className="text-white font-black text-sm">كليك بيلد</p>
            <p className="text-gray-500 text-xs">{isAr ? "لوحة الإدارة" : "Admin Panel"}</p>
          </div>
        </div>
      </div>
      <nav className="flex-1 p-3 space-y-1">
        {nav.map(item => (
          <Link key={item.ar} href={`/${locale}/${item.href}`}
            className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition ${
              active === item.href
                ? "bg-emerald-600 text-white"
                : "text-gray-400 hover:bg-gray-800 hover:text-white"
            }`}>
            <span>{item.icon}</span>
            <span>{isAr ? item.ar : item.en}</span>
          </Link>
        ))}
      </nav>
      <div className="p-3 border-t border-gray-800">
        <Link href="/" target="_blank"
          className="flex items-center gap-2 px-3 py-2 text-xs text-gray-500 hover:text-gray-300 mb-1">
          🌐 {isAr ? "عرض الموقع" : "View Site"}
        </Link>
        <button
          onClick={() => { logout(); router.push(`/${locale}/login`); }}
          className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-500 hover:text-red-400 hover:bg-red-900/20 rounded-xl transition">
          🚪 {isAr ? "خروج" : "Logout"}
        </button>
      </div>
    </aside>
  );
}

export default function AdminPage() {
  const { locale } = useParams() as { locale: string };
  const isAr = locale === "ar";
  const router = useRouter();
  const { accessToken, user } = useAuthStore();

  const [stats, setStats] = useState<any>(null);
  const [instances, setInstances] = useState<any[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!accessToken) { router.push(`/${locale}/login`); return; }
    Promise.all([
      api.get("/admin/stats").then(r => setStats(r.data)).catch(() => {}),
      api.get("/admin/instances").then(r => setInstances(r.data.instances || r.data || [])).catch(() => {}),
      api.get("/admin/users").then(r => setUsers(r.data.users || r.data || [])).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, [accessToken]);

  const STAT_CARDS = [
    { icon: "👥", label_ar: "إجمالي العملاء",   label_en: "Total Customers",   val: stats?.total_users ?? users.length,       color: "blue" },
    { icon: "🖥️", label_ar: "أنظمة نشطة",       label_en: "Active Instances",  val: stats?.active_instances ?? instances.filter((i:any) => ["RUNNING","running"].includes(i.status)).length, color: "emerald" },
    { icon: "💰", label_ar: "الإيراد الشهري",    label_en: "Monthly Revenue",   val: `${(stats?.monthly_revenue || 0).toLocaleString()} ر.س`, color: "violet" },
    { icon: "🆕", label_ar: "جديد هذا الشهر",   label_en: "New This Month",    val: stats?.new_users_month ?? "—",            color: "amber" },
  ];

  const running   = instances.filter((i:any) => ["RUNNING","running"].includes(i.status));
  const errored   = instances.filter((i:any) => ["ERROR","error"].includes(i.status));
  const provision = instances.filter((i:any) => ["PROVISIONING","provisioning"].includes(i.status));

  return (
    <div className="min-h-screen bg-gray-50 flex" dir={isAr ? "rtl" : "ltr"}>
      <AdminSidebar locale={locale} isAr={isAr} active="admin" />

      <main className="flex-1 ms-56 p-8">
        <div className="max-w-6xl mx-auto">

          <div className="mb-8">
            <h1 className="text-2xl font-black text-gray-900">
              {isAr ? "لوحة التحكم الرئيسية" : "Admin Dashboard"}
            </h1>
            <p className="text-gray-400 text-sm mt-1">
              {isAr ? "نظرة عامة على المنصة" : "Platform overview"}
            </p>
          </div>

          {/* Stat Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-5 mb-8">
            {STAT_CARDS.map(s => (
              <div key={s.label_ar} className="bg-white rounded-2xl border border-gray-100 p-6 shadow-sm">
                <div className={`w-10 h-10 rounded-xl bg-${s.color}-100 flex items-center justify-center text-xl mb-4`}>
                  {s.icon}
                </div>
                <p className="text-2xl font-black text-gray-900 mb-1">{loading ? "—" : s.val}</p>
                <p className="text-sm text-gray-400">{isAr ? s.label_ar : s.label_en}</p>
              </div>
            ))}
          </div>

          {/* Instance Status Overview */}
          <div className="grid grid-cols-3 gap-5 mb-8">
            {[
              { label_ar: "✅ تعمل",       label_en: "✅ Running",     count: running.length,   color: "emerald" },
              { label_ar: "⏳ جاري الإنشاء", label_en: "⏳ Provisioning", count: provision.length, color: "amber" },
              { label_ar: "❌ أخطاء",       label_en: "❌ Errors",      count: errored.length,   color: "red" },
            ].map(s => (
              <div key={s.label_ar} className={`bg-${s.color}-50 border border-${s.color}-200 rounded-2xl p-5 text-center`}>
                <p className={`text-3xl font-black text-${s.color}-700 mb-1`}>{s.count}</p>
                <p className={`text-sm font-medium text-${s.color}-600`}>{isAr ? s.label_ar : s.label_en}</p>
              </div>
            ))}
          </div>

          {/* Recent Customers Table */}
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm mb-6">
            <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
              <h2 className="font-black text-gray-900">{isAr ? "آخر العملاء" : "Recent Customers"}</h2>
              <Link href={`/${locale}/admin/customers`}
                className="text-sm text-emerald-600 font-semibold hover:underline">
                {isAr ? "عرض الكل ←" : "View All →"}
              </Link>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-50">
                    {[
                      { ar: "العميل",    en: "Customer" },
                      { ar: "البريد",    en: "Email" },
                      { ar: "النظام",    en: "Instance" },
                      { ar: "الحالة",   en: "Status" },
                      { ar: "الإجراء",  en: "Action" },
                    ].map(h => (
                      <th key={h.ar} className="text-start px-6 py-3 text-xs font-bold text-gray-400 uppercase">
                        {isAr ? h.ar : h.en}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr><td colSpan={5} className="px-6 py-8 text-center text-gray-400">{isAr ? "جاري التحميل..." : "Loading..."}</td></tr>
                  ) : users.length === 0 ? (
                    <tr><td colSpan={5} className="px-6 py-8 text-center text-gray-400">{isAr ? "لا يوجد عملاء بعد" : "No customers yet"}</td></tr>
                  ) : users.slice(0, 8).map((u: any) => {
                    const inst = instances.find((i: any) => i.user_id === u.id || i.owner_id === u.id);
                    const isActive = inst && ["RUNNING","running"].includes(inst.status);
                    return (
                      <tr key={u.id} className="border-b border-gray-50 hover:bg-gray-50 transition">
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 bg-emerald-100 rounded-full flex items-center justify-center font-black text-emerald-700 text-xs flex-shrink-0">
                              {(u.name || u.email || "?").charAt(0).toUpperCase()}
                            </div>
                            <span className="font-medium text-gray-900">{u.name || "—"}</span>
                          </div>
                        </td>
                        <td className="px-6 py-4 text-gray-400">{u.email}</td>
                        <td className="px-6 py-4 font-mono text-xs text-gray-500">
                          {inst ? `${inst.subdomain}.odoo.clickbulid.com` : "—"}
                        </td>
                        <td className="px-6 py-4">
                          <span className={`px-2.5 py-1 rounded-full text-xs font-bold ${
                            isActive ? "bg-emerald-100 text-emerald-700" :
                            inst ? "bg-amber-100 text-amber-700" :
                            "bg-gray-100 text-gray-500"
                          }`}>
                            {isActive ? (isAr ? "✅ نشط" : "✅ Active") :
                             inst ? inst.status :
                             (isAr ? "بدون نظام" : "No instance")}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          <Link href={`/${locale}/admin/customers/${u.id}`}
                            className="text-xs text-emerald-600 font-semibold hover:underline">
                            {isAr ? "إدارة" : "Manage"}
                          </Link>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Recent Instances with Actions */}
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm">
            <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
              <h2 className="font-black text-gray-900">{isAr ? "الأنظمة النشطة" : "Active Instances"}</h2>
              <Link href={`/${locale}/admin/instances`}
                className="text-sm text-emerald-600 font-semibold hover:underline">
                {isAr ? "إدارة الكل ←" : "Manage All →"}
              </Link>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-50">
                    {["النطاق الفرعي","الحالة","المنفذ","إجراء"].map((h, i) => (
                      <th key={i} className="text-start px-6 py-3 text-xs font-bold text-gray-400 uppercase">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {instances.slice(0, 6).map((inst: any) => (
                    <tr key={inst.id} className="border-b border-gray-50 hover:bg-gray-50 transition">
                      <td className="px-6 py-4 font-mono text-sm font-bold text-gray-900">
                        {inst.subdomain}
                        <span className="text-gray-300">.odoo.clickbulid.com</span>
                      </td>
                      <td className="px-6 py-4">
                        <span className={`px-2.5 py-1 rounded-full text-xs font-bold ${
                          ["RUNNING","running"].includes(inst.status) ? "bg-emerald-100 text-emerald-700" :
                          ["ERROR","error"].includes(inst.status) ? "bg-red-100 text-red-700" :
                          "bg-amber-100 text-amber-700"
                        }`}>{inst.status}</span>
                      </td>
                      <td className="px-6 py-4 text-gray-400 font-mono">{inst.odoo_port}</td>
                      <td className="px-6 py-4">
                        <div className="flex gap-2">
                          <a href={`https://${inst.subdomain}.odoo.clickbulid.com`} target="_blank"
                            className="text-xs text-blue-600 hover:underline">↗ {isAr ? "فتح" : "Open"}</a>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

        </div>
      </main>
    </div>
  );
}
'''

upload('/opt/clickbuild/frontend/src/app/[locale]/admin/page.tsx', ADMIN_DASH)

# ═════════════════════════════════════════════════════════════════
# 7. ADMIN CUSTOMERS PAGE
# ═════════════════════════════════════════════════════════════════
run('mkdir -p "/opt/clickbuild/frontend/src/app/[locale]/admin/customers"')
run('mkdir -p "/opt/clickbuild/frontend/src/app/[locale]/admin/customers/[id]"')

ADMIN_CUSTOMERS = '''"use client";
import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth";

export default function AdminCustomersPage() {
  const { locale } = useParams() as { locale: string };
  const isAr = locale === "ar";
  const router = useRouter();
  const { accessToken } = useAuthStore();

  const [users, setUsers] = useState<any[]>([]);
  const [instances, setInstances] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");

  useEffect(() => {
    if (!accessToken) { router.push(`/${locale}/login`); return; }
    Promise.all([
      api.get("/admin/users").then(r => setUsers(r.data.users || r.data || [])),
      api.get("/admin/instances").then(r => setInstances(r.data.instances || r.data || [])),
    ]).finally(() => setLoading(false));
  }, [accessToken]);

  const filtered = users.filter(u => {
    const q = search.toLowerCase();
    const match = !q || u.name?.toLowerCase().includes(q) || u.email?.toLowerCase().includes(q);
    if (!match) return false;
    const inst = instances.find((i:any) => i.user_id === u.id || i.owner_id === u.id);
    if (filter === "active") return inst && ["RUNNING","running"].includes(inst.status);
    if (filter === "no_instance") return !inst;
    if (filter === "error") return inst && ["ERROR","error"].includes(inst.status);
    return true;
  });

  async function suspendInstance(instanceId: string) {
    if (!confirm(isAr ? "هل تريد تعليق هذا النظام؟" : "Suspend this instance?")) return;
    await api.post(`/admin/instances/${instanceId}/suspend`);
    const r = await api.get("/admin/instances");
    setInstances(r.data.instances || r.data || []);
  }
  async function resumeInstance(instanceId: string) {
    await api.post(`/admin/instances/${instanceId}/resume`);
    const r = await api.get("/admin/instances");
    setInstances(r.data.instances || r.data || []);
  }

  const SIDEBAR_NAV = [
    { icon: "📊", ar: "الإحصائيات",    en: "Dashboard",  href: "admin" },
    { icon: "👥", ar: "العملاء",        en: "Customers",  href: "admin/customers" },
    { icon: "🖥️", ar: "الأنظمة",        en: "Instances",  href: "admin/instances" },
    { icon: "💰", ar: "الإيرادات",      en: "Revenue",    href: "admin/billing" },
    { icon: "🎫", ar: "طلبات الدعم",   en: "Support",    href: "admin/support" },
  ];

  return (
    <div className="min-h-screen bg-gray-50 flex" dir={isAr ? "rtl" : "ltr"}>
      {/* Sidebar */}
      <aside className="w-56 min-h-screen bg-gray-900 text-gray-300 flex-shrink-0 flex flex-col fixed top-0 bottom-0">
        <div className="p-4 border-b border-gray-800">
          <Link href={`/${locale}`} className="flex items-center gap-2">
            <div className="w-8 h-8 bg-emerald-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-black text-xs">CB</span>
            </div>
            <div>
              <p className="text-white font-black text-sm">كليك بيلد</p>
              <p className="text-gray-500 text-xs">{isAr ? "لوحة الإدارة" : "Admin Panel"}</p>
            </div>
          </Link>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          {SIDEBAR_NAV.map(item => (
            <Link key={item.ar} href={`/${locale}/${item.href}`}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition ${
                item.href === "admin/customers"
                  ? "bg-emerald-600 text-white"
                  : "text-gray-400 hover:bg-gray-800 hover:text-white"
              }`}>
              <span>{item.icon}</span>
              <span>{isAr ? item.ar : item.en}</span>
            </Link>
          ))}
        </nav>
      </aside>

      <main className="flex-1 ms-56 p-8">
        <div className="max-w-6xl mx-auto">

          <div className="flex items-center justify-between mb-8">
            <div>
              <h1 className="text-2xl font-black text-gray-900">{isAr ? "إدارة العملاء" : "Customer Management"}</h1>
              <p className="text-gray-400 text-sm mt-1">{users.length} {isAr ? "عميل مسجل" : "registered customers"}</p>
            </div>
          </div>

          {/* Filters */}
          <div className="bg-white rounded-2xl border border-gray-100 p-4 mb-6 flex flex-col md:flex-row gap-4">
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder={isAr ? "🔍 بحث بالاسم أو البريد..." : "🔍 Search by name or email..."}
              className="flex-1 px-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-emerald-400"
            />
            <div className="flex gap-2">
              {[
                { key: "all",         ar: "الكل",       en: "All" },
                { key: "active",      ar: "نشط",        en: "Active" },
                { key: "error",       ar: "أخطاء",      en: "Errors" },
                { key: "no_instance", ar: "بدون نظام",  en: "No Instance" },
              ].map(f => (
                <button key={f.key}
                  onClick={() => setFilter(f.key)}
                  className={`px-4 py-2 rounded-xl text-sm font-medium transition ${
                    filter === f.key
                      ? "bg-emerald-600 text-white"
                      : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                  }`}>
                  {isAr ? f.ar : f.en}
                </button>
              ))}
            </div>
          </div>

          {/* Table */}
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead className="border-b border-gray-100 bg-gray-50">
                <tr>
                  {[
                    { ar: "العميل",           en: "Customer" },
                    { ar: "البريد الإلكتروني", en: "Email" },
                    { ar: "النظام",            en: "Instance" },
                    { ar: "الحالة",            en: "Status" },
                    { ar: "تاريخ التسجيل",    en: "Registered" },
                    { ar: "إجراءات",           en: "Actions" },
                  ].map(h => (
                    <th key={h.ar} className="text-start px-5 py-3.5 text-xs font-bold text-gray-400 uppercase">
                      {isAr ? h.ar : h.en}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan={6} className="py-16 text-center text-gray-400">{isAr ? "جاري التحميل..." : "Loading..."}</td></tr>
                ) : filtered.length === 0 ? (
                  <tr><td colSpan={6} className="py-16 text-center text-gray-400">{isAr ? "لا توجد نتائج" : "No results"}</td></tr>
                ) : filtered.map((u: any) => {
                  const inst = instances.find((i:any) => i.user_id === u.id || i.owner_id === u.id);
                  const isActive = inst && ["RUNNING","running"].includes(inst.status);
                  const isError = inst && ["ERROR","error"].includes(inst.status);
                  return (
                    <tr key={u.id} className="border-b border-gray-50 hover:bg-gray-50 transition">
                      <td className="px-5 py-4">
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 bg-emerald-100 rounded-full flex items-center justify-center font-black text-emerald-700 text-sm flex-shrink-0">
                            {(u.name || u.email).charAt(0).toUpperCase()}
                          </div>
                          <span className="font-bold text-gray-900">{u.name || "—"}</span>
                        </div>
                      </td>
                      <td className="px-5 py-4 text-gray-500">{u.email}</td>
                      <td className="px-5 py-4">
                        {inst ? (
                          <a href={`https://${inst.subdomain}.odoo.clickbulid.com`} target="_blank"
                            className="font-mono text-xs text-blue-600 hover:underline">
                            {inst.subdomain}.odoo.clickbulid.com ↗
                          </a>
                        ) : (
                          <span className="text-gray-300 text-xs">{isAr ? "لا يوجد نظام" : "No instance"}</span>
                        )}
                      </td>
                      <td className="px-5 py-4">
                        <span className={`px-2.5 py-1 rounded-full text-xs font-bold ${
                          isActive  ? "bg-emerald-100 text-emerald-700" :
                          isError   ? "bg-red-100 text-red-700" :
                          inst      ? "bg-amber-100 text-amber-700" :
                                      "bg-gray-100 text-gray-500"
                        }`}>
                          {isActive ? "✅ نشط" : isError ? "❌ خطأ" : inst ? inst.status : "—"}
                        </span>
                      </td>
                      <td className="px-5 py-4 text-gray-400 text-xs">
                        {u.created_at ? new Date(u.created_at).toLocaleDateString("ar-SA") : "—"}
                      </td>
                      <td className="px-5 py-4">
                        <div className="flex items-center gap-2">
                          <Link href={`/${locale}/admin/customers/${u.id}`}
                            className="text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 px-3 py-1.5 rounded-lg font-medium transition">
                            {isAr ? "إدارة" : "Manage"}
                          </Link>
                          {inst && (
                            isActive ? (
                              <button onClick={() => suspendInstance(inst.id)}
                                className="text-xs bg-amber-100 hover:bg-amber-200 text-amber-700 px-3 py-1.5 rounded-lg font-medium transition">
                                {isAr ? "تعليق" : "Suspend"}
                              </button>
                            ) : (
                              <button onClick={() => resumeInstance(inst.id)}
                                className="text-xs bg-emerald-100 hover:bg-emerald-200 text-emerald-700 px-3 py-1.5 rounded-lg font-medium transition">
                                {isAr ? "تشغيل" : "Resume"}
                              </button>
                            )
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

        </div>
      </main>
    </div>
  );
}
'''

upload('/opt/clickbuild/frontend/src/app/[locale]/admin/customers/page.tsx', ADMIN_CUSTOMERS)

# ═════════════════════════════════════════════════════════════════
# 8. ADMIN — Customer Detail Page
# ═════════════════════════════════════════════════════════════════
CUSTOMER_DETAIL = '''"use client";
import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth";

export default function CustomerDetailPage() {
  const { locale, id } = useParams() as { locale: string; id: string };
  const isAr = locale === "ar";
  const router = useRouter();
  const { accessToken } = useAuthStore();

  const [customer, setCustomer] = useState<any>(null);
  const [instance, setInstance] = useState<any>(null);
  const [logs, setLogs] = useState<string>("");
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState("");
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (!accessToken) { router.push(`/${locale}/login`); return; }
    loadData();
  }, [accessToken]);

  async function loadData() {
    setLoading(true);
    try {
      // get customer from users list
      const usersR = await api.get("/admin/users");
      const users = usersR.data.users || usersR.data || [];
      const cust = users.find((u: any) => u.id === id);
      setCustomer(cust);

      // find their instance
      const instR = await api.get("/admin/instances");
      const instances = instR.data.instances || instR.data || [];
      const inst = instances.find((i: any) => i.user_id === id || i.owner_id === id);
      setInstance(inst);

      // get instance stats + logs if available
      if (inst) {
        api.get(`/admin/instances/${inst.id}/stats`).then(r => setStats(r.data)).catch(() => {});
        api.get(`/admin/instances/${inst.id}/logs`).then(r => setLogs(r.data?.logs || "")).catch(() => {});
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  async function doAction(action: string) {
    if (!instance) return;
    setActionLoading(action);
    setMsg("");
    try {
      if (action === "suspend") {
        await api.post(`/admin/instances/${instance.id}/suspend`);
        setMsg(isAr ? "تم تعليق النظام بنجاح" : "Instance suspended successfully");
      } else if (action === "resume") {
        await api.post(`/admin/instances/${instance.id}/resume`);
        setMsg(isAr ? "تم تشغيل النظام بنجاح" : "Instance resumed successfully");
      } else if (action === "backup") {
        await api.post(`/admin/instances/${instance.id}/backup`);
        setMsg(isAr ? "جاري إنشاء نسخة احتياطية..." : "Backup in progress...");
      } else if (action === "delete") {
        if (!confirm(isAr ? "هل أنت متأكد من حذف هذا النظام؟ لا يمكن التراجع!" : "Are you sure? This cannot be undone!")) {
          setActionLoading(""); return;
        }
        await api.delete(`/admin/instances/${instance.id}`);
        router.push(`/${locale}/admin/customers`);
        return;
      }
      await loadData();
    } catch (e: any) {
      setMsg(e.response?.data?.detail || (isAr ? "حدث خطأ" : "Error occurred"));
    } finally {
      setActionLoading("");
    }
  }

  const isRunning = instance && ["RUNNING","running"].includes(instance.status);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center" dir={isAr ? "rtl" : "ltr"}>
        <div className="w-10 h-10 border-4 border-emerald-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50" dir={isAr ? "rtl" : "ltr"}>
      <div className="max-w-5xl mx-auto px-4 py-8">

        {/* Back */}
        <Link href={`/${locale}/admin/customers`}
          className="inline-flex items-center gap-2 text-sm text-gray-500 hover:text-gray-900 mb-6">
          ← {isAr ? "رجوع إلى العملاء" : "Back to Customers"}
        </Link>

        {/* Customer Header */}
        <div className="bg-white rounded-3xl border border-gray-100 p-8 mb-6 flex items-start justify-between">
          <div className="flex items-center gap-5">
            <div className="w-16 h-16 bg-emerald-100 rounded-2xl flex items-center justify-center text-3xl font-black text-emerald-700">
              {(customer?.name || customer?.email || "?").charAt(0).toUpperCase()}
            </div>
            <div>
              <h1 className="text-2xl font-black text-gray-900">{customer?.name || "—"}</h1>
              <p className="text-gray-400">{customer?.email}</p>
              <p className="text-gray-400 text-sm">{customer?.phone || ""}</p>
              <p className="text-xs text-gray-300 mt-1">
                {isAr ? "تسجيل:" : "Registered:"} {customer?.created_at ? new Date(customer.created_at).toLocaleDateString("ar-SA") : "—"}
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            {customer?.is_active ? (
              <span className="px-3 py-1 bg-emerald-100 text-emerald-700 text-sm font-bold rounded-full">✅ {isAr ? "نشط" : "Active"}</span>
            ) : (
              <span className="px-3 py-1 bg-red-100 text-red-700 text-sm font-bold rounded-full">❌ {isAr ? "موقوف" : "Inactive"}</span>
            )}
          </div>
        </div>

        {msg && (
          <div className="bg-emerald-50 border border-emerald-200 text-emerald-700 px-4 py-3 rounded-xl text-sm mb-6 font-medium">
            ✅ {msg}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

          {/* Instance Card */}
          <div className="bg-white rounded-2xl border border-gray-100 p-6">
            <h2 className="font-black text-gray-900 mb-4">{isAr ? "نظام Odoo" : "Odoo Instance"}</h2>
            {instance ? (
              <div className="space-y-3">
                {[
                  { label_ar: "النطاق الفرعي", label_en: "Subdomain",  val: instance.subdomain },
                  { label_ar: "الحالة",         label_en: "Status",     val: instance.status },
                  { label_ar: "المنفذ",          label_en: "Port",       val: instance.odoo_port },
                  { label_ar: "الإصدار",         label_en: "Version",    val: `Odoo ${instance.odoo_version || 17}` },
                  { label_ar: "تاريخ الإنشاء",  label_en: "Created",    val: instance.created_at ? new Date(instance.created_at).toLocaleDateString("ar-SA") : "—" },
                ].map(item => (
                  <div key={item.label_ar} className="flex justify-between items-center py-2 border-b border-gray-50">
                    <span className="text-sm text-gray-400">{isAr ? item.label_ar : item.label_en}</span>
                    <span className="text-sm font-bold text-gray-900">{item.val}</span>
                  </div>
                ))}
                <a href={`https://${instance.subdomain}.odoo.clickbulid.com`} target="_blank"
                  className="block w-full text-center bg-emerald-50 text-emerald-700 font-bold py-3 rounded-xl hover:bg-emerald-100 transition text-sm mt-4">
                  ↗ {isAr ? "فتح النظام" : "Open Instance"}
                </a>
              </div>
            ) : (
              <p className="text-gray-400 text-sm">{isAr ? "لا يوجد نظام لهذا العميل" : "No instance for this customer"}</p>
            )}
          </div>

          {/* Actions */}
          <div className="bg-white rounded-2xl border border-gray-100 p-6">
            <h2 className="font-black text-gray-900 mb-4">{isAr ? "الإجراءات" : "Actions"}</h2>
            <div className="space-y-3">
              {[
                {
                  action: "suspend", label_ar: "⏸ تعليق النظام",    label_en: "⏸ Suspend Instance",
                  color: "amber", disabled: !instance || !isRunning,
                  desc_ar: "إيقاف النظام مؤقتاً مع الحفاظ على البيانات",
                  desc_en: "Temporarily stop the system while preserving data",
                },
                {
                  action: "resume", label_ar: "▶ تشغيل النظام",    label_en: "▶ Resume Instance",
                  color: "emerald", disabled: !instance || isRunning,
                  desc_ar: "إعادة تشغيل النظام الموقوف",
                  desc_en: "Restart the suspended system",
                },
                {
                  action: "backup", label_ar: "💾 أخذ نسخة احتياطية", label_en: "💾 Take Backup",
                  color: "blue", disabled: !instance,
                  desc_ar: "إنشاء نسخة احتياطية فورية",
                  desc_en: "Create an immediate backup snapshot",
                },
                {
                  action: "delete", label_ar: "🗑 حذف النظام",      label_en: "🗑 Delete Instance",
                  color: "red", disabled: !instance,
                  desc_ar: "حذف النظام بشكل دائم — لا يمكن التراجع",
                  desc_en: "Permanently delete — cannot be undone",
                },
              ].map(a => (
                <button key={a.action}
                  onClick={() => doAction(a.action)}
                  disabled={a.disabled || actionLoading === a.action}
                  className={`w-full flex items-start gap-3 p-4 rounded-xl border text-start transition ${
                    a.disabled ? "opacity-40 cursor-not-allowed border-gray-100" :
                    a.action === "delete" ? "border-red-200 bg-red-50 hover:bg-red-100" :
                    `border-${a.color}-200 bg-${a.color}-50 hover:bg-${a.color}-100`
                  }`}>
                  <div>
                    <p className={`font-bold text-sm text-${a.action === "delete" ? "red" : a.color}-700`}>
                      {actionLoading === a.action ? "..." : (isAr ? a.label_ar : a.label_en)}
                    </p>
                    <p className="text-xs text-gray-400 mt-0.5">{isAr ? a.desc_ar : a.desc_en}</p>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Stats */}
          {stats && (
            <div className="bg-white rounded-2xl border border-gray-100 p-6">
              <h2 className="font-black text-gray-900 mb-4">{isAr ? "إحصائيات النظام" : "System Stats"}</h2>
              <div className="space-y-3">
                {Object.entries(stats).slice(0, 6).map(([key, val]) => (
                  <div key={key} className="flex justify-between py-2 border-b border-gray-50 text-sm">
                    <span className="text-gray-400">{key}</span>
                    <span className="font-bold text-gray-900">{String(val)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Logs */}
          {logs && (
            <div className="bg-white rounded-2xl border border-gray-100 p-6">
              <h2 className="font-black text-gray-900 mb-4">{isAr ? "سجلات النظام" : "Instance Logs"}</h2>
              <pre className="bg-gray-900 text-gray-300 text-xs p-4 rounded-xl overflow-auto max-h-48 font-mono">
                {logs.slice(-2000)}
              </pre>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
'''

upload('/opt/clickbuild/frontend/src/app/[locale]/admin/customers/[id]/page.tsx', CUSTOMER_DETAIL)

# ═════════════════════════════════════════════════════════════════
# 9. ADMIN INSTANCES PAGE (clean rebuild)
# ═════════════════════════════════════════════════════════════════
ADMIN_INSTANCES = '''"use client";
import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth";

export default function AdminInstancesPage() {
  const { locale } = useParams() as { locale: string };
  const isAr = locale === "ar";
  const { accessToken } = useAuthStore();
  const router = useRouter();

  const [instances, setInstances] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");

  useEffect(() => {
    if (!accessToken) { router.push(`/${locale}/login`); return; }
    api.get("/admin/instances")
      .then(r => setInstances(r.data.instances || r.data || []))
      .finally(() => setLoading(false));
  }, [accessToken]);

  const filtered = instances.filter(i => {
    if (filter === "running")     return ["RUNNING","running"].includes(i.status);
    if (filter === "error")       return ["ERROR","error"].includes(i.status);
    if (filter === "provisioning") return ["PROVISIONING","provisioning"].includes(i.status);
    return true;
  });

  async function suspend(id: string) {
    await api.post(`/admin/instances/${id}/suspend`);
    const r = await api.get("/admin/instances");
    setInstances(r.data.instances || r.data || []);
  }
  async function resume(id: string) {
    await api.post(`/admin/instances/${id}/resume`);
    const r = await api.get("/admin/instances");
    setInstances(r.data.instances || r.data || []);
  }

  const SIDEBAR_NAV = [
    { icon:"📊", ar:"الإحصائيات",  en:"Dashboard", href:"admin" },
    { icon:"👥", ar:"العملاء",      en:"Customers", href:"admin/customers" },
    { icon:"🖥️", ar:"الأنظمة",     en:"Instances", href:"admin/instances" },
    { icon:"💰", ar:"الإيرادات",    en:"Revenue",   href:"admin/billing" },
    { icon:"🎫", ar:"طلبات الدعم", en:"Support",   href:"admin/support" },
  ];

  return (
    <div className="min-h-screen bg-gray-50 flex" dir={isAr ? "rtl" : "ltr"}>
      <aside className="w-56 min-h-screen bg-gray-900 text-gray-300 flex-shrink-0 flex flex-col fixed top-0 bottom-0">
        <div className="p-4 border-b border-gray-800">
          <Link href={`/${locale}`} className="flex items-center gap-2">
            <div className="w-8 h-8 bg-emerald-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-black text-xs">CB</span>
            </div>
            <div>
              <p className="text-white font-black text-sm">كليك بيلد</p>
              <p className="text-gray-500 text-xs">{isAr ? "لوحة الإدارة" : "Admin Panel"}</p>
            </div>
          </Link>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          {SIDEBAR_NAV.map(item => (
            <Link key={item.ar} href={`/${locale}/${item.href}`}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition ${
                item.href === "admin/instances"
                  ? "bg-emerald-600 text-white"
                  : "text-gray-400 hover:bg-gray-800 hover:text-white"
              }`}>
              <span>{item.icon}</span>
              <span>{isAr ? item.ar : item.en}</span>
            </Link>
          ))}
        </nav>
      </aside>

      <main className="flex-1 ms-56 p-8">
        <div className="max-w-6xl mx-auto">
          <div className="mb-8">
            <h1 className="text-2xl font-black text-gray-900">{isAr ? "إدارة الأنظمة" : "Instance Management"}</h1>
            <p className="text-gray-400 text-sm mt-1">{instances.length} {isAr ? "نظام مسجل" : "registered instances"}</p>
          </div>

          {/* Filter Tabs */}
          <div className="flex gap-2 mb-6">
            {[
              { key:"all",          ar:`الكل (${instances.length})`,                                                  en:`All (${instances.length})` },
              { key:"running",      ar:`✅ نشط (${instances.filter(i=>["RUNNING","running"].includes(i.status)).length})`, en:`✅ Running` },
              { key:"error",        ar:`❌ خطأ (${instances.filter(i=>["ERROR","error"].includes(i.status)).length})`,    en:`❌ Error` },
              { key:"provisioning", ar:`⏳ يُنشأ`,                                                                       en:`⏳ Provisioning` },
            ].map(f => (
              <button key={f.key} onClick={() => setFilter(f.key)}
                className={`px-4 py-2 rounded-xl text-sm font-medium transition ${
                  filter===f.key ? "bg-emerald-600 text-white" : "bg-white border border-gray-200 text-gray-600 hover:border-emerald-300"
                }`}>
                {isAr ? f.ar : f.en}
              </button>
            ))}
          </div>

          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead className="border-b border-gray-100 bg-gray-50">
                <tr>
                  {["النطاق الفرعي","الحالة","المنفذ","الإصدار","الرابط","إجراءات"].map(h => (
                    <th key={h} className="text-start px-5 py-3.5 text-xs font-bold text-gray-400 uppercase">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan={6} className="py-16 text-center text-gray-400">جاري التحميل...</td></tr>
                ) : filtered.map((inst: any) => {
                  const isRunning = ["RUNNING","running"].includes(inst.status);
                  const isError   = ["ERROR","error"].includes(inst.status);
                  return (
                    <tr key={inst.id} className="border-b border-gray-50 hover:bg-gray-50 transition">
                      <td className="px-5 py-4 font-mono font-bold text-gray-900">{inst.subdomain}</td>
                      <td className="px-5 py-4">
                        <span className={`px-2.5 py-1 rounded-full text-xs font-bold ${
                          isRunning ? "bg-emerald-100 text-emerald-700" :
                          isError   ? "bg-red-100 text-red-700" :
                                      "bg-amber-100 text-amber-700"
                        }`}>{inst.status}</span>
                      </td>
                      <td className="px-5 py-4 text-gray-400 font-mono">{inst.odoo_port}</td>
                      <td className="px-5 py-4 text-gray-400">v{inst.odoo_version || 17}</td>
                      <td className="px-5 py-4">
                        <a href={`https://${inst.subdomain}.odoo.clickbulid.com`} target="_blank"
                          className="text-xs text-blue-600 hover:underline">
                          {inst.subdomain}.odoo.clickbulid.com ↗
                        </a>
                      </td>
                      <td className="px-5 py-4">
                        <div className="flex gap-2">
                          {isRunning ? (
                            <button onClick={() => suspend(inst.id)}
                              className="text-xs bg-amber-100 text-amber-700 hover:bg-amber-200 px-3 py-1.5 rounded-lg font-medium transition">
                              {isAr ? "تعليق" : "Suspend"}
                            </button>
                          ) : (
                            <button onClick={() => resume(inst.id)}
                              className="text-xs bg-emerald-100 text-emerald-700 hover:bg-emerald-200 px-3 py-1.5 rounded-lg font-medium transition">
                              {isAr ? "تشغيل" : "Resume"}
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  );
}
'''

upload('/opt/clickbuild/frontend/src/app/[locale]/admin/instances/page.tsx', ADMIN_INSTANCES)

print('\n✅ All pages uploaded!')
print('\nBuilding now...')

run('cd /opt/clickbuild/frontend && npm run build 2>&1 | tail -25', timeout=300)
run('pm2 restart clickbuild-frontend && sleep 4')
print('\nTesting routes...')
import time; time.sleep(4)
for path in ['/ar', '/ar/pricing', '/ar/register', '/ar/login', '/ar/dashboard', '/ar/admin', '/ar/admin/customers', '/ar/admin/instances']:
    code = run(f'curl -s -o /dev/null -w "%{{http_code}}" http://localhost:3000{path}')
    icon = '✅' if code.strip() in ['200','307','308'] else '❌'
    print(f'  {icon} {path} → {code}')

c.close()
