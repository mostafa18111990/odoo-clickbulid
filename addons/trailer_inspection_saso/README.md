# Trailer Inspection - SASO (Odoo 19)

An installable Odoo 19 application for controlled trailer and semi-trailer inspections.

## Scope

- O1-O4 trailer categories and VIN validation.
- Version-controlled SASO, GSO, ISO/IEC 17020 and ISO 19011 references.
- 55 bilingual checklist requirements derived from the supplied inspection form.
- Inspector authorization, impartiality confirmation and independent technical review.
- Measuring-equipment calibration control and evidence attachments.
- Axle weights, inspection photos, nonconformities and corrective actions.
- Bilingual PDF inspection report.
- Multi-company security roles: user, inspector, reviewer and manager.
- Server-side numeric rule evaluation and critical-finding approval blocks.
- Controlled nonconformity, root-cause, corrective-action and reinspection workflow.
- Digital inspector/reviewer signatures, report locking and timestamp/IP audit data.
- Public QR report verification and a restricted customer inspection portal.
- CSV/XLSX inspection import and source-document staging for future OCR providers.
- Inspection analytics, quality documents, complaints/appeals and deadline activities.
- Responsive standard Odoo views for inspectors using phones and tablets.
- Complete Arabic localization (`i18n/ar.po`) for menus, fields, buttons, states,
  validation messages, quality workflows and import screens; English remains the source language.
- Controlled GSO 1780 VIN generation using approved WMI/VDS/plant profiles, model-year
  codes, database-locked production sequences, position-9 check-digit calculation,
  low-volume manufacturer rules and duplicate prevention.

## Integration boundaries

The module does not embed third-party credentials. OCR, WhatsApp and external digital-signature
providers require a selected provider and its API credentials. The data fields, workflow states,
portal and extension points are present so these integrations can be added without redesigning
the inspection records. Standard Odoo email/activity notifications work without those providers.

## Reference control

The attached legacy ISO editions remain identified as superseded references. The data set
also records ISO/IEC 17020:2026 and ISO 19011:2026 as current editions so that inspection
methods can be reviewed and updated without silently replacing historical requirements.

The checklist is a controlled starting point. The inspection body must approve its final
method, sampling rules, equipment list, competence matrix and report wording before use.

## Deployment status

This addon has only been built and statically validated in the local workspace. It has not
been installed, upgraded, copied to the server or loaded into any Odoo database.
