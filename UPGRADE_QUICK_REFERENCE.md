# ⚡ Tenant Upgrade — Quick Reference

## 🎯 For Daily Use

---

## 👤 **As a Customer**

### 🔹 How to Request Upgrade

```
1. Log into your account
2. Settings → Edition & Upgrade
3. Click [🚀 Upgrade to Enterprise]
4. Review pricing
5. Enter coupon (if you have one)
6. [Submit Request]
✅ Done! Wait for admin approval
```

### 📍 Where to Check Status

```
Settings → Edition & Upgrade → History
Shows: Status, Date, Approval progress
```

---

## 👨‍💼 **As an Admin**

### 🔹 Approve an Upgrade

```
Admin → Tenant Upgrades (Pending)
├─ See list of pending requests
├─ Click on tenant name
├─ Review details
├─ Click [✅ Approve]
└─ Auto-migration starts (2-5 min)
✅ Customer email sent automatically
```

### 🔹 Reject an Upgrade

```
Admin → Tenant Upgrades
├─ Click request
├─ Click [❌ Reject]
├─ Enter reason: "Outstanding balance"
└─ [Confirm]
✅ Customer notified with reason
```

### 🔹 Manually Upgrade a Customer

```
Admin → Tenants
├─ Open tenant record
├─ Actions → [Upgrade to Enterprise]
├─ Select plan
├─ Select coupon (optional)
├─ ☑ Approve Immediately
└─ [Create Upgrade]
✅ Migration starts immediately
```

### 🔹 View All Upgrades

```
Admin → Tenant Upgrades
├─ Filter: Pending | Completed | All
├─ Sort by: Date, Status, Tenant
└─ Click any to see details
```

---

## 📊 **Key Screens**

### Admin Dashboard
```
Tenant Upgrades (Pending)
├─ Tenant Name
├─ From → To
├─ Status
├─ Requested Date
└─ Price Difference
```

### Upgrade Details
```
├─ Tenant Info
├─ Migration Details
├─ Backup Location
├─ Approval Info
└─ [✅ Approve] [❌ Reject]
```

---

## 💰 **Pricing Quick Math**

```
Community Pro:      $10/month
Enterprise Plus:    $50/month
─────────────────────────────
Difference:         +$40/month

With Coupon:
SUMMER2026-30:     -$10
───────────────────────────
Net Cost:           +$30/month
```

---

## 🔔 **Notifications Sent**

### Customer receives:
- ✉️ Request confirmed
- ✉️ Upgrade approved (success email)
- ✉️ OR rejection (with reason)

### Admin receives:
- 🔔 New request alert
- 🔔 Migration completed notification

---

## ⏱️ **Timeline**

```
Customer Request:      0 min
Admin Review:          ~10 min
Migration Process:     ~2-5 min
─────────────────────────────
Total:                 ~15-20 min
```

---

## ✅ **Checklist Before Approving**

```
☑ Customer has no outstanding balance
☑ Coupon code is valid (not expired)
☑ Tenant is Community edition
☑ Tenant state is Active or Trial
☑ Database size is reasonable
☑ No current provisioning jobs
```

---

## 🆘 **If Something Goes Wrong**

### Upgrade Failed?
```
Check:
1. Admin → Error Logs
2. Check backup file location
3. Verify database space
4. Review migration logs

Recovery:
1. Backup exists at: /opt/backups/pre-upgrades/
2. Can restore from backup
3. Contact: support@clickbuild.com
```

### Customer can't login after?
```
1. Wait 5 minutes (services restarting)
2. Clear browser cache
3. Check: Admin → Tenants → Verify database=enterprise
4. Restart: docker restart odoo_saas_ent
```

---

## 📧 **Email Templates**

### Success Email (sent to customer)
```
Subject: ✅ Upgrade Successful!

Content:
- Congratulations 🎉
- New features list
- Support contact info
- Login link
```

### Rejection Email (if rejected)
```
Subject: Update: Upgrade Request

Content:
- Reason for rejection
- Required action
- Support contact info
- Retry instructions
```

---

## 🔐 **Security Notes**

```
✅ Data is always backed up FIRST
✅ Old database kept for 30 days
✅ Zero data loss guaranteed
✅ Only admins can approve
✅ All actions are logged
```

---

## 📈 **Monitor Progress**

### Real-time status:
```
Admin → Tenant Upgrades → Select Upgrade
├─ Shows current status
├─ Migration progress
└─ Timestamps for each step
```

### Statistics:
```
Admin → Dashboard (Widget)
├─ Total upgrades: X
├─ Pending: Y
├─ Success rate: Z%
└─ Revenue impact: $$$
```

---

## 🎓 **Learning Resources**

| Document | Purpose |
|----------|---------|
| TENANT_UPGRADE_GUIDE.md | Complete reference |
| UPGRADE_DEMO_SCENARIO.md | Real-world example |
| This file | Quick lookup |

---

## 📞 **Support**

**Questions?**
- Check: TENANT_UPGRADE_GUIDE.md
- Email: support@clickbuild.com
- Call: +966 50 123 4567

---

## 🚀 **That's It!**

The upgrade system handles 95% automatically.
Just approve/reject and let it do the work.

**You're all set!** ✨
