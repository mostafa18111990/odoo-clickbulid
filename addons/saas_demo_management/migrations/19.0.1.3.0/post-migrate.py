def migrate(cr, version):
    """Make pending demo readiness visible to the customer within one minute."""
    cr.execute("""
        UPDATE ir_cron
           SET interval_number = 1,
               interval_type = 'minutes'
         WHERE id = (
             SELECT res_id
               FROM ir_model_data
              WHERE module = 'saas_demo_management'
                AND name = 'ir_cron_refresh_demo_health'
                AND model = 'ir.cron'
              LIMIT 1
         )
    """)
