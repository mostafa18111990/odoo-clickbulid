#!/usr/bin/env python3
"""Update module list and install saas_tenant_manager"""
import sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

try:
    import xmlrpc.client as xc
except ImportError:
    import xmlrpclib as xc

URL  = 'https://odoo.clickbulid.com'
DB   = 'odoo'
USER = 'admin'
PASS = '123456'

common = xc.ServerProxy(URL + '/xmlrpc/2/common', allow_none=True)
models = xc.ServerProxy(URL + '/xmlrpc/2/object', allow_none=True)

# Authenticate
print('Authenticating...')
uid = common.authenticate(DB, USER, PASS, {})
if not uid:
    print('❌ Authentication failed!')
    sys.exit(1)
print(f'✅ UID: {uid}')

def call(model, method, *args, **kwargs):
    return models.execute_kw(DB, uid, PASS, model, method, list(args), kwargs)

# Step 1: Update module list
print('\nUpdating module list...')
call('ir.module.module', 'update_list')
print('✅ Module list updated')

# Step 2: Find our module
print('\nSearching for saas_tenant_manager...')
mods = call('ir.module.module', 'search_read',
    [('name', '=', 'saas_tenant_manager')],
    fields=['name', 'state', 'installed_version'],
    limit=5
)
if not mods:
    print('❌ Module not found! Check addons path.')
    sys.exit(1)

mod = mods[0]
print(f'  Module: {mod["name"]}')
print(f'  State:  {mod["state"]}')
print(f'  Version: {mod.get("installed_version", "N/A")}')

if mod['state'] == 'installed':
    print('✅ Module already installed!')
    sys.exit(0)

# Step 3: Install
print('\nInstalling saas_tenant_manager...')
call('ir.module.module', 'button_immediate_install', [mod['id']])
print('Installation triggered. Waiting 30s...')
time.sleep(30)

# Step 4: Verify
mods2 = call('ir.module.module', 'search_read',
    [('name', '=', 'saas_tenant_manager')],
    fields=['name', 'state', 'installed_version'],
    limit=1
)
if mods2:
    m = mods2[0]
    print(f'\nFinal state: {m["state"]}')
    if m['state'] == 'installed':
        print('✅ saas_tenant_manager installed successfully!')
    else:
        print('⚠️  State is:', m['state'])
else:
    print('Module not found after install attempt')
