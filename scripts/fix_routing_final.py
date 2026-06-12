#!/usr/bin/env python3
"""
Fix routing once and for all:
1. Register page: window.location.href after success (bypasses RSC middleware issue)
2. Login page: same
3. Verify page: same
4. Landing page: back to server component (fixes next-intl hydration)
5. Dashboard: window.location for logout
"""
import paramiko, io, sys, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HOST = "129.121.98.243"; USER = "root"; PASS = "Mh@01007121878"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30)
sftp = client.open_sftp()

def upload(path, content):
    with sftp.open(path, 'w') as f:
        f.write(content)
    print(f"  ✓ {path}")

def run(cmd, timeout=60):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return (stdout.read() + stderr.read()).decode('utf-8', errors='replace')

print("=" * 60)
print("Fix routing — final")
print("=" * 60)

# ─── 1. register/page.tsx — use window.location.href ─────────────────
upload("/opt/clickbuild/frontend/src/app/[locale]/register/page.tsx", r"""'use client';
import { useState, FormEvent } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';

const API = process.env.NEXT_PUBLIC_API_URL ?? '/api/v1';

const COUNTRIES = [
  { value: 'EG', label: 'مصر 🇪🇬' },
  { value: 'SA', label: 'السعودية 🇸🇦' },
  { value: 'AE', label: 'الإمارات 🇦🇪' },
  { value: 'KW', label: 'الكويت 🇰🇼' },
  { value: 'QA', label: 'قطر 🇶🇦' },
  { value: 'BH', label: 'البحرين 🇧🇭' },
  { value: 'OM', label: 'عُمان 🇴🇲' },
  { value: 'JO', label: 'الأردن 🇯🇴' },
  { value: 'OTHER', label: 'دولة أخرى 🌍' },
];

export default function RegisterPage() {
  const params = useParams();
  const locale = (params?.locale as string) ?? 'ar';

  const [form, setForm] = useState({
    name: '', email: '', password: '', confirmPassword: '',
    phone: '', company_name: '', country: 'EG',
  });
  const [error, setError]     = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  function update(field: string, value: string) {
    setForm(prev => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    if (form.password !== form.confirmPassword) {
      setError('كلمتا المرور غير متطابقتين');
      return;
    }
    if (form.password.length < 8) {
      setError('كلمة المرور يجب أن تكون 8 أحرف على الأقل');
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${API}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name:         form.name,
          email:        form.email,
          password:     form.password,
          phone:        form.phone || null,
          company_name: form.company_name || null,
          country:      form.country,
          language:     'ar',
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail?.ar ?? data.detail ?? 'حدث خطأ، حاول مجدداً');
        return;
      }
      setSuccess(true);
      // Hard navigation so middleware sets locale correctly
      window.location.href = `/${locale}/verify?email=${encodeURIComponent(form.email)}`;
    } catch {
      setError('تعذر الاتصال بالخادم، تحقق من اتصالك بالإنترنت');
    } finally {
      setLoading(false);
    }
  }

  if (success) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-violet-950 via-violet-800 to-purple-700 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-8 text-center">
          <div className="text-6xl mb-4">📧</div>
          <h2 className="text-2xl font-black text-violet-800 mb-2">تم التسجيل!</h2>
          <p className="text-gray-500">جاري تحويلك لصفحة التحقق...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-violet-950 via-violet-800 to-purple-700 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg p-8">
        <div className="text-center mb-8">
          <Link href={`/${locale}`} className="text-3xl font-black text-violet-800">ClickBuild</Link>
          <p className="text-gray-500 mt-2">إنشاء حساب مجاني • 14 يوم تجريبي</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl p-3 text-sm text-center">
              {error}
            </div>
          )}

          <Field label="الاسم الكامل" required>
            <input type="text" required value={form.name}
              onChange={e => update('name', e.target.value)}
              placeholder="محمد أحمد" className={inputCls} />
          </Field>

          <Field label="البريد الإلكتروني" required>
            <input type="email" required value={form.email}
              onChange={e => update('email', e.target.value)}
              placeholder="you@company.com" className={inputCls} dir="ltr" />
          </Field>

          <Field label="اسم الشركة (اختياري)">
            <input type="text" value={form.company_name}
              onChange={e => update('company_name', e.target.value)}
              placeholder="شركة مثال للتجارة" className={inputCls} />
          </Field>

          <Field label="رقم الهاتف (اختياري)">
            <input type="tel" value={form.phone}
              onChange={e => update('phone', e.target.value)}
              placeholder="+20 10X XXX XXXX" className={inputCls} dir="ltr" />
          </Field>

          <Field label="الدولة" required>
            <select value={form.country} onChange={e => update('country', e.target.value)} className={inputCls}>
              {COUNTRIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
          </Field>

          <Field label="كلمة المرور" required>
            <input type="password" required value={form.password}
              onChange={e => update('password', e.target.value)}
              placeholder="8 أحرف على الأقل" className={inputCls} />
          </Field>

          <Field label="تأكيد كلمة المرور" required>
            <input type="password" required value={form.confirmPassword}
              onChange={e => update('confirmPassword', e.target.value)}
              placeholder="••••••••" className={inputCls} />
          </Field>

          <button type="submit" disabled={loading}
            className="w-full bg-violet-700 text-white font-bold py-3 rounded-xl hover:bg-violet-800 transition disabled:opacity-60 mt-2">
            {loading ? '⏳ جاري إنشاء الحساب...' : 'إنشاء حساب مجاني 🚀'}
          </button>

          <p className="text-center text-xs text-gray-400">
            بالتسجيل توافق على <a href="#" className="underline">شروط الاستخدام</a>
          </p>
        </form>

        <p className="text-center text-gray-500 text-sm mt-4">
          لديك حساب بالفعل؟{' '}
          <Link href={`/${locale}/login`} className="text-violet-700 font-semibold hover:underline">
            تسجيل الدخول
          </Link>
        </p>
      </div>
    </div>
  );
}

const inputCls = "w-full border border-gray-300 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent transition text-sm";

function Field({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        {label} {required && <span className="text-red-500">*</span>}
      </label>
      {children}
    </div>
  );
}
""")

