#!/usr/bin/env python
"""Fix Next.js 15 compatibility issues"""
import paramiko
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HOST = "129.121.98.243"
USER = "root"
PASS = "Mh@01007121878"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30)
sftp = client.open_sftp()

def write_file(remote_path, content):
    sftp.putfo(io.BytesIO(content.encode('utf-8')), remote_path)
    print(f"  [OK] {remote_path}")


# ─── layout.tsx ───────────────────────────────────────────────────────────────
write_file('/opt/clickbuild/frontend/src/app/[locale]/layout.tsx', """\
import type { Metadata } from 'next';
import { NextIntlClientProvider } from 'next-intl';
import { getMessages } from 'next-intl/server';
import { Cairo, Inter } from 'next/font/google';
import '../globals.css';

const cairo = Cairo({ subsets: ['arabic', 'latin'], variable: '--font-arabic' });
const inter  = Inter({ subsets: ['latin'], variable: '--font-latin' });

export const metadata: Metadata = {
  title: 'OdooClickBuild',
  description: 'منصة Odoo السحابية للشركات العربية',
};

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const messages   = await getMessages();
  const isRtl      = locale === 'ar';

  return (
    <html lang={locale} dir={isRtl ? 'rtl' : 'ltr'}>
      <body className={`${cairo.variable} ${inter.variable} ${isRtl ? 'font-arabic' : 'font-latin'} antialiased`}>
        <NextIntlClientProvider messages={messages}>
          {children}
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
""")


# ─── Home page ────────────────────────────────────────────────────────────────
write_file('/opt/clickbuild/frontend/src/app/[locale]/page.tsx', """\
import { useTranslations } from 'next-intl';
import Link from 'next/link';

export default function HomePage() {
  const th = useTranslations('hero');
  const tf = useTranslations('features');

  const features = [
    { key: 'accounting' as const, icon: '📊' },
    { key: 'sales'      as const, icon: '💼' },
    { key: 'inventory'  as const, icon: '📦' },
    { key: 'hr'         as const, icon: '👥' },
    { key: 'crm'        as const, icon: '🎯' },
    { key: 'pos'        as const, icon: '🛒' },
  ];

  return (
    <main className="min-h-screen bg-white">
      <section className="bg-gradient-to-br from-violet-950 via-violet-800 to-purple-700 text-white py-24">
        <div className="max-w-5xl mx-auto px-4 text-center">
          <h1 className="text-5xl md:text-7xl font-black mb-6">
            {th('title')} <span className="text-yellow-300">{th('titleHighlight')}</span>
          </h1>
          <p className="text-xl text-violet-200 max-w-2xl mx-auto mb-10">{th('subtitle')}</p>
          <Link href="/register"
            className="bg-white text-violet-900 font-bold px-8 py-4 rounded-xl text-lg hover:bg-violet-50 transition inline-block">
            {th('cta')}
          </Link>
          <p className="text-violet-300 text-sm mt-4">{th('ctaSub')}</p>
        </div>
      </section>

      <section className="py-24 bg-gray-50">
        <div className="max-w-6xl mx-auto px-4">
          <h2 className="text-4xl font-black text-center mb-16">{tf('title')}</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {features.map(({ key, icon }) => (
              <div key={key} className="bg-white rounded-2xl p-6 shadow-sm border hover:shadow-md transition">
                <div className="text-4xl mb-3">{icon}</div>
                <h3 className="text-xl font-bold mb-2">{tf(`${key}.title` as any)}</h3>
                <p className="text-gray-600">{tf(`${key}.desc` as any)}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="py-20 bg-violet-700 text-white text-center">
        <h2 className="text-4xl font-black mb-4">ابدأ الآن مجاناً</h2>
        <p className="text-violet-200 mb-8">14 يوم تجريبي مجاني • بدون بطاقة ائتمان</p>
        <Link href="/register"
          className="bg-white text-violet-900 font-bold px-10 py-4 rounded-xl text-lg hover:bg-violet-50 transition inline-block">
          إنشاء حساب مجاني
        </Link>
      </section>
    </main>
  );
}
""")


