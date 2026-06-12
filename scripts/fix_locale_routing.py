#!/usr/bin/env python3
"""Fix locale-aware routing in all auth pages"""
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

def run(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return (stdout.read() + stderr.read()).decode('utf-8', errors='replace')

print("Fixing locale routing in auth pages...")

# ─── register/page.tsx ────────────────────────────────────────────────
upload("/opt/clickbuild/frontend/src/app/[locale]/register/page.tsx", r"""'use client';
import { useState, FormEvent } from 'react';
import { useRouter, useParams } from 'next/navigation';
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
  const router = useRouter();
  const params = useParams();
  const locale = (params?.locale as string) ?? 'ar';

  const [form, setForm] = useState({
    name: '', email: '', password: '', confirmPassword: '',
    phone: '', company_name: '', country: 'EG',
  });
  const [error, setError]     = useState('');
  const [loading, setLoading] = useState(false);

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
        setError(data.detail?.ar ?? data.detail ?? 'حدث خطأ');
        return;
      }
      router.push(`/${locale}/verify?email=${encodeURIComponent(form.email)}`);
    } catch {
      setError('تعذر الاتصال بالخادم');
    } finally {
      setLoading(false);
    }
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
              placeholder="you@company.com" className={inputCls} />
          </Field>
          <Field label="اسم الشركة (اختياري)">
            <input type="text" value={form.company_name}
              onChange={e => update('company_name', e.target.value)}
              placeholder="شركة مثال للتجارة" className={inputCls} />
          </Field>
          <Field label="رقم الهاتف (اختياري)">
            <input type="tel" value={form.phone}
              onChange={e => update('phone', e.target.value)}
              placeholder="+20 10X XXX XXXX" className={inputCls} />
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
            {loading ? 'جاري إنشاء الحساب...' : 'إنشاء حساب مجاني 🚀'}
          </button>
          <p className="text-center text-xs text-gray-400">
            بالتسجيل توافق على شروط الاستخدام وسياسة الخصوصية
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

# ─── verify/page.tsx ──────────────────────────────────────────────────
upload("/opt/clickbuild/frontend/src/app/[locale]/verify/page.tsx", r"""'use client';
import { useState, FormEvent, Suspense } from 'react';
import { useRouter, useSearchParams, useParams } from 'next/navigation';
import Link from 'next/link';

const API = process.env.NEXT_PUBLIC_API_URL ?? '/api/v1';

function VerifyContent() {
  const router       = useRouter();
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
        setError(data.detail?.ar ?? data.detail ?? 'الكود غير صحيح');
        return;
      }
      setSuccess(true);
      setTimeout(() => router.push(`/${locale}/login`), 2500);
    } catch {
      setError('تعذر الاتصال بالخادم');
    } finally {
      setLoading(false);
    }
  }

  async function resendCode() {
    if (!email) return;
    setResending(true);
    try {
      await fetch(`${API}/auth/resend-verification`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
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
            أرسلنا كود مكوّن من 6 أرقام إلى <strong>{email}</strong>
          </p>
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
              className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-violet-500 transition" />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">كود التحقق</label>
            <input type="text" required value={code} maxLength={6}
              onChange={e => setCode(e.target.value.replace(/\D/g, ''))}
              placeholder="123456"
              className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-violet-500 transition text-center text-2xl tracking-widest font-mono" />
          </div>

          <button type="submit" disabled={loading || code.length < 6}
            className="w-full bg-violet-700 text-white font-bold py-3 rounded-xl hover:bg-violet-800 transition disabled:opacity-60">
            {loading ? 'جاري التحقق...' : 'تأكيد'}
          </button>
        </form>

        <div className="flex items-center justify-between mt-6 text-sm text-gray-500">
          <button onClick={resendCode} disabled={resending}
            className="text-violet-700 font-semibold hover:underline disabled:opacity-50">
            {resending ? 'جاري الإرسال...' : 'إعادة إرسال الكود'}
          </button>
          <Link href={`/${locale}/register`} className="hover:underline">
            تغيير البريد
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function VerifyPage() {
  return <Suspense><VerifyContent /></Suspense>;
}
""")

# ─── login/page.tsx ───────────────────────────────────────────────────
upload("/opt/clickbuild/frontend/src/app/[locale]/login/page.tsx", r"""'use client';
import { useState, FormEvent } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';

const API = process.env.NEXT_PUBLIC_API_URL ?? '/api/v1';

export default function LoginPage() {
  const router = useRouter();
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
        setError(data.detail?.ar ?? data.detail ?? 'خطأ في تسجيل الدخول');
        return;
      }
      localStorage.setItem('clickbuild-auth', JSON.stringify({
        state: {
          user:         data.user,
          accessToken:  data.access_token,
          refreshToken: data.refresh_token,
        }
      }));
      router.push(`/${locale}/dashboard`);
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
          <p className="text-gray-500 mt-2">تسجيل الدخول</p>
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
              placeholder="you@example.com"
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
            {loading ? 'جاري الدخول...' : 'تسجيل الدخول'}
          </button>
        </form>

        <p className="text-center text-gray-500 text-sm mt-6">
          ليس لديك حساب؟{' '}
          <Link href={`/${locale}/register`} className="text-violet-700 font-semibold hover:underline">
            سجل مجاناً
          </Link>
        </p>
      </div>
    </div>
  );
}
""")

# ─── Fix dashboard logout/links ───────────────────────────────────────
# Read current dashboard
with sftp.open('/opt/clickbuild/frontend/src/app/[locale]/dashboard/page.tsx', 'r') as f:
    dash = f.read().decode('utf-8', errors='replace')

# Check if already has useParams
if 'useParams' not in dash:
    # Add useParams to import and fix router.push('/login') → locale-aware
    dash = dash.replace(
        "import { useRouter } from 'next/navigation';",
        "import { useRouter, useParams } from 'next/navigation';"
    )
    # Add locale extraction after useRouter
    dash = dash.replace(
        "  const router  = useRouter();",
        "  const router  = useRouter();\n  const params   = useParams();\n  const locale   = (params?.locale as string) ?? 'ar';"
    )
    # Fix all router.push('/login')
    dash = dash.replace("router.push('/login')", "router.push(`/${locale}/login`)")
    # Fix all router.push('/dashboard')
    dash = dash.replace("router.push('/dashboard')", "router.push(`/${locale}/dashboard`)")
    # Fix Link href="/create"
    dash = dash.replace('href="/create"', 'href={`/${locale}/create`}')
    dash = dash.replace('href="/onboarding"', 'href={`/${locale}/onboarding`}')

    with sftp.open('/opt/clickbuild/frontend/src/app/[locale]/dashboard/page.tsx', 'w') as f:
        f.write(dash)
    print("  ✓ dashboard patched")
else:
    print("  ✓ dashboard already has useParams")

sftp.close()

# Build
print("\nBuilding frontend...")
stdin, stdout, stderr = client.exec_command(
    'cd /opt/clickbuild/frontend && npm run build 2>&1', timeout=240
)
output = stdout.read().decode('utf-8', errors='replace')
lines = output.strip().split('\n')
# Print summary
for line in lines:
    if any(k in line for k in ['Route', 'locale', 'Error', 'error TS', 'Failed', 'compiled', '✓', 'locale']):
        print(line)

has_error = 'Error' in output and 'error' in output.lower()
print()
if has_error:
    print("BUILD FAILED — last 20 lines:")
    print('\n'.join(lines[-20:]))
else:
    print("Build OK. Restarting...")
    print(run('pm2 restart clickbuild-frontend && sleep 3 && pm2 show clickbuild-frontend | grep -E "status"', 20))

client.close()