# ─── 2. login/page.tsx — window.location.href ─────────────────────────
upload("/opt/clickbuild/frontend/src/app/[locale]/login/page.tsx", r"""'use client';
import { useState, FormEvent } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';

const API = process.env.NEXT_PUBLIC_API_URL ?? '/api/v1';

export default function LoginPage() {
  const params = useParams();
  const locale = (params?.locale as string) ?? 'ar';

  const [email, setEmail]       = useState('');
  const [password, setPassword] = useState('');
  const [error, setError]       = useState('');
  const [loading, setLoading]   = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await fetch(`${API}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail?.ar ?? data.detail ?? 'خطأ في البريد الإلكتروني أو كلمة المرور');
        return;
      }
      localStorage.setItem('clickbuild-auth', JSON.stringify({
        state: {
          user:         data.user,
          accessToken:  data.access_token,
          refreshToken: data.refresh_token,
        }
      }));
      // Hard navigation to ensure middleware runs
      window.location.href = `/${locale}/dashboard`;
    } catch {
      setError('تعذر الاتصال بالخادم');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-violet-950 via-violet-800 to-purple-700 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-8">
        <div className="text-center mb-8">
          <Link href={`/${locale}`} className="text-3xl font-black text-violet-800">ClickBuild</Link>
          <p className="text-gray-500 mt-2">تسجيل الدخول إلى حسابك</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl p-3 text-sm text-center">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">البريد الإلكتروني</label>
            <input type="email" required value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="you@example.com" dir="ltr"
              className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-violet-500 transition" />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">كلمة المرور</label>
            <input type="password" required value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-violet-500 transition" />
          </div>

          <button type="submit" disabled={loading}
            className="w-full bg-violet-700 text-white font-bold py-3 rounded-xl hover:bg-violet-800 transition disabled:opacity-60">
            {loading ? '⏳ جاري الدخول...' : 'تسجيل الدخول'}
          </button>
        </form>

        <div className="flex items-center justify-between mt-4 text-sm">
          <Link href={`/${locale}/register`} className="text-violet-700 hover:underline">
            إنشاء حساب جديد
          </Link>
          <span className="text-gray-400">·</span>
          <a href="#" className="text-gray-500 hover:underline">نسيت كلمة المرور؟</a>
        </div>
      </div>
    </div>
  );
}
""")

