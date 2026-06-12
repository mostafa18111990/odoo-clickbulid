#!/usr/bin/env python
"""Update admin instance detail page with snapshots + staging UI"""
import paramiko, io, sys, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
HOST = "129.121.98.243"; USER = "root"; PASS = "Mh@01007121878"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30)
sftp = client.open_sftp()

DOMAIN = "odoo.clickbulid.com"

def upload(path, content):
    remote_dir = "/".join(path.split("/")[:-1])
    client.exec_command(f"mkdir -p '{remote_dir}'"); time.sleep(0.05)
    sftp.putfo(io.BytesIO(content.encode('utf-8')), path)
    print(f"  [OK] {path}")

def run(cmd, timeout=20):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='replace') + stderr.read().decode('utf-8', errors='replace')

# Updated instance detail page with 5 tabs: overview, logs, backups, snapshots, staging
upload('/opt/clickbuild/frontend/src/app/[locale]/admin/instances/[id]/page.tsx', f"""
'use client';
import {{ useState, useEffect, useRef }} from 'react';
import {{ useRouter, useParams }} from 'next/navigation';
import Link from 'next/link';

const API = process.env.NEXT_PUBLIC_API_URL ?? '/api/v1';
type Tab = 'overview' | 'logs' | 'backups' | 'snapshots' | 'staging';

export default function InstanceDetailPage() {{
  const router = useRouter();
  const {{ id }} = useParams<{{ id: string }}>();
  const [inst, setInst]       = useState<any>(null);
  const [stats, setStats]     = useState<any>(null);
  const [logs, setLogs]       = useState('');
  const [backups, setBackups] = useState<any[]>([]);
  const [snapshots, setSnaps] = useState<any[]>([]);
  const [token, setToken]     = useState('');
  const [tab, setTab]         = useState<Tab>('overview');
  const [loading, setLoading] = useState(true);
  const [actionMsg, setMsg]   = useState('');
  const [cloneSubdomain, setCloneSub] = useState('');
  const [backupType, setBackupType]   = useState('manual');
  const logsRef = useRef<HTMLPreElement>(null);

  useEffect(() => {{
    const stored = localStorage.getItem('clickbuild-auth');
    if (!stored) {{ router.push('/login'); return; }}
    const t = JSON.parse(stored)?.state?.accessToken;
    setToken(t);
    loadAll(t);
  }}, []);

  useEffect(() => {{
    if (logsRef.current) logsRef.current.scrollTop = logsRef.current.scrollHeight;
  }}, [logs]);

  async function loadAll(t: string) {{
    const h = {{ Authorization: `Bearer ${{t}}` }};
    const [iRes, sRes, lRes, bRes, snRes] = await Promise.all([
      fetch(`${{API}}/admin/instances?per_page=200`, {{ headers: h }}),
      fetch(`${{API}}/admin/instances/${{id}}/stats`, {{ headers: h }}),
      fetch(`${{API}}/admin/instances/${{id}}/logs?lines=100`, {{ headers: h }}),
      fetch(`${{API}}/admin/instances/${{id}}/backups?backup_type=${{backupType}}`, {{ headers: h }}),
      fetch(`${{API}}/admin/instances/${{id}}/snapshots`, {{ headers: h }}),
    ]);
    if (iRes.ok) {{
      const d = await iRes.json();
      setInst(d.instances?.find((i: any) => i.id === id) ?? null);
    }}
    if (sRes.ok) setStats(await sRes.json());
    if (lRes.ok) setLogs((await lRes.json()).logs ?? '');
    if (bRes.ok) setBackups((await bRes.json()).backups ?? []);
    if (snRes.ok) setSnaps((await snRes.json()).snapshots ?? []);
    setLoading(false);
  }}

  async function doAction(url: string, method = 'POST', body?: any) {{
    setMsg('جاري التنفيذ...');
    const opts: RequestInit = {{
      method,
      headers: {{ Authorization: `Bearer ${{token}}`, 'Content-Type': 'application/json' }},
    }};
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(url, opts);
    const data = await res.json().catch(() => ({{}}));
    setMsg(data.message || (res.ok ? '✓ تم بنجاح' : '✗ ' + (data.detail || 'خطأ')));
    setTimeout(() => {{ setMsg(''); loadAll(token); }}, 3000);
  }}

  const TABS: [Tab, string][] = [
    ['overview', 'نظرة عامة'],
    ['logs',     'سجلات'],
    ['backups',  'نسخ احتياطية'],
    ['snapshots','Snapshots'],
    ['staging',  'بيئة اختبار'],
  ];

  if (loading) return <div className="flex items-center justify-center h-screen text-gray-400">جاري التحميل...</div>;
  if (!inst)   return <div className="flex items-center justify-center h-screen text-red-500">البيئة غير موجودة</div>;

  const isRunning   = inst.status === 'running';
  const statusColor = isRunning ? 'bg-green-100 text-green-700' : 'bg-orange-100 text-orange-700';

  return (
    <div className="min-h-screen bg-gray-50" dir="rtl">
      <header className="bg-white border-b px-6 h-14 flex items-center gap-3 shadow-sm">
        <Link href="/admin/instances" className="text-gray-400 hover:text-violet-700 text-sm">← جميع البيئات</Link>
        <span className="text-gray-300">|</span>
        <span className="font-bold text-violet-700">{{inst.subdomain}}.{DOMAIN}</span>
        <span className={{`text-xs px-2 py-0.5 rounded-full font-medium ${{statusColor}}`}}>{{inst.status}}</span>
        {{actionMsg && (
          <span className="mr-auto text-sm bg-violet-50 border border-violet-200 text-violet-700 px-3 py-1 rounded-lg">
            {{actionMsg}}
          </span>
        )}}
      </header>

      <main className="max-w-5xl mx-auto px-4 py-6">
        {{/* Action bar */}}
        <div className="flex flex-wrap gap-2 mb-6">
          {{isRunning && (
            <a href={{inst.url}} target="_blank" rel="noopener"
              className="bg-violet-700 text-white px-4 py-2 rounded-xl text-sm font-semibold hover:bg-violet-800 transition">
              فتح Odoo
            </a>
          )}}
          {{isRunning ? (
            <button onClick={{() => doAction(`${{API}}/admin/instances/${{id}}/suspend`)}}
              className="bg-orange-100 text-orange-700 px-4 py-2 rounded-xl text-sm font-medium hover:bg-orange-200 transition">
              إيقاف مؤقت
            </button>
          ) : (
            <button onClick={{() => doAction(`${{API}}/admin/instances/${{id}}/resume`)}}
              className="bg-green-100 text-green-700 px-4 py-2 rounded-xl text-sm font-medium hover:bg-green-200 transition">
              تشغيل
            </button>
          )}}
          <button onClick={{() => doAction(`${{API}}/admin/instances/${{id}}/backup`)}}
            className="bg-blue-100 text-blue-700 px-4 py-2 rounded-xl text-sm font-medium hover:bg-blue-200 transition">
            نسخ احتياطي
          </button>
          <button onClick={{() => doAction(`${{API}}/admin/instances/${{id}}/snapshot`)}}
            className="bg-purple-100 text-purple-700 px-4 py-2 rounded-xl text-sm font-medium hover:bg-purple-200 transition">
            📸 Snapshot
          </button>
          <button
            onClick={{() => {{
              if (confirm('حذف البيئة نهائياً؟')) {{
                doAction(`${{API}}/admin/instances/${{id}}`, 'DELETE').then(() => router.push('/admin/instances'));
              }}
            }}}}
            className="bg-red-100 text-red-700 px-4 py-2 rounded-xl text-sm font-medium hover:bg-red-200 transition">
            حذف
          </button>
        </div>

        {{/* Tabs */}}
        <div className="flex gap-1 mb-6 bg-white border rounded-xl p-1 w-fit overflow-x-auto">
          {{TABS.map(([t, label]) => (
            <button key={{t}} onClick={{() => setTab(t)}}
              className={{`px-4 py-1.5 rounded-lg text-sm font-medium whitespace-nowrap transition ${{
                tab === t ? 'bg-violet-700 text-white' : 'text-gray-600 hover:bg-gray-100'
              }}`}}>
              {{label}}
            </button>
          ))}}
        </div>

        {{/* Overview */}}
        {{tab === 'overview' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white rounded-2xl border p-5 shadow-sm">
              <h3 className="font-bold mb-4">معلومات البيئة</h3>
              <dl className="space-y-2 text-sm">
                {{([
                  ['النطاق', `${{inst.subdomain}}.{DOMAIN}`],
                  ['الإصدار', `Odoo ${{inst.odoo_version}}`],
                  ['المنفذ', inst.port || '—'],
                  ['قاعدة البيانات', inst.db_name || '—'],
                  ['تجريبي', inst.is_trial ? 'نعم' : 'لا'],
                  ['تاريخ الإنشاء', inst.created_at ? new Date(inst.created_at).toLocaleDateString('ar-EG') : '—'],
                  ['تاريخ الانتهاء', inst.expires_at ? new Date(inst.expires_at).toLocaleDateString('ar-EG') : 'لا ينتهي'],
                  ['المستخدم', inst.user?.email],
                  ['الشركة', inst.user?.company || '—'],
                ] as [string,any][]).map(([k, v]) => (
                  <div key={{k}} className="flex justify-between border-b border-gray-100 pb-1">
                    <dt className="text-gray-500">{{k}}</dt>
                    <dd className="font-medium text-gray-800">{{String(v)}}</dd>
                  </div>
                ))}}
              </dl>
              {{inst.error_msg && (
                <div className="mt-4 bg-red-50 border border-red-200 rounded-lg p-3 text-xs text-red-700 font-mono">
                  {{inst.error_msg}}
                </div>
              )}}
            </div>

            {{stats && (
              <div className="bg-white rounded-2xl border p-5 shadow-sm">
                <h3 className="font-bold mb-4">موارد الحاوية</h3>
                {{([
                  ['الحالة', stats.status],
                  ['CPU', `${{stats.cpu_pct}}%`],
                  ['RAM', `${{stats.mem_used_mb}} / ${{stats.mem_limit_mb}} MB (${{stats.mem_pct}}%)`],
                  ['شبكة داخل', `${{stats.net_in_mb}} MB`],
                  ['شبكة خارج', `${{stats.net_out_mb}} MB`],
                ] as [string,any][]).map(([k, v]) => (
                  <div key={{k}} className="flex justify-between text-sm py-2 border-b border-gray-100 last:border-0">
                    <span className="text-gray-500">{{k}}</span>
                    <span className="font-medium">{{String(v)}}</span>
                  </div>
                ))}}
              </div>
            )}}
          </div>
        )}}

        {{/* Logs */}}
        {{tab === 'logs' && (
          <div>
            <div className="flex justify-between items-center mb-3">
              <span className="text-sm text-gray-500">آخر 100 سطر</span>
              <button onClick={{() => loadAll(token)}}
                className="text-xs bg-gray-100 hover:bg-gray-200 px-3 py-1 rounded-lg">
                تحديث
              </button>
            </div>
            <div className="bg-gray-900 rounded-2xl p-4 overflow-auto max-h-[600px]">
              <pre ref={{logsRef}} className="text-green-400 text-xs font-mono whitespace-pre-wrap">
                {{logs || 'لا توجد سجلات'}}
              </pre>
            </div>
          </div>
        )}}

        {{/* Backups */}}
        {{tab === 'backups' && (
          <div>
            <div className="flex gap-2 mb-4">
              {{(['manual','hourly','daily','weekly','monthly'] as const).map(t => (
                <button key={{t}} onClick={{() => {{ setBackupType(t); loadAll(token); }}}}
                  className={{`text-xs px-3 py-1.5 rounded-lg ${{
                    backupType === t ? 'bg-violet-700 text-white' : 'bg-white border hover:bg-gray-50'
                  }}`}}>
                  {{t === 'manual' ? 'يدوي' : t === 'hourly' ? 'ساعي' : t === 'daily' ? 'يومي' : t === 'weekly' ? 'أسبوعي' : 'شهري'}}
                </button>
              ))}}
            </div>
            <div className="bg-white rounded-2xl border shadow-sm overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-gray-50">
                  <tr>{{['اسم الملف','الحجم','التاريخ'].map(h => (
                    <th key={{h}} className="text-right px-4 py-3 font-semibold text-gray-600">{{h}}</th>
                  ))}}</tr>
                </thead>
                <tbody className="divide-y">
                  {{backups.map(b => (
                    <tr key={{b.name}} className="hover:bg-gray-50">
                      <td className="px-4 py-3 font-mono text-xs">{{b.name}}</td>
                      <td className="px-4 py-3">{{b.size_mb}} MB</td>
                      <td className="px-4 py-3 text-gray-500">
                        {{new Date(b.created_at).toLocaleString('ar-EG')}}
                      </td>
                    </tr>
                  ))}}
                </tbody>
              </table>
              {{backups.length === 0 && <div className="text-center py-8 text-gray-400">لا توجد نسخ ({{backupType}})</div>}}
            </div>
          </div>
        )}}

        {{/* Snapshots */}}
        {{tab === 'snapshots' && (
          <div>
            <div className="mb-4 bg-blue-50 border border-blue-200 rounded-xl p-4 text-sm text-blue-700">
              <strong>Snapshot</strong> = نسخة كاملة من قاعدة البيانات + حاوية Docker في لحظة معينة.
              يمكن الرجوع إليها بضغطة واحدة.
            </div>
            <div className="bg-white rounded-2xl border shadow-sm overflow-hidden">
              <div className="px-4 py-3 border-b flex justify-between items-center">
                <span className="font-semibold">Snapshots المتاحة</span>
                <button onClick={{() => doAction(`${{API}}/admin/instances/${{id}}/snapshot`)}}
                  className="text-sm bg-purple-100 text-purple-700 hover:bg-purple-200 px-3 py-1.5 rounded-lg">
                  📸 Snapshot جديد
                </button>
              </div>
              <table className="w-full text-sm">
                <thead className="bg-gray-50">
                  <tr>{{['الاسم','الحجم','التاريخ','استرجاع'].map(h => (
                    <th key={{h}} className="text-right px-4 py-3 font-semibold text-gray-600">{{h}}</th>
                  ))}}</tr>
                </thead>
                <tbody className="divide-y">
                  {{snapshots.map(s => (
                    <tr key={{s.name}} className="hover:bg-gray-50">
                      <td className="px-4 py-3 font-mono text-xs">{{s.name}}</td>
                      <td className="px-4 py-3">{{s.size_mb}} MB</td>
                      <td className="px-4 py-3 text-gray-500">
                        {{new Date(s.created_at).toLocaleString('ar-EG')}}
                      </td>
                      <td className="px-4 py-3">
                        <button
                          onClick={{() => {{
                            if (confirm(`استرجاع Snapshot "${{s.name}}"؟ سيتم إيقاف البيئة مؤقتاً.`)) {{
                              doAction(`${{API}}/admin/instances/${{id}}/snapshots/${{s.name}}/restore`);
                            }}
                          }}}}
                          className="text-xs bg-orange-100 text-orange-700 hover:bg-orange-200 px-2 py-1 rounded-lg">
                          Restore
                        </button>
                      </td>
                    </tr>
                  ))}}
                </tbody>
              </table>
              {{snapshots.length === 0 && <div className="text-center py-8 text-gray-400">لا توجد snapshots بعد</div>}}
            </div>
          </div>
        )}}

        {{/* Staging */}}
        {{tab === 'staging' && (
          <div>
            <div className="mb-4 bg-green-50 border border-green-200 rounded-xl p-4 text-sm text-green-700">
              <strong>بيئة الاختبار (Staging)</strong> = نسخة مطابقة من البيئة للتجربة قبل التطبيق على Production.
            </div>
            <div className="bg-white rounded-2xl border p-6 shadow-sm">
              <h3 className="font-bold mb-4">إنشاء نسخة اختبار</h3>
              <div className="flex gap-3">
                <input
                  type="text"
                  placeholder={{`staging-${{inst.subdomain}}`}}
                  value={{cloneSubdomain}}
                  onChange={{e => setCloneSub(e.target.value)}}
                  className="flex-1 border border-gray-200 rounded-xl px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-400"
                />
                <button
                  onClick={{() => {{
                    const sub = cloneSubdomain || `staging-${{inst.subdomain}}`;
                    doAction(`${{API}}/admin/instances/${{id}}/clone`, 'POST', {{ subdomain: sub }});
                  }}}}
                  className="bg-green-600 text-white px-5 py-2 rounded-xl text-sm font-medium hover:bg-green-700 transition">
                  إنشاء Staging
                </button>
              </div>
              <p className="text-xs text-gray-400 mt-2">
                سيتم إنشاء بيئة جديدة بنفس بيانات هذه البيئة على Subdomain مختلف.
              </p>
            </div>
          </div>
        )}}
      </main>
    </div>
  );
}}
""")

print("Building frontend...")
sftp.close()

build_cmd = "cd /opt/clickbuild/frontend && NODE_OPTIONS=--max-old-space-size=1500 npm run build 2>&1 | tail -15"
stdin, stdout, stderr = client.exec_command(build_cmd, timeout=300)
while not stdout.channel.exit_status_ready():
    if stdout.channel.recv_ready():
        data = stdout.channel.recv(4096).decode('utf-8', errors='replace')
        print(data, end='', flush=True)
    time.sleep(0.5)
remaining = stdout.read().decode('utf-8', errors='replace')
if remaining: print(remaining)
b_code = stdout.channel.recv_exit_status()
print(f"Build: {b_code}")
if b_code == 0:
    stdin, stdout, stderr = client.exec_command("pm2 restart clickbuild-frontend 2>&1 | grep online | head -2")
    print(stdout.read().decode())

client.close()
print("Admin UI v2 deployed!")
