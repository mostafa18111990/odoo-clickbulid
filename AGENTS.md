# ClickBuild Odoo SaaS agent rules

## Scope

- Target runtime: Odoo 19 with PostgreSQL 15 and Docker Compose.
- Treat `addons/` as the product source. Do not commit generated archives, backups,
  database dumps, rendered documents, browser profiles, or local deployment files.
- Preserve unrelated user changes. Never reset, delete, or overwrite a dirty worktree.

## Security

- Never print, commit, copy into patches, or expose passwords, tokens, API keys,
  private SSH keys, database dumps, filestore contents, or production environment files.
- Use example placeholders in documentation and configuration samples.
- Production credentials must not be available during normal Codex Cloud agent work.
- Do not weaken authentication, TLS, database-manager restrictions, CSRF, rate limits,
  tenant isolation, or backup verification.

## Delivery workflow

1. Work on a dedicated `codex/` branch.
2. Run static checks and relevant tests.
3. Open a pull request for review.
4. Deploy to the protected `staging` environment first.
5. Verify public routes, Odoo logs, assets, RTL/mobile layout, and rollback readiness.
6. Production deployment requires an explicit user approval and a protected GitHub
   `production` environment approval. A code change or merge is not deployment approval.

## Production guardrails

- Never deploy production directly from a cloud chat or ordinary push.
- Before production deployment, create and verify a timestamped backup containing the
  database, filestore, deployed addon code, and runtime configuration checksums.
- Any failed upgrade or smoke test must stop deployment and run the documented rollback.
- Never use `|| true` on backup, database restore, module upgrade, or smoke-test steps.
