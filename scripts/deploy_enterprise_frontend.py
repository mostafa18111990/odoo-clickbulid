#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Enterprise Frontend Pages Deployment."""
import paramiko, time, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HOST = "129.121.98.243"
USER = "root"
PASS = "Mh@01007121878"

def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=30)
    return c

def run(client, cmd, timeout=180):
    print(f"\n$ {cmd[:100]}")
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if out: print(out[:2000])
    if err and 'warn' not in err.lower() and not out: print(f"[err] {err[:300]}")
    return out, err

def upload(client, path, content):
    sftp = client.open_sftp()
    # ensure dir exists
    import os
    d = os.path.dirname(path)
    try:
        sftp.stat(d)
    except FileNotFoundError:
        sftp.mkdir(d)
    with sftp.open(path, 'w') as f:
        f.write(content)
    sftp.close()
    print(f"  -> {path}")

def section(t):
    print(f"\n{'='*60}\n  {t}\n{'='*60}")

FE = '/opt/clickbuild/frontend/src/app/[locale]'

# ─── SRE DASHBOARD PAGE ───────────────────────────────────────────────────────
SRE_PAGE = """\
'use client';
import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';

export default function SREDashboard() {
  const { locale } = useParams() as { locale: string };
  const isAr = locale === 'ar';
  const [slos, setSlos] = useState([]);
  const [incidents, setIncidents] = useState([]);
  const [tenants, setTenants] = useState([]);
  const [loading, setLoading] = useState(true);

  const L = {
    title: isAr ? 'لوحة موثوقية المنصة (SRE)' : 'Platform Reliability Dashboard',
    slos: isAr ? 'اهداف مستوى الخدمة SLOs' : 'Service Level Objectives',
    incidents: isAr ? 'الحوادث النشطة' : 'Active Incidents',
    tenants: isAr ? 'صحة التطبيقات' : 'Tenant Health',
    noInc: isAr ? 'لا توجد حوادث نشطة' : 'No active incidents',
    budget: isAr ? 'ميزانية الاخطاء' : 'Error Budget',
  };

  const sev: Record<string,string> = { SEV1:'bg-red-600', SEV2:'bg-orange-500', SEV3:'bg-yellow-500', SEV4:'bg-blue-500' };
  const budgetColor = (v: number) => v > 0.5 ? 'text-green-400' : v > 0.2 ? 'text-yellow-400' : 'text-red-400';
  const healthColor = (s: number) => s >= 80 ? 'border-green-700 bg-green-950' : s >= 50 ? 'border-yellow-700 bg-yellow-950' : 'border-red-700 bg-red-950';

  useEffect(() => {
    const t = localStorage.getItem('access_token');
    const h = { Authorization: `Bearer ${t}` };
    Promise.all([
      fetch('/api/v1/sre/slos', {headers:h}).then(r=>r.json()),
      fetch('/api/v1/sre/incidents?status=OPEN', {headers:h}).then(r=>r.json()),
      fetch('/api/v1/sre/health/tenants', {headers:h}).then(r=>r.json()),
    ]).then(([a,b,c]) => {
      setSlos(a.slos||[]); setIncidents(b.incidents||[]); setTenants(c.tenants||[]);
      setLoading(false);
    }).catch(()=>setLoading(false));
  }, []);

  if (loading) return <div className="min-h-screen bg-gray-950 flex items-center justify-center text-white text-xl">Loading SRE data...</div>;

  const counts = { ok: slos.filter((s:any)=>s.status==='OK').length, warn: slos.filter((s:any)=>s.status==='WARNING').length, breach: slos.filter((s:any)=>s.status==='BREACH').length };

  return (
    <div className={`min-h-screen bg-gray-950 text-white p-6 ${isAr?'rtl':'ltr'}`} dir={isAr?'rtl':'ltr'}>
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold mb-1">{L.title}</h1>
          <p className="text-gray-400 text-sm">{new Date().toLocaleString(isAr?'ar-SA':'en-US')}</p>
        </div>

        {/* SLO Summary Cards */}
        <div className="grid grid-cols-4 gap-4 mb-8">
          {[
            { label: isAr?'اجمالي':'Total SLOs', val: slos.length, cls:'bg-blue-950 border-blue-700' },
            { label: isAr?'طبيعي':'Healthy',     val: counts.ok,   cls:'bg-green-950 border-green-700' },
            { label: isAr?'تحذير':'Warning',      val: counts.warn, cls:'bg-yellow-950 border-yellow-700' },
            { label: isAr?'انتهاك':'Breached',    val: counts.breach,cls:'bg-red-950 border-red-700' },
          ].map(c=>(
            <div key={c.label} className={`${c.cls} border rounded-xl p-5`}>
              <div className="text-4xl font-bold">{c.val}</div>
              <div className="text-sm text-gray-300 mt-2">{c.label}</div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-6 mb-8">
          {/* SLOs */}
          <div className="bg-gray-900 border border-gray-700 rounded-xl p-5">
            <h2 className="text-lg font-semibold mb-4">{L.slos}</h2>
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {slos.map((s:any) => (
                <div key={`${s.service_name}-${s.slo_name}`} className="flex justify-between items-center p-3 bg-gray-800 rounded-lg">
                  <div>
                    <div className="text-sm font-medium">{s.slo_name}</div>
                    <div className="text-xs text-gray-400">{s.service_name} · target {s.target_pct}%</div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-bold">
                      {s.availability ? `${(s.availability*100).toFixed(2)}%` : 'N/A'}
                    </div>
                    <div className={`text-xs ${budgetColor(s.error_budget_remaining||0)}`}>
                      {L.budget}: {s.error_budget_remaining ? `${(s.error_budget_remaining*100).toFixed(0)}%` : 'N/A'}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Incidents */}
          <div className="bg-gray-900 border border-gray-700 rounded-xl p-5">
            <h2 className="text-lg font-semibold mb-4">{L.incidents}</h2>
            {incidents.length === 0 ? (
              <div className="text-center py-10 text-green-400">
                <div className="text-5xl mb-3">✓</div>
                <div className="font-medium">{L.noInc}</div>
              </div>
            ) : (
              <div className="space-y-2 max-h-80 overflow-y-auto">
                {incidents.map((i:any) => (
                  <div key={i.incident_id} className="p-3 bg-gray-800 rounded-lg border border-gray-600">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-xs px-2 py-0.5 rounded font-bold text-white ${sev[i.severity]||'bg-gray-600'}`}>{i.severity}</span>
                      <span className="text-xs text-gray-400">{i.incident_id}</span>
                    </div>
                    <div className="text-sm font-medium">{i.title}</div>
                    <div className="text-xs text-gray-400 mt-1">{new Date(i.detected_at).toLocaleString(isAr?'ar-SA':'en-US')}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Tenant Health */}
        <div className="bg-gray-900 border border-gray-700 rounded-xl p-5">
          <h2 className="text-lg font-semibold mb-4">{L.tenants}</h2>
          {tenants.length === 0 ? (
            <div className="text-gray-400 text-center py-6">
              {isAr ? 'لا توجد بيانات — سيتم قياس الصحة كل 5 دقائق' : 'No data yet - health checks run every 5 minutes'}
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-3">
              {tenants.map((t:any) => (
                <div key={t.subdomain} className={`p-4 rounded-xl border-2 ${healthColor(t.overall_score||0)}`}>
                  <div className="font-semibold text-lg">{t.subdomain}</div>
                  <div className="text-3xl font-bold mt-1">{(t.overall_score||0).toFixed(0)}%</div>
                  <div className="text-xs text-gray-400 mt-1">{t.container_status} · {t.http_response_ms}ms</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
"""

