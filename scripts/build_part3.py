#!/usr/bin/env python3
"""Part 3 - Views, Security, Menus, Wizard, Cron, Data"""
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
# security/saas_security.xml
# ─────────────────────────────────────────────────────
SECURITY_XML = """<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Groups -->
    <record id="group_saas_admin" model="res.groups">
        <field name="name">SaaS Administrator</field>
        <field name="category_id" ref="base.module_category_administration"/>
        <field name="implied_ids" eval="[(4, ref('base.group_user'))]"/>
        <field name="users" eval="[(4, ref('base.user_admin'))]"/>
    </record>

    <record id="group_saas_manager" model="res.groups">
        <field name="name">SaaS Manager</field>
        <field name="category_id" ref="base.module_category_administration"/>
        <field name="implied_ids" eval="[(4, ref('base.group_user'))]"/>
    </record>

    <!-- Record rules: SaaS Admin sees everything -->
    <record id="rule_tenant_admin" model="ir.rule">
        <field name="name">Tenants: Admin Full Access</field>
        <field name="model_id" ref="model_saas_tenant"/>
        <field name="groups" eval="[(4, ref('group_saas_admin'))]"/>
        <field name="perm_read" eval="True"/>
        <field name="perm_write" eval="True"/>
        <field name="perm_create" eval="True"/>
        <field name="perm_unlink" eval="True"/>
        <field name="domain_force">[(1, '=', 1)]</field>
    </record>

    <record id="rule_tenant_manager" model="ir.rule">
        <field name="name">Tenants: Manager Read/Backup</field>
        <field name="model_id" ref="model_saas_tenant"/>
        <field name="groups" eval="[(4, ref('group_saas_manager'))]"/>
        <field name="perm_read" eval="True"/>
        <field name="perm_write" eval="False"/>
        <field name="perm_create" eval="False"/>
        <field name="perm_unlink" eval="False"/>
        <field name="domain_force">[(1, '=', 1)]</field>
    </record>
</odoo>
"""

# ─────────────────────────────────────────────────────
# security/ir.model.access.csv
# ─────────────────────────────────────────────────────
ACCESS_CSV = """id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_saas_plan_admin,saas.plan admin,model_saas_plan,group_saas_admin,1,1,1,1
access_saas_plan_manager,saas.plan manager,model_saas_plan,group_saas_manager,1,0,0,0
access_saas_tenant_admin,saas.tenant admin,model_saas_tenant,group_saas_admin,1,1,1,1
access_saas_tenant_manager,saas.tenant manager,model_saas_tenant,group_saas_manager,1,1,0,0
access_saas_backup_admin,saas.backup admin,model_saas_backup,group_saas_admin,1,1,1,1
access_saas_backup_manager,saas.backup manager,model_saas_backup,group_saas_manager,1,0,0,0
access_create_tenant_wizard_admin,create.tenant.wizard admin,model_create_tenant_wizard,group_saas_admin,1,1,1,1
"""

