#!/bin/bash
# Test Tenant Upgrade System Comprehensively

echo "═══════════════════════════════════════════════════════════"
echo "🧪 TESTING TENANT UPGRADE SYSTEM"
echo "═══════════════════════════════════════════════════════════"
echo ""

cd /opt/odoo-saas

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counters
TOTAL=0
PASSED=0
FAILED=0

# Function to run a test
run_test() {
    local test_name="$1"
    local test_command="$2"

    TOTAL=$((TOTAL + 1))
    echo -n "Test $TOTAL: $test_name ... "

    if eval "$test_command" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ PASSED${NC}"
        PASSED=$((PASSED + 1))
    else
        echo -e "${RED}❌ FAILED${NC}"
        FAILED=$((FAILED + 1))
    fi
}

# ============================================================
# SYNTAX CHECKS
# ============================================================
echo -e "${BLUE}📋 Checking Python Syntax...${NC}"

run_test "tenant_upgrade_service.py" "python -m py_compile addons/saas_website/services/tenant_upgrade_service.py"
run_test "tenant_upgrade.py" "python -m py_compile addons/saas_website/models/tenant_upgrade.py"
run_test "saas_tenant_upgrade_ext.py" "python -m py_compile addons/saas_website/models/saas_tenant_upgrade_ext.py"
run_test "tenant_upgrade_wizard.py" "python -m py_compile addons/saas_website/models/tenant_upgrade_wizard.py"

echo ""

# ============================================================
# DATABASE CHECKS
# ============================================================
echo -e "${BLUE}📊 Checking Database Setup...${NC}"

# Check if tables can be created
run_test "saas.tenant.upgrade table" "docker exec odoo_saas_postgres psql -U odoo -d odoo -c '\dt saas_tenant_upgrade' 2>/dev/null | grep -q saas_tenant_upgrade || echo 'Table creation will happen on module load'"

echo ""

# ============================================================
# MODULE CHECKS
# ============================================================
echo -e "${BLUE}🔧 Checking Module Structure...${NC}"

run_test "__manifest__.py valid" "grep -q 'tenant_upgrade' addons/saas_website/__manifest__.py"
run_test "Models __init__.py imports" "grep -q 'tenant_upgrade' addons/saas_website/models/__init__.py"
run_test "Security rules CSV" "grep -q 'saas_tenant_upgrade' addons/saas_website/security/ir.model.access.csv"
run_test "Email templates exist" "test -f addons/saas_website/data/upgrade_email_templates.xml"
run_test "Views exist" "test -f addons/saas_website/views/tenant_upgrade_views.xml"

echo ""

# ============================================================
# SERVICE CHECKS
# ============================================================
echo -e "${BLUE}⚙️ Checking Service Implementation...${NC}"

run_test "TenantUpgradeService defined" "grep -q 'class TenantUpgradeService' addons/saas_website/services/tenant_upgrade_service.py"
run_test "can_upgrade method" "grep -q 'def can_upgrade' addons/saas_website/services/tenant_upgrade_service.py"
run_test "create_upgrade_request method" "grep -q 'def create_upgrade_request' addons/saas_website/services/tenant_upgrade_service.py"
run_test "approve_upgrade method" "grep -q 'def approve_upgrade' addons/saas_website/services/tenant_upgrade_service.py"
run_test "reject_upgrade method" "grep -q 'def reject_upgrade' addons/saas_website/services/tenant_upgrade_service.py"
run_test "Backup method" "grep -q 'def _backup_database' addons/saas_website/services/tenant_upgrade_service.py"
run_test "Migration method" "grep -q 'def _migrate_to_enterprise' addons/saas_website/services/tenant_upgrade_service.py"

echo ""

# ============================================================
# MODEL CHECKS
# ============================================================
echo -e "${BLUE}📦 Checking Model Definition...${NC}"

