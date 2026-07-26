def migrate(cr, version):
    cr.execute("""
        UPDATE saas_demo_template
           SET module_codes = module_codes || ',saas_demo_seed'
         WHERE active
           AND module_codes IS NOT NULL
           AND module_codes NOT LIKE '%%saas_demo_seed%%'
    """)