# ─────────────────────────────────────────────────────
# views/saas_plan_views.xml
# ─────────────────────────────────────────────────────
PLAN_VIEWS = """<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Tree -->
    <record id="view_saas_plan_tree" model="ir.ui.view">
        <field name="name">saas.plan.tree</field>
        <field name="model">saas.plan</field>
        <field name="arch" type="xml">
            <tree string="Subscription Plans" decoration-muted="not active">
                <field name="name"/>
                <field name="code"/>
                <field name="max_users"/>
                <field name="max_storage_mb"/>
                <field name="monthly_price"/>
                <field name="yearly_price"/>
                <field name="trial_days"/>
                <field name="tenant_count"/>
                <field name="active" optional="hide"/>
            </tree>
        </field>
    </record>

    <!-- Form -->
    <record id="view_saas_plan_form" model="ir.ui.view">
        <field name="name">saas.plan.form</field>
        <field name="model">saas.plan</field>
        <field name="arch" type="xml">
            <form string="Subscription Plan">
                <sheet>
                    <div class="oe_button_box" name="button_box">
                        <button class="oe_stat_button" type="object"
                            name="action_view_tenants" icon="fa-users">
                            <field name="tenant_count" widget="statinfo" string="Tenants"/>
                        </button>
                    </div>
                    <field name="active" widget="boolean_toggle" class="float-end"/>
                    <div class="oe_title">
                        <h1><field name="name" placeholder="Plan Name"/></h1>
                    </div>
                    <group>
                        <group string="Identity">
                            <field name="code"/>
                            <field name="color" widget="color_picker"/>
                        </group>
                        <group string="Pricing (SAR)">
                            <field name="monthly_price"/>
                            <field name="yearly_price"/>
                            <field name="trial_days"/>
                        </group>
                    </group>
                    <group string="Limits">
                        <field name="max_users"/>
                        <field name="max_storage_mb"/>
                    </group>
                    <group string="Modules">
                        <field name="allowed_modules"
                            placeholder="base,sale,account,purchase"
                            widget="char"
                            colspan="2"/>
                    </group>
                    <group string="Features">
                        <field name="features" nolabel="1" colspan="2"
                            placeholder="One feature per line"/>
                    </group>
                    <field name="description" colspan="2"/>
                </sheet>
            </form>
        </field>
    </record>

    <!-- Action -->
    <record id="action_saas_plan" model="ir.actions.act_window">
        <field name="name">Subscription Plans</field>
        <field name="res_model">saas.plan</field>
        <field name="view_mode">tree,form</field>
    </record>
</odoo>
"""

# ─────────────────────────────────────────────────────
# views/saas_backup_views.xml
# ─────────────────────────────────────────────────────
BACKUP_VIEWS = """<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_saas_backup_tree" model="ir.ui.view">
        <field name="name">saas.backup.tree</field>
        <field name="model">saas.backup</field>
        <field name="arch" type="xml">
            <tree string="Backups" decoration-muted="state == 'deleted'">
                <field name="tenant_id"/>
                <field name="backup_date"/>
                <field name="size_mb"/>
                <field name="db_dump_path"/>
                <field name="state" widget="badge"
                    decoration-success="state == 'done'"
                    decoration-info="state == 'restored'"
                    decoration-danger="state == 'deleted'"/>
                <button name="action_restore" type="object" string="Restore"
                    icon="fa-undo" attrs="{'invisible': [('state', '=', 'deleted')]}"/>
                <button name="action_delete_backup" type="object" string="Delete"
                    icon="fa-trash" attrs="{'invisible': [('state', '=', 'deleted')]}"/>
            </tree>
        </field>
    </record>

    <record id="view_saas_backup_form" model="ir.ui.view">
        <field name="name">saas.backup.form</field>
        <field name="model">saas.backup</field>
        <field name="arch" type="xml">
            <form string="Backup">
                <header>
                    <button name="action_restore" type="object" string="Restore"
                        class="btn-primary"
                        attrs="{'invisible': [('state', '=', 'deleted')]}"/>
                    <button name="action_delete_backup" type="object"
                        string="Delete Files" class="btn-danger"
                        attrs="{'invisible': [('state', '=', 'deleted')]}"/>
                    <field name="state" widget="statusbar"/>
                </header>
                <sheet>
                    <group>
                        <field name="tenant_id"/>
                        <field name="backup_date"/>
                        <field name="size_mb"/>
                        <field name="db_dump_path"/>
                        <field name="filestore_path"/>
                        <field name="notes"/>
                    </group>
                </sheet>
            </form>
        </field>
    </record>

    <record id="action_saas_backup" model="ir.actions.act_window">
        <field name="name">Tenant Backups</field>
        <field name="res_model">saas.backup</field>
        <field name="view_mode">tree,form</field>
        <field name="context">{'search_default_group_tenant': 1}</field>
    </record>
</odoo>
"""

