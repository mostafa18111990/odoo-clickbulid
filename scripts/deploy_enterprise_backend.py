#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Enterprise Platform Backend Deployment."""
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

def run(client, cmd, timeout=120):
    print(f"\n$ {cmd[:100]}")
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if out: print(out)
    if err and 'WARNING' not in err and not out: print(f"[err] {err[:300]}")
    return out, err

def upload(client, path, content):
    sftp = client.open_sftp()
    with sftp.open(path, 'w') as f:
        f.write(content)
    sftp.close()
    print(f"  -> {path}")

def section(t):
    print(f"\n{'='*60}\n  {t}\n{'='*60}")

# ==============================================================================
# FILES
# ==============================================================================

SQL = r"""
CREATE TABLE IF NOT EXISTS audit_logs (
    id            BIGSERIAL PRIMARY KEY,
    tenant_id     UUID,
    user_id       UUID,
    session_id    TEXT,
    action        TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id   TEXT,
    endpoint      TEXT,
    method        TEXT,
    ip_address    INET,
    user_agent    TEXT,
    request_body  JSONB,
    response_code INT,
    duration_ms   INT,
    outcome       TEXT DEFAULT 'SUCCESS',
    risk_level    TEXT DEFAULT 'LOW',
    metadata      JSONB DEFAULT '{}',
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_tenant ON audit_logs(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_risk ON audit_logs(risk_level) WHERE risk_level IN ('HIGH','CRITICAL');

CREATE TABLE IF NOT EXISTS compliance_checks (
    id            SERIAL PRIMARY KEY,
    framework     TEXT NOT NULL,
    control_id    TEXT NOT NULL,
    control_name  TEXT NOT NULL,
    status        TEXT DEFAULT 'PENDING',
    evidence      TEXT,
    automated     BOOLEAN DEFAULT false,
    last_checked  TIMESTAMPTZ,
    next_review   TIMESTAMPTZ,
    owner         TEXT,
    notes         TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(framework, control_id)
);

CREATE TABLE IF NOT EXISTS data_retention_policies (
    id            SERIAL PRIMARY KEY,
    table_name    TEXT NOT NULL UNIQUE,
    retention_days INT NOT NULL,
    legal_basis   TEXT,
    classification TEXT DEFAULT 'INTERNAL',
    auto_delete   BOOLEAN DEFAULT false,
    last_purge    TIMESTAMPTZ,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS slo_definitions (
    id            SERIAL PRIMARY KEY,
    service_name  TEXT NOT NULL,
    slo_name      TEXT NOT NULL,
    description   TEXT,
    sli_type      TEXT NOT NULL,
    target_pct    NUMERIC(5,2) NOT NULL,
    window_days   INT DEFAULT 30,
    owner_team    TEXT,
    alert_pct     NUMERIC(5,2),
    is_active     BOOLEAN DEFAULT true,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(service_name, slo_name)
);

CREATE TABLE IF NOT EXISTS slo_measurements (
    id            BIGSERIAL PRIMARY KEY,
    slo_id        INT REFERENCES slo_definitions(id),
    tenant_id     UUID,
    measured_at   TIMESTAMPTZ DEFAULT NOW(),
    good_events   BIGINT DEFAULT 0,
    total_events  BIGINT DEFAULT 0,
    latency_p50   NUMERIC(10,2),
    latency_p95   NUMERIC(10,2),
    latency_p99   NUMERIC(10,2),
    error_rate    NUMERIC(5,4),
    availability  NUMERIC(5,4),
    error_budget_remaining NUMERIC(5,4),
    status        TEXT DEFAULT 'OK'
);
CREATE INDEX IF NOT EXISTS idx_slo_meas_slo ON slo_measurements(slo_id, measured_at DESC);

CREATE TABLE IF NOT EXISTS incidents (
    id            SERIAL PRIMARY KEY,
    incident_id   TEXT UNIQUE NOT NULL,
    title         TEXT NOT NULL,
    description   TEXT,
    severity      TEXT NOT NULL,
    status        TEXT DEFAULT 'OPEN',
    tenant_ids    TEXT[],
    service_names TEXT[],
    detected_at   TIMESTAMPTZ DEFAULT NOW(),
    acknowledged_at TIMESTAMPTZ,
    mitigated_at  TIMESTAMPTZ,
    resolved_at   TIMESTAMPTZ,
    closed_at     TIMESTAMPTZ,
    oncall_engineer TEXT,
    incident_lead TEXT,
    root_cause    TEXT,
    impact_summary TEXT,
    timeline      JSONB DEFAULT '[]',
    metrics       JSONB DEFAULT '{}',
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS postmortems (
    id            SERIAL PRIMARY KEY,
    incident_id   INT REFERENCES incidents(id),
    status        TEXT DEFAULT 'DRAFT',
    summary       TEXT,
    timeline      TEXT,
    root_cause    TEXT,
    contributing_factors TEXT,
    impact        TEXT,
    action_items  JSONB DEFAULT '[]',
    lessons_learned TEXT,
    author        TEXT,
    reviewers     TEXT[],
    published_at  TIMESTAMPTZ,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS runbooks (
    id            SERIAL PRIMARY KEY,
    slug          TEXT UNIQUE NOT NULL,
    title         TEXT NOT NULL,
    service       TEXT,
    category      TEXT,
    severity      TEXT,
    content       TEXT NOT NULL,
    automated     BOOLEAN DEFAULT false,
    automation_script TEXT,
    last_tested   TIMESTAMPTZ,
    owner_team    TEXT,
    version       INT DEFAULT 1,
    is_active     BOOLEAN DEFAULT true,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tenant_health_scores (
    id            BIGSERIAL PRIMARY KEY,
    tenant_id     TEXT NOT NULL,
    subdomain     TEXT NOT NULL,
    measured_at   TIMESTAMPTZ DEFAULT NOW(),
    availability_score  NUMERIC(5,2),
    performance_score   NUMERIC(5,2),
    security_score      NUMERIC(5,2),
    compliance_score    NUMERIC(5,2),
    overall_score       NUMERIC(5,2),
    container_status    TEXT,
    http_response_ms    INT,
    db_query_ms         INT,
    memory_usage_pct    NUMERIC(5,2),
    cpu_usage_pct       NUMERIC(5,2),
    disk_usage_pct      NUMERIC(5,2),
    last_error          TEXT,
    details             JSONB DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_health_tenant ON tenant_health_scores(subdomain, measured_at DESC);

CREATE TABLE IF NOT EXISTS support_tickets (
    id            SERIAL PRIMARY KEY,
    ticket_id     TEXT UNIQUE NOT NULL,
    tenant_id     TEXT,
    user_id       TEXT,
    subject       TEXT NOT NULL,
    description   TEXT NOT NULL,
    category      TEXT,
    priority      TEXT DEFAULT 'MEDIUM',
    tier          TEXT DEFAULT 'L1',
    status        TEXT DEFAULT 'OPEN',
    sla_deadline  TIMESTAMPTZ,
    sla_breached  BOOLEAN DEFAULT false,
    assigned_to   TEXT,
    tags          TEXT[],
    incident_id   INT REFERENCES incidents(id),
    plan_tier     TEXT,
    metadata      JSONB DEFAULT '{}',
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW(),
    resolved_at   TIMESTAMPTZ,
    csat_score    INT
);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON support_tickets(status, priority);

CREATE TABLE IF NOT EXISTS ticket_messages (
    id            SERIAL PRIMARY KEY,
    ticket_id     INT REFERENCES support_tickets(id),
    author_type   TEXT NOT NULL,
    author_id     TEXT,
    author_name   TEXT,
    content       TEXT NOT NULL,
    is_internal   BOOLEAN DEFAULT false,
    attachments   JSONB DEFAULT '[]',
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sla_policies (
    id            SERIAL PRIMARY KEY,
    plan_tier     TEXT NOT NULL UNIQUE,
    priority_name TEXT NOT NULL,
    first_response_hours  INT NOT NULL,
    resolution_hours      INT NOT NULL,
    escalation_hours      INT NOT NULL,
    business_hours_only   BOOLEAN DEFAULT false,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO sla_policies (plan_tier, priority_name, first_response_hours, resolution_hours, escalation_hours)
VALUES
    ('trial',      'MEDIUM', 72,  168, 240),
    ('starter',    'MEDIUM', 24,  72,  120),
    ('business',   'HIGH',   8,   24,  48),
    ('enterprise', 'CRITICAL',1,  4,   8)
ON CONFLICT (plan_tier) DO NOTHING;

CREATE TABLE IF NOT EXISTS contractor_profiles (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    national_id   TEXT UNIQUE,
    full_name_ar  TEXT,
    full_name_en  TEXT,
    company_name  TEXT,
    cr_number     TEXT,
    vat_number    TEXT,
    email         TEXT,
    phone         TEXT,
    address       JSONB,
    specializations TEXT[],
    certifications TEXT[],
    compliance_score     NUMERIC(5,2) DEFAULT 0,
    performance_score    NUMERIC(5,2) DEFAULT 0,
    reputation_score     NUMERIC(5,2) DEFAULT 0,
    overall_score        NUMERIC(5,2) DEFAULT 0,
    verified      BOOLEAN DEFAULT false,
    kyc_status    TEXT DEFAULT 'PENDING',
    is_active     BOOLEAN DEFAULT true,
    metadata      JSONB DEFAULT '{}',
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS price_intelligence (
    id            BIGSERIAL PRIMARY KEY,
    item_code     TEXT NOT NULL,
    item_name     TEXT NOT NULL,
    category      TEXT,
    unit          TEXT,
    region        TEXT DEFAULT 'SA',
    price_min     NUMERIC(12,2),
    price_max     NUMERIC(12,2),
    price_avg     NUMERIC(12,2),
    price_median  NUMERIC(12,2),
    currency      TEXT DEFAULT 'SAR',
    sample_count  INT DEFAULT 0,
    source        TEXT,
    measured_at   TIMESTAMPTZ DEFAULT NOW(),
    valid_until   TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS vendor_scorecards (
    id            SERIAL PRIMARY KEY,
    contractor_id UUID REFERENCES contractor_profiles(id),
    tenant_id     TEXT,
    evaluation_date TIMESTAMPTZ DEFAULT NOW(),
    quality_score    NUMERIC(5,2),
    delivery_score   NUMERIC(5,2),
    price_score      NUMERIC(5,2),
    compliance_score NUMERIC(5,2),
    overall_score    NUMERIC(5,2),
    contract_value   NUMERIC(15,2),
    on_time_rate     NUMERIC(5,2),
    defect_rate      NUMERIC(5,2),
    notes            TEXT
);

CREATE TABLE IF NOT EXISTS tenant_encryption_keys (
    id            SERIAL PRIMARY KEY,
    tenant_id     TEXT NOT NULL,
    key_alias     TEXT NOT NULL,
    key_version   INT DEFAULT 1,
    encrypted_key TEXT NOT NULL,
    algorithm     TEXT DEFAULT 'AES-256-GCM',
    purpose       TEXT DEFAULT 'DATA',
    is_active     BOOLEAN DEFAULT true,
    rotated_at    TIMESTAMPTZ,
    expires_at    TIMESTAMPTZ,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, key_alias, key_version)
);

CREATE TABLE IF NOT EXISTS ai_audit_logs (
    id            BIGSERIAL PRIMARY KEY,
    tenant_id     TEXT,
    user_id       TEXT,
    model_name    TEXT NOT NULL,
    model_version TEXT,
    prompt_hash   TEXT,
    action_type   TEXT NOT NULL,
    input_tokens  INT,
    output_tokens INT,
    latency_ms    INT,
    outcome       TEXT,
    confidence    NUMERIC(5,4),
    human_reviewed BOOLEAN DEFAULT false,
    human_approved BOOLEAN,
    policy_checks JSONB DEFAULT '[]',
    flagged       BOOLEAN DEFAULT false,
    flag_reason   TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS change_requests (
    id            SERIAL PRIMARY KEY,
    change_id     TEXT UNIQUE NOT NULL,
    title         TEXT NOT NULL,
    description   TEXT,
    change_type   TEXT,
    risk_level    TEXT DEFAULT 'MEDIUM',
    status        TEXT DEFAULT 'DRAFT',
    requester     TEXT,
    approvers     TEXT[],
    approved_by   TEXT[],
    scheduled_at  TIMESTAMPTZ,
    deployed_at   TIMESTAMPTZ,
    rollback_plan TEXT,
    test_plan     TEXT,
    services_affected TEXT[],
    deployment_notes  TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS system_metrics (
    id            BIGSERIAL PRIMARY KEY,
    metric_name   TEXT NOT NULL,
    service       TEXT,
    tenant_id     TEXT,
    value         NUMERIC(15,4) NOT NULL,
    unit          TEXT,
    tags          JSONB DEFAULT '{}',
    measured_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_metrics_name ON system_metrics(metric_name, measured_at DESC);

-- SLO Seed Data
INSERT INTO slo_definitions (service_name, slo_name, description, sli_type, target_pct, window_days, owner_team, alert_pct)
VALUES
    ('api',      'api_availability',      'FastAPI uptime',           'availability', 99.9, 30, 'platform', 20.0),
    ('api',      'api_latency_p95',       'API p95 < 500ms',          'latency',      99.0, 30, 'platform', 30.0),
    ('frontend', 'frontend_availability', 'Next.js uptime',           'availability', 99.9, 30, 'platform', 20.0),
    ('odoo',     'instance_availability', 'Odoo tenant uptime',       'availability', 99.5, 30, 'sre',      25.0),
    ('odoo',     'provision_success',     'Instance provisioning',    'availability', 99.0, 30, 'sre',      30.0),
    ('database', 'db_availability',       'PostgreSQL uptime',        'availability', 99.99,30, 'platform', 10.0),
    ('billing',  'payment_success',       'Payment processing',       'availability', 99.5, 30, 'billing',  25.0)
ON CONFLICT (service_name, slo_name) DO NOTHING;

-- Compliance Controls
INSERT INTO compliance_checks (framework, control_id, control_name, status, automated, owner)
VALUES
    ('SOC2', 'CC6.1', 'Logical Access - Authentication',       'PASS',    true,  'security'),
    ('SOC2', 'CC6.2', 'Logical Access - Authorization',        'PARTIAL', true,  'security'),
    ('SOC2', 'CC7.1', 'System Operations - Capacity',          'PENDING', false, 'platform'),
    ('SOC2', 'CC7.3', 'System Operations - Incident Mgmt',     'PARTIAL', false, 'sre'),
    ('SOC2', 'CC8.1', 'Change Management - Authorization',     'PARTIAL', false, 'engineering'),
    ('GDPR', 'ART5',  'Personal Data Processing Principles',   'PARTIAL', false, 'legal'),
    ('GDPR', 'ART17', 'Right to Erasure',                      'PENDING', true,  'engineering'),
    ('GDPR', 'ART32', 'Security of Processing - Encryption',   'PASS',    true,  'security'),
    ('GDPR', 'ART33', 'Breach Notification 72hr',              'PARTIAL', false, 'sre'),
    ('PDPL', 'ART4',  'Lawfulness of Processing',              'PARTIAL', false, 'legal'),
    ('PDPL', 'ART7',  'Data Localization - Saudi',             'PENDING', false, 'infrastructure'),
    ('PDPL', 'ART18', 'Individual Rights - Access',            'PENDING', false, 'engineering'),
    ('ISO27001', 'A.9.1',  'Access Control Policy',            'PASS',    true,  'security'),
    ('ISO27001', 'A.10.1', 'Cryptography - Encryption at Rest','PARTIAL', true,  'security'),
    ('ISO27001', 'A.12.4', 'Logging and Monitoring',           'PARTIAL', true,  'platform'),
    ('ISO27001', 'A.16.1', 'Incident Management',              'PARTIAL', false, 'sre'),
    ('ISO27001', 'A.17.1', 'Business Continuity',              'PENDING', false, 'sre')
ON CONFLICT (framework, control_id) DO NOTHING;

INSERT INTO data_retention_policies (table_name, retention_days, legal_basis, classification, auto_delete)
VALUES
    ('audit_logs',       2555, 'SOC2/Legal',     'CONFIDENTIAL', false),
    ('system_metrics',    365, 'Operational',    'INTERNAL',     true),
    ('slo_measurements',  730, 'SRE baseline',   'INTERNAL',     true),
    ('support_tickets',  1825, 'Customer contract','CONFIDENTIAL',false),
    ('ai_audit_logs',     730, 'AI governance',  'CONFIDENTIAL', false),
    ('incidents',        2555, 'SOC2/Legal',     'INTERNAL',     false),
    ('postmortems',      2555, 'Engineering',    'INTERNAL',     false)
ON CONFLICT (table_name) DO NOTHING;

INSERT INTO runbooks (slug, title, service, category, severity, content, owner_team)
VALUES (
    'odoo-instance-unhealthy',
    'Odoo Instance Unhealthy',
    'odoo', 'incident', 'SEV2',
    '# Runbook: Odoo Instance Unhealthy

## Detection
Health check returns non-2xx for 3+ consecutive checks.

## Triage Steps
1. docker inspect odoo_{subdomain} --format "{{.State.Status}}"
2. docker logs odoo_{subdomain} --tail 50
3. Check sessions: docker exec -u root odoo_{subdomain} ls -la /var/lib/odoo/

## Fix: Sessions Permission Error
```bash
docker exec -u root odoo_{subdomain} mkdir -p /var/lib/odoo/sessions
docker exec -u root odoo_{subdomain} chown -R odoo:odoo /var/lib/odoo
docker restart odoo_{subdomain}
```

## Escalation
If not resolved in 30min -> SEV1',
    'sre'
),
(
    'api-high-error-rate',
    'FastAPI High Error Rate',
    'api', 'incident', 'SEV2',
    '# Runbook: API High Error Rate

## Detection
Error rate > 5% over 5-minute window.

## Triage
1. systemctl status clickbuild-api
2. journalctl -u clickbuild-api -n 100
3. redis-cli ping

## Fix
systemctl restart clickbuild-api

## Escalation
SEV1 if > 20% error rate or > 10min.',
    'sre'
),
(
    'db-connection-pool-exhausted',
    'Database Connection Pool Exhausted',
    'database', 'incident', 'SEV1',
    '# Runbook: DB Pool Exhausted

## Detection
SQLAlchemy pool timeout errors.

## Triage
SELECT count(*), state FROM pg_stat_activity GROUP BY state;

## Fix
SELECT pg_terminate_backend(pid) FROM pg_stat_activity
WHERE state = ''idle'' AND query_start < NOW() - interval ''10 minutes'';

## Prevention
Install PgBouncer.',
    'sre'
)
ON CONFLICT (slug) DO NOTHING;
"""