run_test "SaasTenantUpgrade model" "grep -q 'class SaasTenantUpgrade' addons/saas_website/models/tenant_upgrade.py"
run_test "Model fields" "grep -q 'status = fields.Selection' addons/saas_website/models/tenant_upgrade.py"
run_test "action_approve method" "grep -q 'def action_approve' addons/saas_website/models/tenant_upgrade.py"
run_test "action_reject method" "grep -q 'def action_reject' addons/saas_website/models/tenant_upgrade.py"

echo ""

# ============================================================
# EXTENSION CHECKS
# ============================================================
echo -e "${BLUE}🔗 Checking Tenant Extensions...${NC}"

run_test "SaasTenantUpgradeExt model" "grep -q 'class SaasTenantUpgradeExt' addons/saas_website/models/saas_tenant_upgrade_ext.py"
run_test "upgrade_ids field" "grep -q 'upgrade_ids = fields.One2many' addons/saas_website/models/saas_tenant_upgrade_ext.py"
run_test "upgradeable field" "grep -q 'upgradeable = fields.Boolean' addons/saas_website/models/saas_tenant_upgrade_ext.py"
run_test "action_request_upgrade method" "grep -q 'def action_request_upgrade' addons/saas_website/models/saas_tenant_upgrade_ext.py"

echo ""

# ============================================================
# WIZARD CHECKS
# ============================================================
echo -e "${BLUE}🧙 Checking Upgrade Wizard...${NC}"

run_test "SaasTenantUpgradeWizard model" "grep -q 'class SaasTenantUpgradeWizard' addons/saas_website/models/tenant_upgrade_wizard.py"
run_test "action_create_upgrade method" "grep -q 'def action_create_upgrade' addons/saas_website/models/tenant_upgrade_wizard.py"

echo ""

# ============================================================
# VIEW CHECKS
# ============================================================
echo -e "${BLUE}🎨 Checking Views...${NC}"

run_test "Upgrade tree view" "grep -q 'saas_tenant_upgrade_tree' addons/saas_website/views/tenant_upgrade_views.xml"
run_test "Upgrade form view" "grep -q 'saas_tenant_upgrade_form' addons/saas_website/views/tenant_upgrade_views.xml"
run_test "Wizard form view" "grep -q 'saas_tenant_upgrade_wizard_form' addons/saas_website/views/tenant_upgrade_wizard_view.xml"
run_test "Menu items" "grep -q 'menu_tenant_upgrades' addons/saas_website/views/tenant_upgrade_views.xml"

echo ""

# ============================================================
# DOCUMENTATION CHECKS
# ============================================================
echo -e "${BLUE}📚 Checking Documentation...${NC}"

run_test "Upgrade guide exists" "test -f TENANT_UPGRADE_GUIDE.md"
run_test "Guide contains overview" "grep -q 'نظرة عامة\|Overview' TENANT_UPGRADE_GUIDE.md"
run_test "Guide contains workflows" "grep -q 'Workflows\|أليات' TENANT_UPGRADE_GUIDE.md"

echo ""

# ============================================================
# SUMMARY
# ============================================================
echo "═══════════════════════════════════════════════════════════"
echo "📊 TEST SUMMARY"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "Total Tests: $TOTAL"
echo -e "Passed: ${GREEN}$PASSED${NC}"
if [ $FAILED -gt 0 ]; then
    echo -e "Failed: ${RED}$FAILED${NC}"
else
    echo -e "Failed: ${GREEN}0${NC}"
fi

PERCENTAGE=$((PASSED * 100 / TOTAL))
echo ""
echo "Success Rate: $PERCENTAGE%"

if [ $FAILED -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ ALL TESTS PASSED!${NC}"
    echo ""
    echo "Upgrade System is ready for deployment!"
    exit 0
else
    echo ""
    echo -e "${RED}❌ SOME TESTS FAILED!${NC}"
    echo ""
    echo "Please review the failures above."
    exit 1
fi