# ─────────────────────────────────────────────────────
# views/saas_tenant_views.xml
# ─────────────────────────────────────────────────────
TENANT_VIEWS = """<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Kanban -->
    <record id="view_saas_tenant_kanban" model="ir.ui.view">
        <field name="name">saas.tenant.kanban</field>
        <field name="model">saas.tenant</field>
        <field name="arch" type="xml">
            <kanban default_group_by="state" class="o_kanban_mobile"
                    records_draggable="0">
                <field name="state"/>
                <field name="color"/>
                <templates>
                    <t t-name="kanban-box">
                        <div t-attf-class="oe_kanban_card oe_kanban_global_click o_kanban_record_has_image_fill">
                            <div class="o_kanban_record_top">
                                <div class="o_kanban_record_headings">
                                    <strong class="o_kanban_record_title">
                                        <field name="name"/>
                                    </strong>
                                    <span class="o_kanban_record_subtitle">
                                        <field name="customer_name"/>
                                    </span>
                                </div>
                                <div class="o_kanban_manage_toggle_button">
                                    <field name="state" widget="label_selection"
                                        options="{
                                            'classes': {
                                                'draft': 'default',
                                                'provisioning': 'info',
                                                'active': 'success',
                                                'suspended': 'warning',
                                                'expired': 'danger',
                                                'cancelled': 'muted'
                                            }
                                        }"/>
                                </div>
                            </div>
                            <div class="o_kanban_record_body">
                                <field name="tenant_url"/>
                                <br/>
                                <small>Plan: <field name="plan_id"/></small>
                                <br/>
                                <small>Expires: <field name="expiry_date"/></small>
                            </div>
                            <div class="o_kanban_record_bottom">
                                <div class="oe_kanban_bottom_left">
                                    <span><i class="fa fa-database"/> <field name="db_size_mb"/> MB</span>
                                    <span class="ms-2"><i class="fa fa-users"/> <field name="user_count"/></span>
                                </div>
                            </div>
                        </div>
                    </t>
                </templates>
            </kanban>
        </field>
    </record>

    <!-- Tree -->
    <record id="view_saas_tenant_tree" model="ir.ui.view">
        <field name="name">saas.tenant.tree</field>
        <field name="model">saas.tenant</field>
        <field name="arch" type="xml">
            <tree string="Tenants"
                  decoration-success="state == 'active'"
                  decoration-warning="state == 'suspended'"
                  decoration-danger="state in ('expired','cancelled')"
                  decoration-info="state == 'provisioning'">
                <field name="name"/>
                <field name="customer_name"/>
                <field name="customer_email" optional="show"/>
                <field name="subdomain"/>
                <field name="plan_id"/>
                <field name="state" widget="badge"
                    decoration-success="state == 'active'"
                    decoration-warning="state == 'suspended'"
                    decoration-danger="state in ('expired','cancelled')"
                    decoration-info="state == 'provisioning'"/>
                <field name="expiry_date"/>
                <field name="db_size_mb" string="DB (MB)"/>
                <field name="user_count" string="Users"/>
                <field name="last_backup_date" optional="show"/>
                <button name="action_suspend" type="object" string="Suspend"
                    icon="fa-pause" attrs="{'invisible': [('state','!=','active')]}"/>
                <button name="action_reactivate" type="object" string="Reactivate"
                    icon="fa-play" attrs="{'invisible': [('state','!=','suspended')]}"/>
            </tree>
        </field>
    </record>

    <!-- Form -->
    <record id="view_saas_tenant_form" model="ir.ui.view">
        <field name="name">saas.tenant.form</field>
        <field name="model">saas.tenant</field>
        <field name="arch" type="xml">
            <form string="Tenant">
                <header>
                    <button name="action_create_tenant" type="object"
                        string="🚀 Create Tenant" class="btn-primary"
                        attrs="{'invisible': [('state','!=','draft')]}"/>
                    <button name="action_suspend" type="object"
                        string="⏸ Suspend" class="btn-warning"
                        attrs="{'invisible': [('state','!=','active')]}"/>
                    <button name="action_reactivate" type="object"
                        string="▶ Reactivate" class="btn-success"
                        attrs="{'invisible': [('state','!=','suspended')]}"/>
                    <button name="action_backup" type="object"
                        string="💾 Backup Now"
                        attrs="{'invisible': [('state','not in',['active','suspended'])]}"/>
                    <button name="action_update_stats" type="object"
                        string="📊 Refresh Stats"
                        attrs="{'invisible': [('db_name','=',False)]}"/>
                    <button name="action_open_tenant" type="object"
                        string="🌐 Open Tenant" class="btn-info"
                        attrs="{'invisible': [('state','!=','active')]}"/>
                    <button name="action_delete_tenant" type="object"
                        string="🗑 Delete Tenant" class="btn-danger"
                        confirm="This will backup and DELETE the tenant database permanently. Continue?"
                        attrs="{'invisible': [('state','in',['draft','cancelled'])]}"/>
                    <field name="state" widget="statusbar"
                        statusbar_visible="draft,provisioning,active,suspended,cancelled"/>
                </header>
                <sheet>
                    <div class="oe_button_box" name="button_box">
                        <button class="oe_stat_button" type="object"
                            name="action_view_backups" icon="fa-archive">
                            <field name="backup_count" widget="statinfo" string="Backups"/>
                        </button>
                        <button class="oe_stat_button" type="object"
                            name="action_open_tenant" icon="fa-external-link"
                            attrs="{'invisible': [('state','!=','active')]}">
                            <span class="o_stat_text">Open ERP</span>
                        </button>
                    </div>
                    <div class="oe_title">
                        <h1><field name="name" placeholder="Tenant Name"/></h1>
                        <h3>
                            <field name="tenant_url" widget="url"/>
                        </h3>
                    </div>

                    <group>
                        <group string="Customer Info">
                            <field name="customer_name"/>
                            <field name="customer_email"/>
                            <field name="phone"/>
                            <field name="company_name"/>
                        </group>
                        <group string="Subscription">
                            <field name="plan_id"/>
                            <field name="expiry_date"/>
                            <field name="template_db"/>
                        </group>
                    </group>

                    <group string="Domain &amp; Database">
                        <group>
                            <field name="subdomain"/>
                            <field name="custom_domain"/>
                        </group>
                        <group>
                            <field name="db_name" readonly="1"/>
                            <field name="db_user" readonly="1"/>
                        </group>
                    </group>

                    <group string="Admin Credentials">
                        <field name="admin_login"/>
                        <field name="admin_password" password="True"/>
                    </group>

                    <group string="Monitoring" attrs="{'invisible': [('db_name','=',False)]}">
                        <group>
                            <field name="db_size_mb" readonly="1"/>
                            <field name="filestore_size_mb" readonly="1"/>
                        </group>
                        <group>
                            <field name="user_count" readonly="1"/>
                            <field name="last_login_date" readonly="1"/>
                            <field name="last_backup_date" readonly="1"/>
                        </group>
                    </group>

                    <group string="Installed Modules" attrs="{'invisible': [('installed_modules','=',False)]}">
                        <field name="installed_modules" nolabel="1" colspan="2" readonly="1"/>
                    </group>

                    <notebook>
                        <page string="Backup History">
                            <field name="backup_ids" mode="tree">
                                <tree>
                                    <field name="backup_date"/>
                                    <field name="size_mb"/>
                                    <field name="state" widget="badge"/>
                                    <button name="action_restore" type="object" string="Restore" icon="fa-undo"/>
                                </tree>
                            </field>
                        </page>
                        <page string="Notes">
                            <field name="notes"/>
                        </page>
                    </notebook>
                </sheet>
                <div class="oe_chatter">
                    <field name="message_follower_ids"/>
                    <field name="activity_ids"/>
                    <field name="message_ids"/>
                </div>
            </form>
        </field>
    </record>

    <!-- Search -->
    <record id="view_saas_tenant_search" model="ir.ui.view">
        <field name="name">saas.tenant.search</field>
        <field name="model">saas.tenant</field>
        <field name="arch" type="xml">
            <search string="Search Tenants">
                <field name="name"/>
                <field name="customer_name"/>
                <field name="customer_email"/>
                <field name="subdomain"/>
                <field name="plan_id"/>
                <filter name="active" string="Active" domain="[('state','=','active')]"/>
                <filter name="suspended" string="Suspended" domain="[('state','=','suspended')]"/>
                <filter name="expired" string="Expired" domain="[('state','=','expired')]"/>
                <filter name="draft" string="Draft" domain="[('state','=','draft')]"/>
                <separator/>
                <filter name="expiring_soon" string="Expiring in 7 days"
                    domain="[('expiry_date','&lt;=',(context_today()+datetime.timedelta(7)).strftime('%Y-%m-%d')),('state','=','active')]"/>
                <group expand="0" string="Group By">
                    <filter name="group_plan" string="Plan" context="{'group_by': 'plan_id'}"/>
                    <filter name="group_state" string="Status" context="{'group_by': 'state'}"/>
                </group>
            </search>
        </field>
    </record>

    <!-- Action -->
    <record id="action_saas_tenant" model="ir.actions.act_window">
        <field name="name">Tenants</field>
        <field name="res_model">saas.tenant</field>
        <field name="view_mode">kanban,tree,form</field>
        <field name="search_view_id" ref="view_saas_tenant_search"/>
        <field name="context">{'search_default_active': 1}</field>
    </record>
</odoo>
"""