SRE_PY = '''"""SRE Service - SLO tracking, incident management, tenant health."""
import time, logging
import httpx
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)
UTC = timezone.utc


async def measure_tenant_health(subdomain: str, port: int) -> dict:
    result = {
        'subdomain': subdomain, 'availability_score': 0.0,
        'performance_score': 0.0, 'overall_score': 0.0,
        'container_status': 'unknown', 'http_response_ms': None, 'last_error': None,
    }
    try:
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=5.0) as cli:
            resp = await cli.get(f"http://127.0.0.1:{port}/web/health")
        ms = int((time.monotonic() - start) * 1000)
        result['http_response_ms'] = ms
        if resp.status_code < 400:
            result['availability_score'] = 100.0
            result['performance_score'] = max(0, 100 - (ms / 10))
            result['container_status'] = 'healthy'
        else:
            result['last_error'] = f"HTTP {resp.status_code}"
            result['container_status'] = 'unhealthy'
    except httpx.ConnectError:
        result['last_error'] = 'Connection refused'
        result['container_status'] = 'down'
    except Exception as e:
        result['last_error'] = str(e)[:200]

    result['overall_score'] = (result['availability_score'] * 0.6 +
                               result['performance_score'] * 0.4)
    return result


async def store_health_score(db: AsyncSession, tenant_id: str, health: dict):
    await db.execute(text("""
        INSERT INTO tenant_health_scores
            (tenant_id, subdomain, availability_score, performance_score,
             overall_score, container_status, http_response_ms, last_error)
        VALUES (:tenant_id, :subdomain, :availability_score, :performance_score,
                :overall_score, :container_status, :http_response_ms, :last_error)
    """), {
        'tenant_id': tenant_id, 'subdomain': health['subdomain'],
        'availability_score': health['availability_score'],
        'performance_score': health['performance_score'],
        'overall_score': health['overall_score'],
        'container_status': health['container_status'],
        'http_response_ms': health['http_response_ms'],
        'last_error': health['last_error'],
    })
    await db.commit()


async def open_incident(db: AsyncSession, title: str, severity: str,
                        description: str, services: list, tenants: list = None) -> str:
    year = datetime.now().year
    row = await db.execute(
        text("SELECT COUNT(*)+1 AS n FROM incidents WHERE EXTRACT(YEAR FROM created_at)=:y"),
        {'y': year}
    )
    n = row.scalar_one()
    incident_id = f"INC-{year}-{n:04d}"
    await db.execute(text("""
        INSERT INTO incidents (incident_id, title, description, severity, status,
                              service_names, tenant_ids, oncall_engineer)
        VALUES (:iid, :title, :desc, :sev, 'OPEN', :services, :tenants, 'on-call')
    """), {
        'iid': incident_id, 'title': title, 'desc': description,
        'sev': severity, 'services': services, 'tenants': tenants or [],
    })
    await db.commit()
    logger.warning(f"INCIDENT OPENED: {incident_id} - {severity} - {title}")
    return incident_id
'''