# ─── COMPLIANCE PAGE ──────────────────────────────────────────────────────────
COMPLIANCE_PAGE = """\
'use client';
import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';

export default function ComplianceDashboard() {
  const { locale } = useParams() as { locale: string };
  const isAr = locale === 'ar';
  const [data, setData] = useState<any>(null);
  const [controls, setControls] = useState<any[]>([]);
  const [selectedFw, setSelectedFw] = useState<string|null>(null);
  const [loading, setLoading] = useState(true);

  const L = {
    title: isAr ? 'لوحة الامتثال والحوكمة' : 'Compliance & Governance',
    frameworks: isAr ? 'الاطر والمعايير' : 'Frameworks',
    controls: isAr ? 'الضوابط التفصيلية' : 'Control Details',
    riskEvents: isAr ? 'احداث عالية المخاطر (24h)' : 'High-Risk Events (24h)',
    auto: isAr ? 'آلي' : 'Automated',
  };

  const statusBadge: Record<string,string> = {
    PASS: 'bg-green-900 text-green-300', FAIL: 'bg-red-900 text-red-300',
    PARTIAL: 'bg-yellow-900 text-yellow-300', PENDING: 'bg-gray-700 text-gray-300', NA: 'bg-gray-800 text-gray-500',
  };

  useEffect(() => {
    const t = localStorage.getItem('access_token');
    const h = { Authorization: `Bearer ${t}` };
    Promise.all([
      fetch('/api/v1/compliance/dashboard', {headers:h}).then(r=>r.json()),
      fetch('/api/v1/compliance/controls', {headers:h}).then(r=>r.json()),
    ]).then(([d,c]) => { setData(d); setControls(c.controls||[]); setLoading(false); })
     .catch(()=>setLoading(false));
  }, []);

  if (loading) return <div className="min-h-screen bg-gray-950 flex items-center justify-center text-white">Loading...</div>;

  const filtered = selectedFw ? controls.filter((c:any)=>c.framework===selectedFw) : controls;

  return (
    <div className={`min-h-screen bg-gray-950 text-white p-6 ${isAr?'rtl':'ltr'}`} dir={isAr?'rtl':'ltr'}>
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-3xl font-bold">{L.title}</h1>
          <div className="bg-red-950 border border-red-700 rounded-xl px-5 py-3 text-center">
            <div className="text-3xl font-bold">{data?.high_risk_events_24h??0}</div>
            <div className="text-xs text-red-300 mt-1">{L.riskEvents}</div>
          </div>
        </div>

        {/* Framework Cards */}
        <div className="grid grid-cols-4 gap-4 mb-8">
          {(data?.frameworks||[]).map((fw:any) => {
            const pct = fw.pass_pct||0;
            const border = pct>=80?'border-green-600':pct>=50?'border-yellow-600':'border-red-600';
            return (
              <button key={fw.framework} onClick={()=>setSelectedFw(selectedFw===fw.framework?null:fw.framework)}
                className={`bg-gray-900 border-2 ${border} rounded-xl p-5 text-left hover:bg-gray-800 transition ${selectedFw===fw.framework?'ring-2 ring-white':''}`}>
                <div className="text-xl font-bold mb-2">{fw.framework}</div>
                <div className="text-4xl font-bold mb-3">{pct}%</div>
                <div className="grid grid-cols-2 gap-1 text-sm">
                  <div className="text-green-400 font-medium">✓ {fw.passing}</div>
                  <div className="text-red-400 font-medium">✗ {fw.failing}</div>
                  <div className="text-yellow-400">~ {fw.partial}</div>
                  <div className="text-gray-400">? {fw.pending}</div>
                </div>
              </button>
            );
          })}
        </div>

        {/* Controls Table */}
        <div className="bg-gray-900 border border-gray-700 rounded-xl p-5">
          <h2 className="text-lg font-semibold mb-4">
            {L.controls} {selectedFw ? `— ${selectedFw}` : `(${filtered.length})`}
          </h2>
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {filtered.map((c:any) => (
              <div key={`${c.framework}-${c.control_id}`}
                   className="flex items-center justify-between p-3 bg-gray-800 rounded-lg">
                <div className="flex items-center gap-3">
                  <div>
                    <div className="text-sm font-medium">{c.control_name}</div>
                    <div className="text-xs text-gray-400">{c.framework} · {c.control_id} · {c.owner}</div>
                  </div>
                  {c.automated && <span className="text-xs bg-blue-900 text-blue-300 px-2 py-0.5 rounded">{L.auto}</span>}
                </div>
                <span className={`text-xs px-3 py-1 rounded-full font-semibold ${statusBadge[c.status]||'bg-gray-700 text-gray-300'}`}>
                  {c.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
"""

