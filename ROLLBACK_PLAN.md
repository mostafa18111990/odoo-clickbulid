# ClickBuild Full Rollback Plan

## Baseline

- Backup name: `clickbuild-production-before-redesign-2026-07-31-0843`
- Created: 2026-07-31 08:43 UTC / 11:43 Asia/Riyadh
- Server: production host `72.60.46.204`
- Protected location: `/opt/backups/clickbuild-production-before-redesign-2026-07-31-0843`
- Access: server administrator (`root`) only; the backup directory is outside the project tree.
- Git commit: `0aa1b6d960c6f5169055b0bcc61c2ba385c58c35`
- Protected branch: `codex/production-before-clickbuild-3`
- Protected tag: `production-before-clickbuild-3`
- Responsible rollback account: the production server administrator using the `root` account.

The branch and tag above are baseline references. They must not be moved, force-updated, or deleted during the project.

## Backup contents

- `databases/`: custom-format dumps of all 42 non-template PostgreSQL databases, a database inventory with source sizes, and PostgreSQL globals.
- `filestore/community-volume.tar.gz`: Community Odoo data, filestores, sessions, and attachments.
- `filestore/enterprise-volume.tar.gz`: Enterprise Odoo data, filestores, sessions, and attachments.
- `filestore/staging-volume.tar.gz`: existing staging Odoo data and filestore.
- `code/odoo-saas.tar.gz`: production source, standard/custom addons, OCA/Cybrosys addons, themes, templates, website code, scripts, Docker/Compose and application configuration.
- `code/clickbuild-staging.tar.gz`: existing staging source and configuration.
- `code/customer-exports.tar.gz`: retained customer export artifacts.
- `system/`: Docker container definitions, Nginx/runtime configuration, systemd services and timers, cron configuration, TLS/Let's Encrypt data, host resolver information, and container/network/volume inventory.
- `dns/`: read-only DNS and TLS snapshots. These are documentation only and are not to be applied unless a separately approved launch requires a DNS change.
- `runtime/`: Odoo, Python, PostgreSQL, Nginx, package and library versions plus functional record counts.
- `images/platform-images.tar.gz`: exact Docker images used by Community, Enterprise, PostgreSQL, Nginx and Certbot.
- `SHA256SUMS`: per-file SHA-256 manifest.
- `CHECKSUM_VALIDATION.log`: proof that every entry in the checksum manifest validated.
- `RESTORE_TEST_REPORT.md` and `RESTORE_TEST_EVIDENCE.log`: practical restore-drill report and evidence.
- `git/production-before-clickbuild-3.bundle`: portable Git baseline bundle.

Configuration archives can contain secrets required for restoration. Do not print, email, paste, or commit their contents. Keep all backup files restricted to the server administrator.

## Restore drill result

A disposable restore environment was created with its own Docker network, PostgreSQL container, database, Odoo container, and data directory. It was bound to localhost only.

The central Odoo database and matching Community filestore were restored from this backup. Odoo 19 loaded 84 installed modules. Administrator authentication succeeded; the login page and home page returned HTTP 200; a stored attachment returned HTTP 200; and functional counts for pages, products, pricelists, attachments, mail servers and payment providers matched the source snapshot.

The drill completed in 101 seconds. All disposable resources were removed automatically. No production container, production database, production filestore, DNS record, or project file was modified.

## Full rollback procedure

Run these steps from an authenticated root shell during an announced maintenance window. Replace `<backup>` with the protected backup directory. Do not place real passwords in shell history; obtain database credentials from the protected configuration on the server.

### 1. Pre-rollback safety snapshot

Before overwriting anything, create a new timestamped emergency snapshot of the then-current database, filestore and code. Record its path and checksum. This preserves any legitimate data created after the baseline.

### 2. Stop writes

1. Put the platform behind a maintenance response.
2. Stop Odoo Community, Odoo Enterprise, provisioning/cron workers and other application writers.
3. Keep PostgreSQL running until database restore is complete.
4. Confirm that no provisioning, backup, certificate or tenant-deletion job is active.

### 3. Restore exact Docker images

```bash
gzip -dc <backup>/images/platform-images.tar.gz | docker image load
```

Verify the loaded image IDs against `system/docker-images.txt`.

### 4. Restore project files

Preserve the current directories by renaming them with a rollback timestamp. Then restore:

```bash
tar -xzf <backup>/code/odoo-saas.tar.gz -C /opt
tar -xzf <backup>/code/clickbuild-staging.tar.gz -C /opt
tar -xzf <backup>/code/customer-exports.tar.gz -C /opt
```

Confirm ownership and permissions against the archived metadata. Never copy protected environment or secret files into Git.

