# Phase 1 Technical SEO — Staging Implementation

Date: 2026-08-01

## Scope

This change is installed only on `clickbuild3_stage` and is delivered by the
isolated `clickbuild_seo` add-on. Production was inspected read-only and was
not modified.

## Implemented

- Canonical, Open Graph URL, Open Graph image, and all hreflang alternatives
  use HTTPS on both Arabic and English pages.
- Organization and WebSite JSON-LD is emitted as valid, parseable JSON.
- Staging emits `noindex,nofollow,noarchive` and its `robots.txt` blocks all
  crawlers so the review environment cannot compete with production.
- Sitemap output is forced to HTTPS behind the reverse proxy.
- Technical or low-value routes are excluded from the sitemap:
  `/contactus`, `/help`, `/error`, `/get-started/success`, and `/website/info`.
- Main public destinations remain in the sitemap, including applications,
  industries, pricing, about, and contact.

## Verification

- Arabic: canonical `/`, `ar`, `en`, and `x-default` alternates are HTTPS;
  `og:url` and `og:image` are HTTPS; HTML direction is RTL.
- English: canonical `/en`, alternates, `og:url`, and `og:image` are HTTPS;
  HTML direction is LTR.
- Browser parsing found JSON-LD types `Organization` and `WebSite` with no
  parse error.
- No horizontal overflow was observed in either language.
- `robots.txt`: HTTP 200 and `Disallow: /`.
- `sitemap.xml`: HTTP 200, 14 locations, no staging HTTP URL, no excluded route.
- Database manager: HTTP 404.
- Recent Staging logs: no ERROR, CRITICAL, or traceback after deployment.
- CRM regression contract: `CRM_BRIDGE_FOLLOWUP_CONTRACT=PASS`; QA residue 0.
- Staging safety: active crons 0, active mail servers 0, enabled payments 0,
  pending Enterprise modules 0.
- Production home remained HTTP 200 and its existing robots output remained
  unchanged. Production still requires an explicit approved promotion before
  its HTTP sitemap reference is corrected.

## Rollback

Latest pre-upgrade restore point:

`/opt/clickbuild-staging/backups/pre-phase1-seo-2026-08-01-195827`

- Database dump: `clickbuild3_stage.dump` (9.2 MB).
- SHA-256:
  `7b9d8a0cc872b46cd05e76749796a3d224c63044a5f041a3e1318fcd1f9c711d`.
- The restore point also includes the complete prior `runtime-addons` tree and
  the prior `clickbuild_seo` source.
- The deployment script restores the database, runtime add-ons, source, and
  Staging container automatically if an upgrade step fails.

No production rollback is required because production was not changed.