# ─── SUPPORT PAGE ─────────────────────────────────────────────────────────────
SUPPORT_PAGE = """\
'use client';
import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';

export default function SupportPortal() {
  const { locale } = useParams() as { locale: string };
  const isAr = locale === 'ar';
  const [tickets, setTickets] = useState<any[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ subject:'', description:'', category:'technical', priority:'MEDIUM' });
  const [submitting, setSubmitting] = useState(false);
  const [msg, setMsg] = useState('');

  const L = {
    title:       isAr ? 'مركز الدعم' : 'Support Center',
    newTicket:   isAr ? 'تذكرة جديدة' : 'New Ticket',
    subject:     isAr ? 'الموضوع' : 'Subject',
    desc:        isAr ? 'الوصف' : 'Description',
    category:    isAr ? 'الفئة' : 'Category',
    priority:    isAr ? 'الاولوية' : 'Priority',
    submit:      isAr ? 'ارسال' : 'Submit',
    cancel:      isAr ? 'الغاء' : 'Cancel',
    myTickets:   isAr ? 'تذاكري' : 'My Tickets',
    slaBreached: isAr ? 'تجاوز SLA' : 'SLA Breached',
    noTickets:   isAr ? 'لا توجد تذاكر بعد' : 'No tickets yet',
    tier:        isAr ? 'المستوى' : 'Tier',
  };

  const priorityColors: Record<string,string> = {
    CRITICAL:'bg-red-900 text-red-200', HIGH:'bg-orange-900 text-orange-200',
    MEDIUM:'bg-yellow-900 text-yellow-200', LOW:'bg-gray-700 text-gray-300',
  };

  const fetchTickets = () => {
    const t = localStorage.getItem('access_token');
    fetch('/api/v1/support/tickets', {headers:{Authorization:`Bearer ${t}`}})
      .then(r=>r.json()).then(d=>setTickets(d.tickets||[]));
  };

  useEffect(()=>{ fetchTickets(); }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault(); setSubmitting(true);
    const t = localStorage.getItem('access_token');
    const res = await fetch('/api/v1/support/tickets', {
      method:'POST', headers:{'Content-Type':'application/json', Authorization:`Bearer ${t}`},
      body: JSON.stringify(form),
    });
    const d = await res.json();
    if (res.ok) {
      setMsg(isAr ? `تم فتح تذكرة: ${d.ticket_id} | المستوى: ${d.tier}` : `Ticket opened: ${d.ticket_id} | Tier: ${d.tier}`);
      setShowForm(false); fetchTickets();
    }
    setSubmitting(false);
  };

  return (
    <div className={`min-h-screen bg-gray-950 text-white p-6 ${isAr?'rtl':'ltr'}`} dir={isAr?'rtl':'ltr'}>
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-3xl font-bold">{L.title}</h1>
          <button onClick={()=>setShowForm(!showForm)}
            className="bg-blue-600 hover:bg-blue-700 px-5 py-2.5 rounded-xl font-semibold transition">
            {L.newTicket}
          </button>
        </div>

        {msg && <div className="bg-green-900 border border-green-700 rounded-xl p-4 mb-4 text-green-300 font-medium">{msg}</div>}

        {showForm && (
          <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 mb-6">
            <h2 className="text-xl font-semibold mb-4">{L.newTicket}</h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">{L.subject}</label>
                <input value={form.subject} onChange={e=>setForm({...form,subject:e.target.value})}
                  className="w-full bg-gray-800 border border-gray-600 rounded-lg px-4 py-2.5 text-white focus:border-blue-500 outline-none" required />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">{L.desc}</label>
                <textarea value={form.description} onChange={e=>setForm({...form,description:e.target.value})}
                  rows={4} className="w-full bg-gray-800 border border-gray-600 rounded-lg px-4 py-2.5 text-white focus:border-blue-500 outline-none resize-none" required />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">{L.category}</label>
                  <select value={form.category} onChange={e=>setForm({...form,category:e.target.value})}
                    className="w-full bg-gray-800 border border-gray-600 rounded-lg px-4 py-2.5 text-white">
                    {['technical','billing','security','compliance','integration','performance','general'].map(c=><option key={c}>{c}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">{L.priority}</label>
                  <select value={form.priority} onChange={e=>setForm({...form,priority:e.target.value})}
                    className="w-full bg-gray-800 border border-gray-600 rounded-lg px-4 py-2.5 text-white">
                    {['CRITICAL','HIGH','MEDIUM','LOW'].map(p=><option key={p}>{p}</option>)}
                  </select>
                </div>
              </div>
              <div className="flex gap-3">
                <button type="submit" disabled={submitting}
                  className="bg-blue-600 hover:bg-blue-700 px-6 py-2.5 rounded-xl font-semibold disabled:opacity-50 transition">
                  {submitting ? '...' : L.submit}
                </button>
                <button type="button" onClick={()=>setShowForm(false)}
                  className="bg-gray-700 hover:bg-gray-600 px-6 py-2.5 rounded-xl transition">
                  {L.cancel}
                </button>
              </div>
            </form>
          </div>
        )}

        <div className="bg-gray-900 border border-gray-700 rounded-xl p-5">
          <h2 className="text-lg font-semibold mb-4">{L.myTickets} ({tickets.length})</h2>
          {tickets.length === 0 ? (
            <div className="text-center py-10 text-gray-500">
              <div className="text-4xl mb-3">🎫</div>
              <div>{L.noTickets}</div>
            </div>
          ) : (
            <div className="space-y-3">
              {tickets.map((tk:any) => (
                <div key={tk.ticket_id}
                     className={`p-4 rounded-xl border ${tk.sla_breached ? 'border-red-700 bg-red-950/50' : 'border-gray-700 bg-gray-800'}`}>
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center flex-wrap gap-2 mb-1.5">
                        <span className="text-sm font-mono text-gray-400">{tk.ticket_id}</span>
                        <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${priorityColors[tk.priority]||'bg-gray-700 text-gray-300'}`}>{tk.priority}</span>
                        <span className="text-xs bg-indigo-900 text-indigo-300 px-2 py-0.5 rounded-full">{L.tier}: {tk.tier}</span>
                        {tk.sla_breached && <span className="text-xs bg-red-700 text-red-200 px-2 py-0.5 rounded-full font-bold">SLA {L.slaBreached}</span>}
                      </div>
                      <div className="font-semibold">{tk.subject}</div>
                      <div className="text-xs text-gray-500 mt-1">{tk.category}</div>
                    </div>
                    <div className="text-right ms-4">
                      <div className="text-sm font-semibold">{tk.status}</div>
                      <div className="text-xs text-gray-500">{new Date(tk.created_at).toLocaleDateString(isAr?'ar-SA':'en-US')}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
"""

