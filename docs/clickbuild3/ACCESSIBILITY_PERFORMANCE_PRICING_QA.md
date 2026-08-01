# Phase 1 Accessibility, Performance, and Pricing QA

Date: 2026-08-01

## Scope

The implementation and all tests were performed only on
`https://staging.odoo.clickbulid.com`. Production was probed read-only and was
not modified.

## Accessibility changes

- Replaced the nested homepage `<main>` with a neutral container, leaving one
  main landmark and one H1.
- Added localized accessible names to both website search inputs and the
  mobile submenu back button.
- Raised essential header, carousel, pricing, and footer targets to at least
  44 px.
- Added a localized region label to the homepage carousel.
- Disabled automatic carousel movement; slides now change only on user action.
- Preserved the existing skip link, visible focus ring, reduced-motion rules,
  RTL/LTR behavior, and responsive layout.
- Marked decorative hero images with empty alt text so the visible heading and
  copy are not repeated by screen readers.

## Performance changes

Three 1408x768 hero assets now use AVIF with WebP fallback. Original files are
kept as source assets for rollback and future recompression.

| Asset | Original | AVIF | WebP fallback |
|---|---:|---:|---:|
| Executive dashboard | 2,046,364 B | 55,646 B | 83,462 B |
| Enterprise team | 722,678 B | 47,521 B | 71,048 B |
| Industry solutions | 2,026,789 B | 48,734 B | 75,492 B |

- The first hero is eager, `fetchpriority=high`, and has explicit 1408x768
  dimensions to reduce LCP delay and layout shift.
- Later carousel images are lazy and low priority.
- Every generated AVIF and WebP is below the 250 KB image budget.

## Browser QA

- Arabic desktop 1280x720: RTL, no horizontal overflow, one main, one H1,
  valid JSON-LD, no unlabeled form control, no undersized essential target.
- Arabic mobile 390x844: same checks passed; hero served as AVIF.
- English mobile 390x844: LTR, no overflow, no unlabeled control, no
  undersized essential target.
- WebP sources resolve to the correct `.webp` files for all three slides.
- Carousel interval is `false`.

## Annual-only pricing QA

- Active plans in `saas.plan`: 6 (three Community and three Enterprise).
- Every stored annual price equals the displayed monthly total multiplied by
  12; discount percentage and amount are zero.
- Backend contract: `ANNUAL_ONLY_PRICING_22_ASSERTIONS=PASS`.
- Frontend, four users:
  - Community: 199 SAR/user/month, 796 SAR/month, 9,552 SAR/year.
  - Enterprise: 299 SAR/user/month, 1,196 SAR/month, 14,352 SAR/year.
- Signup links use `billing=yearly`.
- No monthly billing toggle, 15% discount, or two-free-month copy is present.

## Regression and safety

- CRM contract: `CRM_BRIDGE_FOLLOWUP_CONTRACT=PASS`.
- QA residue: 0.
- Pending Enterprise modules: 0.
- Active Staging crons: 0.
- Active Staging mail servers: 0.
- Enabled Staging payment providers: 0.
- Recent Staging log scan found no ERROR, CRITICAL, or traceback.
- Production home remained HTTP 200 and was not changed.

The first installation attempt used an XPath that did not match Odoo's
indirect search-box template. The deployment stopped before startup and its
automatic rollback restored module versions and returned the Staging home to
HTTP 200. The corrected template targets the actual search input node; all
subsequent upgrades and QA passed.

## Rollback

Latest pre-upgrade restore point:

`/opt/clickbuild-staging/backups/pre-phase1-accessibility-2026-08-01-203821`

- Database dump: `clickbuild3_stage.dump` (9.2 MB).
- SHA-256:
  `802c06429eaf61260fdd171717c66254c20186b79ba3986ff721edb50d03e5d7`.
- Includes the complete prior runtime add-ons plus the prior
  `saas_website` and `clickbuild_website_core` sources.
- The deployment script restores database, code, runtime add-ons, and the
  Staging container automatically on failure.
