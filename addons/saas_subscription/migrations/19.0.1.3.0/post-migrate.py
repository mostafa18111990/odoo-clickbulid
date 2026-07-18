def migrate(cr, version):
    """Normalize archived and deleted tenant metadata to annual billing.

    The previous ORM migration used the default active filter, so historical
    tenant rows were not included even though their linked subscriptions were
    successfully converted.
    """
    cr.execute(
        """
        UPDATE saas_tenant
           SET billing_cycle = 'yearly'
         WHERE billing_cycle = 'monthly'
        """
    )