# ─────────────────────────────────────────────────────
# views/saas_menu.xml
# ─────────────────────────────────────────────────────
MENU_XML = """<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Root menu -->
    <menuitem id="menu_saas_root"
        name="SaaS Management"
        web_icon="saas_tenant_manager,static/description/icon.png"
        sequence="1"/>

    <!-- Dashboard -->
    <menuitem id="menu_saas_dashboard"
        name="Dashboard"
        parent="menu_saas_root"
        action="action_saas_tenant"
        sequence="1"/>

    <!-- Tenants -->
    <menuitem id="menu_saas_tenants"
        name="Tenants"
        parent="menu_saas_root"
        action="action_saas_tenant"
        sequence="2"/>

    <!-- Plans -->
    <menuitem id="menu_saas_plans"
        name="Subscription Plans"
        parent="menu_saas_root"
        action="action_saas_plan"
        sequence="3"/>

    <!-- Backups -->
    <menuitem id="menu_saas_backups"
        name="Tenant Backups"
        parent="menu_saas_root"
        action="action_saas_backup"
        sequence="4"/>

    <!-- New Tenant Wizard -->
    <menuitem id="menu_saas_new_tenant"
        name="New Tenant"
        parent="menu_saas_root"
        action="action_create_tenant_wizard"
        sequence="5"/>
</odoo>
"""

