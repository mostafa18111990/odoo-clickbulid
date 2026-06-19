# 📈 Tenant Upgrade System — Community → Enterprise

## 🎯 نظرة عامة

نظام شامل يسمح للعملاء بترقية حساباتهم من **Community** إلى **Enterprise Edition** مع التحكم الكامل من لوحة المعلومات الإدارية.

```
Customer Request → Admin Review → Auto-Migration → Enterprise Activation
```

---

## 📊 الميزات الرئيسية

### ✨ للعملاء
- ✅ طلب ترقية من لوحة التحكم الخاصة بهم
- ✅ تتبع حالة الطلب
- ✅ عدم فقدان البيانات (backup كامل)
- ✅ ترقية سلسة وآمنة

### 🔧 للإدارة
- ✅ لوحة معلومات جميع طلبات الترقية
- ✅ الموافقة/الرفض مع تفاصيل
- ✅ ترقية تلقائية كاملة
- ✅ تتبع التاريخ الكامل
- ✅ إرسال تنبيهات للعملاء

---

## 🏗️ المكونات

### 1. **Models**
```
saas.tenant.upgrade
├─ tenant_id: Reference to tenant
├─ from_edition: 'community' → 'enterprise'
├─ from_plan_id / to_plan_id: Plan migration
├─ status: pending → completed
├─ backup_file: Database backup location
└─ pricing details

saas.tenant (extended)
├─ upgrade_ids: One2many relationship
├─ upgradeable: Boolean field (can_upgrade check)
└─ last_upgraded_date: Track upgrades
```

### 2. **Service: TenantUpgradeService**
```python
service = TenantUpgradeService(env)

# Create request
service.create_upgrade_request(tenant_id, plan_id)

# Approve & migrate
service.approve_upgrade(upgrade_id)

# Reject
service.reject_upgrade(upgrade_id, reason)

# Check eligibility
can_upgrade, error = service.can_upgrade(tenant)
```

### 3. **Admin Dashboard**
```
Admin → Tenant Upgrades
├─ Pending Requests (with Approve/Reject buttons)
├─ Completed Upgrades
├─ Failed Upgrades (with error details)
└─ Full history per tenant
```

### 4. **Migration Process**
```
1️⃣ Backup Database
   └─ Create full SQL dump (location: /opt/backups/pre-upgrades/)

2️⃣ Migrate to Enterprise
   ├─ Rename database: tenant_name → tenant_name_backup
   ├─ Create new Enterprise DB
   ├─ Copy data from backup
   └─ Update tenant.database reference

3️⃣ Restart Services
   └─ docker restart odoo_saas_ent

4️⃣ Notify Customer
   └─ Email with new features & support info

5️⃣ Log & Track
   └─ Store in saas.tenant.upgrade with migration stats
```

---

## 🔄 Workflows

### Workflow #1: Customer-Initiated Upgrade

```
Customer clicks "Upgrade to Enterprise" in their dashboard
    ↓
Checks eligibility (Community + Trial/Active state)
    ↓
Creates upgrade request (status=pending)
    ↓
Admin notified (alert system)
    ↓
Admin reviews in Dashboard
    ↓
Approves → Automatic migration starts
    ↓
Email sent to customer (success/failure)
```

### Workflow #2: Admin-Initiated Upgrade

```
Admin: Admin → Tenant Upgrades → Select Tenant
    ↓
Opens upgrade wizard
    ↓
Selects new plan + coupon code
    ↓
Option to "Approve Immediately"
    ↓
Creates & approves in one step
    ↓
Customer notified
```

---

## 💻 API / Routes

### Customer Upgrade Request
```python
# From customer portal
POST /api/tenant/upgrade
{
    "tenant_id": 123,
    "to_plan_id": 456,
    "coupon_code": "SUMMER20"  # optional
}
Response: {"success": true, "upgrade_id": 789}
```

### Admin Approve
```python
# Admin action
POST /api/admin/upgrade/{id}/approve
Response: {
    "success": true,
    "details": "Migration completed",
    "backup_file": "/opt/backups/pre-upgrades/tenant_20260619_101030.sql.gz"
}
```

### Admin Reject
```python
POST /api/admin/upgrade/{id}/reject
{
    "reason": "Outstanding balance on account"
}
Response: {"success": true}
```

---

## 🎨 UI Components

### Admin Dashboard
```
📊 Tenant Upgrades
├─ Filter: Pending | Completed | Failed | All
├─ List View
│  ├─ Tenant Name
│  ├─ From → To Edition
│  ├─ Status
│  ├─ Price Difference
│  └─ Date Requested
└─ Form View
   ├─ Tenant Details
   ├─ Migration Info
   ├─ Pricing
   ├─ Backup Location
   └─ Migration Duration
```