SUPPORT_PY = '''"""Enterprise Support System - L1/L2/L3 ticket routing with SLA."""
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)
UTC = timezone.utc

SLA_HOURS = {
    'enterprise': {'CRITICAL': 1,  'HIGH': 4,  'MEDIUM': 8,  'LOW': 24},
    'business':   {'CRITICAL': 4,  'HIGH': 8,  'MEDIUM': 24, 'LOW': 72},
    'starter':    {'CRITICAL': 8,  'HIGH': 24, 'MEDIUM': 72, 'LOW': 168},
    'trial':      {'CRITICAL': 24, 'HIGH': 72, 'MEDIUM': 168, 'LOW': 336},
}

TIER_ROUTING = {
    'billing': 'L1', 'account': 'L1', 'general': 'L1',
    'technical': 'L2', 'integration': 'L2', 'performance': 'L2', 'bug': 'L2',
    'security': 'L3', 'compliance': 'L3', 'enterprise': 'L3', 'data': 'L3',
}


def _route_tier(category: str, plan_tier: str) -> str:
    base = TIER_ROUTING.get(category, 'L1')
    if plan_tier == 'enterprise' and base == 'L1':
        return 'L2'
    return base


def _sla_deadline(plan_tier: str, priority: str) -> datetime:
    hours = SLA_HOURS.get(plan_tier, SLA_HOURS['trial']).get(priority, 168)
    return datetime.now(UTC) + timedelta(hours=hours)


async def create_ticket(db: AsyncSession, data: dict) -> dict:
    year = datetime.now().year
    row = await db.execute(
        text("SELECT COUNT(*)+1 AS n FROM support_tickets WHERE EXTRACT(YEAR FROM created_at)=:y"),
        {'y': year}
    )
    n = row.scalar_one()
    ticket_id = f"TKT-{year}-{n:05d}"

    plan_tier = data.get('plan_tier', 'starter')
    priority  = data.get('priority', 'MEDIUM')
    category  = data.get('category', 'general')
    tier      = _route_tier(category, plan_tier)
    sla_dl    = _sla_deadline(plan_tier, priority)

    await db.execute(text("""
        INSERT INTO support_tickets
            (ticket_id, tenant_id, user_id, subject, description,
             category, priority, tier, sla_deadline, plan_tier, metadata)
        VALUES (:ticket_id, :tenant_id, :user_id, :subject, :description,
                :category, :priority, :tier, :sla_deadline, :plan_tier, \'{}\'::jsonb)
    """), {
        'ticket_id': ticket_id, 'tenant_id': data.get('tenant_id'),
        'user_id': data.get('user_id'), 'subject': data['subject'],
        'description': data['description'], 'category': category,
        'priority': priority, 'tier': tier, 'sla_deadline': sla_dl,
        'plan_tier': plan_tier,
    })

    row2 = await db.execute(
        text("SELECT id FROM support_tickets WHERE ticket_id=:tid"),
        {'tid': ticket_id}
    )
    tid = row2.scalar_one()
    await db.execute(text("""
        INSERT INTO ticket_messages (ticket_id, author_type, author_name, content)
        VALUES (:tid, 'system', 'ClickBuild Support', :msg)
    """), {
        'tid': tid,
        'msg': f"Ticket {ticket_id} created. Tier: {tier} | Priority: {priority} | SLA: {sla_dl.strftime('%Y-%m-%d %H:%M UTC')}",
    })
    await db.commit()
    return {'ticket_id': ticket_id, 'tier': tier, 'sla_deadline': sla_dl.isoformat()}
'''

