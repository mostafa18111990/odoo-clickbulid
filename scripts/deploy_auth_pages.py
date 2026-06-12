#!/usr/bin/env python
"""Deploy Login, Register, Verify pages and rebuild frontend"""
import paramiko
import io
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HOST = "129.121.98.243"
USER = "root"
PASS = "Mh@01007121878"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30)
sftp = client.open_sftp()

def write_file(remote_path, content):
    # Ensure directory exists
    remote_dir = "/".join(remote_path.split("/")[:-1])
    client.exec_command(f"mkdir -p '{remote_dir}'")
    time.sleep(0.2)
    sftp.putfo(io.BytesIO(content.encode('utf-8')), remote_path)
    print(f"  [OK] {remote_path}")


# ─── Login Page ───────────────────────────────────────────────────────────────
write_file("/opt/clickbuild/frontend/src/app/[locale]/login/page.tsx", """\
'use client';
import { useState, FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

const API = process.env.NEXT_PUBLIC_API_URL ?? '/api/v1';

export default function LoginPage() {
  const router = useRouter();
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
      // Store auth in localStorage (same format as dashboard expects)
      localStorage.setItem('clickbuild-auth', JSON.stringify({
        state: { user: data.user, accessToken: data.access_token, refreshToken: data.refresh_token }
      }));
      router.push('/dashboard');
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
          <h1 className="text-3xl font-black text-violet-800">OdooClickBuild</h1>
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
            <input
              type="email" required value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent transition"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">كلمة المرور</label>
            <input
              type="password" required value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent transition"
            />
          </div>

          <div className="text-left">
            <Link href="/forgot-password" className="text-sm text-violet-600 hover:underline">
              نسيت كلمة المرور؟
            </Link>
          </div>

          <button
            type="submit" disabled={loading}
            className="w-full bg-violet-700 text-white font-bold py-3 rounded-xl hover:bg-violet-800 transition disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {loading ? 'جاري الدخول...' : 'تسجيل الدخول'}
          </button>
        </form>

        <p className="text-center text-gray-500 text-sm mt-6">
          ليس لديك حساب؟{' '}
          <Link href="/register" className="text-violet-700 font-semibold hover:underline">
            سجل مجاناً
          </Link>
        </p>
      </div>
    </div>
  );
}
""")