# ─────────────────────────────────────────────────────
# data/saas_plan_data.xml — default plans
# ─────────────────────────────────────────────────────
PLAN_DATA = """<?xml version="1.0" encoding="utf-8"?>
<odoo noupdate="1">
    <record id="plan_starter" model="saas.plan">
        <field name="name">Starter</field>
        <field name="code">STARTER</field>
        <field name="max_users">5</field>
        <field name="max_storage_mb">1024</field>
        <field name="monthly_price">299</field>
        <field name="yearly_price">2990</field>
        <field name="trial_days">14</field>
        <field name="allowed_modules">base,mail,account,sale,purchase</field>
        <field name="color">10</field>
    </record>

    <record id="plan_business" model="saas.plan">
        <field name="name">Business</field>
        <field name="code">BUSINESS</field>
        <field name="max_users">25</field>
        <field name="max_storage_mb">5120</field>
        <field name="monthly_price">899</field>
        <field name="yearly_price">8990</field>
        <field name="trial_days">14</field>
        <field name="allowed_modules">base,mail,account,sale,purchase,stock,mrp,hr</field>
        <field name="color">4</field>
    </record>

    <record id="plan_enterprise" model="saas.plan">
        <field name="name">Enterprise</field>
        <field name="code">ENTERPRISE</field>
        <field name="max_users">999</field>
        <field name="max_storage_mb">51200</field>
        <field name="monthly_price">2499</field>
        <field name="yearly_price">24990</field>
        <field name="trial_days">30</field>
        <field name="allowed_modules">base,mail,account,sale,purchase,stock,mrp,hr,project,helpdesk,website</field>
        <field name="color">1</field>
    </record>
</odoo>
"""