# ─── ADMIN OPERATIONS CENTER ──────────────────────────────────────────────────
ADMIN_OPS_PAGE = """\
'use client';
import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';

export default function AdminOpsCenter() {
  const { locale } = useParams() as { locale: string };
  const router = useRouter();
  const isAr = locale === 'ar';
  const [stats, setStats] = useState<any>({});
  const [loading, setLoading] = useState(true);

  const modules = [
    { key:'sre',        icon:'📡', titleAr:'موثوقية المنصة',   titleEn:'SRE Dashboard',       href:`/${locale}/admin/sre`,        color:'bg-blue-900/40 border-blue-700', desc: isAr?'SLOs · حوادث · صحة Tenants':'SLOs · Incidents · Tenant Health' },
    { key:'compliance', icon:'🛡️', titleAr:'الامتثال والحوكمة',titleEn:'Compliance',           href:`/${locale}/admin/compliance`,  color:'bg-green-900/40 border-green-700', desc: isAr?'SOC2 · GDPR · PDPL · ISO27001':'SOC2 · GDPR · PDPL · ISO27001' },
    { key:'support',    icon:'🎫', titleAr:'تذاكر الدعم',       titleEn:'Support Queue',        href:`/${locale}/admin/support-queue`,color:'bg-purple-900/40 border-purple-700', desc: isAr?'L1 · L2 · L3 · SLA Monitoring':'L1 · L2 · L3 · SLA Monitoring' },
    { key:'instances',  icon:'🖥️', titleAr:'ادارة الانظمة',    titleEn:'Instance Management',  href:`/${locale}/admin`,            color:'bg-orange-900/40 border-orange-700', desc: isAr?'Odoo Tenants · Provisioning':'Odoo Tenants · Provisioning' },
  ];

  useEffect(() => {
    const t = localStorage.getItem('access_token');
    if (!t) { router.push(`/${locale}/login`); return; }
    // Quick stats
    Promise.all([
      fetch('/api/v1/sre/incidents?status=OPEN', {headers:{Authorization:`Bearer ${t}`}}).then(r=>r.json()),
      fetch('/api/v1/support/admin/tickets?status=OPEN', {headers:{Authorization:`Bearer ${t}`}}).then(r=>r.json()),
    ]).then(([inc, tkt]) => {
      setStats({ openIncidents: inc.incidents?.length||0, openTickets: tkt.tickets?.length||0 });
      setLoading(false);
    }).catch(()=>setLoading(false));
  }, [locale]);

  return (
    <div className={`min-h-screen bg-gray-950 text-white p-6 ${isAr?'rtl':'ltr'}`} dir={isAr?'rtl':'ltr'}>
      <div className="max-w-6xl mx-auto">
        <div className="mb-10">
          <h1 className="text-4xl font-bold mb-2">
            {isAr ? 'مركز العمليات' : 'Operations Center'}
          </h1>
          <p className="text-gray-400">{isAr ? 'ClickBuild SaaS — لوحة الادارة المؤسسية' : 'ClickBuild SaaS — Enterprise Admin Dashboard'}</p>
        </div>

        {/* Alert bar */}
        {!loading && (stats.openIncidents > 0 || stats.openTickets > 0) && (
          <div className="bg-red-950 border border-red-700 rounded-xl p-4 mb-8 flex items-center gap-4">
            <span className="text-2xl">🚨</span>
            <div>
              {stats.openIncidents > 0 && <span className="text-red-300 font-semibold me-4">{stats.openIncidents} {isAr?'حادثة نشطة':'active incidents'}</span>}
              {stats.openTickets > 0 && <span className="text-orange-300 font-semibold">{stats.openTickets} {isAr?'تذكرة مفتوحة':'open tickets'}</span>}
            </div>
          </div>
        )}

        {/* Module Grid */}
        <div className="grid grid-cols-2 gap-6">
          {modules.map(m => (
            <Link key={m.key} href={m.href}
              className={`${m.color} border-2 rounded-2xl p-6 hover:scale-[1.02] transition-transform block`}>
              <div className="text-4xl mb-4">{m.icon}</div>
              <h2 className="text-xl font-bold mb-1">{isAr ? m.titleAr : m.titleEn}</h2>
              <p className="text-sm text-gray-400">{m.desc}</p>
            </Link>
          ))}
        </div>

        {/* Platform Philosophy Tags */}
        <div className="mt-10 flex flex-wrap gap-2">
          {['API-First','AI-Native','Cloud-Native','Security-First','Event-Driven',
            'Tenant-Aware','Compliance-by-Design','Enterprise-Ready'].map(tag => (
            <span key={tag} className="text-xs bg-gray-800 border border-gray-700 text-gray-300 px-3 py-1 rounded-full">
              {tag}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
"""

