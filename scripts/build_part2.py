#!/usr/bin/env python3
"""Part 2 - saas_tenant_manager module: __manifest__, __init__, models"""
import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('129.121.98.243', username='root', password='Mh@01007121878')

def upload(path, content):
    sftp = ssh.open_sftp()
    with sftp.open(path, 'w') as f:
        f.write(content)
    sftp.close()
    print(f'  ✅ {path}')

BASE = '/opt/odoo-saas/addons/saas_tenant_manager'

# ─────────────────────────────────────────────────────
# __manifest__.py
# ─────────────────────────────────────────────────────
MANIFEST = """{
    'name': 'SaaS Tenant Manager',
    'version': '17.0.1.0.0',
    'category': 'Administration',
    'summary': 'Multi-tenant SaaS management for Odoo',
    'description': '''
        Complete SaaS management module for Odoo Community.
        - Create and manage tenants
        - Database-per-tenant isolation
        - Subscription plans
        - Automated backups
        - Tenant monitoring
    ''',
    'author': 'SaaS Platform',
    'website': 'https://admin.myerp.com',
    'depends': ['base', 'mail', 'web'],
    'data': [
        'security/saas_security.xml',
        'security/ir.model.access.csv',
        'data/saas_plan_data.xml',
        'data/saas_cron.xml',
        'views/saas_plan_views.xml',
        'views/saas_backup_views.xml',
        'views/saas_tenant_views.xml',
        'views/saas_menu.xml',
        'wizards/create_tenant_wizard.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'images': ['static/description/icon.png'],
}
"""

# ─────────────────────────────────────────────────────
# __init__.py
# ─────────────────────────────────────────────────────
INIT = """from . import models
from . import controllers
from . import wizards
"""

MODELS_INIT = """from . import saas_plan
from . import saas_tenant
from . import saas_backup
"""

# ─────────────────────────────────────────────────────
# models/saas_plan.py
# ─────────────────────────────────────────────────────
SAAS_PLAN = """import logging
from odoo import models, fields, api
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class SaasPlan(models.Model):
    _name = 'saas.plan'
    _description = 'SaaS Subscription Plan'
    _order = 'monthly_price asc'

    name = fields.Char(string='Plan Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True)
    active = fields.Boolean(default=True)
    color = fields.Integer(string='Color')

    # Limits
    max_users = fields.Integer(string='Max Users', default=5)
    max_storage_mb = fields.Integer(string='Max Storage (MB)', default=1024)
    trial_days = fields.Integer(string='Trial Days', default=14)

    # Pricing
    monthly_price = fields.Float(string='Monthly Price (SAR)', digits=(10, 2))
    yearly_price = fields.Float(string='Yearly Price (SAR)', digits=(10, 2))

    # Modules allowed on this plan
    allowed_modules = fields.Text(
        string='Allowed Modules',
        help='Comma-separated list of module names to install on tenant creation'
    )

    # Description
    description = fields.Html(string='Description')
    features = fields.Text(string='Features (one per line)')

    # Stats
    tenant_count = fields.Integer(compute='_compute_tenant_count', string='Tenants')

    def _compute_tenant_count(self):
        for plan in self:
            plan.tenant_count = self.env['saas.tenant'].search_count([
                ('plan_id', '=', plan.id)
            ])

    @api.constrains('max_users')
    def _check_max_users(self):
        for plan in self:
            if plan.max_users < 1:
                raise ValidationError('Max users must be at least 1.')

    def get_modules_list(self):
        \"\"\"Return list of modules to install.\"\"\"
        self.ensure_one()
        if not self.allowed_modules:
            return ['base']
        mods = [m.strip() for m in self.allowed_modules.split(',') if m.strip()]
        if 'base' not in mods:
            mods.insert(0, 'base')
        return mods

    def action_view_tenants(self):
        return {
            'type': 'ir.actions.act_window',
            'name': f'Tenants — {self.name}',
            'res_model': 'saas.tenant',
            'view_mode': 'tree,form,kanban',
            'domain': [('plan_id', '=', self.id)],
            'context': {'default_plan_id': self.id},
        }
"""