# ─── Dashboard (client component - no params issue) ───────────────────────────
write_file('/opt/clickbuild/frontend/src/app/[locale]/dashboard/page.tsx', """\
'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

interface Instance {
  id: string;
  subdomain: string;
  url: string;
  status: string;
  odoo_version: string;
  is_trial: boolean;
  expires_at: string | null;
  upgrade_available: { available: boolean; versions: string[] };
}

const STATUS_COLORS: Record<string, string> = {
  running:      'bg-green-100 text-green-800',
  stopped:      'bg-gray-100 text-gray-700',
  provisioning: 'bg-yellow-100 text-yellow-800',
  expired:      'bg-red-100 text-red-700',
  error:        'bg-red-100 text-red-800',
};

const STATUS_AR: Record<string, string> = {
  running: 'يعمل', stopped: 'متوقف', provisioning: 'جاري الإنشاء',
  expired: 'منتهي', error: 'خطأ', upgrading: 'جاري الترقية',
};

export default function DashboardPage() {
  const router   = useRouter();
  const [instances, setInstances] = useState<Instance[]>([]);
  const [loading, setLoading]     = useState(true);
  const [user, setUser]           = useState<any>(null);

  useEffect(() => {
    const stored = localStorage.getItem('clickbuild-auth');
    if (!stored) { router.push('/login'); return; }
    const auth = JSON.parse(stored);
    if (!auth?.state?.user) { router.push('/login'); return; }
    setUser(auth.state.user);
    loadInstances(auth.state.accessToken);
    const iv = setInterval(() => loadInstances(auth.state.accessToken), 15000);
    return () => clearInterval(iv);
  }, []);

  async function loadInstances(token: string) {
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/instances/`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!res.ok) { router.push('/login'); return; }
      const data = await res.json();
      setInstances(data.instances);
    } finally { setLoading(false); }
  }

  if (loading) return <div className="flex items-center justify-center h-screen text-gray-500">جاري التحميل...</div>;

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b px-6 h-16 flex items-center justify-between">
        <span className="font-black text-xl text-violet-700">OdooClickBuild</span>
        <div className="flex gap-4 items-center">
          <span className="text-gray-600">مرحباً {user?.name}</span>
          <button onClick={() => { localStorage.removeItem('clickbuild-auth'); router.push('/login'); }}
            className="text-sm text-gray-500 hover:text-gray-700">خروج</button>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-10">
        {instances.length === 0 ? (
          <div className="text-center py-24">
            <div className="text-6xl mb-6">🚀</div>
            <h2 className="text-2xl font-bold mb-4">لا توجد بيئة نشطة</h2>
            <Link href="/create"
              className="bg-violet-700 text-white px-8 py-3 rounded-xl font-bold hover:bg-violet-800 transition">
              إنشاء بيئة Odoo مجانية
            </Link>
          </div>
        ) : (
          <div className="space-y-6">
            <div className="flex justify-between items-center mb-6">
              <h1 className="text-2xl font-black">بيئاتي</h1>
              <Link href="/create" className="bg-violet-700 text-white px-4 py-2 rounded-lg text-sm font-medium">+ جديد</Link>
            </div>
            {instances.map(inst => {
              const daysLeft = inst.expires_at
                ? Math.ceil((new Date(inst.expires_at).getTime() - Date.now()) / 86400000) : null;
              return (
                <div key={inst.id} className="bg-white rounded-2xl border shadow-sm overflow-hidden">
                  <div className="p-6">
                    <div className="flex justify-between items-start">
                      <div>
                        <h3 className="text-xl font-bold">{inst.subdomain}.odooclickbuild.com</h3>
                        <p className="text-gray-500 text-sm mt-1">Odoo {inst.odoo_version}</p>
                      </div>
                      <span className={`text-xs font-medium px-3 py-1 rounded-full ${STATUS_COLORS[inst.status] || 'bg-gray-100'}`}>
                        {STATUS_AR[inst.status] || inst.status}
                      </span>
                    </div>
                    {inst.is_trial && daysLeft !== null && (
                      <div className={`mt-4 p-3 rounded-lg text-sm ${daysLeft <= 3 ? 'bg-red-50 text-red-700' : 'bg-amber-50 text-amber-700'}`}>
                        ⏰ التجربة تنتهي خلال <strong>{daysLeft} يوم</strong>
                        <Link href="/pricing" className="ms-2 underline font-medium">اشترك الآن</Link>
                      </div>
                    )}
                  </div>
                  <div className="border-t px-6 py-4 bg-gray-50 flex gap-3">
                    <a href={inst.url} target="_blank" rel="noopener noreferrer"
                      className={`flex-1 text-center bg-violet-700 text-white py-2.5 rounded-lg font-medium hover:bg-violet-800 transition ${inst.status !== 'running' ? 'opacity-50 pointer-events-none' : ''}`}>
                      🔗 فتح Odoo
                    </a>
                    <Link href={`/pricing?instance=${inst.id}`}
                      className="flex-1 text-center border border-violet-200 text-violet-700 py-2.5 rounded-lg font-medium hover:bg-violet-50 transition">
                      ⬆️ ترقية الباقة
                    </Link>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
""")

sftp.close()
client.close()
print("\nAll files fixed!")