AUDIT_PY = '''"""Audit Log Middleware - Compliance-by-Design."""
import time, logging, asyncio
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)

HIGH_RISK = {'/api/v1/instances', '/api/v1/admin', '/api/v1/payments'}
CRITICAL_RISK = {'/api/v1/admin/users/delete', '/api/v1/instances/delete'}


def _risk(method: str, path: str) -> str:
    if any(path.startswith(e) for e in CRITICAL_RISK): return 'CRITICAL'
    if method in ('DELETE', 'PUT') or any(path.startswith(e) for e in HIGH_RISK): return 'HIGH'
    if method == 'POST': return 'MEDIUM'
    return 'LOW'


def _resource(path: str):
    parts = [p for p in path.strip('/').split('/') if p]
    if len(parts) >= 3 and parts[0] == 'api':
        return parts[2] if len(parts) > 2 else 'unknown', parts[3] if len(parts) > 3 else None
    return 'unknown', None


class AuditLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if path in ('/health', '/favicon.ico') or path.startswith('/docs') or path.startswith('/openapi'):
            return await call_next(request)

        start = time.monotonic()
        response = await call_next(request)
        duration_ms = int((time.monotonic() - start) * 1000)

        try:
            resource_type, resource_id = _resource(path)
            risk_level = _risk(request.method, path)
            outcome = 'SUCCESS' if response.status_code < 400 else 'FAILURE'
            ip = request.client.host if request.client else None
            tenant_id = request.headers.get('X-Tenant-ID')
            user_id   = request.headers.get('X-User-ID')

            entry = {
                'tenant_id': tenant_id, 'user_id': user_id,
                'action': request.method, 'resource_type': resource_type,
                'resource_id': resource_id, 'endpoint': path[:200],
                'method': request.method, 'ip_address': ip,
                'user_agent': request.headers.get('user-agent', '')[:200],
                'response_code': response.status_code,
                'duration_ms': duration_ms, 'outcome': outcome, 'risk_level': risk_level,
            }

            from app.core.database import async_engine
            from sqlalchemy import text

            async def _write():
                try:
                    async with async_engine.begin() as conn:
                        await conn.execute(text("""
                            INSERT INTO audit_logs
                                (tenant_id, user_id, action, resource_type, resource_id,
                                 endpoint, method, ip_address, user_agent,
                                 response_code, duration_ms, outcome, risk_level)
                            VALUES
                                (:tenant_id, :user_id, :action, :resource_type, :resource_id,
                                 :endpoint, :method, :ip_address::inet, :user_agent,
                                 :response_code, :duration_ms, :outcome, :risk_level)
                        """), entry)
                except Exception as e:
                    logger.warning(f"Audit write failed: {e}")

            asyncio.create_task(_write())
        except Exception as e:
            logger.warning(f"Audit middleware error: {e}")

        return response
'''

