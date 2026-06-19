import json
import logging
from datetime import datetime
from odoo import http
from odoo.http import request
from odoo.addons.saas_website.services.alert_notifier import AlertNotifier
from odoo.addons.saas_website.services.error_handler import PlatformError

_logger = logging.getLogger(__name__)


class TenantUpgradeService:
    """Handle tenant edition upgrades (Community → Enterprise)."""

    def __init__(self, env):
        self.env = env

    def can_upgrade(self, tenant):
        """Check if tenant can be upgraded."""
        if not tenant:
            return False, "Tenant not found"

        if tenant.edition == 'enterprise':
            return False, "Already on Enterprise"

        if tenant.state not in ['trial', 'active']:
            return False, f"Cannot upgrade tenant in {tenant.state} state"

        return True, None

    def create_upgrade_request(self, tenant_id, new_plan_id=None, coupon_code=None):
        """Create upgrade request for admin approval."""
        try:
            tenant = self.env['saas.tenant'].browse(tenant_id)
            can_upgrade, error_msg = self.can_upgrade(tenant)

            if not can_upgrade:
                raise PlatformError('UPGRADE_NOT_ALLOWED', error_msg)

            upgrade = self.env['saas.tenant.upgrade'].create({
                'tenant_id': tenant_id,
                'from_edition': tenant.edition,
                'to_edition': 'enterprise',
                'from_plan_id': tenant.plan_id.id,
                'to_plan_id': new_plan_id or tenant.plan_id.id,
                'status': 'pending',
                'coupon_code': coupon_code,
                'requested_date': datetime.now(),
                'requested_by': self.env.user.id,
            })

            # Notify admin
            AlertNotifier.notify_error(
                'TENANT_UPGRADE_REQUEST',
                f"Upgrade request from {tenant.subdomain}: {tenant.edition} → enterprise",
                'info',
                {'tenant_id': tenant_id, 'upgrade_id': upgrade.id}
            )

            return {'success': True, 'upgrade_id': upgrade.id}

        except Exception as e:
            _logger.error(f"Upgrade request failed: {e}")
            AlertNotifier.notify_error('UPGRADE_REQUEST_FAILED', str(e), 'warning')
            raise

    def approve_upgrade(self, upgrade_id):
        """Admin approves tenant upgrade."""
        try:
            upgrade = self.env['saas.tenant.upgrade'].browse(upgrade_id)

            if upgrade.status != 'pending':
                raise PlatformError('UPGRADE_INVALID_STATE', f"Upgrade is {upgrade.status}")

            tenant = upgrade.tenant_id

            # Step 1: Backup current database
            _logger.info(f"Backing up {tenant.subdomain} database before upgrade...")
            backup_file = self._backup_database(tenant)

            # Step 2: Migrate to Enterprise edition
            _logger.info(f"Migrating {tenant.subdomain} to Enterprise...")
            migration_result = self._migrate_to_enterprise(tenant, upgrade)

            if not migration_result['success']:
                raise PlatformError('MIGRATION_FAILED', migration_result['error'])

            # Step 3: Update tenant record
            tenant.write({
                'edition': 'enterprise',
                'plan_id': upgrade.to_plan_id.id,
                'upgraded_date': datetime.now(),
            })

            # Step 4: Update upgrade record
            upgrade.write({
                'status': 'completed',
                'completed_date': datetime.now(),
                'backup_file': backup_file,
                'notes': f"Migration completed: {migration_result['details']}",
            })

            # Step 5: Notify tenant & admin
            self._send_upgrade_notification(tenant, upgrade)

            AlertNotifier.notify_recovery(
                'TENANT_UPGRADE',
                f"{tenant.subdomain}",
                'success'
            )

            return {'success': True, 'details': migration_result}

        except Exception as e:
            _logger.error(f"Upgrade approval failed: {e}")
            upgrade.write({
                'status': 'failed',
                'error_message': str(e),
            })
            AlertNotifier.notify_error('UPGRADE_FAILED', str(e), 'critical',
                                      {'upgrade_id': upgrade_id, 'tenant_id': upgrade.tenant_id.id})
            raise

    def reject_upgrade(self, upgrade_id, reason=''):
        """Admin rejects upgrade request."""
        try:
            upgrade = self.env['saas.tenant.upgrade'].write({
                'status': 'rejected',
                'rejection_reason': reason,
                'rejected_date': datetime.now(),
            })

            # Notify tenant
            self._send_rejection_notification(upgrade.tenant_id, reason)

            return {'success': True}

        except Exception as e:
            _logger.error(f"Upgrade rejection failed: {e}")
            raise

    def _backup_database(self, tenant):
        """Backup tenant database before migration."""
        import subprocess
        from datetime import datetime as dt

        backup_dir = '/opt/backups/pre-upgrades'
        timestamp = dt.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f"{backup_dir}/{tenant.subdomain}_{timestamp}.sql.gz"

        try:
            subprocess.run(
                f"docker exec odoo_saas_postgres pg_dump -U odoo {tenant.database} | gzip > {backup_file}",
                shell=True,
                check=True,
                timeout=300
            )
            _logger.info(f"Backup created: {backup_file}")
            return backup_file

        except Exception as e:
            _logger.error(f"Backup failed: {e}")
            raise PlatformError('BACKUP_FAILED', f"Could not backup database: {e}")

    def _migrate_to_enterprise(self, tenant, upgrade):
        """Migrate tenant to Enterprise edition."""
        try:
            import subprocess

            old_db = tenant.database
            new_db = f"{old_db}_ent"

            # Step 1: Rename current database
            subprocess.run(
                f"docker exec odoo_saas_postgres psql -U odoo -c 'ALTER DATABASE {old_db} RENAME TO {old_db}_backup'",
                shell=True,
                check=True
            )

            # Step 2: Create new Enterprise database
            subprocess.run(
                f"docker exec odoo_saas_postgres createdb -U odoo -T template0 {new_db}",
                shell=True,
                check=True
            )

            # Step 3: Copy data from backup
            subprocess.run(
                f"docker exec odoo_saas_postgres pg_dump -U odoo {old_db}_backup | docker exec -i odoo_saas_postgres psql -U odoo {new_db}",
                shell=True,
                check=True
            )

            # Step 4: Update tenant database reference
            tenant.write({'database': new_db})

            # Step 5: Restart Odoo to load Enterprise modules
            subprocess.run(['docker', 'restart', 'odoo_saas_ent'], check=True)

            return {
                'success': True,
                'details': f"Migrated from {old_db} to {new_db}"
            }

        except Exception as e:
            _logger.error(f"Migration failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _send_upgrade_notification(self, tenant, upgrade):
        """Send email to tenant about successful upgrade."""
        try:
            template = self.env.ref('saas_website.email_tenant_upgrade_success')
            template.send_mail(tenant.id, force_send=True)

            _logger.info(f"Upgrade notification sent to {tenant.subdomain}")
        except Exception as e:
            _logger.error(f"Failed to send upgrade notification: {e}")

    def _send_rejection_notification(self, tenant, reason):
        """Send email to tenant about upgrade rejection."""
        try:
            self.env['mail.mail'].create({
                'subject': 'Upgrade Request Rejected',
                'body_html': f"""
                <p>مرحباً {tenant.name},</p>
                <p>عذراً، تم رفض طلب الترقية للإصدار Enterprise:</p>
                <p><strong>السبب:</strong> {reason}</p>
                <p>يرجى التواصل معنا للمزيد من المعلومات.</p>
                """,
                'email_to': tenant.contact_email,
            }).send()
        except Exception as e:
            _logger.error(f"Failed to send rejection notification: {e}")

    def get_upgrade_history(self, tenant_id):
        """Get upgrade history for tenant."""
        return self.env['saas.tenant.upgrade'].search([
            ('tenant_id', '=', tenant_id),
        ], order='requested_date DESC')

    def get_pending_upgrades(self):
        """Get all pending upgrade requests."""
        return self.env['saas.tenant.upgrade'].search([
            ('status', '=', 'pending'),
        ], order='requested_date ASC')

    def auto_approve_upgrade(self, upgrade_id):
        """Auto-approve upgrade if criteria met (admin config)."""
        upgrade = self.env['saas.tenant.upgrade'].browse(upgrade_id)
        config = self.env['saas.config'].sudo()._get_config()

        # Check if auto-approval is enabled
        if not config.auto_approve_upgrades:
            return False

        # Check tenant status
        if upgrade.tenant_id.balance < 0:
            return False  # Outstanding balance

        # Auto-approve
        self.approve_upgrade(upgrade_id)
        return True