# ─── SUPPORT ADMIN QUEUE ──────────────────────────────────────────────────────
SUPPORT_ADMIN_PAGE = """\
'use client';
import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';

export default function SupportQueue() {
  const { locale } = useParams() as { locale: string };
  const isAr = locale === 'ar';
  const [tickets, setTickets] = useState<any[]>([]);
  const [filter, setFilter] = useState({ status:'', priority:'', tier:'' });
  const [loading, setLoading] = useState(true);

  const L = {
    title: isAr ? 'قائمة انتظار الدعم' : 'Support Queue',
    all: isAr ? 'الكل' : 'All',
    slaBreached: isAr ? 'تجاوز SLA' : 'SLA Breached',
    assign: isAr ? 'تعيين' : 'Assign',
  };
  const priorityColors: Record<string,string> = {
    CRITICAL:'bg-red-900/60 text-red-200 border-red-700',
    HIGH:'bg-orange-900/60 text-orange-200 border-orange-700',
    MEDIUM:'bg-yellow-900/60 text-yellow-200 border-yellow-700',
    LOW:'bg-gray-800 text-gray-300 border-gray-700',
  };
  const tierColors: Record<string,string> = {
    L1:'bg-blue-900 text-blue-300', L2:'bg-purple-900 text-purple-300', L3:'bg-red-900 text-red-300',
  };

  const fetchTickets = () => {
    const t = localStorage.getItem('access_token');
    const params = new URLSearchParams();
    if (filter.status) params.set('status', filter.status);
    if (filter.priority) params.set('priority', filter.priority);
    if (filter.tier) params.set('tier', filter.tier);
    fetch(`/api/v1/support/admin/tickets?${params}`, {headers:{Authorization:`Bearer ${t}`}})
      .then(r=>r.json()).then(d=>{ setTickets(d.tickets||[]); setLoading(false); })
      .catch(()=>setLoading(false));
  };

  useEffect(()=>{ fetchTickets(); }, [filter]);

  const breachedCount = tickets.filter((t:any)=>t.sla_breached||t.sla_status).length;

  return (
    <div className={`min-h-screen bg-gray-950 text-white p-6 ${isAr?'rtl':'ltr'}`} dir={isAr?'rtl':'ltr'}>
      <div className="max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-3xl font-bold">{L.title}</h1>
          <div className="flex items-center gap-4">
            {breachedCount > 0 && (
              <div className="bg-red-950 border border-red-700 rounded-xl px-4 py-2 text-red-300 font-semibold">
                {breachedCount} {L.slaBreached}
              </div>
            )}
            <div className="text-gray-400">{tickets.length} {isAr?'تذكرة':'tickets'}</div>
          </div>
        </div>

        {/* Filters */}
        <div className="flex gap-3 mb-6">
          {[
            { field:'status', opts:['','OPEN','IN_PROGRESS','WAITING_AGENT','RESOLVED','CLOSED'] },
            { field:'priority', opts:['','CRITICAL','HIGH','MEDIUM','LOW'] },
            { field:'tier', opts:['','L1','L2','L3'] },
          ].map(({field,opts}) => (
            <select key={field} value={(filter as any)[field]}
              onChange={e=>setFilter({...filter,[field]:e.target.value})}
              className="bg-gray-800 border border-gray-600 text-white rounded-lg px-3 py-2 text-sm">
              {opts.map(o=><option key={o} value={o}>{o||L.all}</option>)}
            </select>
          ))}
          <button onClick={fetchTickets} className="bg-gray-700 hover:bg-gray-600 px-4 py-2 rounded-lg text-sm transition">
            {isAr?'تحديث':'Refresh'}
          </button>
        </div>

        {/* Tickets Table */}
        <div className="space-y-2">
          {loading ? <div className="text-center py-10 text-gray-400">Loading...</div> :
           tickets.length === 0 ? <div className="text-center py-10 text-gray-400">{isAr?'لا توجد تذاكر':'No tickets'}</div> :
           tickets.map((tk:any) => (
            <div key={tk.ticket_id}
                 className={`p-4 rounded-xl border flex items-start justify-between gap-4
                             ${tk.sla_breached||tk.sla_status ? 'border-red-700 bg-red-950/30' : 'border-gray-700 bg-gray-900'}`}>
              <div className="flex-1 min-w-0">
                <div className="flex items-center flex-wrap gap-2 mb-1">
                  <span className="font-mono text-sm text-gray-400">{tk.ticket_id}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-bold border ${priorityColors[tk.priority]||'bg-gray-800 text-gray-300 border-gray-700'}`}>{tk.priority}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-bold ${tierColors[tk.tier]||'bg-gray-700 text-gray-300'}`}>{tk.tier}</span>
                  {(tk.sla_breached||tk.sla_status) && <span className="text-xs bg-red-700 text-red-100 px-2 py-0.5 rounded-full font-bold">SLA</span>}
                </div>
                <div className="font-semibold truncate">{tk.subject}</div>
                <div className="text-xs text-gray-500 mt-0.5">{tk.category} · {tk.plan_tier} · {new Date(tk.created_at).toLocaleString(isAr?'ar-SA':'en-US')}</div>
              </div>
              <div className="text-right shrink-0">
                <div className="text-sm font-semibold mb-1">{tk.status}</div>
                <div className="text-xs text-gray-500">{tk.assigned_to||isAr?'غير معين':'unassigned'}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
"""