SRE_EP = '''"""SRE API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional
from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/v1/sre", tags=["SRE"])


@router.get("/health/tenants")
async def tenants_health(db: AsyncSession = Depends(get_db),
                         u: User = Depends(get_current_user)):
    if not u.is_superuser: raise HTTPException(403, "Admin only")
    r = await db.execute(text("""
        SELECT DISTINCT ON (subdomain)
            subdomain, overall_score, availability_score, performance_score,
            container_status, http_response_ms, last_error, measured_at
        FROM tenant_health_scores ORDER BY subdomain, measured_at DESC
    """))
    return {"tenants": [dict(row._mapping) for row in r.fetchall()]}


@router.get("/slos")
async def list_slos(db: AsyncSession = Depends(get_db), u: User = Depends(get_current_user)):
    if not u.is_superuser: raise HTTPException(403, "Admin only")
    r = await db.execute(text("""
        SELECT d.service_name, d.slo_name, d.target_pct, d.window_days,
               m.availability, m.error_budget_remaining, m.status, m.measured_at
        FROM slo_definitions d
        LEFT JOIN LATERAL (
            SELECT availability, error_budget_remaining, status, measured_at
            FROM slo_measurements WHERE slo_id = d.id
            ORDER BY measured_at DESC LIMIT 1
        ) m ON true
        WHERE d.is_active = true ORDER BY d.service_name, d.slo_name
    """))
    return {"slos": [dict(row._mapping) for row in r.fetchall()]}


@router.get("/incidents")
async def list_incidents(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    u: User = Depends(get_current_user)
):
    if not u.is_superuser: raise HTTPException(403, "Admin only")
    conditions, params = ["1=1"], {'limit': limit}
    if status:   conditions.append("status = :status");   params['status'] = status
    if severity: conditions.append("severity = :severity"); params['severity'] = severity
    r = await db.execute(text(f"""
        SELECT incident_id, title, severity, status, service_names,
               detected_at, mitigated_at, resolved_at, oncall_engineer, impact_summary
        FROM incidents WHERE {" AND ".join(conditions)}
        ORDER BY detected_at DESC LIMIT :limit
    """), params)
    return {"incidents": [dict(row._mapping) for row in r.fetchall()]}


@router.post("/incidents")
async def create_incident(data: dict, db: AsyncSession = Depends(get_db),
                          u: User = Depends(get_current_user)):
    if not u.is_superuser: raise HTTPException(403, "Admin only")
    from app.services.sre import open_incident
    iid = await open_incident(db, data['title'], data.get('severity','SEV3'),
                              data.get('description',''), data.get('services',[]))
    return {"incident_id": iid}


@router.patch("/incidents/{incident_id}")
async def update_incident(incident_id: str, data: dict,
                          db: AsyncSession = Depends(get_db),
                          u: User = Depends(get_current_user)):
    if not u.is_superuser: raise HTTPException(403, "Admin only")
    allowed = {'status','root_cause','impact_summary','oncall_engineer'}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates: raise HTTPException(400, "No valid fields")
    set_clause = ", ".join(f"{k}=:{k}" for k in updates)
    updates['iid'] = incident_id
    import datetime; updates['now'] = datetime.datetime.utcnow()
    await db.execute(text(f"UPDATE incidents SET {set_clause}, updated_at=:now WHERE incident_id=:iid"), updates)
    await db.commit()
    return {"ok": True}


@router.get("/runbooks")
async def list_runbooks(service: Optional[str] = None,
                        db: AsyncSession = Depends(get_db),
                        u: User = Depends(get_current_user)):
    if not u.is_superuser: raise HTTPException(403, "Admin only")
    conditions, params = ["is_active = true"], {}
    if service: conditions.append("service = :service"); params['service'] = service
    r = await db.execute(text(f"""
        SELECT slug, title, service, category, severity, owner_team, last_tested
        FROM runbooks WHERE {" AND ".join(conditions)}
        ORDER BY service, slug
    """), params)
    return {"runbooks": [dict(row._mapping) for row in r.fetchall()]}


@router.get("/runbooks/{slug}")
async def get_runbook(slug: str, db: AsyncSession = Depends(get_db),
                      u: User = Depends(get_current_user)):
    if not u.is_superuser: raise HTTPException(403, "Admin only")
    r = await db.execute(text("SELECT * FROM runbooks WHERE slug=:s AND is_active=true"), {'s': slug})
    row = r.fetchone()
    if not row: raise HTTPException(404, "Not found")
    return dict(row._mapping)
'''