# ─── Register Page ────────────────────────────────────────────────────────────
write_file("/opt/clickbuild/frontend/src/app/[locale]/register/page.tsx", """\
'use client';
import { useState, FormEvent } from 'react';
import { useRouter } from 'next/navigation';
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
  { value: 'LB', label: 'لبنان 🇱🇧' },
  { value: 'OTHER', label: 'دولة أخرى 🌍' },
];

export default function RegisterPage() {
  const router = useRouter();
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
      // Redirect to verify with email
      router.push(`/verify?email=${encodeURIComponent(form.email)}`);
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
          <h1 className="text-3xl font-black text-violet-800">OdooClickBuild</h1>
          <p className="text-gray-500 mt-2">إنشاء حساب مجاني • 14 يوم تجريبي</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl p-3 text-sm text-center">
              {error}
            </div>
          )}

          <div className="grid grid-cols-1 gap-4">
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
                placeholder="+966 5X XXX XXXX" className={inputCls} />
            </Field>

            <Field label="الدولة" required>
              <select value={form.country} onChange={e => update('country', e.target.value)} className={inputCls}>
                {COUNTRIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
              </select>
            </Field>

            <Field label="كلمة المرور" required>
              <input type="password" required value={form.password}
                onChange={e => update('password', e.target.value)}
                placeholder="8 أحرف على الأقل + حرف كبير + رقم" className={inputCls} />
            </Field>

            <Field label="تأكيد كلمة المرور" required>
              <input type="password" required value={form.confirmPassword}
                onChange={e => update('confirmPassword', e.target.value)}
                placeholder="••••••••" className={inputCls} />
            </Field>
          </div>

          <button
            type="submit" disabled={loading}
            className="w-full bg-violet-700 text-white font-bold py-3 rounded-xl hover:bg-violet-800 transition disabled:opacity-60 disabled:cursor-not-allowed mt-2"
          >
            {loading ? 'جاري إنشاء الحساب...' : 'إنشاء حساب مجاني 🚀'}
          </button>

          <p className="text-center text-xs text-gray-400">
            بالتسجيل توافق على شروط الاستخدام وسياسة الخصوصية
          </p>
        </form>

        <p className="text-center text-gray-500 text-sm mt-4">
          لديك حساب بالفعل؟{' '}
          <Link href="/login" className="text-violet-700 font-semibold hover:underline">
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


# ─── Verify Email Page ────────────────────────────────────────────────────────
write_file("/opt/clickbuild/frontend/src/app/[locale]/verify/page.tsx", """\
'use client';
import { useState, FormEvent, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';

const API = process.env.NEXT_PUBLIC_API_URL ?? '/api/v1';

function VerifyContent() {
  const router       = useRouter();
  const searchParams = useSearchParams();
  const emailParam   = searchParams.get('email') ?? '';

  const [email, setEmail]   = useState(emailParam);
  const [code, setCode]     = useState('');
  const [error, setError]   = useState('');
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

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
      setTimeout(() => router.push('/login'), 2500);
    } catch {
      setError('تعذر الاتصال بالخادم');
    } finally {
      setLoading(false);
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
            أرسلنا كود مكوّن من 6 أرقام إلى بريدك الإلكتروني
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
            <input
              type="email" required value={email}
              onChange={e => setEmail(e.target.value)}
              className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-violet-500 transition"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">كود التحقق</label>
            <input
              type="text" required value={code} maxLength={6}
              onChange={e => setCode(e.target.value.replace(/\\D/g, ''))}
              placeholder="123456"
              className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-violet-500 transition text-center text-2xl tracking-widest font-mono"
            />
          </div>

          <button
            type="submit" disabled={loading || code.length < 6}
            className="w-full bg-violet-700 text-white font-bold py-3 rounded-xl hover:bg-violet-800 transition disabled:opacity-60"
          >
            {loading ? 'جاري التحقق...' : 'تأكيد'}
          </button>
        </form>

        <p className="text-center text-gray-500 text-sm mt-6">
          لم تستلم الكود؟{' '}
          <Link href="/register" className="text-violet-700 font-semibold hover:underline">
            أعد التسجيل
          </Link>
        </p>
      </div>
    </div>
  );
}

export default function VerifyPage() {
  return (
    <Suspense>
      <VerifyContent />
    </Suspense>
  );
}
""")


# ─── Create Instance Page ─────────────────────────────────────────────────────
write_file("/opt/clickbuild/frontend/src/app/[locale]/create/page.tsx", """\
'use client';
import { useState, useEffect, FormEvent } from 'react';
import { useRouter } from 'next/navigation';

const API = process.env.NEXT_PUBLIC_API_URL ?? '/api/v1';

export default function CreatePage() {
  const router = useRouter();
  const [subdomain, setSubdomain] = useState('');
  const [error, setError]         = useState('');
  const [loading, setLoading]     = useState(false);
  const [token, setToken]         = useState('');

  useEffect(() => {
    const stored = localStorage.getItem('clickbuild-auth');
    if (!stored) { router.push('/login'); return; }
    const auth = JSON.parse(stored);
    if (!auth?.state?.accessToken) { router.push('/login'); return; }
    setToken(auth.state.accessToken);
  }, []);

  function sanitize(v: string) {
    return v.toLowerCase().replace(/[^a-z0-9-]/g, '').replace(/^-+|-+$/g, '');
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    if (subdomain.length < 3) { setError('الاسم يجب أن يكون 3 أحرف على الأقل'); return; }
    setLoading(true);
    try {
      const res = await fetch(`${API}/instances/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ subdomain, odoo_version: '19', is_trial: true }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail?.ar ?? data.detail ?? 'حدث خطأ');
        return;
      }
      router.push('/dashboard');
    } catch {
      setError('تعذر الاتصال بالخادم');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-sm border w-full max-w-lg p-8">
        <div className="text-center mb-8">
          <div className="text-5xl mb-3">🚀</div>
          <h1 className="text-2xl font-black text-gray-900">إنشاء بيئة Odoo</h1>
          <p className="text-gray-500 mt-2 text-sm">14 يوم تجريبي مجاني • بدون بطاقة ائتمان</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl p-3 text-sm text-center">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              اسم النطاق الفرعي <span className="text-red-500">*</span>
            </label>
            <div className="flex items-center border border-gray-300 rounded-xl overflow-hidden focus-within:ring-2 focus-within:ring-violet-500 focus-within:border-transparent">
              <input
                type="text" required value={subdomain}
                onChange={e => setSubdomain(sanitize(e.target.value))}
                placeholder="mycompany"
                className="flex-1 px-4 py-3 focus:outline-none text-sm"
                maxLength={30} minLength={3}
              />
              <span className="bg-gray-50 px-4 py-3 text-gray-400 text-sm border-r border-gray-300 whitespace-nowrap">
                .odooclickbuild.com
              </span>
            </div>
            <p className="text-xs text-gray-400 mt-1">أحرف انجليزية صغيرة وأرقام وشرطة (-) فقط</p>
          </div>

          {subdomain && (
            <div className="bg-violet-50 rounded-xl p-4 text-sm">
              <p className="text-violet-700">✅ سيكون رابطك: <strong>{subdomain}.odooclickbuild.com</strong></p>
            </div>
          )}

          <button
            type="submit" disabled={loading || subdomain.length < 3}
            className="w-full bg-violet-700 text-white font-bold py-3 rounded-xl hover:bg-violet-800 transition disabled:opacity-60"
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <span className="animate-spin">⚙️</span> جاري الإنشاء...
              </span>
            ) : 'إنشاء البيئة التجريبية 🚀'}
          </button>
        </form>

        <div className="mt-8 grid grid-cols-3 gap-4 text-center text-sm text-gray-500">
          <div><div className="text-2xl mb-1">⚡</div><div>إنشاء فوري</div></div>
          <div><div className="text-2xl mb-1">🔒</div><div>SSL مجاني</div></div>
          <div><div className="text-2xl mb-1">🆓</div><div>14 يوم مجاناً</div></div>
        </div>
      </div>
    </div>
  );
}
""")


sftp.close()
print("\nAll pages written. Building frontend...")

# Rebuild frontend
build_cmd = (
    "cd /opt/clickbuild/frontend && "
    "NODE_OPTIONS=--max-old-space-size=1500 npm run build 2>&1 | tail -20"
)
print("Building (this takes ~2 min)...")
stdin, stdout, stderr = client.exec_command(build_cmd, timeout=300)

while not stdout.channel.exit_status_ready():
    if stdout.channel.recv_ready():
        data = stdout.channel.recv(4096).decode('utf-8', errors='replace')
        print(data, end='', flush=True)
    time.sleep(0.5)

remaining = stdout.read().decode('utf-8', errors='replace')
if remaining:
    print(remaining)

exit_code = stdout.channel.recv_exit_status()
print(f"\nBuild exit code: {exit_code}")

if exit_code == 0:
    print("Restarting PM2...")
    stdin, stdout, stderr = client.exec_command("pm2 restart clickbuild-frontend 2>&1")
    print(stdout.read().decode('utf-8', errors='replace'))
    print("Frontend restarted!")
else:
    print("Build failed. Checking full error...")
    stdin, stdout, stderr = client.exec_command(
        "cd /opt/clickbuild/frontend && NODE_OPTIONS=--max-old-space-size=1500 npm run build 2>&1 | grep -E 'error|Error|failed' | head -20"
    )
    print(stdout.read().decode('utf-8', errors='replace'))

client.close()
print("Done!")
