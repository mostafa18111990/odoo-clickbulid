ANNUAL_FACTOR = 12 * 0.85


def migrate(cr, version):
    """Synchronize stored plan values with the single 15% annual policy."""
    cr.execute("""
        UPDATE saas_plan
           SET yearly_price = ROUND((monthly_price * %s)::numeric, 2)
         WHERE yearly_price IS DISTINCT FROM ROUND((monthly_price * %s)::numeric, 2)
    """, (ANNUAL_FACTOR, ANNUAL_FACTOR))