SUPPORT_EP = '''"""Support Ticket API."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional
from pydantic import BaseModel
from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.services.support import create_ticket

router = APIRouter(prefix="/api/v1/support", tags=["Support"])


class TicketCreate(BaseModel):
    subject: str
    description: str
    category: str = "general"
    priority: str = "MEDIUM"


@router.post("/tickets")
async def open_ticket(body: TicketCreate, db: AsyncSession = Depends(get_db),
                      u: User = Depends(get_current_user)):
    r = await db.execute(text("""
        SELECT p.name FROM subscriptions s JOIN plans p ON p.id=s.plan_id
        WHERE s.user_id=:uid AND s.status='active'
        ORDER BY s.created_at DESC LIMIT 1
    """), {'uid': str(u.id)})
    sub = r.fetchone()
    plan_tier = sub[0].lower() if sub else 'trial'
    return await create_ticket(db, {
        'user_id': str(u.id), 'subject': body.subject,
        'description': body.description, 'category': body.category,
        'priority': body.priority, 'plan_tier': plan_tier,
    })


@router.get("/tickets")
async def my_tickets(status: Optional[str] = None,
                     db: AsyncSession = Depends(get_db),
                     u: User = Depends(get_current_user)):
    cond, params = ["user_id = :uid"], {'uid': str(u.id)}
    if status: cond.append("status = :status"); params['status'] = status
    r = await db.execute(text(f"""
        SELECT ticket_id, subject, category, priority, tier, status,
               sla_deadline, sla_breached, created_at
        FROM support_tickets WHERE {" AND ".join(cond)}
        ORDER BY created_at DESC LIMIT 50
    """), params)
    return {"tickets": [dict(row._mapping) for row in r.fetchall()]}


@router.post("/tickets/{ticket_id}/reply")
async def reply_ticket(ticket_id: str, data: dict,
                       db: AsyncSession = Depends(get_db),
                       u: User = Depends(get_current_user)):
    r = await db.execute(text("SELECT id FROM support_tickets WHERE ticket_id=:tid"), {'tid': ticket_id})
    t = r.fetchone()
    if not t: raise HTTPException(404, "Not found")
    await db.execute(text("""
        INSERT INTO ticket_messages (ticket_id, author_type, author_id, author_name, content)
        VALUES (:tid, 'customer', :uid, :name, :content)
    """), {'tid': t.id, 'uid': str(u.id), 'name': u.email, 'content': data['content']})
    await db.execute(text("UPDATE support_tickets SET status='WAITING_AGENT', updated_at=NOW() WHERE id=:tid"), {'tid': t.id})
    await db.commit()
    return {"ok": True}


@router.get("/admin/tickets")
async def admin_tickets(status: Optional[str] = None,
                        priority: Optional[str] = None,
                        tier: Optional[str] = None,
                        limit: int = Query(100, le=500),
                        db: AsyncSession = Depends(get_db),
                        u: User = Depends(get_current_user)):
    if not u.is_superuser: raise HTTPException(403, "Admin only")
    cond, params = ["1=1"], {'limit': limit}
    for field, val in [('status', status), ('priority', priority), ('tier', tier)]:
        if val: cond.append(f"{field} = :{field}"); params[field] = val
    r = await db.execute(text(f"""
        SELECT ticket_id, subject, category, priority, tier, status, plan_tier,
               sla_deadline, sla_breached, assigned_to, created_at, updated_at,
               CASE WHEN sla_deadline < NOW() AND status NOT IN (\'RESOLVED\',\'CLOSED\')
                    THEN true ELSE sla_breached END as sla_status
        FROM support_tickets WHERE {" AND ".join(cond)}
        ORDER BY CASE priority WHEN \'CRITICAL\' THEN 1 WHEN \'HIGH\' THEN 2
                               WHEN \'MEDIUM\' THEN 3 ELSE 4 END, created_at DESC
        LIMIT :limit
    """), params)
    return {"tickets": [dict(row._mapping) for row in r.fetchall()]}
'''