# ─────────────────────────────────────────────────────
# models/saas_tenant.py
# ─────────────────────────────────────────────────────
SAAS_TENANT = """import logging
import re
import os
import subprocess
import psycopg2
from datetime import date, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import config

_logger = logging.getLogger(__name__)

DB_HOST = os.environ.get('HOST', 'postgres')
DB_PORT = int(os.environ.get('PORT', 5432))
DB_USER = os.environ.get('USER', 'odoo')
DB_PASS = os.environ.get('PASSWORD', 'odoo_pg_pass_2024')


class SaasTenant(models.Model):
    _name = 'saas.tenant'
    _description = 'SaaS Tenant'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    # ── Basic Info ──────────────────────────────────────
    name = fields.Char(string='Tenant Name', required=True, tracking=True)
    customer_name = fields.Char(string='Customer Name', required=True, tracking=True)
    customer_email = fields.Char(string='Customer Email', required=True, tracking=True)
    company_name = fields.Char(string='Company Name', required=True)
    phone = fields.Char(string='Phone')

    # ── Domain & Database ────────────────────────────────
    subdomain = fields.Char(
        string='Subdomain', required=True,
        help='e.g. "client1" for client1.myerp.com'
    )
    custom_domain = fields.Char(string='Custom Domain', help='e.g. erp.client.com')
    db_name = fields.Char(string='Database Name', readonly=True)
    db_user = fields.Char(string='DB User', readonly=True)
    tenant_url = fields.Char(string='Tenant URL', compute='_compute_tenant_url', store=True)

    # ── Admin Credentials ────────────────────────────────
    admin_login = fields.Char(string='Admin Login', default='admin')
    admin_password = fields.Char(string='Admin Password')

    # ── Plan & Status ────────────────────────────────────
    plan_id = fields.Many2one('saas.plan', string='Subscription Plan', tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('provisioning', 'Provisioning'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    # ── Dates ────────────────────────────────────────────
    expiry_date = fields.Date(string='Expiry Date', tracking=True)
    last_backup_date = fields.Datetime(string='Last Backup')
    last_login_date = fields.Datetime(string='Last Login')

    # ── Monitoring ───────────────────────────────────────
    db_size_mb = fields.Float(string='DB Size (MB)', readonly=True)
    filestore_size_mb = fields.Float(string='Filestore Size (MB)', readonly=True)
    user_count = fields.Integer(string='Users', readonly=True)
    installed_modules = fields.Text(string='Installed Modules', readonly=True)

    # ── Backups ──────────────────────────────────────────
    backup_ids = fields.One2many('saas.backup', 'tenant_id', string='Backups')
    backup_count = fields.Integer(compute='_compute_backup_count')

    # ── Template ─────────────────────────────────────────
    template_db = fields.Char(
        string='Template Database',
        help='Duplicate this DB when creating tenant. Leave empty to create fresh.'
    )

    # ── Notes ────────────────────────────────────────────
    notes = fields.Html(string='Notes')
    color = fields.Integer(string='Color')

    # ────────────────────────────────────────────────────
    # Computed
    # ────────────────────────────────────────────────────
    @api.depends('subdomain', 'custom_domain')
    def _compute_tenant_url(self):
        base = 'myerp.com'
        for t in self:
            if t.custom_domain:
                t.tenant_url = f'https://{t.custom_domain}'
            elif t.subdomain:
                t.tenant_url = f'https://{t.subdomain}.{base}'
            else:
                t.tenant_url = ''

    def _compute_backup_count(self):
        for t in self:
            t.backup_count = len(t.backup_ids)

    # ────────────────────────────────────────────────────
    # Constraints
    # ────────────────────────────────────────────────────
    @api.constrains('subdomain')
    def _check_subdomain(self):
        pattern = re.compile(r'^[a-z0-9][a-z0-9\\-]{1,30}[a-z0-9]$')
        for t in self:
            if not pattern.match(t.subdomain or ''):
                raise ValidationError(
                    'Subdomain must be lowercase alphanumeric (2-32 chars), '
                    'hyphens allowed but not at start/end.'
                )

    @api.constrains('customer_email')
    def _check_email(self):
        pattern = re.compile(r'^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$')
        for t in self:
            if t.customer_email and not pattern.match(t.customer_email):
                raise ValidationError('Invalid email address.')

    # ────────────────────────────────────────────────────
    # Private helpers
    # ────────────────────────────────────────────────────
    def _get_pg_conn(self, dbname='postgres'):
        \"\"\"Return a psycopg2 connection to the given database.\"\"\"
        return psycopg2.connect(
            host=DB_HOST, port=DB_PORT,
            user=DB_USER, password=DB_PASS,
            dbname=dbname
        )

    def _sanitize_db_name(self, name):
        \"\"\"Return a safe PostgreSQL identifier.\"\"\"
        safe = re.sub(r'[^a-z0-9_]', '_', name.lower())
        return safe[:63]

    def _db_exists(self, db_name):
        conn = self._get_pg_conn()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
        exists = cur.fetchone() is not None
        cur.close(); conn.close()
        return exists

    def _get_filestore_path(self, db_name):
        data_dir = config.get('data_dir', '/var/lib/odoo')
        return os.path.join(data_dir, 'filestore', db_name)

    # ────────────────────────────────────────────────────
    # Action: Create Tenant
    # ────────────────────────────────────────────────────
    def action_create_tenant(self):
        self.ensure_one()
        if self.state not in ('draft',):
            raise UserError('Can only provision a tenant in Draft state.')

        db_name = self._sanitize_db_name(f'tenant_{self.subdomain}')

        if self._db_exists(db_name):
            raise UserError(f'Database "{db_name}" already exists.')

        self.write({'state': 'provisioning', 'db_name': db_name, 'db_user': DB_USER})
        self._create_database(db_name)
        self._create_filestore(db_name)
        self._initialize_odoo_db(db_name)

        expiry = (date.today() + timedelta(days=self.plan_id.trial_days or 14)) if self.plan_id else False

        self.write({
            'state': 'active',
            'expiry_date': expiry,
        })
        self._update_stats()
        self.message_post(body=f'Tenant created. Database: {db_name}, URL: {self.tenant_url}')
        _logger.info('Tenant %s created — DB: %s', self.name, db_name)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Tenant Created'),
                'message': f'Tenant {self.name} is now active at {self.tenant_url}',
                'type': 'success',
                'sticky': False,
            }
        }

    def _create_database(self, db_name):
        \"\"\"Create a new PostgreSQL database, optionally from a template.\"\"\"
        conn = self._get_pg_conn()
        conn.autocommit = True
        cur = conn.cursor()
        try:
            if self.template_db and self._db_exists(self.template_db):
                _logger.info('Creating DB %s from template %s', db_name, self.template_db)
                # Terminate connections to template before copying
                cur.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = %s AND pid <> pg_backend_pid()",
                    (self.template_db,)
                )
                cur.execute(
                    f'CREATE DATABASE "{db_name}" TEMPLATE "{self.template_db}" '
                    f'OWNER "{DB_USER}" ENCODING \'UTF8\''
                )
            else:
                _logger.info('Creating fresh DB: %s', db_name)
                cur.execute(
                    f'CREATE DATABASE "{db_name}" OWNER "{DB_USER}" '
                    f'ENCODING \'UTF8\' LC_COLLATE \'en_US.UTF-8\' LC_CTYPE \'en_US.UTF-8\' TEMPLATE template0'
                )
        except Exception as e:
            _logger.error('Failed to create database %s: %s', db_name, str(e))
            raise UserError(f'Failed to create database: {str(e)}')
        finally:
            cur.close(); conn.close()

    def _create_filestore(self, db_name):
        \"\"\"Create filestore directory for the tenant.\"\"\"
        path = self._get_filestore_path(db_name)
        os.makedirs(path, exist_ok=True)
        os.chmod(path, 0o755)
        _logger.info('Filestore created at %s', path)

    def _initialize_odoo_db(self, db_name):
        \"\"\"Initialize the Odoo database via odoo-bin.\"\"\"
        modules = 'base'
        if self.plan_id:
            modules = ','.join(self.plan_id.get_modules_list())

        cmd = [
            'odoo', '--config=/etc/odoo/odoo.conf',
            f'--database={db_name}',
            '--init=' + modules,
            '--without-demo=all',
            '--stop-after-init',
            '--no-http',
        ]

        if self.company_name:
            cmd += [f'--company={self.company_name}']

        _logger.info('Initializing Odoo DB %s with modules: %s', db_name, modules)
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300
            )
            if result.returncode != 0:
                _logger.error('Odoo init failed: %s', result.stderr[-2000:])
                raise UserError('Odoo initialization failed. Check logs.')
        except subprocess.TimeoutExpired:
            raise UserError('Odoo initialization timed out (>5 min).')

    # ────────────────────────────────────────────────────
    # Action: Suspend
    # ────────────────────────────────────────────────────
    def action_suspend(self):
        for t in self:
            if t.state != 'active':
                raise UserError(f'{t.name} is not active.')
            t.write({'state': 'suspended'})
            t.message_post(body='Tenant suspended.')
            _logger.info('Tenant %s suspended', t.name)

    # ────────────────────────────────────────────────────
    # Action: Reactivate
    # ────────────────────────────────────────────────────
    def action_reactivate(self):
        for t in self:
            if t.state != 'suspended':
                raise UserError(f'{t.name} is not suspended.')
            t.write({'state': 'active'})
            t.message_post(body='Tenant reactivated.')
            _logger.info('Tenant %s reactivated', t.name)

    # ────────────────────────────────────────────────────
    # Action: Backup
    # ────────────────────────────────────────────────────
    def action_backup(self):
        self.ensure_one()
        if not self.db_name:
            raise UserError('No database to backup.')

        import datetime, shutil
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = f'/opt/odoo-saas/backups/{self.db_name}'
        os.makedirs(backup_dir, exist_ok=True)

        # Database dump
        dump_file = f'{backup_dir}/{self.db_name}_{ts}.sql.gz'
        env = os.environ.copy()
        env['PGPASSWORD'] = DB_PASS

        cmd = (
            f'pg_dump -h {DB_HOST} -p {DB_PORT} -U {DB_USER} '
            f'"{self.db_name}" | gzip > "{dump_file}"'
        )
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env)
        if result.returncode != 0:
            raise UserError(f'Database backup failed: {result.stderr}')

        # Filestore backup
        fs_src = self._get_filestore_path(self.db_name)
        fs_dst = f'{backup_dir}/{self.db_name}_filestore_{ts}.tar.gz'
        if os.path.exists(fs_src):
            subprocess.run(
                ['tar', '-czf', fs_dst, '-C', os.path.dirname(fs_src), os.path.basename(fs_src)],
                check=True
            )

        now = fields.Datetime.now()
        self.env['saas.backup'].create({
            'tenant_id': self.id,
            'db_dump_path': dump_file,
            'filestore_path': fs_dst if os.path.exists(fs_dst) else False,
            'backup_date': now,
            'size_mb': os.path.getsize(dump_file) / (1024 * 1024) if os.path.exists(dump_file) else 0,
        })
        self.write({'last_backup_date': now})
        self.message_post(body=f'Backup created: {dump_file}')
        _logger.info('Backup created for tenant %s: %s', self.name, dump_file)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Backup Complete'),
                'message': f'Backup saved to {dump_file}',
                'type': 'success',
            }
        }

    # ────────────────────────────────────────────────────
    # Action: Delete
    # ────────────────────────────────────────────────────
    def action_delete_tenant(self):
        self.ensure_one()
        # Backup first
        if self.db_name and self._db_exists(self.db_name):
            try:
                self.action_backup()
            except Exception as e:
                _logger.warning('Pre-deletion backup failed: %s', e)

        # Drop DB
        if self.db_name:
            self._drop_database(self.db_name)

        # Remove filestore
        fs_path = self._get_filestore_path(self.db_name or self.subdomain)
        if os.path.exists(fs_path):
            import shutil
            shutil.rmtree(fs_path, ignore_errors=True)

        self.write({'state': 'cancelled'})
        self.message_post(body='Tenant deleted. Database and filestore removed.')
        _logger.info('Tenant %s deleted', self.name)

    def _drop_database(self, db_name):
        conn = self._get_pg_conn()
        conn.autocommit = True
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (db_name,)
            )
            cur.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
            _logger.info('Database %s dropped', db_name)
        except Exception as e:
            raise UserError(f'Failed to drop database: {str(e)}')
        finally:
            cur.close(); conn.close()

    # ────────────────────────────────────────────────────
    # Update Stats
    # ────────────────────────────────────────────────────
    def _update_stats(self):
        for t in self:
            if not t.db_name or not t._db_exists(t.db_name):
                continue
            try:
                conn = t._get_pg_conn(t.db_name)
                cur = conn.cursor()

                # DB size
                cur.execute(
                    "SELECT pg_database_size(%s) / 1048576.0",
                    (t.db_name,)
                )
                db_size = cur.fetchone()[0] or 0

                # User count
                cur.execute("SELECT COUNT(*) FROM res_users WHERE active = true")
                user_count = cur.fetchone()[0] or 0

                # Installed modules
                cur.execute(
                    "SELECT name FROM ir_module_module WHERE state = 'installed' ORDER BY name"
                )
                modules = ', '.join(r[0] for r in cur.fetchall())

                cur.close(); conn.close()

                # Filestore size
                fs_path = t._get_filestore_path(t.db_name)
                fs_size = 0
                if os.path.exists(fs_path):
                    for root, dirs, files in os.walk(fs_path):
                        for f in files:
                            try:
                                fs_size += os.path.getsize(os.path.join(root, f))
                            except OSError:
                                pass
                    fs_size /= (1024 * 1024)

                t.write({
                    'db_size_mb': round(db_size, 2),
                    'user_count': user_count,
                    'installed_modules': modules,
                    'filestore_size_mb': round(fs_size, 2),
                })
            except Exception as e:
                _logger.error('Stats update failed for %s: %s', t.db_name, str(e))

    def action_update_stats(self):
        self._update_stats()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Stats Updated'),
                'type': 'success',
            }
        }

    def action_open_tenant(self):
        self.ensure_one()
        if not self.tenant_url:
            raise UserError('Tenant URL not available.')
        return {'type': 'ir.actions.act_url', 'url': self.tenant_url, 'target': 'new'}

    def action_view_backups(self):
        return {
            'type': 'ir.actions.act_window',
            'name': f'Backups — {self.name}',
            'res_model': 'saas.backup',
            'view_mode': 'tree,form',
            'domain': [('tenant_id', '=', self.id)],
            'context': {'default_tenant_id': self.id},
        }

    # ────────────────────────────────────────────────────
    # Scheduled Actions
    # ────────────────────────────────────────────────────
    @api.model
    def cron_backup_all_tenants(self):
        tenants = self.search([('state', '=', 'active'), ('db_name', '!=', False)])
        _logger.info('Cron: backing up %d tenants', len(tenants))
        for t in tenants:
            try:
                t.action_backup()
            except Exception as e:
                _logger.error('Backup failed for %s: %s', t.name, str(e))

    @api.model
    def cron_update_all_stats(self):
        tenants = self.search([('state', '=', 'active'), ('db_name', '!=', False)])
        tenants._update_stats()

    @api.model
    def cron_check_expired_tenants(self):
        today = date.today()
        expired = self.search([
            ('state', '=', 'active'),
            ('expiry_date', '<', today),
            ('expiry_date', '!=', False),
        ])
        for t in expired:
            t.write({'state': 'expired'})
            t.message_post(body='Tenant suspended: subscription expired.')
            _logger.info('Tenant %s expired', t.name)

        # Reminder: 7 days before expiry
        warn_date = today + timedelta(days=7)
        soon = self.search([
            ('state', '=', 'active'),
            ('expiry_date', '=', warn_date),
        ])
        for t in soon:
            t.message_post(body=f'Reminder: subscription expires on {t.expiry_date}.')
"""