# ─── 3. verify/page.tsx — window.location.href ────────────────────────
upload("/opt/clickbuild/frontend/src/app/[locale]/verify/page.tsx", r"""'use client';
import { useState, FormEvent, Suspense } from 'react';
import { useSearchParams, useParams } from 'next/navigation';
import Link from 'next/link';

const API = process.env.NEXT_PUBLIC_API_URL ?? '/api/v1';

function VerifyContent() {
  const searchParams = useSearchParams();
  const params       = useParams();
  const locale       = (params?.locale as string) ?? 'ar';
  const emailParam   = searchParams.get('email') ?? '';

  const [email, setEmail]     = useState(emailParam);
  const [code, setCode]       = useState('');
  const [error, setError]     = useState('');
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [resent, setResent]   = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await fetch(`${API}/auth/verify-email`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, code }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail?.ar ?? data.detail ?? 'الكود غير صحيح أو منتهي الصلاحية');
        return;
      }
      setSuccess(true);
      setTimeout(() => {
        window.location.href = `/${locale}/login`;
      }, 2000);
    } catch {
      setError('تعذر الاتصال بالخادم');
    } finally {
      setLoading(false);
    }
  }

  async function resendCode() {
    if (!email || resending) return;
    setResending(true);
    setResent(false);
    try {
      await fetch(`${API}/auth/resend-verification`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      setResent(true);
    } finally {
      setResending(false);
    }
  }

  if (success) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-violet-950 via-violet-800 to-purple-700 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-8 text-center">
          <div className="text-6xl mb-4">✅</div>
          <h2 className="text-2xl font-black text-violet-800 mb-2">تم تأكيد البريد!</h2>
          <p className="text-gray-500">جاري تحويلك لصفحة الدخول...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-violet-950 via-violet-800 to-purple-700 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-8">
        <div className="text-center mb-8">
          <div className="text-5xl mb-3">📧</div>
          <h1 className="text-2xl font-black text-violet-800">تأكيد البريد الإلكتروني</h1>
          <p className="text-gray-500 mt-2 text-sm">
            أرسلنا كود تحقق من 6 أرقام إلى{' '}
            <span className="font-semibold text-gray-700">{email || 'بريدك الإلكتروني'}</span>
          </p>
        </div>

        {resent && (
          <div className="bg-green-50 border border-green-200 text-green-700 rounded-xl p-3 text-sm text-center mb-4">
            ✅ تم إعادة إرسال الكود
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl p-3 text-sm text-center">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">البريد الإلكتروني</label>
            <input type="email" required value={email}
              onChange={e => setEmail(e.target.value)} dir="ltr"
              className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-violet-500 transition text-sm" />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">كود التحقق</label>
            <input
              type="text" required value={code} maxLength={6}
              onChange={e => setCode(e.target.value.replace(/\D/g, ''))}
              placeholder="123456"
              className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-violet-500 transition text-center text-3xl tracking-widest font-mono"
              dir="ltr"
            />
          </div>

          <button type="submit" disabled={loading || code.length < 6}
            className="w-full bg-violet-700 text-white font-bold py-3 rounded-xl hover:bg-violet-800 transition disabled:opacity-60">
            {loading ? '⏳ جاري التحقق...' : 'تأكيد الحساب'}
          </button>
        </form>

        <div className="flex items-center justify-between mt-6 text-sm">
          <button onClick={resendCode} disabled={resending}
            className="text-violet-700 hover:underline disabled:opacity-50 font-medium">
            {resending ? '...' : 'إعادة إرسال الكود'}
          </button>
          <Link href={`/${locale}/register`} className="text-gray-500 hover:underline">
            تغيير البريد الإلكتروني
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function VerifyPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-gradient-to-br from-violet-950 to-purple-700 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-white" />
      </div>
    }>
      <VerifyContent />
    </Suspense>
  );
}
""")