COMPLIANCE_EP = '''"""Compliance & Audit API."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional
import datetime
from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/v1/compliance", tags=["Compliance"])


@router.get("/audit-logs")
async def audit_logs(
    resource_type: Optional[str] = None,
    risk_level: Optional[str] = None,
    hours: int = Query(24, le=8760),
    limit: int = Query(100, le=1000),
    db: AsyncSession = Depends(get_db),
    u: User = Depends(get_current_user)
):
    if not u.is_superuser: raise HTTPException(403, "Admin only")
    cond, params = ["created_at > NOW() - INTERVAL :h"], {'h': f'{hours} hours', 'limit': limit}
    if resource_type: cond.append("resource_type = :rt"); params['rt'] = resource_type
    if risk_level:    cond.append("risk_level = :rl");    params['rl'] = risk_level
    r = await db.execute(text(f"""
        SELECT user_id, action, resource_type, resource_id, endpoint,
               ip_address, response_code, duration_ms, outcome, risk_level, created_at
        FROM audit_logs WHERE {" AND ".join(cond)}
        ORDER BY created_at DESC LIMIT :limit
    """), params)
    rows = r.fetchall()
    return {"logs": [dict(row._mapping) for row in rows], "count": len(rows)}


@router.get("/dashboard")
async def compliance_dashboard(db: AsyncSession = Depends(get_db),
                               u: User = Depends(get_current_user)):
    if not u.is_superuser: raise HTTPException(403, "Admin only")
    r1 = await db.execute(text("""
        SELECT framework,
            COUNT(*) FILTER (WHERE status=\'PASS\')    as passing,
            COUNT(*) FILTER (WHERE status=\'FAIL\')    as failing,
            COUNT(*) FILTER (WHERE status=\'PARTIAL\') as partial,
            COUNT(*) FILTER (WHERE status=\'PENDING\') as pending,
            COUNT(*) as total,
            ROUND(COUNT(*) FILTER (WHERE status=\'PASS\') * 100.0 / COUNT(*), 1) as pass_pct
        FROM compliance_checks GROUP BY framework ORDER BY framework
    """))
    frameworks = [dict(r._mapping) for r in r1.fetchall()]

    r2 = await db.execute(text("""
        SELECT COUNT(*) FROM audit_logs
        WHERE risk_level IN (\'HIGH\',\'CRITICAL\') AND created_at > NOW() - INTERVAL \'24 hours\'
    """))
    risk_events = r2.scalar_one()

    r3 = await db.execute(text("""
        SELECT table_name, retention_days, classification FROM data_retention_policies
        ORDER BY classification DESC
    """))
    retention = [dict(r._mapping) for r in r3.fetchall()]

    return {
        "frameworks": frameworks,
        "high_risk_events_24h": risk_events,
        "data_retention_policies": retention,
        "generated_at": datetime.datetime.utcnow().isoformat(),
    }


@router.get("/controls")
async def list_controls(framework: Optional[str] = None,
                        status: Optional[str] = None,
                        db: AsyncSession = Depends(get_db),
                        u: User = Depends(get_current_user)):
    if not u.is_superuser: raise HTTPException(403, "Admin only")
    cond, params = ["1=1"], {}
    if framework: cond.append("framework = :fw"); params['fw'] = framework
    if status:    cond.append("status = :status"); params['status'] = status
    r = await db.execute(text(f"""
        SELECT framework, control_id, control_name, status, automated, owner, last_checked, notes
        FROM compliance_checks WHERE {" AND ".join(cond)}
        ORDER BY framework, control_id
    """), params)
    return {"controls": [dict(row._mapping) for row in r.fetchall()]}


@router.patch("/controls/{framework}/{control_id}")
async def update_control(framework: str, control_id: str, data: dict,
                         db: AsyncSession = Depends(get_db),
                         u: User = Depends(get_current_user)):
    if not u.is_superuser: raise HTTPException(403, "Admin only")
    allowed = {'status', 'evidence', 'notes', 'owner'}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates: raise HTTPException(400, "No valid fields")
    updates['fw'] = framework; updates['cid'] = control_id
    updates['now'] = datetime.datetime.utcnow()
    set_clause = ", ".join(f"{k}=:{k}" for k in updates if k not in ('fw','cid','now'))
    await db.execute(text(f"""
        UPDATE compliance_checks SET {set_clause}, last_checked=:now, updated_at=:now
        WHERE framework=:fw AND control_id=:cid
    """), updates)
    await db.commit()
    return {"ok": True}
'''

CONTRACTORS_EP = '''"""Contractor Identity & Procurement Intelligence."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional
from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/v1/contractors", tags=["Contractors"])


@router.get("/")
async def list_contractors(
    specialization: Optional[str] = None,
    min_score: float = Query(0, ge=0, le=100),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    u: User = Depends(get_current_user)
):
    cond, params = ["is_active = true", "overall_score >= :min_score"], {'min_score': min_score, 'limit': limit}
    if specialization: cond.append(":spec = ANY(specializations)"); params['spec'] = specialization
    r = await db.execute(text(f"""
        SELECT id, full_name_ar, full_name_en, company_name, specializations,
               compliance_score, performance_score, reputation_score, overall_score,
               verified, kyc_status
        FROM contractor_profiles WHERE {" AND ".join(cond)}
        ORDER BY overall_score DESC LIMIT :limit
    """), params)
    return {"contractors": [dict(row._mapping) for row in r.fetchall()]}


@router.post("/")
async def register_contractor(data: dict, db: AsyncSession = Depends(get_db),
                              u: User = Depends(get_current_user)):
    await db.execute(text("""
        INSERT INTO contractor_profiles
            (full_name_ar, full_name_en, company_name, cr_number, vat_number,
             email, phone, specializations)
        VALUES (:na, :ne, :co, :cr, :vat, :em, :ph, :sp)
    """), {'na': data.get('full_name_ar'), 'ne': data.get('full_name_en'),
           'co': data.get('company_name'), 'cr': data.get('cr_number'),
           'vat': data.get('vat_number'), 'em': data.get('email'),
           'ph': data.get('phone'), 'sp': data.get('specializations', [])})
    await db.commit()
    return {"ok": True}


@router.get("/price-intelligence/{item_code}")
async def price_intel(item_code: str, region: str = "SA",
                      db: AsyncSession = Depends(get_db),
                      u: User = Depends(get_current_user)):
    r = await db.execute(text("""
        SELECT item_name, unit, region, price_min, price_max, price_avg,
               price_median, currency, sample_count, measured_at
        FROM price_intelligence WHERE item_code=:c AND region=:reg
        ORDER BY measured_at DESC LIMIT 1
    """), {'c': item_code, 'reg': region})
    row = r.fetchone()
    if not row: raise HTTPException(404, "No price data")
    return dict(row._mapping)
'''

