from odoo import models, fields, api
from datetime import datetime


class SaasTenantUpgrade(models.Model):
    _name = 'saas.tenant.upgrade'
    _description = 'Tenant Edition Upgrade Request'
    _order = 'requested_date DESC'

    tenant_id = fields.Many2one('saas.tenant', 'المستأجر', required=True, ondelete='cascade')
    from_edition = fields.Selection([
        ('community', 'Community'),
        ('enterprise', 'Enterprise'),
    ], string='من الإصدار', required=True)
    to_edition = fields.Selection([
        ('community', 'Community'),
        ('enterprise', 'Enterprise'),
    ], string='إلى الإصدار', required=True)
    from_plan_id = fields.Many2one('saas.plan', 'خطة سابقة')
    to_plan_id = fields.Many2one('saas.plan', 'خطة جديدة')

    status = fields.Selection([
        ('pending', 'قيد الانتظار'),
        ('approved', 'موافق عليه'),
        ('completed', 'مكتمل'),
        ('failed', 'فشل'),
        ('rejected', 'مرفوض'),
    ], default='pending', index=True, track_visibility='onchange')

    requested_date = fields.Datetime('تاريخ الطلب', default=datetime.now())
    requested_by = fields.Many2one('res.users', 'طلبه من قبل')

    approved_date = fields.Datetime('تاريخ الموافقة')
    approved_by = fields.Many2one('res.users', 'وافق عليه')

    completed_date = fields.Datetime('تاريخ الإكمال')
    rejected_date = fields.Datetime('تاريخ الرفض')

    rejection_reason = fields.Text('سبب الرفض')
    error_message = fields.Text('رسالة الخطأ')

    backup_file = fields.Char('ملف النسخة الاحتياطية')
    notes = fields.Text('ملاحظات')

    coupon_code = fields.Char('كود الخصم')

    # Pricing fields
    old_price = fields.Monetary('السعر السابق')
    new_price = fields.Monetary('السعر الجديد')
    price_difference = fields.Monetary('الفرق في السعر')

    currency_id = fields.Many2one('res.currency', 'العملة', default=lambda self: self.env.company.currency_id)

    # Stats
    backup_size = fields.Integer('حجم النسخة الاحتياطية (MB)')
    migration_time = fields.Float('وقت الهجرة (ثانية)')

    @api.onchange('from_plan_id', 'to_plan_id')
    def _compute_price_difference(self):
        """Calculate price difference."""
        for record in self:
            if record.from_plan_id and record.to_plan_id:
                old = record.from_plan_id.monthly_price
                new = record.to_plan_id.monthly_price
                record.old_price = old
                record.new_price = new
                record.price_difference = new - old

    def action_approve(self):
        """Admin approves the upgrade."""
        from odoo.addons.saas_website.services.tenant_upgrade_service import TenantUpgradeService

        for upgrade in self:
            try:
                service = TenantUpgradeService(self.env)
                result = service.approve_upgrade(upgrade.id)

                upgrade.write({
                    'status': 'completed',
                    'approved_by': self.env.user.id,
                    'approved_date': datetime.now(),
                })

                # Send notification to customer
                self._send_upgrade_success_email(upgrade.tenant_id)

            except Exception as e:
                upgrade.write({
                    'status': 'failed',
                    'error_message': str(e),
                })
                raise

    def action_reject(self):
        """Admin rejects the upgrade."""
        for upgrade in self:
            upgrade.write({
                'status': 'rejected',
                'rejected_date': datetime.now(),
            })
            # Send rejection email
            self._send_upgrade_rejection_email(upgrade.tenant_id, upgrade.rejection_reason)

    def action_cancel(self):
        """Cancel pending upgrade."""
        for upgrade in self:
            if upgrade.status == 'pending':
                upgrade.write({'status': 'rejected'})

    def _send_upgrade_success_email(self, tenant):
        """Send success email to tenant."""
        try:
            body = f"""
            <h2>مبروك! تم ترقية حسابك بنجاح 🎉</h2>
            <p>مرحباً {tenant.name},</p>
            <p>تم ترقية حسابك من <strong>Community</strong> إلى <strong>Enterprise</strong>.</p>
            <h3>المميزات الجديدة:</h3>
            <ul>
                <li>🔐 الدعم الفني المميز</li>
                <li>⚡ أداء محسّن</li>
                <li>📊 ميزات إضافية متقدمة</li>
                <li>🔄 النسخ الاحتياطية التلقائية</li>
            </ul>
            <p><a href="https://clickbuild.com/login">تسجيل الدخول الآن</a></p>
            """

            self.env['mail.mail'].create({
                'subject': 'تم ترقية حسابك إلى Enterprise بنجاح ✅',
                'body_html': body,
                'email_to': tenant.contact_email,
            }).send()
        except Exception as e:
            self.env.logger.error(f"Failed to send upgrade email: {e}")

    def _send_upgrade_rejection_email(self, tenant, reason):
        """Send rejection email to tenant."""
        try:
            body = f"""
            <h2>رفض طلب الترقية</h2>
            <p>مرحباً {tenant.name},</p>
            <p>للأسف، تم رفض طلب ترقيتك إلى الإصدار Enterprise.</p>
            <h3>السبب:</h3>
            <p>{reason}</p>
            <p>يرجى التواصل معنا للمزيد من المعلومات: support@clickbuild.com</p>
            """

            self.env['mail.mail'].create({
                'subject': 'تحديث: رفض طلب الترقية',
                'body_html': body,
                'email_to': tenant.contact_email,
            }).send()
        except Exception as e:
            self.env.logger.error(f"Failed to send rejection email: {e}")

    @api.model
    def get_pending_upgrades_count(self):
        """Get count of pending upgrades."""
        return self.search_count([('status', '=', 'pending')])

    @api.model
    def get_completed_upgrades_count(self):
        """Get count of completed upgrades."""
        return self.search_count([('status', '=', 'completed')])