# ─── 4. dashboard — fix logout to use window.location ─────────────────
with sftp.open('/opt/clickbuild/frontend/src/app/[locale]/dashboard/page.tsx', 'r') as f:
    dash = f.read().decode('utf-8', errors='replace')

# Replace router.push('/login') with window.location.href
dash = dash.replace(
    "router.push(`/${locale}/login`)",
    "window.location.href = `/${locale}/login`"
).replace(
    "router.push('/login')",
    "window.location.href = `/${locale}/login`"
)

with sftp.open('/opt/clickbuild/frontend/src/app/[locale]/dashboard/page.tsx', 'w') as f:
    f.write(dash)
print("  ✓ dashboard logout fixed")

# ─── 5. Landing page — back to server component ────────────────────────
upload("/opt/clickbuild/frontend/src/app/[locale]/page.tsx", """import { getTranslations } from 'next-intl/server';
import Link from 'next/link';

export default async function HomePage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const isAr = locale === 'ar';
  const th = await getTranslations({ locale, namespace: 'hero' });
  const tf = await getTranslations({ locale, namespace: 'features' });

  const features = [
    { key: 'accounting', icon: '📊' },
    { key: 'sales',      icon: '💼' },
    { key: 'inventory',  icon: '📦' },
    { key: 'hr',         icon: '👥' },
    { key: 'crm',        icon: '🎯' },
    { key: 'pos',        icon: '🛒' },
  ] as const;

  const PLANS = isAr ? [
    { name: 'مبتدئ',  price: '199', period: 'ج.م / شهر', desc: 'للشركات الصغيرة',     users: '5 مستخدمين',  popular: false },
    { name: 'أعمال',  price: '499', period: 'ج.م / شهر', desc: 'للشركات المتنامية',   users: '25 مستخدماً', popular: true  },
    { name: 'مؤسسي',  price: '999', period: 'ج.م / شهر', desc: 'للمؤسسات الكبيرة',   users: '100 مستخدم',  popular: false },
  ] : [
    { name: 'Starter',    price: '199', period: 'EGP / mo', desc: 'For small businesses', users: '5 users',   popular: false },
    { name: 'Business',   price: '499', period: 'EGP / mo', desc: 'For growing companies', users: '25 users', popular: true  },
    { name: 'Enterprise', price: '999', period: 'EGP / mo', desc: 'For large orgs',         users: '100 users',popular: false },
  ];

  return (
    <main className="min-h-screen bg-white" dir={isAr ? 'rtl' : 'ltr'}>

      {/* Nav */}
      <nav className="sticky top-0 z-50 bg-white/90 backdrop-blur-md border-b border-gray-100">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
          <span className="text-2xl font-black text-violet-700">ClickBuild</span>
          <div className="hidden md:flex items-center gap-6 text-sm text-gray-600">
            <a href="#features" className="hover:text-gray-900 transition">{isAr ? 'المميزات' : 'Features'}</a>
            <Link href={`/${locale}/pricing`} className="hover:text-gray-900 transition">{isAr ? 'الأسعار' : 'Pricing'}</Link>
          </div>
          <div className="flex gap-2">
            <Link href={`/${locale}/login`}
              className="text-gray-600 hover:text-gray-900 px-4 py-2 rounded-lg transition text-sm">
              {isAr ? 'دخول' : 'Login'}
            </Link>
            <Link href={`/${locale}/register`}
              className="bg-violet-700 text-white px-4 py-2 rounded-lg hover:bg-violet-800 transition text-sm font-medium">
              {isAr ? 'ابدأ مجاناً' : 'Start Free'}
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative overflow-hidden bg-gradient-to-br from-violet-950 via-violet-800 to-purple-700 text-white">
        <div className="absolute inset-0 bg-[url('/grid.svg')] opacity-10" />
        <div className="relative max-w-6xl mx-auto px-4 py-24 text-center">
          <span className="inline-block bg-violet-500/30 border border-violet-400/40 text-violet-200 text-sm px-4 py-1 rounded-full mb-6">
            ✨ {th('badge')}
          </span>
          <h1 className="text-5xl md:text-7xl font-black mb-6 leading-tight">
            {th('title')}{' '}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-yellow-300 to-orange-400">
              {th('titleHighlight')}
            </span>
          </h1>
          <p className="text-xl text-violet-200 max-w-2xl mx-auto mb-10">{th('subtitle')}</p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link href={`/${locale}/register`}
              className="bg-white text-violet-900 font-bold px-8 py-4 rounded-xl text-lg hover:bg-violet-50 transition shadow-lg">
              🚀 {th('cta')}
            </Link>
            <Link href={`/${locale}/pricing`}
              className="border border-white/30 text-white px-8 py-4 rounded-xl text-lg hover:bg-white/10 transition">
              {isAr ? 'عرض الأسعار' : 'View Pricing'}
            </Link>
          </div>
          <p className="text-violet-300 text-sm mt-4">{th('ctaSub')}</p>
          <div className="grid grid-cols-3 gap-8 max-w-xl mx-auto mt-16 pt-8 border-t border-white/20">
            {[
              { value: '500+', label: th('stats.clients') },
              { value: '99.9%', label: th('stats.uptime') },
              { value: '24/7', label: th('stats.support') },
            ].map(s => (
              <div key={s.label}>
                <div className="text-3xl font-black text-yellow-300">{s.value}</div>
                <div className="text-violet-300 text-sm">{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-24 bg-gray-50">
        <div className="max-w-6xl mx-auto px-4">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-black text-gray-900 mb-4">{tf('title')}</h2>
            <p className="text-gray-600 text-xl">{tf('subtitle')}</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map(({ key, icon }) => (
              <div key={key} className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 hover:shadow-md hover:-translate-y-1 transition-all">
                <div className="text-4xl mb-4">{icon}</div>
                <h3 className="text-xl font-bold text-gray-900 mb-2">{tf(`${key}.title`)}</h3>
                <p className="text-gray-600">{tf(`${key}.desc`)}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing Preview */}
      <section id="pricing" className="py-24 bg-white">
        <div className="max-w-5xl mx-auto px-4">
          <div className="text-center mb-12">
            <h2 className="text-4xl font-black text-gray-900 mb-4">
              {isAr ? 'أسعار شفافة وبسيطة' : 'Simple, Transparent Pricing'}
            </h2>
            <p className="text-gray-500 text-xl">
              {isAr ? 'جميع الخطط تشمل 14 يوم تجريبي مجاني' : 'All plans include a 14-day free trial'}
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            {PLANS.map(plan => (
              <div key={plan.name} className={`relative rounded-2xl p-6 border-2 ${plan.popular ? 'border-violet-500 shadow-xl' : 'border-gray-200 shadow-sm'}`}>
                {plan.popular && (
                  <span className="absolute -top-3 left-1/2 -translate-x-1/2 bg-violet-700 text-white text-xs px-3 py-1 rounded-full font-bold whitespace-nowrap">
                    {isAr ? '⭐ الأكثر شعبية' : '⭐ Most Popular'}
                  </span>
                )}
                <h3 className="font-black text-gray-900 text-xl mb-1">{plan.name}</h3>
                <p className="text-gray-400 text-sm mb-3">{plan.desc}</p>
                <div className="text-3xl font-black text-violet-700">{plan.price}</div>
                <div className="text-gray-400 text-sm mb-4">{plan.period}</div>
                <div className="text-sm text-gray-600">👥 {plan.users}</div>
              </div>
            ))}
          </div>
          <div className="text-center">
            <Link href={`/${locale}/pricing`}
              className="inline-block bg-violet-700 text-white px-8 py-3 rounded-xl font-bold hover:bg-violet-800 transition">
              {isAr ? 'مقارنة جميع الخطط ←' : 'Compare All Plans →'}
            </Link>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="py-20 bg-gray-50">
        <div className="max-w-4xl mx-auto px-4 text-center">
          <h2 className="text-3xl font-black text-gray-900 mb-4">
            {isAr ? 'كيف يعمل ClickBuild؟' : 'How does ClickBuild work?'}
          </h2>
          <p className="text-gray-500 text-lg mb-12">
            {isAr ? 'من التسجيل إلى نظام جاهز في أقل من دقيقة' : 'From signup to a ready system in under 60 seconds'}
          </p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            {(isAr ? [
              { n:'١', icon:'📝', t:'سجّل حساباً',   d:'مجاناً في 30 ثانية' },
              { n:'٢', icon:'📋', t:'اختر خطتك',     d:'14 يوم تجريبي' },
              { n:'٣', icon:'⚙️', t:'خصّص نظامك',    d:'اختر الوحدات' },
              { n:'٤', icon:'🚀', t:'ابدأ العمل',    d:'جاهز في 30 ثانية' },
            ] : [
              { n:'1', icon:'📝', t:'Create Account', d:'Free in 30 seconds' },
              { n:'2', icon:'📋', t:'Choose Plan',    d:'14-day free trial' },
              { n:'3', icon:'⚙️', t:'Customize',      d:'Pick your modules' },
              { n:'4', icon:'🚀', t:'Start Working',  d:'Ready in 30 seconds' },
            ]).map(s => (
              <div key={s.n} className="flex flex-col items-center">
                <div className="w-10 h-10 rounded-full bg-violet-100 text-violet-700 flex items-center justify-center font-black mb-2">{s.n}</div>
                <div className="text-3xl mb-2">{s.icon}</div>
                <h3 className="font-bold text-gray-900 mb-1 text-sm">{s.t}</h3>
                <p className="text-gray-500 text-xs">{s.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 bg-violet-700 text-white text-center">
        <div className="max-w-2xl mx-auto px-4">
          <h2 className="text-4xl font-black mb-4">
            {isAr ? 'ابدأ الآن مجاناً' : 'Start For Free Today'}
          </h2>
          <p className="text-violet-200 text-xl mb-8">
            {isAr ? '14 يوم تجريبي • لا يلزم بطاقة ائتمان' : '14-day trial • No credit card required'}
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link href={`/${locale}/register`}
              className="bg-white text-violet-900 font-bold px-10 py-4 rounded-xl text-lg hover:bg-violet-50 transition">
              {isAr ? 'إنشاء حساب مجاني' : 'Create Free Account'}
            </Link>
            <Link href={`/${locale}/pricing`}
              className="border border-white/30 text-white px-10 py-4 rounded-xl text-lg hover:bg-white/10 transition">
              {isAr ? 'عرض الأسعار' : 'View Pricing'}
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-gray-900 text-gray-400 py-10">
        <div className="max-w-6xl mx-auto px-4 flex flex-col md:flex-row items-center justify-between gap-4">
          <span className="text-white font-black text-xl">ClickBuild</span>
          <div className="flex gap-6 text-sm">
            <Link href={`/${locale}/pricing`} className="hover:text-white transition">{isAr ? 'الأسعار' : 'Pricing'}</Link>
            <Link href={`/${locale}/register`} className="hover:text-white transition">{isAr ? 'إنشاء حساب' : 'Sign Up'}</Link>
            <Link href={`/${locale}/login`} className="hover:text-white transition">{isAr ? 'دخول' : 'Login'}</Link>
          </div>
          <p className="text-sm">© 2024 ClickBuild. {isAr ? 'جميع الحقوق محفوظة' : 'All rights reserved.'}</p>
        </div>
      </footer>

    </main>
  );
}
""")

sftp.close()
print()
print("Building...")
stdin, stdout, stderr = client.exec_command('cd /opt/clickbuild/frontend && npm run build 2>&1', timeout=240)
output = stdout.read().decode('utf-8', errors='replace')
lines = output.strip().split('\n')
has_error = False
for line in lines:
    if 'error' in line.lower() or 'Error' in line:
        print(f"ERR: {line}")
        has_error = True
    if any(k in line for k in ['Route ', '✓', 'compiled', 'Failed']):
        print(line)

if has_error:
    print("\nFull last 25 lines:")
    print('\n'.join(lines[-25:]))
else:
    print()
    print(run('pm2 restart clickbuild-frontend && sleep 4', 15))
    # Test
    for path in ['/ar', '/ar/register', '/ar/login', '/ar/verify', '/ar/pricing']:
        code = run('curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3000' + path).strip()
        print(f"  {'OK' if code=='200' else 'FAIL'} {path} — {code}")

client.close()
print("\nDone.")