# ─────────────────────────────────────────────────────
# data/saas_cron.xml
# ─────────────────────────────────────────────────────
CRON_XML = """<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Daily backup of all active tenants -->
    <record id="cron_backup_all_tenants" model="ir.cron">
        <field name="name">SaaS: Daily Tenant Backup</field>
        <field name="model_id" ref="model_saas_tenant"/>
        <field name="state">code</field>
        <field name="code">model.cron_backup_all_tenants()</field>
        <field name="interval_number">1</field>
        <field name="interval_type">days</field>
        <field name="numbercall">-1</field>
        <field name="active">True</field>
        <field name="priority">100</field>
    </record>

    <!-- Update stats every 6 hours -->
    <record id="cron_update_all_stats" model="ir.cron">
        <field name="name">SaaS: Update Tenant Stats</field>
        <field name="model_id" ref="model_saas_tenant"/>
        <field name="state">code</field>
        <field name="code">model.cron_update_all_stats()</field>
        <field name="interval_number">6</field>
        <field name="interval_type">hours</field>
        <field name="numbercall">-1</field>
        <field name="active">True</field>
    </record>

    <!-- Check expired tenants daily -->
    <record id="cron_check_expired" model="ir.cron">
        <field name="name">SaaS: Check Expired Tenants</field>
        <field name="model_id" ref="model_saas_tenant"/>
        <field name="state">code</field>
        <field name="code">model.cron_check_expired_tenants()</field>
        <field name="interval_number">1</field>
        <field name="interval_type">days</field>
        <field name="numbercall">-1</field>
        <field name="active">True</field>
    </record>
</odoo>
"""

# ─────────────────────────────────────────────────────
# wizards/__init__.py
# ─────────────────────────────────────────────────────
WIZARDS_INIT = "from . import create_tenant_wizard\n"

# ─────────────────────────────────────────────────────
# wizards/create_tenant_wizard.py
# ─────────────────────────────────────────────────────
WIZARD_PY = """import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class CreateTenantWizard(models.TransientModel):
    _name = 'create.tenant.wizard'
    _description = 'Create New Tenant Wizard'

    # Step 1: Customer
    customer_name = fields.Char(string='Customer Name', required=True)
    customer_email = fields.Char(string='Customer Email', required=True)
    company_name = fields.Char(string='Company Name', required=True)
    phone = fields.Char(string='Phone')

    # Step 2: Domain
    subdomain = fields.Char(string='Subdomain', required=True,
        help='e.g. "mycompany" for mycompany.myerp.com')
    custom_domain = fields.Char(string='Custom Domain (optional)')

    # Step 3: Plan
    plan_id = fields.Many2one('saas.plan', string='Subscription Plan', required=True)

    # Step 4: Template
    template_db = fields.Char(string='Template Database',
        help='Leave empty to create fresh installation')

    # Step 5: Admin
    admin_login = fields.Char(string='Admin Login', default='admin')
    admin_password = fields.Char(string='Admin Password', required=True)

    # Preview
    tenant_url_preview = fields.Char(
        string='Tenant URL', compute='_compute_url_preview'
    )

    @api.depends('subdomain', 'custom_domain')
    def _compute_url_preview(self):
        for w in self:
            if w.custom_domain:
                w.tenant_url_preview = f'https://{w.custom_domain}'
            elif w.subdomain:
                w.tenant_url_preview = f'https://{w.subdomain}.myerp.com'
            else:
                w.tenant_url_preview = ''

    def action_create(self):
        self.ensure_one()
        # Check subdomain not taken
        existing = self.env['saas.tenant'].search([
            ('subdomain', '=', self.subdomain)
        ])
        if existing:
            raise ValidationError(f'Subdomain "{self.subdomain}" is already taken.')

        tenant = self.env['saas.tenant'].create({
            'name': f'{self.company_name} ERP',
            'customer_name': self.customer_name,
            'customer_email': self.customer_email,
            'company_name': self.company_name,
            'phone': self.phone,
            'subdomain': self.subdomain,
            'custom_domain': self.custom_domain,
            'plan_id': self.plan_id.id,
            'template_db': self.template_db,
            'admin_login': self.admin_login,
            'admin_password': self.admin_password,
        })

        # Provision
        tenant.action_create_tenant()

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'saas.tenant',
            'res_id': tenant.id,
            'view_mode': 'form',
            'target': 'current',
        }
"""

