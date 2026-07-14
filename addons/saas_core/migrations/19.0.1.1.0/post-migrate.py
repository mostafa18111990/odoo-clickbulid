def migrate(cr, version):
    prices = {
        'starter': ('community', 299.0, 299.0, 3049.80, 1),
        'business': ('community', 249.0, 498.0, 5079.60, 2),
        'enterprise': ('community', 199.0, 597.0, 6089.40, 9999),
        'starter_ee': ('enterprise', 399.0, 399.0, 4069.80, 1),
        'business_ee': ('enterprise', 349.0, 698.0, 7119.60, 2),
        'enterprise_ee': ('enterprise', 299.0, 897.0, 9149.40, 9999),
    }
    for code, (edition, unit, monthly, yearly, max_users) in prices.items():
        cr.execute(
            """UPDATE saas_plan
                  SET edition=%s, pricing_mode='per_user', price_per_user=%s,
                      monthly_price=%s, yearly_price=%s, max_users=%s
                WHERE lower(code)=lower(%s) AND active=true""",
            (edition, unit, monthly, yearly, max_users, code),
        )
