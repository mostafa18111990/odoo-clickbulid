cases = {
    'community': {
        1: (299.0, 3588.0),
        2: (498.0, 5976.0),
        3: (597.0, 7164.0),
        4: (796.0, 9552.0),
    },
    'enterprise': {
        1: (399.0, 4788.0),
        2: (698.0, 8376.0),
        3: (897.0, 10764.0),
        4: (1196.0, 14352.0),
    },
}
plans = env['saas.plan']
for edition, user_cases in cases.items():
    for users, expected in user_cases.items():
        monthly = plans.tiered_quote(edition, users, 'monthly')
        yearly = plans.tiered_quote(edition, users, 'yearly')
        assert monthly['total'] == expected[0], (edition, users, monthly)
        assert yearly['total'] == expected[1], (edition, users, yearly)
        assert yearly['annual_total'] == yearly['monthly_total'] * 12
        assert yearly['discount_pct'] == 0.0
        assert yearly['discount_amount'] == 0.0
        selected = plans.tier_plan_for(edition, users)
        assert selected, (edition, users, 'missing tier plan')
        assert selected.price_for_users(users, 'yearly') == expected[1]

expected_plans = {
    'starter': (299.0, 299.0, 3588.0),
    'business': (249.0, 498.0, 5976.0),
    'enterprise': (199.0, 597.0, 7164.0),
    'starter_ee': (399.0, 399.0, 4788.0),
    'business_ee': (349.0, 698.0, 8376.0),
    'enterprise_ee': (299.0, 897.0, 10764.0),
}
for code, expected in expected_plans.items():
    plan = plans.search([('code', '=ilike', code), ('active', '=', True)], limit=1)
    assert plan, ('missing plan', code)
    actual = (plan.price_per_user, plan.monthly_price, plan.yearly_price)
    assert actual == expected, (code, actual, expected)
    assert plan.yearly_price == plan.monthly_price * 12

print('ANNUAL_ONLY_PRICING_22_ASSERTIONS=PASS')