def main():
    c = connect()
    print("Connected to server")

    section("1. DATABASE SCHEMA")
    upload(c, '/tmp/enterprise.sql', SQL)
    run(c, 'PGPASSWORD="CB_pg_S3cur3_2024!" psql -h 127.0.0.1 -U clickbuild clickbuild_platform < /tmp/enterprise.sql', timeout=30)
    # Verify
    out, _ = run(c, 'PGPASSWORD="CB_pg_S3cur3_2024!" psql -h 127.0.0.1 -U clickbuild clickbuild_platform -c "SELECT table_name FROM information_schema.tables WHERE table_schema=\'public\' ORDER BY table_name" | grep -E "audit|slo|incident|support|contractor|compliance|runbook|health|ai_audit|change|price_intel|vendor|encrypt|metric|retention|sla_pol|postmortem|ticket_msg"')

    section("2. BACKEND SERVICES")
    run(c, "mkdir -p /opt/clickbuild/backend/app/services /opt/clickbuild/backend/app/middleware")
    upload(c, '/opt/clickbuild/backend/app/services/sre.py', SRE_PY)
    upload(c, '/opt/clickbuild/backend/app/services/support.py', SUPPORT_PY)
    upload(c, '/opt/clickbuild/backend/app/middleware/__init__.py', '')
    upload(c, '/opt/clickbuild/backend/app/middleware/audit.py', AUDIT_PY)

    section("3. API ENDPOINTS")
    upload(c, '/opt/clickbuild/backend/app/api/v1/endpoints/sre.py', SRE_EP)
    upload(c, '/opt/clickbuild/backend/app/api/v1/endpoints/support.py', SUPPORT_EP)
    upload(c, '/opt/clickbuild/backend/app/api/v1/endpoints/compliance.py', COMPLIANCE_EP)
    upload(c, '/opt/clickbuild/backend/app/api/v1/endpoints/contractors.py', CONTRACTORS_EP)

    section("4. WIRE main.py")
    wire_script = r"""python3 -c "
path = '/opt/clickbuild/backend/app/main.py'
with open(path) as f:
    content = f.read()

changes = []

# Add audit middleware import
if 'AuditLogMiddleware' not in content:
    old = 'from app.middleware.audit import AuditLogMiddleware\n'
    if old not in content:
        content = old + content
        changes.append('Added AuditLogMiddleware import')

# Add new router imports
if 'from app.api.v1.endpoints import' in content:
    import re
    m = re.search(r'from app\.api\.v1\.endpoints import (.+)', content)
    if m:
        existing = m.group(1)
        to_add = [x for x in ['sre', 'support', 'compliance', 'contractors'] if x not in existing]
        if to_add:
            new_imports = existing.rstrip() + ', ' + ', '.join(to_add)
            content = content.replace(m.group(0), f'from app.api.v1.endpoints import {new_imports}')
            changes.append(f'Added imports: {to_add}')

# Add routers
for rname in ['sre', 'support', 'compliance', 'contractors']:
    if f'{rname}.router' not in content:
        content += f'\napp.include_router({rname}.router)'
        changes.append(f'Added router: {rname}')

# Add audit middleware
if 'add_middleware(AuditLogMiddleware)' not in content:
    content = content.replace(
        'app.include_router(proxy_router)',
        'app.add_middleware(AuditLogMiddleware)\napp.include_router(proxy_router)'
    )
    changes.append('Added AuditLogMiddleware')

with open(path, 'w') as f:
    f.write(content)
print('Changes:', changes)
"
"""
    run(c, wire_script, timeout=30)
    run(c, "grep -n 'sre\\|support\\|compliance\\|contractor\\|AuditLog' /opt/clickbuild/backend/app/main.py | head -20")

    section("5. RESTART BACKEND")
    run(c, "systemctl restart clickbuild-api")
    time.sleep(5)
    out, _ = run(c, "systemctl is-active clickbuild-api")
    print(f"  clickbuild-api: {out}")

    section("6. VALIDATE ENDPOINTS")
    time.sleep(3)
    for ep in ['/api/v1/sre/slos', '/api/v1/sre/incidents', '/api/v1/support/tickets',
               '/api/v1/compliance/dashboard', '/api/v1/compliance/controls',
               '/api/v1/contractors/']:
        out, _ = run(c, f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost:8000{ep}")
        ok = out in ['200', '401', '403', '422']
        print(f"  [{'OK' if ok else 'FAIL'}] {ep}: {out}")

    section("7. DB SUMMARY")
    run(c, 'PGPASSWORD="CB_pg_S3cur3_2024!" psql -h 127.0.0.1 -U clickbuild clickbuild_platform -c "SELECT (SELECT COUNT(*) FROM slo_definitions) as slos, (SELECT COUNT(*) FROM compliance_checks) as controls, (SELECT COUNT(*) FROM sla_policies) as sla_policies, (SELECT COUNT(*) FROM runbooks) as runbooks;"')

    c.close()
    print("\nBackend deployment complete!")

if __name__ == "__main__":
    main()
