"use client";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuthStore } from "@/store/auth";
import { api } from "@/lib/api";

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
  running:      "bg-green-100 text-green-800",
  stopped:      "bg-gray-100 text-gray-700",
  provisioning: "bg-yellow-100 text-yellow-800",
  expired:      "bg-red-100 text-red-700",
  error:        "bg-red-100 text-red-800",
  upgrading:    "bg-blue-100 text-blue-800",
};

export default function DashboardPage() {
  const t        = useTranslations("dashboard");
  const tStatus  = useTranslations("status");
  const { user, logout } = useAuthStore();
  const router   = useRouter();
  const [instances, setInstances] = useState<Instance[]>([]);
  const [loading, setLoading]     = useState(true);

  useEffect(() => {
    if (!user) { router.push("/login"); return; }
    loadInstances();
    const interval = setInterval(loadInstances, 15000);  // تحديث كل 15 ثانية
    return () => clearInterval(interval);
  }, [user]);

  async function loadInstances() {
    try {
      const res = await api.get("/instances/");
      setInstances(res.data.instances);
    } catch {
      router.push("/login");
    } finally {
      setLoading(false);
    }
  }

  if (loading) return <div className="flex items-center justify-center h-screen text-gray-500">جاري التحميل...</div>;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="font-black text-xl text-violet-700">ClickBuild</div>
          <div className="flex items-center gap-4">
            <span className="text-gray-600">{t("welcome")}, {user?.name}</span>
            <button onClick={logout} className="text-sm text-gray-500 hover:text-gray-700">خروج</button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-10">

        {/* إذا مفيش instance */}
        {instances.length === 0 ? (
          <div className="text-center py-24">
            <div className="text-6xl mb-6">🚀</div>
            <h2 className="text-2xl font-bold text-gray-800 mb-2">{t("no_instance")}</h2>
            <p className="text-gray-500 mb-8">{t("create_first")}</p>
            <Link
              href="/create"
              className="bg-violet-700 text-white px-8 py-3 rounded-xl font-bold hover:bg-violet-800 transition"
            >
              {t("create_demo")}
            </Link>
          </div>
        ) : (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h1 className="text-2xl font-black text-gray-900">{t("my_instance")}</h1>
              <Link href="/create" className="bg-violet-700 text-white px-5 py-2 rounded-lg font-medium hover:bg-violet-800 transition text-sm">
                + جديد
              </Link>
            </div>

            {instances.map((instance) => (
              <InstanceCard key={instance.id} instance={instance} onRefresh={loadInstances} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}


function InstanceCard({ instance, onRefresh }: { instance: Instance; onRefresh: () => void }) {
  const tStatus = useTranslations("status");
  const [upgrading, setUpgrading] = useState(false);

  const daysLeft = instance.expires_at
    ? Math.ceil((new Date(instance.expires_at).getTime() - Date.now()) / 86400000)
    : null;

  async function handleUpgrade(version: string) {
    setUpgrading(true);
    try {
      await api.post(`/instances/${instance.id}/upgrade`, { target_version: version });
      onRefresh();
    } finally {
      setUpgrading(false);
    }
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
      <div className="p-6">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-xl font-bold text-gray-900">{instance.subdomain}.clickbuild.com</h3>
            <p className="text-gray-500 text-sm mt-1">Odoo {instance.odoo_version}</p>
          </div>
          <span className={`text-xs font-medium px-3 py-1 rounded-full ${STATUS_COLORS[instance.status] || "bg-gray-100"}`}>
            {tStatus(instance.status as any)}
          </span>
        </div>

        {/* Trial countdown */}
        {instance.is_trial && daysLeft !== null && (
          <div className={`mt-4 p-3 rounded-lg text-sm ${daysLeft <= 3 ? "bg-red-50 text-red-700" : "bg-amber-50 text-amber-700"}`}>
            ⏰ التجربة تنتهي خلال <strong>{daysLeft} يوم</strong>
            <Link href="/pricing" className="ms-2 underline font-medium">اشترك الآن</Link>
          </div>
        )}

        {/* ترقية متاحة */}
        {instance.upgrade_available.available && (
          <div className="mt-4 p-3 bg-blue-50 rounded-lg text-sm text-blue-700">
            🆙 يتوفر إصدار Odoo {instance.upgrade_available.versions.join(", ")} أحدث
            {instance.upgrade_available.versions.map(v => (
              <button
                key={v}
                onClick={() => handleUpgrade(v)}
                disabled={upgrading}
                className="ms-2 bg-blue-600 text-white px-3 py-1 rounded text-xs hover:bg-blue-700 disabled:opacity-50"
              >
                {upgrading ? "جاري..." : `ترقية إلى ${v}`}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="border-t border-gray-100 px-6 py-4 bg-gray-50 flex gap-3">
        <a
          href={instance.url}
          target="_blank"
          rel="noopener noreferrer"
          className={`flex-1 text-center bg-violet-700 text-white py-2.5 rounded-lg font-medium hover:bg-violet-800 transition ${instance.status !== "running" ? "opacity-50 pointer-events-none" : ""}`}
        >
          🔗 فتح Odoo
        </a>
        <Link
          href={`/pricing?instance=${instance.id}`}
          className="flex-1 text-center border border-violet-200 text-violet-700 py-2.5 rounded-lg font-medium hover:bg-violet-50 transition"
        >
          ⬆️ ترقية الباقة
        </Link>
      </div>
    </div>
  );
}
