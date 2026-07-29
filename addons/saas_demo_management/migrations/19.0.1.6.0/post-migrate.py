RESTAURANT_MODULES = (
    'web_enterprise,account_accountant,point_of_sale,pos_restaurant,pos_loyalty,'
    'sale_loyalty,purchase_stock,stock,stock_barcode,product_expiry,'
    'stock_barcode_product_expiry,mrp,mrp_workorder,mrp_product_expiry,'
    'quality,maintenance,fleet,hr,hr_attendance,hr_holidays,'
    'hr_expense,hr_recruitment,hr_appraisal,hr_payroll,planning,documents,sign,'
    'approvals,helpdesk,delivery,appointment,l10n_sa,l10n_sa_edi,'
    'saas_demo_seed,saas_restaurant_demo'
)


def migrate(cr, version):
    cr.execute(
        """
        UPDATE saas_demo_template
           SET name = jsonb_build_object('en_US', %s::text),
               module_codes = %s,
               sample_scenario = jsonb_build_object('en_US', %s::text)
         WHERE sector = 'restaurants-cafes'
        """,
        (
            'Saudi Restaurants Full Enterprise Demo',
            RESTAURANT_MODULES,
            (
                'Saudi restaurant Enterprise cycle: procurement, lots and expiry, '
                'multi-level recipes, production, restaurant POS, delivery platforms, '
                'own delivery, settlement, food cost, waste, HR, quality, maintenance, '
                'and branch profitability.'
            ),
        ),
    )
