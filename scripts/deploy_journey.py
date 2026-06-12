#!/usr/bin/env python3
"""
Deploy Customer Journey: Landing → Pricing → Register → Onboarding → Dashboard → Billing
"""
import paramiko, io, sys, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HOST = "129.121.98.243"; USER = "root"; PASS = "Mh@01007121878"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30)

def run(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    return out, err

def rp(cmd, label="", timeout=30):
    out, err = run(cmd, timeout)
    r = (out + err).strip()
    if r: print(f"  [{label}] {r[:400]}")
    return out, err

import paramiko.sftp_client

sftp = client.open_sftp()

def upload(remote_path: str, content: str):
    with sftp.open(remote_path, 'w') as f:
        f.write(content)
    print(f"  ✓ {remote_path}")

print("=" * 60)
print("Deploy Customer Journey")
print("=" * 60)

# ─────────────────────────────────────────────────────────────
# STEP 1: Backend — Plans API
# ─────────────────────────────────────────────────────────────
print("\n[1/6] Backend: Plans & Subscriptions API...")

upload("/opt/clickbuild/backend/app/api/v1/endpoints/plans.py", '''
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.subscription import Plan

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("/")
async def list_plans(db: AsyncSession = Depends(get_db)):
    """خطط الاشتراك المتاحة (عامة)"""
    result = await db.execute(
        select(Plan).where(Plan.is_active == True).order_by(Plan.price_egp)
    )
    plans = result.scalars().all()
    return {"plans": [_serialize(p) for p in plans]}


@router.get("/{plan_name}")
async def get_plan(plan_name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Plan).where(Plan.name == plan_name))
    plan = result.scalar_one_or_none()
    if not plan:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="الخطة غير موجودة")
    return _serialize(plan)


def _serialize(p: Plan) -> dict:
    return {
        "id":           str(p.id),
        "name":         p.name,
        "name_ar":      p.name_ar,
        "name_en":      p.name_en,
        "price_egp":    float(p.price_egp or 0),
        "price_sar":    float(p.price_sar or 0),
        "price_aed":    float(p.price_aed or 0),
        "price_usd":    float(p.price_usd or 0),
        "max_users":    p.max_users,
        "storage_gb":   p.storage_gb,
        "max_instances":p.max_instances,
        "cpu_limit":    p.cpu_limit,
        "memory_mb":    p.memory_mb,
        "features_ar":  p.features_ar or [],
        "features_en":  p.features_en or [],
        "is_active":    p.is_active,
    }
''')

upload("/opt/clickbuild/backend/app/api/v1/endpoints/subscriptions.py", '''
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.subscription import Subscription, SubStatus, Plan, PlanName

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get("/me")
async def my_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """اشتراك المستخدم الحالي"""
    result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == current_user.id)
        .order_by(Subscription.started_at.desc())
        .limit(1)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        return {"subscription": None}

    plan_result = await db.execute(select(Plan).where(Plan.id == sub.plan_id))
    plan = plan_result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    days_left = None
    if sub.expires_at:
        delta = sub.expires_at.replace(tzinfo=timezone.utc) - now
        days_left = max(0, delta.days)

    return {
        "subscription": {
            "id":         str(sub.id),
            "status":     sub.status,
            "plan_name":  plan.name if plan else None,
            "plan_ar":    plan.name_ar if plan else None,
            "plan_en":    plan.name_en if plan else None,
            "started_at": sub.started_at,
            "expires_at": sub.expires_at,
            "days_left":  days_left,
            "is_trial":   sub.status == SubStatus.TRIAL,
            "amount":     float(sub.amount or 0),
            "currency":   sub.currency,
        }
    }


class UpgradePlanRequest(BaseModel):
    plan_name: str
    payment_gateway: str = "paymob"
    currency: str = "EGP"


@router.post("/upgrade")
async def upgrade_subscription(
    body: UpgradePlanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """طلب ترقية الاشتراك"""
    plan_result = await db.execute(
        select(Plan).where(Plan.name == body.plan_name, Plan.is_active == True)
    )
    plan = plan_result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="الخطة غير موجودة")

    # Return payment intent info (PayMob integration coming next)
    price = float(plan.price_egp if body.currency == "EGP" else plan.price_usd)
    return {
        "message": {"ar": "سيتم تفعيل الدفع قريباً", "en": "Payment coming soon"},
        "plan":    body.plan_name,
        "amount":  price,
        "currency": body.currency,
        "redirect": None,
    }
''')

# ─────────────────────────────────────────────────────────────
# STEP 2: Update main.py to include new routers
# ─────────────────────────────────────────────────────────────
print("\n[2/6] Update main.py...")

upload("/opt/clickbuild/backend/app/main.py", '''
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.database import engine, Base

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(
    title="ClickBuild API",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.v1.endpoints import auth, instances, payments, plans, subscriptions
from app.api.v1.endpoints.admin import router as admin_router
from app.api.v1.endpoints.proxy import router as proxy_router

app.include_router(auth.router,          prefix="/api/v1")
app.include_router(instances.router,     prefix="/api/v1")
app.include_router(payments.router,      prefix="/api/v1")
app.include_router(plans.router,         prefix="/api/v1")
app.include_router(subscriptions.router, prefix="/api/v1")
app.include_router(admin_router,         prefix="/api/v1")
app.include_router(proxy_router)  # /odoo-proxy/*

@app.get("/api/health")
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}
''')

# ─────────────────────────────────────────────────────────────
# STEP 3: Seed Plans in DB
# ─────────────────────────────────────────────────────────────
print("\n[3/6] Seed plans in DB...")

seed_sql = """
-- Create tables if not exist (handled by SQLAlchemy lifespan, but just in case)
DO $$
DECLARE
  trial_id UUID := gen_random_uuid();
  starter_id UUID := gen_random_uuid();
  business_id UUID := gen_random_uuid();
  enterprise_id UUID := gen_random_uuid();
BEGIN

-- Only seed if plans table is empty
IF (SELECT COUNT(*) FROM plans) = 0 THEN

INSERT INTO plans (id, name, name_ar, name_en, price_egp, price_sar, price_aed, price_usd,
  max_users, storage_gb, max_instances, cpu_limit, memory_mb,
  features_ar, features_en, is_active)
VALUES
(
  trial_id, 'trial', 'تجريبي', 'Trial',
  0, 0, 0, 0,
  3, 1.0, 1, 0.5, 512,
  '["14 يوم مجاناً", "3 مستخدمين", "الوحدات الأساسية", "دعم بالبريد الإلكتروني"]',
  '["14 days free", "3 users", "Core modules", "Email support"]',
  true
),
(
  starter_id, 'starter', 'مبتدئ', 'Starter',
  299, 89, 99, 27,
  10, 10.0, 1, 1.0, 1024,
  '["10 مستخدمين", "10 جيجا تخزين", "نسخ احتياطي يومي", "دعم على مدار الساعة", "جميع الوحدات الأساسية"]',
  '["10 users", "10 GB storage", "Daily backups", "24/7 support", "All core modules"]',
  true
),
(
  business_id, 'business', 'أعمال', 'Business',
  699, 199, 219, 59,
  50, 50.0, 3, 2.0, 2048,
  '["50 مستخدماً", "50 جيجا تخزين", "نسخ احتياطي كل ساعة", "دعم أولوية", "3 بيئات", "بيئة اختبار", "لوحة تحليلات متقدمة"]',
  '["50 users", "50 GB storage", "Hourly backups", "Priority support", "3 instances", "Staging env", "Advanced analytics"]',
  true
),
(
  enterprise_id, 'enterprise', 'متقدم', 'Enterprise',
  1499, 449, 499, 129,
  999, 200.0, 10, 4.0, 4096,
  '["مستخدمون غير محدودون", "200 جيجا تخزين", "نسخ احتياطي فوري", "مدير حساب مخصص", "10 بيئات", "تخصيص كامل", "تكامل API", "SLA 99.9%"]',
  '["Unlimited users", "200 GB storage", "Real-time backups", "Dedicated account manager", "10 instances", "Full customization", "API integration", "99.9% SLA"]',
  true
);

END IF;
END $$;
"""

rp(f"PGPASSWORD='CB_pg_S3cur3_2024!' psql -h localhost -U clickbuild -d clickbuild_platform -c \"{seed_sql.replace(chr(10), ' ').replace('\"', chr(39))}\"", "SEED", timeout=15)

# Run via file to avoid quoting issues
upload("/tmp/seed_plans.sql", seed_sql)
rp("PGPASSWORD='CB_pg_S3cur3_2024!' psql -h localhost -U clickbuild -d clickbuild_platform -f /tmp/seed_plans.sql", "SEED_PLANS", timeout=15)

# ─────────────────────────────────────────────────────────────
# STEP 4: Frontend — Pricing Page
# ─────────────────────────────────────────────────────────────
print("\n[4/6] Frontend: Pricing page...")

rp("mkdir -p /opt/clickbuild/frontend/src/app/\\[locale\\]/pricing", "MKDIR")
rp("mkdir -p /opt/clickbuild/frontend/src/app/\\[locale\\]/onboarding", "MKDIR")
rp("mkdir -p /opt/clickbuild/frontend/src/app/\\[locale\\]/billing", "MKDIR")

upload("/opt/clickbuild/frontend/src/app/[locale]/pricing/page.tsx", '''"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth";

interface Plan {
  id: string;
  name: string;
  name_ar: string;
  name_en: string;
  price_egp: number;
  price_usd: number;
  max_users: number;
  storage_gb: number;
  features_ar: string[];
  features_en: string[];
}

export default function PricingPage() {
  const { locale } = useParams() as { locale: string };
  const isAr = locale === "ar";
  const router = useRouter();
  const { user } = useAuthStore();

  const [plans, setPlans] = useState<Plan[]>([]);
  const [billing, setBilling] = useState<"monthly" | "annual">("monthly");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/plans/").then(r => {
      setPlans(r.data.plans.filter((p: Plan) => p.name !== "trial"));
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  function handleSelectPlan(planName: string) {
    if (user) {
      router.push(`/${locale}/onboarding?plan=${planName}`);
    } else {
      router.push(`/${locale}/register?plan=${planName}`);
    }
  }

  const POPULAR = "business";

  return (
    <div className="min-h-screen bg-gray-50" dir={isAr ? "rtl" : "ltr"}>
      {/* Header */}
      <div className="bg-white border-b border-gray-100 px-4 py-4 flex items-center justify-between max-w-6xl mx-auto">
        <Link href={`/${locale}`} className="text-2xl font-black text-violet-700">ClickBuild</Link>
        <div className="flex gap-3">
          <Link href={`/${locale}/login`} className="text-gray-600 hover:text-gray-900 px-4 py-2 rounded-lg transition">
            {isAr ? "تسجيل الدخول" : "Login"}
          </Link>
          <Link href={`/${locale}/register`} className="bg-violet-700 text-white px-4 py-2 rounded-lg hover:bg-violet-800 transition text-sm font-medium">
            {isAr ? "ابدأ مجاناً" : "Start Free"}
          </Link>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 py-16">
        {/* Title */}
        <div className="text-center mb-12">
          <h1 className="text-4xl md:text-5xl font-black text-gray-900 mb-4">
            {isAr ? "اختر خطتك" : "Choose Your Plan"}
          </h1>
          <p className="text-xl text-gray-500">
            {isAr ? "جميع الخطط تشمل 14 يوم تجريبي مجاني • بدون بطاقة ائتمان" : "All plans include 14-day free trial • No credit card required"}
          </p>

          {/* Billing Toggle */}
          <div className="flex items-center justify-center gap-4 mt-8">
            <button
              onClick={() => setBilling("monthly")}
              className={`px-6 py-2 rounded-full text-sm font-medium transition ${billing === "monthly" ? "bg-violet-700 text-white" : "bg-white text-gray-600 border border-gray-200"}`}
            >
              {isAr ? "شهري" : "Monthly"}
            </button>
            <button
              onClick={() => setBilling("annual")}
              className={`px-6 py-2 rounded-full text-sm font-medium transition ${billing === "annual" ? "bg-violet-700 text-white" : "bg-white text-gray-600 border border-gray-200"}`}
            >
              {isAr ? "سنوي (وفر 20%)" : "Annual (Save 20%)"}
            </button>
          </div>
        </div>

        {loading ? (
          <div className="flex justify-center py-20">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-violet-700" />
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {plans.map((plan) => {
              const isPopular = plan.name === POPULAR;
              const price = billing === "annual" ? Math.round(plan.price_egp * 0.8) : plan.price_egp;
              const features = isAr ? plan.features_ar : plan.features_en;

              return (
                <div
                  key={plan.name}
                  className={`relative bg-white rounded-2xl p-8 border-2 transition-all ${
                    isPopular
                      ? "border-violet-500 shadow-xl shadow-violet-100 scale-105"
                      : "border-gray-200 shadow-sm hover:shadow-md hover:-translate-y-1"
                  }`}
                >
                  {isPopular && (
                    <div className="absolute -top-4 left-1/2 -translate-x-1/2">
                      <span className="bg-violet-700 text-white text-xs font-bold px-4 py-1 rounded-full whitespace-nowrap">
                        {isAr ? "⭐ الأكثر شعبية" : "⭐ Most Popular"}
                      </span>
                    </div>
                  )}

                  <div className="mb-6">
                    <h3 className="text-xl font-black text-gray-900 mb-1">
                      {isAr ? plan.name_ar : plan.name_en}
                    </h3>
                    <div className="flex items-end gap-1 mt-3">
                      <span className="text-4xl font-black text-gray-900">{price.toLocaleString()}</span>
                      <span className="text-gray-500 mb-1">{isAr ? "ج.م / شهر" : "EGP / mo"}</span>
                    </div>
                    <p className="text-sm text-gray-400 mt-1">
                      {plan.max_users === 999
                        ? (isAr ? "مستخدمون غير محدودون" : "Unlimited users")
                        : (isAr ? `حتى ${plan.max_users} مستخدمين` : `Up to ${plan.max_users} users`)
                      }
                      {" · "}
                      {plan.storage_gb >= 100
                        ? (isAr ? `${plan.storage_gb} جيجا` : `${plan.storage_gb} GB`)
                        : (isAr ? `${plan.storage_gb} جيجا` : `${plan.storage_gb} GB`)
                      }
                    </p>
                  </div>

                  <ul className="space-y-3 mb-8">
                    {features.map((f, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                        <span className="text-green-500 mt-0.5 flex-shrink-0">✓</span>
                        {f}
                      </li>
                    ))}
                  </ul>

                  <button
                    onClick={() => handleSelectPlan(plan.name)}
                    className={`w-full py-3 rounded-xl font-bold text-sm transition ${
                      isPopular
                        ? "bg-violet-700 text-white hover:bg-violet-800"
                        : "bg-gray-100 text-gray-900 hover:bg-gray-200"
                    }`}
                  >
                    {isAr ? "ابدأ تجربتك المجانية" : "Start Free Trial"}
                  </button>
                </div>
              );
            })}
          </div>
        )}

        {/* FAQ */}
        <div className="mt-20 max-w-2xl mx-auto">
          <h2 className="text-2xl font-black text-center text-gray-900 mb-8">
            {isAr ? "أسئلة شائعة" : "FAQ"}
          </h2>
          <div className="space-y-4">
            {(isAr ? [
              ["هل يلزم بطاقة ائتمانية؟", "لا، يمكنك البدء مجاناً لمدة 14 يوم بدون أي بيانات دفع."],
              ["ماذا يحدث بعد انتهاء التجربة؟", "ستحتفظ ببياناتك ويمكنك الترقية في أي وقت. بعد 30 يوم إضافي تُحذف البيانات."],
              ["هل يمكنني تغيير الخطة؟", "نعم، يمكنك الترقية أو التخفيض في أي وقت."],
              ["ما طرق الدفع المتاحة؟", "نقبل البطاقات الائتمانية، فودافون كاش، فوري، وحوالات بنكية."],
            ] : [
              ["Is a credit card required?", "No, you can start for free for 14 days without any payment info."],
              ["What happens after the trial?", "Your data is kept and you can upgrade anytime. After 30 extra days, data is deleted."],
              ["Can I change my plan?", "Yes, you can upgrade or downgrade at any time."],
              ["What payment methods are accepted?", "We accept credit cards, Vodafone Cash, Fawry, and bank transfers."],
            ]).map(([q, a], i) => (
              <details key={i} className="bg-white border border-gray-200 rounded-xl p-5">
                <summary className="font-semibold text-gray-900 cursor-pointer">{q}</summary>
                <p className="text-gray-600 mt-3 text-sm">{a}</p>
              </details>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
''')

# ─────────────────────────────────────────────────────────────
# STEP 5: Onboarding Wizard (replaces /create)
# ─────────────────────────────────────────────────────────────
print("\n[5/6] Frontend: Onboarding wizard...")

upload("/opt/clickbuild/frontend/src/app/[locale]/onboarding/page.tsx", '''"use client";
import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useAuthStore } from "@/store/auth";
import { api } from "@/lib/api";

const MODULES = [
  { key: "accounting",    icon: "📊", ar: "المحاسبة",          en: "Accounting" },
  { key: "sales",         icon: "💼", ar: "المبيعات",           en: "Sales" },
  { key: "purchase",      icon: "🛍️",  ar: "المشتريات",          en: "Purchase" },
  { key: "inventory",     icon: "📦", ar: "المخزون",             en: "Inventory" },
  { key: "hr",            icon: "👥", ar: "الموارد البشرية",    en: "HR" },
  { key: "crm",           icon: "🎯", ar: "إدارة العملاء",      en: "CRM" },
  { key: "project",       icon: "📋", ar: "إدارة المشاريع",     en: "Project" },
  { key: "pos",           icon: "🛒", ar: "نقاط البيع",         en: "POS" },
  { key: "website",       icon: "🌐", ar: "الموقع الإلكتروني",  en: "Website" },
  { key: "manufacturing", icon: "🏭", ar: "التصنيع",             en: "Manufacturing" },
];

const INDUSTRIES = [
  { key: "retail",       icon: "🛍️",  ar: "تجزئة وبيع بالتجزئة",  en: "Retail" },
  { key: "services",     icon: "🤝", ar: "خدمات مهنية",            en: "Professional Services" },
  { key: "manufacturing",icon: "🏭", ar: "تصنيع وإنتاج",           en: "Manufacturing" },
  { key: "restaurant",   icon: "🍽️",  ar: "مطاعم وضيافة",           en: "Restaurants" },
  { key: "real_estate",  icon: "🏢", ar: "عقارات",                 en: "Real Estate" },
  { key: "healthcare",   icon: "🏥", ar: "رعاية صحية",             en: "Healthcare" },
  { key: "education",    icon: "🎓", ar: "تعليم",                  en: "Education" },
  { key: "other",        icon: "💡", ar: "أخرى",                   en: "Other" },
];

// Modules recommended per industry
const INDUSTRY_MODULES: Record<string, string[]> = {
  retail:        ["accounting", "sales", "inventory", "pos", "purchase"],
  services:      ["accounting", "sales", "crm", "project", "hr"],
  manufacturing: ["accounting", "manufacturing", "inventory", "purchase", "sales"],
  restaurant:    ["accounting", "pos", "inventory", "purchase"],
  real_estate:   ["accounting", "sales", "crm", "project"],
  healthcare:    ["accounting", "hr", "project", "crm"],
  education:     ["accounting", "hr", "website"],
  other:         ["accounting", "sales"],
};

export default function OnboardingPage() {
  const { locale } = useParams() as { locale: string };
  const isAr = locale === "ar";
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user } = useAuthStore();

  const [step, setStep] = useState(1); // 1=industry, 2=subdomain, 3=modules, 4=creating
  const [industry, setIndustry] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [subdomain, setSubdomain] = useState("");
  const [checkResult, setCheckResult] = useState<{ available: boolean; reason?: any; url?: string } | null>(null);
  const [checking, setChecking] = useState(false);
  const [modules, setModules] = useState<string[]>(["accounting", "sales"]);
  const [error, setError] = useState("");
  const [instanceId, setInstanceId] = useState("");
  const [instanceStatus, setInstanceStatus] = useState("provisioning");

  useEffect(() => {
    if (!user) router.push(`/${locale}/login`);
  }, [user]);

  // Auto-fill subdomain from company name
  useEffect(() => {
    if (companyName) {
      const auto = companyName
        .toLowerCase()
        .replace(/[^a-z0-9\s-]/g, "")
        .trim()
        .replace(/\s+/g, "-")
        .substring(0, 30);
      if (auto.length >= 3) setSubdomain(auto);
    }
  }, [companyName]);

  // Subdomain availability check
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
    const t = setTimeout(() => checkSubdomain(subdomain), 600);
    return () => clearTimeout(t);
  }, [subdomain]);

  // Poll instance status when creating
  useEffect(() => {
    if (step !== 4 || !instanceId) return;
    const poll = setInterval(async () => {
      try {
        const res = await api.get(`/instances/${instanceId}`);
        const s = res.data.status;
        setInstanceStatus(s);
        if (s === "running") {
          clearInterval(poll);
          setTimeout(() => router.push(`/${locale}/dashboard`), 1500);
        } else if (s === "error") {
          clearInterval(poll);
          setError(isAr ? "حدث خطأ أثناء الإنشاء" : "Error during creation");
        }
      } catch {}
    }, 4000);
    return () => clearInterval(poll);
  }, [step, instanceId]);

  function selectIndustry(ind: string) {
    setIndustry(ind);
    setModules(INDUSTRY_MODULES[ind] || ["accounting", "sales"]);
    setStep(2);
  }

  function toggleModule(key: string) {
    setModules(prev =>
      prev.includes(key) ? prev.filter(m => m !== key) : [...prev, key]
    );
  }

  async function handleCreate() {
    if (!checkResult?.available || modules.length === 0) return;
    setStep(4);
    setError("");
    try {
      const res = await api.post("/instances/", { subdomain, modules });
      setInstanceId(res.data.instance_id);
    } catch (err: any) {
      setError(err.response?.data?.detail?.ar || err.response?.data?.detail || (isAr ? "حدث خطأ" : "Error occurred"));
      setStep(3);
    }
  }

  // ─── Step 1: Industry ─────────────────────────────────────────────────
  if (step === 1) return (
    <div className="min-h-screen bg-gray-50 py-12" dir={isAr ? "rtl" : "ltr"}>
      <div className="max-w-2xl mx-auto px-4">
        <div className="text-center mb-10">
          <div className="text-5xl mb-4">👋</div>
          <h1 className="text-3xl font-black text-gray-900 mb-2">
            {isAr ? `أهلاً ${user?.name?.split(" ")[0] || ""}!` : `Welcome ${user?.name?.split(" ")[0] || ""}!`}
          </h1>
          <p className="text-gray-500">
            {isAr ? "ما هو قطاع عملك؟ سنختار الوحدات المناسبة تلقائياً" : "What is your industry? We'll auto-select the right modules"}
          </p>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {INDUSTRIES.map(ind => (
            <button
              key={ind.key}
              onClick={() => selectIndustry(ind.key)}
              className="bg-white border-2 border-gray-200 hover:border-violet-500 hover:bg-violet-50 rounded-2xl p-5 text-center transition-all group"
            >
              <div className="text-4xl mb-2">{ind.icon}</div>
              <div className="text-sm font-semibold text-gray-800 group-hover:text-violet-700">
                {isAr ? ind.ar : ind.en}
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );

  // ─── Step 2: Company Name + Subdomain ─────────────────────────────────
  if (step === 2) return (
    <div className="min-h-screen bg-gray-50 py-12" dir={isAr ? "rtl" : "ltr"}>
      <div className="max-w-lg mx-auto px-4">
        <button onClick={() => setStep(1)} className="text-gray-400 hover:text-gray-600 mb-6 flex items-center gap-2 text-sm">
          {isAr ? "→ رجوع" : "← Back"}
        </button>
        <div className="text-center mb-10">
          <div className="text-5xl mb-4">🏢</div>
          <h1 className="text-2xl font-black text-gray-900 mb-2">
            {isAr ? "ما اسم شركتك؟" : "What is your company name?"}
          </h1>
          <p className="text-gray-500 text-sm">
            {isAr ? "سيكون اسم نظامك على الإنترنت" : "This will be your system URL"}
          </p>
        </div>

        <div className="bg-white rounded-2xl border border-gray-200 p-6 space-y-5 shadow-sm">
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              {isAr ? "اسم الشركة (بالإنجليزية)" : "Company Name (in English)"}
            </label>
            <input
              type="text"
              value={companyName}
              onChange={e => setCompanyName(e.target.value)}
              placeholder={isAr ? "مثال: My Company" : "e.g. My Company"}
              className="w-full px-4 py-3 border border-gray-200 rounded-xl text-gray-900 focus:outline-none focus:border-violet-400 focus:ring-2 focus:ring-violet-100 transition"
              dir="ltr"
            />
          </div>

          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              {isAr ? "رابط نظامك" : "Your System URL"}
            </label>
            <div className="flex items-center bg-gray-50 border border-gray-200 rounded-xl overflow-hidden focus-within:border-violet-400 focus-within:ring-2 focus-within:ring-violet-100 transition">
              <input
                type="text"
                value={subdomain}
                onChange={e => setSubdomain(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))}
                placeholder="my-company"
                className="flex-1 px-4 py-3 bg-transparent text-gray-900 placeholder-gray-400 focus:outline-none"
                dir="ltr"
              />
              <span className="px-3 py-3 text-gray-400 text-sm border-s border-gray-200 whitespace-nowrap">.clickbuild.com</span>
            </div>
            <div className="mt-2 text-sm h-5">
              {checking && <span className="text-gray-400">{isAr ? "جاري التحقق..." : "Checking..."}</span>}
              {!checking && checkResult?.available === true && (
                <span className="text-green-600 font-medium">✓ {isAr ? "متاح" : "Available"} — {checkResult.url}</span>
              )}
              {!checking && checkResult?.available === false && (
                <span className="text-red-500">✗ {checkResult.reason?.ar || checkResult.reason?.en || (isAr ? "محجوز" : "Taken")}</span>
              )}
            </div>
          </div>

          <button
            onClick={() => setStep(3)}
            disabled={!checkResult?.available || !subdomain}
            className="w-full bg-violet-700 text-white py-3 rounded-xl font-bold hover:bg-violet-800 transition disabled:opacity-40"
          >
            {isAr ? "التالي ←" : "Next →"}
          </button>
        </div>
      </div>
    </div>
  );

  // ─── Step 3: Modules ──────────────────────────────────────────────────
  if (step === 3) return (
    <div className="min-h-screen bg-gray-50 py-12" dir={isAr ? "rtl" : "ltr"}>
      <div className="max-w-2xl mx-auto px-4">
        <button onClick={() => setStep(2)} className="text-gray-400 hover:text-gray-600 mb-6 flex items-center gap-2 text-sm">
          {isAr ? "→ رجوع" : "← Back"}
        </button>
        <div className="text-center mb-8">
          <div className="text-5xl mb-4">⚙️</div>
          <h1 className="text-2xl font-black text-gray-900 mb-2">
            {isAr ? "اختر الوحدات" : "Choose Modules"}
          </h1>
          <p className="text-gray-500 text-sm">
            {isAr ? "اخترنا لك الوحدات المناسبة لقطاعك • يمكنك التعديل" : "We pre-selected modules for your industry • you can modify"}
          </p>
        </div>

        <div className="grid grid-cols-2 gap-3 mb-6">
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
                <div className="font-medium text-sm">{isAr ? mod.ar : mod.en}</div>
              </div>
              {modules.includes(mod.key) && <span className="ms-auto text-violet-500">✓</span>}
            </button>
          ))}
        </div>

        <p className="text-xs text-gray-400 text-center mb-6">
          {isAr ? "يمكنك إضافة وحدات أخرى لاحقاً من داخل النظام" : "You can add more modules later from inside the system"}
        </p>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-sm mb-4">{error}</div>
        )}

        <button
          onClick={handleCreate}
          disabled={modules.length === 0 || !checkResult?.available}
          className="w-full bg-violet-700 text-white py-4 rounded-xl font-bold text-lg hover:bg-violet-800 transition disabled:opacity-40"
        >
          {isAr ? "🚀 إنشاء نظامي الآن" : "🚀 Create My System"}
        </button>
      </div>
    </div>
  );

  // ─── Step 4: Creating / Provisioning ─────────────────────────────────
  return (
    <div className="min-h-screen bg-gradient-to-br from-violet-950 via-violet-800 to-purple-700 flex items-center justify-center" dir={isAr ? "rtl" : "ltr"}>
      <div className="text-center text-white px-4">
        {instanceStatus === "running" ? (
          <>
            <div className="text-8xl mb-6">🎉</div>
            <h1 className="text-4xl font-black mb-4">{isAr ? "نظامك جاهز!" : "Your system is ready!"}</h1>
            <p className="text-violet-200 text-xl">{isAr ? "جاري التحويل..." : "Redirecting..."}</p>
          </>
        ) : (
          <>
            <div className="relative w-24 h-24 mx-auto mb-8">
              <div className="absolute inset-0 rounded-full border-4 border-violet-400/30" />
              <div className="absolute inset-0 rounded-full border-4 border-t-white animate-spin" />
              <div className="absolute inset-0 flex items-center justify-center text-3xl">⚙️</div>
            </div>
            <h1 className="text-3xl font-black mb-4">
              {isAr ? "جاري إنشاء نظامك..." : "Creating your system..."}
            </h1>
            <p className="text-violet-200 text-lg mb-8">
              {isAr ? "هذا يستغرق حوالي 30 ثانية" : "This takes about 30 seconds"}
            </p>
            <div className="bg-white/10 rounded-2xl p-6 max-w-sm mx-auto text-start space-y-3">
              {(isAr ? [
                ["✅", "تم إنشاء قاعدة البيانات"],
                [instanceStatus !== "provisioning" ? "✅" : "⏳", "تثبيت Odoo 19"],
                [instanceStatus === "running" ? "✅" : "⏳", "تهيئة النظام"],
                ["⏳", "نشر الوحدات المختارة"],
              ] : [
                ["✅", "Database created"],
                [instanceStatus !== "provisioning" ? "✅" : "⏳", "Installing Odoo 19"],
                [instanceStatus === "running" ? "✅" : "⏳", "System configuration"],
                ["⏳", "Deploying selected modules"],
              ]).map(([icon, label], i) => (
                <div key={i} className="flex items-center gap-3 text-violet-100">
                  <span>{icon}</span>
                  <span className="text-sm">{label}</span>
                </div>
              ))}
            </div>
            <p className="text-violet-300 text-sm mt-8">
              {isAr ? `نظامك: ${subdomain}.clickbuild.com` : `Your system: ${subdomain}.clickbuild.com`}
            </p>
          </>
        )}
      </div>
    </div>
  );
}
''')

# ─────────────────────────────────────────────────────────────
# STEP 6: Billing Page + Update Landing + Update Layout
# ─────────────────────────────────────────────────────────────
print("\n[6/6] Frontend: Billing page + update landing...")

upload("/opt/clickbuild/frontend/src/app/[locale]/billing/page.tsx", '''"use client";
import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useAuthStore } from "@/store/auth";
import { api } from "@/lib/api";

interface SubInfo {
  status: string;
  plan_name: string;
  plan_ar: string;
  plan_en: string;
  started_at: string;
  expires_at: string;
  days_left: number;
  is_trial: boolean;
  amount: number;
  currency: string;
}

interface Plan {
  name: string;
  name_ar: string;
  name_en: string;
  price_egp: number;
  max_users: number;
  storage_gb: number;
  features_ar: string[];
  features_en: string[];
}

export default function BillingPage() {
  const { locale } = useParams() as { locale: string };
  const isAr = locale === "ar";
  const router = useRouter();
  const { user } = useAuthStore();

  const [sub, setSub] = useState<SubInfo | null>(null);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) { router.push(`/${locale}/login`); return; }
    Promise.all([
      api.get("/subscriptions/me"),
      api.get("/plans/"),
    ]).then(([subRes, plansRes]) => {
      setSub(subRes.data.subscription);
      setPlans(plansRes.data.plans.filter((p: Plan) => p.name !== "trial"));
    }).finally(() => setLoading(false));
  }, [user]);

  const statusColor: Record<string, string> = {
    trial:     "bg-blue-100 text-blue-700",
    active:    "bg-green-100 text-green-700",
    past_due:  "bg-red-100 text-red-700",
    cancelled: "bg-gray-100 text-gray-700",
    suspended: "bg-orange-100 text-orange-700",
  };

  const statusAr: Record<string, string> = {
    trial:     "تجريبي",
    active:    "نشط",
    past_due:  "متأخر",
    cancelled: "ملغي",
    suspended: "موقوف",
  };

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-violet-700" />
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-50" dir={isAr ? "rtl" : "ltr"}>
      <div className="max-w-4xl mx-auto px-4 py-10">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-2xl font-black text-gray-900">
            {isAr ? "الاشتراك والفوترة" : "Subscription & Billing"}
          </h1>
          <Link href={`/${locale}/dashboard`} className="text-sm text-gray-500 hover:text-gray-700">
            {isAr ? "← لوحة التحكم" : "→ Dashboard"}
          </Link>
        </div>

        {/* Current Subscription */}
        {sub ? (
          <div className="bg-white rounded-2xl border border-gray-200 p-6 mb-8 shadow-sm">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h2 className="text-lg font-bold text-gray-900">
                  {isAr ? "خطتك الحالية" : "Current Plan"}
                </h2>
                <p className="text-2xl font-black text-violet-700 mt-1">
                  {isAr ? sub.plan_ar : sub.plan_en}
                </p>
              </div>
              <span className={`px-3 py-1 rounded-full text-sm font-medium ${statusColor[sub.status] || "bg-gray-100 text-gray-700"}`}>
                {isAr ? (statusAr[sub.status] || sub.status) : sub.status}
              </span>
            </div>

            {sub.is_trial && sub.days_left !== null && (
              <div className={`rounded-xl p-4 mb-4 ${sub.days_left <= 3 ? "bg-red-50 border border-red-200" : "bg-blue-50 border border-blue-200"}`}>
                <p className={`font-medium ${sub.days_left <= 3 ? "text-red-700" : "text-blue-700"}`}>
                  {isAr
                    ? `${sub.days_left <= 0 ? "انتهت تجربتك المجانية" : `تبقى ${sub.days_left} يوم على انتهاء التجربة`}`
                    : `${sub.days_left <= 0 ? "Your trial has expired" : `${sub.days_left} days left in your trial`}`
                  }
                </p>
                <p className="text-sm text-gray-500 mt-1">
                  {isAr ? "قم بالترقية للاستمرار بدون انقطاع" : "Upgrade to continue without interruption"}
                </p>
              </div>
            )}

            {sub.expires_at && (
              <p className="text-sm text-gray-500">
                {isAr ? "ينتهي في: " : "Expires: "}
                {new Date(sub.expires_at).toLocaleDateString(isAr ? "ar-EG" : "en-US")}
              </p>
            )}
          </div>
        ) : (
          <div className="bg-blue-50 border border-blue-200 rounded-2xl p-6 mb-8">
            <p className="text-blue-700 font-medium">
              {isAr ? "لا يوجد اشتراك نشط" : "No active subscription"}
            </p>
          </div>
        )}

        {/* Upgrade Plans */}
        <h2 className="text-xl font-bold text-gray-900 mb-4">
          {isAr ? "الترقية إلى خطة مدفوعة" : "Upgrade to Paid Plan"}
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-10">
          {plans.map(plan => {
            const isCurrentPlan = sub?.plan_name === plan.name;
            return (
              <div key={plan.name} className={`bg-white rounded-2xl border-2 p-5 ${isCurrentPlan ? "border-violet-500" : "border-gray-200"}`}>
                <h3 className="font-black text-gray-900 text-lg mb-1">
                  {isAr ? plan.name_ar : plan.name_en}
                </h3>
                <p className="text-3xl font-black text-violet-700 mb-3">
                  {plan.price_egp.toLocaleString()}
                  <span className="text-sm font-normal text-gray-400">{isAr ? " ج.م/شهر" : " EGP/mo"}</span>
                </p>
                <ul className="space-y-2 mb-4">
                  {(isAr ? plan.features_ar : plan.features_en).slice(0, 3).map((f, i) => (
                    <li key={i} className="text-xs text-gray-600 flex gap-2">
                      <span className="text-green-500">✓</span>{f}
                    </li>
                  ))}
                </ul>
                {isCurrentPlan ? (
                  <div className="w-full py-2 rounded-xl text-center text-sm font-medium bg-violet-100 text-violet-700">
                    {isAr ? "خطتك الحالية" : "Current Plan"}
                  </div>
                ) : (
                  <Link
                    href={`/${locale}/pricing`}
                    className="w-full py-2 rounded-xl text-center text-sm font-medium bg-violet-700 text-white hover:bg-violet-800 transition block"
                  >
                    {isAr ? "ترقية" : "Upgrade"}
                  </Link>
                )}
              </div>
            );
          })}
        </div>

        {/* Payment Methods Info */}
        <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
          <h3 className="font-bold text-gray-900 mb-4">
            {isAr ? "طرق الدفع المتاحة" : "Payment Methods"}
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {["💳 بطاقة ائتمانية", "📱 فودافون كاش", "💰 فوري", "🏦 حوالة بنكية"].map((m, i) => (
              <div key={i} className="text-center p-3 bg-gray-50 rounded-xl text-sm text-gray-700">{m}</div>
            ))}
          </div>
          <p className="text-xs text-gray-400 mt-4">
            {isAr ? "* سيتم تفعيل بوابات الدفع قريباً" : "* Payment gateways coming soon"}
          </p>
        </div>
      </div>
    </div>
  );
}
''')

# Update landing page to add pricing section and pricing link
upload("/opt/clickbuild/frontend/src/app/[locale]/page.tsx", '''"use client";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useParams } from "next/navigation";

export default function HomePage() {
  const { locale } = useParams() as { locale: string };
  const isAr = locale === "ar";
  const t  = useTranslations();
  const th = useTranslations("hero");
  const tf = useTranslations("features");

  const features = [
    { key: "accounting", icon: "📊" },
    { key: "sales",      icon: "💼" },
    { key: "inventory",  icon: "📦" },
    { key: "hr",         icon: "👥" },
    { key: "crm",        icon: "🎯" },
    { key: "pos",        icon: "🛒" },
  ] as const;

  const PLANS = isAr ? [
    { name: "مبتدئ",  price: "299", period: "ج.م / شهر", desc: "مثالي للشركات الصغيرة", users: "10 مستخدمين", storage: "10 جيجا", popular: false },
    { name: "أعمال",  price: "699", period: "ج.م / شهر", desc: "للشركات المتنامية",     users: "50 مستخدماً", storage: "50 جيجا", popular: true },
    { name: "متقدم",  price: "1,499", period: "ج.م / شهر", desc: "للمؤسسات الكبيرة",    users: "غير محدود",   storage: "200 جيجا", popular: false },
  ] : [
    { name: "Starter",    price: "299",   period: "EGP / mo", desc: "Perfect for small biz", users: "10 users",    storage: "10 GB",  popular: false },
    { name: "Business",   price: "699",   period: "EGP / mo", desc: "For growing companies", users: "50 users",    storage: "50 GB",  popular: true },
    { name: "Enterprise", price: "1,499", period: "EGP / mo", desc: "For large enterprises", users: "Unlimited",   storage: "200 GB", popular: false },
  ];

  return (
    <main className="min-h-screen bg-white" dir={isAr ? "rtl" : "ltr"}>

      {/* ─── Nav ─────────────────────────────────────────────────────────── */}
      <nav className="sticky top-0 z-50 bg-white/80 backdrop-blur-md border-b border-gray-100">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
          <span className="text-2xl font-black text-violet-700">ClickBuild</span>
          <div className="hidden md:flex items-center gap-6 text-sm text-gray-600">
            <a href="#features" className="hover:text-gray-900 transition">{isAr ? "المميزات" : "Features"}</a>
            <Link href={`/${locale}/pricing`} className="hover:text-gray-900 transition">{isAr ? "الأسعار" : "Pricing"}</Link>
          </div>
          <div className="flex gap-3">
            <Link href={`/${locale}/login`} className="text-gray-600 hover:text-gray-900 px-4 py-2 rounded-lg transition text-sm">
              {isAr ? "تسجيل الدخول" : "Login"}
            </Link>
            <Link
              href={`/${locale}/register`}
              className="bg-violet-700 text-white px-4 py-2 rounded-lg hover:bg-violet-800 transition text-sm font-medium"
            >
              {isAr ? "ابدأ مجاناً" : "Start Free"}
            </Link>
          </div>
        </div>
      </nav>

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
          <p className="text-xl text-violet-200 max-w-2xl mx-auto mb-10">{th("subtitle")}</p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href={`/${locale}/register`}
              className="bg-white text-violet-900 font-bold px-8 py-4 rounded-xl text-lg hover:bg-violet-50 transition shadow-lg shadow-violet-900/30"
            >
              🚀 {th("cta")}
            </Link>
            <Link
              href={`/${locale}/pricing`}
              className="border border-white/30 text-white px-8 py-4 rounded-xl text-lg hover:bg-white/10 transition"
            >
              {isAr ? "عرض الأسعار" : "View Pricing"}
            </Link>
          </div>
          <p className="text-violet-300 text-sm mt-4">{th("ctaSub")}</p>

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

      {/* ─── Pricing Preview ─────────────────────────────────────────────── */}
      <section id="pricing" className="py-24 bg-white">
        <div className="max-w-6xl mx-auto px-4">
          <div className="text-center mb-12">
            <h2 className="text-4xl font-black text-gray-900 mb-4">
              {isAr ? "أسعار شفافة وبسيطة" : "Simple, Transparent Pricing"}
            </h2>
            <p className="text-gray-500 text-xl">
              {isAr ? "جميع الخطط تشمل 14 يوم تجريبي مجاني" : "All plans include a 14-day free trial"}
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            {PLANS.map((plan) => (
              <div key={plan.name} className={`relative rounded-2xl p-6 border-2 ${plan.popular ? "border-violet-500 shadow-xl" : "border-gray-200"}`}>
                {plan.popular && (
                  <span className="absolute -top-3 left-1/2 -translate-x-1/2 bg-violet-700 text-white text-xs px-3 py-1 rounded-full font-bold whitespace-nowrap">
                    {isAr ? "⭐ الأكثر شعبية" : "⭐ Most Popular"}
                  </span>
                )}
                <h3 className="font-black text-gray-900 text-xl mb-2">{plan.name}</h3>
                <p className="text-gray-500 text-sm mb-4">{plan.desc}</p>
                <div className="text-3xl font-black text-violet-700 mb-1">{plan.price}</div>
                <div className="text-gray-400 text-sm mb-4">{plan.period}</div>
                <div className="text-sm text-gray-600 space-y-1">
                  <div>👥 {plan.users}</div>
                  <div>💾 {plan.storage}</div>
                </div>
              </div>
            ))}
          </div>
          <div className="text-center">
            <Link
              href={`/${locale}/pricing`}
              className="inline-block bg-violet-700 text-white px-8 py-3 rounded-xl font-bold hover:bg-violet-800 transition"
            >
              {isAr ? "مقارنة جميع الخطط →" : "Compare All Plans →"}
            </Link>
          </div>
        </div>
      </section>

      {/* ─── How it works ────────────────────────────────────────────────── */}
      <section className="py-24 bg-gray-50">
        <div className="max-w-4xl mx-auto px-4 text-center">
          <h2 className="text-4xl font-black text-gray-900 mb-4">
            {isAr ? "كيف يعمل ClickBuild؟" : "How does ClickBuild work?"}
          </h2>
          <p className="text-gray-500 text-xl mb-16">
            {isAr ? "من التسجيل إلى نظام جاهز في أقل من دقيقة" : "From signup to a ready system in under a minute"}
          </p>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            {(isAr ? [
              { step: "١", icon: "📝", title: "سجّل حساباً", desc: "مجاناً في 30 ثانية" },
              { step: "٢", icon: "📋", title: "اختر خطتك", desc: "14 يوم تجريبي مجاني" },
              { step: "٣", icon: "⚙️", title: "خصّص نظامك", desc: "اختر الوحدات المناسبة" },
              { step: "٤", icon: "🚀", title: "ابدأ العمل",  desc: "نظامك جاهز في 30 ثانية" },
            ] : [
              { step: "1", icon: "📝", title: "Create Account", desc: "Free in 30 seconds" },
              { step: "2", icon: "📋", title: "Choose Your Plan", desc: "14-day free trial" },
              { step: "3", icon: "⚙️", title: "Customize",       desc: "Pick your modules" },
              { step: "4", icon: "🚀", title: "Start Working",   desc: "Ready in 30 seconds" },
            ]).map((s) => (
              <div key={s.step} className="flex flex-col items-center">
                <div className="w-12 h-12 rounded-full bg-violet-100 text-violet-700 flex items-center justify-center font-black text-lg mb-3">{s.step}</div>
                <div className="text-3xl mb-2">{s.icon}</div>
                <h3 className="font-bold text-gray-900 mb-1">{s.title}</h3>
                <p className="text-gray-500 text-sm">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── CTA ─────────────────────────────────────────────────────────── */}
      <section className="py-24 bg-violet-700 text-white text-center">
        <div className="max-w-2xl mx-auto px-4">
          <h2 className="text-4xl font-black mb-4">
            {isAr ? "ابدأ الآن مجاناً" : "Start For Free Today"}
          </h2>
          <p className="text-violet-200 text-xl mb-8">
            {isAr ? "14 يوم تجريبي مجاني • لا يلزم بطاقة ائتمان" : "14-day free trial • No credit card required"}
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href={`/${locale}/register`}
              className="bg-white text-violet-900 font-bold px-10 py-4 rounded-xl text-lg hover:bg-violet-50 transition inline-block"
            >
              {isAr ? "إنشاء حساب مجاني" : "Create Free Account"}
            </Link>
            <Link
              href={`/${locale}/pricing`}
              className="border border-white/30 text-white px-10 py-4 rounded-xl text-lg hover:bg-white/10 transition inline-block"
            >
              {isAr ? "عرض الأسعار" : "View Pricing"}
            </Link>
          </div>
        </div>
      </section>

      {/* ─── Footer ──────────────────────────────────────────────────────── */}
      <footer className="bg-gray-900 text-gray-400 py-12">
        <div className="max-w-6xl mx-auto px-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 mb-8">
            <div>
              <h4 className="text-white font-bold mb-3">ClickBuild</h4>
              <p className="text-sm">{isAr ? "منصة Odoo SaaS العربية" : "Arabic Odoo SaaS Platform"}</p>
            </div>
            <div>
              <h4 className="text-white font-bold mb-3">{isAr ? "المنتج" : "Product"}</h4>
              <ul className="space-y-2 text-sm">
                <li><Link href={`/${locale}/pricing`} className="hover:text-white transition">{isAr ? "الأسعار" : "Pricing"}</Link></li>
                <li><a href="#features" className="hover:text-white transition">{isAr ? "المميزات" : "Features"}</a></li>
              </ul>
            </div>
            <div>
              <h4 className="text-white font-bold mb-3">{isAr ? "الحساب" : "Account"}</h4>
              <ul className="space-y-2 text-sm">
                <li><Link href={`/${locale}/register`} className="hover:text-white transition">{isAr ? "إنشاء حساب" : "Sign Up"}</Link></li>
                <li><Link href={`/${locale}/login`} className="hover:text-white transition">{isAr ? "تسجيل الدخول" : "Login"}</Link></li>
              </ul>
            </div>
            <div>
              <h4 className="text-white font-bold mb-3">{isAr ? "تواصل" : "Contact"}</h4>
              <p className="text-sm">support@clickbuild.com</p>
            </div>
          </div>
          <div className="border-t border-gray-800 pt-8 text-center text-sm">
            © 2024 ClickBuild. {isAr ? "جميع الحقوق محفوظة" : "All rights reserved."}
          </div>
        </div>
      </footer>

    </main>
  );
}
''')

# Update dashboard to add billing link
print("\n  Updating dashboard nav link...")
rp("grep -n 'billing\\|فوترة' /opt/clickbuild/frontend/src/app/\\[locale\\]/dashboard/page.tsx | head -5", "CHECK")

# Check layout for nav update
print("\n  Checking layout...")
rp("cat /opt/clickbuild/frontend/src/app/\\[locale\\]/layout.tsx", "LAYOUT")

# ─────────────────────────────────────────────────────────────
# STEP 7: Restart services
# ─────────────────────────────────────────────────────────────
print("\n[7/7] Restart services...")
rp("cd /opt/clickbuild/backend && systemctl restart clickbuild-api", "API_RESTART", timeout=20)
time.sleep(3)
rp("systemctl is-active clickbuild-api", "API_STATUS")
rp("cd /opt/clickbuild/backend && systemctl is-active clickbuild-api && journalctl -u clickbuild-api --no-pager -n 5 2>&1", "API_LOGS", timeout=15)

print("\n  Rebuilding frontend...")
rp("cd /opt/clickbuild/frontend && pm2 restart clickbuild-frontend", "FRONTEND_RESTART", timeout=30)
time.sleep(5)
rp("pm2 list | grep clickbuild-frontend", "FRONTEND_STATUS")

# Verify plans seeded
rp("PGPASSWORD='CB_pg_S3cur3_2024!' psql -h localhost -U clickbuild -d clickbuild_platform -c 'SELECT name, name_ar, price_egp FROM plans ORDER BY price_egp' 2>&1", "PLANS", timeout=10)

# Test API
rp("curl -s http://127.0.0.1:8000/api/v1/plans/ 2>&1 | head -200", "TEST_PLANS_API", timeout=15)

print("\n" + "=" * 60)
print("✅ Customer Journey deployed!")
print("=" * 60)
print("""
Journey:
  / (Landing)      → Features + Pricing preview + CTA
  /pricing         → Plan cards (Starter/Business/Enterprise)
  /register        → Registration (existing)
  /onboarding      → Industry → Subdomain → Modules → Create
  /dashboard       → Live instance status + manage
  /billing         → Current subscription + upgrade plans

Backend:
  GET  /api/v1/plans/         → All active plans
  GET  /api/v1/subscriptions/me → User's current subscription
  POST /api/v1/subscriptions/upgrade → Plan upgrade request
""")

sftp.close()
client.close()
