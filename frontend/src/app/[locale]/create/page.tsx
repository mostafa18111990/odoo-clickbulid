"use client";
import { useState, useEffect, useCallback } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth";
import { api } from "@/lib/api";

const MODULES = [
  { key: "accounting",    icon: "📊", ar: "المحاسبة",         en: "Accounting" },
  { key: "sales",         icon: "💼", ar: "المبيعات",          en: "Sales" },
  { key: "purchase",      icon: "🛍️", ar: "المشتريات",         en: "Purchase" },
  { key: "inventory",     icon: "📦", ar: "المخزون",            en: "Inventory" },
  { key: "hr",            icon: "👥", ar: "الموارد البشرية",   en: "HR" },
  { key: "crm",           icon: "🎯", ar: "إدارة العملاء",     en: "CRM" },
  { key: "project",       icon: "📋", ar: "إدارة المشاريع",    en: "Project" },
  { key: "pos",           icon: "🛒", ar: "نقاط البيع",        en: "POS" },
  { key: "website",       icon: "🌐", ar: "الموقع الإلكتروني", en: "Website" },
  { key: "manufacturing", icon: "🏭", ar: "التصنيع",            en: "Manufacturing" },
];

export default function CreateInstancePage() {
  const { user }     = useAuthStore();
  const router       = useRouter();
  const [subdomain, setSubdomain]     = useState("");
  const [checkResult, setCheckResult] = useState<null | { available: boolean; reason?: any; url?: string }>(null);
  const [checking, setChecking]       = useState(false);
  const [modules, setModules]         = useState<string[]>(["accounting", "sales"]);
  const [submitting, setSubmitting]   = useState(false);
  const [error, setError]             = useState("");
  const [success, setSuccess]         = useState(false);

  useEffect(() => {
    if (!user) router.push("/login");
  }, [user]);

  const checkSubdomain = useCallback(async (value: string) => {
    if (!value || value.length < 3) { setCheckResult(null); return; }
    setChecking(true);
    try {
      const res = await api.post("/instances/check-subdomain", null, { params: { subdomain: value } });
      setCheckResult(res.data);
    } catch {
      setCheckResult(null);
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => checkSubdomain(subdomain), 600);
    return () => clearTimeout(timer);
  }, [subdomain]);

  function toggleModule(key: string) {
    setModules(prev =>
      prev.includes(key) ? prev.filter(m => m !== key) : [...prev, key]
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!checkResult?.available) return;
    setSubmitting(true);
    setError("");
    try {
      await api.post("/instances/", { subdomain, modules });
      setSuccess(true);
      setTimeout(() => router.push("/dashboard"), 3000);
    } catch (err: any) {
      setError(err.response?.data?.detail?.ar || err.response?.data?.detail || "حدث خطأ");
    } finally {
      setSubmitting(false);
    }
  }

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="text-6xl mb-4">🎉</div>
          <h2 className="text-2xl font-bold text-gray-900 mb-2">تم إنشاء بيئتك!</h2>
          <p className="text-gray-600">ستصلك رسالة على بريدك الإلكتروني بتفاصيل الدخول</p>
          <p className="text-gray-400 text-sm mt-2">سيتم تحويلك للوحة التحكم...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-12">
      <div className="max-w-2xl mx-auto px-4">

        <div className="text-center mb-10">
          <h1 className="text-3xl font-black text-gray-900 mb-2">إنشاء بيئة Odoo 19</h1>
          <p className="text-gray-500">14 يوم مجاناً • لا يلزم بطاقة ائتمان</p>
        </div>

        <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 space-y-8">

          {/* اسم الشركة / Subdomain */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              اسم شركتك (سيكون رابط نظامك)
            </label>
            <div className="flex items-center bg-gray-50 border border-gray-200 rounded-xl overflow-hidden focus-within:border-violet-400 focus-within:ring-2 focus-within:ring-violet-100 transition">
              <input
                type="text"
                value={subdomain}
                onChange={e => setSubdomain(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))}
                placeholder="my-company"
                className="flex-1 px-4 py-3 bg-transparent text-gray-900 placeholder-gray-400 focus:outline-none"
                required
              />
              <span className="px-4 py-3 text-gray-400 text-sm whitespace-nowrap border-s border-gray-200">.clickbuild.com</span>
            </div>

            {/* نتيجة التحقق */}
            <div className="mt-2 text-sm h-5">
              {checking && <span className="text-gray-400">جاري التحقق...</span>}
              {!checking && checkResult?.available === true && (
                <span className="text-green-600 font-medium">✓ متاح — {checkResult.url}</span>
              )}
              {!checking && checkResult?.available === false && (
                <span className="text-red-500">✗ {checkResult.reason?.ar || "محجوز"}</span>
              )}
            </div>
          </div>

          {/* الوحدات */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-3">
              اختر الوحدات التي تحتاجها
            </label>
            <div className="grid grid-cols-2 gap-3">
              {MODULES.map(mod => (
                <button
                  key={mod.key}
                  type="button"
                  onClick={() => toggleModule(mod.key)}
                  className={`flex items-center gap-3 p-3 rounded-xl border-2 text-start transition ${
                    modules.includes(mod.key)
                      ? "border-violet-500 bg-violet-50 text-violet-900"
                      : "border-gray-200 bg-white text-gray-700 hover:border-gray-300"
                  }`}
                >
                  <span className="text-2xl">{mod.icon}</span>
                  <div>
                    <div className="font-medium text-sm">{mod.ar}</div>
                    <div className="text-xs text-gray-400">{mod.en}</div>
                  </div>
                  {modules.includes(mod.key) && (
                    <span className="ms-auto text-violet-500 text-lg">✓</span>
                  )}
                </button>
              ))}
            </div>
            <p className="text-xs text-gray-400 mt-2">يمكنك إضافة المزيد من الوحدات لاحقاً</p>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-sm">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting || !checkResult?.available}
            className="w-full bg-violet-700 text-white py-4 rounded-xl font-bold text-lg hover:bg-violet-800 transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? "⏳ جاري الإنشاء... (2-3 دقائق)" : "🚀 إنشاء البيئة"}
          </button>

          <p className="text-center text-xs text-gray-400">
            بالضغط على الزر توافق على <a href="/terms" className="underline">شروط الاستخدام</a>
          </p>
        </form>
      </div>
    </div>
  );
}