### 5. Restore PostgreSQL

First validate all dumps:

```bash
while IFS= read -r db; do
  docker exec -i odoo_saas_postgres pg_restore --list \
    < "<backup>/databases/${db}.dump" >/dev/null
done < <backup>/databases/DATABASES.txt
```

Restore roles only when required and after reviewing conflicts:

```bash
docker exec -i odoo_saas_postgres psql -U odoo -d postgres \
  < <backup>/databases/globals.sql
```

For each database listed in `DATABASES.txt`, terminate connections, drop it, recreate it with its recorded owner, and restore the custom-format dump:

```bash
docker exec odoo_saas_postgres psql -U odoo -d postgres \
  -v dbname="<database>" \
  -c "select pg_terminate_backend(pid) from pg_stat_activity where datname=:'dbname' and pid <> pg_backend_pid();"
docker exec odoo_saas_postgres dropdb -U odoo --if-exists "<database>"
docker exec odoo_saas_postgres createdb -U odoo "<database>"
docker exec -i odoo_saas_postgres pg_restore -U odoo \
  -d "<database>" --no-owner --no-privileges \
  < "<backup>/databases/<database>.dump"
```

Use the source owner inventory when ownership differs from `odoo`. Do not restore into a database receiving live traffic.

### 6. Restore filestores and attachments

Move the current volume contents to timestamped emergency directories. Restore archives into the exact volume roots:

```bash
tar -xzf <backup>/filestore/community-volume.tar.gz \
  -C /var/lib/docker/volumes/odoo-saas_odoo_data/_data
tar -xzf <backup>/filestore/enterprise-volume.tar.gz \
  -C /var/lib/docker/volumes/odoo-saas_odoo_ent_data/_data
tar -xzf <backup>/filestore/staging-volume.tar.gz \
  -C /var/lib/docker/volumes/clickbuild_redesign_odoodata/_data
```

Restore ownership using the Odoo UID/GID recorded by the runtime/container inventory. Confirm that every restored database requiring a filestore has a matching directory.

### 7. Restore server configuration

Review, then restore only the required configuration:

```bash
tar -xzf <backup>/system/letsencrypt.tar.gz -C /etc
tar -xzf <backup>/system/systemd-system.tar.gz -C /etc
tar -xzf <backup>/system/cron.tar.gz -C /etc
```

Reload systemd after review:

```bash
systemctl daemon-reload
```

Nginx/Docker application configuration is also contained in the restored `/opt/odoo-saas` tree. Validate Nginx before starting it. DNS snapshots are documentation and must not be applied automatically.

### 8. Start and validate

1. Start PostgreSQL and confirm readiness.
2. Start Odoo Community and Enterprise with cron temporarily disabled.
3. Verify registry loading and absence of database/filestore errors.
4. Validate Nginx configuration and start the proxy.
5. Test HTTPS, login, website pages, media/attachments, products, prices, forms, CRM, payment provider configuration and outbound-mail configuration.
6. Re-enable cron/provisioning only after those checks pass.
7. Compare functional counts with `runtime/central-functional-counts.txt`.
8. Run `sha256sum -c SHA256SUMS` from the backup root before and after any copy operation.

## Success criteria

- All expected containers are healthy and use the baseline images/configuration.
- All 42 database dumps restore without `pg_restore` errors.
- Website and backend login return HTTP 200.
- An administrator can authenticate.
- Website pages, menus, products, prices and forms match the baseline.
- Media and sampled stored attachments return HTTP 200.
- CRM, mail server and payment provider records match the baseline where their modules are installed.
- Community and Enterprise tenants open with their matching filestores.
- HTTPS certificate and domain routing are valid.
- Cron and provisioning are re-enabled only after the platform is stable.

## Timing and escalation

- Measured central restore drill: 101 seconds.
- Estimated full-platform rollback for 42 databases and all services: 20–45 minutes, plus business validation.
- If any dump, checksum, filestore or login check fails, keep the platform in maintenance mode, do not re-enable writers, preserve logs, and restore the pre-rollback emergency snapshot or escalate to another server administrator.

## Common problems

- **Database host mismatch:** pass the restore PostgreSQL host explicitly in the isolated Odoo command.
- **Filestore permission error:** restore the Odoo container UID/GID ownership before starting HTTP.
- **Missing attachment:** confirm the database name exactly matches its filestore directory and validate the archive.
- **Role conflict:** review `globals.sql`; restore only missing roles, then apply recorded ownership.
- **Certificate/routing failure:** validate Nginx and certificate paths before starting the proxy; do not change DNS as part of an unapproved rollback.
- **Newer data would be lost:** retain and checksum the mandatory pre-rollback emergency snapshot before replacing the live state.

