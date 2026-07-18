ANNUAL_FACTOR = 12


def migrate(cr, version):
    """Synchronize stored plan values with annual-only, no-discount billing."""
    cr.execute("""
        UPDATE saas_plan
           SET yearly_price = ROUND((monthly_price * %s)::numeric, 2)
         WHERE yearly_price IS DISTINCT FROM ROUND((monthly_price * %s)::numeric, 2)
    """, (ANNUAL_FACTOR, ANNUAL_FACTOR))