def main():
    c = connect()
    print("Connected")

    section("FRONTEND: Creating directories")
    run(c, f"mkdir -p '{FE}/admin/sre' '{FE}/admin/compliance' '{FE}/admin/support-queue' '{FE}/admin/ops' '{FE}/support'")

    section("FRONTEND: Uploading pages")
    upload(c, f'{FE}/admin/sre/page.tsx', SRE_PAGE)
    upload(c, f'{FE}/admin/compliance/page.tsx', COMPLIANCE_PAGE)
    upload(c, f'{FE}/support/page.tsx', SUPPORT_PAGE)
    upload(c, f'{FE}/admin/ops/page.tsx', ADMIN_OPS_PAGE)
    upload(c, f'{FE}/admin/support-queue/page.tsx', SUPPORT_ADMIN_PAGE)

    section("FRONTEND: Building Next.js")
    out, err = run(c, "cd /opt/clickbuild/frontend && npm run build 2>&1 | tail -30", timeout=180)

    build_ok = 'Route (app)' in out or 'Generating static pages' in out
    if not build_ok:
        print("Checking for errors...")
        run(c, "cd /opt/clickbuild/frontend && npm run build 2>&1 | grep -i 'error' | head -20", timeout=120)

    if build_ok or 'warn' in out.lower():
        run(c, "pm2 restart clickbuild-frontend 2>&1 | tail -5")
        print("Frontend restarted!")

    section("VERIFICATION")
    time.sleep(3)
    for path in ['/', '/ar/admin/sre', '/ar/admin/compliance', '/ar/support', '/ar/admin/ops']:
        out2, _ = run(c, f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost:3000{path} 2>/dev/null")
        ok = out2 in ['200','307','301','302','308']
        print(f"  [{'OK' if ok else 'FAIL'}] {path}: {out2}")

    c.close()
    print("\nFrontend deployment complete!")
    print("""
ENTERPRISE PAGES:
  /{locale}/admin/ops         — Operations Center (main hub)
  /{locale}/admin/sre         — SRE Dashboard (SLOs, Incidents, Health)
  /{locale}/admin/compliance  — Compliance (SOC2, GDPR, PDPL, ISO27001)
  /{locale}/admin/support-queue — Support Queue (L1/L2/L3)
  /{locale}/support           — Customer Support Portal
""")

if __name__ == "__main__":
    main()
