import { useTranslations } from "next-intl";
import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { Metadata } from "next";

export async function generateMetadata({ params: { locale } }: { params: { locale: string } }): Promise<Metadata> {
  const t = await getTranslations({ locale, namespace: "hero" });
  return { title: `ClickBuild — ${t("title")} ${t("titleHighlight")}` };
}

export default function HomePage() {
  const t  = useTranslations();
  const tn = useTranslations("nav");
  const th = useTranslations("hero");
  const tf = useTranslations("features");
  const tp = useTranslations("pricing");

  const features = [
    { key: "accounting", icon: "📊" },
    { key: "sales",      icon: "💼" },
    { key: "inventory",  icon: "📦" },
    { key: "hr",         icon: "👥" },
    { key: "crm",        icon: "🎯" },
    { key: "pos",        icon: "🛒" },
  ] as const;

  return (
    <main className="min-h-screen bg-white">

      {/* ─── Hero ────────────────────────────────────────────────────────── */}
      <section className="relative overflow-hidden bg-gradient-to-br from-violet-950 via-violet-800 to-purple-700 text-white">
        <div className="absolute inset-0 bg-[url('/grid.svg')] opacity-10" />
        <div className="relative max-w-6xl mx-auto px-4 py-24 text-center">

          <span className="inline-block bg-violet-500/30 border border-violet-400/40 text-violet-200 text-sm px-4 py-1 rounded-full mb-6">
            ✨ {th("badge")}
          </span>

          <h1 className="text-5xl md:text-7xl font-black mb-6 leading-tight">
            {th("title")}{" "}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-yellow-300 to-orange-400">
              {th("titleHighlight")}
            </span>
          </h1>

          <p className="text-xl text-violet-200 max-w-2xl mx-auto mb-10">
            {th("subtitle")}
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/register"
              className="bg-white text-violet-900 font-bold px-8 py-4 rounded-xl text-lg hover:bg-violet-50 transition shadow-lg shadow-violet-900/30"
            >
              🚀 {th("cta")}
            </Link>
            <a
              href="#features"
              className="border border-white/30 text-white px-8 py-4 rounded-xl text-lg hover:bg-white/10 transition"
            >
              {th("watchDemo")}
            </a>
          </div>

          <p className="text-violet-300 text-sm mt-4">{th("ctaSub")}</p>

          {/* Stats */}
          <div className="grid grid-cols-3 gap-8 max-w-xl mx-auto mt-16 pt-8 border-t border-white/20">
            {[
              { value: "500+", label: th("stats.clients") },
              { value: "99.9%", label: th("stats.uptime") },
              { value: "24/7", label: th("stats.support") },
            ].map((s) => (
              <div key={s.label}>
                <div className="text-3xl font-black text-yellow-300">{s.value}</div>
                <div className="text-violet-300 text-sm">{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── Features ────────────────────────────────────────────────────── */}
      <section id="features" className="py-24 bg-gray-50">
        <div className="max-w-6xl mx-auto px-4">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-black text-gray-900 mb-4">{tf("title")}</h2>
            <p className="text-gray-600 text-xl">{tf("subtitle")}</p>
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

      {/* ─── CTA ─────────────────────────────────────────────────────────── */}
      <section className="py-24 bg-violet-700 text-white text-center">
        <div className="max-w-2xl mx-auto px-4">
          <h2 className="text-4xl font-black mb-4">ابدأ الآن مجاناً</h2>
          <p className="text-violet-200 text-xl mb-8">14 يوم تجريبي مجاني • لا يلزم بطاقة</p>
          <Link
            href="/register"
            className="bg-white text-violet-900 font-bold px-10 py-4 rounded-xl text-lg hover:bg-violet-50 transition inline-block"
          >
            إنشاء حساب مجاني
          </Link>
        </div>
      </section>

    </main>
  );
}