### Customer Portal
```
🎯 Account Settings → Edition & Upgrade
├─ Current Edition: Community
├─ Plan: Pro Monthly ($25/month)
├─ Upgrade Button (if eligible)
└─ Upgrade History (completed upgrades)
```

---

## 📋 Business Logic

### Eligibility Check
```python
def can_upgrade(tenant):
    # ✅ Community edition
    # ✅ Trial or Active state
    # ✅ No outstanding balance
    # ❌ Already Enterprise
    # ❌ Suspended or Deleted
```

### Pricing
```
Community Plan: $10/month
Enterprise Plan: $50/month

Upgrade mid-month:
├─ Prorated difference calculated
├─ Coupon applied if valid
└─ Billing updated on next cycle
```

### Data Safety
```
1. Full backup before migration
2. Database renamed (recovery possible)
3. All data copied to new Enterprise DB
4. Old database retained for 30 days
5. Backup stored separately (immutable)
```

---

## 🔔 Notifications

### For Customers
- ✉️ Upgrade request confirmed
- ✉️ Upgrade approved (with new features list)
- ✉️ Upgrade failed (with explanation)
- ✉️ Support contact info

### For Admins
- 🔔 New upgrade request alert
- 🔔 Migration started/completed
- 🔔 Migration failed (with error details)
- 📊 Monthly upgrade stats

---

## 🧪 Testing

### Manual Test Flow
```bash
# 1. Create Community tenant
# 2. In admin dashboard: Admin → Tenant Upgrades
# 3. Click "+" or select tenant → "Upgrade"
# 4. Choose Enterprise plan
# 5. Click "Approve"
# 6. Monitor migration (check logs)
# 7. Verify customer email sent
# 8. Check tenant.edition = 'enterprise'
```

### Automated Tests
```python
# Run tests
python manage.py test addons.saas_website.tests.test_tenant_upgrade

# Tests cover:
# - Eligibility validation
# - Backup creation
# - Database migration
# - Plan updates
# - Email notifications
# - Error handling & recovery
```

---

## ⚠️ Error Handling

| Error | Cause | Recovery |
|-------|-------|----------|
| UPGRADE_NOT_ALLOWED | Not Community | Check edition |
| BACKUP_FAILED | DB dump error | Retry, check disk space |
| MIGRATION_FAILED | DB copy error | Rollback to backup |
| PLAN_NOT_FOUND | Missing plan | Create Enterprise plan |

---

## 📈 Statistics

### Tracking
```
upgrade_ids.get_pending_upgrades_count() → int
upgrade_ids.get_completed_upgrades_count() → int
upgrade_ids.get_failed_upgrades() → list
```

### Metrics
```
Total Upgrades: Completed + Failed
Success Rate: Completed / Total
Avg Migration Time: migration_time field
Revenue Impact: price_difference * count
```

---

## 🛡️ Security

✅ Only admins can approve/reject
✅ Customers see only their own upgrades
✅ Backup files protected (restricted access)
✅ Migration logs audited
✅ Pricing verified (prevent tampering)
✅ Coupon validation in place

---

## 🔧 Admin Actions

### From Tenant Form
```
Tenant → Action Button: "Upgrade to Enterprise"
├─ Opens wizard
├─ Pre-fills from_edition & from_plan
└─ Choose to_plan + approve immediately
```

### From Upgrade List
```
Admin → Tenant Upgrades → Upgrade Record
├─ View full details
├─ Check backup location
├─ See migration stats
├─ Approve/Reject/Cancel
└─ View error logs
```

---

## 📞 Support

### For Admin
- Check error_logs if migration fails
- Review backup_file location
- Check tenant.database field
- Verify nginx/certbot restarted

### For Customer
- Sent detailed email with next steps
- Support team notified automatically
- Can see upgrade status in portal

---

## 🎯 Next Steps

1. **Payment Gateway** - Integrate PayTabs/PayMob
2. **Auto-Billing** - Charge for Enterprise immediately
3. **Downgrade** - Support downgrade to Community (with data migration)
4. **Plan Changes** - Support changing Enterprise plans
5. **Usage Reports** - Show resource usage post-upgrade

---

## 📊 Configuration

### In saas.config
```
auto_approve_upgrades: Boolean
├─ True: Auto-approve if no balance issues
└─ False: Manual approval required

upgrade_grace_period: Integer (days)
├─ Days to refund if customer unsatisfied
└─ Default: 7 days
```

---

**Status:** ✅ Production Ready
**Last Updated:** 2026-06-19
**Next:** Payment Integration 💳