# ─────────────────────────────────────────────────────
# wizards/create_tenant_wizard.xml
# ─────────────────────────────────────────────────────
WIZARD_XML = """<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_create_tenant_wizard_form" model="ir.ui.view">
        <field name="name">create.tenant.wizard.form</field>
        <field name="model">create.tenant.wizard</field>
        <field name="arch" type="xml">
            <form string="Create New Tenant">
                <group string="Customer Information">
                    <field name="customer_name"/>
                    <field name="customer_email"/>
                    <field name="company_name"/>
                    <field name="phone"/>
                </group>
                <group string="Domain">
                    <field name="subdomain"/>
                    <field name="custom_domain"/>
                    <field name="tenant_url_preview" readonly="1"/>
                </group>
                <group string="Subscription">
                    <field name="plan_id"/>
                    <field name="template_db"/>
                </group>
                <group string="Admin Credentials">
                    <field name="admin_login"/>
                    <field name="admin_password" password="True"/>
                </group>
                <footer>
                    <button name="action_create" type="object"
                        string="🚀 Create Tenant" class="btn-primary"/>
                    <button string="Cancel" class="btn-secondary" special="cancel"/>
                </footer>
            </form>
        </field>
    </record>

    <record id="action_create_tenant_wizard" model="ir.actions.act_window">
        <field name="name">New Tenant</field>
        <field name="res_model">create.tenant.wizard</field>
        <field name="view_mode">form</field>
        <field name="target">new</field>
    </record>
</odoo>
"""

# ─────────────────────────────────────────────────────
# controllers/__init__.py and main.py
# ─────────────────────────────────────────────────────
CONTROLLERS_INIT = "from . import main\n"

CONTROLLER_MAIN = """import logging
from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


class SaasController(http.Controller):

    @http.route('/saas/health', auth='none', type='http', methods=['GET'])
    def health_check(self, **kwargs):
        return Response('OK', status=200, content_type='text/plain')

    @http.route('/saas/suspended', auth='none', type='http', methods=['GET'])
    def suspended_page(self, **kwargs):
        \"\"\"Shown when a tenant is suspended.\"\"\"
        return request.render('saas_tenant_manager.page_suspended', {})
"""

print('── Uploading views, security, cron, wizard ──')
upload(f'{BASE}/security/saas_security.xml', SECURITY_XML)
upload(f'{BASE}/security/ir.model.access.csv', ACCESS_CSV)
upload(f'{BASE}/views/saas_plan_views.xml', PLAN_VIEWS)
upload(f'{BASE}/views/saas_backup_views.xml', BACKUP_VIEWS)
upload(f'{BASE}/views/saas_tenant_views.xml', TENANT_VIEWS)
upload(f'{BASE}/views/saas_menu.xml', MENU_XML)
upload(f'{BASE}/data/saas_plan_data.xml', PLAN_DATA)
upload(f'{BASE}/data/saas_cron.xml', CRON_XML)
upload(f'{BASE}/wizards/__init__.py', WIZARDS_INIT)
upload(f'{BASE}/wizards/create_tenant_wizard.py', WIZARD_PY)
upload(f'{BASE}/wizards/create_tenant_wizard.xml', WIZARD_XML)
upload(f'{BASE}/controllers/__init__.py', CONTROLLERS_INIT)
upload(f'{BASE}/controllers/main.py', CONTROLLER_MAIN)
print('\n✅ Part 3 done!')
ssh.close()
