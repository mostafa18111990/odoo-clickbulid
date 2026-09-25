def migrate(cr, version):
    """Allow one trailer (VIN) to be inspected more than once.

    UNIQUE(vin) made periodic inspections and reinspections of the same
    trailer impossible. It is replaced by a Python constraint allowing only
    one open inspection per VIN; the database constraint must be dropped
    explicitly because removing it from the model does not.
    """
    cr.execute("ALTER TABLE trailer_inspection DROP CONSTRAINT IF EXISTS trailer_inspection_vin_unique")
    cr.execute("DELETE FROM ir_model_constraint WHERE name = 'trailer_inspection_vin_unique'")
    cr.execute(
        "DELETE FROM ir_model_data WHERE module = 'trailer_inspection_saso' "
        "AND name = 'constraint_trailer_inspection_vin_unique'"
    )
