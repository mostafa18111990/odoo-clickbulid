import os
import logging
import gzip
import subprocess
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
        """Restore tenant from this backup."""
        self.ensure_one()
        t = self.tenant_id
        if not self.db_dump_path or not os.path.exists(self.db_dump_path):
            raise UserError('Backup file not found.')

        db_host = os.environ.get('PGHOST') or os.environ.get('DB_HOST') or 'postgres'
        db_port = os.environ.get('PGPORT') or os.environ.get('DB_PORT') or '5432'
        db_user = os.environ.get('PGUSER') or os.environ.get('DB_USER') or 'odoo'
        db_pass = os.environ.get('PGPASSWORD') or os.environ.get('DB_PASSWORD')
        if not db_pass:
            raise UserError(_('Database credentials are not configured.'))

        env = os.environ.copy()
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
            f'CREATE DATABASE "{t.db_name}" OWNER "{db_user}" ENCODING \'UTF8\''
        )
        cur.close(); conn.close()

        # Restore
        cmd = [
            'psql', '-v', 'ON_ERROR_STOP=1',
            '-h', db_host, '-p', str(db_port), '-U', db_user, t.db_name,
        ]
        with gzip.open(self.db_dump_path, 'rb') as dump_stream:
            result = subprocess.run(
                cmd,
                stdin=dump_stream,
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
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
        """Delete backup files from disk."""
        self.ensure_one()
        for path in [self.db_dump_path, self.filestore_path]:
            if path and os.path.exists(path):
                os.remove(path)
                _logger.info('Deleted backup file: %s', path)
        self.write({'state': 'deleted'})
