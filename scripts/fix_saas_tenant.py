#!/usr/bin/env python3
"""Rewrite saas_tenant.py with clean syntax"""
import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('129.121.98.243', username='root', password='Mh@01007121878')

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

    # Basic
    name            = fields.Char(string='Tenant Name', required=True, tracking=True)
    customer_name   = fields.Char(string='Customer Name', required=True, tracking=True)
    customer_email  = fields.Char(string='Customer Email', required=True, tracking=True)
    company_name    = fields.Char(string='Company Name', required=True)
    phone           = fields.Char(string='Phone')

    # Domain
    subdomain     = fields.Char(string='Subdomain', required=True)
    custom_domain = fields.Char(string='Custom Domain')
    db_name       = fields.Char(string='Database Name', readonly=True)
    db_user       = fields.Char(string='DB User', readonly=True)
    tenant_url    = fields.Char(string='Tenant URL', compute='_compute_tenant_url', store=True)

    # Admin
    admin_login    = fields.Char(string='Admin Login', default='admin')
    admin_password = fields.Char(string='Admin Password')

    # Plan & Status
    plan_id = fields.Many2one('saas.plan', string='Subscription Plan', tracking=True)
    state   = fields.Selection([
        ('draft',        'Draft'),
        ('provisioning', 'Provisioning'),
        ('active',       'Active'),
        ('suspended',    'Suspended'),
        ('expired',      'Expired'),
        ('cancelled',    'Cancelled'),
    ], default='draft', tracking=True)

    # Dates
    expiry_date     = fields.Date(string='Expiry Date', tracking=True)
    last_backup_date = fields.Datetime(string='Last Backup')
    last_login_date  = fields.Datetime(string='Last Login')

    # Monitoring
    db_size_mb        = fields.Float(string='DB Size (MB)', readonly=True)
    filestore_size_mb = fields.Float(string='Filestore Size (MB)', readonly=True)
    user_count        = fields.Integer(string='Users', readonly=True)
    installed_modules = fields.Text(string='Installed Modules', readonly=True)

    # Backups
    backup_ids   = fields.One2many('saas.backup', 'tenant_id', string='Backups')
    backup_count = fields.Integer(compute='_compute_backup_count')

    # Template
    template_db = fields.Char(string='Template Database')

    # Notes
    notes = fields.Html(string='Notes')
    color = fields.Integer(string='Color')

    # ── Computed ──────────────────────────────────────────────────────────
    @api.depends('subdomain', 'custom_domain')
    def _compute_tenant_url(self):
        base = 'clickbulid.com'
        for t in self:
            if t.custom_domain:
                t.tenant_url = 'https://' + t.custom_domain
            elif t.subdomain:
                t.tenant_url = 'https://' + t.subdomain + '.' + base
            else:
                t.tenant_url = ''

    def _compute_backup_count(self):
        for t in self:
            t.backup_count = len(t.backup_ids)

    # ── Constraints ────────────────────────────────────────────────────────
    @api.constrains('subdomain')
    def _check_subdomain(self):
        pattern = re.compile(r'^[a-z0-9][a-z0-9\\-]{1,30}[a-z0-9]$')
        for t in self:
            if not pattern.match(t.subdomain or ''):
                raise ValidationError(
                    'Subdomain must be 2-32 chars, lowercase, alphanumeric, hyphens allowed.'
                )

    @api.constrains('customer_email')
    def _check_email(self):
        pattern = re.compile(r'^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$')
        for t in self:
            if t.customer_email and not pattern.match(t.customer_email):
                raise ValidationError('Invalid email address.')

    # ── Helpers ────────────────────────────────────────────────────────────
    def _get_pg_conn(self, dbname='postgres'):
        return psycopg2.connect(
            host=DB_HOST, port=DB_PORT,
            user=DB_USER, password=DB_PASS,
            dbname=dbname
        )

    def _sanitize_db_name(self, name):
        safe = re.sub(r'[^a-z0-9_]', '_', name.lower())
        return safe[:63]

    def _db_exists(self, db_name):
        conn = self._get_pg_conn()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
        exists = cur.fetchone() is not None
        cur.close()
        conn.close()
        return exists

    def _get_filestore_path(self, db_name):
        data_dir = config.get('data_dir', '/var/lib/odoo')
        return os.path.join(data_dir, 'filestore', db_name)

    # ── Create Tenant ──────────────────────────────────────────────────────
    def action_create_tenant(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError('Can only provision a Draft tenant.')

        db_name = self._sanitize_db_name('tenant_' + self.subdomain)
        if self._db_exists(db_name):
            raise UserError('Database "' + db_name + '" already exists.')

        self.write({'state': 'provisioning', 'db_name': db_name, 'db_user': DB_USER})
        self._create_database(db_name)
        self._create_filestore(db_name)
        self._initialize_odoo_db(db_name)

        expiry = False
        if self.plan_id and self.plan_id.trial_days:
            expiry = date.today() + timedelta(days=self.plan_id.trial_days)

        self.write({'state': 'active', 'expiry_date': expiry})
        self._update_stats()
        self.message_post(body='Tenant created. DB: ' + db_name + ' URL: ' + (self.tenant_url or ''))
        _logger.info('Tenant %s created — DB: %s', self.name, db_name)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Tenant Created'),
                'message': 'Tenant ' + self.name + ' is now active at ' + (self.tenant_url or ''),
                'type': 'success',
                'sticky': False,
            }
        }

    def _create_database(self, db_name):
        conn = self._get_pg_conn()
        conn.autocommit = True
        cur = conn.cursor()
        try:
            if self.template_db and self._db_exists(self.template_db):
                _logger.info('Creating DB %s from template %s', db_name, self.template_db)
                cur.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = %s AND pid <> pg_backend_pid()",
                    (self.template_db,)
                )
                sql = (
                    'CREATE DATABASE "' + db_name + '"'
                    ' TEMPLATE "' + self.template_db + '"'
                    ' OWNER "' + DB_USER + '" ENCODING \'UTF8\''
                )
                cur.execute(sql)
            else:
                _logger.info('Creating fresh DB: %s', db_name)
                sql = (
                    'CREATE DATABASE "' + db_name + '"'
                    ' OWNER "' + DB_USER + '"'
                    " ENCODING 'UTF8'"
                    " LC_COLLATE 'en_US.UTF-8'"
                    " LC_CTYPE 'en_US.UTF-8'"
                    ' TEMPLATE template0'
                )
                cur.execute(sql)
        except Exception as e:
            _logger.error('Failed to create database %s: %s', db_name, str(e))
            raise UserError('Failed to create database: ' + str(e))
        finally:
            cur.close()
            conn.close()

    def _create_filestore(self, db_name):
        path = self._get_filestore_path(db_name)
        os.makedirs(path, exist_ok=True)
        os.chmod(path, 0o755)
        _logger.info('Filestore created at %s', path)

    def _initialize_odoo_db(self, db_name):
        modules = 'base'
        if self.plan_id:
            modules = ','.join(self.plan_id.get_modules_list())

        cmd = [
            'odoo', '--config=/etc/odoo/odoo.conf',
            '--database=' + db_name,
            '--init=' + modules,
            '--without-demo=all',
            '--stop-after-init',
            '--no-http',
        ]
        _logger.info('Initializing Odoo DB %s with modules: %s', db_name, modules)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                _logger.error('Odoo init failed: %s', result.stderr[-2000:])
                raise UserError('Odoo initialization failed. Check logs.')
        except subprocess.TimeoutExpired:
            raise UserError('Odoo initialization timed out (>5 min).')

    # ── Suspend / Reactivate ───────────────────────────────────────────────
    def action_suspend(self):
        for t in self:
            if t.state != 'active':
                raise UserError(t.name + ' is not active.')
            t.write({'state': 'suspended'})
            t.message_post(body='Tenant suspended.')

    def action_reactivate(self):
        for t in self:
            if t.state != 'suspended':
                raise UserError(t.name + ' is not suspended.')
            t.write({'state': 'active'})
            t.message_post(body='Tenant reactivated.')

    # ── Backup ─────────────────────────────────────────────────────────────
    def action_backup(self):
        self.ensure_one()
        if not self.db_name:
            raise UserError('No database to backup.')

        import datetime
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = '/opt/odoo-saas/backups/' + self.db_name
        os.makedirs(backup_dir, exist_ok=True)

        dump_file = backup_dir + '/' + self.db_name + '_' + ts + '.sql.gz'
        env = os.environ.copy()
        env['PGPASSWORD'] = DB_PASS

        cmd = (
            'pg_dump -h ' + DB_HOST + ' -p ' + str(DB_PORT) +
            ' -U ' + DB_USER + ' "' + self.db_name + '" | gzip > "' + dump_file + '"'
        )
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env)
        if result.returncode != 0:
            raise UserError('Database backup failed: ' + result.stderr)

        fs_src = self._get_filestore_path(self.db_name)
        fs_dst = backup_dir + '/' + self.db_name + '_filestore_' + ts + '.tar.gz'
        if os.path.exists(fs_src):
            subprocess.run(
                ['tar', '-czf', fs_dst, '-C', os.path.dirname(fs_src), os.path.basename(fs_src)],
                check=True
            )

        now = fields.Datetime.now()
        size = os.path.getsize(dump_file) / (1024 * 1024) if os.path.exists(dump_file) else 0
        self.env['saas.backup'].create({
            'tenant_id': self.id,
            'db_dump_path': dump_file,
            'filestore_path': fs_dst if os.path.exists(fs_dst) else False,
            'backup_date': now,
            'size_mb': size,
        })
        self.write({'last_backup_date': now})
        self.message_post(body='Backup created: ' + dump_file)
        _logger.info('Backup created for tenant %s: %s', self.name, dump_file)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Backup Complete'),
                'message': 'Backup saved to ' + dump_file,
                'type': 'success',
            }
        }

    # ── Delete ─────────────────────────────────────────────────────────────
    def action_delete_tenant(self):
        self.ensure_one()
        if self.db_name and self._db_exists(self.db_name):
            try:
                self.action_backup()
            except Exception as e:
                _logger.warning('Pre-deletion backup failed: %s', e)

        if self.db_name:
            self._drop_database(self.db_name)

        fs_path = self._get_filestore_path(self.db_name or self.subdomain)
        if os.path.exists(fs_path):
            import shutil
            shutil.rmtree(fs_path, ignore_errors=True)

        self.write({'state': 'cancelled'})
        self.message_post(body='Tenant deleted.')

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
            cur.execute('DROP DATABASE IF EXISTS "' + db_name + '"')
            _logger.info('Database %s dropped', db_name)
        except Exception as e:
            raise UserError('Failed to drop database: ' + str(e))
        finally:
            cur.close()
            conn.close()

    # ── Stats ──────────────────────────────────────────────────────────────
    def _update_stats(self):
        for t in self:
            if not t.db_name or not t._db_exists(t.db_name):
                continue
            try:
                conn = t._get_pg_conn(t.db_name)
                cur = conn.cursor()

                cur.execute("SELECT pg_database_size(%s) / 1048576.0", (t.db_name,))
                db_size = cur.fetchone()[0] or 0

                cur.execute("SELECT COUNT(*) FROM res_users WHERE active = true")
                user_count = cur.fetchone()[0] or 0

                cur.execute("SELECT name FROM ir_module_module WHERE state = 'installed' ORDER BY name")
                modules = ', '.join(r[0] for r in cur.fetchall())

                cur.close()
                conn.close()

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
            'params': {'title': _('Stats Updated'), 'type': 'success'}
        }

    def action_open_tenant(self):
        self.ensure_one()
        if not self.tenant_url:
            raise UserError('Tenant URL not available.')
        return {'type': 'ir.actions.act_url', 'url': self.tenant_url, 'target': 'new'}

    def action_view_backups(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Backups — ' + self.name,
            'res_model': 'saas.backup',
            'view_mode': 'tree,form',
            'domain': [('tenant_id', '=', self.id)],
            'context': {'default_tenant_id': self.id},
        }

    # ── Scheduled Actions ──────────────────────────────────────────────────
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

        warn_date = today + timedelta(days=7)
        soon = self.search([('state', '=', 'active'), ('expiry_date', '=', warn_date)])
        for t in soon:
            t.message_post(body='Reminder: subscription expires on ' + str(t.expiry_date))
"""

sftp = ssh.open_sftp()
with sftp.open('/opt/odoo-saas/addons/saas_tenant_manager/models/saas_tenant.py', 'w') as f:
    f.write(SAAS_TENANT)
sftp.close()
print('  ✅ saas_tenant.py rewritten')

def run(cmd, timeout=30):
    _, o, e = ssh.exec_command(cmd, timeout=timeout)
    return (o.read().decode('utf-8','replace') + e.read().decode('utf-8','replace')).strip()

# Verify syntax
result = run('python3 -c "import ast; ast.parse(open(\'/opt/odoo-saas/addons/saas_tenant_manager/models/saas_tenant.py\').read()); print(\'SYNTAX OK\')"')
print('Syntax check:', result)

ssh.close()
