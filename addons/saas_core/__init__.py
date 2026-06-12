from . import mixins
from . import models
from . import repositories
from . import services
from . import controllers


def post_init_hook(env):
    tenants = env['saas.tenant'].search([('state', 'in', ['draft', 'expired'])])
    for tenant in tenants:
        new_state = 'trial' if tenant.state == 'draft' else 'archived'
        env.cr.execute("UPDATE saas_tenant SET state = %s WHERE id = %s", (new_state, tenant.id))