# ─────────────────────────────────────────────────────
# models/saas_backup.py
# ─────────────────────────────────────────────────────
SAAS_BACKUP = """import os
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SaasBackup(models.Model):
    _name = 'saas.backup'
    _description = 'Tenant Backup Record'
    _order = 'backup_date desc'

    tenant_id = fields.Many2one('saas.tenant', string='Tenant', required=True, ondelete='cascade')
    backup_date = fields.Datetime(string='Backup Date', default=fields.Datetime.now)
    db_dump_path = fields.Char(string='Database Dump Path')
    filestore_path = fields.Char(string='Filestore Archive Path')
    size_mb = fields.Float(string='Size (MB)', digits=(10, 2))
    notes = fields.Char(string='Notes')
    state = fields.Selection([
        ('done', 'Done'),
        ('restored', 'Restored'),
        ('deleted', 'Deleted'),
    ], default='done')

    def action_restore(self):
        \"\"\"Restore tenant from this backup.\"\"\"
        self.ensure_one()
        t = self.tenant_id
        if not self.db_dump_path or not os.path.exists(self.db_dump_path):
            raise UserError('Backup file not found.')

        import subprocess
        env = os.environ.copy()
        env['PGPASSWORD'] = t._get_pg_conn.__func__.__globals__.get('DB_PASS', 'odoo_pg_pass_2024')

        db_host = os.environ.get('HOST', 'postgres')
        db_port = os.environ.get('PORT', '5432')
        db_user = os.environ.get('USER', 'odoo')
        db_pass = os.environ.get('PASSWORD', 'odoo_pg_pass_2024')
        env['PGPASSWORD'] = db_pass

        # Drop existing and recreate
        conn = __import__('psycopg2').connect(
            host=db_host, port=db_port, user=db_user,
            password=db_pass, dbname='postgres'
        )
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid()",
            (t.db_name,)
        )
        cur.execute(f'DROP DATABASE IF EXISTS "{t.db_name}"')
        cur.execute(
            f'CREATE DATABASE "{t.db_name}" OWNER "{db_user}" ENCODING \\'UTF8\\''
        )
        cur.close(); conn.close()

        # Restore
        cmd = f'gunzip -c "{self.db_dump_path}" | psql -h {db_host} -p {db_port} -U {db_user} "{t.db_name}"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env)
        if result.returncode != 0:
            raise UserError(f'Restore failed: {result.stderr[:500]}')

        self.write({'state': 'restored'})
        t.message_post(body=f'Database restored from backup: {self.db_dump_path}')
        _logger.info('Tenant %s restored from %s', t.name, self.db_dump_path)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Restore Complete'),
                'message': f'Tenant {t.name} restored successfully.',
                'type': 'success',
            }
        }

    def action_delete_backup(self):
        \"\"\"Delete backup files from disk.\"\"\"
        self.ensure_one()
        for path in [self.db_dump_path, self.filestore_path]:
            if path and os.path.exists(path):
                os.remove(path)
                _logger.info('Deleted backup file: %s', path)
        self.write({'state': 'deleted'})
"""

print('── Uploading module files ──')
upload(f'{BASE}/__manifest__.py', MANIFEST)
upload(f'{BASE}/__init__.py', INIT)
upload(f'{BASE}/models/__init__.py', MODELS_INIT)
upload(f'{BASE}/models/saas_plan.py', SAAS_PLAN)
upload(f'{BASE}/models/saas_tenant.py', SAAS_TENANT)
upload(f'{BASE}/models/saas_backup.py', SAAS_BACKUP)
print('\n✅ Part 2 done!')
ssh.close()
