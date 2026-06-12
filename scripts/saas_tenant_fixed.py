import logging
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

    # Plan
    plan_id = fields.Many2one('saas.plan', string='Plan', tracking=True)
    template_db = fields.Char(string='Template DB')

    # Dates
    trial_start    = fields.Date(string='Trial Start')
    trial_end      = fields.Date(string='Trial End')
    expiry_date    = fields.Date(string='Expiry Date', tracking=True)
    last_backup    = fields.Datetime(string='Last Backup')
    create_date    = fields.Datetime(string='Created', readonly=True)

    # Stats
    disk_usage_mb  = fields.Float(string='Disk Usage (MB)', readonly=True)
    users_count    = fields.Integer(string='Users Count', readonly=True)

    # State
    state = fields.Selection([
        ('draft',    'Draft'),
        ('trial',    'Trial'),
        ('active',   'Active'),
        ('suspended','Suspended'),
        ('expired',  'Expired'),
        ('cancelled','Cancelled'),
    ], string='State', default='draft', tracking=True)

    active = fields.Boolean(default=True)
    notes  = fields.Text(string='Notes')

    backup_ids = fields.One2many('saas.backup', 'tenant_id', string='Backups')
    backup_count = fields.Integer(compute='_compute_backup_count')

    _sql_constraints = [
        ('subdomain_unique', 'unique(subdomain)', 'Subdomain must be unique!'),
    ]

    @api.depends('backup_ids')
    def _compute_backup_count(self):
        for rec in self:
            rec.backup_count = len(rec.backup_ids)

    @api.depends('subdomain')
    def _compute_tenant_url(self):
        for rec in self:
            if rec.subdomain:
                rec.tenant_url = 'https://' + rec.subdomain + '.clickbulid.com'
            else:
                rec.tenant_url = False

    @api.constrains('subdomain')
    def _check_subdomain(self):
        pattern = re.compile(r'^[a-z0-9][a-z0-9\-]{1,30}[a-z0-9]$')
        for rec in self:
            if not pattern.match(rec.subdomain or ''):
                raise ValidationError(
                    'Subdomain must be 3-32 chars, lowercase letters/numbers/hyphens, '
                    'start and end with letter/number.'
                )

    def _get_pg_conn(self):
        return psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASS,
            dbname='postgres',
        )

    def _db_exists(self, db_name):
        conn = self._get_pg_conn()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
        exists = cur.fetchone() is not None
        cur.close()
        conn.close()
        return exists

    def _get_filestore_path(self, db_name):
        data_dir = config.get('data_dir', '/var/lib/odoo')
        return os.path.join(data_dir, 'filestore', db_name)

    def action_provision(self):
        self.ensure_one()
        if self.state not in ('draft', 'trial'):
            raise UserError('Can only provision tenants in Draft or Trial state.')

        db_name = 'tenant_' + self.subdomain
        if self._db_exists(db_name):
            raise UserError('Database ' + db_name + ' already exists!')

        self._create_database(db_name)
        self._create_filestore(db_name)

        self.write({
            'db_name': db_name,
            'db_user': DB_USER,
            'state': 'active',
        })
        _logger.info('Tenant %s provisioned. DB: %s', self.subdomain, db_name)

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
                    "CREATE DATABASE \"" + db_name + "\""
                    " TEMPLATE \"" + self.template_db + "\""
                    " OWNER \"" + DB_USER + "\" ENCODING 'UTF8'"
                )
                cur.execute(sql)
            else:
                _logger.info('Creating fresh DB: %s', db_name)
                sql = (
                    "CREATE DATABASE \"" + db_name + "\""
                    " OWNER \"" + DB_USER + "\""
                    " ENCODING 'UTF8'"
                    " LC_COLLATE 'en_US.UTF-8'"
                    " LC_CTYPE 'en_US.UTF-8'"
                    " TEMPLATE template0"
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

    def action_suspend(self):
        self.write({'state': 'suspended'})

    def action_activate(self):
        self.write({'state': 'active'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_backup(self):
        self.ensure_one()
        if not self.db_name:
            raise UserError('No database assigned to this tenant.')
        return self._do_backup()

    def _do_backup(self):
        import datetime
        db = self.db_name
        backup_dir = '/opt/odoo-saas/backups/' + db
        os.makedirs(backup_dir, exist_ok=True)
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = backup_dir + '/' + db + '_' + ts + '.sql.gz'

        env = dict(os.environ, PGPASSWORD=DB_PASS)
        cmd = [
            'pg_dump',
            '-h', DB_HOST,
            '-p', str(DB_PORT),
            '-U', DB_USER,
            db,
        ]
        try:
            with open(backup_file, 'wb') as f:
                pg = subprocess.Popen(cmd, stdout=subprocess.PIPE, env=env)
                gz = subprocess.Popen(['gzip'], stdin=pg.stdout, stdout=f, env=env)
                pg.stdout.close()
                gz.communicate()
                if pg.wait() != 0:
                    raise UserError('pg_dump failed for ' + db)

            size_mb = os.path.getsize(backup_file) / (1024 * 1024)
            self.env['saas.backup'].create({
                'tenant_id': self.id,
                'backup_file': backup_file,
                'size_mb': size_mb,
            })
            self.last_backup = fields.Datetime.now()
            _logger.info('Backup done: %s (%.1f MB)', backup_file, size_mb)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Backup Complete'),
                    'message': 'Backup saved: ' + backup_file,
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            if os.path.exists(backup_file):
                os.remove(backup_file)
            raise UserError('Backup failed: ' + str(e))

    def action_update_stats(self):
        for rec in self:
            if not rec.db_name:
                continue
            try:
                conn = self._get_pg_conn()
                cur = conn.cursor()
                cur.execute(
                    "SELECT pg_database_size(%s)",
                    (rec.db_name,)
                )
                row = cur.fetchone()
                if row:
                    rec.disk_usage_mb = row[0] / (1024 * 1024)
                cur.close()
                conn.close()
            except Exception as e:
                _logger.warning('Failed to get stats for %s: %s', rec.db_name, str(e))

    def action_view_backups(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Backups'),
            'res_model': 'saas.backup',
            'view_mode': 'list,form',
            'domain': [('tenant_id', '=', self.id)],
            'context': {'default_tenant_id': self.id},
        }

    @api.model
    def cron_backup_all(self):
        tenants = self.search([('state', '=', 'active'), ('db_name', '!=', False)])
        for t in tenants:
            try:
                t._do_backup()
            except Exception as e:
                _logger.error('Cron backup failed for %s: %s', t.subdomain, str(e))

    @api.model
    def cron_update_all_stats(self):
        tenants = self.search([('state', '=', 'active')])
        tenants.action_update_stats()

    @api.model
    def cron_check_expired(self):
        today = date.today()
        expired = self.search([
            ('state', '=', 'active'),
            ('expiry_date', '<', today),
        ])
        expired.write({'state': 'expired'})
        _logger.info('Expired %d tenants', len(expired))
