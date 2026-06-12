"""End-to-end smoke test: exercises core SaaS workflow on the production DB.

Runs inside the odoo_saas_app container via:
    docker exec odoo_saas_app python3 /tmp/e2e_smoke_test.py

Creates an isolated tenant + subscription + ticket, then deletes the rows
so the test is idempotent. Prints PASS/FAIL summary at the end.
"""
import sys
import traceback

ODOO_RC = '/etc/odoo/odoo.conf'
DB = 'odoo'


def main():
    import odoo
    from odoo.tools import config
    config.parse_config(['-c', ODOO_RC])
    registry = odoo.modules.registry.Registry(DB)
    with registry.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        results = []
        cleanup_ids = {}

        def step(name, fn):
            try:
                out = fn(env, cleanup_ids)
                results.append((name, True, out))
                print(f'PASS {name}: {out}')
            except Exception as e:
                results.append((name, False, str(e)))
                print(f'FAIL {name}: {e}')
                traceback.print_exc()

        step('1_event_bus', test_event_bus)
        step('2_signup_lead', test_signup_lead)
        step('3_create_tenant', test_create_tenant)
        step('4_create_subscription', test_create_subscription)
        step('5_create_ticket', test_create_ticket)
        step('6_publish_kb_article', test_publish_kb_article)
        step('7_generate_api_token', test_generate_api_token)
        step('8_validate_coupon', test_validate_coupon)
        step('9_snapshot_metrics', test_snapshot_metrics)
        step('10_run_health_check', test_run_health_check)

        cleanup(env, cleanup_ids)
        cr.commit()

        passed = sum(1 for _, ok, _ in results if ok)
        total = len(results)
        print(f'\n=== E2E RESULT: {passed}/{total} passed ===')
        return 0 if passed == total else 1


def test_event_bus(env, ids):
    ev = env['saas.event'].sudo()._publish(
        event_type='tenant.lead.created', model='saas.tenant', record_id=0,
        payload={'msg': 'hello', 'source': 'e2e_test'})
    ids.setdefault('events', []).append(ev.id)
    return f'event_id={ev.id}'


def test_signup_lead(env, ids):
    lead = env['saas.website.lead'].sudo().create({
        'name': 'E2E Test Lead', 'email': 'e2e@test.local'})
    ids.setdefault('leads', []).append(lead.id)
    return f'lead_id={lead.id}'


def test_create_tenant(env, ids):
    plan = env.ref('saas_core.plan_business', raise_if_not_found=False)
    if not plan:
        plan = env['saas.plan'].sudo().search([], limit=1)
    tenant = env['saas.tenant'].sudo().create({
        'name': 'E2E Test Tenant',
        'company_name': 'E2E Test Co',
        'subdomain': 'e2etest-tenant',
        'customer_name': 'E2E Customer',
        'customer_email': 'e2e-tenant@test.local',
        'plan_id': plan.id, 'state': 'trial'})
    ids['tenant_id'] = tenant.id
    ids['plan_id'] = plan.id
    return f'tenant_id={tenant.id} plan={plan.name}'


def test_create_subscription(env, ids):
    sub = env['saas.subscription'].sudo().create({
        'tenant_id': ids['tenant_id'], 'plan_id': ids['plan_id'],
        'status': 'active', 'base_amount': 100.0})
    ids['subscription_id'] = sub.id
    return f'sub_id={sub.id} status={sub.status} base={sub.base_amount}'


def test_create_ticket(env, ids):
    priority = env.ref('saas_support.priority_normal')
    category = env.ref('saas_support.category_technical')
    ticket = env['saas.ticket'].sudo().create({
        'subject': 'E2E Test ticket',
        'description': '<p>Created by smoke test</p>',
        'tenant_id': ids['tenant_id'],
        'priority_id': priority.id, 'category_id': category.id,
        'customer_email': 'e2e-tenant@test.local'})
    ids['ticket_id'] = ticket.id
    msg = env['saas.ticket.message'].sudo().create({
        'ticket_id': ticket.id, 'body': '<p>agent reply</p>',
        'is_internal': False, 'is_from_customer': False})
    ids['ticket_msg_id'] = msg.id
    ticket = env['saas.ticket'].sudo().browse(ticket.id)
    return (f'ticket={ticket.name} state={ticket.state} '
            f'first_response_at={ticket.sla_first_response_at}')


def test_publish_kb_article(env, ids):
    cat = env.ref('saas_knowledge.kb_cat_getting_started')
    article = env['saas.kb.article'].sudo().create({
        'name': 'E2E Test Article', 'slug': 'e2e-test-article',
        'category_id': cat.id, 'summary': 'Smoke test article',
        'body': '<p>Hello world</p>', 'visibility': 'portal'})
    article.action_publish()
    ids['article_id'] = article.id
    return f'article_id={article.id} state={article.state}'


def test_generate_api_token(env, ids):
    token = env['saas.api.token'].sudo().create({
        'name': 'E2E Token', 'user_id': odoo_uid(env),
        'scopes': 'read'})
    ids['token_id'] = token.id
    has_plain = bool(token.plain_token_once and token.plain_token_once.startswith('sk_'))
    return f'token_id={token.id} prefix={token.token_prefix} plain_ok={has_plain}'


def odoo_uid(env):
    user = env['res.users'].sudo().search([('login', '=', 'admin')], limit=1)
    return user.id if user else 1


def test_validate_coupon(env, ids):
    from odoo.addons.saas_marketing.services.coupon_service import CouponService
    coupon = env['saas.coupon'].sudo().create({
        'code': 'E2E10', 'name': 'E2E test coupon',
        'discount_type': 'percent', 'discount_value': 10.0,
        'state': 'active'})
    ids['coupon_id'] = coupon.id
    ok, msg, c = CouponService(env).validate('E2E10', amount=100.0)
    discount = CouponService(env).calculate_discount(coupon, 100.0)
    return f'coupon ok={ok} msg={msg} discount={discount}'


def test_snapshot_metrics(env, ids):
    from odoo.addons.saas_reporting.services.reporting_service import ReportingService
    snap = ReportingService(env).snapshot_today()
    return f'snapshot_date={snap.snapshot_date} mrr={snap.mrr} active_subs={snap.active_subscriptions}'


def test_run_health_check(env, ids):
    check = env.ref('saas_monitoring.health_check_db')
    from odoo.addons.saas_monitoring.services.health_service import HealthService
    status = HealthService(env).execute(check)
    return f'db_check={status}'


def cleanup(env, ids):
    print('--- cleanup ---')
    if ids.get('ticket_msg_id'):
        env['saas.ticket.message'].sudo().browse(ids['ticket_msg_id']).unlink()
    if ids.get('ticket_id'):
        env['saas.ticket'].sudo().browse(ids['ticket_id']).unlink()
    if ids.get('subscription_id'):
        env['saas.subscription'].sudo().browse(ids['subscription_id']).unlink()
    if ids.get('tenant_id'):
        env['saas.tenant'].sudo().browse(ids['tenant_id']).unlink()
    if ids.get('article_id'):
        env['saas.kb.article'].sudo().browse(ids['article_id']).unlink()
    if ids.get('token_id'):
        env['saas.api.token'].sudo().browse(ids['token_id']).unlink()
    if ids.get('coupon_id'):
        env['saas.coupon'].sudo().browse(ids['coupon_id']).unlink()
    # Events are intentionally immutable (audit log) — not deleted.
    for lead_id in ids.get('leads', []):
        env['saas.website.lead'].sudo().browse(lead_id).unlink()


if __name__ == '__main__':
    sys.exit(main())
